import requests
import json
import os
from bs4 import BeautifulSoup

BASE_URL = "https://streamwide.tv"
COOKIE_FILE = "cookies.json"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or CHAT_ID is missing!")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # تقسیم متن‌های طولانی به قطعات ۳۰۰۰ کاراکتری
    max_length = 3000
    chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(url, json=payload)
            print(f"Telegram response status: {res.status_code}")
        except Exception as e:
            print(f"Error sending message: {e}")

class StreamWideScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': BASE_URL
        })
        self.load_cookies()

    def load_cookies(self):
        if os.path.exists(COOKIE_FILE):
            print("Cookies file found. Loading...")
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'streamwide.tv'))
        else:
            print("ERROR: cookies.json not found!")

    def get_raw_api_data(self, movie_url):
        try:
            response = self.session.get(movie_url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            tp_dl_div = soup.find('div', {'id': 'tp-dl'})
            if not tp_dl_div:
                return "❌ خطا: ساختار صفحه پیدا نشد."
                
            download_api_path = tp_dl_div.get('data-download-url')
            if not download_api_path:
                return "❌ خطا: لینک API پیدا نشد."
                
            api_url = BASE_URL + download_api_path
            api_response = self.session.get(api_url)
            
            if api_response.status_code == 200:
                # گرفتن متن خام پاسخ API
                raw_text = api_response.text
                return f"🔍 متن خام دریافتی از API:\n\n{raw_text}"
            else:
                return f"❌ خطا در API: {api_response.status_code}"
                
        except Exception as e:
            return f"❌ Exception: {str(e)}"

if __name__ == "__main__":
    scraper = StreamWideScraper()
    movie_url = os.environ.get("MOVIE_URL")
    
    if movie_url:
        print(f"Getting raw API data for: {movie_url}")
        raw_data = scraper.get_raw_api_data(movie_url)
        print("Scraping finished. Sending to Telegram...")
        send_telegram_message(raw_data)
    else:
        print("No URL provided.")
