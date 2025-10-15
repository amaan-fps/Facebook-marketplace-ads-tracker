from playwright.sync_api import sync_playwright
import time
import json
import random
import re
import os

STORAGE_FILE = "facebook_storage.json"  # produced earlier by save_facebook_storage.py
OUTPUT_FILE = "fb_marketplace_results.json"

SEARCH_TERMS_FILE = "../add_queries/search_terms.json"
SEEN_FILE = "facebook_seen_ads.json"
MAX_SEEN = 1000  # how many old ads to keep per query-location

# --- Utility functions ---
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def parse_price(text):
    """Convert ₹2,000 → 2000"""
    try:
        text = text.split("\n")[0].strip()
        clean = re.sub(r"[^\d]", "", text)
        return int(clean) if clean else None
    except:
        return None

def human_sleep(min_s=0.8, max_s=2.2):
    time.sleep(random.uniform(min_s, max_s))

def scroll_page(page, scrolls=5, pause=1.0):
    """Scroll down the page slowly to trigger lazy loading."""
    for i in range(scrolls):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.9)")
        human_sleep(pause, pause + 0.7)

def extract_listings(page):
    # Step 1: Create a locator for all cards
    cards = page.locator("a[href*='/marketplace/item/']")
    count = cards.count()
    print("Found cards:", count)

    results = []

    # Step 2: Loop through locators using .nth()
    for i in range(count):
        c = cards.nth(i)
        # print(c.evaluate("el => el.outerHTML"))
        try:
            # --- Image ---
            photo_url = c.locator("img").first.get_attribute("src") or ""

            # --- Title ---
            title_el = c.locator("span[dir='auto']:below(:has-text('₹'))").first
            title = title_el.inner_text().strip()

            # --- Location ---
            location_el = title_el.locator("xpath=following::span[@dir='auto'][1]")
            location = location_el.inner_text().strip() if location_el.count() else None

            # --- Price ---
            price_el = c.locator("span:has-text('₹')").first
            price = price_el.inner_text().strip('\n') if price_el.count() else None

            # --- Link ---
            href = c.get_attribute("href") or ""
            match = re.search(r"/item/(\d+)/", href)
            item_id =  match.group(1) if match else None
            if href.fastartswith("/"):
                href = "https://www.facebook.com" + href

            results.append({
                "item_id": item_id,
                "title": title,
                "price": price,
                "url": href,
                "img_url": photo_url,
                "location": location
            })
        except Exception as e:
            print("Error parsing card:", e)
            continue

    return results

