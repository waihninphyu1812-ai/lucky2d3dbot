import os
import re
import json
import time
import random
import threading
try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.error

from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== RENDER 24/7 WEB SERVER (PORT 10000) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Lucky2D3D Official Real-Time Bot Running Live 24/7!".encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Health Server Error: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

# ==================== BOT CONFIG & ADMIN ====================
TOKEN = '8988776248:AAFgvT1qJn60-eM71QicjcAXrioqk7kxOK4'
ADMIN_USERNAME = "snow78"
ADMIN_EMAIL = "waihninphyu1812@gmail.com"

# HTTP Headers for authentic scraping
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
}

# ==================== RESILIENT HTTP CLIENT (NO MODULE CRASH) ====================

def http_get_json(url, timeout=7):
    """
    requests မရှိသော်လည်း Python ၏ မူရင်း urllib ဖြင့် အလိုအလျောက် ဆွဲယူပေးသော Function
    """
    if requests is not None:
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code == 200:
                raw_bytes = resp.read()
                return json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        pass
    return None

def http_post_json(url, payload=None, timeout=8):
    """
    HTTP POST Request (GLO ထီရလဒ်ဆွဲယူရန်)
    """
    if requests is not None:
        try:
            r = requests.post(url, json=payload or {}, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass

    try:
        data_bytes = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=HEADERS)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code == 200:
                raw_bytes = resp.read()
                return json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        pass
    return None

# In-memory storage for bets, balances, and admin overrides
user_bets = {}
user_balances = {}
admin_override = {
    "2d": None,
    "3d": None
}

# ==================== 100% REAL-TIME SCRAPING & API (ZERO MOCK DATA) ====================

def calculate_2d(set_val, val_val):
    """
    ထိုင်းစတော့အိတ်ချိန်း (SET) အညွှန်းကိန်း နှင့် တန်ဖိုးတို့မှ 2D ကို တရားဝင် ဖော်မြူလာအတိုင်း တွက်ထုတ်ခြင်း
    SET Index ဒသမနောက်ဆုံးဂဏန်း + Value ဒသမနောက်ဆုံးဂဏန်း
    """
    try:
        s_str = str(set_val).replace(",", "").strip()
        v_str = str(val_val).replace(",", "").strip()
        if "." in s_str and "." in v_str:
            d1 = s_str.split(".")[1][-1]
            d2 = v_str.split(".")[1][-1]
            return f"{d1}{d2}"
    except Exception:
        pass
    return None

def extract_time(obj):
    t = obj.get("open_time")
    if not t:
        t = obj.get("time")
    return str(t or "")[:5]

def extract_set(obj):
    s = obj.get("stock")
    if not s:
        s = obj.get("set")
    return str(s or "").strip()

def extract_value(obj):
    v = obj.get("value")
    if not v:
        v = obj.get("val")
    return str(v or "").strip()

def extract_twod(obj):
    num = obj.get("number")
    if not num:
        num = obj.get("twod")
    return str(num or "").strip()

def fetch_realtime_2d():
    """
    ထိုင်း SET ဈေးကွက်မှ ၂လုံး (2D Live) အချက်အလက်အစစ်များကို တိုက်ရိုက်ဆွဲထုတ်ခြင်း (Zero Mock Data)
    """
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)

    data_result = {
        "is_open": True,
        "is_holiday": False,
        "date": now.strftime("%d-%m-%Y"),
        "live_set": "--",
        "live_value": "--",
        "live_2d": "--",
        "live_time": now.strftime("%H:%M:%S"),
        "slots": {
            "11:00": {"time": "11:00 AM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"},
            "12:01": {"time": "12:01 PM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"},
            "15:00": {"time": "03:00 PM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"},
            "16:30": {"time": "04:30 PM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"}
        },
        "last_result": None
    }

    if now.weekday() in [5, 6]:
        data_result["is_open"] = False
        data_result["is_holiday"] = True

    try:
        # ၁။ ThaiStock2D Live Feed မှ တိုက်ရိုက် ရယူခြင်း
        raw = http_get_json("https://api.thaistock2d.com/live", timeout=7)
        if raw and isinstance(raw, dict):
            live = raw.get("live", {})
            results = raw.get("result", [])

            set_num = str(live.get("set", "")).strip()
            val_num = str(live.get("value", "")).strip()
            time_str = str(live.get("time", "")).strip()
            twod_num = str(live.get("twod", "")).strip()

            if set_num and set_num not in ["0.00", "0", "-", "None"]:
                data_result["live_set"] = set_num
                data_result["live_value"] = val_num
                data_result["live_time"] = time_str if time_str else now.strftime("%H:%M:%S")
                data_result["live_2d"] = twod_num if (twod_num and twod_num not in ["--", "00"]) else calculate_2d(set_num, val_num)

            valid_slots_found = 0
            if isinstance(results, list):
                for item in results:
                    slot_time = extract_time(item)
                    slot_set = extract_set(item)
                    slot_val = extract_value(item)
                    slot_twod = extract_twod(item)

                    if slot_time in data_result["slots"]:
                        if slot_set and slot_set not in ["0.00", "0", "-", "None"]:
                            valid_slots_found += 1
                            tw = slot_twod if (slot_twod and slot_twod not in ["--", "00"]) else calculate_2d(slot_set, slot_val)
                            data_result["slots"][slot_time] = {
                                "time": data_result["slots"][slot_time]["time"],
                                "set": slot_set,
                                "val": slot_val,
                                "twod": tw if tw else "--",
                                "status": "ထွက်ရှိပြီး"
                            }
                            data_result["last_result"] = tw

            # ဈေးကွက်ပိတ်ချိန်တွင် နောက်ဆုံးဖွင့်ရက်၏ တရားဝင်ရလဒ်အစစ်များကို ဆွဲယူခြင်း
            if data_result["live_set"] == "--" or valid_slots_found == 0:
                hist_data = http_get_json("https://api.thaistock2d.com/2d_result", timeout=7)
                if hist_data and isinstance(hist_data, list):
                    for day in hist_data:
                        day_date = day.get("date", "")
                        children = day.get("child", [])
                        day_valid = False

                        for c in children:
                            c_time = extract_time(c)
                            c_set = extract_set(c)
                            c_val = extract_value(c)
                            c_twod = extract_twod(c)

                            if c_time in data_result["slots"] and c_set not in ["0.00", "0", "-", "None"]:
                                day_valid = True
                                tw = c_twod if (c_twod and c_twod not in ["--", "00"]) else calculate_2d(c_set, c_val)
                                data_result["slots"][c_time] = {
                                    "time": data_result["slots"][c_time]["time"],
                                    "set": c_set,
                                    "val": c_val,
                                    "twod": tw if tw else "--",
                                    "status": "ထွက်ရှိပြီး"
                                }
                                data_result["last_result"] = tw

                        if day_valid:
                            data_result["date"] = day_date
                            data_result["is_open"] = False
                            break
    except Exception as e:
        print(f"2D
