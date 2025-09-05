from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pandas.tseries.offsets import DateOffset
from scrapping import aggregate_basic
from serpapi import GoogleSearch
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from twilio.rest import Client

import sqlite3
import pytz
import pickle
import pandas as pd
import numpy as np
import threading
import time
import os




load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Twilio config from .env
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")

# Initialize model
model = ChatGroq(model="llama3-8b-8192", groq_api_key=groq_api_key)

# ✅ DB INIT
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Always check and create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            phno TEXT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wishlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        platform TEXT,
        price TEXT,
        expiry_time TEXT,
        notified INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS delivery_days (
        pincode TEXT PRIMARY KEY,
        days_required INTEGER
    )
""")

    conn.commit()
    conn.close()


# DB QUERIES
def get_user_by_email(email):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()
    return user

def insert_user(username, phno, email, password_hash):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, phno, email, password) VALUES (?, ?, ?, ?)",
                (username, phno, email, password_hash))
    conn.commit()
    conn.close()

#  PROTECT ROUTE
def login_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect("/login")
        return func(*args, **kwargs)
    return decorated_function

# ROUTES
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question")

    if not question:
        return jsonify({"answer": "Please provide a valid question."}), 400

    try:
        prompt = f"Answer the following question in only 3-4 bullet points:\n\n{question}"
        response = model.invoke([HumanMessage(content=prompt)])
        return jsonify({"answer": response.content})
    except Exception as e:
        return jsonify({"answer": f"Error: {str(e)}"}), 500

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        phno = request.form["phno"]
        email = request.form["email"]
        password = request.form["password"]

        if get_user_by_email(email):
            flash("Email already registered. Try logging in.", "error")
            return redirect("/login")

        password_hash = generate_password_hash(password)
        insert_user(username, phno, email, password_hash)
        flash("Signup successful! Please log in.", "success")
        return redirect("/login")

    return render_template("signup.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = get_user_by_email(email)
        if user and check_password_hash(user[4], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash("Login successful!", "success")
            return redirect("/")  
        else:
            flash("Invalid credentials. Try again.", "error")
            return redirect("/login")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect("/login")

@app.route('/search_index', methods=['GET'])
def search_index():
    product = request.args.get('q')
    min_price = request.args.get('min', type=int)
    max_price = request.args.get('max', type=int)

    if not product:
        return jsonify({"error": "Please provide a product name using ?q=product_name"}), 400

    try:
        params = {
            "engine": "google_shopping",
            "q": product,
            "api_key": SERPAPI_KEY,
            "gl": "in"
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        items = results.get("shopping_results", [])

        products = []
        for item in items:
            price_str = item.get("price")
            if not price_str:
                continue
            try:
                clean_price = int(''.join(filter(str.isdigit, price_str)))
            except:
                continue

            if (min_price and clean_price < min_price) or (max_price and clean_price > max_price):
                continue

            products.append({
                "title": item.get("title"),
                "price": clean_price,
                "platform": item.get("source"),
                "link": item.get("link"),
                "image": item.get("thumbnail"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews")
            })

        return jsonify({"products": products})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/compare', methods=["GET", "POST"])
@login_required
def compare():
    return render_template("compare.html")

@app.route('/green', methods=["GET", "POST"])
@login_required
def green():
    return render_template("green.html")

@app.route('/search', methods=['POST'])
@login_required
def search():
    query = request.form.get("product")
    results = aggregate_basic(query)
    return jsonify(results)

@app.route("/details")
@login_required
def show_details():

    raw_discount = request.args.get("discount", "0")
    cleaned_discount = ''.join(c for c in raw_discount if c.isdigit() or c == '.')
    discount_value = float(cleaned_discount) if cleaned_discount else 0.0

    raw_rating = request.args.get("rating", "0")
    cleaned_rating = ''.join(c for c in raw_rating if c.isdigit() or c == '.')
    rating_value = float(cleaned_rating) if cleaned_rating else 0.0

    data = {
        "platform": request.args.get("platform", "N/A"),
        "title": request.args.get("title", "N/A"),
        "price": request.args.get("price", "N/A"),
        "mrp": request.args.get("mrp", "N/A"),
        "discount": request.args.get("discount", "0"),
        "rating": request.args.get("rating", "0"),
        "image_url": request.args.get("image_url", "#"),
        "category": request.args.get("category", "Fashion"),
        "link": request.args.get("link", "#") 
    }
    

    try:
        with open("fprice_forecast_model.pkl", "rb") as f:
            model = pickle.load(f)

        np.random.seed(42)
        rating_variation = np.clip(rating_value + np.random.normal(0, 0.2, 4), 1, 5)
        stock_variation = np.clip(100 + np.random.normal(0, 10, 4), 10, 500).astype(int)
        discount_variation = np.clip(discount_value + np.random.normal(0, 2, 4), 0, 100)
        month_number_start = 32
        future_months = pd.date_range(start=datetime.now() + DateOffset(months=1), periods=4, freq="MS")

        future_data = pd.DataFrame({
            "Category": [data["category"]] * 4,
            "Rating": rating_variation,
            "Stock": stock_variation,
            "Discount (%)": discount_variation,
            "MonthNumber": [month_number_start + i for i in range(4)],
            "Month": future_months.strftime("%B %Y")
        })

        future_data["PredictedPrice"] = model.predict(
            future_data[["Category", "Rating", "Stock", "Discount (%)", "MonthNumber"]]
        )

        data["future_predictions"] = future_data[["Month", "PredictedPrice"]].to_dict(orient="records")

    except Exception as e:
        print("ML Prediction error:", e)
        data["future_predictions"] = []

    return render_template("more_info.html", **data)


@app.route('/add_to_wishlist', methods=["POST"])
@login_required
def add_to_wishlist():
    data = request.json
    expiry_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata")) + datetime.timedelta(minutes=5)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO wishlist (user_id, title, platform, price, expiry_time)
        VALUES (?, ?, ?, ?, ?)
    """, (session['user_id'], data['title'], data['platform'], data['price'], expiry_time.isoformat()))
    conn.commit()
    conn.close()
    return jsonify({"status": "added"})


