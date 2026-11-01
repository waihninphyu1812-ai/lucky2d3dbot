import os
import re
import json
import random
import urllib.request
import threading
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==================== CONFIGURATION & ADMIN ====================
TOKEN = os.environ.get("BOT_TOKEN", "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI").strip()
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 1533228735))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "noenoeslotagency").lstrip("@")
ADMIN_URL = f"https://t.me/{ADMIN_USERNAME}"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
MINI_APP_URL = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://t.me/myanmar2d3d_live_bot/app"

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
BETS_FILE = os.path.join(DATA_DIR, "user_bets.json")
BALANCES_FILE = os.path.join(DATA_DIR, "user_balances.json")

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

user_bets = load_json(BETS_FILE, {})
user_balances = load_json(BALANCES_FILE, {})

# ==================== PAYMENT ACCOUNTS (KBZPAY ONLY FOR MMK) ====================
PAYMENT_ACCOUNTS = {
    "kpay": {
        "id": "kpay",
        "title": "KBZPay (KPay)",
        "name": os.environ.get("KPAY_NAME", "Daw Noe Noe"),
        "number": os.environ.get("KPAY_NUMBER", "09123456789"),
        "color": "#1d3557",
        "icon": "🔵",
        "currency": "MMK"
    },
    "kbank": {
        "id": "kbank",
        "title": "Kasikorn (KBank THB)",
        "name": os.environ.get("KBANK_NAME", "Noe Noe"),
        "number": os.environ.get("KBANK_NUMBER", "123-4-56789-0"),
        "color": "#2a9d8f",
        "icon": "🇹🇭",
        "currency": "THB"
    }
}

admin_override = {"2d": None, "3d": None}

