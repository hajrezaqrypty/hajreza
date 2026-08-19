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
    max_length = 4000
    chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
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

    def get_download_links(self, movie_url):
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
                try:
                    data = api_response.json().get('download', {})
                except:
                    data = {}
                    
                versions = data.get('versions', [])
                domains = data.get('domains', {})
                iran_warning = data.get('iran_warning', '')
                
                lang_map = {"DUB": "دوبله فارسی", "RAW": "زبان اصلی", "SUB": "زیرنویس چسبیده"}
                formatted_links = []
                
                if iran_warning:
                    formatted_links.append(f"⚠️ توجه: {iran_warning}\n" + "="*30)
                
                # حالت اول: استخراج لینک فیلم‌ها از API (اگر versions وجود داشته باشد)
                if versions:
                    for v in versions:
                        quality = v.get('quality', 'نامشخص')
                        lang_code = v.get('lang', '')
                        lang_fa = lang_map.get(lang_code, lang_code)
                        size = v.get('size_h', '')
                        url_path = v.get('url', '')
                        dc_key = str(v.get('dc', '1'))
                        
                        domain_info = domains.get(dc_key, {})
                        out_url = domain_info.get('out_domain', 'https://s4.antstg.com') + url_path
                        in_url = domain_info.get('in_domain', 'https://s4.709711.ir.cdn.ir') + url_path
                        
                        text = f"🎬 کیفیت: {quality}\n🗣 زبان: {lang_fa}\n📦 حجم: {size}\n\n🌍 لینک خارج:\n{out_url}\n\n🇮🇷 لینک داخل ایران:\n{in_url}\n" + "="*30
                        formatted_links.append(text)
                
                # حالت دوم: استخراج لینک سریال‌ها از داخل HTML (اگر versions خالی باشد)
                else:
                    tp_eps_div = soup.find('div', {'class': 'tp-eps'})
                    if tp_eps_div:
                        episodes = tp_eps_div.find_all('div', {'class': 'tp-ep'})
                        for ep in episodes:
                            ep_num_tag = ep.find('div', {'class': 'tp-ep-num'})
                            ep_num = ep_num_tag.text.strip() if ep_num_tag else '?'
                            
                            title_tag = ep.find('div', {'class': 'tp-ep-title'})
                            ep_title = ""
                            tags = []
                            if title_tag:
                                spans = title_tag.find_all('span')
                                if spans:
                                    ep_title = spans[0].text.strip()
                                tag_spans = title_tag.find_all('span', {'class': 'tp-file-tag'})
                                tags = [t.text.strip() for t in tag_spans]
                            
                            lang_str = " | ".join(tags) if tags else ''
                            
                            size_tag = ep.find('span', {'class': 'tp-file-size'})
                            size = size_tag.text.strip() if size_tag else ''
                            
                            dl_btn = ep.find('button', {'class': 'tp-file-dl'})
                            if dl_btn:
                                url_path = dl_btn.get('data-rel', '')
                                dc_key = str(dl_btn.get('data-dc', '1'))
                                domain_info = domains.get(dc_key, {})
                                out_url = domain_info.get('out_domain', 'https://s4.antstg.com') + url_path
                                in_url = domain_info.get('in_domain', 'https://s4.709711.ir.cdn.ir') + url_path
                                
                                text = f"📺 قسمت {ep_num} | {ep_title} | {lang_str}\n📦 حجم: {size}\n\n🌍 لینک خارج:\n{out_url}\n\n🇮🇷 لینک داخل ایران:\n{in_url}\n" + "="*30
                                formatted_links.append(text)
                                
                return "\n\n".join(formatted_links) if formatted_links else "❌ هیچ لینکی پیدا نشد."
            else:
                return f"❌ خطا در API: {api_response.status_code}"
        except Exception as e:
            return f"❌ Exception: {str(e)}"

if __name__ == "__main__":
    scraper = StreamWideScraper()
    movie_url = os.environ.get("MOVIE_URL")
    
    if movie_url:
        print(f"Getting links for: {movie_url}")
        links_text = scraper.get_download_links(movie_url)
        print("Scraping finished. Sending to Telegram...")
        send_telegram_message(links_text)
    else:
        print("No URL provided.")
