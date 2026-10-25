import os
import json
import time
import random
import asyncio
import logging
import threading
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 1. RENDER CLOUD 24/7 WEB SERVER
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Myanmar 2D/3D All-in-One Telegram Bot Running Live 24/7!".encode('utf-8'))

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"Web server started on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

# ==========================================
# 2. CONFIGURATION & ADMIN INFO (TELEGRAM ONLY)
# ==========================================
TOKEN = '8988776248:AAFj84YUTvHfWXjH-Mc4fPgbkx-MjR6ytG8'
ADMIN_USERNAME = "Sno78".lstrip('@')

USERS_FILE = "users.json"
BETS_FILE = "bets_data.json"
MARKET_FILE = "market_data.json"
PAYMENT_FILE = "payment_data.json"

# ==========================================
# 3. DATA STORAGE & HELPERS
# ==========================================
def get_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def add_user(user_id):
    users = set(get_users())
    if user_id not in users:
        users.add(user_id)
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(users), f)
        except Exception as e:
            print(f"Error saving user: {e}")

def get_user_bets(user_id):
    if not os.path.exists(BETS_FILE):
        return []
    try:
        with open(BETS_FILE, "r", encoding="utf-8") as f:
            all_bets = json.load(f)
            return all_bets.get(str(user_id), [])
    except Exception:
        return []

