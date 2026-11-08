import os
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

PAYMENT_ACCOUNTS = {
    "kpay": {
        "id": "kpay",
        "title": "KBZPay (KPay)",
        "name": os.environ.get("KPAY_NAME", "Ma Moe Thu Zar"),
        "number": os.environ.get("KPAY_NUMBER", "09766646412"),
        "color": "#1d3557",
        "icon": "🔵",
        "currency": "MMK",
        "qr": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('KPAY_NUMBER', '09766646412')}",
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('KPAY_NUMBER', '09766646412')}"
    },
    "promptpay": {
        "id": "promptpay",
        "title": "PromptPay (Prove Pay)",
        "name": os.environ.get("PROMPTPAY_NAME", "MR.AUNG MYAT TUN"),
        "number": os.environ.get("PROMPTPAY_NUMBER", "0816404238"),
        "color": "#005696",
        "icon": "🇹🇭",
        "currency": "THB",
        "qr": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('PROMPTPAY_NUMBER', '0816404238')}",
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('PROMPTPAY_NUMBER', '0816404238')}"
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

OFFICIAL_GLO_3D_BACKUP = {
    "first_prize": "187221",
    "threed": "221",
    "adjacent_tickets": ["187220", "187222"],
    "adjacent_threed": ["220", "222"],
    "front_3d": ["036", "923"],
    "back_3d": ["980", "547"],
    "back_2d": "38",
    "date": "16-11-2024",
    "source": "Thai Government Lottery Office (GLO) Official"
}

CACHED_3D = None
CACHED_3D_TIME = 0

def http_get_json(url, timeout=4):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
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

def parse_glo_response(raw_text):
    data = json.loads(raw_text)
    resp = data.get("response") or data.get("data") or data
    
    first_prize = ""
    first_obj = resp.get("first", {})
    if isinstance(first_obj, dict):
        nums = first_obj.get("number", [])
        if nums and isinstance(nums, list):
            first_prize = str(nums[0].get("value", nums[0]))
    elif isinstance(first_obj, list) and first_obj:
        first_prize = str(first_obj[0].get("value", first_obj[0]))
    elif isinstance(first_obj, str):
        first_prize = first_obj

    if not first_prize or len(first_prize) < 6:
        raise ValueError("Invalid first prize: " + str(first_prize))

    threed = first_prize[-3:]
    
    last2_val = ""
    last2_obj = resp.get("last2", {})
    if isinstance(last2_obj, dict):
        l2_nums = last2_obj.get("number", [])
        if l2_nums:
            last2_val = str(l2_nums[0].get("value", l2_nums[0]))
    elif isinstance(last2_obj, list) and last2_obj:
        last2_val = str(last2_obj[0].get("value", last2_obj[0]))
    elif isinstance(last2_obj, str):
        last2_val = last2_obj

    front3d_list = []
    last3f_obj = resp.get("last3f", {})
    if isinstance(last3f_obj, dict):
        for item in last3f_obj.get("number", []):
            val = str(item.get("value", item))
            if val:
                front3d_list.append(val)
    elif isinstance(last3f_obj, list):
        for item in last3f_obj:
            val = str(item.get("value", item) if isinstance(item, dict) else item)
            if val:
                front3d_list.append(val)

    back3d_list = []
    last3b_obj = resp.get("last3b", {})
    if isinstance(last3b_obj, dict):
        for item in last3b_obj.get("number", []):
            val = str(item.get("value", item))
            if val:
                back3d_list.append(val)
    elif isinstance(last3b_obj, list):
        for item in last3b_obj:
            val = str(item.get("value", item) if isinstance(item, dict) else item)
            if val:
                back3d_list.append(val)

    adj_threed = []
    adj_tickets = []
    near1_obj = resp.get("near1", {})
    if isinstance(near1_obj, dict):
        for item in near1_obj.get("number", []):
            t_val = str(item.get("value", item))
            if t_val:
                adj_tickets.append(t_val)
                if len(t_val) >= 3:
                    adj_threed.append(t_val[-3:])
    
    if not adj_threed and len(first_prize) == 6:
        p_int = int(first_prize)
        adj_tickets = [f"{p_int-1:06d}", f"{p_int+1:06d}"]
        adj_threed = [f"{(int(threed)-1)%1000:03d}", f"{(int(threed)+1)%1000:03d}"]

    draw_date = str(resp.get("displayDate") or resp.get("date") or "Official Latest")

    return {
        "success": True,
        "source": "Thai Government Lottery Office (GLO) Official API (www.glo.or.th)",
        "date": draw_date,
        "first_prize": first_prize,
        "threed": threed,
        "adjacent_tickets": adj_tickets,
        "adjacent_threed": adj_threed,
        "front_3d": front3d_list,
        "back_3d": back3d_list,
        "back_2d": last2_val
    }

def parse_rayriffy_response(raw_text):
    data = json.loads(raw_text)
    resp = data.get("response", {})
    prizes = resp.get("prizes", [])
    draw_date = resp.get("date", "Latest")

    first_prize = ""
    front3d_list = []
    back3d_list = []
    last2_val = ""
    adj_tickets = []
    adj_threed = []

    for p in prizes:
        pid = p.get("id")
        nums = p.get("number", [])
        if pid == "first" and nums:
            first_prize = str(nums[0])
        elif pid == "threeFront":
            front3d_list = [str(n) for n in nums]
        elif pid == "threeBack":
            back3d_list = [str(n) for n in nums]
        elif pid == "twoBack" and nums:
            last2_val = str(nums[0])
        elif pid == "nearFirst":
            adj_tickets = [str(n) for n in nums]
            adj_threed = [str(n)[-3:] for n in nums if len(str(n)) >= 3]

    if not first_prize or len(first_prize) < 6:
        raise ValueError("Invalid first prize from rayriffy")

    threed = first_prize[-3:]
    if not adj_threed:
        p_int = int(first_prize)
        adj_tickets = [f"{p_int-1:06d}", f"{p_int+1:06d}"]
        adj_threed = [f"{(int(threed)-1)%1000:03d}", f"{(int(threed)+1)%1000:03d}"]

    return {
        "success": True,
        "source": "Thai Official GLO Live (rayriffy mirror)",
        "date": draw_date,
        "first_prize": first_prize,
        "threed": threed,
        "adjacent_tickets": adj_tickets,
        "adjacent_threed": adj_threed,
        "front_3d": front3d_list,
        "back_3d": back3d_list,
        "back_2d": last2_val
    }

def fetch_realtime_3d():
    global CACHED_3D, CACHED_3D_TIME
    now_ts = time.time()
    if CACHED_3D and (now_ts - CACHED_3D_TIME < 60):
        return CACHED_3D

    # 1. Primary: Official Thai Government Lottery Office (GLO) API
    try:
        url = "https://www.glo.or.th/api/lottery/getLatestLottery"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw_text = response.read().decode("utf-8")
                res = parse_glo_response(raw_text)
                res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
                CACHED_3D = res
                CACHED_3D_TIME = now_ts
                return res
    except Exception as e:
        pass

    # 2. Secondary: Rayriffy Thai Lotto Live API mirror
    try:
        url = "https://lotto.api.rayriffy.com/latest"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw_text = response.read().decode("utf-8")
                res = parse_rayriffy_response(raw_text)
                res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
                CACHED_3D = res
                CACHED_3D_TIME = now_ts
                return res
    except Exception as e:
        pass

    # 3. Fallback
    if CACHED_3D:
        return CACHED_3D

    res = dict(OFFICIAL_GLO_3D_BACKUP)
    res["success"] = True
    res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
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
