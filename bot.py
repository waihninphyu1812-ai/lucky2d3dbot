import os
import re
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

# ==================== BOT CREDENTIALS & ADMIN CONFIG ====================
TOKEN = '8988776248:AAFj84YUTvHfWXjH-Mc4fPgbkx-MjR6ytG8'
ADMIN_USERNAME = "Sno78"
ADMIN_EMAIL = "waihninphyu1812@gmail.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

# User bets and balances stored in memory
user_bets = {}
user_balances = {}

# ==================== 2D & 3D DATA FETCHING ====================

def fetch_2d_data():
    """2D Live အချက်အလက်များကို ဆွဲယူခြင်း (Live မရှိပါက နောက်ဆုံးရလဒ်ကို အလိုအလျောက် ဆွဲယူသည်)"""
    try:
        res = requests.get("https://api.thaistock2d.com/live", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json()
            live = data.get("live", {})
            # စတော့ဈေးကွက် ပိတ်ထားချိန် သို့မဟုတ် 0.00 ဖြစ်နေချိန်
            if live.get("set") in ["0.00", "0", "-", None]:
                res_prev = requests.get("https://api.thaistock2d.com/2d_result", headers=HEADERS, timeout=8)
                if res_prev.status_code == 200:
                    prev_data = res_prev.json()
                    if isinstance(prev_data, list) and len(prev_data) > 0:
                        latest_day = prev_data[0]
                        return {"live": live, "result": latest_day.get("child", []), "history_date": latest_day.get("date")}
            return data
    except Exception as e:
        print(f"2D Fetch error: {e}")
    return None

def fetch_3d_data():
    """3D ထွက်ဂဏန်း အချက်အလက်များကို ဆွဲယူခြင်း"""
    try:
        res = requests.get("https://api.thaistock2d.com/3d_result", headers=HEADERS, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
    except Exception as e:
        print(f"3D Fetch error: {e}")
    return None

def format_2d_message():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    date_str = now.strftime("%d-%m-%Y")

    data = fetch_2d_data()
    live = data.get("live", {}) if data else {}
    results = data.get("result", []) if data else []
    history_date = data.get("history_date") if data else None

    set_val = live.get("set", "0.00")
    val_val = live.get("value", "0.00")
    twod_val = live.get("twod", "--")
    time_val = live.get("time", now.strftime("%Y-%m-%d %H:%M:%S"))

    is_closed = (set_val in ["0.00", "0", "-", None])

    time_slots = {
        "11:00": "မနက် ၁၁:၀၀ (11:00 AM)",
        "12:01": "နေ့လယ် ၁၂:၀၁ (12:01 PM)",
        "15:00": "ညနေ ၀၃:၀၀ (03:00 PM)",
        "16:30": "ညနေ ၀၄:၃၀ (04:30 PM)"
    }

    found = {}
    if results:
        for r in results:
            ot = r.get("open_time", "")[:5]
            found[ot] = r

    # နောက်ဆုံးထွက်ရှိခဲ့သော အမှန်တကယ် ပေါက်ဂဏန်းကို ရှာဖွေခြင်း (00 မဖြစ်စေရန်)
    last_winning_num = None
    for slot in ["16:30", "15:00", "12:01", "11:00"]:
        r = found.get(slot)
        if r and r.get("set") not in ["0.00", "0", "-", None]:
            tw = str(r.get("twod", "")).strip()
            if tw and tw not in ["00", "--", "-"]:
                last_winning_num = tw
                break

    if is_closed:
        display_date = history_date if history_date else date_str
        closing_num = last_winning_num if last_winning_num else (twod_val if twod_val not in ["00", "0", "--", ""] else "စောင့်ဆိုင်းဆဲ")
        status_line = "🔴 *ဈေးကွက်ပိတ်ထားပါသည် (Market Closed / ตลาดปิด)*\n*(နောက်ဆုံးထွက်ရှိခဲ့သော တရားဝင် ရလဒ်များ ဖြစ်ပါသည်)*"
        live_line = f"▫️ *နောက်ဆုံးပိတ်ဂဏန်း:* 【 *{closing_num}* 】"
    else:
        display_date = date_str
        status_line = "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live / ผลสด)*"
        live_line = f"🟢 *Live 2D:* 【 *{twod_val}* 】\n📈 *SET:* `{set_val}` | 💰 *Value:* `{val_val}`"

    msg = (
        f"📊 *မြန်မာ/ထိုင်း ၂လုံး (Thai Stock 2D) - {display_date}*\n"
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

    # 3D နောက်ဆုံးထွက်ဂဏန်း ဖော်ပြခြင်း
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
        "🔍 *ပေါက်ဂဏန်း တိုက်ရန် (ตรวจหวย):*\n"
        "မိမိထိုးထားသော ဂဏန်း ၂ လုံး (ဥပမာ - `45`) ကို စာရိုက်ပို့၍ တိုက်ဆိုင်စစ်ဆေးနိုင်ပါသည်ခင်ဗျာ!"
    )
    return msg

# ==================== KEYBOARD MENUS ====================

def get_main_menu():
    keyboard = [
        [KeyboardButton("🟢 ၂လုံး Live & ထွက်ဂဏန်း"), KeyboardButton("🏆 ထီပေါက်စဉ်/တိုက်ရန်")],
        [KeyboardButton("🎯 2D ထိုး (แทง 2D)"), KeyboardButton("🎯 3D ထိုး (แทง 3D)")],
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ် (ฝาก-ถอน)"), KeyboardButton("💵 ငွေလက်ကျန် (ยอดเงิน)")],
        [KeyboardButton("📜 ထိုးထားသော စာရင်းများ"), KeyboardButton("👩💻 Admin Account")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "✨ *မြန်မာ/ထိုင်း 2D & 3D စနစ်မှ ကြိုဆိုပါသည်* ✨\n"
        "ยินดีต้อนรับสู่ระบบหวย 2D/3D พม่า-ไทย 🙏\n\n"
        "🇲🇲 *မြန်မာကျပ်ငွေ (MMK)* ဖြင့်ဖြစ်စေ\n"
        "🇹🇭 *ထိုင်းဘတ်ငွေ (THB / บาท)* ဖြင့်ဖြစ်စေ\n"
        "အဆင်ပြေ လွယ်ကူစွာ တိုက်ရိုက် ထိုးနိုင်ပါသည်ခင်ဗျာ!\n\n"
        "အောက်ပါ Menu ခလုတ်များမှ ရွေးချယ်နိုင်ပါသည် 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

def is_2d_open():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    if now.weekday() in [5, 6]:
        return False, "📅 ယနေ့သည် 2D ပိတ်ရက် (စနေ/တနင်္ဂနွေ) ဖြစ်ပါသဖြင့် အသုံးပြု၍မရနိုင်ပါ ❌\n(วันนี้ตลาดปิด เสาร์-อาทิตย์)"
    return True, "ဖွင့်လှစ်ထားပါသည်"

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id if user else 0

    # ၂လုံး Live & ထွက်ဂဏန်း / ထီပေါက်စဉ် တိုက်ရန်
    if text in ["🟢 ၂လုံး Live & ထွက်ဂဏန်း", "🏆 ထီပေါက်စဉ်/တိုက်ရန်", "🏆 ထီပေါက်စဉ်"]:
        msg = format_2d_message()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_2d")]])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    # 2D ထိုးခြင်း လမ်းညွှန်ချက် (မြန်မာကျပ် & ထိုင်းဘတ်)
    elif text in ["🎯 2D ထိုး (แทง 2D)", "🎯 2D ထိုး"]:
        is_open, msg = is_2d_open()
        if not is_open:
            await update.message.reply_text(msg)
        else:
            bet_info = (
                "🎯 *2D ထိုးရန် ပုံစံများ (รูปแบบการแทง 2D)*:\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🇲🇲 *မြန်မာကျပ်ငွေ (MMK) ဖြင့် ထိုးရန်:*\n"
                "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
                "ဥပမာ - `45=500` (သို့မဟုတ်) `12=1000`\n"
                "💰 အလျော်အစား: ၁ ကျပ်လျှင် ၈၅ ကျပ် (1:85)\n\n"
                "🇹🇭 *ထိုင်းဘတ်ငွေ (THB / บาท) ဖြင့် ထိုးရန်:*\n"
                "👉 `ဂဏန်း=ဘတ်B`\n"
                "ဥပမာ - `45=20B` (သို့မဟုတ်) `45=20ဘတ်` (သို့မဟုတ်) `45=20บาท`\n"
                "💰 အလျော်အစား: ၁ ဘတ်လျှင် ၉၀ ဘတ် (จ่าย 1:90 บาท)\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ ထိုးလိုသော ဂဏန်းများကို အထက်ပါအတိုင်း စာရိုက်ပို့ပေးရုံဖြင့် Bot မှ အလိုအလျောက် မှတ်တမ်းတင်ပေးပါမည်ခင်ဗျာ!"
            )
            await update.message.reply_text(bet_info, parse_mode="Markdown")

    # 3D ထိုးခြင်း လမ်းညွှန်ချက် (မြန်မာကျပ် & ထိုင်းဘတ်)
    elif text in ["🎯 3D ထိုး (แทง 3D)", "🎯 3D ထိုး"]:
        bet_3d_info = (
            "🎯 *3D ထိုးရန် ပုံစံများ (รูปแบบการแทง 3D)*:\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာကျပ်ငွေဖြင့် ထိုးရန်:*\n"
            "👉 `ဂဏန်း=ကျပ်ငွေ`\n"
            "ဥပမာ - `789=1000`\n"
            "💰 အလျော်အစား: ၁ ကျပ်လျှင် ၇၀၀ ကျပ် (1:700)\n\n"
            "🇹🇭 *ထိုင်းဘတ်ငွေဖြင့် ထိုးရန် (บาท):*\n"
            "👉 `ဂဏန်း=ဘတ်B`\n"
            "ဥပမာ - `789=50B` (သို့မဟုတ်) `789=50ဘတ်` (သို့မဟုတ်) `789=50บาท`\n"
            "💰 အလျော်အစား: ၁ ဘတ်လျှင် ၉၀၀ ဘတ် (จ่าย 1:900 บาท)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ ထိုးလိုသော ဂဏန်းများကို စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )
        await update.message.reply_text(bet_3d_info, parse_mode="Markdown")

    # ငွေသွင်း/ငွေထုတ် (မြန်မာ & ထိုင်း ဘဏ်များ အပြည့်အစုံ)
    elif text in ["💰 ငွေသွင်း/ငွေထုတ် (ฝาก-ถอน)", "💰 ငွေသွင်း/ငွေထုတ်"]:
        deposit_text = (
            "💰 *ငွေသွင်း / ငွေထုတ် ပြုလုပ်နည်း (ฝาก - ถอนเงิน)*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🇲🇲 *မြန်မာနိုင်ငံမှ ငွေပေးချေမှုစနစ်များ:*\n"
            "• KPay (KBZPay)\n"
            "• WavePay\n"
            "• CB Pay, AYA Pay\n\n"
            "🇹🇭 *ထိုင်းနိုင်ငံမှ ငွေပေးချေမှုစနစ်များ (ช่องทางโอนเงินไทย):*\n"
            "• KBank (Kasikornbank / ธนาคารกสิกรไทย)\n"
            "• SCB (Siam Commercial Bank / ไทยพาณิชย์)\n"
            "• PromptPay (พร้อมเพย์ QR)\n"
            "• TrueMoney Wallet (ทรูมันนี่ วอลเล็ท)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💱 *ငွေလဲနှုန်း:* ပြင်ပပေါက်ဈေးအတိုင်း တိကျမှန်ကန်စွာ တွက်ချက်လက်ခံပေးပါသည်ခင်ဗျာ။\n\n"
            "👉 ငွေသွင်းရန် အကောင့်နံပါတ် သို့မဟုတ် ငွေထုတ်ယူလိုပါက Admin ထံ တိုက်ရိုက် ဆက်သွယ်ပါခင်ဗျာ!"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ငွေသွင်း/ငွေထုတ်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(deposit_text, parse_mode="Markdown", reply_markup=inline_kb)

    # ငွေလက်ကျန် (MMK & THB နှစ်မျိုးလုံး ဖော်ပြသည်)
    elif text in ["💵 ငွေလက်ကျန် (ยอดเงิน)", "💵 ငွေလက်ကျန်"]:
        bal = user_balances.get(user_id, {"mmk": 0, "thb": 0})
        balance_text = (
            "💵 *သင့် လက်ကျန်ငွေစာရင်း (ยอดเงินคงเหลือ)*:\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *အသုံးပြုသူ ID:* `{user_id}`\n\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal.get('mmk', 0):,} MMK (ကျပ်)`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal.get('thb', 0):,} THB (บาท)`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 *ငွေဖြည့်သွင်းလိုပါက:*\n"
            "KPay, WavePay သို့မဟုတ် Thai Bank, PromptPay တို့ဖြင့် ငွေလွှဲပြီး Admin ထံ ဆက်သွယ်၍ လက်ကျန်ငွေ ဖြည့်သွင်းနိုင်ပါသည်ခင်ဗျာ။"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin ထံ လက်ကျန်ငွေဖြည့်ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(balance_text, parse_mode="Markdown", reply_markup=inline_kb)

    # Admin Account ခလုတ်
    elif text == "👩💻 Admin Account":
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် စကားပြောရန်", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("📧 Email တိုက်ရိုက် ပို့ရန်", url=f"mailto:{ADMIN_EMAIL}")]
        ])
        msg = (
            "👇 *Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန် (ติดต่อแอดมิน)* 👇\n\n"
            f"👤 *Admin Telegram:* @{ADMIN_USERNAME}\n"
            f"📧 *Admin Email:* `{ADMIN_EMAIL}`\n\n"
            "🇲🇲 မြန်မာစကား နှင့် 🇹🇭 ภาษาไทย နှစ်မျိုးလုံးဖြင့် နွေးထွေးစွာ ဆက်သွယ်မေးမြန်းနိုင်ပါသည်ခင်ဗျာ။"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_kb)

    # ထိုးထားသော စာရင်းများ
    elif text in ["📜 ထိုးထားသော စာရင်းများ", "📜 ထိုးခဲ့သော မှတ်တမ်းများ"]:
        bets = user_bets.get(user_id, [])
        if not bets:
            await update.message.reply_text(
                "📜 *ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါခင်ဗျာ။*\n"
                "(ยังไม่มีรายการแทงในระบบ)\n\n"
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
                    thb_lines.append(f"• {b['type']} 【 `{b['number']}` 】 = `{b['amount']} ဘတ်` (ပေါက်: `{b['payout']:,} THB`)")
                    total_thb += b["amount"]
                else:
                    mmk_lines.append(f"• {b['type']} 【 `{b['number']}` 】 = `{b['amount']:,} ကျပ်` (ပေါက်: `{b['payout']:,} Ks`)")
                    total_mmk += b["amount"]

            history_msg = (
                f"📜 *သင် ထိုးထားသော စာရင်းများ (ประวัติการแทงของคุณ)*\n"
                f"📅 *ရက်စွဲ:* `{now_str}`\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )

            if mmk_lines:
                history_msg += "🇲🇲 *မြန်မာကျပ်ငွေ ထိုးစာရင်းများ:*\n" + "\n".join(mmk_lines) + f"\n👉 စုစုပေါင်း MMK: `{total_mmk:,} ကျပ်`\n\n"
            if thb_lines:
                history_msg += "🇹🇭 *ထိုင်းဘတ်ငွေ ထိုးစာရင်းများ (บาท):*\n" + "\n".join(thb_lines) + f"\n👉 စုစုပေါင်း THB: `{total_thb:,} ဘတ်`\n\n"

            history_msg += "━━━━━━━━━━━━━━━━━━━━\nဆုကြေးငွေ ထုတ်ယူရန် Admin ထံ ဆက်သွယ်ပါခင်ဗျာ!"
            inline_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Admin ထံ စာရင်းအတည်ပြုရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
            ])
            await update.message.reply_text(history_msg, parse_mode="Markdown", reply_markup=inline_kb)

    elif text == "🏠 Home":
        await update.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ပြန်လည်ရောက်ရှိပါပြီခင်ဗျာ။", reply_markup=get_main_menu())

    # User က ထီထိုးသည့် Format စာရိုက်ပို့ခြင်း (ဥပမာ - 45=500 သို့မဟုတ် 45=20B သို့မဟုတ် 789=50ဘတ်)
    elif "=" in text:
        bet_pattern = re.compile(r'(\d{2,3})\s*=\s*(\d+)\s*([a-zA-Z\u1000-\u109F\u0E00-\u0E7F]*)')
        matches = bet_pattern.findall(text)

        if matches:
            tz_mm = timezone(timedelta(hours=6, minutes=30))
            now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")

            recorded_list = []
            sub_total_mmk = 0
            sub_total_thb = 0

            for num, amt_str, curr_str in matches:
                amt = int(amt_str)
                curr_clean = curr_str.lower().strip()
                # ထိုင်းဘတ် အခေါ်အဝေါ်များ စစ်ဆေးခြင်း
                is_thb = curr_clean in ['b', 'baht', 'thb', 'ဘတ်', 'บาท', 'บ']

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
                    "time": now_str
                }
                user_bets.setdefault(user_id, []).append(record)
                recorded_list.append(record)

            if recorded_list:
                confirm_msg = (
                    "✅ *ထီထိုးသွင်းမှု အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ*\n"
                    "🎉 *บันทึกการแทงสำเร็จเรียบร้อยแล้ว!*\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                )
                for r in recorded_list:
                    rate_str = "1:90" if (r["currency"] == "THB" and r["type"] == "2D") else ("1:900" if r["currency"] == "THB" else ("1:85" if r["type"] == "2D" else "1:700"))
                    confirm_msg += f"• *{r['type']}:* 【 `{r['number']}` 】 ➔ `{r['amount']:,} {r['unit']}` (ဆုကြေး: `{r['payout']:,} {r['unit']}` [{rate_str}])\n"

                confirm_msg += "━━━━━━━━━━━━━━━━━━━━\n"
                if sub_total_mmk > 0:
                    confirm_msg += f"🇲🇲 စုစုပေါင်း မြန်မာကျပ်: `{sub_total_mmk:,} ကျပ်`\n"
                if sub_total_thb > 0:
                    confirm_msg += f"🇹🇭 စုစုပေါင်း ထိုင်းဘတ်: `{sub_total_thb:,} ဘတ်`\n"

                confirm_msg += (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ *ငွေလွှဲပြေစာ အတည်ပြုရန်:*\n"
                    "ငွေလွှဲ Slip ပြေစာအား Admin ထံ ပေးပို့အတည်ပြုပေးပါခင်ဗျာ။\n"
                    "(กรุณาส่งสลิปโอนเงินให้แอดมินเพื่อยืนยันรายการ)"
                )
                inline_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ငွေလွှဲပြေစာ ပို့ရန်", url=f"https://t.me/{ADMIN_USERNAME}")]
                ])
                await update.message.reply_text(confirm_msg, parse_mode="Markdown", reply_markup=inline_kb)
                return

        # Matches မရှိပါက format မှားယွင်းကြောင်း အသိပေးခြင်း
        await update.message.reply_text(
            "⚠️ ထိုးသည့် Format မှားယွင်းနေပါသည် ခင်ဗျာ။\n\n"
            "👉 မြန်မာကျပ်: `45=500`\n"
            "👉 ထိုင်းဘတ်: `45=20B` (သို့မဟုတ် `45=20ဘတ်`)\n"
            "👉 3D ထိုးရန်: `789=1000` (သို့မဟုတ် `789=50B`)\n"
            "ကျေးဇူးပြု၍ ပြန်လည် စာရိုက်ပို့ပေးပါခင်ဗျာ!"
        )

    # User က ဂဏန်း ၂ လုံး ရိုက်ပို့ပါက ပေါက်/မပေါက် အလိုအလျောက် စစ်ဆေးပေးခြင်း
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
                "ထွက်ဂဏန်း ထွက်ပေါ်လာချိန်မှသာ ပြန်လည် တိုက်ဆိုင်စစ်ဆေးပေးပါမည်ခင်ဗျာ!\n"
                "(รอผลออกรางวัล)"
            )
        elif text in valid_twods:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "🎉 ဂုဏ်ယူပါသည်! ယနေ့ ပေါက်ဂဏန်းနှင့် တိုက်ဆိုင်ပါသည်! 💰✨\n"
                "ยินดีด้วย! ถูกรางวัลหวย 2D 🎉\n"
                "ဆုငွေ ထုတ်ယူရန် Admin ထံ ချက်ချင်း ဆက်သွယ်ပါခင်ဗျာ။"
            )
        else:
            await update.message.reply_text(
                f"🎯 ဂဏန်း 【 {text} 】 အား စစ်ဆေးချက်:\n\n"
                "❌ ယနေ့ထွက်ရှိထားသော ပေါက်ဂဏန်းများနှင့် မတိုက်ဆိုင်သေးပါခင်ဗျာ။\n"
                "နောက်ပွဲများတွင် ကံကောင်းပါစေခင်ဗျာ! 🍀\n"
                "(ไม่ถูกรางวัล ขอให้โชคดีในงวดถัดไป)"
            )

# ==================== CALLBACK QUERY HANDLER ====================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "refresh_2d":
        msg = format_2d_message()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh အသစ်ရယူရန်", callback_data="refresh_2d")]])
        try:
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
            await query.answer("🔄 2D အချက်အလက်များ အသစ်ရယူပြီးပါပြီ!")
        except Exception:
            await query.answer("✅ နောက်ဆုံးရ အချက်အလက်အတိုင်း ဖြစ်ပါသည်")

# ==================== MAIN APPLICATION ====================

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
    print("🚀 Myanmar & Thai 2D/3D Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling(drop_pending_updates=True)
