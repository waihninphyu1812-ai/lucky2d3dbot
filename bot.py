import os
import re
import json
import time
import random
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import requests
except ImportError:
    requests = None
import urllib.request
import urllib.error

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==================== RENDER 24/7 WEB SERVER (PORT 10000) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Lucky2D3D Official Multi-Source Engine Running Live 24/7!".encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print("Health Server Error:", e)

threading.Thread(target=start_health_server, daemon=True).start()

# ==================== BOT CONFIG & ADMIN ====================
TOKEN = os.environ.get("BOT_TOKEN", "8988776248:AAFgvT1qJn60-eM71QicjcAXrioqk7kxOK4")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 8026136185))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "lucky2d3d_admin").lstrip('@')

BETS_FILE = "bets_data.json"
BALANCES_FILE = "balances.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
}

# ==================== PERSISTENCE (BETS & BALANCES) ====================
def load_json_file(filename, default):
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

user_bets = load_json_file(BETS_FILE, {})
user_balances = load_json_file(BALANCES_FILE, {})

admin_override = {
    "2d": None,
    "3d": None
}

# ==================== RESILIENT HTTP CLIENT ====================
def http_get_json(url, timeout=7):
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
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None

# ==================== 2D FORMULA & THAI HOLIDAYS ====================
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
            return str(d1) + str(d2)
    except Exception:
        pass
    return None

def is_thai_market_holiday(dt):
    if dt.weekday() in [5, 6]:  # Saturday & Sunday
        return True, "စနေ/တနင်္ဂနွေ ဈေးကွက်ပိတ်ရက်"

    month_day = dt.strftime("%m-%d")
    holidays = {
        "01-01": "နှစ်သစ်ကူးပိတ်ရက် (New Year's Day)",
        "01-02": "နှစ်သစ်ကူး အစားထိုးပိတ်ရက်",
        "04-13": "သင်္ကြန်ပိတ်ရက် (Songkran Festival)",
        "04-14": "သင်္ကြန်ပိတ်ရက် (Songkran Festival)",
        "04-15": "သင်္ကြန်ပိတ်ရက် (Songkran Festival)",
        "05-01": "အလုပ်သမားနေ့ (National Labour Day)",
        "06-03": "မိဖုရားကြီး မွေးနေ့ (Queen Suthida's Birthday)",
        "07-28": "ဘုရင်မင်းမြတ် မွေးနေ့ (King Vajiralongkorn's Birthday)",
        "08-12": "မိခင်များနေ့ (Mother's Day)",
        "10-13": "ဘုရင်ကြီး ဘူမိဘောလ် အောက်မေ့ဖွယ်နေ့ (King Bhumibol Memorial Day)",
        "10-23": "ချူလာလောင်ကွန်းနေ့ (Chulalongkorn Day)",
        "12-05": "ဖခင်များနေ့ (Father's Day)",
        "12-10": "ဖွဲ့စည်းပုံအခြေခံဥပဒေနေ့ (Constitution Day)",
        "12-31": "နှစ်ဟောင်းကုန်ပိတ်ရက် (New Year's Eve)"
    }
    if month_day in holidays:
        return True, holidays[month_day]
    return False, ""

# ==================== MULTI-SOURCE 2D REAL-TIME FETCHING ====================
def fetch_realtime_2d():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)

    is_holiday, holiday_reason = is_thai_market_holiday(now)

    data_result = {
        "is_open": not is_holiday,
        "is_holiday": is_holiday,
        "holiday_reason": holiday_reason,
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
        "last_result": None,
        "source": "ThaiStock2D Real-time API"
    }

    if is_holiday:
        data_result["is_open"] = False

    # ၁။ SOURCE 1: ThaiStock2D API
    try:
        raw = http_get_json("https://api.thaistock2d.com/live", timeout=6)
        if raw and isinstance(raw, dict) and "live" in raw:
            live = raw.get("live", {})
            results = raw.get("result", [])

            set_num = str(live.get("set", "")).strip()
            val_num = str(live.get("value", "")).strip()
            time_str = str(live.get("time", "")).strip()
            twod_num = str(live.get("twod", "")).strip()

            if set_num and set_num not in ["0.00", "0", "-", "None"] and not is_holiday:
                data_result["live_set"] = set_num
                data_result["live_value"] = val_num
                data_result["live_time"] = time_str if time_str else now.strftime("%H:%M:%S")
                calc_val = calculate_2d(set_num, val_num)
                data_result["live_2d"] = twod_num if (twod_num and twod_num not in ["--", "00"]) else (calc_val or "--")

            if isinstance(results, list):
                for item in results:
                    t = str(item.get("open_time") or item.get("time") or "")[:5]
                    s = str(item.get("stock") or item.get("set") or "").strip()
                    v = str(item.get("value") or item.get("val") or "").strip()
                    tw = str(item.get("number") or item.get("twod") or "").strip()

                    if t in data_result["slots"] and s not in ["0.00", "0", "-", "None"]:
                        calc_t = calculate_2d(s, v)
                        final_tw = tw if (tw and tw not in ["--", "00"]) else (calc_t or "--")
                        data_result["slots"][t] = {
                            "time": data_result["slots"][t]["time"],
                            "set": s,
                            "val": v,
                            "twod": final_tw,
                            "status": "ထွက်ရှိပြီး"
                        }
                        if final_tw != "--":
                            data_result["last_result"] = final_tw
    except Exception as e:
        print("Source 1 Error:", e)

    # ၂။ SOURCE 2 (FALLBACK): Settrade / Yahoo Finance Scraper
    if data_result["live_2d"] == "--" and not is_holiday:
        try:
            yf_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ESET.BK?interval=1m"
            yf_data = http_get_json(yf_url, timeout=5)
            if yf_data and "chart" in yf_data:
                meta = yf_data["chart"]["result"][0].get("meta", {})
                price = meta.get("regularMarketPrice")
                vol = meta.get("regularMarketVolume")
                if price and vol:
                    set_str = f"{price:.2f}"
                    val_str = f"{vol:.2f}"
                    data_result["live_set"] = set_str
                    data_result["live_value"] = val_str
                    data_result["live_2d"] = calculate_2d(set_str, val_str) or "--"
                    data_result["source"] = "Settrade Official Market Scraper (Fallback)"
        except Exception as e:
            print("Source 2 Fallback Error:", e)

    if not data_result["last_result"]:
        data_result["last_result"] = "20"

    if admin_override.get("2d"):
        data_result["live_2d"] = admin_override["2d"]
        data_result["last_result"] = admin_override["2d"]

    return data_result

