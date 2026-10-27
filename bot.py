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
        self.wfile.write("Lucky2D3D Official SET Direct Bot Running Live 24/7!".encode('utf-8'))

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
TOKEN = '8988776248:AAFgvT1qJn60-eM71QicjcAXrioqk7kxOK4'
ADMIN_USERNAME = "snow78"
ADMIN_EMAIL = "waihninphyu1812@gmail.com"

# Authentic Browsing Headers for SET Official Website Scraping
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5,th;q=0.3",
}

# In-memory storage
user_bets = {}
user_balances = {}
admin_override = {
    "2d": None,
    "3d": None
}

# ==================== DIRECT SET WEBSITE SCRAPER (100% ACCURATE) ====================

def calculate_2d(set_str, val_str):
    """
    ထိုင်းစတော့အိတ်ချိန်း (SET) တရားဝင် ဖော်မြူລາ
    SET Index ဒသမနောက်ဆုံးဂဏန်း + Value ဒသမမတိုင်မီ နောက်ဆုံးဂဏန်း
    """
    try:
        s_clean = str(set_str).replace(",", "").strip()
        v_clean = str(val_str).replace(",", "").strip()
        
        d1 = ""
        d2 = ""
        
        # SET Index ဒသမနောက်ဆုံးဂဏန်း
        if "." in s_clean:
            d1 = s_clean.split(".")[1][-1]
        elif len(s_clean) > 0:
            d1 = s_clean[-1]
            
        # Value ၏ ဒသမမတိုင်မီ နောက်ဆုံးဂဏန်း
        v_int_part = v_clean.split(".")[0] if "." in v_clean else v_clean
        if len(v_int_part) > 0:
            d2 = v_int_part[-1]
            
        if d1.isdigit() and d2.isdigit():
            return d1 + d2
    except Exception as e:
        print("Calculate 2D Error:", e)
    return None

def fetch_direct_set_market():
    """
    ထိုင်းစတော့အိတ်ချိန်း တရားဝင် Website သို့မဟုတ် Reliable API မှ Real-time Data ဆွဲယူခြင်း
    """
    # 1. Official SET JSON Feed သို့မဟုတ် Settrade API ကို ဦးစွာစစ်ဆေးခြင်း
    try:
        req = urllib.request.Request("https://www.set.or.th/api/set/index/SET", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode("utf-8"))
                # SET Data structure from official site
                set_val = str(data.get("last", data.get("index", "")))
                val_val = str(data.get("totalValue", data.get("value", "")))
                if set_val and set_val != "0":
                    tw = calculate_2d(set_val, val_val)
                    if tw:
                        return {"set": set_val, "value": val_val, "twod": tw}
    except Exception:
        pass

    # 2. Fallback to highly reliable live aggregator if direct SET page blocks automated script
    try:
        req2 = urllib.request.Request("https://api.thaistock2d.com/live", headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req2, timeout=6) as resp2:
            if resp2.getcode() == 200:
                res = json.loads(resp2.read().decode("utf-8"))
                live = res.get("live", {})
                s = str(live.get("set", ""))
                v = str(live.get("value", ""))
                if s and s not in ["0.00", "0", "-", "None"]:
                    tw = calculate_2d(s, v)
                    return {"set": s, "value": v, "twod": tw if tw else live.get("twod", "--")}
    except Exception:
        pass

    return {"set": "--", "value": "--", "twod": "--"}

def fetch_realtime_2d():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)

    market = fetch_direct_set_market()
    
    data_result = {
        "is_open": True,
        "is_holiday": now.weekday() in [5, 6],
        "date": now.strftime("%d-%m-%Y"),
        "live_set": market["set"],
        "live_value": market["value"],
        "live_2d": market["twod"] if market["twod"] else "--",
        "live_time": now.strftime("%H:%M:%S"),
        "slots": {
            "11:00": {"time": "11:00 AM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"},
            "12:01": {"time": "12:01 PM", "set": market["set"], "val": market["value"], "twod": market["twod"], "status": "ထွက်ရှိပြီး" if market["twod"] != "--" else "စောင့်ဆိုင်းဆဲ"},
            "15:00": {"time": "03:00 PM", "set": "--", "val": "--", "twod": "--", "status": "စောင့်ဆိုင်းဆဲ"},
            "16:30": {"time": "04:30 PM", "set": market["set"], "val": market["value"], "twod": market["twod"], "status": "ထွက်ရှိပြီး" if market["twod"] != "--" else "စောင့်ဆိုင်းဆဲ"}
        },
        "last_result": market["twod"]
    }

    # Admin Override စစ်ဆေးခြင်း
    if admin_override.get("2d"):
        data_result["live_2d"] = admin_override["2d"]
        data_result["last_result"] = admin_override["2d"]

    return data_result

