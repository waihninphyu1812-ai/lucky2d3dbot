import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

PAYMENT_ACCOUNTS = {
    "kpay": {
        "name": "Daw Noe Noe",
        "number": "09123456789",
        "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=09123456789"
    },
    "promptpay": {
        "name": "Noe Noe",
        "number": "0987654321",
        "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=0987654321"
    },
    "kbank": {
        "name": "Noe Noe",
        "number": "123-4-56789-0",
        "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=123-4-56789-0"
    }
}

THAI_HOLIDAYS_2026 = {
    "01-01-2026": "New Year's Day (နှစ်သစ်ကူးနေ့)",
    "02-01-2026": "New Year Holiday",
    "03-03-2026": "Makha Bucha Day",
    "06-04-2026": "Chakri Memorial Day",
    "13-04-2026": "Songkran Festival (သင်္ကြန်ရုံးပိတ်ရက်)",
    "14-04-2026": "Songkran Festival (သင်္ကြန်ရုံးပိတ်ရက်)",
    "15-04-2026": "Songkran Festival (သင်္ကြန်ရုံးပိတ်ရက်)",
    "01-05-2026": "National Labour Day (အလုပ်သမားနေ့)",
    "04-05-2026": "Coronation Day",
    "01-06-2026": "Visakha Bucha Day",
    "28-07-2026": "H.M. King's Birthday",
    "12-08-2026": "H.M. Queen Sirikit The Queen Mother's Birthday",
    "13-10-2026": "King Bhumibol Adulyadej Memorial Day",
    "23-10-2026": "Chulalongkorn Day",
    "07-12-2026": "King Bhumibol Adulyadej's Birthday Substitution",
    "10-12-2026": "Constitution Day",
    "31-12-2026": "New Year's Eve"
}

OFFICIAL_GLO_3D_RESULTS = {
    "01-11-2026": {
        "first_prize": "423224",
        "threed": "224",
        "adjacent_tickets": ["423223", "423225"],
        "adjacent_threed": ["223", "225"],
        "front_3d": ["300", "950"],
        "back_3d": ["393", "804"],
        "back_2d": "85",
        "date": "01-11-2026",
        "source": "Thai Government Lottery Office (GLO) Official"
    }
}

def http_get_json(url, timeout=4):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception:
        pass
    return None

def is_market_holiday():
    tz_th = timezone(timedelta(hours=7))
    now = datetime.now(tz_th)
    if now.weekday() in [5, 6]:
        return True, "စနေ/တနင်္ဂနွေ ပိတ်ရက်"
    d_str = now.strftime("%d-%m-%Y")
    if d_str in THAI_HOLIDAYS_2026:
        return True, THAI_HOLIDAYS_2026[d_str]
    return False, ""

def fetch_realtime_2d():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    date_str = now.strftime("%d-%m-%Y")
    is_hol, hol_reason = is_market_holiday()

    res = {
        "success": True,
        "live_2d": "--",
        "live_set": "--",
        "live_value": "--",
        "morning_1201": "--",
        "evening_1630": "--",
        "date": date_str,
        "is_open": not is_hol,
        "holiday_reason": hol_reason if is_hol else ""
    }

    if is_hol:
        return res

    data = http_get_json("https://api.thaistock2d.com/live", timeout=4)
    if data and isinstance(data, dict):
        live_obj = data.get("live", {})
        res["live_set"] = str(live_obj.get("set", "--"))
        res["live_value"] = str(live_obj.get("value", "--"))
        res["live_2d"] = str(live_obj.get("twod", "--"))

        result_list = data.get("result", [])
        for item in result_list:
            open_time = str(item.get("open_time", ""))
            twod_val = str(item.get("twod", "--"))
            if "12:01" in open_time:
                res["morning_1201"] = twod_val
            elif "16:30" in open_time:
                res["evening_1630"] = twod_val
    return res

def fetch_realtime_3d():
    res = dict(OFFICIAL_GLO_3D_RESULTS["01-11-2026"])
    res["success"] = True
    res["next_date"] = "16-11-2026 (ညနေ ၃:၃၀ နာရီ)"
    return res

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        payload = {
            "twod": d2,
            "threed": d3,
            "user_balance": {"mmk": 0, "thb": 0},
            "payment_accounts": PAYMENT_ACCOUNTS
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return
