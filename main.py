import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
import uvicorn

data_store = {
    "success": True,
    "last_updated": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    "base_currency": "USD",
    "target_currency": "IQD",
    "unit": "100 USD",
    "markets": {
        "baghdad": {"name": "بغداد (الكفاح والحارثية)", "price": 168300, "sell": 168750, "buy": 167750},
        "erbil": {"name": "أربيل", "price": 168200, "sell": 168500, "buy": 168000},
        "basra": {"name": "البصرة", "price": 168400, "sell": 168750, "buy": 167750},
        "sulaymaniyah": {"name": "السليمانية", "price": 168300, "sell": 168500, "buy": 168000},
        "duhok": {"name": "دهوك", "price": 168350, "sell": 168600, "buy": 168100},
        "najaf": {"name": "النجف الأشرف", "price": 168400, "sell": 168750, "buy": 167750},
        "kirkuk": {"name": "كركوك", "price": 168300, "sell": 168600, "buy": 168000},
        "mosul": {"name": "الموصل", "price": 168400, "sell": 168750, "buy": 167750}
    },
    "gold_rates": {
        "unit": "مثقال (5 غرامات)",
        "gulf_21": {"name": "مثقال عيار 21 (خليجي وتركي وأوروبي)", "sell": 575000, "buy": 565000},
        "iraqi_21": {"name": "مثقال عيار 21 (عراقي)", "sell": 545000, "buy": 535000},
        "gram_24": {"name": "غرام عيار 24", "sell": 131500, "buy": 129000},
        "gram_18": {"name": "غرام عيار 18", "sell": 98500, "buy": 96000}
    },
    "official_rate": 151000,
    "source_status": "initialized"
}

def clean_price(val: str) -> Optional[int]:
    nums = re.sub(r"[^\d]", "", val)
    return int(nums) if nums else None

def auto_scrape_rates():
    global data_store
    url = "https://shafaq.com/ar/اقتصـاد"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = soup.get_text()

            cities_patterns = {
                "erbil": r"اربيل.*?([\d,]{6,7})",
                "basra": r"البصرة.*?([\d,]{6,7})",
                "sulaymaniyah": r"السليمانية.*?([\d,]{6,7})",
                "duhok": r"دهوك.*?([\d,]{6,7})",
                "najaf": r"النجف.*?([\d,]{6,7})",
                "kirkuk": r"كركوك.*?([\d,]{6,7})",
                "mosul": r"الموصل.*?([\d,]{6,7})"
            }

            kifah_found = re.search(r"الكفاح.*?([\d,]{6,7})", text)
            sell_found = re.search(r"البيع.*?([\d,]{6,7})", text)
            buy_found = re.search(r"الشراء.*?([\d,]{6,7})", text)

            if kifah_found:
                p = clean_price(kifah_found.group(1))
                if p and 120000 < p < 220000:
                    data_store["markets"]["baghdad"]["price"] = p

            if sell_found and buy_found:
                s = clean_price(sell_found.group(1))
                b = clean_price(buy_found.group(1))
                if s and b:
                    data_store["markets"]["baghdad"]["sell"] = s
                    data_store["markets"]["baghdad"]["buy"] = b

            for city_key, pattern in cities_patterns.items():
                match = re.search(pattern, text)
                if match:
                    val = clean_price(match.group(1))
                    if val and 120000 < val < 220000:
                        data_store["markets"][city_key]["price"] = val
                        data_store["markets"][city_key]["sell"] = val + 350
                        data_store["markets"][city_key]["buy"] = val - 350

            gold_gulf = re.search(r"(الخليجي|المستورد).*?([\d,]{6,7})", text)
            gold_iraqi = re.search(r"(العراقي).*?([\d,]{6,7})", text)

            if gold_gulf:
                gp = clean_price(gold_gulf.group(2))
                if gp and 400000 < gp < 800000:
                    data_store["gold_rates"]["gulf_21"]["sell"] = gp
                    data_store["gold_rates"]["gulf_21"]["buy"] = gp - 10000

            if gold_iraqi:
                ip = clean_price(gold_iraqi.group(2))
                if ip and 350000 < ip < 750000:
                    data_store["gold_rates"]["iraqi_21"]["sell"] = ip
                    data_store["gold_rates"]["iraqi_21"]["buy"] = ip - 10000

            data_store["last_updated"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            data_store["source_status"] = "synced_online"
            print(f"[{datetime.now()}] تم تحديث أسعار المحافظات والذهب بنجاح.")
    except Exception as err:
        print(f"Scrape error: {err}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_scrape_rates()
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_scrape_rates, 'interval', minutes=10)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Iraq Dollar & Gold Live API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "running", "service": "Iraq Dollar & Gold API"}

@app.get("/api/v1/rates")
def get_rates():
    return data_store

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
