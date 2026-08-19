import os
import json
import re
import datetime
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup

DB_DIR = "db"
INDEX_FILE = os.path.join(DB_DIR, "index.json")

# متغیرهای محیطی
CF_API_URL = os.environ.get("CF_API_URL", "").strip()
CF_API_KEY = os.environ.get("CF_API_KEY", "").strip()
SITE_COOKIES_STR = os.environ.get("SITE_COOKIES", "[]")
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
REQ_KEY = os.environ.get("REQ_KEY", "").strip()
SEARCH_TERM = os.environ.get("SEARCH_TERM", "").strip()
MODE = os.environ.get("MODE", "normal").strip()
LAST_SEEN_URL = os.environ.get("LAST_SEEN_URL", "").strip()

try:
    COUNT = int(os.environ.get("COUNT", "1"))
except:
    COUNT = 1

AUTO_UPDATE_MAX_MOVIES = 10
BASE_URL = "https://streamwide.tv"

def ensure_dir():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

def build_cf_url(endpoint):
    base = CF_API_URL
    if "/api/add" in base:
        base = base.rsplit("/api/add", 1)[0]
    return base.rstrip("/") + endpoint

def send_to_cf(endpoint, payload):
    cf_url = build_cf_url(endpoint)
    if not cf_url or not CF_API_KEY:
        print("  [CLOUDFLARE] Missing CF_API_URL or CF_API_KEY")
        return False
    try:
        res = requests.post(cf_url, json=payload, headers={"X-API-Key": CF_API_KEY}, timeout=60)
        print(f"  [CLOUDFLARE] POST {endpoint} -> {res.status_code}")
        return 200 <= res.status_code < 300
    except Exception as e:
        print(f"  [CLOUDFLARE] Error: {e}")
        return False

def notify_quick_done(movies, last_seen_url="", site_error=False):
    if not CHAT_ID or not REQ_KEY: return False
    return send_to_cf("/api/quick_done", {
        "chatId": CHAT_ID, "req_key": REQ_KEY, "movies": movies,
        "last_seen_url": last_seen_url, "site_error": site_error
    })

def notify_logout():
    if not CHAT_ID or not REQ_KEY: return False
    return send_to_cf("/api/logout", {"chatId": CHAT_ID, "req_key": REQ_KEY})

class StreamWideScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': BASE_URL
        })
        self.load_cookies()

    def load_cookies(self):
        try:
            cookies = json.loads(SITE_COOKIES_STR)
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'streamwide.tv'))
        except:
            pass

    def check_logged_out(self, soup):
        gate = soup.find('div', class_='tp-dl-gate-over')
        if gate:
            text = gate.get_text()
            if "وارد شو" in text or "login" in text.lower():
                return True
        return False

    def search_catalog(self, query, mode):
        target_url = "https://streamwide.tv/catalog/?sort=new" if mode == "auto_update" else f"https://streamwide.tv/catalog/?q={quote(query)}"
        print(f"  [SCRAPER] Searching: {target_url}")
        
        res = self.session.get(target_url)
        if res.status_code != 200: return []
            
        soup = BeautifulSoup(res.text, 'lxml')
        cards = soup.find_all("a", class_="sw-card")
        movies = []
        
        for card in cards:
            title_el = card.find(class_="sw-card-title")
            meta_el = card.find(class_="sw-card-meta")
            link = card.get("href", "")
            
            if not (title_el and link): continue
            
            title = title_el.get_text(strip=True)
            meta = meta_el.get_text(strip=True) if meta_el else ""
            movie_url = link if link.startswith("http") else BASE_URL + link
            
            year = meta.split("·")[0].strip() if meta else ""
            movies.append({"title": title, "meta": meta, "year": year, "url": movie_url})
        return movies

    def process_movie(self, movie_url):
        print(f"  -> Deep scraping: {movie_url}")
        res = self.session.get(movie_url)
        soup = BeautifulSoup(res.text, 'lxml')
        
        if self.check_logged_out(soup):
            return "logout"
            
        # استخراج متادیتا
        title_en_tag = soup.find('h1', class_='tp-title')
        title_fa_tag = soup.find('div', class_='tp-title-fa')
        badge_tag = soup.find('span', class_='sw-badge')
        imdb_tag = soup.find('span', class_='sw-imdb-link')
        year_tag = soup.find('span', class_='tp-year')
        country_tag = soup.find('span', class_='tp-countries')
        og_image = soup.find('meta', property='og:image')
        og_desc = soup.find('meta', property='og:description')
        genre_els = soup.select('.tp-genres a')
        
        metadata = {
            "url": movie_url,
            "title": title_en_tag.get_text(strip=True) if title_en_tag else '',
            "title_fa": title_fa_tag.get_text(strip=True) if title_fa_tag else '',
            "type": "Series" if (badge_tag and "سریال" in badge_tag.get_text()) else "Movie",
            "year": year_tag.get_text(strip=True) if year_tag else '',
            "country": country_tag.get_text(strip=True).replace('محصول', '').strip() if country_tag else '',
            "genres": " | ".join([g.get_text(strip=True) for g in genre_els]),
            "imdb": imdb_tag.get_text(strip=True).replace('IMDb', '').strip() if imdb_tag else '',
            "image": og_image['content'] if og_image else '',
            "plot": og_desc['content'] if og_desc else '',
        }
        
        tp_dl_div = soup.find('div', {'id': 'tp-dl'})
        if not tp_dl_div: return None
            
        download_api_path = tp_dl_div.get('data-download-url')
        api_url = BASE_URL + download_api_path
        api_res = self.session.get(api_url)
        
        if api_res.status_code != 200: return None
            
        data = api_res.json().get('download', {})
        versions = data.get('versions', [])
        seasons = data.get('seasons', [])
        domains = data.get('domains', {})
        
        lang_map = {"DUB": "دوبله فارسی", "RAW": "زبان اصلی", "SUB": "زیرنویس چسبیده"}
        downloads = []
        
        # ساختار درختی برای دیتابیس (منطبق با کد بات شما)
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
                    
                    # لینک خارج
                    downloads.append({
                        "url": out_url, "size": size, "server": "خارج ایران",
                        "language": lang_fa, "quality": quality, "season": "", "episode": ""
                    })
                    # لینک داخل
                    downloads.append({
                        "url": in_url, "size": size, "server": "داخل ایران",
                        "language": lang_fa, "quality": quality, "season": "", "episode": ""
                    })
                    
        elif seasons:
            for season in seasons:
                season_label = season.get('label', '')
                for ep in season.get('episodes', []):
                    ep_num = ep.get('num_fa', ep.get('num', '?'))
                    for v in ep.get('versions', []):
                        quality = v.get('quality', '')
                        lang_fa = lang_map.get(v.get('lang', ''), '')
                        size = v.get('size_h', '')
                        url_path = v.get('url', '')
                        dc_key = str(v.get('dc', '1'))
                        if url_path:
                            domain_info = domains.get(dc_key, {})
                            out_url = domain_info.get('out_domain', '') + url_path
                            in_url = domain_info.get('in_domain', '') + url_path
                            
                            downloads.append({
                                "url": out_url, "size": size, "server": "خارج ایران",
                                "language": lang_fa, "quality": quality, "season": season_label, "episode": str(ep_num)
                            })
                            downloads.append({
                                "url": in_url, "size": size, "server": "داخل ایران",
                                "language": lang_fa, "quality": quality, "season": season_label, "episode": str(ep_num)
                            })
                            
        metadata["downloads"] = downloads
        metadata["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return metadata

def run_scraper():
    ensure_dir()
    scraper = StreamWideScraper()
    
    cards_info = scraper.search_catalog(SEARCH_TERM, MODE)
    print(f"  [SCRAPER] Found {len(cards_info)} cards")
    
    movies_to_process = []
    first_movie_url = ""
    new_last_seen_url = LAST_SEEN_URL
    max_count = AUTO_UPDATE_MAX_MOVIES if MODE == "auto_update" else COUNT
    
    for info in cards_info:
        if len(movies_to_process) >= max_count: break
        title = info["title"]
        if info["year"]: title = f"{title} ({info['year']})"
        movie_url = info["url"]
        
        if MODE == "auto_update":
            if movie_url == LAST_SEEN_URL and LAST_SEEN_URL: break
            if not first_movie_url: first_movie_url = movie_url
            
        movies_to_process.append({"title": title, "url": movie_url})
        
    if MODE == "auto_update" and first_movie_url:
        new_last_seen_url = first_movie_url
    elif MODE != "auto_update":
        new_last_seen_url = ""
        
    new_movies_to_send = []
    stop_reason = None
    
    for item in movies_to_process:
        movie_data = scraper.process_movie(item["url"])
        
        if movie_data == "logout":
            stop_reason = "logout"
            break
        elif movie_data is None: continue
            
        send_to_cf("/api/add", movie_data)
        
        # ذخیره در گیت‌هاب
        safe_title = re.sub(r'[\\/*?:"<>|]', "", movie_data["title"]).replace(" ", "_")[:80]
        filepath = os.path.join(DB_DIR, f"{movie_data['type']}_{safe_title}_{movie_data['year']}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(movie_data, f, indent=4, ensure_ascii=False)
            
        new_movies_to_send.append({"title": item["title"], "url": item["url"]})
        
    if stop_reason == "logout":
        notify_logout()
    else:
        notify_quick_done(new_movies_to_send, new_last_seen_url)

if __name__ == "__main__":
    run_scraper()
