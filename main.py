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
    "rates": {
        "kifah": 168300,
        "harithiya": 168300,
        "exchange_shops": {
            "sell": 168750,
            "buy": 167750
        },
        "official": 151000
    },
    "source_status": "initialized"
}

def clean_price(val: str) -> Optional[int]:
    nums = re.sub(r"[^\d]", "", val)
    return int(nums) if nums else None

def auto_scrape_rates():
    """كشط الأخبار وتحديث الأسعار"""
    global data_store
    url = "https://shafaq.com/ar/اقتصـاد"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            text = soup.get_text()
            
            kifah_found = re.search(r"الكفاح.*?([\d,]{6,7})", text)
            sell_found = re.search(r"البيع.*?([\d,]{6,7})", text)
            buy_found = re.search(r"الشراء.*?([\d,]{6,7})", text)
            
            if kifah_found:
                p = clean_price(kifah_found.group(1))
                if p and 120000 < p < 220000:
                    data_store["rates"]["kifah"] = p
                    data_store["rates"]["harithiya"] = p
            
            if sell_found and buy_found:
                s = clean_price(sell_found.group(1))
                b = clean_price(buy_found.group(1))
                if s and b:
                    data_store["rates"]["exchange_shops"]["sell"] = s
                    data_store["rates"]["exchange_shops"]["buy"] = b
            
            data_store["last_updated"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
            data_store["source_status"] = "synced_online"
            print(f"[{datetime.now()}] تم تحديث الأسعار بنجاح.")
    except Exception as err:
        print(f"Scrape error: {err}")

# إدارة بدء وإيقاف الخدمات عبر Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_scrape_rates()
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_scrape_rates, 'interval', minutes=10)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Iraq Dollar Live API", lifespan=lifespan)

# السماح لجميع الاتصالات
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "running", "service": "Iraq Dollar Live API"}

@app.get("/api/v1/rates")
def get_rates():
    return data_store

@app.post("/api/v1/rates/force-update")
def force_update():
    auto_scrape_rates()
    return {"status": "ok", "data": data_store}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)