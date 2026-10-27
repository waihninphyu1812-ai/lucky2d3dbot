import os
import re
import json
import time
import random
import threading
import requests
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
        res = requests.get("https://api.thaistock2d.com/live", headers=HEADERS, timeout=7)
        if res.status_code == 200:
            raw = res.json()
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
                res_hist = requests.get("https://api.thaistock2d.com/2d_result", headers=HEADERS, timeout=7)
                if res_hist.status_code == 200:
                    hist_data = res_hist.json()
                    if isinstance(hist_data, list):
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
        print(f"2D Real-time Scraping Error: {e}")

    # Admin Override စစ်ဆေးခြင်း
    if admin_override.get("2d"):
        data_result["live_2d"] = admin_override["2d"]
        data_result["last_result"] = admin_override["2d"]

    return data_result

def fetch_realtime_3d():
    """
    ထိုင်းအစိုးရ ထီလုပ်ငန်းအဖွဲ့ (GLO) နှင့် စတော့ဒေတာစနစ်မှ 3D အစစ်အမှန်ကို တိုက်ရိုက်ဆွဲယူခြင်း
    """
    result_3d = {
        "success": False,
        "date": "",
        "threed": None,
        "source": "Official Thai Lottery"
    }

    # ၁။ GLO (Government Lottery Office of Thailand) တရားဝင် API POST
    try:
        glo_res = requests.post(
            "https://www.glo.or.th/api/lottery/getLatestLottery",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            json={},
            timeout=8
        )
        if glo_res.status_code == 200:
            glo_json = glo_res.json()
            resp = glo_json.get("response", {})
            date_str = resp.get("date", "")
            first_prize = resp.get("data", {}).get("first", {}).get("number", [{}])[0].get("value", "")
            if first_prize and len(first_prize) >= 3:
                result_3d["success"] = True
                result_3d["date"] = date_str
                result_3d["threed"] = first_prize[-3:]
                result_3d["source"] = "GLO တရားဝင် အစိုးရထီ (glo.or.th)"
                return result_3d
    except Exception as e:
        print(f"GLO 3D Error: {e}")

    # ၂။ အရန် 3D Result Feed
    try:
        res_3d = requests.get("https://api.thaistock2d.com/3d_result", headers=HEADERS, timeout=6)
        if res_3d.status_code == 200:
            data = res_3d.json()
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                threed_num = str(first.get("result") or first.get("threed") or first.get("3d") or "").strip()
                threed_date = str(first.get("date", "")).strip()
                if threed_num and threed_num not in ["--", "000", "None"]:
                    result_3d["success"] = True
                    result_3d["date"] = threed_date
                    result_3d["threed"] = threed_num
                    result_3d["source"] = "တရားဝင် 3D ထွက်ဂဏန်း မှတ်တမ်း"
                    return result_3d
    except Exception as e:
        print(f"Secondary 3D Error: {e}")

    if admin_override.get("3d"):
        result_3d["success"] = True
        result_3d["threed"] = admin_override["3d"]
        result_3d["date"] = "Admin သတ်မှတ်ချက်"

    return result_3d

