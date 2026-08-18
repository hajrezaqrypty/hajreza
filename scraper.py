import requests
import json
import os
from bs4 import BeautifulSoup

BASE_URL = "https://streamwide.tv"
COOKIE_FILE = "cookies.json"

class StreamWideScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': BASE_URL
        })
        self.load_cookies()

    def load_cookies(self):
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'streamwide.tv'))
            print("کوکی‌های موجود بارگذاری شدند.")

    def save_cookies(self):
        new_cookies = []
        for cookie in self.session.cookies:
            new_cookies.append({"domain": cookie.domain, "name": cookie.name, "value": cookie.value})
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_cookies, f, indent=4)
        print("کوکی‌های جدید ذخیره شدند.")

    def auto_login(self):
        print("کوکی نامعتبر است. در حال تلاش برای لاگین...")
        # در آینده برای لاگین خودکار با API واقعی جایگزین می‌شود
        return False

    def get_download_links(self, movie_url):
        print(f"در حال بررسی صفحه: {movie_url}")
        response = self.session.get(movie_url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        tp_dl_div = soup.find('div', {'id': 'tp-dl'})
        if not tp_dl_div:
            return ["خطا: ساختار صفحه پیدا نشد."]
            
        is_logged_in = tp_dl_div.get('data-logged-in', '0')
        
        if is_logged_in == '0':
            if self.auto_login():
                return self.get_download_links(movie_url)
            else:
                return ["خطا: کوکی منقضی شده و امکان لاگین خودکار وجود ندارد."]
                
        download_api_path = tp_dl_div.get('data-download-url')
        if not download_api_path:
            return ["خطا: لینک API پیدا نشد."]
            
        api_url = BASE_URL + download_api_path
        print(f"درخواست به API مخفی: {api_url}")
        
        api_response = self.session.get(api_url)
        
        if api_response.status_code == 200:
            data = api_response.json().get('download', {})
            versions = data.get('versions', [])
            domains = data.get('domains', {})
            
            # دیکشنری برای تبدیل کدهای زبان به فارسی
            lang_map = {"DUB": "دوبله", "RAW": "زبان اصلی", "SUB": "زیرنویس"}
            
            formatted_links = []
            for v in versions:
                quality = v.get('quality', 'نامشخص')
                lang_code = v.get('lang', '')
                lang_fa = lang_map.get(lang_code, lang_code)
                size = v.get('size_h', '')
                url_path = v.get('url', '')
                dc_key = str(v.get('dc', '1'))
                
                # ساخت لینک نهایی دانلود
                domain_info = domains.get(dc_key, {})
                full_domain = domain_info.get('out_domain', 'https://s4.antstg.com') # پیش‌فرض خارج
                full_url = full_domain + url_path
                
                # متن نهایی برای بات تلگرام
                link_text = f"🎬 {quality} | {lang_fa} | حجم: {size}\n🔗 {full_url}"
                formatted_links.append(link_text)
                
            return formatted_links
        else:
            return [f"خطا در API: {api_response.status_code}"]

# اجرای اسکریپت
if __name__ == "__main__":
    scraper = StreamWideScraper()
    
    test_url = os.environ.get("TEST_MOVIE_URL", "https://streamwide.tv/t/spider-man-brand-new-day-fb980ca7/")
    
    links = scraper.get_download_links(test_url)
    
    print("\n" + "="*40)
    print("لینک‌های نهایی استخراج شده:")
    print("="*40)
    for link in links:
        print(link)
        print("-" * 30)