def run_scraper():
    search_terms = load_json(SEARCH_TERMS_FILE, [])
    seen_ads = load_json(SEEN_FILE, {})

    all_new_results = []  # Collect all new ads across all queries

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=30)
        context = browser.new_context(storage_state=STORAGE_FILE, viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page.goto("https://www.facebook.com/marketplace", wait_until="domcontentloaded")
        human_sleep(1.5, 2.5)
        print("Marketplace title:", page.title())
        first_time = True
        for term in search_terms:

            query = term["query"]
            min_p = term.get("min_price", 0)
            max_p = term.get("max_price", 9999999)

            print(f"\n🔍 Searching for '{query}'...")
            search_input = page.query_selector("input[aria-label='Search Marketplace'], input[placeholder='Search Marketplace']")

            search_input.click()
            human_sleep(1, 2)
            search_input.fill(f"{query}")
            human_sleep(0.3, 0.8)
            search_input.press("Enter")
            human_sleep(1, 2)
            # 🆕 Click the "Last 24 hours" filter if it exists

            if first_time:
                date_btn = page.locator("span:has-text('Date listed')").nth(1)
                if date_btn.count():
                    date_btn.first.click()
                    filter_btn = page.locator("span:has-text('Last 24 hours')")
                    if filter_btn.count():
                        filter_btn.first.click()
                        print("✅ Clicked 'Last 24 hours' filter")
                        page.wait_for_timeout(4000)
                    else:
                        print("⚠️ 'Last 24 Hrs' Filter not found")
                else:
                    print("⚠️ 'Date Listed' Button not found")
                    # print(date_btn.evaluate(("el => el.outerHTML")))
                    # print(date_btn.count())
            else:
                filter_btn = page.locator("span:has-text('Last 24 hours')")
                if filter_btn.count():
                    filter_btn.first.click()
                    print("✅ Clicked 'Last 24 hours' filter")
                    page.wait_for_timeout(4000)
                else:
                    print("⚠️ 'Last 24 Hrs' Filter not found")

            # Scroll to load more results (simulate human)
            scroll_page(page, scrolls=3, pause=1.5)
            first_time = False
            page.wait_for_timeout(3000)


            # Wait a bit for lazy content
            human_sleep(1.5, 2.5)

            listings = extract_listings(page)
            print(f"Found {len(listings)} results for {query}")

            first_run =False
            if query not in seen_ads:
                seen_ads[query] = []
                first_run = True
            seen_ids = seen_ads[query]
            new_ads = []
            new_ids = []

            for item in listings:
                if not item["item_id"]:
                    continue
                if item["item_id"] in seen_ids:
                    continue
                if item["price"] is None or not (min_p <= parse_price(item["price"]) <= max_p):
                    continue

                if not first_run:
                    # This ad is new and matches the filters
                    new_ads.append(item)
                new_ids.append(item["item_id"])

            updated_seen = (new_ids + seen_ids)[:MAX_SEEN]
            seen_ads[query] = updated_seen
            all_new_results.extend(new_ads)

            print(f"✅ {len(new_ids)} new results for '{query}' in price range {min_p}-{max_p}:")
            for res in new_ads:
                print(f"- {res['title']} | {res['price']} | {res['url']}")

        # Save updated seen ads
        save_json(SEEN_FILE, seen_ads)

        # Save all new ads for telegram/alerts
        save_json("fb_new_ads.json", all_new_results)
        print(f"\n💾 Saved {len(all_new_results)} new ads to fb_new_ads.json")

        # Optionally: update and persist any changed storage (cookies/localStorage)
        context.storage_state(path=STORAGE_FILE)  # overwrite with current state
        print("Updated storage state saved back to", STORAGE_FILE)

        browser.close()

#
# def run():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True, slow_mo=30)  # headed and slightly slowed
#         # load saved logged-in session
#         context = browser.new_context(storage_state=STORAGE_FILE, viewport={"width":1280,"height":800})
#         page = context.new_page()
#
#         # OPTIONAL: set a realistic user agent if you changed earlier
#         # page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; ... )"})
#
#         # Go to Marketplace
#         page.goto("https://www.facebook.com/marketplace", wait_until="domcontentloaded")
#         human_sleep(1.5, 2.5)
#         print("Marketplace title:", page.title())
#
#         # Perform a search using UI (so requests look like a user)
#         # Find the search input — selector may differ across accounts / FB versions
#         try:
#             search_input = page.query_selector("input[aria-label='Search Marketplace'], input[placeholder='Search Marketplace']")
#             if search_input:
#                 search_input.click()
#                 human_sleep(0.3, 0.8)
#                 search_input.fill("ps4 pro")
#                 human_sleep(0.3, 0.8)
#                 search_input.press("Enter")
#         except Exception as e:
#             print("Search input not found or failed:", e)
#             page.goto("https://www.facebook.com/marketplace/search?query=ps4%20pro", wait_until="networkidle")
#
#         human_sleep(2, 3)
#
#         # Scroll to load more results (simulate human)
#         scroll_page(page, scrolls=8, pause=1.0)
#
#         # Wait a bit for lazy content
#         human_sleep(1.5, 2.5)
#
#         # Extract visible listings
#         listings = extract_listings(page)
#         print(f"Found {len(listings)} candidate listings on page.")
#
#         # Save output
#         with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
#             json.dump(listings, f, ensure_ascii=False, indent=2)
#         print("Saved results to", OUTPUT_FILE)
#
#         # Optionally: update and persist any changed storage (cookies/localStorage)
#         context.storage_state(path=STORAGE_FILE)  # overwrite with current state
#         print("Updated storage state saved back to", STORAGE_FILE)
#
#         browser.close()

if __name__ == "__main__":
    run_scraper()

