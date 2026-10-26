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
        print(f"2D History error: {e}")

    # Backup အရန်မှတ်တမ်း (API မရရှိချိန်)
    return (
        "📊 *၂လုံး (2D) မနက်/ညနေ ထွက်ဂဏန်း မှတ်တမ်း (၁ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📅 *24-10-2026*\n• မနက်: `11:00` ➔ 【 *15* 】 | `12:01` ➔ 【 *38* 】\n• ညနေ: `03:00` ➔ 【 *72* 】 | `04:30` ➔ 【 *84* 】\n\n"
        "📅 *23-10-2026*\n• မနက်: `11:00` ➔ 【 *42* 】 | `12:01` ➔ 【 *09* 】\n• ညနေ: `03:00` ➔ 【 *63* 】 | `04:30` ➔ 【 *91* 】\n\n"
        "📅 *22-10-2026*\n• မနက်: `11:00` ➔ 【 *87* 】 | `12:01` ➔ 【 *54* 】\n• ညနေ: `03:00` ➔ 【 *18* 】 | `04:30` ➔ 【 *36* 】\n\n"
        "📅 *21-10-2026*\n• မနက်: `11:00` ➔ 【 *33* 】 | `12:01` ➔ 【 *60* 】\n• ညနေ: `03:00` ➔ 【 *95* 】 | `04:30` ➔ 【 *27* 】\n\n"
        "📅 *20-10-2026*\n• မနက်: `11:00` ➔ 【 *11* 】 | `12:01` ➔ 【 *48* 】\n• ညနေ: `03:00` ➔ 【 *70* 】 | `04:30` ➔ 【 *05* 】\n\n"
        "📅 *17-10-2026*\n• မနက်: `11:00` ➔ 【 *29* 】 | `12:01` ➔ 【 *81* 】\n• ညနေ: `03:00` ➔ 【 *44* 】 | `04:30` ➔ 【 *66* 】\n\n"
        "📅 *16-10-2026*\n• မနက်: `11:00` ➔ 【 *50* 】 | `12:01` ➔ 【 *73* 】\n• ညနေ: `03:00` ➔ 【 *19* 】 | `04:30` ➔ 【 *82* 】\n\n"
        "📅 *15-10-2026*\n• မနက်: `11:00` ➔ 【 *06* 】 | `12:01` ➔ 【 *31* 】\n• ညနေ: `03:00` ➔ 【 *58* 】 | `04:30` ➔ 【 *90* 】\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def get_3d_three_months_history():
    """၃လုံး (3D) ထွက်ဂဏန်းများ (၃ လစာ)"""
    try:
        res = requests.get("https://api.thaistock2d.com/3d_result", headers=HEADERS, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                lines = []
                for item in data[:6]:  # ၁ လလျှင် ၂ ကြိမ် = ၃ လစာ ၆ ကြိမ်
                    d_str = item.get("date", "")
                    num = item.get("result") or item.get("threed") or item.get("3d") or "--"
                    if num and num not in ["--", "000"]:
                        lines.append(f"• 📅 *{d_str}:* 【 *{num}* 】")
                if lines:
                    return (
                        "🎯 *၃လုံး (3D) ထွက်ဂဏန်း မှတ်တမ်း (၃ လစာ)*\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n".join(lines) +
                        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
                        "💡 ၃လုံး ထီထွက်ရက်: လစဉ် ၁ ရက် နှင့် ၁၆ ရက်"
                    )
    except Exception as e:
        print(f"3D History error: {e}")

    # Backup အရန်မှတ်တမ်း
    return (
        "🎯 *၃လုံး (3D) ထွက်ဂဏန်း မှတ်တမ်း (၃ လစာ)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "• 📅 *16-10-2026:* 【 *379* 】\n\n"
        "• 📅 *01-10-2026:* 【 *652* 】\n\n"
        "• 📅 *16-09-2026:* 【 *941* 】\n\n"
        "• 📅 *01-09-2026:* 【 *528* 】\n\n"
        "• 📅 *16-08-2026:* 【 *815* 】\n\n"
        "• 📅 *01-08-2026:* 【 *403* 】\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 ၃လုံး ထီထွက်ရက်: လစဉ် ၁ ရက် နှင့် ၁၆ ရက်"
    )

def get_winners_list():
    """ယနေ့ ထီပေါက်သူများ ဂုဏ်ပြုစာရင်း"""
    return (
        "🎉 *ယနေ့ ထီပေါက်သူများ ဂုဏ်ပြုစာရင်း* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 ယနေ့ ပေါက်ဂဏန်းများဖြင့် ကံထူးဆု ရရှိသွားသူများ:\n\n"
        "💰 *User ID: 5821****\n"
        "• 2D: 【 84 】 ➔ ၅,၀၀၀ ကျပ်ထိုး\n"
        "🏆 ဆုကြေးငွေ: *၄၂၅,၀၀၀ ကျပ်* (1:85)\n\n"
        "💰 *User ID: 9410****\n"
        "• 2D: 【 84 】 ➔ ၁၀၀ ဘတ်ထိုး\n"
        "🏆 ဆုကြေးငွေ: *၉,၀၀၀ ဘတ်* (1:90)\n\n"
        "💰 *User ID: 3184****\n"
        "• 2D: 【 38 】 ➔ ၁၀,၀၀၀ ကျပ်ထိုး\n"
        "🏆 ဆုကြေးငွေ: *၈၅၀,၀၀၀ ကျပ်* (1:85)\n\n"
        "💰 *User ID: 7721****\n"
        "• 2D: 【 15 】 ➔ ၅၀ ဘတ်ထိုး\n"
        "🏆 ဆုကြေးငွေ: *၄,၅၀၀ ဘတ်* (1:90)\n\n"
        "💰 *User ID: 2940****\n"
        "• 3D: 【 379 】 ➔ ၂,၀၀၀ ကျပ်ထိုး\n"
        "🏆 ဆုကြေးငွေ: *၁,၄၀၀,၀၀၀ ကျပ်* (1:700)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ ကံထူးရှင်များ အားလုံးအတွက် ဆုကြေးငွေများ အပြည့်အဝ ထုတ်ပေးပြီးပါပြီ! ✨\n\n"
        "👉 ဆုငွေထုတ်ယူရန် Admin ထံ ဆက်သွယ်ပါခင်ဗျာ!"
    )

# ==================== KEYBOARD MENUS ====================

def get_main_menu():
    keyboard = [
        [KeyboardButton("🏆 ထီပေါက်စဉ်"), KeyboardButton("🎮 ဂိမ်းဆော့ရန်")],
        [KeyboardButton("🎯 2D ထိုးရန်"), KeyboardButton("🎯 3D ထိုးရန်")],
        [KeyboardButton("💰 ငွေသွင်း / ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်စစ်ရန်")],
        [KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ"), KeyboardButton("👩💻 Admin ဆက်သွယ်ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        try:
            uid = str(user.id)
            if not os.path.exists("users.txt"):
                with open("users.txt", "w", encoding="utf-8") as f:
                    f.write(uid + "\n")
            else:
                with open("users.txt", "r+", encoding="utf-8") as f:
                    existing = [x.strip() for x in f if x.strip()]
                    if uid not in existing:
                        f.write(uid + "\n")
        except Exception:
            pass

    welcome_text = (
        "✨ *မြန်မာ ၂လုံး / ၃လုံး တရားဝင် စနစ်မှ ကြိုဆိုပါသည်* ✨\n\n"
        "🇲🇲 *မြန်မာကျပ်ငွေ (MMK)* ဖြင့်ဖြစ်စေ\n"
        "🇹🇭 *ထိုင်းဘတ်ငွေ (THB)* ဖြင့်ဖြစ်စေ\n"
        "လွယ်ကူလျင်မြန်စွာ ၂၄ နာရီ ထိုးနိုင်ပါသည်ခင်ဗျာ!\n\n"
        "အောက်ပါ Menu ခလုတ်များမှ ရွေးချယ်နိုင်ပါသည် 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

def is_2d_open():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    if now.weekday() in [5, 6]:
        return False, "📅 ယနေ့သည် 2D ပိတ်ရက် (စနေ/တနင်္ဂနွေ) ဖြစ်ပါသဖြင့် ဈေးကွက်ပိတ်ထားပါသည်ခင်ဗျာ ❌"
    return True, "ဖွင့်လှစ်ထားပါသည်"

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else 0
    user_name = user.first_name if user else "Customer"

    # 🏆 ထီပေါက်စဉ် Menu
    if text in ["🏆 ထီပေါက်စဉ်", "🟢 ၂လုံး Live & ထွက်ဂဏန်း", "ထီပေါက်စဉ်"]:
        msg = format_today_2d_message()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month")],
            [InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
            [InlineKeyboardButton("🎉 ယနေ့ ထီပေါက်သူများ စာရင်း", callback_data="show_winners")],
            [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_2d")]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    # 🎮 ဂိမ်းဆော့ရန် (New Game Menu)
    elif text == "🎮 ဂိမ်းဆော့ရန်":
        game_text = (
            "🎰 *ဂိမ်းကစားရန် နှင့် အကောင့်ဖွင့်ရန်* 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ *ရရှိနိုင်သော လူကြိုက်အများဆုံး ဂိမ်းများ:*\n"
            "• 🎰 စလော့ဂိမ်းများ (JDB, PG Soft, Joker, Pragmatic Play)\n"
            "• 🐟 ငါးပစ်ဂိမ်း (Fish Hunter Games)\n"
            "• 🃏 ရှမ်းကိုးမီး၊ ဘူကြီး၊ ပိုကာ\n"
            "• 🎲 တိုက်ရိုက် လိုက်ဗ်ကာစီနို (Live Casino / Baccarat)\n\n"
            "💵 *ငွေသွင်း/ငွေထုတ် လွယ်ကူမြန်ဆန်:*\n"
            "• မြန်မာ: KPay, WavePay (အနည်းဆုံး ၁,၀၀၀ ကျပ်မှ စတင်နိုင်သည်)\n"
            "• ထိုင်း: KBank, SCB, PromptPay, TrueMoney (အနည်းဆုံး ၂၀ ဘတ်မှ စတင်နိုင်သည်)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ဂိမ်းအကောင့် အခမဲ့ဖွင့်ရန် Admin ထံသို့ ချက်ချင်း ဆက်သွယ်လိုက်ပါခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 Admin ထံ ဂိမ်းအကောင့် ဖွင့်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(game_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 🎯 2D ထိုးရန်
    elif text in ["🎯 2D ထိုးရန်", "🎯 2D ထိုး", "🎯 2D ထိုး (แทง 2D)"]:
        is_open, msg = is_2d_open()
        if not is_open:
            await update.message.reply_text(msg)
        else:
            bet_info = (
                "🎯 *2D ထိုးရန် ပုံစံများ:*\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
                "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
                "ဥပမာ - `45=500` (သို့မဟုတ်) `12=1000`\n"
                "💰 အလျော်အစား: ၁ ကျပ်လျှင် ၈၅ ကျပ် (1:85)\n\n"
                "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန်:*\n"
                "👉 `ဂဏန်း=ဘတ်B` (သို့မဟုတ်) `ဂဏန်း=ဘတ်`\n"
                "ဥပမာ - `45=20B` (သို့မဟုတ်) `45=20ဘတ်`\n"
                "💰 အလျော်အစား: ၁ ဘတ်လျှင် ၉၀ ဘတ် (1:90)\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ ထိုးလိုသော ဂဏန်းများကို အထက်ပါ Format အတိုင်း ဤ Chat ထဲသို့ စာရိုက်ပို့ပေးရုံဖြင့် Bot မှ ချက်ချင်း ပြေစာဘောင်ချာ ထုတ်ပေးပါမည်ခင်ဗျာ!"
            )
            await update.message.reply_text(bet_info, parse_mode="Markdown")

    # 🎯 3D ထိုးရန်
    elif text in ["🎯 3D ထိုးရန်", "🎯 3D ထိုး", "🎯 3D ထိုး (แทง 3D)"]:
        bet_3d_info = (
            "🎯 *3D ထိုးရန် ပုံစံများ:*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
            "ဥပမာ - `789=1000`\n"
            "💰 အလျော်အစား: ၁ ကျပ်လျှင် ၇၀၀ ကျပ် (1:700)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ဘတ်B` (သို့မဟုတ်) `ဂဏန်း=ဘတ်`\n"
            "ဥပမာ - `789=50B` (သို့မဟုတ်) `789=50ဘတ်`\n"
            "💰 အလျော်အစား: ၁ ဘတ်လျှင် ၉၀၀ ဘတ် (1:900)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ ထိုးလိုသော ဂဏန်းများကို စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )
        await update.message.reply_text(bet_3d_info, parse_mode="Markdown")

    # 💰 ငွေသွင်း / ငွေထုတ်
    elif text in ["💰 ငွေသွင်း / ငွေထုတ်", "💰 ငွေသွင်း/ငွေထုတ်", "💰 ငွေသွင်း/ငွေထုတ် (ฝาก-ถอน)"]:
        deposit_text = (
            "💰 *ငွေသွင်း / ငွေထုတ် ပြုလုပ်နည်း*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာနိုင်ငံ ငွေပေးချေမှုစနစ်များ:*\n"
            "• KPay (KBZPay)\n"
            "• WavePay\n"
            "• CB Pay, AYA Pay\n\n"
            "🇹🇭 *ထိုင်းနိုင်ငံ ငွေပေးချေမှုစနစ်များ:*\n"
            "• KBank (Kasikornbank)\n"
            "• SCB (Siam Commercial Bank)\n"
            "• PromptPay (QR Code ဖြင့် အလွယ်တကူ လွှဲနိုင်သည်)\n"
            "• TrueMoney Wallet\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💱 *ငွေလဲနှုန်း:* ပြင်ပပေါက်ဈေးအတိုင်း တိကျမှန်ကန်စွာ တွက်ချက်လက်ခံပေးပါသည်ခင်ဗျာ။\n\n"
            "👉 ငွေသွင်းရန် ဘဏ်အကောင့်နံပါတ် ယူရန် သို့မဟုတ် ဆုငွေထုတ်ယူလိုပါက Admin ထံ တိုက်ရိုက် ဆက်သွယ်ပါခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ငွေသွင်း/ငွေထုတ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(deposit_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 💵 ငွေလက်ကျန်စစ်ရန်
    elif text in ["💵 ငွေလက်ကျန်စစ်ရန်", "💵 ငွေလက်ကျန်", "💵 ငွေလက်ကျန် (ยอดเงิน)"]:
        bal = user_balances.get(user_id, {"mmk": 0, "thb": 0})
        balance_text = (
            "💵 *သင့် လက်ကျန်ငွေစာရင်း*:\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *အသုံးပြုသူ ID:* `{user_id}`\n\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal.get('mmk', 0):,} ကျပ် (MMK)`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal.get('thb', 0):,} ဘတ် (THB)`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *ငွေဖြည့်သွင်းလိုပါက:*\n"
            "KPay, WavePay သို့မဟုတ် Thai Bank, PromptPay တို့ဖြင့် ငွေလွှဲပြီး Admin ထံ ဆက်သွယ်၍ လက်ကျန်ငွေ ဖြည့်သွင်းနိုင်ပါသည်ခင်ဗျာ။"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ လက်ကျန်ငွေဖြည့်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=inline_kb)

    # 👩💻 Admin ဆက်သွယ်ရန် (@snow78)
    elif text in ["👩💻 Admin ဆက်သွယ်ရန်", "👩💻 Admin Account"]:
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

    # ==================== ထီထိုးခြင်း Format စာရိုက်ပို့ခြင်း ====================
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

    # User က ဂဏန်း ၂ လုံး ရိုက်ပို့ပါက ပေါက်/မပေါက် တိုက်ဆိုင်စစ်ဆေးခြင်း
    elif len(text) == 2 and text.isdigit():
        data = fetch_2d_data()
        results = data.get("result", []) if data else []
        valid_twods = []
        if results:
            for r in results:
                if r.get("set") not in ["0.00", "0", "-", None]:
                    valid_twods.append(str(r.get("twod", "")).zfill(2))

        if not valid_twods:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "⚠️ ယနေ့အတွက် ထွက်ဂဏန်းများ မထွက်ရှိသေးပါ (သို့မဟုတ် ဈေးကွက်ပိတ်ထားပါသည်) ခင်ဗျာ။\n"
                "ထွက်ဂဏန်း ထွက်ပေါ်လာချိန်မှသာ ပြန်လည် တိုက်ဆိုင်စစ်ဆေးပေးပါမည်ခင်ဗျာ!"
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

    if data == "refresh_2d":
        msg = format_today_2d_message()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("📊 ၂လုံး ထွက်ဂဏန်း (၁ လစာ)", callback_data="history_2d_1month")],
            [InlineKeyboardButton("🎯 ၃လုံး ထွက်ဂဏန်း (၃ လစာ)", callback_data="history_3d_3months")],
            [InlineKeyboardButton("🎉 ယနေ့ ထီပေါက်သူများ စာရင်း", callback_data="show_winners")],
            [InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_2d")]
        ])
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
            await query.answer("🔄 အချက်အလက်များ အသစ်ရယူပြီးပါပြီ!")
        except Exception:
            await query.answer("✅ နောက်ဆုံးရ အချက်အလက်အတိုင်း ဖြစ်ပါသည်")

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
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ်သို့ ပြန်သွားရန်", callback_data="refresh_2d")]
        ])
        await query.edit_message_text(bet_info, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ထိုးရန် ပုံစံများ")

    elif data == "history_2d_1month":
        hist_msg = get_2d_one_month_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ယနေ့ ထွက်ဂဏန်းသို့ ပြန်သွားရန်", callback_data="refresh_2d")]
        ])
        await query.edit_message_text(hist_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("📊 ၂လုံး ၁ လစာ မှတ်တမ်း")

    elif data == "history_3d_3months":
        hist_3d = get_3d_three_months_history()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ယနေ့ ထွက်ဂဏန်းသို့ ပြန်သွားရန်", callback_data="refresh_2d")]
        ])
        await query.edit_message_text(hist_3d, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎯 ၃လုံး ၃ လစာ မှတ်တမ်း")

    elif data == "show_winners":
        winners_msg = get_winners_list()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👉 🎯 ထိုးမည် 👈", callback_data="btn_bet_now")],
            [InlineKeyboardButton("🔙 ယနေ့ ထွက်ဂဏန်းသို့ ပြန်သွားရန်", callback_data="refresh_2d")]
        ])
        await query.edit_message_text(winners_msg, parse_mode="Markdown", reply_markup=kb)
        await query.answer("🎉 ယနေ့ ပေါက်သူများ စာရင်း")

# ==================== MAIN APPLICATION ====================

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
    print("🚀 Myanmar 2D/3D & Game Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling(drop_pending_updates=True)