def save_bet(user_id, bet_info):
    all_bets = {}
    if os.path.exists(BETS_FILE):
        try:
            with open(BETS_FILE, "r", encoding="utf-8") as f:
                all_bets = json.load(f)
        except Exception:
            all_bets = {}

    uid_str = str(user_id)
    if uid_str not in all_bets:
        all_bets[uid_str] = []

    all_bets[uid_str].append(bet_info)
    try:
        with open(BETS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_bets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving bet: {e}")

def get_market_data():
    default_data = {
        "ak_gold": "၅,၆၈၀,၀၀၀ ကျပ် (ပြင်ပပေါက်ဈေး)",
        "fifteen_gold": "၅,၃၂၀,၀၀၀ ကျပ်",
        "world_gold": "$2,745 / oz (XAU/USD)",
        "usd": "၄,၅၂၀ ကျပ် (ပြင်ပပေါက်ဈေး)",
        "thb": "၁၃၂.၅ ကျပ် (၁ ဘတ်)",
        "sgd": "၃,၄၂၀ ကျပ် (၁ ဒေါ်လာ)",
        "myr": "၁,၀၄၀ ကျပ် (၁ ရင်းဂစ်)",
        "updated_time": "ယနေ့ ဈေးကွက်ပေါက်ဈေး"
    }
    if not os.path.exists(MARKET_FILE):
        return default_data
    try:
        with open(MARKET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_data

def save_market_data(ak, fifteen, world, usd, thb):
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")
    data = get_market_data()
    data["ak_gold"] = ak
    data["fifteen_gold"] = fifteen
    data["world_gold"] = world
    data["usd"] = usd
    data["thb"] = thb
    data["updated_time"] = now_str
    try:
        with open(MARKET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving market data: {e}")
    return data

def get_payment_info():
    default_info = {
        "kpay_no": "09xxxxxxxxx",
        "kpay_name": "Admin Name",
        "wave_no": "09xxxxxxxxx",
        "wave_name": "Admin Name",
        "min_deposit": "1,000 ကျပ်",
        "min_withdraw": "3,000 ကျပ်"
    }
    if not os.path.exists(PAYMENT_FILE):
        return default_info
    try:
        with open(PAYMENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_info

# ==========================================
# 4. 2D LIVE API DATA
# ==========================================
def fetch_2d_results():
    url = "https://api.thaistock2d.com/live"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching 2D API: {e}")
    return None

def format_results_message():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    today_str = now.strftime("%d-%m-%Y")
    data = fetch_2d_results()

    time_map = {
        "11:00:00": "မနက် ၁၁:၀၀",
        "12:01:00": "နေ့လယ် ၁၂:၀၁",
        "15:00:00": "ညနေ ၀၃:၀၀",
        "16:30:00": "ညနေ ၀၄:၃၀"
    }

    if not data or "live" not in data:
        return (
            f"🏆 <b>ယနေ့ 2D/3D ထွက်ဂဏန်းများ ({today_str})</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ လက်ရှိတွင် Live Data မရရှိနိုင်သေးပါ (ပိတ်ရက် သို့မဟုတ် ဈေးကွက်ဖွင့်ချိန် မရောက်သေးပါ)။\n\n"
            "⏰ <b>2D ထွက်ရှိချိန်များ:</b>\n"
            "▫️ မနက် ၁၁:၀၀\n"
            "▫️ နေ့လယ် ၁၂:၀၁\n"
            "▫️ ညနေ ၀၃:၀၀\n"
            "▫️ ညနေ ၀၄:၃၀\n\n"
            "🎯 <b>3D ထွက်ဂဏန်း:</b> လစဉ် ၁ ရက် နှင့် ၁၆ ရက်\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Refresh ခလုတ်ကို နှိပ်၍ အသစ်ရယူနိုင်ပါသည်</i>"
        )

    live = data.get("live", {})
    results = data.get("result", [])

    live_2d = live.get("twod", "--")
    live_set = live.get("set", "--")
    live_val = live.get("value", "--")
    live_time = live.get("time", "")

    msg = (
        f"🏆 <b>မြန်မာ 2D/3D ယနေ့ ထွက်ဂဏန်းများ ({today_str})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Live 2D:</b> 【 <b>{live_2d}</b> 】\n"
        f"📈 SET: <code>{live_set}</code> | 💰 Value: <code>{live_val}</code>\n"
        f"🕒 အချိန်: <code>{live_time}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ <b>ယနေ့ ထွက်ရှိပြီး ဂဏန်းများ:</b>\n\n"
    )

    for r in results:
        open_time = r.get("open_time", "")
        label = time_map.get(open_time, open_time)
        twod = r.get("twod", "--")
        set_val = r.get("set", "--")
        msg += f"▫️ <b>{label}:</b> 【 <b>{twod}</b> 】 (SET: {set_val})\n"

    msg += (
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>3D ထွက်ဂဏန်း:</b> လစဉ် ၁ ရက် နှင့် ၁၆ ရက်\n\n"
        "🔍 <b>ပေါက်ဂဏန်း အလိုအလျောက် တိုက်ရန်:</b>\n"
        "မိမိထိုးထားသော ဂဏန်း ၂ လုံး (ဥပမာ - <code>45</code>) ကို စာရိုက်ပို့၍ တိုက်ဆိုင်စစ်ဆေးနိုင်ပါသည်ခင်ဗျာ!"
    )
    return msg

def format_market_message():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    today_str = datetime.now(tz_mm).strftime("%d-%m-%Y")
    data = get_market_data()

    msg = (
        f"🪙 <b>ရွှေဈေးနှင့် ကမ္ဘာ့ငွေကြေး ပေါက်ဈေးများ ({today_str})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🥇 <b>မြန်မာ့ရွှေဈေး:</b>\n"
        f"• အခေါက်ရွှေ (၁၆ ပဲရည်): <code>{data.get('ak_gold')}</code>\n"
        f"• ၁၅ ပဲရည် ရွှေဈေး: <code>{data.get('fifteen_gold')}</code>\n\n"
        "🌍 <b>ကမ္ဘာ့ရွှေဈေး:</b>\n"
        f"• World Gold (Spot): <code>{data.get('world_gold')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💵 <b>နိုင်ငံခြားငွေလဲနှုန်း (Foreign Exchange):</b>\n"
        f"• အမေရိကန်ဒေါ်လာ (USD): <code>{data.get('usd')}</code>\n"
        f"• ထိုင်းဘတ် (THB): <code>{data.get('thb')}</code>\n"
        f"• စင်ကာပူဒေါ်လာ (SGD): <code>{data.get('sgd')}</code>\n"
        f"• မလေးရှားရင်းဂစ် (MYR): <code>{data.get('myr')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>နောက်ဆုံး အပ်ဒိတ်: {data.get('updated_time')}</i>\n\n"
        "💡 <i>ဈေးကွက် အတက်အကျအလိုက် အချိန်နှင့်တပြေးညီ ပြောင်းလဲနိုင်ပါသည်ခင်ဗျာ။</i>"
    )
    return msg

# ==========================================
# 5. KEYBOARD MENUS
# ==========================================
def get_main_menu(is_admin=False):
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်/ID")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("🏆 ထီပေါက်စဉ်/တိုက်ရန်"), KeyboardButton("🪙 ရွှေဈေး/ငွေဈေး")],
        [KeyboardButton("🎮 Game ကဏ္ဍ"), KeyboardButton("📜 ထိုးမှတ်တမ်း")],
        [KeyboardButton("👩‍💻 Admin Account"), KeyboardButton("🏠 Home")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("📢 Admin Broadcast")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==========================================
# 6. BOT COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user = update.effective_user
        add_user(user.id)
        is_admin = (user.username or "").lower() == ADMIN_USERNAME.lower()
        await update.message.reply_text(
            f"✨ <b>မြန်မာ 2D/3D & Game စနစ်မှ ကြိုဆိုပါသည်</b> ✨\n\n"
            f"👤 အကောင့်: <b>{user.first_name}</b>\n"
            f"🆔 သင်၏ User ID: <code>{user.id}</code>\n\n"
            "၂လုံး၊ ၃လုံး ထီပေါက်စဉ်များ၊ ရွှေဈေး/ငွေဈေးများနှင့် ဂိမ်းများကို အချိန်နှင့်တပြေးညီ ကြည့်ရှုနိုင်ပါသည်ခင်ဗျာ။\n\n"
            "မိမိ ပြုလုပ်လိုသည်ကို အောက်ပါ ခလုတ်များမှ ရွေးချယ်ပါ -",
            parse_mode="HTML",
            reply_markup=get_main_menu(is_admin)
        )

def is_2d_open():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    if now.weekday() in [5, 6]:
        return False, "📅 ယနေ့သည် 2D ပိတ်ရက် ဖြစ်ပါသဖြင့် အသုံးပြု၍မရနိုင်ပါ ❌"
    return True, "ဖွင့်လှစ်ထားပါသည်"

# ဂဏန်း ပေါက်/မပေါက် တိုက်ပေးခြင်း
async def check_winning_number(update: Update, number_str: str):
    data = fetch_2d_results()
    if not data or "result" not in data:
        await update.message.reply_text(
            f"🎯 <b>ဂဏန်း 【 {number_str} 】 အား စစ်ဆေးချက်:</b>\n\n"
            "⚠️ ယနေ့အတွက် Live Data မရရှိသေးပါ (သို့မဟုတ်) ဈေးကွက်ပိတ်ချိန် ဖြစ်ပါသည်ခင်ဗျာ။",
            parse_mode="HTML"
        )
        return

    results = data.get("result", [])
    found_matches = []
    time_map = {
        "11:00:00": "မနက် ၁၁:၀၀",
        "12:01:00": "နေ့လယ် ၁၂:၀၁",
        "15:00:00": "ညနေ ၀၃:၀၀",
        "16:30:00": "ညနေ ၀၄:၃၀"
    }

    for r in results:
        open_time = r.get("open_time", "")
        label = time_map.get(open_time, open_time)
        twod = r.get("twod", "")
        if twod == number_str:
            found_matches.append(label)

    if found_matches:
        matches_str = "၊ ".join(found_matches)
        await update.message.reply_text(
            f"🎉 <b>ဂုဏ်ယူပါသည်! ပေါက်ပါသည်!</b> 🎉\n\n"
            f"🎯 ထိုးဂဏန်း: 【 <b>{number_str}</b> 】\n"
            f"🏆 ပေါက်သောအချိန်: <b>{matches_str}</b>\n\n"
            "💰 အနိုင်ငွေ ထုတ်ယူရန် Admin ထံ ချက်ချင်း ဆက်သွယ်လိုက်ပါခင်ဗျာ!",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"🎯 <b>ဂဏန်း 【 {number_str} 】 အား စစ်ဆေးချက်:</b>\n\n"
            "❌ ယနေ့ထွက်ရှိထားသော ပေါက်ဂဏန်းများနှင့် မတိုက်ဆိုင်သေးပါခင်ဗျာ။\n"
            "နောက်ပွဲများတွင် ကံကောင်းပါစေခင်ဗျာ! 🍀",
            parse_mode="HTML"
        )

# ထိုးပြေစာ ဘောင်ချာ ထုတ်ပေးသည့် Function (Ticket Generator)
async def process_bet_ticket(update: Update, text: str):
    user = update.effective_user
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)

    parts = text.split("=")
    num_part = parts[0].strip().upper()
    amount_part = parts[1].strip()

    is_3d = len(num_part.rstrip('R')) == 3
    bet_type = "3D" if is_3d else "2D"
    date_str = now.strftime("%d-%m-%Y %I:%M %p")
    ticket_id = f"{bet_type}{now.strftime('%d%m')}-{random.randint(1000, 9999)}"

    bet_data = {
        "ticket_id": ticket_id,
        "type": bet_type,
        "number": num_part,
        "amount": amount_part,
        "date": date_str
    }
    save_bet(user.id, bet_data)

    voucher_text = (
        f"🧾 <b>{bet_type} တရားဝင် ထိုးပြေစာ (Voucher)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>ပြေစာ ID:</b> <code>#{ticket_id}</code>\n"
        f"👤 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>နေ့စွဲ/အချိန်:</b> <code>{date_str}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>ထိုးဂဏန်း:</b> 【 <b>{num_part}</b> 】\n"
        f"💰 <b>ထိုးငွေ:</b> <b>{amount_part} ကျပ်</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>စာရင်း အောင်မြင်စွာ မှတ်သားပြီးပါပြီ!</b>\n"
        "💡 <i>အငြင်းပွားမှုမရှိစေရန် ပြေစာနံပါတ်ကို သိမ်းထားပါခင်ဗျာ။</i>"
    )
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])
    await update.message.reply_text(voucher_text, parse_mode="HTML", reply_markup=inline_kb)

# ==========================================
# 7. MAIN BUTTONS HANDLER
# ==========================================
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    user = update.effective_user
    add_user(user.id)
    is_admin = (user.username or "").lower() == ADMIN_USERNAME.lower()

    # 1. ဂဏန်းထိုးခြင်း (45=500 သို့မဟုတ် 789=1000 ပါပါက တိုက်ရိုက် ထိုးပြေစာ ဘောင်ချာ ထုတ်ပေးခြင်း)
    if "=" in text:
        parts = text.split("=")
        if len(parts) == 2 and parts[1].strip().isdigit():
            await process_bet_ticket(update, text)
            return

    # 2. ဂဏန်း ၂ လုံး ရိုက်ပို့ပါက အလိုအလျောက် ပေါက်ဂဏန်း တိုက်ပေးခြင်း
    if text.isdigit() and len(text) in [2, 3]:
        await check_winning_number(update, text)
        return

    # 3. 2D ထိုး
    if "2D ထိုး" in text:
        is_open, msg = is_2d_open()
        if not is_open:
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text(
                "🎯 <b>2D ထိုးရန် Format:</b>\n"
                "<code>ဂဏန်း=ငွေပမာဏ</code>\n\n"
                "💡 ဥပမာ စာရိုက်ပို့ပါ -\n"
                "• <code>45=500</code> (၄၅ ကို ၅၀၀ ကျပ်)\n"
                "• <code>45R=500</code> (၄၅ အာ ၅၀၀ ကျပ်)\n\n"
                "📌 အလျော်အစား: ၈၅ ဆ / ၉၀ ဆ\n"
                "ရိုက်ပို့လိုက်သည်နှင့် <b>တရားဝင် ထိုးပြေစာ (Voucher ID)</b> အလိုအလျောက် ထွက်လာပါမည်!",
                parse_mode="HTML"
            )

    # 4. 3D ထိုး
    elif "3D ထိုး" in text:
        await update.message.reply_text(
            "🎯 <b>3D ထိုးရန် Format:</b>\n"
            "<code>ဂဏန်း=ငွေပမာဏ</code>\n\n"
            "💡 ဥပမာ စာရိုက်ပို့ပါ -\n"
            "• <code>789=1000</code> (၇၈၉ ကို ၁၀၀၀ ကျပ်)\n"
            "• <code>789R=1000</code> (၇၈၉ အာ ၁၀၀၀ ကျပ်)\n\n"
            "📌 အလျော်အစား: တိုက်ရိုက် ၇၀၀ ဆ / ပတ်လည် ၁၀ ဆ\n"
            "📌 ထွက်မည့်ရက်: လစဉ် ၁ ရက် နှင့် ၁၆ ရက်\n"
            "ရိုက်ပို့လိုက်သည်နှင့် <b>တရားဝင် ထိုးပြေစာ (Voucher ID)</b> အလိုအလျောက် ထွက်လာပါမည်!",
            parse_mode="HTML"
        )

    # 5. ထီပေါက်စဉ် / တိုက်ရန်
    elif "ထီပေါက်စဉ်" in text:
        res_msg = format_results_message()
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_results")]
        ])
        await update.message.reply_text(res_msg, parse_mode="HTML", reply_markup=inline_kb)

    # 6. ရွှေဈေး / ငွေဈေး
    elif "ရွှေဈေး" in text or "ငွေဈေး" in text:
        market_msg = format_market_message()
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh ဈေးနှုန်းအသစ်ရယူရန်", callback_data="refresh_market")]
        ])
        await update.message.reply_text(market_msg, parse_mode="HTML", reply_markup=inline_kb)

    # 7. ငွေသွင်း / ငွေထုတ်
    elif "ငွေသွင်း" in text or "ငွေထုတ်" in text:
        pay = get_payment_info()
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        msg = (
            "💳 <b>ငွေသွင်း / ငွေထုတ် အချက်အလက်များ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>သင့် User ID:</b> <code>{user.id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📥 <b>ငွေသွင်းရန် အကောင့်များ:</b>\n"
            f"📱 <b>KBZPay:</b> <code>{pay.get('kpay_no')}</code> ({pay.get('kpay_name')})\n"
            f"📱 <b>WavePay:</b> <code>{pay.get('wave_no')}</code> ({pay.get('wave_name')})\n\n"
            f"💵 အနည်းဆုံး ငွေသွင်း: {pay.get('min_deposit')}\n"
            f"💵 အနည်းဆုံး ငွေထုတ်: {pay.get('min_withdraw')}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>ငွေလွှဲမှတ်ချက် (Note):</b> တွင် မိမိ User ID <code>{user.id}</code> ထည့်သွင်းပေးပါခင်ဗျာ။\n"
            "ငွေလွှဲပြေစာ ပုံကို Bot ထဲ ပို့လိုက်သည်နှင့် အကောင့်ထဲ ငွေချက်ချင်း ဖြည့်ပေးပါမည်!"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=inline_kb)

    # 8. ငွေလက်ကျန် / ID
    elif "ငွေလက်ကျန်" in text or "ID" in text:
        tz_mm = timezone(timedelta(hours=6, minutes=30))
        today_str = datetime.now(tz_mm).strftime("%d-%m-%Y")
        msg = (
            "💵 <b>သင့်အကောင့် အချက်အလက်</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>အမည်:</b> {user.first_name}\n"
            f"🆔 <b>သင့် User ID:</b> <code>{user.id}</code>\n"
            f"💰 <b>လက်ကျန်ငွေ:</b> 0 ကျပ်\n"
            f"📅 <b>နေ့စွဲ:</b> <code>{today_str}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ငွေဖြည့်လိုပါက '💰 ငွေသွင်း/ငွေထုတ်' ခလုတ်ကို နှိပ်ပါခင်ဗျာ။"
        )
        await update.message.reply_text(msg, parse_mode="HTML")

    # 9. ထိုးမှတ်တမ်း (ဘောင်ချာများ ပြန်ကြည့်ခြင်း)
    elif "မှတ်တမ်း" in text:
        user_bets = get_user_bets(user.id)
        if not user_bets:
            await update.message.reply_text(
                f"📜 <b>ထိုးခဲ့သော မှတ်တမ်းများ</b>\n"
                f"🆔 User ID: <code>{user.id}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါခင်ဗျာ။",
                parse_mode="HTML"
            )
        else:
            msg = (
                f"📜 <b>သင်၏ ထိုးပြေစာ မှတ်တမ်းများ ({len(user_bets)} စောင်)</b>\n"
                f"🆔 User ID: <code>{user.id}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )
            for b in user_bets[-5:]:
                msg += (
                    f"▫️ <b>#{b.get('ticket_id')}</b> ({b.get('date')})\n"
                    f"   ဂဏန်း: 【 <b>{b.get('number')}</b> 】 | ငွေ: <b>{b.get('amount')} ကျပ်</b>\n"
                )
            msg += "━━━━━━━━━━━━━━━━━━━━\n💡 <i>အထက်ပါ စာရင်းများသည် တရားဝင် ထိုးပြေစာများ ဖြစ်ပါသည်</i>"
            await update.message.reply_text(msg, parse_mode="HTML")

    # 10. Game ကဏ္ဍ
    elif "Game" in text or "ဂိမ်း" in text:
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် ဆက်သွယ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        msg = (
            "🎮 <b>လူကြိုက်များသော ဂိမ်းကဏ္ဍများ</b> 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 <b>ဆော့ကစားနိုင်သော ဂိမ်းများ:</b>\n"
            "• JDB / JILI / CQ9 စလော့ဂိမ်းများ\n"
            "• ရှမ်းကိုးမီး၊ ဘူကြီး၊ ရွှေရှမ်း ဖဲဂိမ်းများ\n"
            "• တိုက်ရိုက် ကာစီနို (Live Casino) & ငါးပစ်ဂိမ်းများ\n"
            "• အလျော်အစား ၁၀၀% တိကျမှန်ကန်မှု\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ဂိမ်းအကောင့် အခမဲ့ဖွင့်ရန် Telegram မှတစ်ဆင့် တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ -"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=inline_kb)

    # 11. Admin Account (TELEGRAM ONLY)
    elif "Admin" in text or "admin" in text:
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် စကားပြောရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        msg = (
            "👇 <b>Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန်</b> 👇\n\n"
            f"👤 <b>Admin Telegram:</b> @{ADMIN_USERNAME}\n\n"
            "၂၄ နာရီ ဝန်ဆောင်မှု ပေးနေပါသည်ခင်ဗျာ။ အောက်ပါ ခလုတ်ကို နှိပ်ပြီး <b>Telegram မှတစ်ဆင့် တိုက်ရိုက် ဆက်သွယ် စကားပြောနိုင်ပါသည်ခင်ဗျာ။</b>"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=inline_kb)

    # 12. Home
    elif "Home" in text or "home" in text:
        await update.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ရောက်ရှိနေပါပြီ။", reply_markup=get_main_menu(is_admin))

    # 13. Broadcast Info for Admin
    elif "Broadcast" in text or "broadcast" in text:
        if not is_admin:
            await update.message.reply_text("⛔ သင်သည် Admin မဟုတ်ပါသဖြင့် ဤကဏ္ဍကို သုံးခွင့်မရှိပါခင်ဗျာ။")
            return
        users_count = len(get_users())
        await update.message.reply_text(
            f"📢 <b>Admin Broadcast စနစ်</b>\n\n"
            f"👥 လက်ရှိ စာရင်းဝင် အသုံးပြုသူ: <b>{users_count}</b> ဦး\n\n"
            "အသုံးပြုသူ အားလုံးထံ စာပို့လိုပါက အောက်ပါအတိုင်း စာရိုက်ပို့ပါ -\n\n"
            "<code>/broadcast ပို့လိုသောစာသား</code>\n\n"
            "ဥပမာ -\n"
            "<code>/broadcast မင်္ဂလာပါ ယနေ့ ညနေ 2D ပရိုမိုးရှင်း စတင်ပါပြီ!</code>",
            parse_mode="HTML"
        )

# ==========================================
# 8. PHOTO / PAYMENT SLIP HANDLER
# ==========================================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    user = update.effective_user
    add_user(user.id)
    await update.message.reply_text(
        f"✅ <b>ငွေလွှဲပြေစာ ပုံအား လက်ခံရရှိပါသည်!</b>\n\n"
        f"🆔 သင့် User ID: <code>{user.id}</code>\n\n"
        "ကျေးဇူးပြု၍ မိမိ၏ <b>KPay/Wave ဖုန်းနံပါတ်</b> နှင့် <b>ငွေပမာဏ</b> ကို စာရိုက်ပို့ပေးထားပါခင်ဗျာ။\n"
        f"Admin (@{ADMIN_USERNAME}) ဘက်မှ ၂ မိနစ်အတွင်း အကောင့်ထဲ ငွေဖြည့်သွင်းပေးပါမည်ခင်ဗျာ! 🙏",
        parse_mode="HTML"
    )

# ==========================================
# 9. CALLBACK QUERIES (REFRESH BUTTONS)
# ==========================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "refresh_results":
        res_msg = format_results_message()
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_results")]
        ])
        try:
            await query.edit_message_text(text=res_msg, parse_mode="HTML", reply_markup=inline_kb)
        except Exception:
            pass

    elif query.data == "refresh_market":
        market_msg = format_market_message()
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh ဈေးနှုန်းအသစ်ရယူရန်", callback_data="refresh_market")]
        ])
        try:
            await query.edit_message_text(text=market_msg, parse_mode="HTML", reply_markup=inline_kb)
        except Exception:
            pass

