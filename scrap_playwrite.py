from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup

def fetch_with_playwright(url, wait_time=10, take_screenshot=False, screenshot_path="flipkart_screenshot.png"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        for _ in range(10):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(1000)

        page.wait_for_timeout(5000)

        html = page.content()

        if take_screenshot:
            try:
                page.screenshot(path=screenshot_path, full_page=True, timeout=5000)
            except TimeoutError:
                print("⚠️ Screenshot skipped due to font loading timeout.")

        with open("flipkart_live_detail.html", "w", encoding="utf-8") as f:
            f.write(html)

        browser.close()
        return html

def parse_amazon(query):
    url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
    html = fetch_with_playwright(url, wait_time=10)

    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.s-main-slot div[data-component-type='s-search-result']")
    if not product:
        print("❌ Amazon: No product tile found.")
        return None

    title_tag = product.select_one("h2 span")
    price_span = product.select_one("span.a-offscreen")
    link_tag = product.select_one("a.a-link-normal.s-no-outline")

    return {
        "platform": "Amazon",
        "title": title_tag.text.strip() if title_tag else "N/A",
        "price": price_span.text.strip() if price_span else "N/A",
        "link": "https://www.amazon.in" + link_tag.get("href", "") if link_tag else "N/A"
    }

def parse_flipkart(query):
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    html = fetch_with_playwright(url, wait_time=10, take_screenshot=True)

    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("a.CGtC98")
    if not product:
        print("❌ Flipkart: No matching product tile found.")
        with open("flipkart_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        return None

    title_tag = product.select_one("div.KzDlHZ") or product.select_one("div.cPHDOP")
    price_tag = product.select_one("div.Nx9bqj") or product.select_one("div._30jeq3")

    return {
        "platform": "Flipkart",
        "title": title_tag.text.strip() if title_tag else "N/A",
        "price": price_tag.text.strip() if price_tag else "N/A",
        "link": "https://www.flipkart.com" + product.get("href", "")
    }

from playwright.sync_api import sync_playwright, TimeoutError
import re

from playwright.sync_api import sync_playwright

def fetch_product_details_with_playwright(url):
    data = {
        "rating": "N/A",
        "reviews": "N/A",
        "price": "N/A",
        "mrp": "N/A",
        "discount": "N/A",
        "highlights": [],
        "offers": [],
        "description": "N/A"
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_load_state("domcontentloaded")

        print("⏳ Scrolling for hydration...")
        for _ in range(6):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)

        print("✅ DOM Snapshot:\n", page.title())

        # 🔹 Add your verified class names here:
        class_map = {
            "price": "div.Nx9bqj CxhGGd",                # ✅ Selling Price
            "mrp": "div.yRaY8j A6+E6v",                 # ✅ MRP
            "discount": "div._3Ay6Sb span",       # ✅ Discount %
            "rating": "div._3LWZlK",              # ✅ Rating
            "reviews": "span._2_R_DZ",            # ✅ Ratings & Reviews
            "description": "div._1mXcCf span",    # ✅ Short description
            "highlights": "div._2418kt ul li",    # ✅ Bullet specs
            "offers": "div._2RzXYy div._3TT44I"   # ✅ Offers (bank/coupon)
        }

        for key, selector in class_map.items():
            try:
                if key in ["highlights", "offers"]:
                    elements = page.locator(selector).all()
                    data[key] = [el.inner_text().strip() for el in elements if el.inner_text().strip()]
                else:
                    locator = page.locator(selector).first
                    if locator.is_visible():
                        data[key] = locator.inner_text().strip()
            except Exception as e:
                print(f"⚠️ Could not fetch {key}: {e}")

        # 💾 Save DOM
        with open("flipkart_live_detail.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        # 📸 Screenshot (optional)
        try:
            page.screenshot(path="flipkart_screenshot.png", full_page=True)
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")

        browser.close()
        return data








def aggregate_prices(query):
    return [parse_amazon(query)]

if __name__ == "__main__":
    query = "Narzo 70 Pro 5G"
    results = aggregate_prices(query)
    for r in results:
        print("\n=== Amazon ===")
        if r:
            for key, value in r.items():
                print(f"{key}: {value}")
        else:
            print("No result.")

    product_info = parse_flipkart(query)
    if product_info:
        print("\n=== Flipkart Basic ===")
        for key, value in product_info.items():
            print(f"{key}: {value}")

        details = fetch_product_details_with_playwright(product_info["link"])

        product_info.update(details)

        print("\n=== Flipkart Full Details ===")
        for k, v in product_info.items():
            if isinstance(v, list):
                print(f"{k}:")
                for item in v:
                    print(f"  - {item}")
            else:
                print(f"{k}: {v}")
    else:
        print("❌ Flipkart: No product found.")
