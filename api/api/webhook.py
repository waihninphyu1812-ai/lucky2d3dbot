import os
import json
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI"
ADMIN_CHAT_ID = "1533228735"

def send_telegram(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=6)
    except Exception as e:
        print("Telegram Send Error:", e)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            update = json.loads(body.decode('utf-8'))

            # ၁။ Message သို့မဟုတ် Mini App Data လာသည့်အခါ
            if "message" in update:
                msg = update["message"]
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                # Mini App (ထိုးမယ်) မှ ဘောက်ချာဒေတာ ပေးပို့လာခြင်း
                if "web_app_data" in msg:
                    data = json.loads(msg["web_app_data"]["data"])
                    action = data.get("action")
                    
                    if action == "submit_bet":
                        # အသုံးပြုသူထံ ပြန်စာပို့ခြင်း
                        send_telegram(
                            chat_id, 
                            f"✅ *ထိုးငွေ အတည်ပြုပြီးပါပြီ!*\n🎫 ဘောက်ချာနံပါတ်: `{data.get('ticket_id')}`\n💵 စုစုပေါင်း: {data.get('total_amount')} ကျပ်/ဘတ်"
                        )
                        # Admin ထံ စာရင်းချက်ချင်းပို့ခြင်း
                        admin_msg = (
                            f"🔔 *ထီထိုးစာရင်း အသစ် ရောက်ရှိပါသည်!*\n\n"
                            f"👤 အမည်: `{data.get('user_name')}` (ID: `{data.get('user_id')}`)\n"
                            f"🎯 အမျိုးအစား: {data.get('type')}\n"
                            f"💵 ထိုးကြေး: {data.get('total_amount')}\n"
                            f"📌 ဘောက်ချာ: `{data.get('ticket_id')}`"
                        )
                        send_telegram(ADMIN_CHAT_ID, admin_msg)

                # /start နှိပ်သည့်အခါ
                elif text == "/start":
                    welcome = (
                        "🇲🇲 *မြန်မာ ၂လုံး / ၃လုံး တရားဝင် Bot မှ ကြိုဆိုပါသည်!*\n\n"
                        "🎯 ၂လုံး / ၃လုံး ထိုးရန် အောက်ပါ *'🎯 ထိုးမယ်'* ခလုတ်ကို နှိပ်၍ Mini App တွင် လွယ်ကူစွာ ထိုးနိုင်ပါသည်ခင်ဗျာ။"
                    )
                    kb = {
                        "inline_keyboard": [
                            [{"text": "🎯 ထိုးမယ် (Mini App ဖွင့်ရန်)", "web_app": {"url": "https://lucky2d3dbot.vercel.app"}}]
                        ]
                    }
                    send_telegram(chat_id, welcome, reply_markup=kb)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode('utf-8'))
        except Exception as e:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode('utf-8'))
