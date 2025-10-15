# save as save_facebook_storage.py
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Create a context where user can login manually
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com", wait_until="networkidle")
        print("Please log in manually in the opened browser window. After login, press Enter here...")
        input()  # wait for you to login and press Enter
        # Save storage state (cookies + localStorage)
        context.storage_state(path="facebook_storage.json")
        print("Saved storage state to facebook_storage.json")
        browser.close()

if __name__ == "__main__":
    run()
