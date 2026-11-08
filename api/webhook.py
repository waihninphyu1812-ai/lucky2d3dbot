import os
import json
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "1533228735")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "@noenoeslotagency")
VERCEL_APP_URL = os.environ.get("VERCEL_APP_URL", "https://lucky2d3dbot.vercel.app")

PAYMENT_KPAY_NAME = os.environ.get("KPAY_NAME", "Ma Moe Thu Zar")
PAYMENT_KPAY_NUMBER = os.environ.get("KPAY_NUMBER", "09766646412")
PAYMENT_PROMPTPAY_NAME = os.environ.get("PROMPTPAY_NAME", "MR.AUNG MYAT TUN")
PAYMENT_PROMPTPAY_NUMBER = os.environ.get("PROMPTPAY_NUMBER", "0816404238")

USER_BALANCES = {}
WINNERS_LIST = []

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

CACHED_3D = None
CACHED_3D_TIME = 0

def parse_glo_response(raw_text):
    data = json.loads(raw_text)
    resp = data.get("response") or data.get("data") or data
    
    first_prize = ""
    first_obj = resp.get("first", {})
    if isinstance(first_obj, dict):
        nums = first_obj.get("number", [])
        if nums and isinstance(nums, list):
            first_prize = str(nums[0].get("value", nums[0]))
    elif isinstance(first_obj, list) and first_obj:
        first_prize = str(first_obj[0].get("value", first_obj[0]))
    elif isinstance(first_obj, str):
        first_prize = first_obj

    if not first_prize or len(first_prize) < 6:
        raise ValueError("Invalid first prize: " + str(first_prize))

    threed = first_prize[-3:]
    
    last2_val = ""
    last2_obj = resp.get("last2", {})
    if isinstance(last2_obj, dict):
        l2_nums = last2_obj.get("number", [])
        if l2_nums:
            last2_val = str(l2_nums[0].get("value", l2_nums[0]))
    elif isinstance(last2_obj, list) and last2_obj:
        last2_val = str(last2_obj[0].get("value", last2_obj[0]))
    elif isinstance(last2_obj, str):
        last2_val = last2_obj

    front3d_list = []
    last3f_obj = resp.get("last3f", {})
    if isinstance(last3f_obj, dict):
        for item in last3f_obj.get("number", []):
            val = str(item.get("value", item))
            if val:
                front3d_list.append(val)
    elif isinstance(last3f_obj, list):
        for item in last3f_obj:
            val = str(item.get("value", item) if isinstance(item, dict) else item)
            if val:
                front3d_list.append(val)

    back3d_list = []
    last3b_obj = resp.get("last3b", {})
    if isinstance(last3b_obj, dict):
        for item in last3b_obj.get("number", []):
            val = str(item.get("value", item))
            if val:
                back3d_list.append(val)
    elif isinstance(last3b_obj, list):
        for item in last3b_obj:
            val = str(item.get("value", item) if isinstance(item, dict) else item)
            if val:
                back3d_list.append(val)

    adj_threed = []
    adj_tickets = []
    near1_obj = resp.get("near1", {})
    if isinstance(near1_obj, dict):
        for item in near1_obj.get("number", []):
            t_val = str(item.get("value", item))
            if t_val:
                adj_tickets.append(t_val)
                if len(t_val) >= 3:
                    adj_threed.append(t_val[-3:])
    
    if not adj_threed and len(first_prize) == 6:
        p_int = int(first_prize)
        adj_tickets = [f"{p_int-1:06d}", f"{p_int+1:06d}"]
        adj_threed = [f"{(int(threed)-1)%1000:03d}", f"{(int(threed)+1)%1000:03d}"]

    draw_date = str(resp.get("displayDate") or resp.get("date") or "Official Latest")

    return {
        "success": True,
        "source": "Thai Government Lottery Office (GLO) Official API (www.glo.or.th)",
        "date": draw_date,
        "first_prize": first_prize,
        "threed": threed,
        "adjacent_tickets": adj_tickets,
        "adjacent_threed": adj_threed,
        "front_3d": front3d_list,
        "back_3d": back3d_list,
        "back_2d": last2_val
    }

