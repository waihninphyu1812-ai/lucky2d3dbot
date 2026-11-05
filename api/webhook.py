import os
import json
import urllib.request
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler

TOKEN = os.environ.get("BOT_TOKEN", "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI").strip()
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 1533228735))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "noenoeslotagency").lstrip("@")
ADMIN_URL = f"https://t.me/{ADMIN_USERNAME}"
MINI_APP_URL = os.environ.get("MINI_APP_URL", "https://lucky2d3dbot.vercel.app").rstrip("/")

PAYMENT_ACCOUNTS = {
    "kpay": {
        "title": "KBZPay (KPay)",
        "name": "Ma Moe Thu Zar",
        "number": "09766646412",
        "currency": "MMK",
        "qr": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=09766646412"
    },
    "promptpay": {
        "title": "PromptPay (Prove Pay)",
        "name": "MR.AUNG MYAT TUN",
        "number": "0816404238",
        "currency": "THB",
        "qr": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=0816404238"
    }
}

# Telegram ပင်မ Home Menu ခလုတ် ၉ ခု
HOME_KEYBOARD = {
    "keyboard": [
        [
            {"text": "📱 2D/3D Live App ဖွင့်မည်", "web_app": {"url": MINI_APP_URL}},
            {"text": "📊 2D တိုက်ရိုက်ကြည့်မည်"}
        ],
        [
            {"text": "🎲 3D ထွက်ဂဏန်းများ"},
            {"text": "💳 ငွေသွင်းရန် (Top Up)"}
        ],
        [
            {"text": "💰 ငွေထုတ်ရန် (Withdraw)"},
            {"text": "🎰 Lucky Spin (ကံစမ်းမဲ)", "web_app": {"url": MINI_APP_URL}}
        ],
        [
            {"text": "📜 ထိုးထားသော စာရင်းများ"},
            {"text": "ℹ️ အကူအညီနှင့် စည်းကမ်းများ"}
        ],
        [
            {"text": "💬 Admin ဆက်သွယ်ရန်"}
        ]
    ],
    "resize_keyboard": True,
    "persistent": True
}

def tg_api_call(method, payload):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"Telegram API Error ({method}): {e}")
        return None

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_api_call("sendMessage", payload)

