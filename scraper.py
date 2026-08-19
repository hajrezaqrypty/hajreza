import requests
import json
import os
from bs4 import BeautifulSoup

BASE_URL = "https://streamwide.tv"
COOKIE_FILE = "cookies.json"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
CF_WORKER_URL = os.environ.get("CF_WORKER_URL")

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    max_length = 4000
    chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    for chunk in chunks:
        payload = {"chat_id": CHAT_ID, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True}
        try: requests.post(url, json=payload)
        except: pass

def save_to_cloudflare(data):
    if not CF_WORKER_URL: return
    try:
        requests.post(f"{CF_WORKER_URL}/save", json=data)
    except: pass

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
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'streamwide.tv'))

    def process_movie(self, movie_url):
        try:
            response = self.session.get(movie_url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # استخراج متادیتا
            title_en_tag = soup.find('h1', class_='tp-title')
            title_fa_tag = soup.find('div', class_='tp-title-fa')
            badge_tag = soup.find('span', class_='sw-badge')
            imdb_tag = soup.find('span', class_='sw-imdb-link')
            year_tag = soup.find('span', class_='tp-year')
            country_tag = soup.find('span', class_='tp-countries')
            og_image = soup.find('meta', property='og:image')
            og_desc = soup.find('meta', property='og:description')
            
            metadata = {
                "id": movie_url.split('/t/')[-1].split('/')[0],
                "url": movie_url,
                "title_en": title_en_tag.text.strip() if title_en_tag else '',
                "title_fa": title_fa_tag.text.strip() if title_fa_tag else '',
                "kind": badge_tag.text.strip() if badge_tag else '',
                "rating": imdb_tag.text.replace('IMDb', '').strip() if imdb_tag else '',
                "year": year_tag.text.strip() if year_tag else '',
                "country": country_tag.text.replace('محصول', '').strip() if country_tag else '',
                "poster": og_image['content'] if og_image else '',
                "description": og_desc['content'] if og_desc else '',
            }
            
            tp_dl_div = soup.find('div', {'id': 'tp-dl'})
            if not tp_dl_div: return "❌ خطا: ساختار صفحه پیدا نشد.", metadata
                
            download_api_path = tp_dl_div.get('data-download-url')
            api_url = BASE_URL + download_api_path
            api_response = self.session.get(api_url)
            
            if api_response.status_code != 200: return f"❌ خطا در API", metadata
                
            data = api_response.json().get('download', {})
            versions = data.get('versions', [])
            seasons = data.get('seasons', [])
            domains = data.get('domains', {})
            iran_warning = data.get('iran_warning', '')
            
            lang_map = {"DUB": "دوبله فارسی", "RAW": "زبان اصلی", "SUB": "زیرنویس چسبیده"}
            formatted_links = []
            
            if iran_warning:
                formatted_links.append(f"⚠️ توجه: {iran_warning}\n" + "="*30)
            
            if versions:
                for v in versions:
                    quality = v.get('quality', '')
                    lang_fa = lang_map.get(v.get('lang', ''), '')
                    size = v.get('size_h', '')
                    url_path = v.get('url', '')
                    dc_key = str(v.get('dc', '1'))
                    
                    if url_path:
                        domain_info = domains.get(dc_key, {})
                        out_url = domain_info.get('out_domain', '') + url_path
                        in_url = domain_info.get('in_domain', '') + url_path
                        
                        text = f"🎬 کیفیت: {quality}\n🗣 زبان: {lang_fa}\n📦 حجم: {size}\n\n🌍 لینک خارج:\n{out_url}\n\n🇮🇷 لینک داخل ایران:\n{in_url}\n" + "="*30
                        formatted_links.append(text)
                        
            elif seasons:
                for season in seasons:
                    season_label = season.get('label', '')
                    formatted_links.append(f"\n🌟 {season_label} 🌟\n" + "="*30)
                    for ep in season.get('episodes', []):
                        ep_num = ep.get('num_fa', ep.get('num', '?'))
                        ep_versions = ep.get('versions', [])
                        if not ep_versions: continue
                        formatted_links.append(f"\n📺 قسمت {ep_num}")
                        for v in ep_versions:
                            quality = v.get('quality', '')
                            lang_fa = lang_map.get(v.get('lang', ''), '')
                            size = v.get('size_h', '')
                            url_path = v.get('url', '')
                            dc_key = str(v.get('dc', '1'))
                            if url_path:
                                domain_info = domains.get(dc_key, {})
                                out_url = domain_info.get('out_domain', '') + url_path
                                in_url = domain_info.get('in_domain', '') + url_path
                                text = f"  🎬 {quality} | {lang_fa} | حجم: {size}\n  🌍 خارج: {out_url}\n  🇮🇷 ایران: {in_url}"
                                formatted_links.append(text)
                        formatted_links.append("-" * 30)
            
            links_text = "\n\n".join(formatted_links) if formatted_links else "❌ هیچ لینکی پیدا نشد."
            
            # ساخت هدر زیبا برای تلگرام
            header = f"🎬 <b>{metadata.get('title_fa', '')}</b> ({metadata.get('title_en', '')})\n"
            header += f"📅 سال: {metadata.get('year', '')} | ⭐ امتیاز: {metadata.get('rating', '')}\n"
            header += f"🌍 نوع: {metadata.get('kind', '')} | 🎥 کشور: {metadata.get('country', '')}\n"
            header += f"📖 داستان: {metadata.get('description', '')}\n\n"
            
            final_message = header + links_text
            
            # ذخیره در دیتابیس کلودفلر D1
            metadata["message_text"] = final_message
            save_to_cloudflare(metadata)
            
            # ذخیره لینک در فایل گیت‌هاب
            with open("processed_urls.txt", "a", encoding="utf-8") as f:
                f.write(f"{movie_url}\n")
            
            return final_message, metadata
            
        except Exception as e:
            return f"❌ Exception: {str(e)}", {}

if __name__ == "__main__":
    scraper = StreamWideScraper()
    movie_url = os.environ.get("MOVIE_URL")
    
    if movie_url:
        print(f"Processing: {movie_url}")
        final_text, _ = scraper.process_movie(movie_url)
        send_telegram_message(final_text)