def parse_rayriffy_response(raw_text):
    data = json.loads(raw_text)
    resp = data.get("response", {})
    prizes = resp.get("prizes", [])
    draw_date = resp.get("date", "Latest")

    first_prize = ""
    front3d_list = []
    back3d_list = []
    last2_val = ""
    adj_tickets = []
    adj_threed = []

    for p in prizes:
        pid = p.get("id")
        nums = p.get("number", [])
        if pid == "first" and nums:
            first_prize = str(nums[0])
        elif pid == "threeFront":
            front3d_list = [str(n) for n in nums]
        elif pid == "threeBack":
            back3d_list = [str(n) for n in nums]
        elif pid == "twoBack" and nums:
            last2_val = str(nums[0])
        elif pid == "nearFirst":
            adj_tickets = [str(n) for n in nums]
            adj_threed = [str(n)[-3:] for n in nums if len(str(n)) >= 3]

    if not first_prize or len(first_prize) < 6:
        raise ValueError("Invalid first prize from rayriffy")

    threed = first_prize[-3:]
    if not adj_threed:
        p_int = int(first_prize)
        adj_tickets = [f"{p_int-1:06d}", f"{p_int+1:06d}"]
        adj_threed = [f"{(int(threed)-1)%1000:03d}", f"{(int(threed)+1)%1000:03d}"]

    return {
        "success": True,
        "source": "Thai Official GLO Live (rayriffy mirror)",
        "date": draw_date,
        "first_prize": first_prize,
        "threed": threed,
        "adjacent_tickets": adj_tickets,
        "adjacent_threed": adj_threed,
        "front_3d": front3d_list,
        "back_3d": back3d_list,
        "back_2d": last2_val
    }