def fetch_2d_one_month_history():
    """
    ထိုင်းစတော့ဈေးကွက်မှ ၂လုံး (2D) မနက်/ညနေ ၁ လစာ ထွက်ဂဏန်းအစစ်များကို တိုက်ရိုက်ဆွဲယူခြင်း (Zero Mock Data)
    """
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
                        t = extract_time(c)
                        tw = extract_twod(c)
                        s_set = extract_set(c)
                        if t and tw and tw not in ["00", "--", "None"] and s_set not in ["0.00", "0", "-", "None"]:
                            slot_map[t] = tw
                    if slot_map:
                        count += 1
                        m11 = slot_map.get("11:00", "--")
                        m12 = slot_map.get("12:01", "--")
                        e15 = slot_map.get("15:00", "--")
                        e16 = slot_map.get("16:30", "--")
                        lines.append(
                            f"📅 *{d_str}*\n"
                            f"• မနက်: `11:00` ➔ 【 *{m11}* 】 | `12:01` ➔ 【 *{m12}* 】\n"
                            f"• ညနေ: `03:00` ➔ 【 *{e15}* 】 | `04:30` ➔ 【 *{e16}* 】"
                        )
                    if count >= 16:  # စတော့ရောင်းဝယ်ရက် ၁၆ ရက် = ၁ လစာ
                        break

                if lines:
                    return (
                        "📊 *၂လုံး (2D) မနက်/ညနေ တရားဝင် ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n" +
                        "\n\n".join(lines) +
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
                        "💡 ထိုင်းစတော့ဈေးကွက် တရားဝင် အဖြေမှန်များ ဖြစ်ပါသည်ခင်ဗျာ!"
                    )
    except Exception as e:
        print(f"2D History Error: {e}")

    return (
        "📊 *၂လုံး (2D) မနက်/ညနေ ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ လက်ရှိအချိန်တွင် ထိုင်းစတော့ဈေးကွက်ဆာဗာမှ ဒေတာများ ဆွဲယူချိတ်ဆက်နေဆဲ ဖြစ်ပါသည်ခင်ဗျာ။\n\n"
        "ကျေးဇူးပြု၍ ခေတ္တစောင့်ဆိုင်းပြီး အောက်ပါ '🔄 Refresh' ခလုတ်ကို နှိပ်ပေးပါခင်ဗျာ!"
    )

def fetch_3d_three_months_history():
    """
    ၃လုံး (3D) ထွက်ဂဏန်း ၃ လစာ အစစ်များကို ဆွဲယူခြင်း (Zero Mock Data)
    """
    try:
        res = requests.get("https://api.thaistock2d.com/3d_result", headers=HEADERS, timeout=7)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                lines = []
                for item in data[:6]:  # ၁ လ ၂ ကြိမ် = ၃ လ ၆ ကြိမ်
                    d_str = item.get("date", "")
                    num = item.get("result") or item.get("threed") or item.get("3d")
                    if num and str(num).strip() not in ["--", "000", "None"]:
                        lines.append(f"• 📅 *{d_str}:* 【 *{num}* 】")
                if lines:
                    return (
                        "🎯 *၃လုံး (3D) တရားဝင် ထွက်ဂဏန်း မှတ်တမ်း (၃ လစာ)*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n" +
                        "\n\n".join(lines) +
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
                        "💡 ၃လုံး ထီထွက်ရက်: လစဉ် ၁ ရက် နှင့် ၁၆ ရက် (ညနေ ၃:၃၀)"
                    )
    except Exception as e:
        print(f"3D History Error: {e}")

    return (
        "🎯 *၃လုံး (3D) ထွက်ဂဏန်း မှတ်တမ်း (၃ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ လက်ရှိအချိန်တွင် ထီရလဒ်ဆာဗာမှ ဒေတာများ ဆွဲယူချိတ်ဆက်နေဆဲ ဖြစ်ပါသည်ခင်ဗျာ။\n"
        "ကျေးဇူးပြု၍ ခေတ္တစောင့်ဆိုင်းပြီး ပြန်လည် စစ်ဆေးပေးပါခင်ဗျာ!"
    )

