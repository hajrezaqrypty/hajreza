import requests
import json
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

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
        """بارگذاری کوکی‌ها از فایل JSON"""
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.session.cookies.set(
                        cookie['name'], 
                        cookie['value'], 
                        domain=cookie.get('domain', 'streamwide.tv')
                    )
            print("کوکی‌ها با موفقیت بارگذاری شدند.")

    def save_cookies(self):
        """ذخیره کوکی‌های جدید در فایل JSON"""
        new_cookies = []
        for cookie in self.session.cookies:
            new_cookies.append({
                "domain": cookie.domain,
                "name": cookie.name,
                "value": cookie.value
            })
        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_cookies, f, indent=4)
        print("کوکی‌های جدید ذخیره شدند.")

    def auto_login(self):
        """لاگین کردن با یوزر پسورد در صورت منقضی شدن کوکی"""
        print("کوکی منقضی شده است. تلاش برای لاگین مجدد...")
        
        # آدرس لاگین API را باید از روی شبکه سایت استخراج کنیم
        # فعلا فرض می‌کنیم این آدرس است (باید با F12 شبکه را چک کنیم)
        login_api_url = f"{BASE_URL}/api/v1/auth/login/"
        
        payload = {
            "email": os.getenv("WEBSITE_USERNAME"),
            "password": os.getenv("WEBSITE_PASSWORD")
        }
        
        response = self.session.post(login_api_url, json=payload)
        
        if response.status_code == 200:
            print("لاگین موفقیت‌آمیز بود!")
            self.save_cookies()
            return True
        else:
            print(f"خطا در لاگین: {response.text}")
            return False

    def get_download_links(self, movie_url):
        """استخراج لینک‌های دانلود از یک صفحه فیلم"""
        print(f"در حال بررسی صفحه: {movie_url}")
        response = self.session.get(movie_url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # پیدا کردن تگی که اطلاعات لاگین و API دانلود را دارد
        tp_dl_div = soup.find('div', {'id': 'tp-dl'})
        
        if not tp_dl_div:
            return ["خطا: ساختار صفحه پیدا نشد."]
            
        # بررسی اینکه آیا کاربر لاگین شده است یا خیر
        is_logged_in = tp_dl_div.get('data-logged-in', '0')
        
        if is_logged_in == '0':
            # اگر لاگین نبود، اول لاگین می‌کند و دوباره صفحه را لود می‌کند
            if self.auto_login():
                return self.get_download_links(movie_url)
            else:
                return ["خطا: امکان لاگین وجود ندارد."]
                
        # استخراج آدرس API مخفی دانلود
        download_api_path = tp_dl_div.get('data-download-url')
        if not download_api_path:
            return ["خطا: لینک API دانلود پیدا نشد."]
            
        # درخواست به API برای گرفتن لینک‌های واقعی دانلود
        api_url = BASE_URL + download_api_path
        print(f"درخواست به API مخفی: {api_url}")
        
        api_response = self.session.get(api_url)
        
        if api_response.status_code == 200:
            # سایت معمولا لینک‌ها را در قالب JSON می‌فرستد
            data = api_response.json()
            # این بخش بستگی به ساختار JSON سایت دارد
            links = []
            if isinstance(data, dict):
                for quality, link in data.get('links', {}).items():
                    links.append(f"{quality}: {link}")
                if not links and 'url' in data:
                    links.append(data['url'])
            return links if links else ["لینکی در JSON پیدا نشد. ساختار را بررسی کنید."]
        else:
            return [f"خطا در دریافت از API: {api_response.status_code}"]

# تست اسکریپت
if __name__ == "__main__":
    scraper = StreamWideScraper()
    
    # برای تست، آدرس همان فیلمی که فرستادید
    test_url = "https://streamwide.tv/t/spider-man-brand-new-day-fb980ca7/"
    
    links = scraper.get_download_links(test_url)
    
    print("\n--- لینک‌های استخراج شده ---")
    for link in links:
        print(link)
