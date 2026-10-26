import os
import re
import random
import threading
import requests
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== RENDER WEB SERVER (PORT 10000) ====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Myanmar & Thai 2D/3D Telegram Bot Running Live 24/7!".encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

# ==================== BOT CONFIG & ADMIN ====================
TOKEN = '8988776248:AAFj84YUTvHfWXjH-Mc4fPgbkx-MjR6ytG8'
ADMIN_USERNAME = "snow78"
ADMIN_EMAIL = "waihninphyu1812@gmail.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

# User bets and balances stored in memory
user_bets = {}
user_balances = {}

# ==================== 2D & 3D LIVE / DATA FETCHING ====================

def fetch_2d_data():
    """2D Live အချက်အလက်များ (ပိတ်ရက်ဖြစ်ပါက နောက်ဆုံးဖွင့်ရက်၏ ရလဒ်အစစ်များကို ရယူသည်)"""
    try:
        res = requests.get("https://api.thaistock2d.com/live", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            live = data.get("live", {})
            results = data.get("result", [])

            is_zero_live = live.get("set") in ["0.00", "0", "-", None]
            has_no_valid = not any(
                r.get("set") not in ["0.00", "0", "-", None] and r.get("twod") not in ["00", "--", None]
                for r in results
            )

            if is_zero_live or has_no_valid:
                res_prev = requests.get("https://api.thaistock2d.com/2d_result", headers=HEADERS, timeout=8)
                if res_prev.status_code == 200:
                    prev_data = res_prev.json()
                    if isinstance(prev_data, list):
                        for day in prev_data:
                            children = day.get("child", [])
                            if any(c.get("set") not in ["0.00", "0", "-", None] and c.get("twod") not in ["00", "--", None] for c in children):
                                return {
                                    "live": live,
                                    "result": children,
                                    "history_date": day.get("date"),
                                    "is_closed": True
                                }
            return data
    except Exception as e:
        print(f"2D Fetch error: {e}")
    return None

def fetch_3d_data():
    """3D နောက်ဆုံးထွက်ဂဏန်း အချက်အလက်များ ရယူခြင်း"""
    try:
        res = requests.get("https://api.thaistock2d.com/3d_result", headers=HEADERS, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
    except Exception as e:
        print(f"3D Fetch error: {e}")
    return None

def format_today_2d_message():
    """ယနေ့ထွက်ဂဏန်း မျက်နှာပြင်"""
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    date_str = now.strftime("%d-%m-%Y")

    data = fetch_2d_data()
    live = data.get("live", {}) if data else {}
    results = data.get("result", []) if data else []
    history_date = data.get("history_date") if data else None
    force_closed = data.get("is_closed", False) if data else False

    set_val = live.get("set", "0.00")
    val_val = live.get("value", "0.00")
    twod_val = live.get("twod", "--")
    time_val = live.get("time", now.strftime("%Y-%m-%d %H:%M:%S"))

    is_closed = force_closed or (set_val in ["0.00", "0", "-", None])

    time_slots = {
        "11:00": "မနက် ၁၁:၀၀ (11:00 AM)",
        "12:01": "နေ့လယ် ၁၂:၀၁ (12:01 PM)",
        "15:00": "ညနေ ၀၃:၀၀ (03:00 PM)",
        "16:30": "ညနေ ၀၄:၃၀ (04:30 PM)"
    }

    found = {}
    if results:
        for r in results:
            ot = (r.get("open_time") or r.get("time") or "")[:5]
            if ot:
                found[ot] = r

    last_winning_num = None
    for slot in ["16:30", "15:00", "12:01", "11:00"]:
        r = found.get(slot)
        if r and r.get("set") not in ["0.00", "0", "-", None]:
            tw = str(r.get("twod", "")).strip()
            if tw and tw not in ["00", "--", "-", "None"]:
                last_winning_num = tw
                break

    if is_closed:
        display_date = history_date if history_date else date_str
        closing_num = last_winning_num if last_winning_num else (twod_val if twod_val not in ["00", "0", "--", ""] else "စောင့်ဆိုင်းဆဲ")
        status_line = "🔴 *ဈေးကွက်ပိတ်ထားပါသည် (နောက်ဆုံးထွက်ရှိခဲ့သော တရားဝင် ရလဒ်များ)*"
        live_line = f"▫️ *နောက်ဆုံးပိတ်ဂဏန်း:* 【 *{closing_num}* 】"
    else:
        display_date = date_str
        status_line = "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live)*"
        live_line = f"🟢 *Live 2D:* 【 *{twod_val}* 】\n📈 *SET:* `{set_val}` | 💰 *Value:* `{val_val}`"

    msg = (
        f"📊 *မြန်မာ ၂လုံး (2D Live) - {display_date}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_line}\n"
        f"{live_line}\n"
        f"🕒 *အချိန်:* `{time_val}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *ယနေ့ အလှည့်အလိုက် ထွက်ဂဏန်းများ:*\n\n"
    )

    for slot, label in time_slots.items():
        r = found.get(slot)
        if r and r.get("set") not in ["0.00", "0", "-", None]:
            r_twod = r.get("twod", "--")
            r_set = r.get("set", "-")
            msg += f"• *{label}:* 【 *{r_twod}* 】 `(SET: {r_set})`\n"
        else:
            msg += f"• *{label}:* `မထွက်ရှိသေးပါ (စောင့်ဆိုင်းဆဲ)`\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"

    d3 = fetch_3d_data()
    threed_val = None
    threed_date = ""
    if d3:
        threed_val = d3.get("result") or d3.get("threed") or d3.get("3d")
        threed_date = d3.get("date", "")

    if threed_val and str(threed_val).strip() not in ["", "--", "000", "0", "None"]:
        msg += f"🎯 *နောက်ဆုံးထွက် 3D ပေါက်ဂဏန်း:* 【 *{threed_val}* 】 `({threed_date})`\n\n"
    else:
        msg += "🎯 *3D ထွက်ဂဏန်း:* လစဉ် ၁ ရက် နှင့် ၁၆ ရက် (ညနေ ၃:၃၀)\n\n"

    msg += (
        "🔍 *ပေါက်ဂဏန်း တိုက်ရန်:*\n"
        "မိမိထိုးထားသော ဂဏန်း ၂ လုံး (ဥပမာ - `45`) ကို စာရိုက်ပို့၍ တိုက်ဆိုင်စစ်ဆေးနိုင်ပါသည်ခင်ဗျာ!"
    )
    return msg

# ==================== ထီပေါက်စဉ် မှတ်တမ်းများ (၁ လစာ & ၃ လစာ) ====================

def get_2d_one_month_history():
    """၂လုံး မနက်/ညနေ ထွက်ဂဏန်းများ (၁ လစာ)"""
    try:
        res = requests.get("https://api.thaistock2d.com/2d_result", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                lines = []
                count = 0
                for day in data:
                    d_str = day.get("date", "")
                    children = day.get("child", [])
                    slot_map = {}
                    for c in children:
                        t = (c.get("open_time") or c.get("time") or "")[:5]
                        tw = c.get("twod")
                        if t and tw and tw not in ["00", "--", None] and c.get("set") not in ["0.00", "0", "-", None]:
                            slot_map[t] = tw
                    if slot_map:
                        count += 1
                        m11 = slot_map.get("11:00", "--")
                        m12 = slot_map.get("12:01", "--")
                        e15 = slot_map.get("15:00", "--")
                        e16 = slot_map.get("16:30", "--")
                        lines.append(f"📅 *{d_str}*\n• မနက်: `11:00` ➔ 【 *{m11}* 】 | `12:01` ➔ 【 *{m12}* 】\n• ညနေ: `03:00` ➔ 【 *{e15}* 】 | `04:30` ➔ 【 *{e16}* 】")
                    if count >= 16:  # စတော့ရောင်းဝယ်ရက် ၁၆ ရက် = အကြမ်းဖျင်း ၁ လစာ
                        break
                if lines:
                    return (
                        "📊 *၂လုံး (2D) မနက်/ညနေ ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(lines) +
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
                        "💡 နေ့စဉ် ပေါက်ဂဏန်း အဖြေမှန်များ ဖြစ်ပါသည်ခင်ဗျာ!"
                    )
    except Exception as e:
        print(f"2D History