def fetch_2d_summary():
    try:
        req = urllib.request.Request("https://api.thaistock2d.com/live", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as res:
            d = json.loads(res.read().decode("utf-8"))
            live = d.get("live", {})
            m1201 = "--"
            e1630 = "--"
            for item in d.get("result", []):
                t = str(item.get("open_time", ""))
                v = str(item.get("twod", "--"))
                if "12:01" in t: m1201 = v
                elif "16:30" in t: e1630 = v
            tz_mm = timezone(timedelta(hours=6, minutes=30))
            now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M:%S %p")
            return (
                f"📊 <b>ထိုင်းစတော့ (SET) 2D Live တိုက်ရိုက်ရလဒ်</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🕒 အချိန်: <code>{now_str}</code> (မြန်မာစံတော်ချိန်)\n\n"
                f"🟢 <b>Live 2D:</b>  <code>{live.get('twod', '--')}</code>\n"
                f"📈 <b>SET Index:</b> <code>{live.get('set', '--')}</code>\n"
                f"💵 <b>Value:</b> <code>{live.get('val', live.get('value', '--'))}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"☀️ <b>မနက် (12:01):</b> <code>{m1201}</code>\n"
                f"🌆 <b>ညနေ (04:30):</b> <code>{e1630}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Mini App တွင် စက္ကန့်မလပ် Live ကြည့်ရှုနိုင်ပါသည်!</i>"
            )
    except Exception:
        return "📊 <b>ထိုင်းစတော့ (SET) 2D တိုက်ရိုက်ရလဒ်</b>\nလိုင်းချိတ်ဆက်နေပါသည်..."

def get_deposit_text():
    k = PAYMENT_ACCOUNTS["kpay"]
    p = PAYMENT_ACCOUNTS["promptpay"]
    return (
        "💳 <b>ငွေသွင်းရန် တရားဝင် အကောင့်များ (Deposit Accounts)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔵 <b>{k['title']}</b>\n"
        f"• အကောင့်အမည်: <b>{k['name']}</b>\n"
        f"• အကောင့်နံပါတ်: <code>{k['number']}</code>\n\n"
        f"🇹🇭 <b>{p['title']}</b>\n"
        f"• အကောင့်အမည်: <b>{p['name']}</b>\n"
        f"• အကောင့်နံပါတ်: <code>{p['number']}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ ငွေလွှဲပြီးပါက ပြေစာအား Admin ထံ ပေးပို့ပေးပါခင်ဗျာ!"
    )

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"status": "ok", "message": "Telegram Webhook Active"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            update = json.loads(post_data)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

        if "message" in update:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            user_name = msg.get("from", {}).get("first_name", "မိတ်ဆွေ")
            text = msg.get("text", "").strip()

            if not chat_id:
                return

            if text.startswith("/start"):
                welcome = (
                    f"👋 မင်္ဂလာပါ <b>{user_name}</b> ခင်ဗျာ!\n\n"
                    f"🎰 <b>Myanmar 2D/3D Live Official Bot</b> မှ ကြိုဆိုပါသည်!\n\n"
                    f"🎁 <b>Lucky Wheel Spin:</b> နေ့စဉ် ကံစမ်းမဲ လှည့်ပြီး ဆုကြေးငွေများ ရယူလိုက်ပါ!\n\n"
                    f"အောက်ပါ Menu ခလုတ်များမှတစ်ဆင့် အလွယ်တကူ အသုံးပြုနိုင်ပါပြီခင်ဗျာ 👇"
                )
                app_inline = {
                    "inline_keyboard": [
                        [{"text": "🚀 2D/3D Live App ဖွင့်မည်", "web_app": {"url": MINI_APP_URL}}],
                        [{"text": "💬 Admin ဆက်သွယ်ရန်", "url": ADMIN_URL}]
                    ]
                }
                send_message(chat_id, welcome, reply_markup=HOME_KEYBOARD)
                send_message(chat_id, "✨ <b>Live Mini App ကို အောက်ပါခလုတ်မှ ဖွင့်ပါ:</b>", reply_markup=app_inline)

            elif "2D တိုက်ရိုက်ကြည့်မည်" in text:
                send_message(chat_id, fetch_2d_summary())
            elif "3D ထွက်ဂဏန်းများ" in text:
                send_message(chat_id, "🎲 <b>ထိုင်းအစိုးရ (GLO) 3D</b>\nဆုကြီး: <code>423224</code> | 3D: <code>224</code>")
            elif "ငွေသွင်းရန်" in text:
                send_message(chat_id, get_deposit_text())
            elif "ငွေထုတ်ရန်" in text:
                send_message(chat_id, f"💰 <b>ငွေထုတ်ယူရန်</b>\nသင်၏ Telegram ID: <code>{chat_id}</code>\nထုတ်ယူလိုပါက Admin ({ADMIN_URL}) ထံ ဆက်သွယ်ပါခင်ဗျာ။")
            elif "ထိုးထားသော စာရင်းများ" in text:
                send_message(chat_id, "📜 <b>ထိုးထားသော စာရင်းများ:</b>\nMini App ၏ 'မှတ်တမ်း' ကဏ္ဍတွင် အချိန်မရွေး ကြည့်ရှုနိုင်ပါသည်ခင်ဗျာ!")
            elif "အကူအညီနှင့် စည်းကမ်းများ" in text:
                send_message(chat_id, f"ℹ️ <b>စည်းကမ်းများ:</b>\n2D ပေါက်ကြေး: 85~90 ဆ\n3D ပေါက်ကြေး: 500~700 ဆ\nAdmin: @{ADMIN_USERNAME}")
            elif "Admin ဆက်သွယ်ရန်" in text:
                send_message(chat_id, f"💬 Admin ထံ ဆက်သွယ်ရန်: {ADMIN_URL}")
            else:
                send_message(chat_id, "အောက်ပါ Menu မှ လိုရာကို ရွေးချယ်နိုင်ပါသည်ခင်ဗျာ 👇", reply_markup=HOME_KEYBOARD)
