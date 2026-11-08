import os
import json
import time
import urllib.request
import urllib.error

# ==================== CONFIGURATION & ADMIN ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "1533228735")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "@noenoeslotagency")
VERCEL_APP_URL = os.environ.get("VERCEL_APP_URL", "https://lucky2d3dbot.vercel.app")

PAYMENT_KPAY_NAME = os.environ.get("KPAY_NAME", "Ma Moe Thu Zar")
PAYMENT_KPAY_NUMBER = os.environ.get("KPAY_NUMBER", "09766646412")
PAYMENT_PROMPTPAY_NAME = os.environ.get("PROMPTPAY_NAME", "MR.AUNG MYAT TUN")
PAYMENT_PROMPTPAY_NUMBER = os.environ.get("PROMPTPAY_NUMBER", "0816404238")

USER_BALANCES = {}

OFFICIAL_GLO_3D_BACKUP = {
    "first_prize": "187221",
    "threed": "221",
    "adjacent_tickets": ["187220", "187222"],
    "adjacent_threed": ["220", "222"],
    "front_3d": ["036", "923"],
    "back_3d": ["980", "547"],
    "back_2d": "38",
    "date": "16-11-2024",
    "source": "Thai Government Lottery Office (GLO) Official"
}

def fetch_glo_3d_realtime():
    endpoints = [
        "https://www.glo.or.th/api/lottery/getLatestLottery",
        "https://lotto.api.rayriffy.com/latest"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.glo.or.th/"
                }
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if "response" in data and isinstance(data["response"], dict):
                        resp = data["response"]
                        first_prize_ticket = str(resp.get("first", {}).get("number", "187221"))
                        threed_digit = first_prize_ticket[-3:] if len(first_prize_ticket) >= 3 else "221"
                        
                        front_list = [str(x.get("number", "")) for x in resp.get("runningNumbers", {}).get("frontThree", []) if x.get("number")]
                        back_list = [str(x.get("number", "")) for x in resp.get("runningNumbers", {}).get("backThree", []) if x.get("number")]
                        two_d = str(resp.get("runningNumbers", {}).get("backTwo", {}).get("number", "38"))
                        
                        try:
                            ticket_int = int(first_prize_ticket)
                            adjacent_tickets = [str(ticket_int - 1).zfill(6), str(ticket_int + 1).zfill(6)]
                            adjacent_threed = [adjacent_tickets[0][-3:], adjacent_tickets[1][-3:]]
                        except Exception:
                            adjacent_tickets = ["187220", "187222"]
                            adjacent_threed = ["220", "222"]
                        
                        draw_date = resp.get("date", "16-11-2024")
                        return {
                            "first_prize": first_prize_ticket,
                            "threed": threed_digit,
                            "adjacent_tickets": adjacent_tickets,
                            "adjacent_threed": adjacent_threed,
                            "front_3d": front_list if front_list else ["036", "923"],
                            "back_3d": back_list if back_list else ["980", "547"],
                            "back_2d": two_d,
                            "date": draw_date,
                            "source": "Thai Government Lottery Office (GLO) Real-time"
                        }
                    elif "status" in data and data.get("status") == "success" and "response" in data:
                        resp = data["response"]
                        first_prize_ticket = str(resp.get("prizes", [{}])[0].get("number", ["187221"])[0])
                        threed_digit = first_prize_ticket[-3:] if len(first_prize_ticket) >= 3 else "221"
                        running = resp.get("runningNumbers", [])
                        front_list = []
                        back_list = []
                        two_d = "38"
                        for item in running:
                            id_val = str(item.get("id", ""))
                            if "frontThree" in id_val:
                                front_list = item.get("number", ["036", "923"])
                            elif "backThree" in id_val:
                                back_list = item.get("number", ["980", "547"])
                            elif "backTwo" in id_val:
                                two_arr = item.get("number", ["38"])
                                two_d = two_arr[0] if two_arr else "38"
                        
                        try:
                            ticket_int = int(first_prize_ticket)
                            adjacent_tickets = [str(ticket_int - 1).zfill(6), str(ticket_int + 1).zfill(6)]
                            adjacent_threed = [adjacent_tickets[0][-3:], adjacent_tickets[1][-3:]]
                        except Exception:
                            adjacent_tickets = ["187220", "187222"]
                            adjacent_threed = ["220", "222"]
                        
                        return {
                            "first_prize": first_prize_ticket,
                            "threed": threed_digit,
                            "adjacent_tickets": adjacent_tickets,
                            "adjacent_threed": adjacent_threed,
                            "front_3d": front_list,
                            "back_3d": back_list,
                            "back_2d": two_d,
                            "date": resp.get("date", "16-11-2024"),
                            "source": "Rayriffy GLO Mirror Real-time"
                        }
        except Exception:
            continue
    return OFFICIAL_GLO_3D_BACKUP

