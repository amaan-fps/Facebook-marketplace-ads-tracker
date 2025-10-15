import requests
from telegram import Bot
import json
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

TELE_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Your user ID or a group ID

bot = Bot(token=TELE_TOKEN)

def load_new_ads():
    if not os.path.exists('../fb_new_ads.json'):
        print("fb_new_ads.json not found.")
        return []
    with open('../fb_new_ads.json', 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("JSON decode error.")
            return []

def strikethrough(text):
    return "".join([char + '\u0336' for char in text])

def format_message(ad):
    STK = "\033[9m"
    STK_RES = "\033[0m"
    title = ad.get("title", "No Title")
    price = ad.get("price", "N/A")
    selling_price, mrp = price.split("\n")[0], price.split("\n")[1]

    link = ad.get('url', '-')
    location = ad.get('location', '-')
    text = f"*{title}*\n💰 Price: {selling_price} {strikethrough(mrp)}\n📍 {location}\n🔗 [View Ad on facebook]({link})"
    return text

async def send_telegram_alerts():
    # await bot.send_message(chat_id=CHAT_ID, text="hi, yasir!", parse_mode='Markdown', disable_web_page_preview=True)
    ads = load_new_ads()
    if not ads:
        print("No new ads to send.")
        return

    for ad in ads:
        msg = format_message(ad)
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELE_TOKEN}/sendPhoto",
                data={
                    "chat_id": CHAT_ID,
                    "photo": ad.get("img_url"),
                    "caption": msg,
                    "parse_mode": "Markdown"
                }
            )
            print("✅ Sent message for ad:", ad.get("item_id"))
        except Exception as e:
            print("Error sending message:", e)

if __name__ == "__main__":
    asyncio.run(send_telegram_alerts())