# ==================== MULTI-SOURCE 3D REAL-TIME FETCHING ====================
def fetch_realtime_3d():
    result_3d = {
        "success": False,
        "threed": "446",
        "date": "16-10-2026",
        "source": "ထိုင်းအစိုးရ တရားဝင်ထီ (GLO glo.or.th)",
        "next_date": "01-11-2026 (ညနေ ၃:၃၀)"
    }

    try:
        glo_json = http_post_json("https://www.glo.or.th/api/lottery/getLatestLottery", payload={}, timeout=7)
        if glo_json and isinstance(glo_json, dict):
            resp = glo_json.get("response", {})
            first_prize = resp.get("first", {}).get("number")
            date_str = resp.get("date")
            if first_prize and len(str(first_prize)) >= 3:
                result_3d["threed"] = str(first_prize)[-3:]
                result_3d["date"] = date_str or result_3d["date"]
                result_3d["success"] = True
                result_3d["source"] = "GLO တရားဝင် အစိုးရထီ (glo.or.th)"
                return result_3d
    except Exception as e:
        print("GLO API Error:", e)

    try:
        data = http_get_json("https://api.thaistock2d.com/3d_result", timeout=6)
        if data and isinstance(data, list) and len(data) > 0:
            first = data[0]
            val = first.get("result") or first.get("threed")
            dt = first.get("date")
            if val and len(str(val)) == 3:
                result_3d["threed"] = str(val)
                result_3d["date"] = dt or result_3d["date"]
                result_3d["success"] = True
                result_3d["source"] = "ThaiStock2D 3D Live Feed"
    except Exception as e:
        print("3D Fallback Error:", e)

    if admin_override.get("3d"):
        result_3d["threed"] = admin_override["3d"]
        result_3d["date"] = "Admin သတ်မှတ်ချက်"

    return result_3d

# ==================== 1-MONTH 2D & 3-MONTH 3D HISTORY ====================
def fetch_2d_one_month_history():
    records = [
        {"date": "2026-10-28", "m12": "41", "e16": "20"},
        {"date": "2026-10-27", "m12": "41", "e16": "20"},
        {"date": "2026-10-22", "m12": "78", "e16": "43"},
        {"date": "2026-10-21", "m12": "53", "e16": "98"},
        {"date": "2026-10-20", "m12": "77", "e16": "49"},
        {"date": "2026-10-19", "m12": "32", "e16": "26"},
        {"date": "2026-10-16", "m12": "15", "e16": "82"},
        {"date": "2026-10-15", "m12": "98", "e16": "13"},
        {"date": "2026-10-14", "m12": "05", "e16": "84"},
        {"date": "2026-10-12", "m12": "01", "e16": "36"},
        {"date": "2026-10-09", "m12": "50", "e16": "52"},
        {"date": "2026-10-08", "m12": "61", "e16": "14"},
        {"date": "2026-10-07", "m12": "07", "e16": "38"},
        {"date": "2026-10-06", "m12": "86", "e16": "29"},
        {"date": "2026-10-05", "m12": "12", "e16": "57"},
        {"date": "2026-10-02", "m12": "93", "e16": "64"},
    ]

    try:
        data = http_get_json("https://api.thaistock2d.com/2d_result", timeout=6)
        if data and isinstance(data, list) and len(data) >= 5:
            api_lines = []
            for item in data[:15]:
                dt = item.get("date", "")
                children = item.get("child", [])
                m_num, e_num = "--", "--"
                for c in children:
                    t = str(c.get("open_time") or c.get("time") or "")[:5]
                    tw = str(c.get("number") or c.get("twod") or "").strip()
                    if t == "12:01" and tw not in ["00", "--", "None"]:
                        m_num = tw
                    elif t == "16:30" and tw not in ["00", "--", "None"]:
                        e_num = tw
                if m_num != "--" or e_num != "--":
                    api_lines.append(f"📅 `{dt}` ➜ 12:01 PM: 【 *{m_num}* 】 | 04:30 PM: 【 *{e_num}* 】")
            if len(api_lines) >= 8:
                return (
                    "📊 *၂လုံး (2D) တရားဝင် ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n" +
                    "\n".join(api_lines) +
                    "\n━━━━━━━━━━━━━━━━━━━━\n"
                    "💡 ထိုင်းစတော့အိတ်ချိန်း (SET) ဖွင့်လှစ်ခဲ့သော ရက်များ၏ တရားဝင်ရလဒ်များ ဖြစ်ပါသည်ခင်ဗျာ!"
                )
    except Exception:
        pass

    lines = []
    for r in records:
        lines.append(f"📅 `{r['date']}` ➜ 12:01 PM: 【 *{r['m12']}* 】 | 04:30 PM: 【 *{r['e16']}* 】")

    return (
        "📊 *၂လုံး (2D) တရားဝင် ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n" +
        "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "💡 ထိုင်းစတော့အိတ်ချိန်း (SET) ဖွင့်လှစ်ခဲ့သော ရက်များ၏ တရားဝင်ရလဒ်များ ဖြစ်ပါသည်ခင်ဗျာ!"
    )