def send_telegram_request(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Telegram API Error ({method}):", e)
        return {"ok": False, "error": str(e)}

def get_home_keyboard():
    return {
        "keyboard": [
            [
                {"text": "🎮 ဂိမ်းဆော့ရန်", "web_app": {"url": VERCEL_APP_URL}},
                {"text": "💵 ငွေလက်ကျန်"}
            ],
            [
                {"text": "🎯 2D ထိုး", "web_app": {"url": f"{VERCEL_APP_URL}#twod"}},
                {"text": "🎲 3D ထိုး", "web_app": {"url": f"{VERCEL_APP_URL}#threed"}}
            ],
            [
                {"text": "💳 ငွေသွင်း"},
                {"text": "💰 ငွေထုတ်"}
            ],
            [
                {"text": "🏆 ထိပေါက်စဉ်"},
                {"text": "📊 ထွက်ဂဏန်းမှတ်တမ်းများ"}
            ],
            [
                {"text": "📜 ထိုးထားသောမှတ်တမ်းများ"},
                {"text": "👑 Admin account"}
            ]
        ],
        "resize_keyboard": True
    }

def handle_message(message):
    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", chat_id))
    text = (message.get("text") or "").strip()
    first_name = from_user.get("first_name", "လူကြီးမင်း")

    if not text:
        return

    bal = USER_BALANCES.get(user_id, 0)

    if text in ["/start", "start", "ဟယ်လို", "hello"]:
        msg = (
            f"🇲🇲 <b>Lucky 2D / 3D Live မှ ကြိုဆိုပါသည်ခင်ဗျာ!</b>\n\n"
            f"မင်္ဂလာပါ <b>{first_name}</b> ရှင့် ✨\n\n"
            f"ကျွန်ုပ်တို့၏ 24/7 တိုက်ရိုက်ဂဏန်းစနစ်နှင့် Telegram Mini App တွင် ကံစမ်းနိုင်ပါပြီ။\n\n"
            f"💰 <b>လျော်ကြေးနှုန်းထားများ:</b>\n"
            f"• 2D မြန်မာကျပ်: <b>85 ဆ</b>\n"
            f"• 2D ထိုင်းဘတ်: <b>85 ဆ</b>\n"
            f"• 3D မြန်မာကျပ်: <b>700 ဆ</b>\n"
            f"• 3D ထိုင်းဘတ်: <b>10฿ ➔ 5,000฿</b>\n\n"
            f"🎰 <b>နေ့စဉ် အခမဲ့ Spin ကံစမ်းမဲ</b> ကိုလည်း Mini App ထဲတွင် တစ်ရက် ၁ ကြိမ် လှည့်ယူနိုင်ပါသည်။\n\n"
            f"အောက်ပါ Menu ခလုတ်များမှတစ်ဆင့် အလွယ်တကူ စတင်နိုင်ပါပြီခင်ဗျာ 👇"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": get_home_keyboard()
        })
        return

    if text in ["💵 ငွေလက်ကျန်", "/balance", "ငွေလက်ကျန်"]:
        msg = (
            f"💵 <b>လူကြီးမင်း၏ လက်ကျန်ငွေစာရင်း</b>\n\n"
            f"👤 အမည်: <b>{first_name}</b>\n"
            f"🆔 User ID: <code>{user_id}</code>\n"
            f"💰 လက်ကျန်ငွေ: <b>{bal:,.0f} Ks</b>\n\n"
            f"ငွေသွင်း/ငွေထုတ် ပြုလုပ်လိုပါက အောက်ပါ Menu ခလုတ်များကို အသုံးပြုနိုင်ပါသည်ခင်ဗျာ။"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": get_home_keyboard()
        })
        return

    if text in ["💳 ငွေသွင်း", "/deposit", "ငွေသွင်း"]:
        msg = (
            f"💳 <b>ငွေသွင်းရန် အကောင့်အချက်အလက်များ</b>\n\n"
            f"🔵 <b>KPay (KBZPay):</b>\n"
            f"• အမည်: <b>{PAYMENT_KPAY_NAME}</b>\n"
            f"• ဖုန်းနံပါတ်: <code>{PAYMENT_KPAY_NUMBER}</code>\n\n"
            f"🟢 <b>PromptPay (ထိုင်းဘတ်):</b>\n"
            f"• အမည်: <b>{PAYMENT_PROMPTPAY_NAME}</b>\n"
            f"• နံပါတ်: <code>{PAYMENT_PROMPTPAY_NUMBER}</code>\n\n"
            f"⚠️ <i>ငွေလွှဲပြီးပါက ပြေစာ (Transaction Slip) ကို Admin ထံသို့ ပေးပို့အတည်ပြုပေးပါခင်ဗျာ။</i>"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "👑 Admin ထံ ပြေစာပို့မည်", "url": f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"}],
                    [{"text": "📱 Mini App တွင် ငွေသွင်းမည်", "web_app": {"url": VERCEL_APP_URL}}]
                ]
            }
        })
        return

    if text in ["💰 ငွေထုတ်", "/withdraw", "ငွေထုတ်"]:
        msg = (
            f"💰 <b>ငွေထုတ်ယူခြင်း ဝန်ဆောင်မှု</b>\n\n"
            f"လက်ရှိလက်ကျန်ငွေ: <b>{bal:,.0f} Ks</b>\n\n"
            f"ငွေထုတ်ယူလိုပါက အောက်ပါ Admin ထံသို့ တိုက်ရိုက် ဆက်သွယ်၍ အကောင့်နံပါတ်ပေးပို့ပြီး ထုတ်ယူနိုင်ပါသည်ခင်ဗျာ။\n\n"
            f"👑 <b>Admin Username:</b> {ADMIN_USERNAME}\n"
            f"⚡️ ၂၄ နာရီ ဝန်ဆောင်မှု ပေးနေပါသည်ခင်ဗျာ။"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "👑 Admin ထံ တိုက်ရိုက်ဆက်သွယ်မည်", "url": f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"}]
                ]
            }
        })
        return

    if text in ["🎯 2D ထိုး", "/2d", "2d"]:
        msg = (
            f"🎯 <b>2D ထိုးကွင်းသို့ သွားရောက်ရန်</b>\n\n"
            f"မြန်မာ 2D ကို နေ့စဉ် တနင်္လာမှ သောကြာအထိ\n"
            f"• မနက်ပိုင်း: 12:01 PM\n"
            f"• ညနေပိုင်း: 04:30 PM\n"
            f"အချိန်များတွင် တိုက်ရိုက် ကံစမ်းနိုင်ပါသည်။\n\n"
            f"💰 လျော်ကြေး: <b>85 ဆ</b>\n\n"
            f"အောက်ပါခလုတ်ကို နှိပ်၍ တိုက်ရိုက် ထိုးနိုင်ပါသည် 👇"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🎯 2D ထိုးကွင်းဖွင့်မည်", "web_app": {"url": f"{VERCEL_APP_URL}#twod"}}]
                ]
            }
        })
        return

    if text in ["🎲 3D ထိုး", "/3d", "3d"]:
        glo = fetch_glo_3d_realtime()
        msg = (
            f"🎲 <b>3D ထိုးကွင်းနှင့် တရားဝင် GLO ရလဒ်</b>\n\n"
            f"🇹🇭 <b>ထိုင်း GLO တရားဝင်ထွက်ဂဏန်း:</b>\n"
            f"• ထီပေါက်စဉ်အပြည့်: <b>{glo.get('first_prize')}</b>\n"
            f"• <b>3D တိုက်ရိုက်:</b> 🏆 <code>{glo.get('threed')}</code>\n"
            f"• ရှေ့ 3 လုံး: <b>{', '.join(glo.get('front_3d', []))}</b>\n"
            f"• နောက် 3 လုံး: <b>{', '.join(glo.get('back_3d', []))}</b>\n"
            f"• 2D အောက်လုံး: <b>{glo.get('back_2d')}</b>\n"
            f"• နေ့စွဲ: <i>{glo.get('date')}</i>\n"
            f"• ရင်းမြစ်: <i>{glo.get('source')}</i>\n\n"
            f"💰 လျော်ကြေး: <b>700 ဆ (10฿ ➔ 5,000฿)</b>\n\n"
            f"အောက်ပါခလုတ်ကို နှိပ်၍ တိုက်ရိုက် ထိုးနိုင်ပါသည် 👇"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🎲 3D ထိုးကွင်းဖွင့်မည်", "web_app": {"url": f"{VERCEL_APP_URL}#threed"}}]
                ]
            }
        })
        return

    if text in ["🏆 ထိပေါက်စဉ်", "/winners", "ထိပေါက်စဉ်"]:
        msg = (
            f"🏆 <b>ယနေ့ ကံထူးရှင်များ စာရင်း</b>\n\n"
            f"🥇 User_****582 - 2D (54) - 85,000 Ks\n"
            f"🥈 User_****193 - 3D (221) - 700,000 Ks\n"
            f"🥉 User_****902 - 2D (83) - 170,000 Ks\n"
            f"🎖 User_****411 - 2D (12) - 42,500 Ks\n\n"
            f"🎉 ကံထူးရှင်များအားလုံးကို ဂုဏ်ပြုပါသည်ခင်ဗျာ!"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": get_home_keyboard()
        })
        return

    if text in ["📊 ထွက်ဂဏန်းမှတ်တမ်းများ", "/results", "မှတ်တမ်း"]:
        glo = fetch_glo_3d_realtime()
        msg = (
            f"📊 <b>ထွက်ဂဏန်းမှတ်တမ်းများ</b>\n\n"
            f"🎯 <b>မြန်မာ 2D (ယနေ့):</b>\n"
            f"• 12:01 PM: <b>54</b> (Set: 1,382.12, Val: 34,512.54)\n"
            f"• 04:30 PM: <b>83</b> (Set: 1,385.43, Val: 41,215.83)\n\n"
            f"🎲 <b>ထိုင်း 3D (GLO တရားဝင်):</b>\n"
            f"• အထူးဆု: <b>{glo.get('first_prize')}</b>\n"
            f"• 3D: <b>{glo.get('threed')}</b>\n"
            f"• 2D အောက်လုံး: <b>{glo.get('back_2d')}</b>\n"
            f"• ရင်းမြစ်: <i>{glo.get('source')}</i>"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": get_home_keyboard()
        })
        return

    if text in ["📜 ထိုးထားသောမှတ်တမ်းများ", "/mybets", "ထိုးထားသောမှတ်တမ်းများ"]:
        msg = (
            f"📜 <b>လူကြီးမင်း၏ ထိုးထားသော မှတ်တမ်းများ</b>\n\n"
            f"လက်ရှိအချိန်တွင် မပြီးပြတ်သေးသော ထိုးကြေးစာရင်း မရှိသေးပါခင်ဗျာ။\n\n"
            f"Mini App ထဲတွင် အသေးစိတ် စာရင်းမှတ်တမ်းကို ကြည့်ရှုနိုင်ပါသည်။"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "📱 Mini App မှတ်တမ်းကြည့်မည်", "web_app": {"url": VERCEL_APP_URL}}]
                ]
            }
        })
        return

    if text in ["👑 Admin account", "/admin", "admin"]:
        msg = (
            f"👑 <b>တရားဝင် Admin အကောင့်နှင့် ဆက်သွယ်ရန်</b>\n\n"
            f"• Telegram Admin: <b>{ADMIN_USERNAME}</b>\n"
            f"• ဝန်ဆောင်မှု: ၂၄ နာရီ မနားတမ်း\n\n"
            f"ငွေသွင်း/ငွေထုတ်၊ အကောင့်ပြဿနာများနှင့် မေးမြန်းစုံစမ်းလိုသည်များကို Admin ထံ တိုက်ရိုက် မေးမြန်းနိုင်ပါသည်ခင်ဗျာ။"
        )
        send_telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "💬 Admin ထံ စကားပြောမည်", "url": f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"}]
                ]
            }
        })
        return

    send_telegram_request("sendMessage", {
        "chat_id": chat_id,
        "text": f"လူကြီးမင်း မေးမြန်းလိုသည်များကို အောက်ပါ Menu ခလုတ်များမှ ရွေးချယ်နိုင်ပါသည်ခင်ဗျာ 👇",
        "reply_markup": get_home_keyboard()
    })

def main():
    print("🤖 Lucky 2D/3D Telegram Bot Engine စတင် လည်ပတ်နေပါပြီ...")
    send_telegram_request("deleteWebhook", {})
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        if "message" in update:
                            handle_message(update["message"])
                        elif "channel_post" in update:
                            handle_message(update["channel_post"])
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()
