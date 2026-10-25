import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# BotFather ဆီက ရထားတဲ့ Token ကို ဒီမှာ အစားထိုးပါ
TOKEN = '8988776248:AAFj84YUTvHfWXjH-Mc4fPgbkx-MjR6ytG8'

# သင့်ရဲ့ Telegram Username (@ မပါဘဲ ထည့်ပါ)
ADMIN_USERNAME = "lucky2d3d_mm_bot"

def get_main_menu():
    keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သော မှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩‍💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🏠 Home")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = get_main_menu()
    await update.message.reply_text(
        "✨ မြန်မာ 2D/3D စနစ်မှ ကြိုဆိုပါသည် ✨\n\nမိမိ ပြုလုပ်လိုသည်ကို ရွေးချယ်ပါ-",
        reply_markup=reply_markup
    )

def is_2d_open():
    tz = pytz.timezone('Asia/Yangon')
    now = datetime.datetime.now(tz)
    if now.weekday() in [5, 6]: # စနေ၊ တနင်္ဂနွေ ပိတ်သည်
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

    elif text == "👩‍💻 Admin Account":
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
        ])
        await update.message.reply_text(
            "👇 Admin နဲ့ တိုက်ရိုက်ဆက်သွယ်ရန် 👇",
            reply_markup=inline_kb
        )

    elif text == "💵 ငွေလက်ကျန်":
        await update.message.reply_text("💵 သင့်လက်ကျန်ငွေ: 0 ကျပ်")

    elif text == "💰 ငွေသွင်း/ငွေထုတ်":
        await update.message.reply_text("ငွေသွင်း/ငွေထုတ် ပြုလုပ်ရန် Admin ကို ဆက်သွယ်ပါခင်ဗျာ။")

    elif text == "🎯 3D ထိုး":
        await update.message.reply_text("🎯 3D ထိုးရန် Format:\nဂဏန်း=ငွေပမာဏ (ဥပမာ - 789=1000)")

    elif text == "📜 ထိုးခဲ့သော မှတ်တမ်းများ":
        await update.message.reply_text("📜 ယခုပွဲအတွက် ထိုးထားသော စာရင်းများ မရှိသေးပါ။")

    elif text == "🏆 ထီပေါက်စဉ်"
