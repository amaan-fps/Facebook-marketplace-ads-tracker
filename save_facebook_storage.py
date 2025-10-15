import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import random

def human_sleep(min_s=0.8, max_s=2.2):
    time.sleep(random.uniform(min_s, max_s))

def run():
    # Prefer credentials from env vars for automation, fallback to interactive prompt
    fb_user = os.getenv("FB_USER")  # phone or email
    fb_pass = os.getenv("FB_PASS")

    if not fb_user:
        fb_user = input("Enter Facebook email address or phone number: ").strip()
    if not fb_pass:
        fb_pass = input("Enter Facebook password: ").strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page.goto("https://www.facebook.com", wait_until="domcontentloaded")

        # Wait a little for page UI to render
        page.wait_for_timeout(1000)

        try:
            # Fill the "Email address or phone number" input (placeholder exact match)
            email_selector = "input[placeholder='Email address or phone number'], input[name='email']"
            email_input = page.locator(email_selector).first
            human_sleep(1.5, 2.5)
            if email_input.count():
                email_input.type(fb_user, delay=100)
            else:
                print("⚠️ Email/phone input not found by placeholder. Trying common selector fallback.")
                page.fill("input[name='email']", fb_user)

            # Fill the "Password" input
            password_selector = "input[placeholder='Password'], input[name='pass']"
            pass_input = page.locator(password_selector).first
            human_sleep(1.5, 2.5)
            if pass_input.count():
                pass_input.type(fb_pass, delay=100)
            else:
                print("⚠️ Password input not found by placeholder. Trying common selector fallback.")
                page.fill("input[name='pass']", fb_pass)
            human_sleep(1.5, 2.5)
            # Try to click submit button (common patterns)
            # 1) button[type='submit']
            # 2) button:has-text("Log In") or input[type='submit']
            clicked = False
            for sel in ["button[type='submit']", "input[type='submit']", "button:has-text('Log In')", "button:has-text('Log in')"]:
                btn = page.locator(sel).first
                if btn.count():
                    btn.click()
                    clicked = True
                    break

            if not clicked:
                # fallback: press Enter in password field
                try:
                    pass_input.press("Enter")
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                print("❗ Could not find or click a submit button. Please submit login manually in the opened browser.")
                input("After you log in manually, press Enter here to continue...")

            # Wait for network idle / logged-in indicator
            try:
                # Wait for either Marketplace or profile link to appear as evidence of login
                page.wait_for_selector("a[href*='profile.php'], a[aria-label='Home'], a[href*='/marketplace']", timeout=15000)
            except PWTimeoutError:
                # Fallback: wait a bit and continue
                print("⚠️ Login confirmation not detected automatically; waiting a few more seconds...")
                page.wait_for_timeout(5000)

            # Small delay to ensure cookies/localStorage are set
            time.sleep(1.5)

            # Save storage state (cookies + localStorage)
            context.storage_state(path="facebook_storage.json")
            print("✅ Saved storage state to facebook_storage.json")

            # Optionally print cookies (for debugging) - do NOT expose this file publicly
            cookies = context.cookies()
            print("Cookies fetched (names only):", [c.get("name") for c in cookies])

        finally:
            browser.close()

if __name__ == "__main__":
    run()