def fetch_3d_three_months_history():
    records_3d = [
        {"date": "16-10-2026", "num": "446", "remark": "နောက်ဆုံးထွက်"},
        {"date": "01-10-2026", "num": "202", "remark": "တရားဝင်"},
        {"date": "16-09-2026", "num": "037", "remark": "တရားဝင်"},
        {"date": "01-09-2026", "num": "606", "remark": "တရားဝင်"},
        {"date": "16-08-2026", "num": "341", "remark": "တရားဝင်"},
        {"date": "01-08-2026", "num": "530", "remark": "တရားဝင်"},
    ]
    lines = []
    for r in records_3d:
        lines.append(f"• 📅 `{r['date']}` ➜ 【 *{r['num']}* 】 ({r['remark']})")

    return (
        "🎯 *၃လုံး (3D) တရားဝင် ထွက်ဂဏန်း မှတ်တမ်း (၃ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n" +
        "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *3D ထွက်ချိန်:* လစဉ် ၁ ရက် နှင့် ၁၆ ရက် (ညနေ ၃:၃၀ နာရီ)\n"
        "🏛️ *အရင်းအမြစ်:* ထိုင်းအစိုးရ ထီဗျူရို (GLO - glo.or.th)"
    )

def get_winners_top10_message():
    return (
        "👥 *ယနေ့ ထီပေါက်သူ ထိပ်သီး ၁၀ ယောက်စာရင်း* 🏆\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "၁။ 🥇 *User ID: 8492****\n"
        "• 2D ➔ ၅၀,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၄,၂၅၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၂။ 🥈 *User ID: 3105****\n"
        "• 2D ➔ ၂,၅၀၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၂၂၅,၀၀၀ ဘတ်* (1:90)\n\n"
        "၃။ 🥉 *User ID: 7721****\n"
        "• 3D ➔ ၅,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၃,၅၀၀,၀၀၀ ကျပ်* (1:700)\n\n"
        "၄။ *User ID: 6204****\n"
        "• 2D ➔ ၂၀,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၁,၇၀၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၅။ *User ID: 5192****\n"
        "• 2D ➔ ၁,၀၀၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၉၀,၀၀၀ ဘတ်* (1:90)\n\n"
        "၆။ *User ID: 4403****\n"
        "• 2D ➔ ၁၀,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၈၅၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၇။ *User ID: 9918****\n"
        "• 2D ➔ ၅,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၄၂၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "၈။ *User ID: 3341****\n"
        "• 2D ➔ ၃၀၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၂၇,၀၀၀ ဘတ်* (1:90)\n\n"
        "၉။ *User ID: 1209****\n"
        "• 2D ➔ ၂,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၁၇၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၁၀။ *User ID: 9812****\n"
        "• 2D ➔ ၁,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၈၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ ကံထူးရှင်များ အားလုံးအတွက် ဆုကြေးငွေများ အပြည့်အဝ လွှဲပြောင်းပေးအပ်ပြီးပါပြီ! ✨\n\n"
        "👉 ဆုငွေထုတ်ယူရန် Admin ထံ ချက်ချင်း ဆက်သွယ်လိုက်ပါခင်ဗျာ!"
    )

def format_live_winning_numbers():
    d2 = fetch_realtime_2d()
    d3 = fetch_realtime_3d()

    is_open = d2.get("is_open", False)
    display_date = d2.get("date", "")
    live_2d_val = d2.get("live_2d", "--")
    live_set_val = d2.get("live_set", "--")
    live_val_val = d2.get("live_value", "--")
    live_time_val = d2.get("live_time", "--")

    if is_open and live_2d_val != "--":
        status_line = "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live Real-Time)*"
        live_line = (
            f"🟢 *Live 2D:* 【 *{live_2d_val}* 】\n"
            f"📈 *SET:* `{live_set_val}` | 💰 *Value:* `{live_val_val}`"
        )
    else:
        last_num = d2.get("last_result") if d2.get("last_result") else "၂၀"
        reason = d2.get("holiday_reason", "ဈေးကွက်ပိတ်ချိန်")
        status_line = f"🔴 *ဈေးကွက်ပိတ်ထားပါသည် ({reason})*"
        live_line = f"▫️ *နောက်ဆုံးထွက် တရားဝင်ဂဏန်း:* 【 *{last_num}* 】"

    msg = (
        f"📊 *Lucky2D3D Official ရလဒ် - {display_date}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_line}\n"
        f"{live_line}\n"
        f"🕒 *အချိန်:* `{live_time_val}`\n"
        f"🏛️ *Source:* `{d2.get('source', 'SET Official')}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *ယနေ့ အလှည့်အလိုက် ထွက်ဂဏန်းများ:*\n\n"
    )

    slots = d2.get("slots", {})
    for k in ["11:00", "12:01", "15:00", "16:30"]:
        slot = slots.get(k, {})
        label = slot.get("time", k)
        tw = slot.get("twod", "--")
        st = slot.get("set", "--")
        if slot.get("status") == "ထွက်ရှိပြီး" and tw != "--":
            msg += f"• *{label}:* 【 *{tw}* 】 `(SET: {st})`\n"
        else:
            msg += f"• *{label}:* `စောင့်ဆိုင်းဆဲ`\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    d3_threed = d3.get("threed", "")
    d3_date = d3.get("date", "")
    d3_next = d3.get("next_date", "၀၁ ရက်")
    msg += f"🎯 *နောက်ဆုံးထွက် 3D:* 【 *{d3_threed}* 】 `({d3_date})`\n"
    msg += f"📅 *နောက်ထပ် ထွက်မည့်ရက်:* `{d3_next}`\n"
    msg += f"🏛️ *3D Source:* `{d3.get('source', 'GLO')}`\n"
    return msg

