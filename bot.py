import os
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Render Cloud Web Server (Port 10000 အတွက်)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write("Myanmar 2D/3D Telegram Bot Running Live 24/7!".encode('utf-8'))

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

# Bot Token & Admin အချက်အလက်များ
TOKEN = '8988776248:AAFj84YUTvHfWXjH-Mc4fPgbkx-MjR6ytG8'
ADMIN_USERNAME = "Sno78"
ADMIN_EMAIL = "waihninphyu1812@gmail.com"

def get_main_menu():
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သော မှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ မြန်မာ 2D/3D စနစ်မှ ကြိုဆိုပါသည် ✨\n\nမိမိ ပြုလုပ်လိုသည်ကို ရွေးချယ်ပါ-",
        reply_markup=get_main_menu()
    )

def is_2d_open():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    if now.weekday() in [5, 6]:
        return False, "📅 ယနေ့သည် 2D ပိတ်ရက် ဖြစ်ပါသဖြင့် အသုံးပြု၍မရနိုင်ပါ ❌"
    return True, "ဖွင့်လှစ်ထားပါသည်"

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🎯 2D ထိုး":
        is_open, msg = is_2d_open()
        if not is_open:
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("🎯 2D ထိုးရန် Format:\nဂဏန်း=ငွေပမာဏ (ဥပမာ - 45=500)")
    elif text == "👩💻 Admin Account":
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Telegram ဖြင့် တိုက်ရိုက် စကားပြောရန်", url=f"https://t.me/{ADMIN_USERNAME}")],
            [InlineKeyboardButton("📧 Email တိုက်ရိုက် ပို့ရန်", url=f"mailto:{ADMIN_EMAIL}")]
        ])
        msg = (
            "👇 *Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန်* 👇\n\n"
            f"👤 *Admin Telegram:* @{ADMIN_USERNAME}\n"
            f"📧 *Admin Email:* `{ADMIN_EMAIL}`\n\n"
            "အောက်ပါ ခလုတ်များကို နှိပ်ပြီး တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ။"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=inline_kb)
    elif text == "💵 ငွေလက်ကျန်":
        await update.message.reply_text("💵 သင့်လက်ကျန်ငွေ: 0 ကျပ်")
    elif text == "💰 ငွေသွင်း/ငွေထုတ်":
        await update.message.reply_text("ငွေသွင်း/ငွေထုတ် ပြုလုပ်ရန် Admin ကို ဆက်သွယ်ပါခင်ဗျာ။")
    elif text == "🎯 3D ထိုး":
        await update.message.reply_text("🎯 3D ထိုးရန် Format:\nဂဏန်း=ငွေပမာဏ (ဥပမာ - 789=1000)")
    elif text == "📜 ထိုးခဲ့သော မှတ်တမ်းများ":
        await update.message.reply_text("📜 ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါ။")
    elif text == "🏆 ထီပေါက်စဉ်":
        await update.message.reply_text("🏆 ယနေ့ ထွက်ဂဏန်းများကို စောင့်ကြည့်နေပါသည်...")
    elif text == "🎮 Game ဆော့ရန်":
        await update.message.reply_text("🎮 ဂိမ်းကဏ္ဍကို မကြာမီ မိတ်ဆက်ပေးပါမည်။")
    elif text == "🏠 Home":
        await update.message.reply_text("🏠 ပင်မစာမျက်နှာသို့ ရောက်ရှိနေပါပြီ။", reply_markup=get_main_menu())

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))
    print("🚀 Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    app.run_polling(drop_pending_updates=True)
