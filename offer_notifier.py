import sqlite3
import datetime
import pytz
import time
from twilio.rest import Client

DB_PATH = "users.db"

def send_whatsapp(phone, title, platform):
    account_sid = 'AC73e49b3c63c9a67ac6a0a2475ba96298'
    auth_token = '7011fe68eb63139f1d49f306feafd96e'
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_='whatsapp:++14155238886',
        to=f'whatsapp:+91{phone}',
        body=f"⚠️ Hurry! The offer on *{title}* ({platform}) is expiring soon!"
    )
    print(f"Sent WhatsApp to {phone}: {message.sid}")

def check_offer_expiry():
    while True:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))

        cur.execute("""
            SELECT w.title, w.platform, w.expiry_time, u.phno
            FROM wishlist w
            JOIN users u ON w.user_id = u.id
        """)
        for row in cur.fetchall():
            title, platform, expiry_time, phone = row
            expiry_dt = datetime.datetime.fromisoformat(expiry_time).astimezone(pytz.timezone("Asia/Kolkata"))

            time_left = (expiry_dt - now).total_seconds()
            if 0 < time_left < 300:  # Less than 5 minutes left
                send_whatsapp(phone, title, platform)

        conn.close()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    check_offer_expiry()
