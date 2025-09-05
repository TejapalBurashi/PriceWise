import requests
from bs4 import BeautifulSoup

ZENROWS_API_KEY = "30c5bd2c1bc7e5e877829f72f49904698fa023ba"

def fetch_page(url):
    params = {
        "apikey": ZENROWS_API_KEY,
        "js_render": "true",  # JS rendering
        "premium_proxy": "true",  # Avoid block (optional, works on free tier)
        "wait_for": "div._30jeq3",
        "wait": "3000"
    }
    response = requests.get("https://api.zenrows.com/v1", params={**params, "url": url})
    return response.text

def parse_amazon(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")

    product = soup.select_one("div.s-main-slot div[data-component-type='s-search-result']")
    if not product:
        print("No product tile found.")
        return None

    title_tag = product.select_one("h2 span")
    title = title_tag.text.strip() if title_tag else "N/A"

    price_span = product.select_one("span.a-offscreen")
    price = price_span.text.strip() if price_span else "N/A"

    link_tag = product.select_one("a.a-link-normal.s-line-clamp-2")
    link = "https://www.amazon.in" + link_tag.get("href", "") if link_tag else "N/A"


    


    return {
        "platform": "Amazon",
        "title": title,
        "price": price,
        "link": link
    }




def parse_flipkart(query):
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    html = fetch_page(url)
    soup = BeautifulSoup(html, "html.parser")

    # Try new product tile class
    product = soup.select_one("a.CGtC98")

    if not product:
        print("❌ Flipkart: No matching product tile found.")
        with open("flipkart_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        return None

    # Extract title and price using updated class names
    title_tag = product.select_one("div.KzDlHZ")  # New title class
    price_tag = product.select_one("div.Nx9bqj")  # New price class

    return {
        "platform": "Flipkart",
        "title": title_tag.text.strip() if title_tag else "N/A",
        "price": price_tag.text.strip() if price_tag else "N/A",
        "link": "https://www.flipkart.com" + product.get("href", "")
    }


def fetch_product_details(product_url):
    html = fetch_page(product_url)
    soup = BeautifulSoup(html, "html.parser")

    # ✅ Rating & Reviews
    rating = soup.select_one("div._3LWZlK")
    review_count = soup.select_one("span._2_R_DZ span span")

    # ✅ Price details (Current Price, MRP, Discount)
    price = soup.select_one("div._30jeq3")
    mrp = soup.select_one("div._3I9_wc")
    discount = soup.select_one("div._3Ay6Sb span")

    # ✅ Highlights (Specifications)
    highlights = [li.text.strip() for li in soup.select("ul._1xgFaf li")]

    # ✅ Offers
    offers = [li.text.strip() for li in soup.select("div._16eBzU li")]

    # ✅ Description
    desc_tag = soup.select_one("div._1mXcCf span") or soup.select_one("div._1mXcCf > div")
    description = desc_tag.text.strip() if desc_tag else "N/A"

    return {
        "rating": rating.text.strip() if rating else "N/A",
        "reviews": review_count.text.strip() if review_count else "N/A",
        "price": price.text.strip() if price else "N/A",
        "mrp": mrp.text.strip() if mrp else "N/A",
        "discount": discount.text.strip() if discount else "N/A",
        "highlights": highlights if highlights else [],
        "offers": offers if offers else [],
        "description": description
    }




def aggregate_prices(query):
    return [
        parse_amazon(query),
    ]

# Example:
query = "Redmi 13C 5G"
results = aggregate_prices(query)
for r in results:
    print(r)

product_info = parse_flipkart("Redmi 13C 5G")
details = fetch_product_details(product_info["link"])

product_info.update(details)
print(product_info)