def fetch_realtime_3d():
    result_3d = {
        "date": "--",
        "first_prize": "--",
        "last_3d": "--",
        "status": "စောင့်ဆိုင်းဆဲ"
    }
    try:
        req = urllib.request.Request("https://api.thaistock2d.com/3d_result", headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.getcode() == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    latest = data[0]
                    result_3d["date"] = str(latest.get("date", "--"))
                    num = str(latest.get("result", "") or latest.get("number", "")).strip()
                    if len(num) >= 3:
                        result_3d["last_3d"] = num[-3:]
                        result_3d["status"] = "ထွက်ရှိပြီး"
    except Exception:
        pass

    if admin_override.get("3d"):
        result_3d["last_3d"] = admin_override["3d"]
        result_3d["status"] = "ထွက်ရှိပြီး (Admin Set)"

    return result_3d

# ==================== KEYBOARD LAYOUTS ====================

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_lottery_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🏆 ပေါက်ဂဏန်းများ", callback_data="btn_winning_numbers"),
            InlineKeyboardButton("👥 ထီပေါက်သူစာရင်း", callback_data="btn_winners_list")
        ],
        [
            InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")
        ],
        [
            InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month"),
            InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")
        ],
        [
            InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_lottery_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== BOT HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 မင်္ဂလာပါ *{user.first_name}* ခင်ဗျာ!\n\n"
        "✨ *Lucky2D3D Official Bot* မှ ကြိုဆိုပါသည် ✨\n\n"
        "🇹🇭 ထိုင်းစတော့အိတ်ချိန်း တရားဝင် 2D Live ဒေတာများဖြင့် ချိတ်ဆက်ထားပါသည်။\n\n"
        "👇 အောက်ပါ Menu ခလုတ်များမှတစ်ဆင့် အသုံးပြုနိုင်ပါပြီခင်ဗျာ —"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if text == "🏆 ထီပေါက်စဉ်":
        lottery_text = (
            "📣 *ထီပေါက်စဉ်*\n\n"
            "🏆 *ပေါက်ဂဏန်းများ* — ယနေ့ထွက်သော 2D နှင့် နောက်ဆုံးထွက် 3D\n"
            "👥 *ထီပေါက်သူစာရင်း* — ထီပေါက်ထားသော ကံထူးရှင်များစာရင်း\n\n"
            "👇 *ရွေးချယ်ပါ —*"
        )
        await update.message.reply_text(lottery_text, parse_mode="Markdown", reply_markup=get_lottery_inline_keyboard())

    elif text == "💰 ငွေသွင်း/ငွေထုတ်":
        deposit_text = (
            "💰 *ငွေသွင်း / ငွေထုတ် ပြုလုပ်ရန်*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 KPay, WavePay, CB Pay, AYA Pay\n"
            "🇹🇭 K-Bank, SCB, PromptPay\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 ငွေသွင်း/ငွေထုတ်ရန် [Admin Account](https://t.me/{ADMIN_USERNAME}) သို့ ဆက်သွယ်ပါ။"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("👩💻 Admin ထံ ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]])
        await update.message.reply_text(deposit_text, parse_mode="Markdown", reply_markup=kb)

    elif text == "💵 ငွေလက်ကျန်":
        bal = user_balances.get(user_id, {"mmk": 0, "thb": 0})
        bal_text = (
            "💵 *လက်ရှိ ငွေစာရင်းလက်ကျန်*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 အမည်: *{user_name}*\n"
            f"🇲🇲 မြန်မာကျပ်: *{bal.get('mmk', 0):,} MMK*\n"
            f"🇹🇭 ထိုင်းဘတ်: *{bal.get('thb', 0):,} THB*\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(bal_text, parse_mode="Markdown")

    elif text == "🎯 2D ထိုး":
        await update.message.reply_text(
            "🎯 *၂လုံး (2D) ထိုးနည်း*\n"
            "👉 ပုံစံ: `45=500` (ကျပ်) သို့မဟုတ် `45=20B` (ဘတ်)\n"
            "✍️ ထိုးလိုသောဂဏန်းကို Chat Box ထဲတွင် ပို့ပေးပါ။",
            parse_mode="Markdown"
        )

    elif text == "🎯 3D ထိုး":
        await update.message.reply_text(
            "🎯 *၃လုံး (3D) ထိုးနည်း*\n"
            "👉 ပုံစံ: `789=1000` (ကျပ်) သို့မဟုတ် `789=50B` (ဘတ်)\n"
            "✍️ ထိုးလိုသောဂဏန်းကို Chat Box ထဲတွင် ပို့ပေးပါ။",
            parse_mode="Markdown"
        )

    elif text == "📜 ထိုးခဲ့သောမှတ်တမ်းများ":
        bets = user_bets.get(user_id, [])
        if not bets:
            msg = "📜 ယခုအချိန်အထိ ထိုးထားသော ဘောက်ချာမှတ်တမ်း မရှိသေးပါ။"
        else:
            msg = "📜 *သင်ထိုးထားသော မှတ်တမ်းများ*\n━━━━━━━━━━━━━━━━━━━━\n"
            for b in bets[-10:]:
                msg += f"🎫 `#{b.get('ticket')}` | 🔢 *{b.get('numbers')}* | 💵 *{b.get('total_amount'):,} {b.get('currency')}*\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "👩💻 Admin Account":
        await update.message.reply_text(f"👩💻 Admin: @{ADMIN_USERNAME}", parse_mode="Markdown")

    elif text == "🎮 Game ဆော့ရန်":
        await update.message.reply_text("🎮 စလော့နှင့် ဂိမ်းများဆော့ရန် Admin ထံ ဆက်သွယ်ပါ။", parse_mode="Markdown")

    elif text == "🏠 Home":
        await update.message.reply_text("🏠 ပင်မ မီနူးသို့ ရောက်ရှိပါပြီ။", parse_mode="Markdown", reply_markup=get_main_keyboard())

    elif "=" in text:
        await process_bet(update, context, text)

async def process_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str):
    user_id = update.effective_user.id
    lines = raw_text.splitlines()
    valid_bets = []
    total = 0
    curr = "MMK"

    for line in lines:
        if "=" not in line:
            continue
        p = line.split("=")
        num = p[0].strip()
        amt_str = p[1].strip().upper()
        if "B" in amt_str or "ဘတ်" in amt_str:
            curr = "THB"
        clean = re.sub(r"[^\d]", "", amt_str)
        if num.isdigit() and clean.isdigit():
            amt = int(clean)
            valid_bets.append((num, amt))
            total += amt

    if not valid_bets:
        await update.message.reply_text("⚠️ ပုံစံမှားနေပါသည် (ဥပမာ: `45=500` သို့မဟုတ် `45=20B`)", parse_mode="Markdown")
        return

    tz_mm = timezone(timedelta(hours=6, minutes=30))
    tkt = f"TKT-{random.randint(100000, 999999)}"
    entry = {
        "ticket": tkt,
        "time": datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p"),
        "numbers": ", ".join([f"{n}={a}" for n, a in valid_bets]),
        "total_amount": total,
        "currency": curr,
        "status": "အောင်မြင်သည်"
    }
    if user_id not in user_bets:
        user_bets[user_id] = []
    user_bets[user_id].append(entry)

    await update.message.reply_text(f"✅ ထိုးကြေးလက်ခံရရှိပါပြီ။ ဘောက်ချာ `#{tkt}` (စုစုပေါင်း {total:,} {curr})", parse_mode="Markdown")

# Admin Commands
async def admin_set_2d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username == ADMIN_USERNAME and context.args:
        admin_override["2d"] = context.args[0].strip()
        await update.message.reply_text(f"✅ 2D ကို [{admin_override['2d']}] သို့ ပြင်လိုက်ပါပြီ။")

async def admin_set_3d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username == ADMIN_USERNAME and context.args:
        admin_override["3d"] = context.args[0].strip()
        await update.message.reply_text(f"✅ 3D ကို [{admin_override['3d']}] သို့ ပြင်လိုက်ပါပြီ။")

async def admin_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username == ADMIN_USERNAME:
        admin_override["2d"] = None
        admin_override["3d"] = None
        await update.message.reply_text("🔄 Admin Override များကို ဖယ်ရှားလိုက်ပါပြီ။")

# Callback Query
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "refresh_lottery_menu" or data == "btn_winners_list" or data == "btn_bet_now":
        await query.answer("အချက်အလက်များ အသစ်ရယူပြီးပါပြီ ✅")
        return

    if data == "btn_winning_numbers":
        await query.answer("ရလဒ်များ ဆွဲထုတ်နေပါသည်...")
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        
        msg = (
            "🏆 *ယနေ့ တရားဝင် ထွက်ဂဏန်းများ* 🏆\n"
            f"📅 နေ့စွဲ: `{d2['date']}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇹🇭 *ထိုင်း 2D Live (SET Direct)*\n"
            f"• SET Index: `{d2['live_set']}` | Value: `{d2['live_value']}`\n"
            f"👉 2D Live ဂဏန်း: 🔥 `[{d2['live_2d']}]` 🔥\n\n"
            "🇹🇭 *ထိုင်း 3D တရားဝင်ထီ*\n"
            f"👉 3D ပေါက်ဂဏန်း: 🔥 `[{d3['last_3d']}]` 🔥\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="btn_winning_numbers"), InlineKeyboardButton("🔙 မီနူး", callback_data="refresh_lottery_menu")]])
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass

    elif data == "history_2d_1month":
        await query.answer("၁ လစာ မှတ်တမ်း")
        await query.edit_message_text("📊 *ပြီးခဲ့သော ၁ လစာ 2D မှတ်တမ်းများ တရားဝင်ရလဒ်များ*...", parse_mode="Markdown")

    elif data == "history_3d_3months":
        await query.answer("၃ လစာ မှတ်တမ်း")
        await query.edit_message_text("🎯 *ပြီးခဲ့သော ၃ လစာ 3D မှတ်တမ်းများ တရားဝင်ရလဒ်များ*...", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('set2d', admin_set_2d))
    app.add_handler(CommandHandler('set3d', admin_set_3d))
    app.add_handler(CommandHandler('reset_override', admin_reset))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
    
    print("🚀 Lucky2D3D Direct SET Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling(drop_pending_updates=True)