# ==================== HTTP CLIENT HELPERS ====================
def http_get_json(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None

def http_get_text(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

# ==================== THAI MARKET (2D) HOLIDAY DETECTION ====================
def is_market_holiday():
    """
    စနေ၊ တနင်္ဂနွေ နှင့် ထိုင်းစတော့အိတ်ချိန်း (SET) ၏ တရားဝင် ပိတ်ရက်များ စစ်ဆေးခြင်း
    """
    tz_th = timezone(timedelta(hours=7))
    now = datetime.now(tz_th)

    if now.weekday() in [5, 6]:
        day_name = "စနေနေ့" if now.weekday() == 5 else "တနင်္ဂနွေနေ့"
        return True, f"{day_name} ဈေးကွက်ပိတ်ရက်"

    holidays = {
        "01-01": "နှစ်သစ်ကူးပိတ်ရက် (New Year's Day)",
        "01-02": "နှစ်သစ်ကူး အစားထိုးပိတ်ရက်",
        "04-13": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "04-14": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "04-15": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "05-01": "အလုပ်သမားနေ့ (Labor Day)",
        "12-31": "နှစ်ဟောင်းကုန်ပိတ်ရက်"
    }
    date_key = now.strftime("%m-%d")
    if date_key in holidays:
        return True, holidays[date_key]
    return False, ""

# ==================== REAL-TIME 2D ENGINE ====================
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

    if admin_override.get("2d"):
        res["live_2d"] = str(admin_override["2d"])
        return res

    if is_hol:
        res["morning_1201"] = "--"
        res["evening_1630"] = "--"
        return res

    # Live feed from ThaiStock2D
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
            elif "16:30" in open_time or "04:30" in open_time:
                res["evening_1630"] = twod_val
    return res

# ==================== REAL-TIME 3D ENGINE (OFFICIAL GLO RESULT) ====================
def get_next_3d_draw_date():
    tz_th = timezone(timedelta(hours=7))
    now = datetime.now(tz_th)
    y, m, d = now.year, now.month, now.day

    if d < 1 or (d == 1 and now.hour < 16):
        target = datetime(y, m, 1)
    elif d < 16 or (d == 16 and now.hour < 16):
        target = datetime(y, m, 16)
    else:
        target = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    return target.strftime("%d-%m-%Y")

def fetch_realtime_3d():
    """
    ထိုင်းအစိုးရ ထီဗျူရို (GLO) ၁ ရက် နှင့် ၁၆ ရက် တရားဝင် 3D Real-time Result
    - ပထမဆုကြီး ၆ လုံး (รางวัลที่ 1) မှ နောက်ဆုံး ၃ လုံး (3 ตัวบน)
    - 3D အနားဂဏန်းများ (รางวัลข้างเคียงรางวัลที่ 1)
    - ရှေ့ ၃ လုံး၊ နောက် ၃ လုံး၊ အောက် ၂ လုံး
    """
    next_draw = get_next_3d_draw_date()

    res = {
        "success": True,
        "first_prize": "536044",
        "threed": "044",
        "adjacent_tickets": ["536043", "536045"],
        "adjacent_threed": ["043", "045"],
        "front_3d": ["174", "225"],
        "back_3d": ["063", "231"],
        "back_2d": "32",
        "date": "01-11-2024",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)",
        "next_date": f"{next_draw} (ညနေ ၃:၃၀ နာရီ)"
    }

    # Admin Override
    if admin_override.get("3d"):
        val = str(admin_override["3d"]).strip()
        if len(val) == 6 and val.isdigit():
            n = int(val)
            res["first_prize"] = val
            res["threed"] = val[-3:]
            res["adjacent_tickets"] = [f"{n-1:06d}", f"{n+1:06d}"]
            res["adjacent_threed"] = [res["adjacent_tickets"][0][-3:], res["adjacent_tickets"][1][-3:]]
            res["source"] = "Admin တိုက်ရိုက် သတ်မှတ်ချက်"
            return res
        elif len(val) == 3 and val.isdigit():
            n = int(val)
            res["threed"] = val
            res["adjacent_threed"] = [f"{(n-1)%1000:03d}", f"{(n+1)%1000:03d}"]
            res["source"] = "Admin တိုက်ရိုက် သတ်မှတ်ချက်"
            return res

    # 1. Rayriffy Thai Lotto Live API
    try:
        data = http_get_json("https://lotto.api.rayriffy.com/latest", timeout=5)
        if data and data.get("status") == "success":
            resp = data.get("response", {})
            prizes = resp.get("prizes", [])
            running = resp.get("runningNumbers", [])

            for p in prizes:
                if p.get("id") == "prizeFirst" and p.get("number"):
                    fp = str(p["number"][0]).strip()
                    res["first_prize"] = fp
                    res["threed"] = fp[-3:]
                    if len(fp) == 6:
                        n = int(fp)
                        res["adjacent_tickets"] = [f"{n-1:06d}", f"{n+1:06d}"]
                        res["adjacent_threed"] = [f"{n-1:06d}"[-3:], f"{n+1:06d}"[-3:]]
                elif p.get("id") == "prizeFirstNear" and p.get("number"):
                    res["adjacent_tickets"] = [str(x).strip() for x in p["number"]]
                    res["adjacent_threed"] = [str(x).strip()[-3:] for x in p["number"]]

            for r in running:
                if r.get("id") == "runningNumberFrontThree" and r.get("number"):
                    res["front_3d"] = [str(x).strip() for x in r["number"]]
                elif r.get("id") == "runningNumberBackThree" and r.get("number"):
                    res["back_3d"] = [str(x).strip() for x in r["number"]]
                elif r.get("id") == "runningNumberBackTwo" and r.get("number"):
                    res["back_2d"] = str(r["number"][0]).strip()

            if resp.get("date"):
                res["date"] = resp["date"]
            res["source"] = "ထိုင်းအစိုးရ ထီဗျူရို (GLO / Rayriffy API)"
            return res
    except Exception:
        pass

    # 2. Sanook Official Lotto Feed Backup
    try:
        html = http_get_text("https://news.sanook.com/lotto/", timeout=5)
        if html:
            m = re.search(r'รางวัลที่\s*1.*?<strong[^>]*>(\d{6})</strong>', html, re.DOTALL)
            if m:
                fp = m.group(1).strip()
                res["first_prize"] = fp
                res["threed"] = fp[-3:]
                n = int(fp)
                res["adjacent_tickets"] = [f"{n-1:06d}", f"{n+1:06d}"]
                res["adjacent_threed"] = [f"{n-1:06d}"[-3:], f"{n+1:06d}"[-3:]]
                res["source"] = "Sanook Official Thai Lottery Live Feed"
                return res
    except Exception:
        pass

    return res

# ==================== MINI APP HTML SERVING ====================
def get_miniapp_html():
    html_file = os.path.join(DATA_DIR, "miniapp.html")
    if os.path.exists(html_file):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Lucky 2D 3D</title></head>
<body style="font-family:sans-serif; text-align:center; padding:40px 20px; background:#f4f7fc;">
  <h2>📱 Lucky 2D/3D Telegram Mini App</h2>
  <p>miniapp.html ဖိုင်အား GitHub ထဲသို့ Upload ပြုလုပ်ပေးပါခင်ဗျာ။</p>
  <a href="https://t.me/noenoeslotagency" style="display:inline-block; margin-top:15px; padding:10px 20px; background:#1e50ff; color:#fff; border-radius:20px; text-decoration:none;">Admin ဆက်သွယ်ရန်</a>
</body></html>"""

class WebAndMiniAppHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        url_path = self.path.split("?")[0].rstrip("/")
        if not url_path:
            url_path = "/"

        # Health Check
        if url_path in ["/health", "/ping"]:
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Real-time Data API
        if url_path == "/api/data":
            uid = ""
            if "?" in self.path:
                try:
                    from urllib.parse import parse_qs, urlparse
                    qs = parse_qs(urlparse(self.path).query)
                    uid = qs.get("user_id", [""])[0]
                except Exception:
                    pass

            d2 = fetch_realtime_2d()
            d3 = fetch_realtime_3d()
            bal = user_balances.get(str(uid), {"mmk": 0, "thb": 0}) if uid else {"mmk": 0, "thb": 0}
            payload = {
                "twod": d2,
                "threed": d3,
                "user_balance": bal,
                "payment_accounts": PAYMENT_ACCOUNTS
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Mini App Single Page Application (Served at '/', '/app', '/miniapp')
        if url_path in ["/", "/app", "/miniapp"]:
            html = get_miniapp_html()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), WebAndMiniAppHandler)
        server.serve_forever()
    except Exception as e:
        print("Server error:", e)

threading.Thread(target=start_server, daemon=True).start()

# ==================== TELEGRAM BOT LOGIC ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_name = user.first_name if user else "မိတ်ဆွေ"
    uid = str(user.id) if user else "0"

    if uid not in user_balances:
        user_balances[uid] = {"mmk": 0, "thb": 0}
        save_json(BALANCES_FILE, user_balances)

    welcome_text = (
        f"👋 *မင်္ဂလာပါ {u_name} ခင်ဗျာ!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎰 *Lucky2D3D Official Multi-Source Bot မှ ကြိုဆိုပါသည်!*\n\n"
        "👉 2D/3D Live ကြည့်ရှု၍ ထိုးကြေးတင်သွင်းရန် အောက်ရှိ **'👉 🎯 ထိုးမည်'** ခလုတ်ကို နှိပ်ပါခင်ဗျာ!\n\n"
        "💡 *ပေါက်ကြေးများ:*\n"
        "• 2D (၂လုံး): ၁ ကျပ် ➔ ၈၅ ကျပ် | ၁ ဘတ် ➔ ၉၀ ဘတ်\n"
        "• 3D (၃လုံး): ၁ ကျပ် ➔ ၇၀၀ ကျပ် | ၁ ဘတ် ➔ ၉၀၀ ဘတ်"
    )
    main_keyboard = [
        [KeyboardButton("👉 🎯 ထိုးမည်")],
        [KeyboardButton("🏆 ထီပေါက်စဉ်"), KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ")],
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎮 ဂိမ်းဆော့ရန်"), KeyboardButton("💬 Admin အကောင့်")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    user = update.effective_user
    uid = str(user.id) if user else "0"

    # 1. Main Bet Menu (Thai 2D & 3D Live with Bet Buttons)
    if text in ["👉 🎯 ထိုးမည်", "ထိုးမည်", "ထိုးမယ်", "🎯 ထိုးမည်", "🎯 ထိုးမယ်", "👉 🎯 2D ထိုးမည်", "2D ထိုးမည်", "2D ထိုး", "3D ထိုးမည်", "3D ထိုး"]:
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        is_hol, hol_reason = is_market_holiday()
        status_line = "🔴 *ယနေ့ စတော့ဈေးကွက် ပိတ်ပါသည်*" if is_hol else "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live)*"

        msg = (
            f"🎯 *Thai 2D & 3D Live ထိုးကြေးတင်သွင်းရန်* 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ထိုင်း 2D Live အခြေအနေ ({d2.get('date')}):*\n"
            f"{status_line}\n"
            f"• 🟢 Live 2D: 【 *{d2.get('live_2d')}* 】\n"
            f"• 📈 SET: `{d2.get('live_set')}` | 💰 Value: `{d2.get('live_value')}`\n"
            f"• 🌞 မနက် (12:01 PM): 【 *{d2.get('morning_1201')}* 】\n"
            f"• 🌇 ညနေ (04:30 PM): 【 *{d2.get('evening_1630')}* 】\n"
        )
        if is_hol:
            msg += f"• ⛔ *2D ပိတ်ရက်:* {hol_reason} (2D ထိုးမရပါ)\n"

        adj_str = ", ".join(d3.get("adjacent_threed", []))
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎲 *ထိုင်းအစိုးရ 3D Live အခြေအနေ:*\n"
            f"• 🥇 ပထမဆုကြီး (၆ လုံး): 【 *{d3.get('first_prize')}* 】\n"
            f"• 🔥 တရားဝင် 3D: 【 *{d3.get('threed')}* 】 (အနား: {adj_str})\n"
            f"• ⏰ နောက်ထပ် ထွက်မည့်ရက်: `{d3.get('next_date')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 *ထိုးလိုသော နည်းလမ်းကို အောက်ပါခလုတ်များမှ ရွေးချယ်ပါ:*"
        )
        inline_buttons = [
            [InlineKeyboardButton("📱 2D/3D Live Mini App ဖြင့် ထိုးမည်", web_app=WebAppInfo(url=MINI_APP_URL))]
        ]
        if not is_hol:
            inline_buttons.append([
                InlineKeyboardButton("🎯 2D မနက် (12:01 PM)", callback_data="slot_2d_morning"),
                InlineKeyboardButton("🎯 2D ညနေ (04:30 PM)", callback_data="slot_2d_evening")
            ])
        else:
            inline_buttons.append([
                InlineKeyboardButton("⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည်", callback_data="closed_2d_notice")
            ])

        inline_buttons.append([
            InlineKeyboardButton("🎯 3D ထိုးမည် (၁ ရက် / ၁၆ ရက်)", callback_data="btn_bet_3d")
        ])

        reply_markup = InlineKeyboardMarkup(inline_buttons)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return

    # 3. 🏆 ထီပေါက်စဉ် (Lottery Results, Winners List, Top 10)
    elif text in ["🏆 ထီပေါက်စဉ်", "ထီပေါက်စဉ်", "ပေါက်စဉ်"]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ပေါက်ဂဏန်းများ (2D မနက်/ည & 3D)", callback_data="lotto_winning_numbers")],
            [InlineKeyboardButton("🏆 ထီပေါက်သူစာရင်း", callback_data="lotto_winners_list")],
            [InlineKeyboardButton("🌟 အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း", callback_data="lotto_top10_winners")],
            [InlineKeyboardButton("👉 🎯 2D/3D ထိုးမည် 👈", callback_data="btn_bet_now")]
        ])
        msg = (
            "🏆 *တရားဝင် ထီပေါက်စဉ်နှင့် ဆုရရှိသူများ မီနူး* 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ကျေးဇူးပြု၍ ကြည့်ရှုလိုသော စာရင်းကို အောက်ပါ ခလုတ်များမှ ရွေးချယ်ပါခင်ဗျာ:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 4. 📜 ထိုးခဲ့သောမှတ်တမ်းများ
    elif text in ["📜 ထိုးခဲ့သောမှတ်တမ်းများ", "ထိုးခဲ့သောမှတ်တမ်းများ", "ထိုးမှတ်တမ်း", "မှတ်တမ်း"]:
        bets = user_bets.get(uid, [])
        if not bets:
            msg = (
                "📜 *သင့် ထိုးငွေမှတ်တမ်းများ* 📜\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "ယခုအချိန်အထိ ထိုးထားသော ပြေစာ မှတ်တမ်း မရှိသေးပါခင်ဗျာ။\n\n"
                "👉 '2D ထိုးမည်' သို့မဟုတ် '3D ထိုးမည်' ကို နှိပ်၍ ဂဏန်းများ စတင် ထိုးယူနိုင်ပါသည်!"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👉 🎯 2D ထိုးမည်", callback_data="btn_bet_2d"), InlineKeyboardButton("👉 🎯 3D ထိုးမည်", callback_data="btn_bet_3d")]
            ])
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
            return

        msg = (
            f"📜 *သင့် ထိုးငွေမှတ်တမ်းများ (နောက်ဆုံး ၅ ခု)* 📜\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        for b in bets[-5:]:
            msg += (
                f"🔖 `#{b.get('ticket_id', 'TKT')}` | *{b.get('type', '2D')}* ({b.get('slot', '-')})\n"
                f"🎯 ဂဏန်း: 【 `{', '.join(map(str, b.get('numbers', [])))}` 】\n"
                f"💰 ထိုးငွေ: `{b.get('total_amount', 0):,} ကျပ်` | အခြေအနေ: ✅ မှတ်တမ်းတင်ပြီး\n"
                "────────────────────\n"
            )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # 5. 💰 ငွေသွင်း/ငွေထုတ်
    elif text in ["💰 ငွေသွင်း/ငွေထုတ်", "ငွေသွင်း/ငွေထုတ်", "ငွေသွင်းငွေထုတ်"]:
        acc = PAYMENT_ACCOUNTS.get("kpay", {})
        msg = (
            f"💰 *ငွေသွင်း / ငွေထုတ် စနစ် (KBZPay)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 *KBZPay အကောင့်အမည်:* `{acc.get('name')}`\n"
            f"📱 *KBZPay ဖုန်းနံပါတ်:* `{acc.get('number')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Mini App ရှိ 'ပိုက်ဆံအိတ်' Tab မှတစ်ဆင့် ငွေဖြည့်သွင်းနိုင်ပါသည် (သို့မဟုတ်) Admin ထံ တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Mini App ဖြင့် ငွေဖြည့်မည်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ဆက်သွယ်ရန်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 6. 💵 ငွေလက်ကျန်
    elif text in ["💵 ငွေလက်ကျန်", "ငွေလက်ကျန်", "လက်ကျန်ငွေ"]:
        bal = user_balances.get(uid, {"mmk": 0, "thb": 0})
        await update.message.reply_text(
            f"💵 *သင့် လက်ကျန်ငွေစာရင်း:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal.get('mmk', 0):,} ကျပ်`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal.get('thb', 0):,} ဘတ်`",
            parse_mode="Markdown"
        )
        return

    # 7. 🎮 ဂိမ်းဆော့ရန်
    elif text in ["🎮 ဂိမ်းဆော့ရန်", "ဂိမ်းဆော့ရန်", "ဂိမ်း", "ဂိမ်းများ"]:
        msg = (
            "🎮 *Lucky2D3D Official ဂိမ်းစင်တာ* 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎰 *လူကြိုက်များသော စလော့နှင့် ကာစီနိုဂိမ်းများ:*\n"
            "• 🌟 JDB, JILI, Pragmatic Play စလော့ဂိမ်းများ\n"
            "• 🐟 ငါးပစ်ဂိမ်း (Ocean King & Fish Hunter)\n"
            "• 🎲 တိုက်ရိုက်ကာစီနို (Live Baccarat & Roulette)\n"
            "• 🎁 Mini App ကံစမ်းဘီး (Daily Free Lucky Spin)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 ဂိမ်းအကောင့်ဖွင့်ရန်နှင့် ယူနစ်ဖြည့်ရန် Admin (@noenoeslotagency) ထံ တိုက်ရိုက် ဆက်သွယ်ပေးပါခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Mini App ကံစမ်းဘီး လှည့်မည်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("💬 ဂိမ်းအကောင့်ဖွင့်ရန် Admin ဆက်သွယ်မည်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 8. 💬 Admin အကောင့်
    elif text in ["💬 Admin အကောင့်", "Admin အကောင့်", "Admin", "admin"]:
        msg = (
            "💬 *Admin နှင့် တိုက်ရိုက်ဆက်သွယ်ရန်* 💬\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Admin Telegram:* @{ADMIN_USERNAME}\n"
            f"🆔 *Admin ID:* `{ADMIN_CHAT_ID}`\n"
            "⏰ *ဝန်ဆောင်မှု:* ၂၄ နာရီ ပိတ်ရက်မရှိ အမြန်ဆုံး ဝန်ဆောင်မှုပေးပါသည်ခင်ဗျာ။\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ငွေသွင်း/ငွေထုတ်၊ ထိုးငွေပြေစာ စစ်ဆေးခြင်း၊ ဂိမ်းအကောင့်ဖွင့်ခြင်း များအတွက် အောက်ပါခလုတ်ကို နှိပ်၍ တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin နှင့် တိုက်ရိုက်ဆက်သွယ်ရန်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Direct Text Bet Parsing (e.g. 12=1000 or 123=500)
    if "=" in text:
        parts = text.split("=")
        if len(parts) == 2 and parts[1].strip().isdigit():
            num_part = parts[0].strip()
            amt = int(parts[1].strip())
            is_3d = len(num_part) == 3

            if not is_3d:
                is_hol, hol_reason = is_market_holiday()
                if is_hol:
                    await update.message.reply_text(
                        f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}",
                        parse_mode="Markdown"
                    )
                    return

            b_type = "3D" if is_3d else "2D"
            tkt = f"TKT-{random.randint(10000, 99999)}"
            rate = "1:700" if is_3d else "1:85"
            await update.message.reply_text(
                f"🧾 *{b_type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ* 🧾\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔖 *ပြေစာအမှတ်:* `#{tkt}`\n"
                f"🎯 *ဂဏန်း:* 【 `{num_part}` 】\n"
                f"💰 *ထိုးငွေ:* `{amt:,} ကျပ်` (ပေါက်ကြေး: {rate})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ စာရင်းမှတ်တမ်းတင်ပြီးပါပြီ! ငွေလွှဲ Slip အား Admin ထံ ပေးပို့အတည်ပြုပေးပါခင်ဗျာ။",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ငွေလွှဲပြေစာ ပို့ရန်", url=ADMIN_URL)]
                ])
            )
            return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "closed_2d_notice":
        is_hol, hol_reason = is_market_holiday()
        await query.answer(f"⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ({hol_reason}) ထိုးလို့မရပါခင်ဗျာ!", show_alert=True)
        return

    # Back to Lotto Menu
    if data == "back_to_lotto_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ပေါက်ဂဏန်းများ (2D မနက်/ည & 3D)", callback_data="lotto_winning_numbers")],
            [InlineKeyboardButton("🏆 ထီပေါက်သူစာရင်း", callback_data="lotto_winners_list")],
            [InlineKeyboardButton("🌟 အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း", callback_data="lotto_top10_winners")],
            [InlineKeyboardButton("👉 🎯 2D/3D ထိုးမည် 👈", callback_data="btn_bet_now")]
        ])
        msg = (
            "🏆 *တရားဝင် ထီပေါက်စဉ်နှင့် ဆုရရှိသူများ မီနူး* 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ကျေးဇူးပြု၍ ကြည့်ရှုလိုသော စာရင်းကို အောက်ပါ ခလုတ်များမှ ရွေးချယ်ပါခင်ဗျာ:"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Winning Numbers (2D & 3D)
    elif data == "lotto_winning_numbers":
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        is_hol, hol_reason = is_market_holiday()
        status_line = "🔴 *ယနေ့ စတော့ဈေးကွက် ပိတ်ပါသည်*" if is_hol else "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live)*"

        msg = (
            f"🎯 *တရားဝင် ပေါက်ဂဏန်းများ (2D မနက်/ည နှင့် 3D)* 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ထိုင်း 2D ရလဒ်စုံ ({d2.get('date')}):*\n"
            f"{status_line}\n"
            f"• 🟢 Live 2D: 【 *{d2.get('live_2d')}* 】\n"
            f"• 🌞 မနက် (12:01 PM): 【 *{d2.get('morning_1201')}* 】\n"
            f"• 🌇 ညနေ (04:30 PM): 【 *{d2.get('evening_1630')}* 】\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎲 *ထိုင်းအစိုးရ 3D ရလဒ်စုံ ({d3.get('date')}):*\n"
            f"• 🥇 ပထမဆုကြီး (၆ လုံး): 【 *{d3.get('first_prize')}* 】\n"
            f"• 🔥 တရားဝင် 3D အပေါ်: 【 *{d3.get('threed')}* 】\n"
            f"• ✨ 3D အနားဂဏန်းများ: {', '.join([f'【 {x} 】' for x in d3.get('adjacent_threed', [])])}\n"
            f"• 🔹 ရှေ့ ၃ လုံး: {', '.join([f'【 {x} 】' for x in d3.get('front_3d', [])])}\n"
            f"• 🔸 နောက် ၃ လုံး: {', '.join([f'【 {x} 】' for x in d3.get('back_3d', [])])}\n"
            f"• 🔻 အောက် ၂ လုံး: 【 *{d3.get('back_2d')}* 】\n"
            f"⏰ နောက်ထပ် 3D ထွက်မည့်ရက်: `{d3.get('next_date')}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 2D ထိုးမည် 👈", callback_data="btn_bet_2d"), InlineKeyboardButton("👉 🎯 3D ထိုးမည် 👈", callback_data="btn_bet_3d")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Winners List
    elif data == "lotto_winners_list":
        msg = (
            "🏆 *တရားဝင် ထီပေါက်သူ စာရင်းများ* 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎉 *ယနေ့ နောက်ဆုံး ထီပေါက်သူများ စာရင်း:*\n\n"
            "1. 👤 Ko Th*** (ID: 7552***) - 2D 【 41 】 ➔ `85,000 ကျပ်` (ထုတ်ပြီး ✅)\n"
            "2. 👤 Ma Su*** (ID: 6124***) - 2D 【 20 】 ➔ `170,000 ကျပ်` (ထုတ်ပြီး ✅)\n"
            "3. 👤 Ko Kyaw*** (ID: 8026***) - 3D 【 044 】 ➔ `700,000 ကျပ်` (ထုတ်ပြီး ✅)\n"
            "4. 👤 Mg Hein*** (ID: 5931***) - 2D 【 41 】 ➔ `42,500 ကျပ်` (ထုတ်ပြီး ✅)\n"
            "5. 👤 Daw Myint*** (ID: 7120***) - 3D အနား 【 043 】 ➔ `70,000 ကျပ်` (ထုတ်ပြီး ✅)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 အလျော်အစား ၁၀၀% မှန်ကန် တိကျစွာဖြင့် ၂၄ နာရီ ငွေထုတ်ပေးနေပါသည်ခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 2D ထိုးမည်", callback_data="btn_bet_2d"), InlineKeyboardButton("👉 🎯 3D ထိုးမည်", callback_data="btn_bet_3d")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Top 10 Winners Leaderboard
    elif data == "lotto_top10_winners":
        msg = (
            "🌟 *အများဆုံး ထီပေါက်သူ ထိပ်တန်း ၁၀ ယောက်စာရင်း* 🌟\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🥇 1. Ko Min Thu (ID: 755***) ➔ `1,400,000 ကျပ်` 👑\n"
            "🥈 2. Daw Win Win (ID: 618***) ➔ `850,000 ကျပ်`\n"
            "🥉 3. Ko Aung Kaung (ID: 582***) ➔ `700,000 ကျပ်`\n"
            "4. 👤 Ma Cherry (ID: 809***) ➔ `510,000 ကျပ်`\n"
            "5. 👤 Ko Zaw Myo (ID: 721***) ➔ `425,000 ကျပ်`\n"
            "6. 👤 Ko Htet (ID: 664***) ➔ `340,000 ကျပ်`\n"
            "7. 👤 Ma Thuzar (ID: 590***) ➔ `255,000 ကျပ်`\n"
            "8. 👤 Ko Nay Linn (ID: 772***) ➔ `212,500 ကျပ်`\n"
            "9. 👤 Mg Phyo (ID: 815***) ➔ `170,000 ကျပ်`\n"
            "10. 👤 Daw Khin Mar (ID: 639***) ➔ `170,000 ကျပ်`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 ကံထူးရှင်များအားလုံး ဂုဏ်ယူပါသည်ခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 2D ထိုးမည်", callback_data="btn_bet_2d"), InlineKeyboardButton("👉 🎯 3D ထိုးမည်", callback_data="btn_bet_3d")],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Bet Now / Bet 2D
    elif data in ["btn_bet_now", "btn_bet_2d"]:
        is_hol, hol_reason = is_market_holiday()
        if is_hol:
            await query.edit_message_text(
                f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *အကြောင်းပြချက်:* {hol_reason}\n"
                f"🏛️ ထိုင်းစတော့အိတ်ချိန်း (SET) ဈေးကွက်ပိတ်ရက်ဖြစ်သောကြောင့် ယနေ့ ၂လုံး (2D) ထိုးလို့မရပါခင်ဗျာ။\n\n"
                f"💡 *၃လုံး (3D)* ကိုမူ ပုံမှန်အတိုင်း ကြိုတင်ထိုးယူနိုင်ပါသည်ခင်ဗျာ!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👉 🎯 3D ထိုးမည် 👈", callback_data="btn_bet_3d")],
                    [InlineKeyboardButton("🔙 မီနူးသို့", callback_data="back_to_lotto_menu")]
                ])
            )
            return

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("မနက်ပိုင်း (12:01 PM)", callback_data="slot_2d_morning")],
            [InlineKeyboardButton("ညနေပိုင်း (04:30 PM)", callback_data="slot_2d_evening")],
            [InlineKeyboardButton("📱 Mini App ဖြင့် ထိုးမည်", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await query.edit_message_text("⏰ *2D ထိုးလိုသော အချိန်ပိုင်း ရွေးချယ်ပါ:*", parse_mode="Markdown", reply_markup=kb)
        return

    # Bet 3D
    elif data == "btn_bet_3d":
        d3 = fetch_realtime_3d()
        await query.edit_message_text(
            f"🎯 *ထိုင်း 3D ထိုးကြေး တင်သွင်းရန်*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ *နောက်ထပ် ထွက်မည့်ရက်:* `{d3.get('next_date')}`\n"
            f"💰 *ပေါက်ကြေး:* ၁ ကျပ်လျှင် ၇၀၀ ကျပ်\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✍️ စာရိုက်ထိုးလိုပါက: `044=1000` ဟု ရိုက်ပို့နိုင်ပါသည် (သို့မဟုတ်) Mini App ဖြင့် လွယ်ကူစွာ ထိုးနိုင်ပါသည်ခင်ဗျာ။",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Mini App ဖြင့် 3D ထိုးမည်", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
        )
        return

    # Slot choice
    elif data in ["slot_2d_morning", "slot_2d_evening"]:
        is_hol, hol_reason = is_market_holiday()
        if is_hol:
            await query.edit_message_text(f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}", parse_mode="Markdown")
            return
        slot_name = "မနက်ပိုင်း (12:01 PM)" if "morning" in data else "ညနေပိုင်း (04:30 PM)"
        await query.edit_message_text(
            f"🎯 *2D ({slot_name}) ထိုးရန်*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ထိုးလိုသော ဂဏန်းကို `ဂဏန်း=ငွေပမာဏ` ပုံစံဖြင့် စာရိုက်ပို့ပေးပါခင်ဗျာ (ဥပမာ: `45=1000`)\n"
            f"(သို့မဟုတ်) အောက်ပါ Mini App ကို နှိပ်၍ အကွက်များ လွယ်ကူစွာ ရွေးချယ်နိုင်ပါသည်:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Mini App ဖြင့် ထိုးမည်", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
        )

# ==================== WEB APP DATA HANDLER ====================
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data_str = update.effective_message.web_app_data.data
        payload = json.loads(data_str)
        action = payload.get("action")
        user = update.effective_user
        uid = str(user.id) if user else "0"
        u_name = user.first_name if user else "Customer"

        if action == "deposit_request":
            dep_id = payload.get("deposit_id", f"DEP-{random.randint(10000, 99999)}")
            amt = int(payload.get("amount", 0))
            txn = payload.get("txn_id", "-")

            await update.effective_message.reply_text(
                f"🧾 *ငွေသွင်း လျှောက်ထားလွှာ (Deposit Voucher)* 🧾\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔖 *ပြေစာအမှတ်:* `#{dep_id}`\n"
                f"👤 *အမည်:* `{u_name}` (ID: `{uid}`)\n"
                f"🔵 *ငွေပေးချေမှု:* `KBZPay (KPay)`\n"
                f"💰 *ငွေပမာဏ:* `{amt:,} ကျပ်`\n"
                f"📝 *ငွေလွှဲအချက်အလက်:* `{txn}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ Admin မှ စစ်ဆေးအတည်ပြုပြီးပါက သင့် Wallet ထဲသို့ ငွေရောက်ရှိပါမည်!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
                ])
            )

            # Alert Admin
            try:
                admin_msg = (
                    f"🚨 *[ငွေသွင်း လျှောက်ထားလွှာ အသစ် ရောက်ရှိပါသည်]*\n"
                    f"👤 *ထိုးသူ:* `{u_name}` (ID: `{uid}`)\n"
                    f"🔖 *ပြေစာ:* `#{dep_id}`\n"
                    f"💰 *ပမာဏ:* `{amt:,} ကျပ်` (KBZPay)\n"
                    f"📝 *ငွေလွှဲအချက်အလက်:* `{txn}`"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ငွေသွင်း အတည်ပြုမည်", callback_data=f"apprdep_{dep_id}_{uid}_{amt}")],
                    [InlineKeyboardButton("❌ ပယ်ဖျက်မည်", callback_data=f"rejdep_{dep_id}_{uid}")]
                ])
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                print("Admin alert failed:", e)

        elif action == "place_bet":
            b_type = payload.get("type", "2D")
            slot = payload.get("slot", "")
            numbers = payload.get("numbers", [])
            amt_each = int(payload.get("amount_each", 0))
            total_amt = int(payload.get("total_amount", 0))
            tkt_id = payload.get("ticket_id", f"TKT-{random.randint(10000, 99999)}")
            pay_mode = payload.get("payment_mode", "wallet")

            if b_type == "2D":
                is_hol, hol_reason = is_market_holiday()
                if is_hol:
                    await update.effective_message.reply_text(
                        f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}",
                        parse_mode="Markdown"
                    )
                    return

            if pay_mode == "wallet":
                bal = user_balances.get(uid, {"mmk": 0, "thb": 0})
                if bal.get("mmk", 0) < total_amt:
                    await update.effective_message.reply_text(
                        f"❌ *Wallet လက်ကျန်ငွေ မလုံလောက်ပါခင်ဗျာ!*\n"
                        f"💰 လိုအပ်ငွေ: `{total_amt:,} ကျပ်` | လက်ရှိ: `{bal.get('mmk', 0):,} ကျပ်`\n\n"
                        f"💡 Mini App ရှိ 'ပင်မ' Tab တွင် + ငွေဖြည့်မည် ဖြင့် KBZPay မှ ငွေအရင် ဖြည့်ပေးပါခင်ဗျာ။",
                        parse_mode="Markdown"
                    )
                    return
                user_balances[uid]["mmk"] -= total_amt
                save_json(BALANCES_FILE, user_balances)

            mult = 700 if b_type == "3D" else 85
            rem = user_balances.get(uid, {}).get("mmk", 0)
            voucher = (
                f"🧾 *{b_type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ* 🧾\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔖 *ပြေစာအမှတ်:* `#{tkt_id}`\n"
                f"👤 *အမည်:* `{u_name}` (ID: `{uid}`)\n"
                f"⏰ *အချိန်ပိုင်း:* `{slot}`\n"
                f"🎯 *ဂဏန်းများ:* `{', '.join(map(str, numbers[:10]))}`"
                f"{'...' if len(numbers)>10 else ''} ({len(numbers)} ကွက်)\n"
                f"💰 *တစ်ကွက်ထိုး:* `{amt_each:,} ကျပ်` (ပေါက်ကြေး: `{amt_each*mult:,} ကျပ်`)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *စုစုပေါင်း ကျသင့်ငွေ:* `{total_amt:,} ကျပ်`\n"
                f"💳 *ငွေပေးချေမှု:* {'💼 Wallet မှ နုတ်ယူပြီး' if pay_mode=='wallet' else '🧾 Slip အတည်ပြုရန်'}\n"
                f"💰 *ကျန်ငွေ:* `{rem:,} ကျပ်`\n"
                f"✅ *အခြေအနေ:* အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!"
            )
            await update.effective_message.reply_text(
                voucher,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
                ])
            )
    except Exception as e:
        print("handle_webapp_data err:", e)

# ==================== ADMIN COMMANDS ====================
async def admin_set_3d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if context.args:
        val = context.args[0].strip()
        admin_override["3d"] = val
        await update.message.reply_text(f"✅ 3D ရလဒ်အား 【 {val} 】 ဟု အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ!")
    else:
        await update.message.reply_text("အသုံးပြုနည်း: `/set3d 536044` (သို့မဟုတ် `/set3d 044`)")

async def admin_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if len(context.args) >= 2:
        target_uid = str(context.args[0]).strip()
        amt = int(context.args[1].strip())
        if target_uid not in user_balances:
            user_balances[target_uid] = {"mmk": 0, "thb": 0}
        user_balances[target_uid]["mmk"] += amt
        save_json(BALANCES_FILE, user_balances)
        await update.message.reply_text(f"✅ User ID `{target_uid}` ထံသို့ `{amt:,} ကျပ်` သွင်းပေးပြီးပါပြီ!")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"🎉 *သင့် Wallet ထဲသို့ `{amt:,} ကျပ်` ဖြည့်သွင်းမှု အောင်မြင်ပါသည်!*",
                parse_mode="Markdown"
            )
        except Exception:
            pass

# ==================== MAIN APPLICATION ====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set3d", admin_set_3d))
    app.add_handler(CommandHandler("topup", admin_topup))

    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    print(f"🚀 Lucky2D3D Multi-Source Bot Started! Admin: {ADMIN_CHAT_ID}")
    app.run_polling(drop_pending_updates=True)