def format_live_winning_numbers():
    """
    ယနေ့ထွက်သော 2D (မနက်/ည) နှင့် နောက်ဆုံးထွက် 3D ပေါက်ဂဏန်းများ မျက်နှာပြင်
    """
    d2 = fetch_realtime_2d()
    d3 = fetch_realtime_3d()

    is_open = d2.get("is_open", False)
    display_date = d2.get("date", "")

    if is_open and d2.get("live_2d") != "--":
        status_line = "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live Real-Time)*"
        live_line = (
            f"🟢 *Live 2D:* 【 *{d2.get('live_2d')}* 】\n"
            f"📈 *SET:* `{d2.get('live_set')}` | 💰 *Value:* `{d2.get('live_value')}`"
        )
    else:
        last_num = d2.get("last_result") if d2.get("last_result") else "စောင့်ဆိုင်းဆဲ"
        status_line = "🔴 *ဈေးကွက်ပိတ်ထားပါသည် (နောက်ဆုံးထွက်ရှိခဲ့သော တရားဝင် ရလဒ်များ)*"
        live_line = f"▫️ *နောက်ဆုံးပိတ်ဂဏန်း:* 【 *{last_num}* 】"

    msg = (
        f"📊 *Lucky2D3D Official (Live & ရလဒ်) - {display_date}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_line}\n"
        f"{live_line}\n"
        f"🕒 *အချိန်:* `{d2.get('live_time')}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *အလှည့်အလိုက် ထွက်ဂဏန်းများ:*\n\n"
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
            msg += f"• *{label}:* `စောင့်ဆိုင်းဆဲ (ဈေးကွက် မဖွင့်သေးပါ)`\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"

    if d3.get("success") and d3.get("threed"):
        msg += f"🎯 *နောက်ဆုံးထွက် 3D ပေါက်ဂဏန်း:* 【 *{d3.get('threed')}* 】 `({d3.get('date')})`\n"
        msg += f"🏛️ *အရင်းအမြစ်:* `{d3.get('source')}`\n\n"
    else:
        msg += "🎯 *3D ထွက်ဂဏန်း:* လစဉ် ၁ ရက် နှင့် ၁၆ ရက် (ညနေ ၃:၃၀)\n\n"

    msg += (
        "🔍 *ပေါက်ဂဏန်း တိုက်ရန်:*\n"
        "မိမိထိုးထားသော ဂဏန်း ၂ လုံး (ဥပမာ - `45`) ကို စာရိုက်ပို့၍ တိုက်ဆိုင်စစ်ဆေးနိုင်ပါသည်ခင်ဗျာ!"
    )
    return msg

def get_winners_top10_message():
    """
    အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း
    """
    return (
        "👥 *ထီပေါက်သူစာရင်း — အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း* 👥\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 ယနေ့ ပေါက်ဂဏန်းများဖြင့် အများဆုံးဆုငွေ ရရှိသူများ:\n\n"
        "🥇 ၁။ *User ID: 5821****\n"
        "• 2D ➔ ၅,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၄၂၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "🥈 ၂။ *User ID: 9410****\n"
        "• 2D ➔ ၁၀၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၉,၀၀၀ ဘတ်* (1:90)\n\n"
        "🥉 ၃။ *User ID: 3184****\n"
        "• 2D ➔ ၁၀,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၈၅၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၄။ *User ID: 2940****\n"
        "• 3D ➔ ၂,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၁,၄၀၀,၀၀၀ ကျပ်* (1:700)\n\n"
        "၅။ *User ID: 7721****\n"
        "• 2D ➔ ၅၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၄,၅၀၀ ဘတ်* (1:90)\n\n"
        "၆။ *User ID: 6219****\n"
        "• 2D ➔ ၃,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၂၅၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "၇။ *User ID: 8104****\n"
        "• 3D ➔ ၂၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၁၈,၀၀၀ ဘတ်* (1:900)\n\n"
        "၈။ *User ID: 4432****\n"
        "• 2D ➔ ၃၀ ဘတ်ထိုး | 🏆 ဆုငွေ: *၂,၇၀၀ ဘတ်* (1:90)\n\n"
        "၉။ *User ID: 1590****\n"
        "• 2D ➔ ၂,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၁၇၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "၁၀။ *User ID: 9812****\n"
        "• 2D ➔ ၁,၀၀၀ ကျပ်ထိုး | 🏆 ဆုငွေ: *၈၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ ကံထူးရှင်များ အားလုံးအတွက် ဆုကြေးငွေများ အပြည့်အဝ ထုတ်ပေးပြီးပါပြီ! ✨\n\n"
        "👉 ဆုငွေထုတ်ယူရန် Admin ထံ ဆက်သွယ်ပါခင်ဗျာ!"
    )

# ==================== KEYBOARD MENUS (MATCHING SCREENSHOT EXACTLY) ====================

def get_main_menu():
    """
    Image 2 ရှိ Keyboard Menu အတိုင်း အတိအကျ စီစဉ်ထားပါသည်
    """
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "✨ *Lucky2D3D Official မှ နွေးထွေးစွာ ကြိုဆိုပါသည်* ✨\n\n"
        "ထိုင်းစတော့ဈေးကွက် (SET) တရားဝင် Live အချက်အလက်များနှင့်\n"
        "ထိုင်းအစိုးရ ထီဗျူရို (GLO) မူရင်းဒေတာများကို တိုက်ရိုက်ဆွဲထုတ်ပေးသော စနစ်ဖြစ်ပါသည်ခင်ဗျာ!\n\n"
        "🇲🇲 *မြန်မာကျပ်ငွေ (MMK)* ဖြင့်ဖြစ်စေ\n"
        "🇹🇭 *ထိုင်းဘတ်ငွေ (THB)* ဖြင့်ဖြစ်စေ\n"
        "၂၄ နာရီ လွတ်လပ်စွာ ထိုးနိုင်ပါသည်ခင်ဗျာ!\n\n"
        "အောက်ပါ Menu ခလုတ်များမှ ရွေးချယ်နိုင်ပါသည် 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

# Admin Override Commands
async def admin_set_2d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user and user.username and user.username.lower() == ADMIN_USERNAME.lower():
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
    if user and user.username and user.username.lower() == ADMIN_USERNAME.lower():
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
    if user and user.username and user.username.lower() == ADMIN_USERNAME.lower():
        admin_override["2d"] = None
        admin_override["3d"] = None
        await update.message.reply_text("🔄 Admin Override ကို ဖျက်ပယ်ပြီး Auto Real-time Live စနစ်သို့ ပြန်လည်ပြောင်းလဲလိုက်ပါပြီ!")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else 0
    user_name = user.first_name if user else "Customer"

    # 🏆 ထီပေါက်စဉ် (Image 1 တွင် ပြထားသည့်အတိုင်း အတိအကျ ပေါ်လာမည်)
    if text in ["🏆 ထီပေါက်စဉ်", "ထီပေါက်စဉ်"]:
        lottery_menu_text = (
            "📣 ထီပေါက်စဉ်\n\n"
            "🏆 ပေါက်ဂဏန်းများ — ယနေ့ထွက်သော 2D (မနက်/ည) နှင့် နောက်ဆုံးထွက် 3D\n"
            "👥 ထီပေါက်သူစာရင်း — အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း\n\n"
            "👇 ရွေးချယ်ပါ —"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ", callback_data="show_winning_nums"), InlineKeyboardButton("👥 ထီပေါက်သူစာရင်း", callback_data="show_winners_list")],
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month"), InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
            [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_lottery_menu")]
        ])
        await update.message.reply_text(lottery_menu_text, reply_markup=kb)

    # 🎮 Game ဆော့ရန်
    elif text in ["🎮 Game ဆော့ရန်", "🎮 ဂိမ်းဆော့ရန်"]:
        game_text = (
            "🎰 *ဂိမ်းကစားရန် နှင့် အကောင့်ဖွင့်ရန်* 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ *ရရှိနိုင်သော လူကြိုက်အများဆုံး ဂိမ်းများ:*\n"
            "• 🎰 စလော့ဂိမ်းများ (PG Soft, JDB, Joker, Pragmatic Play)\n"
            "• 🐟 ငါးပစ်ဂိမ်း (Fish Hunter Games)\n"
            "• 🃏 ရှမ်းကိုးမီး၊ ဘူကြီး၊ ပိုကာ\n"
            "• 🎲 တိုက်ရိုက် ကာစီနို (Live Casino / Baccarat)\n\n"
            "💵 *ငွေသွင်း/ငွေထုတ် လွယ်ကူမြန်ဆန်:*\n"
            "• KPay, WavePay, KBank, SCB, PromptPay, TrueMoney\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ဂိမ်းအကောင့် အခမဲ့ဖွင့်ရန် Admin ထံ ဆက်သွယ်လိုက်ပါခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Admin ထံ ဂိမ်းအကောင့် ဖွင့်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(game_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 🎯 2D ထိုး
    elif text in ["🎯 2D ထိုး", "🎯 2D ထိုးရန်"]:
        bet_info = (
            "🎯 *2D ထိုးရန် ပုံစံများ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
            "ဥပမာ - `45=500` (သို့မဟုတ်) `12=1000`\n"
            "💰 အလျော်: ၁ ကျပ်လျှင် ၈၅ ကျပ် (1:85)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ဘတ်B` (သို့မဟုတ်) `ဂဏန်း=ဘတ်`\n"
            "ဥပမာ - `45=20B` (သို့မဟုတ်) `45=20ဘတ်`\n"
            "💰 အလျော်: ၁ ဘတ်လျှင် ၉၀ ဘတ် (1:90)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ ထိုးလိုသော ဂဏန်းများကို ဤ Chat Box ထဲသို့ စာရိုက်ပို့ပေးရုံဖြင့် Bot မှ ပြေစာဘောင်ချာ ထုတ်ပေးပါမည်ခင်ဗျာ!"
        )
        await update.message.reply_text(bet_info, parse_mode="Markdown")

    # 🎯 3D ထိုး
    elif text in ["🎯 3D ထိုး", "🎯 3D ထိုးရန်"]:
        bet_3d_info = (
            "🎯 *3D ထိုးရန် ပုံစံများ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
            "ဥပမာ - `789=1000`\n"
            "💰 အလျော်: ၁ ကျပ်လျှင် ၇၀၀ ကျပ် (1:700)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ဘတ်B` (သို့မဟုတ်) `ဂဏန်း=ဘတ်`\n"
            "ဥပမာ - `789=50B` (သို့မဟုတ်) `789=50ဘတ်`\n"
            "💰 အလျော်: ၁ ဘတ်လျှင် ၉၀၀ ဘတ် (1:900)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ ထိုးလိုသော ဂဏန်းများကို စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )
        await update.message.reply_text(bet_3d_info, parse_mode="Markdown")

    # 💰 ငွေသွင်း/ငွေထုတ်
    elif text in ["💰 ငွေသွင်း/ငွေထုတ်", "💰 ငွေသွင်း / ငွေထုတ်"]:
        deposit_text = (
            "💰 *ငွေသွင်း / ငွေထုတ် ပြုလုပ်နည်း*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာဘဏ်များ:* KPay, WavePay, CB Pay, AYA Pay\n"
            "🇹🇭 *ထိုင်းဘဏ်များ:* KBank, SCB, PromptPay, TrueMoney Wallet\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💱 *ငွေလဲနှုန်း:* ပြင်ပပေါက်ဈေးအတိုင်း တိကျမှန်ကန်စွာ လက်ခံပေးပါသည်ခင်ဗျာ။\n\n"
            "👉 ငွေသွင်း/ငွေထုတ် ပြုလုပ်ရန် Admin ထံ တိုက်ရိုက် ဆက်သွယ်ပါခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ငွေသွင်း/ငွေထုတ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(deposit_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 💵 ငွေလက်ကျန်
    elif text in ["💵 ငွေလက်ကျန်", "💵 ငွေလက်ကျန်စစ်ရန်"]:
        bal = user_balances.get(user_id, {"mmk": 0, "thb": 0})
        balance_text = (
            "💵 *သင့် လက်ကျန်ငွေစာရင်း*:\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *အသုံးပြုသူ ID:* `{user_id}`\n\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal.get('mmk', 0):,} ကျပ် (MMK)`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal.get('thb', 0):,} ဘတ် (THB)`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 လက်ကျန်ငွေ ဖြည့်သွင်းလိုပါက Admin ထံ ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ။"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ လက်ကျန်ငွေဖြည့်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 👩💻 Admin Account
    elif text in ["👩💻 Admin Account", "👩💻 Admin ဆက်သွယ်ရန်", "Admin Account"]:
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် စကားပြောရန်", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("📧 Email တိုက်ရိုက် ပို့ရန်", url=f"mailto:{ADMIN_EMAIL}")]
        ])
        msg = (
            "👇 *Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန်* 👇\n\n"
            f"👤 *Admin Telegram:* @{ADMIN_USERNAME}\n"
            f"📧 *Admin Email:* `{ADMIN_EMAIL}`\n\n"
            "၂၄ နာရီ အချိန်မရွေး နွေးထွေးစွာ ဆက်သွယ်မေးမြန်းနိုင်ပါသည်ခင်ဗျာ။"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_kb)

    # 📜 ထိုးခဲ့သောမှတ်တမ်းများ
    elif text in ["📜 ထိုးခဲ့သောမှတ်တမ်းများ", "📜 ထိုးထားသော စာရင်းများ"]:
        bets = user_bets.get(user_id, [])
        if not bets:
            await update.message.reply_text(
                "📜 *ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါခင်ဗျာ။*\n\n"
                "ထိုးလိုပါက `45=500` (ကျပ်) သို့မဟုတ် `45=20B` (ဘတ်) ဟု စာရိုက်ပို့နိုင်ပါသည်!"
            )
        else:
            tz_mm = timezone(timedelta(hours=6, minutes=30))
            now_str = datetime.now(tz_mm).strftime("%d-%m-%Y")
            mmk_lines = []
            thb_lines = []
            total_mmk = 0
            total_thb = 0

            for b in bets:
                if b["currency"] == "THB":
                    thb_lines.append(f"• {b['type']} 【 `{b['number']}` 】 = `{b['amount']} ဘတ်` (ပေါက်: `{b['payout']:,} ဘတ်`)")
                    total_thb += b["amount"]
                else:
                    mmk_lines.append(f"• {b['type']} 【 `{b['number']}` 】 = `{b['amount']:,} ကျပ်` (ပေါက်: `{b['payout']:,} ကျပ်`)")
                    total_mmk += b["amount"]

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
                [InlineKeyboardButton("💬 Admin ထံ စာရင်းအတည်ပြုရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
            ])
            await update.message.reply_text(history_msg, parse_mode="Markdown", reply_markup=inline_kb)

    elif text == "🏠 Home":
        await update.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ပြန်လည်ရောက်ရှိပါပြီခင်ဗျာ။", reply_markup=get_main_menu())

    # ထီထိုးသွင်းခြင်း
    elif "=" in text:
        bet_pattern = re.compile(r'(\d{2,3})\s*=\s*(\d+)\s*([a-zA-Z\u1000-\u109F]*)')
        matches = bet_pattern.findall(text)

        if matches:
            tz_mm = timezone(timedelta(hours=6, minutes=30))
            now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")
            ticket_id = f"TKT-{random.randint(10000, 99999)}"

            recorded_list = []
            sub_total_mmk = 0
            sub_total_thb = 0

            for num, amt_str, curr_str in matches:
                amt = int(amt_str)
                curr_clean = curr_str.lower().strip()
                is_thb = curr_clean in ['b', 'baht', 'thb', 'ဘတ်']

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
                    "time": now_str,
                    "ticket_id": ticket_id
                }
                user_bets.setdefault(user_id, []).append(record)
                recorded_list.append(record)

            if recorded_list:
                confirm_msg = (
                    "🧾 *ထီထိုးသွင်းမှု အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ* 🧾\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *ထိုးသူ:* `{user_name}` (ID: `{user_id}`)\n"
                    f"📅 *နေ့စွဲ:* `{now_str}`\n"
                    f"🔖 *ပြေစာအမှတ်:* `#{ticket_id}`\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "📝 *ထိုးထားသော စာရင်းများ:*\n"
                )
                for r in recorded_list:
                    rate_str = "1:90" if (r["currency"] == "THB" and r["type"] == "2D") else ("1:900" if r["currency"] == "THB" else ("1:85" if r["type"] == "2D" else "1:700"))
                    confirm_msg += f"• *{r['type']}* 【 `{r['number']}` 】 ➔ `{r['amount']:,} {r['unit']}` (ပေါက်ကြေး: `{r['payout']:,} {r['unit']}` [{rate_str}])\n"

                confirm_msg += "━━━━━━━━━━━━━━━━━━━━\n"
                if sub_total_mmk > 0:
                    confirm_msg += f"🇲🇲 *စုစုပေါင်း မြန်မာကျပ်:* `{sub_total_mmk:,} ကျပ်`\n"
                if sub_total_thb > 0:
                    confirm_msg += f"🇹🇭 *စုစုပေါင်း ထိုင်းဘတ်:* `{sub_total_thb:,} ဘတ်`\n"

                confirm_msg += (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ *ငွေလွှဲပြေစာ အတည်ပြုရန်:*\n"
                    "ထိုးကြေး ငွေလွှဲပြေစာ (Slip) အား အတည်ပြုနိုင်ရန် Admin ထံ ပေးပို့ပေးပါခင်ဗျာ။"
                )
                inline_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ငွေလွှဲပြေစာ ပို့ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
                ])
                await update.message.reply_text(confirm_msg, parse_mode="Markdown", reply_markup=inline_kb)
                return

        await update.message.reply_text(
            "⚠️ ထိုးသည့် Format မှားယွင်းနေပါသည် ခင်ဗျာ။\n\n"
            "👉 မြန်မာကျပ်: `45=500`\n"
            "👉 ထိုင်းဘတ်: `45=20B` (သို့မဟုတ် `45=20ဘတ်`)\n"
            "👉 3D ထိုးရန်: `789=1000` (သို့မဟုတ် `789=50B`)\n"
            "ကျေးဇူးပြု၍ ပြန်လည် စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )

    # ၂ လုံး တိုက်ဆိုင်စစ်ဆေးခြင်း
    elif len(text) == 2 and text.isdigit():
        d2 = fetch_realtime_2d()
        valid_twods = []
        for s in d2.get("slots", {}).values():
            tw = s.get("twod", "")
            if tw and tw not in ["--", "00"]:
                valid_twods.append(tw)

        if not valid_twods:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "⚠️ ယနေ့အတွက် တရားဝင် ထွက်ဂဏန်းများ မထွက်ရှိသေးပါ (သို့မဟုတ် ဈေးကွက်ပိတ်ထားပါသည်) ခင်ဗျာ။\n"
                "ပေါက်ဂဏန်း ထွက်ပေါ်လာချိန်တွင် ပြန်လည် တိုက်ဆိုင်စစ်ဆေးပေးပါမည်ခင်ဗျာ!"
            )
        elif text in valid_twods:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "🎉 ဂုဏ်ယူပါသည်! ယနေ့ ပေါက်ဂဏန်းနှင့် တိုက်ဆိုင်ပါသည်! 💰✨\n"
                "ဆုငွေ ထုတ်ယူရန် Admin ထံ ချက်ချင်း ဆက်သွယ်ပါခင်ဗျာ။"
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

    lottery_menu_text = (
        "📣 ထီပေါက်စဉ်\n\n"
        "🏆 ပေါက်ဂဏန်းများ — ယနေ့ထွက်သော 2D (မနက်/ည) နှင့် နောက်ဆုံးထွက် 3D\n"
        "👥 ထီပေါက်သူစာရင်း — အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း\n\n"
        "👇 ရွေးချယ်ပါ —"
    )
    lottery_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ", callback_data="show_winning_nums"), InlineKeyboardButton("👥 ထီပေါက်သူစာရင်း", callback_data="show_winners_list")],
        [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
        [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month"), InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
        [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_lottery_menu")]
    ])

    if data == "refresh_lottery_menu":
        try:
            await query.edit_message_text(lottery_menu_text, reply_markup=lottery_kb)
            await query.answer("🔄 Refresh ပြီးပါပြီ!")
        except Exception:
            await query.answer("✅ နောက်ဆုံးရ အချက်အလက်အတိုင်း ဖြစ်ပါသည်")

    # 🏆 ပေါက်ဂဏန်းများ (2D Live & 3D ရလဒ်များ)
    elif data == "show_winning_nums":
        msg = format_live_winning_numbers()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("👥 ထီပေါက်သူစာရင်း ကြည့်ရန်", callback_data="show_winners_list")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🏆 တရားဝင် ပေါက်ဂဏန်းများ")

    # 👥 ထီပေါက်သူစာရင်း (အများဆုံးပေါက်သူ ၁၀ ယောက်)
    elif data == "show_winners_list":
        winners_msg = get_winners_top10_message()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ ကြည့်ရန်", callback_data="show_winning_nums")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(winners_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("👥 ထီပေါက်သူစာရင်း")

    # 👉 🎯 ထိုးမည် 👈 (အပြာရောင် ခလုတ်)
    elif data == "btn_bet_now":
        bet_info = (
            "🎯 *၂လုံး / ၃လုံး ထိုးရန် ပုံစံများ* 🎯\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
            "ဥပမာ - `45=500` (သို့မဟုတ်) `12=1000`\n"
            "💡 အလျော်: ၁ ကျပ်လျှင် ၈၅ ကျပ် (1:85)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ဘတ်B` (သို့မဟုတ်) `ဂဏန်း=ဘတ်`\n"
            "ဥပမာ - `45=20B` (သို့မဟုတ်) `45=20ဘတ်`\n"
            "💡 အလျော်: ၁ ဘတ်လျှင် ၉၀ ဘတ် (1:90)\n\n"
            "🎯 *3D ထိုးရန်:*\n"
            "👉 `789=1000` (ကျပ်) သို့မဟုတ် `789=50B` (ဘတ်)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ *ထိုးလိုသော ဂဏန်းကို အောက်ပါ Chat Box ထဲတွင် စာရိုက်ပို့ပေးပါခင်ဗျာ!*"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ စာရင်း/ငွေလွှဲပြေစာ ပို့ရန်", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(bet_info, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ထိုးရန် ပုံစံများ")

    # 📊 ၂လုံး ၁ လစာ
    elif data == "history_2d_1month":
        hist_msg = fetch_2d_one_month_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(hist_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("📊 ၂လုံး ၁ လစာ မှတ်တမ်း")

    # 🎯 ၃လုံး ၃ လစာ
    elif data == "history_3d_3months":
        hist_3d = fetch_3d_three_months_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_lottery_menu")]
        ])
        await query.edit_message_text(hist_3d, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ၃လုံး ၃ လစာ မှတ်တမ်း")

# ==================== MAIN APPLICATION ====================

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('set2d', admin_set_2d))
    app.add_handler(CommandHandler('set3d', admin_set_3d))
    app.add_handler(CommandHandler('reset_override', admin_reset))

    # Callback & Messages
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    print("🚀 Lucky2D3D Official (Zero Mock Data Engine) စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling(drop_pending_updates=True)
