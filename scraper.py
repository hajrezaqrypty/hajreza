import requests
import json
import os
from bs4 import BeautifulSoup

BASE_URL = "https://streamwide.tv"
LOGIN_URL = f"{BASE_URL}/auth/login"
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
        """بارگذاری کوکی‌ها از فایل JSON (اگر وجود داشته باشند)"""
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', 'streamwide.tv'))
            print("کوکی‌های موجود بارگذاری شدند.")

    def save_cookies(self):
        """ذخیره کوکی‌های جدید در فایل JSON"""
        new_cookies = []
        for cookie in self.session.cookies:
            new_cookies.append({"domain": cookie.domain, "name": cookie.name, "value": cookie.value})
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_cookies, f, indent=4)
        print("کوکی‌های جدید ذخیره شدند.")

    def auto_login(self):
        """لاگین خودکار با استفاده از یوزر و پسورد ذخیره شده در GitHub Secrets"""
        print("کوکی نامعتبر است. در حال تلاش برای لاگین...")
        
        # دریافت توکن CSRF از صفحه اصلی
        res = self.session.get(BASE_URL)
        soup = BeautifulSoup(res.text, 'lxml')
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        csrf_token = csrf_meta['content'] if csrf_meta else None

        headers = {
            'X-CSRFToken': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
        
        # خواندن یوزرنیم و پسورد از متغیرهای محیطی گیت‌هاب
        payload = {
            "email": os.environ.get("WEBSITE_USERNAME"),
            "password": os.environ.get("WEBSITE_PASSWORD")
        }

        response = self.session.post(LOGIN_URL, json=payload, headers=headers)
        
        if response.status_code in [200, 201]:
            print("لاگین موفقیت‌آمیز بود!")
            self.save_cookies()
            return True
        else:
            print(f"خطا در لاگین: {response.status_code} - {response.text}")
            return False

    def get_download_links(self, movie_url):
        """استخراج لینک‌های دانلود از صفحه فیلم"""
        print(f"در حال بررسی صفحه: {movie_url}")
        response = self.session.get(movie_url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        tp_dl_div = soup.find('div', {'id': 'tp-dl'})
        if not tp_dl_div:
            return ["خطا: ساختار صفحه پیدا نشد."]
            
        is_logged_in = tp_dl_div.get('data-logged-in', '0')
        
        # اگر لاگین نبود، اول لاگین می‌کند و دوباره صفحه را لود می‌کند
        if is_logged_in == '0':
            if self.auto_login():
                return self.get_download_links(movie_url)
            else:
                return ["خطا: عدم توانایی در لاگین."]
                
        # استخراج لینک API مخفی دانلود
        download_api_path = tp_dl_div.get('data-download-url')
        if not download_api_path:
            return ["خطا: لینک API پیدا نشد."]
            
        api_url = BASE_URL + download_api_path
        print(f"درخواست به API مخفی: {api_url}")
        
        api_response = self.session.get(api_url)
        
        if api_response.status_code == 200:
            data = api_response.json()
            links = []
            # اینجا ساختار JSON سایت را چاپ می‌کنیم تا ببینیم لینک‌ها کجا هستند
            print("ساختار دریافت شده از API:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        else:
            return [f"خطا در API: {api_response.status_code}"]

# اجرای اسکریپت
if __name__ == "__main__":
    scraper = StreamWideScraper()
    
    # گرفتن لینک از متغیر محیطی گیت‌هاب (برای تست)
    test_url = os.environ.get("TEST_MOVIE_URL", "https://streamwide.tv/t/spider-man-brand-new-day-fb980ca7/")
    
    links = scraper.get_download_links(test_url)
