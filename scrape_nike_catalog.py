"""
Nike Product Catalog Scraper
Runs in GitHub Actions via Playwright (headless Chromium)
Fetches real Nike product data and saves to data/nike_catalog.csv
"""

import json
import csv
import os
import sys
import time
from playwright.sync_api import sync_playwright


OUTPUT_FILE = "data/nike_catalog.csv"
FIELDNAMES  = [
    "SKU / Product ID", "Product Name", "Subtitle",
    "Colorway", "Gender", "Category",
    "Retail Price ($)", "Full Price ($)", "Status", "In Stock",
]

CATEGORY_PAGES = [
    ("https://www.nike.com/w/mens-shoes-nik1zy7ok",    "Men's Shoes",   "Men"),
    ("https://www.nike.com/w/womens-shoes-5e1x6zy7ok", "Women's Shoes", "Women"),
    ("https://www.nike.com/w/jordan-shoes-37eefzy7ok",  "Jordan Shoes",  "Men"),
    ("https://www.nike.com/w/running-shoes-37v7jzy7ok", "Running Shoes", "Unisex"),
]


def parse_product(p: dict, category: str, gender: str) -> dict:
    price     = p.get("price") or {}
    cur_price = price.get("currentPrice") or price.get("fullPrice") or ""
    full_price= price.get("fullPrice") or cur_price
    in_stock  = p.get("inStock", True)
    label     = str(p.get("label", ""))

    on_sale = False
    try:
        on_sale = (float(str(cur_price).replace(",","") or 0) <
                   float(str(full_price).replace(",","") or 1))
    except Exception:
        pass

    if "New" in label or "Just In" in label:
        status = "NEW"
    elif on_sale:
        status = "SALE"
    elif not in_stock:
        status = "OUT OF STOCK"
    else:
        status = "ACTIVE"

    return {
        "SKU / Product ID": p.get("pid", ""),
        "Product Name":     p.get("title", ""),
        "Subtitle":         p.get("subtitle", ""),
        "Colorway":         p.get("colorDescription", ""),
        "Gender":           gender,
        "Category":         category,
        "Retail Price ($)": cur_price,
        "Full Price ($)":   full_price,
        "Status":           status,
        "In Stock":         "Yes" if in_stock else "No",
    }


def scrape_category(page, url: str, category: str, gender: str) -> list:
    """Navigate to Nike category page and intercept the product API response."""
    products = []
    api_responses = []

    def handle_response(response):
        """Capture API calls Nike's site makes to load products."""
        if "api.nike.com" in response.url and response.status == 200:
            try:
                data = response.json()
                prods = (data.get("data", {})
                             .get("products", {})
                             .get("products", []))
                if prods:
                    api_responses.extend(prods)
                    print(f"   Intercepted {len(prods)} products from API")
            except Exception:
                pass

    page.on("response", handle_response)

    print(f"   Loading: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)  # wait for additional API calls
    except Exception as ex:
        print(f"   Page load warning: {ex}")

    page.remove_listener("response", handle_response)

    if api_responses:
        for p in api_responses:
            if isinstance(p, dict):
                products.append(parse_product(p, category, gender))
        print(f"   Got {len(products)} products via API interception")
    else:
        # Fallback: extract from page JSON
        print("   Trying page JSON extraction...")
        try:
            content = page.content()
            import re
            # Nike embeds product data in __NEXT_DATA__ script tag
            match = re.search(r'"products":\{"products":\[(.*?)\],"pages"', content, re.DOTALL)
            if match:
                raw = json.loads("[" + match.group(1) + "]")
                for p in raw:
                    if isinstance(p, dict):
                        products.append(parse_product(p, category, gender))
                print(f"   Got {len(products)} products via page extraction")
        except Exception as ex:
            print(f"   Page extraction failed: {ex}")

    return products


def main():
    os.makedirs("data", exist_ok=True)
    all_products = []

    print("=" * 55)
    print("  Nike Catalog Scraper — GitHub Actions")
    print("=" * 55)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )

        # Set cookies to appear like a real browser
        context.add_cookies([{
            "name":   "nike_locale",
            "value":  "en_US",
            "domain": ".nike.com",
            "path":   "/",
        }])

        page = context.new_page()

        # Visit homepage first to set cookies
        print("\nWarming up browser session...")
        try:
            page.goto("https://www.nike.com", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
        except Exception:
            pass

        # Scrape each category
        for url, category, gender in CATEGORY_PAGES:
            print(f"\n📦 Category: {category}")
            products = scrape_category(page, url, category, gender)
            all_products.extend(products)
            print(f"   Running total: {len(all_products)} products")
            time.sleep(2)

        browser.close()

    if not all_products:
        print("\n❌ No products scraped. Nike may be blocking the request.")
        sys.exit(1)

    # Save CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_products)

    print(f"\n✅ Saved {len(all_products)} products → {OUTPUT_FILE}")
    print("=" * 55)


if __name__ == "__main__":
    main()