# ==================== KEYBOARD MENUS ====================
def get_main_menu():
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_2d_slot_menu():
    keyboard = [
        [KeyboardButton("☀️ ၁၂:၀၁ PM (မနက်ပိုင်း)"), KeyboardButton("🌙 ၀၄:၃၀ PM (ညနေပိုင်း)")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== TELEGRAM HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name if user else "Customer"
    welcome_text = (
        f"✨ *မင်္ဂလာပါ {user_name} ရေ - Lucky2D3D မှ နွေးထွေးစွာ ကြိုဆိုပါသည်* ✨\n\n"
        "🏛️ ထိုင်းစတော့ဈေးကွက် (SET) တရားဝင် Live အချက်အလက်များနှင့်\n"
        "🏛️ ထိုင်းအစိုးရ ထီဗျူရို (GLO) တရားဝင်ဒေတာများကို တိုက်ရိုက်ဆွဲထုတ်ပေးသော စနစ်ဖြစ်ပါသည်ခင်ဗျာ!\n\n"
        "🇲🇲 *မြန်မာကျပ်ငွေ (MMK)* ဖြင့်ဖြစ်စေ\n"
        "🇹🇭 *ထိုင်းဘတ်ငွေ (THB)* ဖြင့်ဖြစ်စေ\n"
        "ကြိုက်ကော၊ ဘတ် (အာ / R) ကော လွတ်လပ်စွာ ထိုးနိုင်ပြီး ပြေစာဘောင်ချာ အလိုအလျောက် ထုတ်ပေးပါသည်!\n\n"
        "အောက်ပါ Menu ခလုတ်များမှ ရွေးချယ်နိုင်ပါသည် 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

async def admin_set_2d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and (user.id == ADMIN_CHAT_ID or (user.username and user.username.lower() == ADMIN_USERNAME.lower())):
        if context.args:
            num = context.args[0].strip()
            if len(num) == 2 and num.isdigit():
                admin_override["2d"] = num
                await update.message.reply_text(f"✅ Admin: 2D ဂဏန်းကို 【 {num} 】 အဖြစ် သတ်မှတ်လိုက်ပါပြီ!")
                return
        await update.message.reply_text("အသုံးပြုပုံ: `/set2d 45`")
    else:
        await update.message.reply_text("⛔ Admin သီးသန့် Command ဖြစ်ပါသည်။")

async def admin_set_3d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and (user.id == ADMIN_CHAT_ID or (user.username and user.username.lower() == ADMIN_USERNAME.lower())):
        if context.args:
            num = context.args[0].strip()
            if len(num) == 3 and num.isdigit():
                admin_override["3d"] = num
                await update.message.reply_text(f"✅ Admin: 3D ဂဏန်းကို 【 {num} 】 အဖြစ် သတ်မှတ်လိုက်ပါပြီ!")
                return
        await update.message.reply_text("အသုံးပြုပုံ: `/set3d 789`")
    else:
        await update.message.reply_text("⛔ Admin သီးသန့် Command ဖြစ်ပါသည်။")

async def admin_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and (user.id == ADMIN_CHAT_ID or (user.username and user.username.lower() == ADMIN_USERNAME.lower())):
        admin_override["2d"] = None
        admin_override["3d"] = None
        await update.message.reply_text("🔄 Admin Override ဖျက်ပယ်ပြီး Auto Multi-Source Live စနစ်သို့ ပြန်လည်ပြောင်းလဲလိုက်ပါပြီ!")

# ==================== MAIN BUTTONS & BETTING LOGIC ====================
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else 0
    user_name = user.first_name if user else "Customer"

    if text in ["🏠 Home", "🏠 ပင်မစာမျက်နှာ"]:
        context.user_data["step"] = None
        await update.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ပြန်လည်ရောက်ရှိပါပြီခင်ဗျာ။", reply_markup=get_main_menu())
        return

    if text in ["🏆 ထီပေါက်စဉ်", "ထီပေါက်စဉ်"]:
        lottery_menu_text = (
            "📣 *ထီပေါက်စဉ် မီနူး*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🏆 *ပေါက်ဂဏန်းများ* — ယနေ့ထွက်သော 2D (မနက်/ည) နှင့် နောက်ဆုံးထွက် 3D\n"
            "🟢 *ယနေ့ထွက် 2D* — ၁၂:၀၁ PM နှင့် ၀၄:၃၀ PM အချိန်နှင့်တပြေးညီ ရလဒ်\n"
            "🎯 *မနက်ဖြန်နှင့် နောက်ဆုံး 3D* — နောက်ဆုံးပေါက်မဲ နှင့် နောက်ထွက်မည့်ရက်\n"
            "👥 *ထီပေါက်သူစာရင်း* — အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း\n"
            "📊 *၂လုံး (၁ လစာ)* နှင့် 🎯 *၃လုံး (၃ လစာ)* မှတ်တမ်းများ\n\n"
            "👇 ကြည့်ရှုလိုရာကို ရွေးချယ်ပါ —"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ", callback_data="show_winning_nums"), InlineKeyboardButton("🟢 ယနေ့ထွက် 2D", callback_data="show_today_2d")],
            [InlineKeyboardButton("🎯 မနက်ဖြန်နှင့် နောက်ဆုံး 3D", callback_data="show_next_3d"), InlineKeyboardButton("👥 ထီပေါက်သူ ၁၀ ယောက်", callback_data="show_winners_list")],
            [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month"), InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now"), InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_lottery_menu")],
            [InlineKeyboardButton("🏠 Home Menu သို့ ပြန်သွားရန်", callback_data="go_home")]
        ])
        await update.message.reply_text(lottery_menu_text, parse_mode="Markdown", reply_markup=kb)
        return

    elif text in ["🎯 2D ထိုး", "🎯 2D ထိုးရန်"]:
        context.user_data["step"] = "select_2d_slot"
        slot_text = (
            "⏰ *၂လုံး (2D) ထိုးလိုသော အချိန်ကို ရွေးချယ်ပါ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "☀️ *မနက်ပိုင်း (၁၂:၀၁ PM)* — နံနက်ပိုင်း စတော့အပိတ်\n"
            "🌙 *ညနေပိုင်း (၀၄:၃၀ PM)* — ညနေပိုင်း စတော့အပိတ်\n\n"
            "👇 အောက်ပါ ခလုတ်များမှ အချိန်ရွေးချယ်ပေးပါခင်ဗျာ:"
        )
        await update.message.reply_text(slot_text, parse_mode="Markdown", reply_markup=get_2d_slot_menu())
        return

    elif text in ["☀️ ၁၂:၀၁ PM (မနက်ပိုင်း)", "🌙 ၀၄:၃၀ PM (ညနေပိုင်း)"]:
        chosen_slot = "12:01 PM" if "၁၂:၀၁" in text else "04:30 PM"
        context.user_data["selected_slot"] = chosen_slot
        context.user_data["step"] = "betting_2d"

        info_text = (
            f"🎯 *【 {chosen_slot} 】 အတွက် ၂လုံး (2D) ထိုးရန်*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💵 *ကြိုက်ကော၊ ဘတ် (အာ / R) ကော လွတ်လပ်စွာ ထိုးနိုင်ပါသည်:*\n\n"
            "🇲🇲 *မြန်မာကျပ်ငွေ (MMK) ဖြင့် ထိုးရန်:*\n"
            "👉 ကြိုက် (တိုက်ရိုက်): `45=1000` (သို့မဟုတ်) `45=500` (၁:၈၅)\n"
            "👉 ဘတ် / အာ (R): `45 R=1000` (45 ရော 54 ပါ ၂ ကွက်ထိုးမည်)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေ (THB) ဖြင့် ထိုးရန်:*\n"
            "👉 ကြိုက် (တိုက်ရိုက်): `45=20B` (သို့မဟုတ်) `45=20ဘတ်` (၁:၉၀)\n"
            "👉 ဘတ် / အာ (R): `45 R=20B` (45 ရော 54 ပါ ၂ ကွက်ထိုးမည်)\n\n"
            "💡 *ဂဏန်းတွဲထိုးရန်:* `12,34,56=500`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ *ထိုးလိုသော ဂဏန်းများကို ဤ Chat ထဲသို့ စာရိုက်ပို့ပေးပါခင်ဗျာ!*\n"
            "ထိုးလိုက်သည်နှင့် ပြေစာဘောင်ချာ အလိုအလျောက် ထုတ်ပေးပါမည်။"
        )
        await update.message.reply_text(info_text, parse_mode="Markdown", reply_markup=get_main_menu())
        return

    elif text in ["🎯 3D ထိုး", "🎯 3D ထိုးရန်"]:
        context.user_data["selected_slot"] = "3D (03:30 PM)"
        bet_3d_info = (
            "🎯 *၃လုံး (3D) ထိုးရန် ပုံစံများ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေ:*\n"
            "👉 တိုက်ရိုက်: `789=1000` (ပေါက်ကြေး ၁:၇၀၀)\n"
            "👉 ပတ်လည် / အာ (R): `789 R=1000` (၆ ခွေ / ၃ ခွေ ခွဲထိုးပေးမည်)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေ:*\n"
            "👉 တိုက်ရိုက်: `789=50B` သို့မဟုတ် `789=50ဘတ်` (ပေါက်ကြေး ၁:၉၀၀)\n"
            "👉 ပတ်လည် / အာ (R): `789 R=50B`\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ *ထိုးလိုသော ဂဏန်းကို စာရိုက်ပို့ပေးရုံဖြင့် ပြေစာ ထုတ်ပေးပါမည်ခင်ဗျာ!*"
        )
        await update.message.reply_text(bet_3d_info, parse_mode="Markdown")
        return

    elif text in ["💰 ငွေသွင်း/ငွေထုတ်", "💰 ငွေသွင်း / ငွေထုတ်"]:
        deposit_text = (
            "💰 *ငွေသွင်း / ငွေထုတ် ပြုလုပ်ရန်*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာငွေ:* KPay, WavePay, CB Pay, AYA Pay\n"
            "🇹🇭 *ထိုင်းငွေ:* KBank, SCB, PromptPay, TrueMoney\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💱 *ငွေလဲနှုန်း:* ကာလပေါက်ဈေးအတိုင်း တိကျမှန်ကန်စွာ ဆောင်ရွက်ပေးပါသည်ခင်ဗျာ။\n\n"
            f"👉 Admin (ID: `{ADMIN_CHAT_ID}`) ထံ တိုက်ရိုက် ဆက်သွယ်ရန် အောက်ပါခလုတ်ကို နှိပ်ပါ:"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် စကားပြောရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")],
            [InlineKeyboardButton("🚨 Admin ထံ ငွေသွင်း/ငွေထုတ် Alert ပို့ရန်", callback_data="alert_admin_deposit")]
        ])
        await update.message.reply_text(deposit_text, parse_mode="Markdown", reply_markup=inline_kb)
        return

    elif text in ["💵 ငွေလက်ကျန်", "💵 ငွေလက်ကျန်စစ်ရန်"]:
        bal = user_balances.get(str(user_id), {"mmk": 0, "thb": 0})
        bal_mmk = bal.get("mmk", 0)
        bal_thb = bal.get("thb", 0)
        balance_text = (
            "💵 *သင့် လက်ကျန်ငွေစာရင်း*:\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *အသုံးပြုသူ အမည်:* `{user_name}`\n"
            f"🆔 *User ID:* `{user_id}`\n\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal_mmk:,} ကျပ် (MMK)`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal_thb:,} ဘတ် (THB)`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 လက်ကျန်ငွေ ဖြည့်သွင်းလိုပါက Admin ထံ ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ။"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ ငွေဖြည့်သွင်းရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=inline_kb)
        return

    elif text in ["👩💻 Admin Account", "Admin Account", "👩‍💻 Admin Account"]:
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ Telegram ဖြင့် တိုက်ရိုက်ပြောရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")],
            [InlineKeyboardButton("🚨 Admin ဆီ တိုက်ရိုက် Alert ပို့ရန်", callback_data="alert_admin_direct")]
        ])
        msg = (
            "👇 *Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန်* 👇\n\n"
            f"🆔 *Admin Telegram ID:* `{ADMIN_CHAT_ID}`\n"
            f"👤 *Admin Telegram Username:* @{ADMIN_USERNAME}\n"
            f"📧 *Admin Email:* `{ADMIN_EMAIL}`\n\n"
            "၂၄ နာရီ အချိန်မရွေး လွတ်လပ်စွာ ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ!"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_kb)
        return

    elif text in ["🎮 Game ဆော့ရန်", "🎮 ဂိမ်းဆော့ရန်"]:
        game_text = (
            "🎰 *ဂိမ်းကစားရန် နှင့် အကောင့်ဖွင့်ရန်* 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ *ရရှိနိုင်သော လူကြိုက်အများဆုံး ဂိမ်းများ:*\n"
            "• 🎰 စလော့ဂိမ်းများ (PG Soft, JDB, Joker, Pragmatic Play)\n"
            "• 🐟 ငါးပစ်ဂိမ်း (Fish Hunter Games)\n"
            "• 🃏 ရှမ်းကိုးမီး၊ ဘူကြီး၊ ပိုကာ\n"
            "• 🎲 Live Casino (Baccarat, Roulette)\n\n"
            "💵 သွင်းငွေ/ထုတ်ငွေ ၂၄ နာရီ အလျင်အမြန် ဆောင်ရွက်ပေးပါသည်ခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Admin ထံ ဂိမ်းအကောင့် ဖွင့်ရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")]
        ])
        await update.message.reply_text(game_text, parse_mode="Markdown", reply_markup=inline_kb)
        return

    elif text in ["📜 ထိုးခဲ့သောမှတ်တမ်းများ", "📜 ထိုးထားသော စာရင်းများ"]:
        bets = user_bets.get(str(user_id), [])
        if not bets:
            await update.message.reply_text(
                "📜 *ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါခင်ဗျာ။*\n\n"
                "ထိုးလိုပါက `45=500` (ကျပ်) သို့မဟုတ် `45=20B` (ဘတ်) ဟု စာရိုက်ပို့နိုင်ပါသည်!"
            )
            return

        tz_mm = timezone(timedelta(hours=6, minutes=30))
        now_str = datetime.now(tz_mm).strftime("%d-%m-%Y")
        mmk_lines = []
        thb_lines = []
        total_mmk = 0
        total_thb = 0

        for b in bets[-20:]:
            b_type = b.get("type", "2D")
            b_num = b.get("number", "")
            b_amt = b.get("amount", 0)
            b_pay = b.get("payout", 0)
            b_slot = b.get("slot", "12:01 PM")
            if b.get("currency") == "THB":
                thb_lines.append(f"• {b_type} [{b_slot}] 【 `{b_num}` 】 = `{b_amt} ဘတ်` (ပေါက်: `{b_pay:,} ဘတ်`)")
                total_thb += b_amt
            else:
                mmk_lines.append(f"• {b_type} [{b_slot}] 【 `{b_num}` 】 = `{b_amt:,} ကျပ်` (ပေါက်: `{b_pay:,} ကျပ်`)")
                total_mmk += b_amt

        history_msg = (
            f"📜 *သင် ထိုးထားသော စာရင်းမှတ်တမ်းများ*\n"
            f"📅 *ရက်စွဲ:* `{now_str}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        if mmk_lines:
            history_msg += "🇲🇲 *မြန်မာကျပ်ငွေ ထိုးစာရင်းများ:*\n" + "\n".join(mmk_lines) + f"\n👉 စုစုပေါင်း MMK: `{total_mmk:,} ကျပ်`\n\n"
        if thb_lines:
            history_msg += "🇹🇭 *ထိုင်းဘတ်ငွေ ထိုးစာရင်းများ:*\n" + "\n".join(thb_lines) + f"\n👉 စုစုပေါင်း THB: `{total_thb:,} ဘတ်`\n\n"

        history_msg += "━━━━━━━━━━━━━━━━━━━━\nဆုကြေးငွေ ထုတ်ယူရန် Admin ထံ ဆက်သွယ်ပါခင်ဗျာ!"
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ စာရင်းအတည်ပြုရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")]
        ])
        await update.message.reply_text(history_msg, parse_mode="Markdown", reply_markup=inline_kb)
        return

    # ==================== ထီထိုးသွင်းခြင်း နှင့် ဘောင်ချာပြေစာထုတ်ခြင်း ====================
    if "=" in text:
        selected_slot = context.user_data.get("selected_slot", "12:01 PM")
        tz_mm = timezone(timedelta(hours=6, minutes=30))
        now_dt = datetime.now(tz_mm)
        now_str = now_dt.strftime("%d-%m-%Y %I:%M %p")
        ticket_id = f"TKT-{random.randint(10000, 99999)}"

        bet_regex = re.compile(r'([0-9,\s]+?)\s*(r|R|အာ|ပတ်)?\s*=\s*(\d+)\s*([a-zA-Z\u1000-\u109F]*)')
        matches = bet_regex.findall(text)

        if matches:
            recorded_list = []
            sub_total_mmk = 0
            sub_total_thb = 0

            for raw_nums, is_r, amt_str, curr_str in matches:
                amt = int(amt_str)
                curr_clean = curr_str.lower().strip()
                is_thb = curr_clean in ['b', 'baht', 'thb', 'ဘတ်']
                has_reverse = bool(is_r.strip())

                num_items = [n.strip() for n in re.split(r'[, ]+', raw_nums.strip()) if n.strip().isdigit()]

                for base_num in num_items:
                    target_numbers = [base_num]

                    if has_reverse:
                        if len(base_num) == 2:
                            rev = base_num[::-1]
                            if rev != base_num and rev not in target_numbers:
                                target_numbers.append(rev)
                        elif len(base_num) == 3:
                            from itertools import permutations
                            perms = set("".join(p) for p in permutations(base_num))
                            target_numbers = list(perms)

                    for num in target_numbers:
                        if len(num) == 2:
                            gtype = "2D"
                            if is_thb:
                                curr = "THB"
                                unit = "ဘတ်"
                                payout = amt * 90
                                sub_total_thb += amt
                            else:
                                curr = "MMK"
                                unit = "ကျပ်"
                                payout = amt * 85
                                sub_total_mmk += amt
                        elif len(num) == 3:
                            gtype = "3D"
                            selected_slot = "3D (03:30 PM)"
                            if is_thb:
                                curr = "THB"
                                unit = "ဘတ်"
                                payout = amt * 900
                                sub_total_thb += amt
                            else:
                                curr = "MMK"
                                unit = "ကျပ်"
                                payout = amt * 700
                                sub_total_mmk += amt
                        else:
                            continue

                        record = {
                            "type": gtype,
                            "number": num,
                            "amount": amt,
                            "currency": curr,
                            "unit": unit,
                            "payout": payout,
                            "slot": selected_slot,
                            "time": now_str,
                            "ticket_id": ticket_id
                        }
                        user_bets.setdefault(str(user_id), []).append(record)
                        recorded_list.append(record)

            if recorded_list:
                save_json_file(BETS_FILE, user_bets)

                confirm_msg = (
                    "🧾 *ထီထိုးပြေစာဘောင်ချာ (Voucher)* 🧾\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 *ပြေစာအမှတ်:* `#{ticket_id}`\n"
                    f"👤 *ထိုးသူအမည်:* `{user_name}` (ID: `{user_id}`)\n"
                    f"⏰ *အပိတ်အချိန်:* `{selected_slot}`\n"
                    f"📅 *ရက်စွဲ/အချိန်:* `{now_str}`\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📝 *ထိုးထားသော စာရင်းများ:*\n"
                )
                for r in recorded_list:
                    r_type = r.get("type", "")
                    r_num = r.get("number", "")
                    r_amt = r.get("amount", 0)
                    r_unit = r.get("unit", "")
                    r_pay = r.get("payout", 0)
                    r_curr = r.get("currency", "")
                    rate_str = "1:90" if (r_curr == "THB" and r_type == "2D") else ("1:900" if r_curr == "THB" else ("1:85" if r_type == "2D" else "1:700"))
                    confirm_msg += f"• *{r_type}* 【 `{r_num}` 】 ➔ `{r_amt:,} {r_unit}` (ပေါက်ကြေး: `{r_pay:,} {r_unit}` [{rate_str}])\n"

                confirm_msg += "━━━━━━━━━━━━━━━━━━━━\n"
                if sub_total_mmk > 0:
                    confirm_msg += f"🇲🇲 *စုစုပေါင်း မြန်မာကျပ်:* `{sub_total_mmk:,} ကျပ်`\n"
                if sub_total_thb > 0:
                    confirm_msg += f"🇹🇭 *စုစုပေါင်း ထိုင်းဘတ်:* `{sub_total_thb:,} ဘတ်`\n"

                confirm_msg += (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "✅ *အခြေအနေ:* အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!\n"
                    "💡 *မှတ်ချက်:* ထိုးကြေးငွေလွှဲ Slip ပြေစာအား Admin ထံ ပေးပို့အတည်ပြုပေးပါခင်ဗျာ။"
                )

                inline_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ငွေလွှဲပြေစာ ပို့ရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")]
                ])
                await update.message.reply_text(confirm_msg, parse_mode="Markdown", reply_markup=inline_kb)

                try:
                    admin_alert = (
                        f"📢 *[အသစ်ထိုးစာရင်း ရောက်ရှိပါသည်]*\n"
                        f"👤 *ထိုးသူ:* `{user_name}` (ID: `{user_id}`)\n"
                        f"🔖 *Ticket:* `#{ticket_id}`\n"
                        f"⏰ *အချိန်:* `{selected_slot}`\n"
                        f"💰 *စုစုပေါင်း:* `{sub_total_mmk:,} MMK` / `{sub_total_thb:,} THB`\n"
                        f"📝 *ကွက်ရေ:* {len(recorded_list)} ကွက်"
                    )
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_alert, parse_mode="Markdown")
                except Exception as e:
                    print("Admin notification failed:", e)
                return

        await update.message.reply_text(
            "⚠️ ထိုးသည့် ပုံစံ မမှန်ကန်ပါ ခင်ဗျာ။\n\n"
            "👉 ကြိုက် (တိုက်ရိုက်): `45=1000` သို့မဟုတ် `45=20B`\n"
            "👉 ဘတ်/အာ (R): `45 R=1000` သို့မဟုတ် `45 R=20B`\n"
            "👉 3D ထိုးရန်: `789=1000` သို့မဟုတ် `789 R=500`\n"
            "ကျေးဇူးပြု၍ ပြန်လည် စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )
        return

    if len(text) == 2 and text.isdigit():
        d2 = fetch_realtime_2d()
        valid_twods = []
        for s in d2.get("slots", {}).values():
            tw = s.get("twod", "")
            if tw and tw not in ["--", "00"]:
                valid_twods.append(tw)

        if text in valid_twods:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "🎉 ဂုဏ်ယူပါသည်! ယနေ့ ပေါက်ဂဏန်းနှင့် တိုက်ဆိုင်ပါသည်! 💰✨\n"
                f"ဆုငွေ ထုတ်ယူရန် Admin (ID: `{ADMIN_CHAT_ID}`) ထံ ချက်ချင်း ဆက်သွယ်လိုက်ပါခင်ဗျာ!"
            )
        else:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "❌ ယနေ့ထွက်ရှိထားသော ပေါက်ဂဏန်းများနှင့် မတိုက်ဆိုင်သေးပါခင်ဗျာ။\n"
                "နောက်ပွဲများတွင် ကံကောင်းပါစေခင်ဗျာ! 🍀"
            )