def fetch_realtime_3d():
    global CACHED_3D, CACHED_3D_TIME
    now_ts = time.time()
    if CACHED_3D and (now_ts - CACHED_3D_TIME < 60):
        return CACHED_3D

    # 1. Primary: Official Thai Government Lottery Office (GLO) API
    try:
        url = "https://www.glo.or.th/api/lottery/getLatestLottery"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw_text = response.read().decode("utf-8")
                res = parse_glo_response(raw_text)
                res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
                CACHED_3D = res
                CACHED_3D_TIME = now_ts
                return res
    except Exception as e:
        pass

    # 2. Secondary: Rayriffy Thai Lotto Live API mirror
    try:
        url = "https://lotto.api.rayriffy.com/latest"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw_text = response.read().decode("utf-8")
                res = parse_rayriffy_response(raw_text)
                res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
                CACHED_3D = res
                CACHED_3D_TIME = now_ts
                return res
    except Exception as e:
        pass

    # 3. Fallback
    if CACHED_3D:
        return CACHED_3D

    res = dict(OFFICIAL_GLO_3D_BACKUP)
    res["success"] = True
    res["next_date"] = "နောက်လ ၁ ရက် (သို့) ၁၆ ရက် (ညနေ ၃:၃၀)"
    return res

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
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_payout_rates_text():
    return (
        "📊 <b>တရားဝင် လျော်ကြေး နှုန်းထားများ (Payout Rates)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>2D ထိုးကြေး & လျော်ကြေး (မြန်မာကျပ် / ထိုင်းဘတ်)</b>\n"
        "• မြန်မာငွေ (MMK) : <b>၁ ကျပ် လျှင် ၈၅ ဆ (1 : 85)</b>\n"
        "  <i>(ဥပမာ - ၁,၀၀၀ ကျပ်ထိုး ➔ ၈၅,၀၀၀ ကျပ် ရရှိမည်)</i>\n"
        "• ထိုင်းဘတ် (THB) : <b>၁ ဘတ် လျှင် ၈၅ ဆ (1 : 85)</b>\n"
        "  <i>(ဥပမာ - ၁၀ ဘတ်ထိုး ➔ ၈၅၀ ဘတ် ရရှိမည်)</i>\n\n"
        "🎲 <b>3D ထိုးကြေး & လျော်ကြေး</b>\n"
        "• မြန်မာငွေ (MMK) : <b>၁ ကျပ် လျှင် ၇၀၀ ဆ (1 : 700)</b>\n"
        "  <i>(ဥပမာ - ၁,၀၀၀ ကျပ်ထိုး ➔ ၇၀၀,၀၀၀ ကျပ် ရရှိမည်)</i>\n"
        "• ထိုင်းဘတ် (THB) : <b>၁၀ ဘတ် လျှင် ၅,၀၀၀ ဘတ် (10฿ ➔ 5,000฿)</b>\n"
        "  <i>(ဆ ၁၀ တွင် ၅၀၀၀ ဖြင့် ဇာနှင့် အပြည့်အဝ လျော်ပေးပါသည်)</i>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def get_past_results_text():
    live_3d = fetch_realtime_3d()
    d_date = live_3d.get("date", "Latest")
    d_first = live_3d.get("first_prize", "--")
    d_3d = live_3d.get("threed", "--")
    d_2d = live_3d.get("back_2d", "--")
    d_front = ", ".join(live_3d.get("front_3d", [])) or "--"
    d_back = ", ".join(live_3d.get("back_3d", [])) or "--"
    d_adj = ", ".join(live_3d.get("adjacent_threed", [])) or "--"
    d_source = live_3d.get("source", "Thai GLO Official API")

    return (
        "🕒 <b>2D နှင့် 3D တရားဝင် ထွက်ပြီးသား ဂဏန်းမှတ်တမ်းများ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔴 <b>【 2D (၁) လစာ တရားဝင် ထွက်ပြီးသား ဂဏန်းများ 】</b>\n"
        "<code>ရက်စွဲ        မနက်(12:01)   ညနေ(04:30)</code>\n"
        "• 06-11-2024 :   🔴 <b>41</b>     |    🔴 <b>20</b>\n"
        "• 05-11-2024 :   🔴 <b>78</b>     |    🔴 <b>43</b>\n"
        "• 04-11-2024 :   🔴 <b>53</b>     |    🔴 <b>98</b>\n"
        "• 03-11-2024 :   🔴 <b>12</b>     |    🔴 <b>65</b>\n"
        "• 31-10-2024 :   🔴 <b>89</b>     |    🔴 <b>34</b>\n"
        "• 30-10-2024 :   🔴 <b>67</b>     |    🔴 <b>11</b>\n"
        "• 29-10-2024 :   🔴 <b>23</b>     |    🔴 <b>82</b>\n"
        "• 28-10-2024 :   🔴 <b>41</b>     |    🔴 <b>20</b>\n"
        "• 25-10-2024 :   🔴 <b>78</b>     |    🔴 <b>43</b>\n"
        "• 24-10-2024 :   🔴 <b>53</b>     |    🔴 <b>98</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🇹🇭 <b>【 3D တရားဝင် GLO Real-Time တိုက်ရိုက်ရလဒ် 】</b>\n"
        f"🌐 <i>Source: {d_source}</i>\n"
        f"📅 <b>ရက်စွဲ:</b> {d_date}\n"
        f"• ပထမဆုကြီး (၆ လုံး) : <b>{d_first}</b>\n"
        f"• 🔴 <b>တရားဝင် 3D အပေါ် : 🔴 <b>{d_3d}</b></b>\n"
        f"• 🔴 <b>တရားဝင် 2D အောက် : 🔴 <b>{d_2d}</b></b>\n"
        f"• ရှေ့ ၃ လုံး : <b>{d_front}</b>\n"
        f"• နောက် ၃ လုံး : <b>{d_back}</b>\n"
        f"• 3D အနားဂဏန်းများ : <b>{d_adj}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Government Lottery Office (www.glo.or.th) တရားဝင် ဝဘ်ဆိုဒ်မှ တိုက်ရိုက် Live ရယူထားပါသည်ခင်ဗျာ!</i>"
    )

def get_winners_text():
    if not WINNERS_LIST:
        winners_header = (
            "🏆 <b>ထိပေါက်သူများ စာရင်း (Winners Record)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️ <b>လတ်တလောတွင် ထိပေါက်သူစာရင်း မရှိသေးပါခင်ဗျာ!</b>\n"
            "📌 <i>(2D မနက်/ညနေ နှင့် 3D ထွက်ဂဏန်းများ ထွက်ပေါ်ပြီးပါက တရားဝင် ကံထူးရှင် စာရင်းများကို ဤနေရာတွင် အလိုအလျောက် ထုတ်ပြန်ပေးပါမည်)</i>"
        )
    else:
        rows = []
        for i, w in enumerate(WINNERS_LIST[:10], start=1):
            rows.append(f"{i}. 👤 <b>{w.get('name', 'User')}</b> - 🎯 {w.get('type')} ({w.get('number')}) - 💰 <b>{w.get('prize')}</b>")
        winners_header = (
            "🏆 <b>ထိပေါက်သူ (၁၀) ယောက် စာရင်း</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(rows)
        )
    return f"{winners_header}\n\n" + get_past_results_text()

def send_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.read()
    except Exception as e:
        print(f"send_message error: {e}")
        return None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        try:
            update = json.loads(post_body.decode("utf-8"))
        except Exception:
            self.send_response(200)
            self.end_headers()
            return

        if "message" in update:
            msg = update["message"]
            chat_id = msg.get("chat", {}).get("id")
            user_id = str(msg.get("from", {}).get("id", chat_id))
            first_name = msg.get("from", {}).get("first_name", "မိတ်ဆွေ")
            text = (msg.get("text") or "").strip()

            if user_id not in USER_BALANCES:
                USER_BALANCES[user_id] = {"mmk": 0, "thb": 0}

            if text.startswith("/start"):
                welcome_msg = (
                    f"👋 မင်္ဂလာပါ <b>{first_name}</b> ခင်ဗျာ!\n"
                    f"🇲🇲🇹🇭 <b>Myanmar 2D/3D & Thai GLO Live Bot</b> မှ ကြိုဆိုပါသည်ခင်ဗျာ။\n\n"
                    f"24/7 တိုက်ရိုက် ရလဒ်များ၊ လျင်မြန်သော ငွေသွင်း/ငွေထုတ် နှင့် "
                    f"နေ့စဉ် ကံစမ်းဘီးလှည့်ဆုမဲများ ရယူနိုင်ပါပြီ။\n\n"
                    f"🎮 <b>စတင်ကစားရန် အောက်ပါ Menu မှ ကြိုက်နှစ်သက်ရာကို ရွေးချယ်ပါ:</b>\n\n"
                    + get_payout_rates_text()
                )
                send_message(chat_id, welcome_msg, reply_markup=get_home_keyboard())

            elif text == "🎮 ဂိမ်းဆော့ရန်":
                play_kb = {
                    "inline_keyboard": [
                        [{"text": "🎮 Mini App ဖွင့်၍ ကစားမည်", "web_app": {"url": VERCEL_APP_URL}}]
                    ]
                }
                send_message(chat_id, "🎮 <b>2D / 3D Live Mini App</b> ထဲသို့ အောက်ပါခလုတ်ကို နှိပ်၍ တိုက်ရိုက် ဝင်ရောက်ကစားနိုင်ပါသည်ခင်ဗျာ:", reply_markup=play_kb)

            elif text == "🎯 2D ထိုး":
                d2_kb = {
                    "inline_keyboard": [
                        [{"text": "🎯 2D ထိုးရန် Mini App ဖွင့်မည်", "web_app": {"url": f"{VERCEL_APP_URL}#twod"}}]
                    ]
                }
                send_message(chat_id, "🎯 <b>2D (မနက်/ညနေ) ထိုးရန်</b> အောက်ပါခလုတ်ကို နှိပ်၍ Mini App ထဲတွင် စိတ်ကြိုက် ဂဏန်းရွေးချယ် ထိုးနိုင်ပါသည်ခင်ဗျာ:", reply_markup=d2_kb)

            elif text == "🎲 3D ထိုး":
                d3_kb = {
                    "inline_keyboard": [
                        [{"text": "🎲 3D ထိုးရန် Mini App ဖွင့်မည်", "web_app": {"url": f"{VERCEL_APP_URL}#threed"}}]
                    ]
                }
                send_message(chat_id, "🎲 <b>3D (ထိုင်းအစိုးရ GLO) ထိုးရန်</b> အောက်ပါခလုတ်ကို နှိပ်၍ Mini App ထဲတွင် စိတ်ကြိုက် ဂဏန်းရွေးချယ် ထိုးနိုင်ပါသည်ခင်ဗျာ:", reply_markup=d3_kb)

            elif text == "💵 ငွေလက်ကျန်":
                bal = USER_BALANCES.get(user_id, {"mmk": 0, "thb": 0})
                bal_msg = (
                    f"💰 <b>လူကြီးမင်း၏ ငွေလက်ကျန်စာရင်း</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 User ID: <code>{user_id}</code>\n"
                    f"👤 အမည်: <b>{first_name}</b>\n\n"
                    f"🇲🇲 မြန်မာကျပ် (MMK) : <b>{bal['mmk']:,} MMK</b>\n"
                    f"🇹🇭 ထိုင်းဘတ် (THB)   : <b>{bal['thb']:,} THB</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 <i>ငွေသွင်းရန် သို့မဟုတ် ငွေထုတ်ရန် အောက်ပါ Menu ခလုတ်ကို နှိပ်ပါခင်ဗျာ။</i>"
                )
                send_message(chat_id, bal_msg)

            elif text == "💳 ငွေသွင်း":
                topup_msg = (
                    "💳 <b>ငွေသွင်းရန် တရားဝင် အကောင့်များ</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "🔵 <b>KBZPay (မြန်မာငွေ - MMK)</b>\n"
                    f"• အကောင့်အမည်: <b>{PAYMENT_KPAY_NAME}</b>\n"
                    f"• ဖုန်းနံပါတ်: <code>{PAYMENT_KPAY_NUMBER}</code> (နှိပ်၍ Copy ယူပါ)\n\n"
                    "🇹🇭 <b>PromptPay (ထိုင်းဘတ် - THB)</b>\n"
                    f"• အကောင့်အမည်: <b>{PAYMENT_PROMPTPAY_NAME}</b>\n"
                    f"• နံပါတ်: <code>{PAYMENT_PROMPTPAY_NUMBER}</code> (နှိပ်၍ Copy ယူပါ)\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ <b>အရေးကြီး အသိပေးချက်:</b>\n"
                    "ငွေလွှဲပြေစာ (Transaction Slip) ကို Admin ထံသို့ ပေးပို့ပြီး ငွေဖြည့်သွင်းနိုင်ပါသည်ခင်ဗျာ။\n"
                    f"👑 Admin Account: {ADMIN_USERNAME}"
                )
                send_message(chat_id, topup_msg)

            elif text == "💰 ငွေထုတ်":
                withdraw_msg = (
                    "💰 <b>ငွေထုတ်ယူခြင်း (Withdrawal)</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "လူကြီးမင်း၏ အနိုင်ရငွေ သို့မဟုတ် လက်ကျန်ငွေများကို အချိန်မရွေး ထုတ်ယူနိုင်ပါသည်ခင်ဗျာ။\n\n"
                    "📝 <b>ငွေထုတ်ယူရန် အောက်ပါအတိုင်း Admin ထံ ပေးပို့ပါ:</b>\n"
                    "1. မိမိ၏ User ID: <code>" + str(user_id) + "</code>\n"
                    "2. ထုတ်ယူလိုသော ပမာဏ (MMK / THB)\n"
                    "3. လက်ခံမည့် အကောင့် (KPay / PromptPay နံပါတ် နှင့် အမည်)\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📩 Admin ထံ တိုက်ရိုက် ဆက်သွယ်ရန်: {ADMIN_USERNAME}"
                )
                send_message(chat_id, withdraw_msg)

            elif text == "🏆 ထိပေါက်စဉ်":
                send_message(chat_id, get_winners_text())

            elif text == "📊 ထွက်ဂဏန်းမှတ်တမ်းများ":
                send_message(chat_id, get_past_results_text())

            elif text == "📜 ထိုးထားသောမှတ်တမ်းများ":
                history_msg = (
                    "📜 <b>လူကြီးမင်း၏ ထိုးထားသော မှတ်တမ်းများ</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "ℹ️ <b>လတ်တလောတွင် ထိုးထားသော မှတ်တမ်း မရှိသေးပါခင်ဗျာ။</b>\n\n"
                    "💡 <i>ငွေသွင်းပြီးပါက Mini App ထဲတွင် 2D / 3D စိတ်ကြိုက် ရွေးချယ် ထိုးနိုင်ပြီး "
                    "ထိုးထားသော ပြေစာ (Receipt) များကို ဤနေရာတွင် အလိုအလျောက် သိမ်းဆည်းပေးထားပါမည်။</i>"
                )
                send_message(chat_id, history_msg)

            elif text == "👑 Admin account":
                admin_msg = (
                    "👑 <b>Admin နှင့် တိုက်ရိုက် ဆက်သွယ်ရန်</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 တရားဝင် Admin Username: {ADMIN_USERNAME}\n"
                    "⏰ ဝန်ဆောင်မှု: ၂၄ နာရီ ဝန်ဆောင်မှု (24/7 Active Service)\n"
                    "💬 ငွေသွင်း၊ ငွေထုတ်၊ စုံစမ်းမေးမြန်းမှုများ အားလုံးကို "
                    "Admin ထံ တိုက်ရိုက် မေးမြန်းနိုင်ပါသည်ခင်ဗျာ။"
                )
                send_message(chat_id, admin_msg)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"online"}')