#--- Missed Discount Notification using Twillo

import time
from twilio.rest import Client
DB_PATH = "users.db"

def send_whatsapp(phone, title, platform):
    account_sid = TWILIO_SID
    auth_token = TWILIO_AUTH_TOKEN
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_='whatsapp:'+TWILIO_NUMBER,
        to=f'whatsapp:+91{phone}',
        body=f"⚠️ Hurry! The offer on *{title}* ({platform}) is expiring soon!"
    )
    print(f"Sent WhatsApp to {phone}: {message.sid}")

def check_offer_expiry():
    while True:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.now(pytz.timezone("Asia/Kolkata")) 

        # Only select items that are not yet notified
        cur.execute("""
            SELECT w.id, w.title, w.platform, w.expiry_time, u.phno
            FROM wishlist w
            JOIN users u ON w.user_id = u.id
            WHERE w.notified = 0
        """)

        for row in cur.fetchall():
            wishlist_id, title, platform, expiry_time, phone = row
            try:
                expiry_dt = datetime.datetime.fromisoformat(expiry_time).astimezone(pytz.timezone("Asia/Kolkata"))
                time_left = (expiry_dt - now).total_seconds()

                if 0 < time_left < 300:
                    send_whatsapp(phone, title, platform)

                    # Mark as notified
                    cur.execute("UPDATE wishlist SET notified = 1 WHERE id = ?", (wishlist_id,))
                    conn.commit()

            except Exception as e:
                print(f"[ERROR] Failed to check/notify for {title}: {e}")

        conn.close()
        time.sleep(60)  # check every 60 second

#---Get Delivery Details

from datetime import datetime, timedelta

@app.route('/get_delivery_date', methods=['POST'])
@login_required
def get_delivery_date():
    pincode = request.json.get("pincode")
    if not pincode or not pincode.isdigit() or len(pincode) != 6:
        return jsonify({"error": "Invalid pincode"}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT days_required, distance FROM delivery_days WHERE pincode = ?", (pincode,))
    row = cur.fetchone()
    conn.close()

    if row:
        days_required, distance = row
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
        delivery_date = now + timedelta(days=days_required)
        formatted_date = delivery_date.strftime("%d %B %Y, %A")
        sustainable = "Yes ✅" if distance < 500 else "No ❌"

        return jsonify({
            "expected_delivery": formatted_date,
            "distance_km": distance,
            "sustainable": sustainable
        })
    else:
        return jsonify({"error": "Delivery info not available for this pincode"}), 404



# --- WISHLIST


def get_wishlist_items(user_id):
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM wishlist WHERE user_id = ?", (user_id,))
    items = cur.fetchall()
    conn.close()
    return items

@app.route('/wishlist')
def show_wishlist():
    user_id = session.get('user_id')
    if not user_id:
        return "User not logged in", 401  # or redirect to login

    raw_items = get_wishlist_items(user_id)
    items = []

    for row in raw_items:
        item = dict(row)
        expiry_str = item.get('expiry_time')

        if expiry_str:
            try:
                expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                delta = expiry_dt - datetime.now()
                item['remaining_days'] = max(delta.days, 0)
                item['is_expired'] = delta.total_seconds() < 0
            except ValueError:
                item['remaining_days'] = None
                item['is_expired'] = False
        else:
            item['remaining_days'] = None
            item['is_expired'] = False

        items.append(item)

    return render_template('wishlist.html', items=items)

import threading

if __name__ == "__main__":
    init_db()
    threading.Thread(target=check_offer_expiry, daemon=True).start()
    app.run(debug=True)