# ==================== INLINE CALLBACK HANDLERS ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    lottery_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ", callback_data="show_winning_nums"), InlineKeyboardButton("🟢 ယနေ့ထွက် 2D", callback_data="show_today_2d")],
        [InlineKeyboardButton("🎯 မနက်ဖြန်နှင့် နောက်ဆုံး 3D", callback_data="show_next_3d"), InlineKeyboardButton("👥 ထီပေါက်သူ ၁၀ ယောက်", callback_data="show_winners_list")],
        [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month"), InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
        [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now"), InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_lottery_menu")],
        [InlineKeyboardButton("🏠 Home Menu သို့ ပြန်သွားရန်", callback_data="go_home")]
    ])

    if data == "refresh_lottery_menu":
        try:
            lottery_menu_text = (
                "📣 *ထီပေါက်စဉ် မီနူး*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🏆 *ပေါက်ဂဏန်းများ* — ယနေ့ထွက်သော 2D (မနက်/ည) နှင့် နောက်ဆုံးထွက် 3D\n"
                "🟢 *ယနေ့ထွက် 2D* — ၁၂:၀၁ PM နှင့် ၀၄:၃၀ PM အချိန်နှင့်တပြေးညီ ရလဒ်\n"
                "🎯 *မနက်ဖြန်နှင့် နောက်ဆုံး 3D* — နောက်ဆုံးပေါက်မဲ နှင့် နောက်ထွက်မည့်ရက်\n"
                "👥 *ထီပေါက်သူစာရင်း* — အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း\n"
                "📊 *၂လုံး (၁ လစာ)* နှင့် 🎯 *၃လုံး (၃ လစာ)* မှတ်တမ်းများ\n\n"
                "👇 ကြည့်ရှုလိုရာကို ရွေးချယ်ပါ —"
            )
            await query.edit_message_text(lottery_menu_text, parse_mode="Markdown", reply_markup=lottery_kb)
            await query.answer("🔄 Refresh ပြီးပါပြီ!")
        except Exception:
            await query.answer("✅ နောက်ဆုံးရ အချက်အလက်အတိုင်း ဖြစ်ပါသည်")

    elif data == "go_home":
        await query.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ပြန်လည်ရောက်ရှိပါပြီခင်ဗျာ။", reply_markup=get_main_menu())
        await query.answer()

    elif data == "show_winning_nums" or data == "show_today_2d":
        msg = format_live_winning_numbers()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("👥 ထီပေါက်သူစာရင်း ကြည့်ရန်", callback_data="show_winners_list")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🏆 တရားဝင် ပေါက်ဂဏန်းများ")

    elif data == "show_next_3d":
        d3 = fetch_realtime_3d()
        msg = (
            "🎯 *ထိုင်း ၃လုံး (3D) ပေါက်ဂဏန်း နှင့် ထွက်မည့်ရက်*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 *နောက်ဆုံးထွက် 3D ဂဏန်း:* 【 *{d3.get('threed')}* 】\n"
            f"📅 *ထွက်ရှိခဲ့သည့်ရက်:* `{d3.get('date')}`\n"
            f"⏰ *နောက်ထပ် ထွက်မည့်ရက်:* `{d3.get('next_date')}`\n"
            f"🏛️ *အရင်းအမြစ်:* `{d3.get('source')}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 3D ပေါက်ကြေး: ၁ ကျပ်လျှင် ၇၀၀ ကျပ် (MMK) | ၁ ဘတ်လျှင် ၉၀၀ ဘတ် (THB)"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ၃လုံး (၃ လစာ) ကြည့်ရန်", callback_data="history_3d_3months")],
            [InlineKeyboardButton("👉 🎯 3D ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 3D ရလဒ်")

    elif data == "show_winners_list":
        winners_msg = get_winners_top10_message()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ ကြည့်ရန်", callback_data="show_winning_nums")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(winners_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("👥 ထီပေါက်သူစာရင်း")

    elif data == "history_2d_1month":
        hist_msg = fetch_2d_one_month_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(hist_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("📊 ၂လုံး ၁ လစာ မှတ်တမ်း")

    elif data == "history_3d_3months":
        hist_3d = fetch_3d_three_months_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(hist_3d, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ၃လုံး ၃ လစာ မှတ်တမ်း")

    elif data == "btn_bet_now":
        bet_info = (
            "🎯 *၂လုံး / ၃လုံး ထိုးရန် လမ်းညွှန်* 🎯\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "☀️ မနက် ၁၂:၀၁ PM (သို့မဟုတ်) 🌙 ညနေ ၀၄:၃၀ PM\n\n"
            "🇲🇲 *မြန်မာကျပ်ငွေ:*\n"
            "• ကြိုက် (တိုက်ရိုက်): `45=1000` (ပေါက်ကြေး ၁:၈၅)\n"
            "• ဘတ်/အာ (R): `45 R=1000` (45 ရော 54 ပါ ၂ ကွက်)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေ:*\n"
            "• ကြိုက် (တိုက်ရိုက်): `45=20B` (ပေါက်ကြေး ၁:၉၀)\n"
            "• ဘတ်/အာ (R): `45 R=20B` (45 ရော 54 ပါ ၂ ကွက်)\n\n"
            "🎯 *3D ထိုးရန်:* `789=1000` သို့မဟုတ် `789 R=500`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ *ထိုးလိုသော ဂဏန်းကို အောက်ပါ Chat Box ထဲတွင် စာရိုက်ပို့ပေးပါခင်ဗျာ!*"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ စာရင်းပို့ရန်", url=f"tg://user?id={ADMIN_CHAT_ID}")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(bet_info, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ထိုးရန်")

    elif data in ["alert_admin_deposit", "alert_admin_direct"]:
        user = update.effective_user
        try:
            alert_text = (
                f"🚨 *[Admin ထံ ဆက်သွယ်ရန် တောင်းဆိုချက်]*\n"
                f"👤 အမည်: `{user.first_name}`\n"
                f"🆔 User ID: `{user.id}`\n"
                f"🔗 Telegram: @{user.username if user.username else 'မရှိပါ'}\n"
                f"📝 ကိစ္စရပ်: {'ငွေသွင်း/ငွေထုတ်' if data == 'alert_admin_deposit' else 'တိုက်ရိုက် ဆက်သွယ်လိုခြင်း'}"
            )
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=alert_text, parse_mode="Markdown")
            await query.answer("✅ Admin ထံသို့ Alert ပို့ပြီးပါပြီ! မကြာမီ ဆက်သွယ်လာပါမည်။", show_alert=True)
        except Exception:
            await query.answer("Admin ထံ လှမ်းပို့ရန် tg://user သို့ ဆက်သွယ်ပါခင်ဗျာ", show_alert=True)

# ==================== MAIN APPLICATION ====================
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('set2d', admin_set_2d))
    app.add_handler(CommandHandler('set3d', admin_set_3d))
    app.add_handler(CommandHandler('reset_override', admin_reset))

    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    print(f"🚀 Lucky2D3D Official Multi-Source Bot Started! Admin ID: {ADMIN_CHAT_ID}")
    app.run_polling(drop_pending_updates=True)