# ==========================================
# 10. ADMIN COMMANDS (/setgold, /broadcast)
# ==========================================
async def set_gold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = (user.username or "").lower()
    if username != ADMIN_USERNAME.lower():
        await update.message.reply_text("⛔ သင်သည် Admin မဟုတ်ပါသဖြင့် ဤ Command ကို သုံးခွင့်မရှိပါခင်ဗျာ။")
        return

    raw_text = " ".join(context.args)
    if not raw_text or "|" not in raw_text:
        await update.message.reply_text(
            "🪙 <b>ရွှေဈေး/ငွေဈေး ပြင်ဆင်နည်း Format:</b>\n\n"
            "<code>/setgold အခေါက်ရွှေ | ၁၅ပဲရည် | ကမ္ဘာ့ရွှေ | ဒေါ်လာ | ဘတ်</code>\n\n"
            "ဥပမာ -\n"
            "<code>/setgold 5,700,000 ကျပ် | 5,350,000 ကျပ် | $2,750 | 4,530 ကျပ် | 133 ကျပ်</code>",
            parse_mode="HTML"
        )
        return

    parts = [p.strip() for p in raw_text.split("|")]
    if len(parts) >= 5:
        ak, fifteen, world, usd, thb = parts[0], parts[1], parts[2], parts[3], parts[4]
        save_market_data(ak, fifteen, world, usd, thb)
        await update.message.reply_text(
            "✅ <b>ဈေးကွက်ပေါက်ဈေးများကို အောင်မြင်စွာ ပြင်ဆင်ပြီးပါပြီ!</b>\n\n"
            + format_market_message(),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ ဈေးနှုန်း ၅ ခုလုံးကို | (မတ်တတ်လိုင်း) ခြား၍ ပြည့်စုံစွာ ထည့်သွင်းပေးပါခင်ဗျာ။")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = (user.username or "").lower()
    if username != ADMIN_USERNAME.lower():
        await update.message.reply_text("⛔ သင်သည် Admin မဟုတ်ပါသဖြင့် ဤ Command ကို သုံးခွင့်မရှိပါခင်ဗျာ။")
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>Broadcast အသုံးပြုနည်း:</b>\n\n"
            "<code>/broadcast သင်ပို့လိုသော စာသား</code>\n\n"
            "ဥပမာ -\n"
            "<code>/broadcast မင်္ဂလာပါ ယနေ့အတွက် 2D အထူးပရိုမိုးရှင်း စတင်ပါပြီ!</code>",
            parse_mode="HTML"
        )
        return

    text_to_send = " ".join(context.args)
    users = get_users()
    total = len(users)

    if total == 0:
        await update.message.reply_text("⚠️ စာပို့ရန် Bot အသုံးပြုသူ မရှိသေးပါခင်ဗျာ။")
        return

    status_msg = await update.message.reply_text(f"⏳ အသုံးပြုသူ {total} ဦးထံသို့ စာပို့နေပါသည်...")

    success_count = 0
    fail_count = 0

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 <b>[သတင်းလွှာ / အသိပေးချက်]</b>\n\n{text_to_send}",
                parse_mode="HTML"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"✅ <b>Broadcast ပို့ဆောင်ပြီးစီးပါပြီ!</b>\n\n"
        f"👥 စုစုပေါင်း: {total} ဦး\n"
        f"🟢 အောင်မြင်စွာ ပို့ပြီး: {success_count} ဦး\n"
        f"🔴 မရောက်ရှိသူ: {fail_count} ဦး",
        parse_mode="HTML"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Bot Error occurred: {context.error}")

# ==========================================
# 11. MAIN APPLICATION LOOP (AUTO-RETRY)
# ==========================================
if __name__ == '__main__':
    while True:
        try:
            print("🚀 Bot စတင် အလုပ်လုပ်နေပါပြီ...")
            app = ApplicationBuilder().token(TOKEN).build()
            app.add_handler(CommandHandler('start', start))
            app.add_handler(CommandHandler('broadcast', broadcast_command))
            app.add_handler(CommandHandler('setgold', set_gold_command))
            app.add_handler(CallbackQueryHandler(handle_callback))
            app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
            app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
            app.add_error_handler(error_handler)
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            print(f"Telegram connection error: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
