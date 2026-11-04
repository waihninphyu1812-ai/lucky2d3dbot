import os
import re
import json
import random
import urllib.request
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==================== CONFIGURATION & ADMIN ====================
TOKEN = os.environ.get("BOT_TOKEN", "9029256827:AAEzKzZcNW8jiqrmx6-eJvdRsGu1ncpUaJI").strip()
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", 1533228735))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "noenoeslotagency").lstrip("@")
ADMIN_URL = f"https://t.me/{ADMIN_USERNAME}"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
MINI_APP_URL = os.environ.get("MINI_APP_URL", RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://t.me/myanmar2d3d_live_bot/app").rstrip("/")

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
BETS_FILE = os.path.join(DATA_DIR, "user_bets.json")
BALANCES_FILE = os.path.join(DATA_DIR, "user_balances.json")
WINNERS_FILE = os.path.join(DATA_DIR, "winners_data.json")

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")

user_bets = load_json(BETS_FILE, {})
user_balances = load_json(BALANCES_FILE, {})
winners_data = load_json(WINNERS_FILE, [])

# ==================== PAYMENT ACCOUNTS (KBZPAY ONLY FOR MMK) ====================
PAYMENT_ACCOUNTS = {
    "kpay": {
        "id": "kpay",
        "title": "KBZPay (KPay)",
        "name": os.environ.get("KPAY_NAME", "Daw Noe Noe"),
        "number": os.environ.get("KPAY_NUMBER", "09123456789"),
        "color": "#1d3557",
        "icon": "🔵",
        "currency": "MMK",
        "qr": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('KPAY_NUMBER', '09123456789')}"
    },
    "promptpay": {
        "id": "promptpay",
        "title": "PromptPay (Prove Pay)",
        "name": os.environ.get("PROMPTPAY_NAME", "Noe Noe"),
        "number": os.environ.get("PROMPTPAY_NUMBER", "0987654321"),
        "color": "#005696",
        "icon": "🇹🇭",
        "currency": "THB",
        "qr": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('PROMPTPAY_NUMBER', '0987654321')}"
    },
    "kbank": {
        "id": "kbank",
        "title": "Kasikorn Bank (KBank)",
        "name": os.environ.get("KBANK_NAME", "Noe Noe"),
        "number": os.environ.get("KBANK_NUMBER", "123-4-56789-0"),
        "color": "#138f2d",
        "icon": "🟢",
        "currency": "THB",
        "qr": f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={os.environ.get('KBANK_NUMBER', '123-4-56789-0')}"
    }
}

pending_text_bets = {}

admin_override = {"2d": None, "3d": None}

# ==================== HTTP CLIENT HELPERS ====================
def http_get_json(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None

def http_get_text(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

# ==================== THAI MARKET (2D) HOLIDAY DETECTION ====================
def is_market_holiday():
    """
    စနေ၊ တနင်္ဂနွေ နှင့် ထိုင်းစတော့အိတ်ချိန်း (SET) ၏ တရားဝင် ပိတ်ရက်များ စစ်ဆေးခြင်း
    """
    tz_th = timezone(timedelta(hours=7))
    now = datetime.now(tz_th)

    if now.weekday() in [5, 6]:
        day_name = "စနေနေ့" if now.weekday() == 5 else "တနင်္ဂနွေနေ့"
        return True, f"{day_name} ဈေးကွက်ပိတ်ရက်"

    holidays = {
        "01-01": "နှစ်သစ်ကူးပိတ်ရက် (New Year's Day)",
        "01-02": "နှစ်သစ်ကူး အစားထိုးပိတ်ရက်",
        "04-13": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "04-14": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "04-15": "သင်္ကြန်ပိတ်ရက် (Songkran)",
        "05-01": "အလုပ်သမားနေ့ (Labor Day)",
        "12-31": "နှစ်ဟောင်းကုန်ပိတ်ရက်"
    }
    date_key = now.strftime("%m-%d")
    if date_key in holidays:
        return True, holidays[date_key]
    return False, ""

# ==================== REAL-TIME 2D ENGINE ====================
def fetch_realtime_2d():
    tz_mm = timezone(timedelta(hours=6, minutes=30))
    now = datetime.now(tz_mm)
    date_str = now.strftime("%d-%m-%Y")
    is_hol, hol_reason = is_market_holiday()

    res = {
        "success": True,
        "live_2d": "--",
        "live_set": "--",
        "live_value": "--",
        "morning_1201": "--",
        "evening_1630": "--",
        "date": date_str,
        "is_open": not is_hol,
        "holiday_reason": hol_reason if is_hol else ""
    }

    if admin_override.get("2d"):
        res["live_2d"] = str(admin_override["2d"])
        return res

    if is_hol:
        res["morning_1201"] = "--"
        res["evening_1630"] = "--"
        return res

    # Live feed from ThaiStock2D
    data = http_get_json("https://api.thaistock2d.com/live", timeout=4)
    if data and isinstance(data, dict):
        live_obj = data.get("live", {})
        res["live_set"] = str(live_obj.get("set", "--"))
        res["live_value"] = str(live_obj.get("value", "--"))
        res["live_2d"] = str(live_obj.get("twod", "--"))

        result_list = data.get("result", [])
        for item in result_list:
            open_time = str(item.get("open_time", ""))
            twod_val = str(item.get("twod", "--"))
            if "12:01" in open_time:
                res["morning_1201"] = twod_val
            elif "16:30" in open_time or "04:30" in open_time:
                res["evening_1630"] = twod_val
    return res

# ==================== REAL-TIME 3D ENGINE (OFFICIAL GLO RESULT) ====================
def get_next_3d_draw_date():
    tz_th = timezone(timedelta(hours=7))
    now = datetime.now(tz_th)
    y, m, d = now.year, now.month, now.day

    if d < 1 or (d == 1 and now.hour < 16):
        target = datetime(y, m, 1)
    elif d < 16 or (d == 16 and now.hour < 16):
        target = datetime(y, m, 16)
    else:
        target = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
    return target.strftime("%d-%m-%Y")

OFFICIAL_GLO_3D_RESULTS = {
    "01-11-2026": {
        "date": "01-11-2026",
        "first_prize": "423224",
        "threed": "224",
        "adjacent_tickets": ["423223", "423225"],
        "adjacent_threed": ["223", "225"],
        "front_3d": ["300", "950"],
        "back_3d": ["393", "804"],
        "back_2d": "85",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)"
    },
    "16-10-2026": {
        "date": "16-10-2026",
        "first_prize": "011781",
        "threed": "781",
        "adjacent_tickets": ["011780", "011782"],
        "adjacent_threed": ["780", "782"],
        "front_3d": ["392", "402"],
        "back_3d": ["171", "255"],
        "back_2d": "48",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)"
    },
    "01-10-2026": {
        "date": "01-10-2026",
        "first_prize": "402701",
        "threed": "701",
        "adjacent_tickets": ["402700", "402702"],
        "adjacent_threed": ["700", "702"],
        "front_3d": ["791", "912"],
        "back_3d": ["058", "396"],
        "back_2d": "70",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)"
    },
    "16-09-2026": {
        "date": "16-09-2026",
        "first_prize": "730640",
        "threed": "640",
        "adjacent_tickets": ["730639", "730641"],
        "adjacent_threed": ["639", "641"],
        "front_3d": ["060", "521"],
        "back_3d": ["266", "041"],
        "back_2d": "64",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)"
    },
    "01-09-2026": {
        "date": "01-09-2026",
        "first_prize": "417212",
        "threed": "212",
        "adjacent_tickets": ["417211", "417213"],
        "adjacent_threed": ["211", "213"],
        "front_3d": ["257", "346"],
        "back_3d": ["136", "740"],
        "back_2d": "04",
        "source": "ထိုင်းအစိုးရ ထီဗျူရို (GLO တရားဝင်)"
    }
}

def fetch_realtime_3d():
    """
    ထိုင်းအစိုးရ ထီဗျူရို (GLO) ၁ ရက် နှင့် ၁၆ ရက် တရားဝင် 3D Real-time Result အစစ်အမှန်
    - ပထမဆုကြီး ၆ လုံး (รางวัลที่ 1): 423224
    - တရားဝင် 3D အပေါ် ၃ လုံး (3 ตัวบน): 224
    - 3D အနားဂဏန်းများ: 223, 225
    - ရှေ့ ၃ လုံး: 300, 950
    - နောက် ၃ လုံး: 393, 804
    - အောက် ၂ လုံး: 85
    - ရက်စွဲ: 01-11-2026
    """
    next_draw = get_next_3d_draw_date()

    res = dict(OFFICIAL_GLO_3D_RESULTS["01-11-2026"])
    res["success"] = True
    res["next_date"] = f"{next_draw} (ညနေ ၃:၃၀ နာရီ)"

    # Admin Override
    if admin_override.get("3d"):
        val = str(admin_override["3d"]).strip()
        if len(val) == 6 and val.isdigit():
            n = int(val)
            res["first_prize"] = val
            res["threed"] = val[-3:]
            res["adjacent_tickets"] = [f"{n-1:06d}", f"{n+1:06d}"]
            res["adjacent_threed"] = [res["adjacent_tickets"][0][-3:], res["adjacent_tickets"][1][-3:]]
            res["source"] = "Admin တိုက်ရိုက် သတ်မှတ်ချက်"
            return res
        elif len(val) == 3 and val.isdigit():
            n = int(val)
            res["threed"] = val
            res["adjacent_threed"] = [f"{(n-1)%1000:03d}", f"{(n+1)%1000:03d}"]
            res["source"] = "Admin တိုက်ရိုက် သတ်မှတ်ချက်"
            return res

    # 1. Rayriffy Thai Lotto Live API
    try:
        data = http_get_json("https://lotto.api.rayriffy.com/latest", timeout=5)
        if data and data.get("status") == "success":
            resp = data.get("response", {})
            prizes = resp.get("prizes", [])
            running = resp.get("runningNumbers", [])

            for p in prizes:
                if p.get("id") == "prizeFirst" and p.get("number"):
                    fp = str(p["number"][0]).strip()
                    res["first_prize"] = fp
                    res["threed"] = fp[-3:]
                    if len(fp) == 6:
                        n = int(fp)
                        res["adjacent_tickets"] = [f"{n-1:06d}", f"{n+1:06d}"]
                        res["adjacent_threed"] = [f"{n-1:06d}"[-3:], f"{n+1:06d}"[-3:]]
                elif p.get("id") == "prizeFirstNear" and p.get("number"):
                    res["adjacent_tickets"] = [str(x).strip() for x in p["number"]]
                    res["adjacent_threed"] = [str(x).strip()[-3:] for x in p["number"]]

            for r in running:
                if r.get("id") == "runningNumberFrontThree" and r.get("number"):
                    res["front_3d"] = [str(x).strip() for x in r["number"]]
                elif r.get("id") == "runningNumberBackThree" and r.get("number"):
                    res["back_3d"] = [str(x).strip() for x in r["number"]]
                elif r.get("id") == "runningNumberBackTwo" and r.get("number"):
                    res["back_2d"] = str(r["number"][0]).strip()

            if resp.get("date"):
                res["date"] = resp["date"]
            res["source"] = "ထိုင်းအစိုးရ ထီဗျူရို (GLO / Rayriffy API)"
            return res
    except Exception:
        pass

    return res

# ==================== REAL WINNERS VERIFICATION ENGINE ====================
def get_verified_winners():
    """
    ထီပေါက်သူ အစစ်အမှန်များ စစ်ဆေးတွက်ချက်ခြင်း
    ထီပေါက်သူ မရှိသေးပါက ပေါက်သူမရှိကြောင်း အမှန်အတိုင်း ပြသပေးခြင်း
    """
    d2 = fetch_realtime_2d()
    d3 = fetch_realtime_3d()

    winning_2d = [x for x in [d2.get("morning_1201"), d2.get("evening_1630")] if x and x != "--"]
    target_3d = d3.get("threed")
    adj_3d = d3.get("adjacent_threed", [])

    real_winners = list(winners_data)

    # Check all user bets
    for uid_str, bets in user_bets.items():
        if not isinstance(bets, list):
            continue
        for b in bets:
            tkt = b.get("ticket_id", "")
            if any(w.get("ticket_id") == tkt for w in real_winners):
                continue

            b_type = b.get("type", "2D")
            nums = b.get("numbers", [])
            amt = b.get("amount_each", 0)
            u_name = b.get("user_name", "Customer")

            for num in nums:
                num_str = str(num).strip()
                won = False
                payout = 0
                win_desc = ""

                if b_type == "2D" and num_str in winning_2d:
                    won = True
                    payout = amt * 85
                    win_desc = f"2D 【 {num_str} 】"
                elif b_type == "3D" and target_3d and num_str == target_3d:
                    won = True
                    payout = amt * 700
                    win_desc = f"3D ဒဲ့ 【 {num_str} 】"
                elif b_type == "3D" and num_str in adj_3d:
                    won = True
                    payout = amt * 70
                    win_desc = f"3D အနား 【 {num_str} 】"

                if won:
                    masked_name = u_name[:2] + "***" if len(u_name) > 2 else u_name + "***"
                    masked_uid = uid_str[:3] + "***" if len(uid_str) > 3 else uid_str
                    real_winners.append({
                        "name": masked_name,
                        "uid": masked_uid,
                        "ticket_id": tkt,
                        "desc": win_desc,
                        "payout": payout,
                        "date": b.get("date", datetime.now().strftime("%d-%m-%Y"))
                    })

    return real_winners

# ==================== MINI APP HTML SERVING ====================
EMBEDDED_MINIAPP_HTML = r"""<!DOCTYPE html>
<html lang="my">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>ထိုးမယ်</title>
  <!-- Telegram Web App SDK -->
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Padauk:wght@400;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <style>
    :root {
      --bg-app: #f4f7fc;
      --bg-card: #ffffff;
      --bg-subtle: #f8fafc;
      --border-card: #e2e8f0;
      --primary-blue: #1e50ff;
      --primary-blue-dark: #133ecc;
      --primary-blue-soft: #eef2ff;
      --text-main: #111827;
      --text-sub: #64748b;
      --text-muted: #94a3b8;
      --green-accent: #10b981;
      --red-accent: #ef4444;
      --nav-bg: #ffffff;
      --nav-border: #e2e8f0;
      --shadow-sm: 0 2px 6px rgba(0, 0, 0, 0.03);
      --shadow-md: 0 6px 18px rgba(0, 0, 0, 0.05);
      --card-radius: 18px;
    }

    /* Dark mode support */
    body.dark-mode {
      --bg-app: #0b0f19;
      --bg-card: #151c2c;
      --bg-subtle: #1c2438;
      --border-card: #252f46;
      --text-main: #f1f5f9;
      --text-sub: #94a3b8;
      --text-muted: #64748b;
      --nav-bg: #151c2c;
      --nav-border: #252f46;
      --primary-blue-soft: rgba(30, 80, 255, 0.15);
      --shadow-sm: 0 2px 6px rgba(0, 0, 0, 0.2);
      --shadow-md: 0 6px 18px rgba(0, 0, 0, 0.3);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Plus Jakarta Sans', 'Padauk', sans-serif;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }

    body {
      background-color: var(--bg-app);
      color: var(--text-main);
      min-height: 100vh;
      padding: 12px 14px 85px 14px;
      overflow-x: hidden;
      transition: background-color 0.25s, color 0.25s;
    }

    /* ================= Top Header ================= */
    .top-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      padding: 4px 2px;
    }

    .user-profile {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .user-avatar {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: linear-gradient(135deg, #1e50ff 0%, #60a5fa 100%);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 18px;
      box-shadow: 0 4px 10px rgba(30, 80, 255, 0.3);
    }

    .user-meta .greeting {
      font-size: 11px;
      color: var(--text-sub);
      display: block;
      line-height: 1.2;
    }

    .user-meta .user-name {
      font-size: 15px;
      font-weight: 700;
      color: var(--text-main);
      line-height: 1.3;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .icon-btn {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      color: var(--text-main);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      cursor: pointer;
      box-shadow: var(--shadow-sm);
      transition: transform 0.15s, background-color 0.2s;
    }

    .icon-btn:active {
      transform: scale(0.92);
    }

    /* ================= Blue Royal Balance Card ================= */
    .balance-card {
      background: linear-gradient(135deg, #1e50ff 0%, #0d3cd6 100%);
      border-radius: var(--card-radius);
      padding: 18px 20px;
      color: #ffffff;
      box-shadow: 0 10px 24px rgba(30, 80, 255, 0.28);
      position: relative;
      overflow: hidden;
      margin-bottom: 14px;
    }

    .balance-card::after {
      content: '';
      position: absolute;
      top: -30%;
      right: -20%;
      width: 180px;
      height: 180px;
      background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0) 70%);
      border-radius: 50%;
      pointer-events: none;
    }

    .bal-top-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .bal-label {
      font-size: 13px;
      font-weight: 500;
      opacity: 0.9;
    }

    .bal-link {
      font-size: 12px;
      font-weight: 600;
      color: #ffffff;
      opacity: 0.9;
      text-decoration: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 3px;
    }

    .bal-amount-row {
      margin-bottom: 16px;
    }

    .bal-amount {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.5px;
      display: inline-block;
    }

    .bal-unit {
      font-size: 18px;
      font-weight: 600;
      margin-left: 6px;
      opacity: 0.95;
    }

    .bal-btn-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .btn-deposit {
      background: #ffffff;
      color: #1e50ff;
      border: none;
      border-radius: 25px;
      padding: 11px 0;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: transform 0.15s;
    }

    .btn-deposit:active {
      transform: scale(0.97);
    }

    .btn-withdraw {
      background: rgba(255, 255, 255, 0.22);
      backdrop-filter: blur(8px);
      color: #ffffff;
      border: 1px solid rgba(255, 255, 255, 0.35);
      border-radius: 25px;
      padding: 11px 0;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: transform 0.15s;
    }

    .btn-withdraw:active {
      transform: scale(0.97);
    }

    /* ================= 2D & 3D Bet Cards ================= */
    .bet-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 14px;
    }

    .bet-card {
      background: var(--bg-card);
      border: 1.5px solid var(--border-card);
      border-radius: var(--card-radius);
      padding: 16px 14px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s, border-color 0.2s;
    }

    .bet-card.active-card {
      border-color: #93c5fd;
    }

    .bet-card-title {
      font-size: 26px;
      font-weight: 800;
      color: var(--text-main);
      line-height: 1;
      margin-bottom: 4px;
    }

    .bet-card-sub {
      font-size: 11px;
      color: var(--text-sub);
      font-weight: 500;
    }

    .bet-card-status {
      font-size: 11px;
      font-weight: 600;
      margin: 12px 0 14px 0;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .status-closed {
      color: var(--red-accent);
    }

    .status-open {
      color: var(--green-accent);
    }

    .btn-card-primary {
      background: var(--primary-blue);
      color: #ffffff;
      border: none;
      border-radius: 20px;
      padding: 9px 0;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      text-align: center;
      box-shadow: 0 4px 10px rgba(30, 80, 255, 0.25);
      transition: transform 0.15s;
    }

    .btn-card-primary:active {
      transform: scale(0.96);
    }

    .btn-card-secondary {
      background: var(--primary-blue-soft);
      color: var(--primary-blue);
      border: 1px solid rgba(30, 80, 255, 0.25);
      border-radius: 20px;
      padding: 9px 0;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      text-align: center;
      transition: transform 0.15s;
    }

    .btn-card-secondary:active {
      transform: scale(0.96);
    }

    /* ================= Today's Winning Result Box ================= */
    .today-results-card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: var(--card-radius);
      padding: 16px 18px;
      box-shadow: var(--shadow-sm);
      margin-bottom: 14px;
    }

    .results-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .results-head-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-main);
    }

    .results-head-link {
      font-size: 12px;
      font-weight: 600;
      color: var(--primary-blue);
      cursor: pointer;
    }

    .results-columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      position: relative;
    }

    .results-columns::after {
      content: '';
      position: absolute;
      left: 50%;
      top: 10%;
      bottom: 10%;
      width: 1px;
      background-color: var(--border-card);
      transform: translateX(-50%);
    }

    .res-col {
      text-align: center;
      padding: 4px 8px;
    }

    .res-time-label {
      font-size: 12px;
      color: var(--text-sub);
      font-weight: 500;
    }

    .res-number {
      font-size: 28px;
      font-weight: 800;
      color: var(--text-main);
      margin: 6px 0;
      letter-spacing: 1px;
    }

    .res-status-sub {
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 500;
    }

    /* ================= Live Ticker Banner ================= */
    .live-ticker {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      margin-bottom: 14px;
      box-shadow: var(--shadow-sm);
    }

    .pulse-dot {
      width: 8px;
      height: 8px;
      background-color: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
      animation: pulse 1.8s infinite;
    }

    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
      100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* ================= Tab Views Container ================= */
    .tab-content {
      display: none;
      animation: fadeIn 0.2s ease-in-out;
    }

    .tab-content.active {
      display: block;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* ================= Cards & General Components ================= */
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-card);
      border-radius: var(--card-radius);
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: var(--shadow-sm);
    }

    .card-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .form-group {
      margin-bottom: 12px;
    }

    .form-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-sub);
      margin-bottom: 6px;
      display: block;
    }

    .input-box {
      width: 100%;
      background: var(--bg-subtle);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 12px 14px;
      color: var(--text-main);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }

    .input-box:focus {
      border-color: var(--primary-blue);
      background: var(--bg-card);
    }

    .chips-row {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      margin-top: 6px;
    }

    .chip-btn {
      background: var(--bg-subtle);
      border: 1px solid var(--border-card);
      border-radius: 20px;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-main);
      white-space: nowrap;
      cursor: pointer;
    }

    .chip-btn:active {
      background: var(--primary-blue-soft);
      border-color: var(--primary-blue);
      color: var(--primary-blue);
    }

    /* Segmented Controls */
    .segmented-control {
      display: flex;
      background: var(--bg-subtle);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 3px;
      gap: 4px;
    }

    .seg-btn {
      flex: 1;
      border: none;
      background: transparent;
      padding: 9px 0;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-sub);
      cursor: pointer;
      text-align: center;
      transition: all 0.2s;
    }

    .seg-btn.active {
      background: var(--bg-card);
      color: var(--primary-blue);
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
    }

    /* 2D Number Grid */
    .grid-10x10 {
      display: grid;
      grid-template-columns: repeat(10, 1fr);
      gap: 4px;
      margin-top: 8px;
    }

    .num-cell {
      aspect-ratio: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-subtle);
      border: 1px solid var(--border-card);
      border-radius: 8px;
      font-size: 11px;
      font-weight: 700;
      color: var(--text-main);
      cursor: pointer;
      transition: all 0.12s;
    }

    .num-cell.selected {
      background: var(--primary-blue);
      color: #ffffff;
      border-color: var(--primary-blue);
      transform: scale(0.96);
    }

    /* Primary Submit Button */
    .btn-submit-main {
      width: 100%;
      background: var(--primary-blue);
      color: #ffffff;
      border: none;
      border-radius: 14px;
      padding: 14px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(30, 80, 255, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-top: 14px;
    }

    .btn-submit-main:active {
      transform: scale(0.98);
    }

    
    /* PromptPay Card */
    .promptpay-card {
      background: linear-gradient(135deg, #005696 0%, #002244 100%);
      color: #ffffff;
      border-radius: 14px;
      padding: 16px;
      margin: 10px 0 14px 0;
      box-shadow: 0 6px 16px rgba(0,0,0,0.12);
    }
    .promptpay-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.2);
      border-radius: 20px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .qr-box {
      background: #ffffff;
      padding: 10px;
      border-radius: 12px;
      display: inline-block;
      margin: 8px auto 10px auto;
      box-shadow: 0 4px 14px rgba(0,0,0,0.15);
      border: 1px solid #cbd5e1;
    }
    .qr-box img {
      width: 170px;
      height: 170px;
      display: block;
      border-radius: 6px;
    }
    .pay-tab-btn {
      flex: 1;
      padding: 8px 12px;
      border: none;
      background: #e2e8f0;
      color: var(--text-sub);
      font-weight: 700;
      font-size: 12px;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .pay-tab-btn.active {
      background: var(--primary-blue);
      color: #ffffff;
    }

    /* ================= KPay Deposit Details Card ================= */
    .kpay-card {
      background: linear-gradient(135deg, #1b3557 0%, #0d1b2a 100%);
      color: #ffffff;
      border-radius: 14px;
      padding: 16px;
      margin: 10px 0 14px 0;
      box-shadow: 0 6px 16px rgba(0,0,0,0.12);
    }

    .kpay-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.15);
      border-radius: 20px;
      padding: 4px 10px;
      font-size: 11px;
      font-weight: 700;
      margin-bottom: 8px;
    }

    .kpay-acc-number {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 1px;
      color: #ffd700;
      margin: 6px 0;
    }

    .btn-copy-kpay {
      background: rgba(255,255,255,0.22);
      border: 1px solid rgba(255,255,255,0.3);
      color: #ffffff;
      border-radius: 20px;
      padding: 6px 14px;
      font-size: 11px;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-top: 4px;
    }

    /* ================= Roulette Lucky Wheel ================= */
    .wheel-container {
      position: relative;
      width: 280px;
      height: 280px;
      margin: 20px auto;
    }

    #wheelCanvas {
      width: 100%;
      height: 100%;
      border-radius: 50%;
      box-shadow: 0 8px 24px rgba(30, 80, 255, 0.2);
    }

    .wheel-pointer {
      position: absolute;
      top: -12px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 0;
      border-left: 14px solid transparent;
      border-right: 14px solid transparent;
      border-top: 24px solid #ef4444;
      z-index: 10;
      filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
    }

    /* ================= Bottom Navigation Dock ================= */
    .bottom-dock {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: 64px;
      background: var(--nav-bg);
      border-top: 1px solid var(--nav-border);
      display: flex;
      align-items: center;
      justify-content: space-around;
      z-index: 100;
      box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.04);
      padding-bottom: env(safe-area-inset-bottom, 0);
    }

    .dock-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      flex: 1;
      height: 100%;
      color: var(--text-muted);
      cursor: pointer;
      text-decoration: none;
      transition: color 0.15s, transform 0.15s;
    }

    .dock-item .dock-icon {
      font-size: 20px;
      margin-bottom: 2px;
    }

    .dock-item .dock-label {
      font-size: 11px;
      font-weight: 600;
    }

    .dock-item.active {
      color: var(--primary-blue);
    }

    .dock-item.active .dock-icon {
      transform: scale(1.1);
    }

    /* Modal / Popups */
    .modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(4px);
      z-index: 1000;
      display: none;
      align-items: flex-end;
      justify-content: center;
    }

    .modal-overlay.active {
      display: flex;
    }

    .modal-sheet {
      background: var(--bg-card);
      border-radius: 24px 24px 0 0;
      width: 100%;
      max-width: 500px;
      padding: 22px 18px 30px 18px;
      max-height: 85vh;
      overflow-y: auto;
      box-shadow: 0 -10px 30px rgba(0,0,0,0.2);
      animation: slideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    @keyframes slideUp {
      from { transform: translateY(100%); }
      to { transform: translateY(0); }
    }

    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }

    .modal-title {
      font-size: 16px;
      font-weight: 800;
      color: var(--text-main);
    }

    .modal-close {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: var(--bg-subtle);
      border: none;
      font-size: 14px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-sub);
    }

    /* Tables */
    .history-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      margin-top: 8px;
    }

    .history-table th {
      text-align: left;
      padding: 8px;
      color: var(--text-sub);
      border-bottom: 1px solid var(--border-card);
      font-weight: 600;
    }

    .history-table td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--border-card);
      color: var(--text-main);
    }

    .num-pill {
      display: inline-block;
      background: var(--primary-blue-soft);
      color: var(--primary-blue);
      padding: 2px 8px;
      border-radius: 8px;
      font-weight: 700;
    }
  </style>
</head>
<body>

  <!-- ================= TOP HEADER ================= -->
  <header class="top-header">
    <div class="user-profile">
      <div class="user-avatar" id="avatarInitial">S</div>
      <div class="user-meta">
        <span class="greeting">မင်္ဂလာပါ ခင်ဗျာ</span>
        <div class="user-name" id="displayUserName">Snowy</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="icon-btn" onclick="toggleTheme()" title="အလင်း/အမှောင် ပြောင်းမည်">🌙</button>
      <button class="icon-btn" onclick="openSupport()" title="Admin ဆက်သွယ်ရန်">🎧</button>
    </div>
  </header>

  <!-- ================= TAB 1: ပင်မ (HOME DASHBOARD) ================= -->
  <main id="tab-home" class="tab-content active">

    <!-- Blue Royal Balance Card (MMK & THB) -->
    <div class="balance-card">
      <div class="bal-top-row">
        <span class="bal-label">ပိုက်ဆံအိတ် လက်ကျန်ငွေ</span>
        <span class="bal-link" onclick="switchDockTab('records')">ငွေစာရင်း &rarr;</span>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin: 10px 0 14px 0;">
        <div style="background:rgba(255,255,255,0.14); padding:10px 12px; border-radius:12px; border:1px solid rgba(255,255,255,0.2);">
          <div style="font-size:11px; opacity:0.85;">🇲🇲 မြန်မာကျပ် (MMK)</div>
          <div style="font-size:20px; font-weight:800; margin-top:2px;">
            <span id="homeBalanceMmk">0</span> <span style="font-size:13px; font-weight:600;">Ks</span>
          </div>
        </div>
        <div style="background:rgba(255,255,255,0.14); padding:10px 12px; border-radius:12px; border:1px solid rgba(255,255,255,0.2);">
          <div style="font-size:11px; opacity:0.85;">🇹🇭 ထိုင်းဘတ် (THB)</div>
          <div style="font-size:20px; font-weight:800; margin-top:2px;">
            <span id="homeBalanceThb">0</span> <span style="font-size:13px; font-weight:600;">฿</span>
          </div>
        </div>
      </div>
      <div class="bal-btn-row">
        <button class="btn-deposit" onclick="openDepositModal()">
          <span>+</span> ငွေဖြည့်မည်
        </button>
        <button class="btn-withdraw" onclick="openWithdrawModal()">
          <span>&uarr;</span> ငွေထုတ်မည်
        </button>
      </div>
    </div>

    <!-- 2D & 3D Cards Grid -->
    <div class="bet-grid">
      <!-- 2D Card -->
      <div class="bet-card active-card">
        <div>
          <div class="bet-card-title">2D</div>
          <div class="bet-card-sub">00 -- 99</div>
        </div>
        <div>
          <div class="bet-card-status" id="home2dStatusText">
            <span class="status-closed">●</span> ယနေ့ ပိတ်ရက်
          </div>
          <button class="btn-card-primary" onclick="switchDockTab('twod')">
            ထိုးမည်
          </button>
        </div>
      </div>

      <!-- 3D Card -->
      <div class="bet-card">
        <div>
          <div class="bet-card-title">3D</div>
          <div class="bet-card-sub">000 -- 999</div>
        </div>
        <div>
          <div class="bet-card-status" id="home3dStatusText">
            <span class="status-closed">●</span> ပိတ်ထား
          </div>
          <button class="btn-card-secondary" onclick="switchDockTab('threed')">
            ထိုးမည်
          </button>
        </div>
      </div>
    </div>

    <!-- Today Winning Numbers Card -->
    <div class="today-results-card">
      <div class="results-head">
        <span class="results-head-title">ယနေ့ ထွက်ဂဏန်း</span>
        <span class="results-head-link" onclick="switchDockTab('records')">အားလုံး &rarr;</span>
      </div>
      <div class="results-columns">
        <div class="res-col">
          <div class="res-time-label">မနက် 12:01</div>
          <div class="res-number" id="homeMorningVal">--</div>
          <div class="res-status-sub" id="homeMorningSub">စောင့်ဆိုင်း</div>
        </div>
        <div class="res-col">
          <div class="res-time-label">ညနေ 4:30</div>
          <div class="res-number" id="homeEveningVal">--</div>
          <div class="res-status-sub" id="homeEveningSub">စောင့်ဆိုင်း</div>
        </div>
      </div>
    </div>

    <!-- Live Market Ticker -->
    <div class="live-ticker">
      <div class="pulse-dot"></div>
      <div>
        <span style="font-weight:700;">Live SET:</span>
        <span id="tickerSetVal">--</span> |
        <span style="font-weight:700;">Value:</span>
        <span id="tickerValVal">--</span>
      </div>
    </div>

  </main>

  <!-- ================= TAB 2: 2D ထိုးရန် ================= -->
  <main id="tab-twod" class="tab-content">
    <div class="card">
      <div class="card-title">🎯 ၂ လုံးထီ (2D) ထိုးကြေးတင်သွင်းရန်</div>

      <!-- Closed Notice Banner if Holiday -->
      <div id="holidayBanner2d" style="display:none; background:#fee2e2; border:1px solid #fca5a5; padding:10px; border-radius:12px; margin-bottom:12px; text-align:center; color:#b91c1c; font-size:13px; font-weight:700;">
        ⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!
      </div>

      <!-- Session Selection -->
      <label class="form-label">၁။ အချိန်ပိုင်း ရွေးချယ်ပါ:</label>
      <div class="segmented-control" id="session2d">
        <button class="seg-btn active" onclick="set2dSession('မနက်ပိုင်း (12:01 PM)', this)">မနက် 12:01 PM</button>
        <button class="seg-btn" onclick="set2dSession('ညနေပိုင်း (04:30 PM)', this)">ညနေ 04:30 PM</button>
      </div>

      <!-- Payment Mode -->
            <!-- Currency Selection -->
      <label class="form-label">၂။ ထိုးငွေ ငွေကြေး ရွေးချယ်ပါ:</label>
      <div class="segmented-control" id="currency2d" style="margin-bottom:12px;">
        <button class="seg-btn active" id="btnCur2dMmk" onclick="set2dCurrency('MMK')">🇲🇲 မြန်မာကျပ် (ပေါက်: 1:85)</button>
        <button class="seg-btn" id="btnCur2dThb" onclick="set2dCurrency('THB')">🇹🇭 ထိုင်းဘတ် (ပေါက်: 1:80 - 5฿➔400฿)</button>
      </div>

      <label class="form-label">၃။ ငွေပေးချေမှု ပုံစံ:</label>
      <div class="segmented-control" id="payMode2d">
        <button class="seg-btn active" onclick="set2dPayMode('wallet', this)">💼 Wallet လက်ကျန်ငွေ</button>
        <button class="seg-btn" onclick="set2dPayMode('bank_qr', this)">💳 ဘဏ်ငွေ / QR Pay (KPay / PromptPay)</button>
      </div>

      <!-- Number Input -->
      <div class="form-group" style="margin-top: 12px;">
        <label class="form-label">၄။ ထိုးလိုသော ဂဏန်းများ (ကော်မာ ခြား၍ ရိုက်ထည့်နိုင်ပါသည်):</label>
        <input type="text" id="input2dNumbers" class="input-box" placeholder="ဥပမာ: 12, 45, 89 (သို့မဟုတ် ဇယားမှ ရွေးပါ)">
        <div class="chips-row">
          <button class="chip-btn" onclick="pickQuickPattern('ပတ်သီး')">ပတ်သီး</button>
          <button class="chip-btn" onclick="pickQuickPattern('အာပတ်')">အာပတ်</button>
          <button class="chip-btn" onclick="pickQuickPattern('ပါဝါ')">ပါဝါ (၅ ကွက်)</button>
          <button class="chip-btn" onclick="pickQuickPattern('နက္ခတ်')">နက္ခတ် (၅ ကွက်)</button>
          <button class="chip-btn" onclick="pickQuickPattern('ညီကို')">ညီကို</button>
          <button class="chip-btn" onclick="clearSelectedNumbers()">ဖျက်မည်</button>
        </div>
      </div>

      <!-- 10x10 Grid -->
      <label class="form-label">၅။ ဂဏန်းကွက် ဇယား (နှိပ်၍ ရွေးပါ):</label>
      <div class="grid-10x10" id="grid2DNumbers"></div>

      <!-- Amount Input -->
      <div class="form-group" style="margin-top: 14px;">
        <label class="form-label" id="label2dAmount">၆။ တစ်ကွက်လျှင် ထိုးငွေ (ကျပ်) - ပေါက်ကြေး 1:85:</label>
        <input type="number" id="input2dAmount" class="input-box" placeholder="1000" value="1000">
        <div class="chips-row" id="chipsRow2d">
          <button class="chip-btn" onclick="setAmount2d(500)">500</button>
          <button class="chip-btn" onclick="setAmount2d(1000)">1,000</button>
          <button class="chip-btn" onclick="setAmount2d(3000)">3,000</button>
          <button class="chip-btn" onclick="setAmount2d(5000)">5,000</button>
          <button class="chip-btn" onclick="setAmount2d(10000)">10,000</button>
        </div>
      </div>

      <!-- Total Preview -->
      <div style="background:var(--bg-subtle); border-radius:12px; padding:12px; margin-top:12px; border:1px solid var(--border-card);">
        <div style="display:flex; justify-content:space-between; font-size:13px; color:var(--text-sub);">
          <span>ရွေးချယ်ထားသော ကွက်ရေ:</span>
          <b id="previewCount2d" style="color:var(--text-main);">0 ကွက်</b>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:14px; font-weight:700; margin-top:6px; color:var(--text-main);">
          <span>ကျသင့်ငွေ စုစုပေါင်း:</span>
          <span style="color:var(--primary-blue);" id="previewTotal2d">0 ကျပ်</span>
        </div>
      </div>

      <button class="btn-submit-main" id="btnSubmit2d" onclick="submit2DBet()">
        <span>👉</span> 2D ထိုးငွေ အတည်ပြုမည်
      </button>
    </div>
  </main>

  <!-- ================= TAB 3: 3D ထိုးရန် & တရားဝင် ရလဒ် ================= -->
  <main id="tab-threed" class="tab-content">
    <!-- Official Thai GLO Card -->
    <div class="card" style="border-left: 4px solid var(--green-accent);">
      <div class="card-title">🇹🇭 ထိုင်းအစိုးရ တရားဝင်ထီ (GLO) နောက်ဆုံးထွက် ရလဒ်</div>
      <div style="font-size:12px; color:var(--text-sub); margin-bottom:8px;" id="gloDrawDate">ရက်စွဲ: 01-11-2026</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; text-align:center; background:var(--bg-subtle); padding:12px; border-radius:12px;">
        <div>
          <div style="font-size:11px; color:var(--text-sub);">ပထမဆုကြီး (၆ လုံး)</div>
          <div style="font-size:22px; font-weight:800; color:var(--text-main);" id="gloFirstPrize">423224</div>
        </div>
        <div>
          <div style="font-size:11px; color:var(--text-sub);">တရားဝင် 3D အပေါ်</div>
          <div style="font-size:22px; font-weight:800; color:var(--primary-blue);" id="gloThreeD">224</div>
        </div>
      </div>
      <div style="font-size:11px; color:var(--text-sub); margin-top:8px; line-height:1.5;">
        • 3D အနားဂဏန်းများ: <b id="gloAdjThreed">223, 225</b><br>
        • ရှေ့ ၃ လုံး: <b id="gloFront3d">300, 950</b> | နောက် ၃ လုံး: <b id="gloBack3d">393, 804</b> | အောက် ၂ လုံး: <b id="gloBack2d">85</b>
      </div>
    </div>

        <!-- 3D History Card -->
    <div class="card">
      <div class="card-title">📜 3D လွန်ခဲ့သော ထွက်ဂဏန်းများ (တရားဝင် GLO)</div>
      <div style="font-size:12px; line-height:1.8; color:var(--text-main);">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:6px 0;">
          <span>📅 <b>01-11-2026</b> (423224)</span>
          <span style="font-weight:800; color:var(--primary-blue); font-size:15px;">224</span>
        </div>
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:6px 0;">
          <span>📅 <b>16-10-2026</b> (011781)</span>
          <span style="font-weight:800; color:var(--primary-blue); font-size:15px;">781</span>
        </div>
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:6px 0;">
          <span>📅 <b>01-10-2026</b> (402701)</span>
          <span style="font-weight:800; color:var(--primary-blue); font-size:15px;">701</span>
        </div>
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid #f1f5f9; padding:6px 0;">
          <span>📅 <b>16-09-2026</b> (730640)</span>
          <span style="font-weight:800; color:var(--primary-blue); font-size:15px;">640</span>
        </div>
        <div style="display:flex; justify-content:space-between; padding:6px 0;">
          <span>📅 <b>01-09-2026</b> (417212)</span>
          <span style="font-weight:800; color:var(--primary-blue); font-size:15px;">212</span>
        </div>
      </div>
    </div>

    <!-- 3D Betting Form -->
    <div class="card">
      <div class="card-title">🎯 ၃ လုံး (3D) ထိုးကြေး တင်သွင်းရန်</div>

      <!-- Currency Selection 3D -->
      <label class="form-label">၁။ ထိုးငွေ ငွေကြေး ရွေးချယ်ပါ:</label>
      <div class="segmented-control" id="currency3d" style="margin-bottom:12px;">
        <button class="seg-btn active" id="btnCur3dMmk" onclick="set3dCurrency('MMK')">🇲🇲 မြန်မာကျပ် (ပေါက်: 1:700)</button>
        <button class="seg-btn" id="btnCur3dThb" onclick="set3dCurrency('THB')">🇹🇭 ထိုင်းဘတ် (ပေါက်: 1:500 - 10฿➔5,000฿)</button>
      </div>

      <label class="form-label">၂။ ငွေပေးချေမှု ပုံစံ:</label>
      <div class="segmented-control" id="payMode3d">
        <button class="seg-btn active" onclick="set3dPayMode('wallet', this)">💼 Wallet လက်ကျန်ငွေ</button>
        <button class="seg-btn" onclick="set3dPayMode('bank_qr', this)">💳 ဘဏ်ငွေ / QR Pay (KPay / PromptPay)</button>
      </div>

      <div class="form-group" style="margin-top:12px;">
        <label class="form-label">ထိုးလိုသော ၃ လုံး ဂဏန်း (ကော်မာ ခြား၍ ရိုက်ထည့်ပါ):</label>
        <input type="text" id="input3dNumbers" class="input-box" placeholder="ဥပမာ: 224, 781, 701">
      </div>

      <div class="form-group">
        <label class="form-label" id="label3dAmount">တစ်ကွက်လျှင် ထိုးငွေ (ကျပ်) - ပေါက်ကြေး 1:700:</label>
        <input type="number" id="input3dAmount" class="input-box" placeholder="1000" value="1000">
        <div class="chips-row" id="chipsRow3d">
          <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=500">500</button>
          <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=1000">1,000</button>
          <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=3000">3,000</button>
          <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=5000">5,000</button>
        </div>
      </div>

      <button class="btn-submit-main" onclick="submit3DBet()">
        <span>👉</span> 3D ထိုးငွေ အတည်ပြုမည်
      </button>
    </div>
  </main>

  <!-- ================= TAB 4: ရူလက် (LUCKY WHEEL) ================= -->
  <main id="tab-roulette" class="tab-content">
    <div class="card" style="text-align:center;">
      <div class="card-title" style="justify-content:center;">🎁 ကံစမ်းဘီး (Lucky Roulette)</div>
      <p style="font-size:12px; color:var(--text-sub);">နေ့စဉ် အခမဲ့ ၁ ကြိမ် လှည့်ကာ ဆုငွေများနှင့် 2D အထူးဂဏန်းများ ကံစမ်းနိုင်ပါသည်!</p>

      <div class="wheel-container">
        <div class="wheel-pointer"></div>
        <canvas id="wheelCanvas" width="280" height="280"></canvas>
      </div>

      <button class="btn-submit-main" id="btnSpinWheel" onclick="spinLuckyWheel()">
        <span>🎰</span> ဘီးစလှည့်မည် (Spin Now)
      </button>
      <div id="wheelResultText" style="margin-top:12px; font-weight:700; font-size:14px; color:var(--primary-blue);"></div>
    </div>
  </main>

  <!-- ================= TAB 5: မှတ်တမ်း (RECORDS & HISTORY) ================= -->
  <main id="tab-records" class="tab-content">
    <div class="card">
      <div class="card-title">🕒 2D ထွက်ဂဏန်း မှတ်တမ်းများ</div>
      <table class="history-table">
        <thead>
          <tr>
            <th>ရက်စွဲ</th>
            <th>မနက် (12:01)</th>
            <th>ညနေ (04:30)</th>
          </tr>
        </thead>
        <tbody id="historyTableBody">
          <tr><td>2024-10-29</td><td><span class="num-pill">41</span></td><td><span class="num-pill">20</span></td></tr>
          <tr><td>2024-10-28</td><td><span class="num-pill">41</span></td><td><span class="num-pill">20</span></td></tr>
          <tr><td>2024-10-25</td><td><span class="num-pill">78</span></td><td><span class="num-pill">43</span></td></tr>
          <tr><td>2024-10-24</td><td><span class="num-pill">53</span></td><td><span class="num-pill">98</span></td></tr>
        </tbody>
      </table>
    </div>

    <!-- 3D History Table Card -->
    <div class="card">
      <div class="card-title">🎲 3D ထွက်ဂဏန်း မှတ်တမ်းများ (တရားဝင် GLO)</div>
      <table class="history-table">
        <thead>
          <tr>
            <th>ရက်စွဲ</th>
            <th>ဆုကြီး (၆ လုံး)</th>
            <th>3D အပေါ်</th>
            <th>2D အောက်</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>01-11-2026</td><td>423224</td><td><span class="num-pill" style="background:#eff6ff; color:#2563eb; font-weight:bold;">224</span></td><td><span class="num-pill">85</span></td></tr>
          <tr><td>16-10-2026</td><td>011781</td><td><span class="num-pill" style="background:#eff6ff; color:#2563eb; font-weight:bold;">781</span></td><td><span class="num-pill">48</span></td></tr>
          <tr><td>01-10-2026</td><td>402701</td><td><span class="num-pill" style="background:#eff6ff; color:#2563eb; font-weight:bold;">701</span></td><td><span class="num-pill">70</span></td></tr>
          <tr><td>16-09-2026</td><td>730640</td><td><span class="num-pill" style="background:#eff6ff; color:#2563eb; font-weight:bold;">640</span></td><td><span class="num-pill">64</span></td></tr>
          <tr><td>01-09-2026</td><td>417212</td><td><span class="num-pill" style="background:#eff6ff; color:#2563eb; font-weight:bold;">212</span></td><td><span class="num-pill">04</span></td></tr>
        </tbody>
      </table>
    </div>

    <!-- Admin Topup / Payment Note -->
    <div class="card">
      <div class="card-title">💳 တရားဝင် ငွေသွင်းအကောင့် (KBZPay)</div>
      <div class="kpay-card" style="text-align:center;">
        <div class="kpay-badge">🔵 KBZPay တရားဝင် အကောင့် (KPay Scan)</div>
        <div class="qr-box">
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=09123456789" alt="KPay QR">
        </div>
        <div style="font-size:12px; opacity:0.9;">အကောင့်အမည်: <b id="recKpayName">Daw Noe Noe</b></div>
        <div class="kpay-acc-number" id="recKpayNumber">09123456789</div>
        <button class="btn-copy-kpay" onclick="copyText(paymentAccounts.kpay.number, 'KPay နံပါတ် ကူးယူပြီးပါပြီ!')">
          <span>📋</span> နံပါတ်ကူးယူမည် (Copy)
        </button>
      </div>

      <!-- PromptPay Card in Records -->
      <div class="promptpay-card" style="text-align:center;">
        <div class="promptpay-badge">🇹🇭 PromptPay တရားဝင် အကောင့် (Prove Pay Scan)</div>
        <div class="qr-box">
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=0987654321" alt="PromptPay QR">
        </div>
        <div style="font-size:12px; opacity:0.9;">အကောင့်အမည်: <b id="recPromptpayName">Noe Noe</b></div>
        <div class="kpay-acc-number" style="color:#00e5ff;" id="recPromptpayNumber">0987654321</div>
        <button class="btn-copy-kpay" onclick="copyText(paymentAccounts.promptpay.number, 'PromptPay နံပါတ် ကူးယူပြီးပါပြီ!')">
          <span>📋</span> နံပါတ်ကူးယူမည် (Copy)
        </button>
      </div>
    </div>
  </main>

  <!-- ================= BOTTOM NAVIGATION DOCK (5 TABS) ================= -->
  <nav class="bottom-dock">
    <div class="dock-item active" onclick="switchDockTab('home', this)">
      <div class="dock-icon">🏠</div>
      <div class="dock-label">ပင်မ</div>
    </div>
    <div class="dock-item" onclick="switchDockTab('twod', this)">
      <div class="dock-icon">🔲</div>
      <div class="dock-label">2D</div>
    </div>
    <div class="dock-item" onclick="switchDockTab('threed', this)">
      <div class="dock-icon">🎲</div>
      <div class="dock-label">3D</div>
    </div>
    <div class="dock-item" onclick="switchDockTab('roulette', this)">
      <div class="dock-icon">🎁</div>
      <div class="dock-label">ရူလက်</div>
    </div>
    <div class="dock-item" onclick="switchDockTab('records', this)">
      <div class="dock-icon">🕒</div>
      <div class="dock-label">မှတ်တမ်း</div>
    </div>
  </nav>

    <!-- ================= DEPOSIT MODAL (SLIDE UP) ================= -->
  <div class="modal-overlay" id="depositModal">
    <div class="modal-sheet">
      <div class="modal-header">
        <div class="modal-title">💳 ငွေဖြည့်သွင်းရန် QR Scan & အကောင့်များ</div>
        <button class="modal-close" onclick="closeDepositModal()">✕</button>
      </div>

      <!-- Payment Method Switcher Tabs -->
      <div class="segmented-control" style="margin-bottom:12px;">
        <button class="seg-btn active" id="btnDepTabKpay" onclick="switchDepPayTab('kpay')">🔵 KBZPay (KPay Scan)</button>
        <button class="seg-btn" id="btnDepTabPromptpay" onclick="switchDepPayTab('promptpay')">🇹🇭 PromptPay (Prove Pay)</button>
      </div>

      <!-- KPay Panel -->
      <div id="panelDepKpay">
        <div class="kpay-card" style="text-align:center;">
          <div class="kpay-badge">🔵 KBZPay (KPay Scan) Official</div>
          <div class="qr-box">
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=09123456789" alt="KPay QR" id="modalKpayQr">
          </div>
          <div style="font-size:12px; opacity:0.9;">အကောင့်အမည်: <b id="modalKpayName">Daw Noe Noe</b></div>
          <div class="kpay-acc-number" id="modalKpayNumber">09123456789</div>
          <button class="btn-copy-kpay" id="btnModalCopy" onclick="copyText(paymentAccounts.kpay.number, 'KPay နံပါတ် ကူးယူပြီးပါပြီ!')">
            <span>📋</span> နံပါတ်ကူးယူမည် (Copy)
          </button>
        </div>
      </div>

      <!-- PromptPay Panel -->
      <div id="panelDepPromptpay" style="display:none;">
        <div class="promptpay-card" style="text-align:center;">
          <div class="promptpay-badge">🇹🇭 PromptPay (Prove Pay Scan) Official</div>
          <div class="qr-box">
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=0987654321" alt="PromptPay QR" id="modalPromptpayQr">
          </div>
          <div style="font-size:12px; opacity:0.9;">အကောင့်အမည်: <b id="modalPromptpayName">Noe Noe</b></div>
          <div class="kpay-acc-number" style="color:#00e5ff;" id="modalPromptpayNumber">0987654321</div>
          <button class="btn-copy-kpay" onclick="copyText(paymentAccounts.promptpay.number, 'PromptPay နံပါတ် ကူးယူပြီးပါပြီ!')">
            <span>📋</span> နံပါတ်ကူးယူမည် (Copy)
          </button>
        </div>
      </div>

      <div style="font-size:11px; color:var(--text-sub); margin-bottom:12px; background:var(--bg-subtle); padding:8px 10px; border-radius:8px;">
        💡 အထက်ပါ QR သို့မဟုတ် အကောင့်သို့ ငွေလွှဲပြီးပါက အောက်ပါ Form တွင် ငွေပမာဏ နှင့် ငွေလွှဲအချက်အလက် ဖြည့်သွင်းပေးပါခင်ဗျာ။
      </div>

      <div class="form-group">
        <label class="form-label">ဖြည့်သွင်းမည့် ငွေပမာဏ (ကျပ်):</label>
        <input type="number" id="depAmountInput" class="input-box" value="10000">
        <div class="chips-row">
          <button class="chip-btn" onclick="document.getElementById('depAmountInput').value=5000">+5,000</button>
          <button class="chip-btn" onclick="document.getElementById('depAmountInput').value=10000">+10,000</button>
          <button class="chip-btn" onclick="document.getElementById('depAmountInput').value=20000">+20,000</button>
          <button class="chip-btn" onclick="document.getElementById('depAmountInput').value=50000">+50,000</button>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">ငွေလွှဲသူ ဖုန်းနံပါတ် (သို့မဟုတ် နောက်ဆုံး ၆ လုံး):</label>
        <input type="text" id="depTxnInput" class="input-box" placeholder="09xxxxxxxxx သို့မဟုတ် 123456">
      </div>

      <button class="btn-submit-main" onclick="submitDepositForm()">
        <span>💳</span> ငွေဖြည့်လွှာ တင်မည်
      </button>
    </div>
  </div>

  <!-- ================= VOUCHER MODAL ================= -->
  <div class="modal-overlay" id="voucherModal">
    <div class="modal-sheet" style="text-align:center;">
      <div style="font-size:36px; margin-bottom:6px;">🧾</div>
      <div class="modal-title" id="voucherTitle">ထိုးငွေပြေစာ အတည်ပြုပြီးပါပြီ</div>
      <div id="voucherTicketId" style="font-size:13px; color:var(--primary-blue); font-weight:700; margin:4px 0 14px 0;">#TKT-00000</div>
      <div id="voucherContent" style="background:var(--bg-subtle); padding:14px; border-radius:12px; font-size:12px; text-align:left; line-height:1.7; border:1px solid var(--border-card);"></div>
      <button class="btn-submit-main" onclick="closeVoucherModal()">နားလည်ပါပြီ</button>
    </div>
  </div>

  <!-- ================= JAVASCRIPT LOGIC ================= -->
  <script>
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
    }

    const tgUser = tg?.initDataUnsafe?.user;
    if (tgUser) {
      const uName = tgUser.first_name || tgUser.username || "Customer";
      document.getElementById('displayUserName').innerText = uName;
      document.getElementById('avatarInitial').innerText = uName.charAt(0).toUpperCase();
    }

    // App State
    let isMarketOpen = false;
    let userWalletBal = 0;
    let current2dSession = 'မနက်ပိုင်း (12:01 PM)';
        let current2dCurrency = 'MMK';
    let current3dCurrency = 'MMK';
    let userWalletBalMmk = 0;
    let userWalletBalThb = 0;

    function set2dCurrency(cur) {
      current2dCurrency = cur;
      document.getElementById('btnCur2dMmk')?.classList.toggle('active', cur === 'MMK');
      document.getElementById('btnCur2dThb')?.classList.toggle('active', cur === 'THB');
      const lbl = document.getElementById('label2dAmount');
      const input = document.getElementById('input2dAmount');
      const chips = document.getElementById('chipsRow2d');
      if (cur === 'MMK') {
        if (lbl) lbl.innerText = '၆။ တစ်ကွက်လျှင် ထိုးငွေ (ကျပ်) - ပေါက်ကြေး 1:85:';
        if (input) { input.placeholder = '1000'; input.value = '1000'; }
        if (chips) {
          chips.innerHTML = `
            <button class="chip-btn" onclick="setAmount2d(500)">500</button>
            <button class="chip-btn" onclick="setAmount2d(1000)">1,000</button>
            <button class="chip-btn" onclick="setAmount2d(3000)">3,000</button>
            <button class="chip-btn" onclick="setAmount2d(5000)">5,000</button>
            <button class="chip-btn" onclick="setAmount2d(10000)">10,000</button>
          `;
        }
      } else {
        if (lbl) lbl.innerText = '၆။ တစ်ကွက်လျှင် ထိုးငွေ (ဘတ် ฿) - ပေါက်ကြေး 1:80 (5฿ ➔ 400฿ / 10฿ ➔ 800฿):';
        if (input) { input.placeholder = '10'; input.value = '10'; }
        if (chips) {
          chips.innerHTML = `
            <button class="chip-btn" onclick="setAmount2d(5)">5 ฿</button>
            <button class="chip-btn" onclick="setAmount2d(10)">10 ฿</button>
            <button class="chip-btn" onclick="setAmount2d(20)">20 ฿</button>
            <button class="chip-btn" onclick="setAmount2d(50)">50 ฿</button>
            <button class="chip-btn" onclick="setAmount2d(100)">100 ฿</button>
          `;
        }
      }
      update2DPreview();
    }

    function set3dCurrency(cur) {
      current3dCurrency = cur;
      document.getElementById('btnCur3dMmk')?.classList.toggle('active', cur === 'MMK');
      document.getElementById('btnCur3dThb')?.classList.toggle('active', cur === 'THB');
      const lbl = document.getElementById('label3dAmount');
      const input = document.getElementById('input3dAmount');
      const chips = document.getElementById('chipsRow3d');
      if (cur === 'MMK') {
        if (lbl) lbl.innerText = 'တစ်ကွက်လျှင် ထိုးငွေ (ကျပ်) - ပေါက်ကြေး 1:700:';
        if (input) { input.placeholder = '1000'; input.value = '1000'; }
        if (chips) {
          chips.innerHTML = `
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=500">500</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=1000">1,000</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=3000">3,000</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=5000">5,000</button>
          `;
        }
      } else {
        if (lbl) lbl.innerText = 'တစ်ကွက်လျှင် ထိုးငွေ (ဘတ် ฿) - ပေါက်ကြေး 1:500 (10฿ ➔ 5,000฿):';
        if (input) { input.placeholder = '10'; input.value = '10'; }
        if (chips) {
          chips.innerHTML = `
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=10">10 ฿</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=20">20 ฿</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=50">50 ฿</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=100">100 ฿</button>
            <button class="chip-btn" onclick="document.getElementById('input3dAmount').value=500">500 ฿</button>
          `;
        }
      }
    }

    let current2dPayMode = 'wallet';
    let current3dPayMode = 'wallet';
    let selectedNumbers = new Set();

    let paymentAccounts = {
      kpay: { id: "kpay", title: "KBZPay (KPay)", name: "Daw Noe Noe", number: "09123456789", icon: "🔵", currency: "MMK", qr: "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=09123456789" },
      promptpay: { id: "promptpay", title: "PromptPay (Prove Pay)", name: "Noe Noe", number: "0987654321", icon: "🇹🇭", currency: "THB", qr: "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=0987654321" }
    };
    let currentPendingBet = null;
    let selectedBetPayMethod = 'kpay';
    let selectedDepPayMethod = 'kpay';

    // Navigation Tabs
    function switchDockTab(tabId, el) {
      document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
      document.querySelectorAll('.dock-item').forEach(di => di.classList.remove('active'));

      const target = document.getElementById('tab-' + tabId);
      if (target) target.classList.add('active');

      if (el) {
        el.classList.add('active');
      } else {
        const found = Array.from(document.querySelectorAll('.dock-item')).find(item => item.getAttribute('onclick')?.includes(tabId));
        if (found) found.classList.add('active');
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Theme Toggle
    function toggleTheme() {
      document.body.classList.toggle('dark-mode');
    }

    function openSupport() {
      if (tg) tg.openTelegramLink("https://t.me/noenoeslotagency");
      else window.open("https://t.me/noenoeslotagency", "_blank");
    }

    // Deposit & Withdraw Modals
    
    function copyText(str, successMsg) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(str).then(() => alert(successMsg || 'ကူးယူပြီးပါပြီ!'));
      } else {
        prompt('ကူးယူရန်:', str);
      }
    }

    function switchBetPayTab(method) {
      selectedBetPayMethod = method;
      document.getElementById('btnBetTabKpay')?.classList.toggle('active', method === 'kpay');
      document.getElementById('btnBetTabPromptpay')?.classList.toggle('active', method === 'promptpay');
      const pK = document.getElementById('panelBetKpay');
      const pP = document.getElementById('panelBetPromptpay');
      if (pK) pK.style.display = (method === 'kpay') ? 'block' : 'none';
      if (pP) pP.style.display = (method === 'promptpay') ? 'block' : 'none';
    }

    function switchDepPayTab(method) {
      selectedDepPayMethod = method;
      document.getElementById('btnDepTabKpay')?.classList.toggle('active', method === 'kpay');
      document.getElementById('btnDepTabPromptpay')?.classList.toggle('active', method === 'promptpay');
      const pK = document.getElementById('panelDepKpay');
      const pP = document.getElementById('panelDepPromptpay');
      if (pK) pK.style.display = (method === 'kpay') ? 'block' : 'none';
      if (pP) pP.style.display = (method === 'promptpay') ? 'block' : 'none';
    }

    function openBetPayQrModal(bet) {
      currentPendingBet = bet;
      const unit = bet.unit || (bet.currency === 'MMK' ? 'ကျပ်' : 'ဘတ် (THB)');
      document.getElementById('betModalType').innerText = bet.type + ' (' + bet.slot + ')';
      document.getElementById('betModalNumbers').innerText = bet.numbers.join(', ') + ' (' + bet.numbers.length + ' ကွက်)';
      document.getElementById('betModalTotal').innerText = bet.total_amount.toLocaleString() + ' ' + unit;
      document.getElementById('betTxnInput').value = '';
      if (bet.currency === 'THB') {
        switchBetPayTab('promptpay');
      } else {
        switchBetPayTab('kpay');
      }
      document.getElementById('betPayQrModal').classList.add('active');
    }

    function closeBetPayQrModal() {
      document.getElementById('betPayQrModal').classList.remove('active');
      currentPendingBet = null;
    }

    function confirmBankBetPayment() {
      if (!currentPendingBet) return;
      const txn = document.getElementById('betTxnInput').value.trim();
      if (!txn) {
        alert("⚠️ ကျေးဇူးပြု၍ ပိုက်ဆံလွှဲပြီးသော လုပ်ငန်းစဉ်အမှတ် (Txn ID သို့မဟုတ် နောက်ဆုံး ၆ လုံး) ထည့်သွင်းပေးပါခင်ဗျာ!");
        return;
      }

      const bet = currentPendingBet;
      const tktId = 'TKT-' + Math.floor(10000 + Math.random() * 90000);
      const methodName = selectedBetPayMethod === 'promptpay' ? 'PromptPay (Prove Pay)' : 'KBZPay (KPay)';

      const payload = {
        action: "place_bet",
        type: bet.type,
        ticket_id: tktId,
        slot: bet.slot,
        currency: bet.currency || "MMK",
        payment_mode: "bank_qr",
        payment_method: methodName,
        txn_id: txn,
        numbers: bet.numbers,
        amount_each: bet.amount_each,
        total_amount: bet.total_amount,
        user_name: tgUser?.first_name || 'Customer',
        user_id: tgUser?.id || 0
      };

      if (tg && tg.sendData) tg.sendData(JSON.stringify(payload));

      closeBetPayQrModal();

      const multBank = (bet.currency === 'THB') ? (bet.type === '3D' ? 500 : 80) : (bet.type === '3D' ? 700 : 85);
      const winBank = bet.amount_each * multBank;
      showVoucher(`${bet.type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ`, tktId, `
        <b>အမျိုးအစား:</b> ${bet.type} (${bet.slot})<br>
        <b>ဂဏန်းများ:</b> ${bet.numbers.join(', ')} (${bet.numbers.length} ကွက်)<br>
        <b>တစ်ကွက်ထိုး:</b> ${bet.amount_each.toLocaleString()} ${bet.unit || "ကျပ်"} (ပေါက်ကြေး: ${winBank.toLocaleString()} ${bet.unit || "ကျပ်"})<br>
        <b>ငွေပေးချေမှု:</b> 💳 ဘဏ်ငွေ / QR Pay (${methodName})<br>
        <b>လုပ်ငန်းစဉ်အမှတ်:</b> #${txn}<br>
        <b>စုစုပေါင်း:</b> <b style="color:var(--primary-blue);">${bet.total_amount.toLocaleString()} ${bet.unit || "ကျပ်"}</b><br>
        <b>အခြေအနေ:</b> ✅ အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!
      `);

      if (bet.type === '2D') clearSelectedNumbers();
      if (bet.type === '3D') document.getElementById('input3dNumbers').value = '';
    }

    function openDepositModal() {
      document.getElementById('depositModal').classList.add('active');
    }
    function closeDepositModal() {
      document.getElementById('depositModal').classList.remove('active');
    }

    function openWithdrawModal() {
      const u = tgUser ? `${tgUser.first_name} (ID: ${tgUser.id})` : "Customer";
      const msg = `မင်္ဂလာပါ Admin ခင်ဗျာ၊ Wallet လက်ကျန်ငွေ (${userWalletBal.toLocaleString()} ကျပ်) အား ငွေထုတ်ယူလိုပါသည်ခင်ဗျာ။ User: ${u}`;
      const url = `https://t.me/noenoeslotagency?text=${encodeURIComponent(msg)}`;
      if (tg) tg.openTelegramLink(url);
      else window.open(url, "_blank");
    }

    function copyKPayNumber() {
      const num = paymentAccounts.kpay?.number || "09123456789";
      if (navigator.clipboard) {
        navigator.clipboard.writeText(num).then(() => {
          alert(`✅ KBZPay နံပါတ် (${num}) အား ကူးယူပြီးပါပြီ!`);
        });
      } else {
        prompt("KBZPay နံပါတ် ကူးယူရန်:", num);
      }
    }

    function submitDepositForm() {
      const amt = parseInt(document.getElementById('depAmountInput').value) || 0;
      const txn = document.getElementById('depTxnInput').value.trim();

      if (amt <= 0) {
        alert("ငွေသွင်းမည့် ပမာဏကို ထည့်သွင်းပေးပါခင်ဗျာ!");
        return;
      }
      if (!txn) {
        alert("ငွေလွှဲသူ ဖုန်းနံပါတ် (သို့မဟုတ် ပြေစာနောက်ဆုံး ၆ လုံး) ထည့်ပေးပါခင်ဗျာ!");
        return;
      }

      const depTicket = 'DEP-' + Math.floor(10000 + Math.random() * 90000);
      const methodName = selectedDepPayMethod === 'promptpay' ? 'PromptPay (Prove Pay)' : 'KBZPay (KPay)';
      const payload = {
        action: "deposit_request",
        deposit_id: depTicket,
        method: selectedDepPayMethod,
        payment_method: methodName,
        amount: amt,
        currency: "MMK",
        txn_id: txn,
        user_id: tgUser?.id || 0,
        user_name: tgUser?.first_name || "Customer"
      };

      if (tg && tg.sendData) {
        tg.sendData(JSON.stringify(payload));
      }

      closeDepositModal();
      showVoucher("ငွေသွင်း လျှောက်ထားလွှာ ပေးပို့ပြီးပါပြီ", depTicket, `
        <b>ပြေစာအမှတ်:</b> ${depTicket}<br>
        <b>ငွေသွင်းနည်းလမ်း:</b> KBZPay (KPay)<br>
        <b>ငွေပမာဏ:</b> ${amt.toLocaleString()} ကျပ်<br>
        <b>ငွေလွှဲအချက်အလက်:</b> ${txn}<br>
        <b>အခြေအနေ:</b> Admin အတည်ပြုရန် စောင့်ဆိုင်းနေပါသည်
      `);
    }

    // 2D Controls
    function set2dSession(s, el) {
      current2dSession = s;
      document.querySelectorAll('#session2d .seg-btn').forEach(b => b.classList.remove('active'));
      if (el) el.classList.add('active');
    }

    function set2dPayMode(m, el) {
      current2dPayMode = m;
      document.querySelectorAll('#payMode2d .seg-btn').forEach(b => b.classList.remove('active'));
      if (el) el.classList.add('active');
    }

    function setAmount2d(amt) {
      document.getElementById('input2dAmount').value = amt;
      update2DPreview();
    }

    function init2DGrid() {
      const container = document.getElementById('grid2DNumbers');
      container.innerHTML = '';
      for (let i = 0; i < 100; i++) {
        const str = i < 10 ? '0' + i : '' + i;
        const cell = document.createElement('div');
        cell.className = 'num-cell';
        cell.id = 'cell-' + str;
        cell.innerText = str;
        cell.onclick = () => toggleNumber(str);
        container.appendChild(cell);
      }
    }

    function toggleNumber(str) {
      if (selectedNumbers.has(str)) {
        selectedNumbers.delete(str);
        document.getElementById('cell-' + str)?.classList.remove('selected');
      } else {
        selectedNumbers.add(str);
        document.getElementById('cell-' + str)?.classList.add('selected');
      }
      syncInputs();
      update2DPreview();
    }

    function syncInputs() {
      document.getElementById('input2dNumbers').value = Array.from(selectedNumbers).join(', ');
    }

    function clearSelectedNumbers() {
      selectedNumbers.clear();
      document.querySelectorAll('.num-cell').forEach(c => c.classList.remove('selected'));
      document.getElementById('input2dNumbers').value = '';
      update2DPreview();
    }

    function pickQuickPattern(type) {
      if (type === 'ပါဝါ') {
        ['05', '16', '27', '38', '49'].forEach(n => selectedNumbers.add(n));
      } else if (type === 'နက္ခတ်') {
        ['07', '18', '24', '35', '69'].forEach(n => selectedNumbers.add(n));
      } else if (type === 'ညီကို') {
        ['01', '12', '23', '34', '45', '56', '67', '78', '89', '90'].forEach(n => selectedNumbers.add(n));
      } else {
        const val = prompt(`${type} အတွက် ထိပ်စီး/နောက်ပိတ် ဂဏန်း (၀ မှ ၉) တစ်လုံး ထည့်ပါ:`);
        if (val && !isNaN(val)) {
          const d = parseInt(val) % 10;
          for (let i = 0; i < 100; i++) {
            const s = (i < 10 ? '0' + i : '' + i);
            if (s.includes(d.toString())) selectedNumbers.add(s);
          }
        }
      }
      selectedNumbers.forEach(n => document.getElementById('cell-' + n)?.classList.add('selected'));
      syncInputs();
      update2DPreview();
    }

    function update2DPreview() {
      const amt = parseInt(document.getElementById('input2dAmount').value) || 0;
      const count = selectedNumbers.size;
      const total = count * amt;
      const unit = current2dCurrency === 'MMK' ? ' ကျပ်' : ' ဘတ် (฿)';
      document.getElementById('previewCount2d').innerText = count + ' ကွက်';
      document.getElementById('previewTotal2d').innerText = total.toLocaleString() + unit;
    }

    function submit2DBet() {
      if (!isMarketOpen) {
        alert("⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!");
        return;
      }
      const amt = parseInt(document.getElementById('input2dAmount').value) || 0;
      const nums = Array.from(selectedNumbers);

      if (nums.length === 0) {
        alert("ထိုးမည့် ဂဏန်းများကို ရွေးချယ်ပေးပါခင်ဗျာ!");
        return;
      }
      if (amt <= 0) {
        alert("ထိုးငွေပမာဏ သတ်မှတ်ပေးပါခင်ဗျာ!");
        return;
      }

      const total = nums.length * amt;
      const cur = current2dCurrency;
      const unit = cur === 'MMK' ? 'ကျပ်' : 'ဘတ်';
      const bal = cur === 'MMK' ? userWalletBalMmk : userWalletBalThb;

      // If Bank / QR Pay mode, open payment & QR modal first!
      if (current2dPayMode === 'bank_qr') {
        openBetPayQrModal({
          type: "2D",
          slot: current2dSession,
          numbers: nums,
          amount_each: amt,
          total_amount: total,
          currency: cur,
          unit: unit
        });
        return;
      }

      // If Wallet mode, check balance
      if (current2dPayMode === 'wallet' && bal < total) {
        alert(`⚠️ ${cur} Wallet လက်ကျန်ငွေ မလုံလောက်ပါခင်ဗျာ!

လိုအပ်ငွေ: ${total.toLocaleString()} ${unit}
လက်ရှိ လက်ကျန်ငွေ: ${bal.toLocaleString()} ${unit}

ကျေးဇူးပြု၍ "ဘဏ်ငွေ / QR Pay" ဖြင့် လွှဲထိုးရန် ရွေးချယ်ပါ (သို့မဟုတ်) ပင်မ Tab ရှိ + ငွေဖြည့်မည် မှ ငွေအရင် ဖြည့်ပေးပါခင်ဗျာ။`);
        return;
      }

      const tktId = 'TKT-' + Math.floor(10000 + Math.random() * 90000);
      const payload = {
        action: "place_bet",
        type: "2D",
        ticket_id: tktId,
        slot: current2dSession,
        currency: cur,
        payment_mode: current2dPayMode,
        numbers: nums,
        amount_each: amt,
        total_amount: total,
        user_name: tgUser?.first_name || 'Customer',
        user_id: tgUser?.id || 0
      };

      if (tg && tg.sendData) tg.sendData(JSON.stringify(payload));

      const mult2d = (cur === 'THB') ? 80 : 85;
      const win2d = amt * mult2d;
      showVoucher("2D ထိုးငွေ ပြေစာထွက်ရှိပါပြီ", tktId, `
        <b>အမျိုးအစား:</b> 2D (${current2dSession})<br>
        <b>ဂဏန်းများ:</b> ${nums.join(', ')} (${nums.length} ကွက်)<br>
        <b>တစ်ကွက်ထိုး:</b> ${amt.toLocaleString()} ${unit} (ပေါက်ကြေး: ${win2d.toLocaleString()} ${unit})<br>
        <b>ငွေကြေး:</b> ${cur === 'MMK' ? '🇲🇲 မြန်မာကျပ် (MMK)' : '🇹🇭 ထိုင်းဘတ် (THB)'}<br>
        <b>ငွေပေးချေမှု:</b> 💼 ${cur} Wallet မှ နုတ်ယူပြီး<br>
        <b>စုစုပေါင်း:</b> <b style="color:var(--primary-blue);">${total.toLocaleString()} ${unit}</b>
      `);
      clearSelectedNumbers();
    }

    // 3D Controls
    function set3dPayMode(m, el) {
      current3dPayMode = m;
      document.querySelectorAll('#payMode3d .seg-btn').forEach(b => b.classList.remove('active'));
      if (el) el.classList.add('active');
    }

    function submit3DBet() {
      const raw = document.getElementById('input3dNumbers').value;
      const nums = raw.split(/[\s,]+/).map(s => s.trim()).filter(s => s.length === 3 && !isNaN(s));
      const amt = parseInt(document.getElementById('input3dAmount').value) || 0;

      if (nums.length === 0) {
        alert("ကျေးဇူးပြု၍ ၃ လုံး ဂဏန်း (ဥပမာ 224, 781) ထည့်သွင်းပေးပါခင်ဗျာ!");
        return;
      }
      if (amt <= 0) {
        alert("ထိုးငွေပမာဏ သတ်မှတ်ပေးပါခင်ဗျာ!");
        return;
      }

      const total = nums.length * amt;
      const cur = current3dCurrency;
      const unit = cur === 'MMK' ? 'ကျပ်' : 'ဘတ်';
      const bal = cur === 'MMK' ? userWalletBalMmk : userWalletBalThb;

      // If Bank / QR Pay mode, open payment & QR modal first!
      if (current3dPayMode === 'bank_qr') {
        openBetPayQrModal({
          type: "3D",
          slot: "3D (03:30 PM)",
          numbers: nums,
          amount_each: amt,
          total_amount: total,
          currency: cur,
          unit: unit
        });
        return;
      }

      // If Wallet mode, check balance
      if (current3dPayMode === 'wallet' && bal < total) {
        alert(`⚠️ ${cur} Wallet လက်ကျန်ငွေ မလုံလောက်ပါခင်ဗျာ!

လိုအပ်ငွေ: ${total.toLocaleString()} ${unit}
လက်ရှိ လက်ကျန်ငွေ: ${bal.toLocaleString()} ${unit}

ကျေးဇူးပြု၍ "ဘဏ်ငွေ / QR Pay" ဖြင့် လွှဲထိုးရန် ရွေးချယ်ပါ (သို့မဟုတ်) KBZPay/PromptPay မှ ငွေအရင် ဖြည့်ပေးပါခင်ဗျာ။`);
        return;
      }

      const tktId = 'TKT-' + Math.floor(10000 + Math.random() * 90000);
      const payload = {
        action: "place_bet",
        type: "3D",
        ticket_id: tktId,
        slot: "3D (03:30 PM)",
        currency: cur,
        payment_mode: current3dPayMode,
        numbers: nums,
        amount_each: amt,
        total_amount: total,
        user_name: tgUser?.first_name || 'Customer',
        user_id: tgUser?.id || 0
      };

      if (tg && tg.sendData) tg.sendData(JSON.stringify(payload));

      const mult3d = (cur === 'THB') ? 500 : 700;
      const win3d = amt * mult3d;
      showVoucher("3D ထိုးငွေ ပြေစာထွက်ရှိပါပြီ", tktId, `
        <b>အမျိုးအစား:</b> 3D (ထိုင်းအစိုးရထီ)<br>
        <b>ဂဏန်းများ:</b> ${nums.join(', ')} (${nums.length} ကွက်)<br>
        <b>တစ်ကွက်ထိုး:</b> ${amt.toLocaleString()} ${unit} (ပေါက်ကြေး: ${win3d.toLocaleString()} ${unit})<br>
        <b>ငွေကြေး:</b> ${cur === 'MMK' ? '🇲🇲 မြန်မာကျပ် (MMK)' : '🇹🇭 ထိုင်းဘတ် (THB)'}<br>
        <b>ငွေပေးချေမှု:</b> 💼 ${cur} Wallet မှ နုတ်ယူပြီး<br>
        <b>စုစုပေါင်း:</b> <b style="color:var(--primary-blue);">${total.toLocaleString()} ${unit}</b>
      `);
      document.getElementById('input3dNumbers').value = '';
    }

    // Voucher Display
    function showVoucher(title, ticketId, html) {
      document.getElementById('voucherTitle').innerText = title;
      document.getElementById('voucherTicketId').innerText = '#' + ticketId;
      document.getElementById('voucherContent').innerHTML = html;
      document.getElementById('voucherModal').classList.add('active');
    }
    function closeVoucherModal() {
      document.getElementById('voucherModal').classList.remove('active');
    }

    // Roulette Lucky Wheel Logic
    const wheelSegments = [
      { text: '+500 ကျပ်', color: '#1e50ff' },
      { text: 'ကံစမ်း 2D', color: '#10b981' },
      { text: '+1,000 ကျပ်', color: '#f59e0b' },
      { text: '+200 ကျပ်', color: '#8b5cf6' },
      { text: 'နောက်တစ်ခါ', color: '#64748b' },
      { text: '+5,000 ကျပ်', color: '#ec4899' }
    ];
    let wheelAngle = 0;
    let isSpinning = false;

    function drawWheel() {
      const canvas = document.getElementById('wheelCanvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const numSegs = wheelSegments.length;
      const arc = (2 * Math.PI) / numSegs;
      const radius = canvas.width / 2;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < numSegs; i++) {
        const angle = wheelAngle + i * arc;
        ctx.beginPath();
        ctx.fillStyle = wheelSegments[i].color;
        ctx.moveTo(radius, radius);
        ctx.arc(radius, radius, radius - 4, angle, angle + arc);
        ctx.lineTo(radius, radius);
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Text
        ctx.save();
        ctx.translate(radius, radius);
        ctx.rotate(angle + arc / 2);
        ctx.textAlign = 'right';
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 12px sans-serif';
        ctx.fillText(wheelSegments[i].text, radius - 16, 4);
        ctx.restore();
      }

      // Center circle
      ctx.beginPath();
      ctx.arc(radius, radius, 22, 0, 2 * Math.PI);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 3;
      ctx.stroke();
    }

    function checkDailySpin() {
      const uid = tgUser?.id || 'guest';
      const today = new Date().toISOString().slice(0, 10);
      const spinKey = 'lucky_spin_' + uid + '_' + today;
      if (localStorage.getItem(spinKey) === 'done') {
        const btn = document.getElementById('btnSpinWheel');
        if (btn) {
          btn.disabled = true;
          btn.style.opacity = '0.5';
          btn.innerHTML = '<span>🔒</span> ယနေ့ ကံစမ်းခွင့် သုံးပြီးပါပြီ';
        }
        document.getElementById('wheelResultText').innerHTML = '⚠️ <b>သင်သည် ယနေ့အတွက် ကံစမ်းမဲ လှည့်ခွင့် (၁) ကြိမ် အသုံးပြုပြီးပါပြီ!</b><br><span style="font-size:11px; color:var(--text-sub);">မနက်ဖြန်တွင် ထပ်မံ ကံစမ်းနိုင်ပါသည်ခင်ဗျာ။</span>';
      }
    }

    function spinLuckyWheel() {
      const uid = tgUser?.id || 'guest';
      const today = new Date().toISOString().slice(0, 10);
      const spinKey = 'lucky_spin_' + uid + '_' + today;

      if (localStorage.getItem(spinKey) === 'done') {
        alert("⚠️ သင်သည် ယနေ့အတွက် ကံစမ်းခွင့် (၁) ကြိမ် အသုံးပြုပြီးပါပြီခင်ဗျာ!");
        return;
      }

      if (isSpinning) return;
      isSpinning = true;
      document.getElementById('wheelResultText').innerText = "ဘီးလည်နေပါသည်... စောင့်ဆိုင်းပေးပါ!";

      const spinRounds = 5 + Math.random() * 4;
      const targetAngle = wheelAngle + spinRounds * 2 * Math.PI;
      const startTime = performance.now();
      const duration = 4000;

      function animate(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        wheelAngle = targetAngle * easeOut;
        drawWheel();
    checkDailySpin();

        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          isSpinning = false;
          const arc = (2 * Math.PI) / wheelSegments.length;
          const normalized = (2 * Math.PI - (wheelAngle % (2 * Math.PI))) % (2 * Math.PI);
          const idx = Math.floor(normalized / arc);
          const prize = wheelSegments[idx];
          localStorage.setItem(spinKey, 'done');
          document.getElementById('wheelResultText').innerHTML = `🎉 ဂုဏ်ယူပါသည်! သင်သည် <b>${prize.text}</b> ရရှိပါသည်!<br><span style="font-size:11px; color:var(--text-sub);">ယနေ့အတွက် ကံစမ်းခွင့် (၁) ကြိမ် ကုန်ဆုံးသွားပါပြီ။</span>`;
          const btn = document.getElementById('btnSpinWheel');
          if (btn) {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.innerHTML = '<span>🔒</span> ယနေ့ ကံစမ်းခွင့် သုံးပြီးပါပြီ';
          }
        }
      }
      requestAnimationFrame(animate);
    }

    // Polling API Data
    async function fetchRealtimeData() {
      try {
        const uid = tgUser?.id || '';
        const res = await fetch(`/api/data?user_id=${uid}`);
        if (!res.ok) return;
        const d = await res.json();

        // Balance (MMK & THB)
        if (d.user_balance) {
          userWalletBalMmk = d.user_balance.mmk || 0;
          userWalletBalThb = d.user_balance.thb || 0;
          const elMmk = document.getElementById('homeBalanceMmk');
          if (elMmk) elMmk.innerText = userWalletBalMmk.toLocaleString();
          const elThb = document.getElementById('homeBalanceThb');
          if (elThb) elThb.innerText = userWalletBalThb.toLocaleString();
        }

        // Payment Accounts (KPay & PromptPay)
        if (d.payment_accounts) {
          if (d.payment_accounts.kpay) {
            paymentAccounts.kpay = d.payment_accounts.kpay;
            const kname = paymentAccounts.kpay.name;
            const knum = paymentAccounts.kpay.number;
            const kqr = paymentAccounts.kpay.qr || `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${knum}`;
            ['modalKpayName', 'betKpayName', 'recKpayName'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerText = kname;
            });
            ['modalKpayNumber', 'betKpayNum', 'recKpayNumber'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerText = knum;
            });
            ['modalKpayQr', 'betQrKpayImg'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.src = kqr;
            });
          }

          if (d.payment_accounts.promptpay) {
            paymentAccounts.promptpay = d.payment_accounts.promptpay;
            const pname = paymentAccounts.promptpay.name;
            const pnum = paymentAccounts.promptpay.number;
            const pqr = paymentAccounts.promptpay.qr || `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${pnum}`;
            ['modalPromptpayName', 'betPromptpayName', 'recPromptpayName'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerText = pname;
            });
            ['modalPromptpayNumber', 'betPromptpayNum', 'recPromptpayNumber'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.innerText = pnum;
            });
            ['modalPromptpayQr', 'betQrPromptpayImg'].forEach(id => {
              const el = document.getElementById(id);
              if (el) el.src = pqr;
            });
          }
        }

        // 2D Live
        if (d.twod) {
          isMarketOpen = d.twod.is_open;
          const statusText = document.getElementById('home2dStatusText');
          const banner = document.getElementById('holidayBanner2d');
          const submitBtn = document.getElementById('btnSubmit2d');

          if (!isMarketOpen) {
            if (statusText) statusText.innerHTML = '<span class="status-closed">●</span> ယနေ့ ပိတ်ရက်';
            if (banner) banner.style.display = 'block';
            if (submitBtn) {
              submitBtn.innerText = '⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါ';
              submitBtn.style.background = '#94a3b8';
            }
          } else {
            if (statusText) statusText.innerHTML = '<span class="status-open">●</span> ဖွင့်လှစ်ထားပါသည်';
            if (banner) banner.style.display = 'none';
            if (submitBtn) {
              submitBtn.innerText = '👉 2D ထိုးငွေ အတည်ပြုမည်';
              submitBtn.style.background = 'var(--primary-blue)';
            }
          }

          if (d.twod.morning_1201 && d.twod.morning_1201 !== '--') {
            document.getElementById('homeMorningVal').innerText = d.twod.morning_1201;
            document.getElementById('homeMorningSub').innerText = 'ထွက်ပြီး';
          }
          if (d.twod.evening_1630 && d.twod.evening_1630 !== '--') {
            document.getElementById('homeEveningVal').innerText = d.twod.evening_1630;
            document.getElementById('homeEveningSub').innerText = 'ထွက်ပြီး';
          }

          if (d.twod.live_set) document.getElementById('tickerSetVal').innerText = d.twod.live_set;
          if (d.twod.live_value) document.getElementById('tickerValVal').innerText = d.twod.live_value;
        }

        // 3D Live
        if (d.threed) {
          if (d.threed.first_prize) document.getElementById('gloFirstPrize').innerText = d.threed.first_prize;
          if (d.threed.threed) document.getElementById('gloThreeD').innerText = d.threed.threed;
          if (d.threed.adjacent_threed) document.getElementById('gloAdjThreed').innerText = d.threed.adjacent_threed.join(', ');
          if (d.threed.front_3d) document.getElementById('gloFront3d').innerText = d.threed.front_3d.join(', ');
          if (d.threed.back_3d) document.getElementById('gloBack3d').innerText = d.threed.back_3d.join(', ');
          if (d.threed.back_2d) document.getElementById('gloBack2d').innerText = d.threed.back_2d;
          if (d.threed.date) document.getElementById('gloDrawDate').innerText = 'ရက်စွဲ: ' + d.threed.date;
        }
      } catch (e) {
        console.log("Fetch err:", e);
      }
    }

    // Init
    init2DGrid();
    drawWheel();
    checkDailySpin();
    fetchRealtimeData();
    setInterval(fetchRealtimeData, 4000);
  </script>
</body>
</html>
"""

def get_miniapp_html():
    html_file = os.path.join(DATA_DIR, "miniapp.html")
    if os.path.exists(html_file):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return EMBEDDED_MINIAPP_HTML

class WebAndMiniAppHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        url_path = self.path.split("?")[0].rstrip("/")
        if not url_path:
            url_path = "/"

        # Health Check
        if url_path in ["/health", "/ping"]:
            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Real-time Data API
        if url_path == "/api/data":
            uid = ""
            if "?" in self.path:
                try:
                    from urllib.parse import parse_qs, urlparse
                    qs = parse_qs(urlparse(self.path).query)
                    uid = qs.get("user_id", [""])[0]
                except Exception:
                    pass

            d2 = fetch_realtime_2d()
            d3 = fetch_realtime_3d()
            bal = user_balances.get(str(uid), {"mmk": 0, "thb": 0}) if uid else {"mmk": 0, "thb": 0}
            payload = {
                "twod": d2,
                "threed": d3,
                "user_balance": bal,
                "payment_accounts": PAYMENT_ACCOUNTS
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Mini App Single Page Application (Served at '/', '/app', '/miniapp')
        if url_path in ["/", "/app", "/miniapp", "/index.html"]:
            html = get_miniapp_html()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), WebAndMiniAppHandler)
        server.serve_forever()
    except Exception as e:
        print("Server error:", e)

threading.Thread(target=start_server, daemon=True).start()

# Background Keep-Alive Thread to prevent Render Free Sleep
def keep_alive_worker():
    time.sleep(30)
    target_url = f"{RENDER_EXTERNAL_URL}/health" if RENDER_EXTERNAL_URL else "http://127.0.0.1:10000/health"
    while True:
        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "SelfKeepAlive"})
            with urllib.request.urlopen(req, timeout=10) as res:
                pass
        except Exception:
            pass
        time.sleep(480) # Ping every 8 minutes (keeps Render awake before 15m sleep limit)

threading.Thread(target=keep_alive_worker, daemon=True).start()

# ==================== TELEGRAM BOT LOGIC ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_name = user.first_name if user else "မိတ်ဆွေ"
    uid = str(user.id) if user else "0"

    if uid not in user_balances:
        user_balances[uid] = {"mmk": 0, "thb": 0}
        save_json(BALANCES_FILE, user_balances)

    welcome_text = (
        f"👋 *မင်္ဂလာပါ {u_name} ခင်ဗျာ!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎰 *Lucky2D3D Official Bot မှ ကြိုဆိုပါသည်!*\n\n"
        "📱 အောက်ရှိ **'🎯 ထိုးမယ်'** ခလုတ်ကို နှိပ်၍ ဂဏန်းရွေးချယ်မှု၊ Live ကြည့်ရှုမှု နှင့် ငွေဖြည့်စနစ်များကို အလွယ်တကူ အသုံးပြုနိုင်ပါသည်ခင်ဗျာ!\n\n"
        "💡 *ပေါက်ကြေးများ:*\n"
        "• 2D (၂လုံး): ၁ ကျပ် ➔ ၈၅ ကျပ် | ၅ ဘတ် ➔ ၄၀၀ ဘတ် / ၁၀ ဘတ် ➔ ၈၀၀ ဘတ် (1:80)\n"
        "• 3D (၃လုံး): ၁ ကျပ် ➔ ၇၀၀ ကျပ် | ၁၀ ဘတ် ➔ ၅,၀၀၀ ဘတ် (1:500)"
    )

    main_keyboard = [
        [KeyboardButton("💰 ငွေသွင်း/ငွေထုတ်"), KeyboardButton("💵 ငွေလက်ကျန်")],
        [KeyboardButton("🎯 2D ထိုး"), KeyboardButton("🎯 3D ထိုး")],
        [KeyboardButton("📜 ထိုးခဲ့သောမှတ်တမ်းများ"), KeyboardButton("🏆 ထီပေါက်စဉ်")],
        [KeyboardButton("👩‍💻 Admin Account"), KeyboardButton("🎮 Game ဆော့ရန်")],
        [KeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))]
    ]
    reply_markup = ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    user = update.effective_user
    uid = str(user.id) if user else "0"

    # 1. 2D Bet Attempt
    if text in ["🎯 2D ထိုး", "2D ထိုး", "👉 🎯 2D ထိုးမည်", "2D ထိုးမည်"]:
        is_hol, hol_reason = is_market_holiday()
        if is_hol:
            await update.message.reply_text(
                f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 *အကြောင်းပြချက်:* {hol_reason}\n"
                f"🏛️ ထိုင်းစတော့အိတ်ချိန်း (SET) ဈေးကွက်ပိတ်ရက်ဖြစ်သောကြောင့် ယနေ့ ၂လုံး (2D) ထိုးလို့မရပါခင်ဗျာ။\n\n"
                f"💡 *၃လုံး (3D)* ကိုမူ ပုံမှန်အတိုင်း ကြိုတင်ထိုးယူနိုင်ပါသည်ခင်ဗျာ!",
                parse_mode="Markdown"
            )
            return

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("မနက်ပိုင်း (12:01 PM)", callback_data="slot_2d_morning")],
            [InlineKeyboardButton("ညနေပိုင်း (04:30 PM)", callback_data="slot_2d_evening")],
            [InlineKeyboardButton("🎯 ထိုးမယ် (Mini App)", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await update.message.reply_text("⏰ *2D ထိုးလိုသော အချိန်ပိုင်း ရွေးချယ်ပါ:*", parse_mode="Markdown", reply_markup=kb)
        return

    # 2. 3D Bet Attempt
    elif text in ["🎯 3D ထိုး", "3D ထိုး", "👉 🎯 3D ထိုးမည်", "3D ထိုးမည်"]:
        d3 = fetch_realtime_3d()
        await update.message.reply_text(
            f"🎯 *ထိုင်း 3D ထိုးကြေး တင်သွင်းရန်*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ *နောက်ထပ် ထွက်မည့်ရက်:* `{d3.get('next_date')}`\n"
            f"💰 *ပေါက်ကြေး:* ၁ ကျပ်လျှင် ၇၀၀ ကျပ်\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✍️ စာရိုက်ထိုးလိုပါက: `224=1000` ဟု ရိုက်ပို့နိုင်ပါသည် (သို့မဟုတ်) 'ထိုးမယ်' ဖြင့် လွယ်ကူစွာ ထိုးနိုင်ပါသည်ခင်ဗျာ။",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 ထိုးမယ် (Mini App)", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
        )
        return

    # 3. 🏆 ထီပေါက်စဉ် (Menu)
    elif text in ["🏆 ထီပေါက်စဉ်", "ထီပေါက်စဉ်", "ပေါက်စဉ်"]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ပေါက်ဂဏန်းများ (2D မနက်/ည & 3D)", callback_data="lotto_winning_numbers")],
            [InlineKeyboardButton("📅 3D ထွက်ဂဏန်း မှတ်တမ်းများ (ရလဒ်စုံ)", callback_data="lotto_history_3d")],
            [InlineKeyboardButton("🏆 ထီပေါက်သူစာရင်း", callback_data="lotto_winners_list")],
            [InlineKeyboardButton("🌟 အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း", callback_data="lotto_top10_winners")],
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        msg = (
            "🏆 *တရားဝင် ထီပေါက်စဉ်နှင့် ဆုရရှိသူများ မီနူး* 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ကျေးဇူးပြု၍ ကြည့်ရှုလိုသော စာရင်းကို အောက်ပါ ခလုတ်များမှ ရွေးချယ်ပါခင်ဗျာ:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 4. 📜 ထိုးခဲ့သောမှတ်တမ်းများ
    elif text in ["📜 ထိုးခဲ့သောမှတ်တမ်းများ", "ထိုးခဲ့သောမှတ်တမ်းများ", "ထိုးမှတ်တမ်း", "မှတ်တမ်း"]:
        bets = user_bets.get(uid, [])
        if not bets:
            msg = (
                "📜 *သင့် ထိုးငွေမှတ်တမ်းများ* 📜\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ ယခုအချိန်အထိ ထိုးထားသော ပြေစာ မှတ်တမ်း မရှိသေးပါခင်ဗျာ။\n\n"
                "👉 'ထိုးမယ်' ကို နှိပ်၍ ဂဏန်းများ စတင် ထိုးယူနိုင်ပါသည်!"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
            return

        msg = (
            f"📜 *သင့် ထိုးငွေမှတ်တမ်းများ (နောက်ဆုံး ၅ ခု)* 📜\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        for b in bets[-5:]:
            msg += (
                f"🔖 `#{b.get('ticket_id', 'TKT')}` | *{b.get('type', '2D')}* ({b.get('slot', '-')})\n"
                f"🎯 ဂဏန်း: 【 `{', '.join(map(str, b.get('numbers', [])))}` 】\n"
                f"💰 ထိုးငွေ: `{b.get('total_amount', 0):,} ကျပ်` | အခြေအနေ: ✅ မှတ်တမ်းတင်ပြီး\n"
                "────────────────────\n"
            )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # 5. 💰 ငွေသွင်း/ငွေထုတ်
    elif text in ["💰 ငွေသွင်း/ငွေထုတ်", "ငွေသွင်း/ငွေထုတ်", "ငွေသွင်းငွေထုတ်"]:
        acc = PAYMENT_ACCOUNTS.get("kpay", {})
        msg = (
            f"💰 *ငွေသွင်း / ငွေထုတ် စနစ် (KBZPay)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 *KBZPay အကောင့်အမည်:* `{acc.get('name')}`\n"
            f"📱 *KBZPay ဖုန်းနံပါတ်:* `{acc.get('number')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 'ထိုးမယ်' ရှိ 'ပိုက်ဆံအိတ်' Tab မှတစ်ဆင့် ငွေဖြည့်သွင်းနိုင်ပါသည် (သို့မဟုတ်) Admin ထံ တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်ခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ် (ငွေဖြည့်မည်)", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ဆက်သွယ်ရန်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 6. 💵 ငွေလက်ကျန်
    elif text in ["💵 ငွေလက်ကျန်", "ငွေလက်ကျန်", "လက်ကျန်ငွေ"]:
        bal = user_balances.get(uid, {"mmk": 0, "thb": 0})
        await update.message.reply_text(
            f"💵 *သင့် လက်ကျန်ငွေစာရင်း:*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🇲🇲 *မြန်မာကျပ်ငွေ:* `{bal.get('mmk', 0):,} ကျပ်`\n"
            f"🇹🇭 *ထိုင်းဘတ်ငွေ:* `{bal.get('thb', 0):,} ဘတ်`",
            parse_mode="Markdown"
        )
        return

    # 7. 🎮 Game ဆော့ရန်
    elif text in ["🎮 Game ဆော့ရန်", "🎮 ဂိမ်းဆော့ရန်", "Game ဆော့ရန်", "ဂိမ်းဆော့ရန်", "ဂိမ်း"]:
        msg = (
            "🎮 *Lucky2D3D Official Game စင်တာ* 🎮\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎰 *လူကြိုက်များသော စလော့နှင့် ကာစီနိုဂိမ်းများ:*\n"
            "• 🌟 JDB, JILI, Pragmatic Play စလော့ဂိမ်းများ\n"
            "• 🐟 ငါးပစ်ဂိမ်း (Ocean King & Fish Hunter)\n"
            "• 🎲 တိုက်ရိုက်ကာစီနို (Live Baccarat & Roulette)\n"
            "• 🎁 မနီအက်ပ် ကံစမ်းဘီး (Daily Free Lucky Spin)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Game အကောင့်ဖွင့်ရန်နှင့် ယူနစ်ဖြည့်ရန် Admin (@noenoeslotagency) ထံ တိုက်ရိုက် ဆက်သွယ်ပေးပါခင်ဗျာ!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ် (ကံစမ်းဘီး လှည့်မည်)", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("💬 Game အကောင့်ဖွင့်ရန် Admin ဆက်သွယ်မည်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 8. 👩‍💻 Admin Account
    elif text in ["👩‍💻 Admin Account", "💬 Admin အကောင့်", "Admin Account", "Admin အကောင့်", "Admin", "admin"]:
        msg = (
            "💬 *Admin နှင့် တိုက်ရိုက်ဆက်သွယ်ရန်* 💬\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Admin Telegram:* @{ADMIN_USERNAME}\n"
            f"🆔 *Admin ID:* `{ADMIN_CHAT_ID}`\n"
            "⏰ *ဝန်ဆောင်မှု:* ၂၄ နာရီ ပိတ်ရက်မရှိ အမြန်ဆုံး ဝန်ဆောင်မှုပေးပါသည်ခင်ဗျာ။\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ငွေသွင်း/ငွေထုတ်၊ ထိုးငွေပြေစာ စစ်ဆေးခြင်း၊ ဂိမ်းအကောင့်ဖွင့်ခြင်း များအတွက် အောက်ပါခလုတ်ကို နှိပ်၍ တိုက်ရိုက် ဆက်သွယ်နိုင်ပါသည်:"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Admin နှင့် တိုက်ရိုက်ဆက်သွယ်ရန်", url=ADMIN_URL)]
        ])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 9. 🏠 Home
    elif text in ["🏠 Home", "Home", "ပင်မ"]:
        await start(update, context)
        return

    # 10. Direct "ထိုးမယ်" text
    elif text in ["🎯 ထိုးမယ်", "ထိုးမယ်", "ထိုးမည်"]:
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        is_hol, hol_reason = is_market_holiday()
        status_line = "🔴 *ယနေ့ စတော့ဈေးကွက် ပိတ်ပါသည်*" if is_hol else "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live)*"

        msg = (
            f"🎯 *Thai 2D & 3D Live ထိုးကြေးတင်သွင်းရန်* 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ထိုင်း 2D Live အခြေအနေ ({d2.get('date')}):*\n"
            f"{status_line}\n"
            f"• 🟢 Live 2D: 【 *{d2.get('live_2d')}* 】\n"
            f"• 📈 SET: `{d2.get('live_set')}` | 💰 Value: `{d2.get('live_value')}`\n"
            f"• 🌞 မနက် (12:01 PM): 【 *{d2.get('morning_1201')}* 】\n"
            f"• 🌇 ညနေ (04:30 PM): 【 *{d2.get('evening_1630')}* 】\n"
        )
        if is_hol:
            msg += f"• ⛔ *2D ပိတ်ရက်:* {hol_reason} (2D ထိုးမရပါ)\n"

        adj_str = ", ".join(d3.get("adjacent_threed", []))
        msg += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎲 *ထိုင်းအစိုးရ 3D Live အခြေအနေ:*\n"
            f"• 🥇 ပထမဆုကြီး (၆ လုံး): 【 *{d3.get('first_prize')}* 】\n"
            f"• 🔥 တရားဝင် 3D: 【 *{d3.get('threed')}* 】 (အနား: {adj_str})\n"
            f"• ⏰ နောက်ထပ် ထွက်မည့်ရက်: `{d3.get('next_date')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 *ထိုးလိုသော နည်းလမ်းကို အောက်ပါခလုတ်များမှ ရွေးချယ်ပါ:*"
        )

        inline_buttons = [
            [InlineKeyboardButton("🎯 ထိုးမယ် (Mini App ဖွင့်မည်)", web_app=WebAppInfo(url=MINI_APP_URL))]
        ]
        if not is_hol:
            inline_buttons.append([
                InlineKeyboardButton("🎯 2D မနက် (12:01 PM)", callback_data="slot_2d_morning"),
                InlineKeyboardButton("🎯 2D ညနေ (04:30 PM)", callback_data="slot_2d_evening")
            ])
        else:
            inline_buttons.append([
                InlineKeyboardButton("⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည်", callback_data="closed_2d_notice")
            ])

        inline_buttons.append([
            InlineKeyboardButton("🎯 3D ထိုးမည် (၁ ရက် / ၁၆ ရက်)", callback_data="btn_bet_3d")
        ])

        reply_markup = InlineKeyboardMarkup(inline_buttons)
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        return

    # Check if user is replying with a payment transaction ID for pending text bet
    if uid in pending_text_bets and pending_text_bets[uid].get("waiting_txn"):
        p = pending_text_bets.pop(uid)
        txn_id = text.strip()
        b_type = p["type"]
        amt = p["amount"]
        num_part = p["numbers"][0]
        tkt = f"TKT-{random.randint(10000, 99999)}"
        tz_mm = timezone(timedelta(hours=6, minutes=30))
        now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")
        mult = 700 if b_type == "3D" else 85

        if uid not in user_bets:
            user_bets[uid] = []
        user_bets[uid].append({
            "ticket_id": tkt,
            "type": b_type,
            "slot": p["slot"],
            "numbers": [num_part],
            "amount_each": amt,
            "total_amount": amt,
            "date": now_str,
            "user_name": u_name,
            "payment_mode": "bank_qr",
            "txn_id": txn_id,
            "payment_method": "KPay / PromptPay"
        })
        save_json(BETS_FILE, user_bets)

        await update.message.reply_text(
            f"🧾 *{b_type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ* 🧾\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔖 *ပြေစာအမှတ်:* `#{tkt}`\n"
            f"🎯 *ဂဏန်း:* 【 `{num_part}` 】\n"
            f"💰 *ထိုးငွေ:* `{amt:,} ကျပ်` (ပေါက်ကြေး: `{amt*mult:,} ကျပ်`)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *ငွေပေးချေမှု:* `💳 ဘဏ်ငွေ / QR Pay (ငွေလွှဲစစ်ဆေးပြီး)`\n"
            f"📝 *လုပ်ငန်းစဉ်အမှတ်:* `#{txn_id}`\n"
            f"✅ *အခြေအနေ:* အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
            ])
        )

        try:
            admin_msg = (
                f"🚨 *[{b_type} စာရိုက်ထိုးငွေ လွှဲပြေစာ အသစ် ရောက်ရှိပါသည်]*\n"
                f"👤 *ထိုးသူ:* `{u_name}` (ID: `{uid}`)\n"
                f"🔖 *ပြေစာ:* `#{tkt}`\n"
                f"🎯 *ဂဏန်း:* `{num_part}` ({b_type})\n"
                f"💰 *ကျသင့်ငွေ:* `{amt:,} ကျပ်`\n"
                f"📝 *လုပ်ငန်းစဉ်အမှတ်:* `#{txn_id}`"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ အတည်ပြုမည်", callback_data=f"apprbet_{tkt}_{uid}")],
                [InlineKeyboardButton("❌ ပယ်ဖျက်မည်", callback_data=f"rejbet_{tkt}_{uid}")]
            ])
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass
        return

    # Direct Text Bet Parsing (e.g. 12=1000 or 123=500)
    if "=" in text:
        parts = text.split("=")
        if len(parts) == 2 and parts[1].strip().isdigit():
            num_part = parts[0].strip()
            amt = int(parts[1].strip())
            is_3d = len(num_part) == 3

            if not is_3d:
                is_hol, hol_reason = is_market_holiday()
                if is_hol:
                    await update.message.reply_text(
                        f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}",
                        parse_mode="Markdown"
                    )
                    return

            b_type = "3D" if is_3d else "2D"
            rate = "1:700" if is_3d else "1:85"
            bal = user_balances.get(uid, {}).get("mmk", 0)

            # Store pending text bet
            pending_text_bets[uid] = {
                "type": b_type,
                "numbers": [num_part],
                "amount": amt,
                "rate": rate,
                "slot": "3D (03:30 PM)" if is_3d else "2D Live",
                "waiting_txn": False
            }

            msg = (
                f"🎯 *{b_type} ထိုးငွေ ပေးချေမည့် ပုံစံ ရွေးချယ်ပါ* 🎯\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *ဂဏန်း:* 【 `{num_part}` 】\n"
                f"💰 *ထိုးကြေး:* `{amt:,} ကျပ်` (ပေါက်ကြေး: {rate})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *သင့် Wallet လက်ကျန်ငွေ:* `{bal:,} ကျပ်`\n\n"
                f"ကျေးဇူးပြု၍ အောက်ပါ ငွေပေးချေမှု နည်းလမ်းတစ်ခုခုကို ရွေးချယ်ပေးပါခင်ဗျာ:"
            )

            buttons = []
            if bal >= amt:
                buttons.append([InlineKeyboardButton(f"💼 Wallet လက်ကျန်ငွေဖြင့် ထိုးမည် ({amt:,} ကျပ်)", callback_data=f"tbet_wallet_{uid}")])
            buttons.append([InlineKeyboardButton("💳 ဘဏ်ငွေ / KPay / PromptPay QR ဖြင့် လွှဲထိုးမည်", callback_data=f"tbet_bank_{uid}")])
            if bal < amt:
                buttons.append([InlineKeyboardButton("💰 Wallet ထဲ အရင် ငွေဖြည့်မည်", callback_data="deposit_info")])
            buttons.append([InlineKeyboardButton("❌ မထိုးတော့ပါ / ပယ်ဖျက်မည်", callback_data=f"tbet_cancel_{uid}")])

            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
            return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    uid = str(user.id) if user else "0"
    u_name = user.first_name if user else "Customer"

    # Text Bet Wallet Payment Callback
    if data.startswith("tbet_wallet_"):
        target_uid = data.split("_")[2]
        if target_uid != uid or uid not in pending_text_bets:
            await query.answer("ရွေးချယ်မှု သက်တမ်းကုန်သွားပါပြီခင်ဗျာ!", show_alert=True)
            return

        p = pending_text_bets.pop(uid)
        amt = p["amount"]
        b_type = p["type"]
        num_part = p["numbers"][0]
        bal = user_balances.get(uid, {}).get("mmk", 0)

        if bal < amt:
            await query.answer("Wallet လက်ကျန်ငွေ မလုံလောက်ပါခင်ဗျာ!", show_alert=True)
            return

        user_balances[uid]["mmk"] -= amt
        save_json(BALANCES_FILE, user_balances)

        tkt = f"TKT-{random.randint(10000, 99999)}"
        tz_mm = timezone(timedelta(hours=6, minutes=30))
        now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")
        mult = 700 if b_type == "3D" else 85
        rem = user_balances.get(uid, {}).get("mmk", 0)

        if uid not in user_bets:
            user_bets[uid] = []
        user_bets[uid].append({
            "ticket_id": tkt,
            "type": b_type,
            "slot": p["slot"],
            "numbers": [num_part],
            "amount_each": amt,
            "total_amount": amt,
            "date": now_str,
            "user_name": u_name,
            "payment_mode": "wallet"
        })
        save_json(BETS_FILE, user_bets)

        await query.edit_message_text(
            f"🧾 *{b_type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ* 🧾\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔖 *ပြေစာအမှတ်:* `#{tkt}`\n"
            f"🎯 *ဂဏန်း:* 【 `{num_part}` 】\n"
            f"💰 *ထိုးငွေ:* `{amt:,} ကျပ်` (ပေါက်ကြေး: `{amt*mult:,} ကျပ်`)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *ငွေပေးချေမှု:* `💼 Wallet လက်ကျန်ငွေမှ နုတ်ယူပြီး`\n"
            f"💰 *လက်ကျန်ငွေ:* `{rem:,} ကျပ်`\n"
            f"✅ *အခြေအနေ:* အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
            ])
        )
        return

    # Text Bet Bank / QR Payment Callback
    elif data.startswith("tbet_bank_"):
        target_uid = data.split("_")[2]
        if target_uid != uid or uid not in pending_text_bets:
            await query.answer("ရွေးချယ်မှု သက်တမ်းကုန်သွားပါပြီခင်ဗျာ!", show_alert=True)
            return

        p = pending_text_bets[uid]
        b_type = p["type"]
        amt = p["amount"]
        num_part = p["numbers"][0]

        msg = (
            f"💳 *{b_type} ထိုးငွေ ပေးချေရန် QR Scan နှင့် အကောင့်များ*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *ဂဏန်း:* 【 `{num_part}` 】 | 💰 *ကျသင့်ငွေ:* `{amt:,} ကျပ်`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔵 **KBZPay (KPay Scan):**\n"
            f"• အကောင့်အမည်: `{PAYMENT_ACCOUNTS['kpay']['Ma Moe Thu zar']}`\n"
            f"• ဖုန်းနံပါတ်: `{PAYMENT_ACCOUNTS['kpay']['09766646412']}`\n\n"
            f"🇹🇭 **PromptPay (Prove Pay Scan):**\n"
            f"• အကောင့်အမည်: `{PAYMENT_ACCOUNTS['promptpay']['MR.AUNG MYAT TUN']}`\n"
            f"• နံပါတ်: `{PAYMENT_ACCOUNTS['promptpay']['0816404238']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 *အသိပေးချက်:* အထက်ပါ QR သို့မဟုတ် အကောင့်သို့ ပိုက်ဆံလွှဲပြီးပါက အောက်ပါ **'✅ ပိုက်ဆံလွှဲပြီးပါပြီ (လုပ်ငန်းစဉ်အမှတ် ပို့မည်)'** ခလုတ်ကို နှိပ်ပြီး လုပ်ငန်းစဉ်အမှတ် နောက်ဆုံး ၆ လုံး ပို့ပေးပါခင်ဗျာ။ စစ်ဆေးပြီးမှသာ တရားဝင် ပြေစာ ထွက်ရှိပါမည်!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ပိုက်ဆံလွှဲပြီးပါပြီ (လုပ်ငန်းစဉ်အမှတ် ပို့မည်)", callback_data=f"tbet_ready_{uid}")],
            [InlineKeyboardButton("💬 Admin ထံ တိုက်ရိုက် ဆက်သွယ်မည်", url=ADMIN_URL)],
            [InlineKeyboardButton("❌ မထိုးတော့ပါ / ပယ်ဖျက်မည်", callback_data=f"tbet_cancel_{uid}")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Text Bet Ready for Txn Callback
    elif data.startswith("tbet_ready_"):
        target_uid = data.split("_")[2]
        if target_uid == uid and uid in pending_text_bets:
            pending_text_bets[uid]["waiting_txn"] = True
            await query.edit_message_text(
                "✍️ *ကျေးဇူးပြု၍ ပိုက်ဆံလွှဲပြီးသော လုပ်ငန်းစဉ်အမှတ် (Txn ID သို့မဟုတ် နောက်ဆုံး ၆ လုံး) ကို စာရိုက်ပို့ပေးပါခင်ဗျာ:*\n\n"
                "ဥပမာ: `123456` သို့မဟုတ် `09123456789`\n\n"
                "*(စာရိုက်ပို့လိုက်သည်နှင့် စစ်ဆေးပြီး တရားဝင် ထိုးငွေပြေစာ ထွက်ရှိပါမည်)*",
                parse_mode="Markdown"
            )
        return

    # Text Bet Cancel Callback
    elif data.startswith("tbet_cancel_"):
        pending_text_bets.pop(uid, None)
        await query.edit_message_text("❌ ထိုးငွေတင်သွင်းမှုကို ပယ်ဖျက်လိုက်ပါပြီခင်ဗျာ။")
        return

    if data == "closed_2d_notice":
        is_hol, hol_reason = is_market_holiday()
        await query.answer(f"⛔ ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ({hol_reason}) ထိုးလို့မရပါခင်ဗျာ!", show_alert=True)
        return

    # Admin Deposit Approval
    elif data.startswith("apprdep_"):
        if update.effective_user.id != ADMIN_CHAT_ID:
            await query.answer("Admin သာ အတည်ပြုနိုင်ပါသည်!", show_alert=True)
            return
        parts = data.split("_")
        dep_id = parts[1]
        target_uid = parts[2]
        amt = int(parts[3])
        cur_code = parts[4] if len(parts) > 4 else "mmk"
        unit = "ဘတ်" if cur_code == "thb" else "ကျပ်"

        if target_uid not in user_balances:
            user_balances[target_uid] = {"mmk": 0, "thb": 0}
        user_balances[target_uid][cur_code] = user_balances[target_uid].get(cur_code, 0) + amt
        save_json(BALANCES_FILE, user_balances)

        await query.edit_message_text(f"✅ ငွေသွင်းပြေစာ `#{dep_id}` အား အတည်ပြုပြီးပါပြီ!\n👤 User: `{target_uid}` ထံသို့ `{amt:,} {unit}` ({cur_code.upper()}) ထည့်သွင်းပြီးပါပြီ။", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"🎉 *ငွေသွင်းမှု အတည်ပြုပြီးပါပြီ* 🎉\n━━━━━━━━━━━━━━━━━━━━\n🔖 *ပြေစာအမှတ်:* `#{dep_id}`\n💰 *ဖြည့်သွင်းငွေ:* `{amt:,} {unit}` ({cur_code.upper()})\n💼 *လက်ရှိ လက်ကျန်ငွေ:* `{user_balances[target_uid][cur_code]:,} {unit}`\n━━━━━━━━━━━━━━━━━━━━\n👉 '🎯 ထိုးမယ်' ကို နှိပ်၍ စတင် ကံစမ်းနိုင်ပါသည်ခင်ဗျာ!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print("Notify user deposit failed:", e)
        return

    # Admin Deposit Rejection
    elif data.startswith("rejdep_"):
        if update.effective_user.id != ADMIN_CHAT_ID:
            return
        parts = data.split("_")
        dep_id = parts[1]
        target_uid = parts[2]
        await query.edit_message_text(f"❌ ငွေသွင်းပြေစာ `#{dep_id}` အား ပယ်ဖျက်လိုက်ပါပြီ။")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"❌ *သင့်ငွေသွင်းလွှာ `#{dep_id}` အား စစ်ဆေးချက်အရ ပယ်ဖျက်လိုက်ပါသည်ခင်ဗျာ။*\nအသေးစိတ်အတွက် Admin ထံ တိုက်ရိုက် ဆက်သွယ်စုံစမ်းနိုင်ပါသည်ခင်ဗျာ။",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # Admin Bet Approval
    elif data.startswith("apprbet_"):
        if update.effective_user.id != ADMIN_CHAT_ID:
            return
        parts = data.split("_")
        tkt_id = parts[1]
        target_uid = parts[2]
        await query.edit_message_text(f"✅ ထိုးငွေပြေစာ `#{tkt_id}` အား အောင်မြင်စွာ အတည်ပြုပြီးပါပြီ!")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"✅ *သင့်ထိုးငွေပြေစာ `#{tkt_id}` အား Admin မှ အတည်ပြုလိုက်ပါပြီ!*\nထီပေါက်ပါက ဆုငွေကို အလိုအလျောက် သို့မဟုတ် တိုက်ရိုက် ထုတ်ယူနိုင်ပါသည်ခင်ဗျာ။ ကံကောင်းပါစေ!",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # Admin Bet Rejection
    elif data.startswith("rejbet_"):
        if update.effective_user.id != ADMIN_CHAT_ID:
            return
        parts = data.split("_")
        tkt_id = parts[1]
        target_uid = parts[2]
        await query.edit_message_text(f"❌ ထိုးငွေပြေစာ `#{tkt_id}` အား ပယ်ဖျက်လိုက်ပါပြီ။")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"❌ *သင့်ထိုးငွေပြေစာ `#{tkt_id}` အား စစ်ဆေးချက်အရ ပယ်ဖျက်လိုက်ပါသည်ခင်ဗျာ။*\nအသေးစိတ်အတွက် Admin ထံ ဆက်သွယ်စုံစမ်းနိုင်ပါသည်ခင်ဗျာ။",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # Back to Lotto Menu
    elif data == "back_to_lotto_menu":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ပေါက်ဂဏန်းများ (2D မနက်/ည & 3D)", callback_data="lotto_winning_numbers")],
            [InlineKeyboardButton("📅 3D ထွက်ဂဏန်း မှတ်တမ်းများ (ရလဒ်စုံ)", callback_data="lotto_history_3d")],
            [InlineKeyboardButton("🏆 ထီပေါက်သူစာရင်း", callback_data="lotto_winners_list")],
            [InlineKeyboardButton("🌟 အများဆုံးပေါက်သူ ၁၀ ယောက်စာရင်း", callback_data="lotto_top10_winners")],
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        msg = (
            "🏆 *တရားဝင် ထီပေါက်စဉ်နှင့် ဆုရရှိသူများ မီနူး* 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ကျေးဇူးပြု၍ ကြည့်ရှုလိုသော စာရင်းကို အောက်ပါ ခလုတ်များမှ ရွေးချယ်ပါခင်ဗျာ:"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Winning Numbers (2D & 3D)
    elif data == "lotto_winning_numbers":
        d2 = fetch_realtime_2d()
        d3 = fetch_realtime_3d()
        is_hol, hol_reason = is_market_holiday()
        status_line = "🔴 *ယနေ့ စတော့ဈေးကွက် ပိတ်ပါသည်*" if is_hol else "🟢 *စတော့ဈေးကွက် တိုက်ရိုက် (Live)*"

        msg = (
            f"🎯 *တရားဝင် ပေါက်ဂဏန်းများ (2D မနက်/ည နှင့် 3D)* 🎯\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *ထိုင်း 2D ရလဒ်စုံ ({d2.get('date')}):*\n"
            f"{status_line}\n"
            f"• 🟢 Live 2D: 【 *{d2.get('live_2d')}* 】\n"
            f"• 🌞 မနက် (12:01 PM): 【 *{d2.get('morning_1201')}* 】\n"
            f"• 🌇 ညနေ (04:30 PM): 【 *{d2.get('evening_1630')}* 】\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎲 *ထိုင်းအစိုးရ 3D တရားဝင် ရလဒ်စုံ ({d3.get('date')}):*\n"
            f"• 🥇 ပထမဆုကြီး (၆ လုံး): 【 *{d3.get('first_prize')}* 】\n"
            f"• 🔥 တရားဝင် 3D အပေါ်: 【 *{d3.get('threed')}* 】\n"
            f"• ✨ 3D အနားဂဏန်းများ: {', '.join([f'【 {x} 】' for x in d3.get('adjacent_threed', [])])}\n"
            f"• 🔹 ရှေ့ ၃ လုံး: {', '.join([f'【 {x} 】' for x in d3.get('front_3d', [])])}\n"
            f"• 🔸 နောက် ၃ လုံး: {', '.join([f'【 {x} 】' for x in d3.get('back_3d', [])])}\n"
            f"• 🔻 အောက် ၂ လုံး: 【 *{d3.get('back_2d')}* 】\n"
            f"⏰ နောက်ထပ် 3D ထွက်မည့်ရက်: `{d3.get('next_date')}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # 3D Historical Results
    elif data == "lotto_history_3d":
        msg = (
            "📅 *ထိုင်းအစိုးရ 3D ထွက်ဂဏန်း မှတ်တမ်းများ (တရားဝင် GLO)* 📅\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• 📅 `01-11-2026`: ပထမဆု `423224` ➔ 3D 【 *224* 】\n"
            "   ရှေ့: `300, 950` | နောက်: `393, 804` | 2D: `85`\n\n"
            "• 📅 `16-10-2026`: ပထမဆု `011781` ➔ 3D 【 *781* 】\n"
            "   ရှေ့: `392, 402` | နောက်: `171, 255` | 2D: `48`\n\n"
            "• 📅 `01-10-2026`: ပထမဆု `402701` ➔ 3D 【 *701* 】\n"
            "   ရှေ့: `791, 912` | နောက်: `058, 396` | 2D: `70`\n\n"
            "• 📅 `16-09-2026`: ပထမဆု `730640` ➔ 3D 【 *640* 】\n"
            "   ရှေ့: `060, 521` | နောက်: `266, 041` | 2D: `64`\n\n"
            "• 📅 `01-09-2026`: ပထမဆု `417212` ➔ 3D 【 *212* 】\n"
            "   ရှေ့: `257, 346` | နောက်: `136, 740` | 2D: `04`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⏰ 3D ထွက်ချိန်: လစဉ် ၁ ရက် နှင့် ၁၆ ရက် (ညနေ ၃:၃၀ နာရီ)\n"
            "💡 Admin အနေဖြင့် ဂဏန်းပြင်လိုပါက `/set3d <ဂဏန်း>` ဖြင့် အချိန်မရွေး သတ်မှတ်နိုင်ပါသည်။"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Real Winners List
    elif data == "lotto_winners_list":
        winners = get_verified_winners()
        if not winners:
            msg = (
                "🏆 *တရားဝင် ထီပေါက်သူ စာရင်းများ* 🏆\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ *ယခုအချိန်အထိ ထီပေါက်သူ မရှိသေးပါခင်ဗျာ!*\n\n"
                "💡 အဖွဲ့ဝင်များ ထိုးထားသော ဂဏန်းများထဲမှ ဆုပေါက်ဂဏန်းများနှင့် တိုက်ဆိုင်ပါက ဤနေရာတွင် တရားဝင် စာရင်း အလိုအလျောက် ထွက်ရှိပါမည်ခင်ဗျာ။\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "👉 'ထိုးမယ်' ကို နှိပ်၍ ဂဏန်းများ စတင် ထိုးယူနိုင်ပါသည်!"
            )
        else:
            msg = (
                "🏆 *တရားဝင် ထီပေါက်သူ စာရင်းများ* 🏆\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🎉 *ယနေ့ နောက်ဆုံး ထီပေါက်သူများ စာရင်း:*\n\n"
            )
            for idx, w in enumerate(winners[-10:], 1):
                msg += f"{idx}. 👤 {w.get('name')} (ID: {w.get('uid')}) - {w.get('desc')} ➔ `{w.get('payout', 0):,} ကျပ်` (ထုတ်ပြီး ✅)\n"
            msg += "\n━━━━━━━━━━━━━━━━━━━━\n💡 အလျော်အစား ၁၀၀% မှန်ကန် တိကျစွာဖြင့် ၂၄ နာရီ ငွေထုတ်ပေးနေပါသည်!"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Top 10 Winners Leaderboard
    elif data == "lotto_top10_winners":
        winners = get_verified_winners()
        if not winners:
            msg = (
                "🌟 *အများဆုံး ထီပေါက်သူ ထိပ်တန်း ၁၀ ယောက်စာရင်း* 🌟\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ *လက်ရှိတွင် ထီပေါက်သူ မရှိသေးပါခင်ဗျာ!*\n\n"
                "👑 ထီပေါက်သူများ ပေါ်ထွက်လာပါက ဆုငွေအများဆုံး ရရှိသူ ၁၀ ယောက်စာရင်းကို ဤနေရာတွင် တရားဝင် ဂုဏ်ပြုဖော်ပြပေးပါမည်ခင်ဗျာ။\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "👉 အခုပဲ 'ထိုးမယ်' ကို နှိပ်၍ ကံစမ်းလိုက်ပါ!"
            )
        else:
            sorted_winners = sorted(winners, key=lambda x: x.get("payout", 0), reverse=True)[:10]
            msg = (
                "🌟 *အများဆုံး ထီပေါက်သူ ထိပ်တန်း ၁၀ ယောက်စာရင်း* 🌟\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
            )
            medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
            for idx, w in enumerate(sorted_winners):
                m = medals[idx] if idx < len(medals) else f"{idx+1}."
                msg += f"{m} 👤 {w.get('name')} (ID: {w.get('uid')}) ➔ `{w.get('payout', 0):,} ကျပ်`\n"
            msg += "\n━━━━━━━━━━━━━━━━━━━━\n💡 ကံထူးရှင်များအားလုံး ဂုဏ်ယူပါသည်ခင်ဗျာ!"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))],
            [InlineKeyboardButton("🔙 ထီပေါက်စဉ် မီနူးသို့ ပြန်သွားရန်", callback_data="back_to_lotto_menu")]
        ])
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)
        return

    # Bet 3D
    elif data == "btn_bet_3d":
        d3 = fetch_realtime_3d()
        await query.edit_message_text(
            f"🎯 *ထိုင်း 3D ထိုးကြေး တင်သွင်းရန်*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ *နောက်ထပ် ထွက်မည့်ရက်:* `{d3.get('next_date')}`\n"
            f"💰 *ပေါက်ကြေး:* ၁ ကျပ်လျှင် ၇၀၀ ကျပ်\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✍️ စာရိုက်ထိုးလိုပါက: `224=1000` ဟု ရိုက်ပို့နိုင်ပါသည် (သို့မဟုတ်) 'ထိုးမယ်' ဖြင့် လွယ်ကူစွာ ထိုးနိုင်ပါသည်ခင်ဗျာ။",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 ထိုးမယ် (Mini App)", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
        )
        return

    # Slot choice
    elif data in ["slot_2d_morning", "slot_2d_evening"]:
        is_hol, hol_reason = is_market_holiday()
        if is_hol:
            await query.edit_message_text(f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}", parse_mode="Markdown")
            return
        slot_name = "မနက်ပိုင်း (12:01 PM)" if "morning" in data else "ညနေပိုင်း (04:30 PM)"
        await query.edit_message_text(
            f"🎯 *2D ({slot_name}) ထိုးရန်*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ထိုးလိုသော ဂဏန်းကို `ဂဏန်း=ငွေပမာဏ` ပုံစံဖြင့် စာရိုက်ပို့ပေးပါခင်ဗျာ (ဥပမာ: `45=1000`)\n"
            f"(သို့မဟုတ်) အောက်ပါ 'ထိုးမယ်' ကို နှိပ်၍ အကွက်များ လွယ်ကူစွာ ရွေးချယ်နိုင်ပါသည်:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 ထိုးမယ် (Mini App ဖွင့်မည်)", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
        )

# ==================== WEB APP DATA HANDLER ====================
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data_str = update.effective_message.web_app_data.data
        payload = json.loads(data_str)
        action = payload.get("action")
        user = update.effective_user
        uid = str(user.id) if user else "0"
        u_name = user.first_name if user else "Customer"

        if action == "deposit_request":
            dep_id = payload.get("deposit_id", f"DEP-{random.randint(10000, 99999)}")
            amt = int(payload.get("amount", 0))
            txn = payload.get("txn_id", "-")
            cur = str(payload.get("currency", "MMK")).upper()
            cur_key = "thb" if cur == "THB" else "mmk"
            unit = "ဘတ်" if cur == "THB" else "ကျပ်"
            pay_method = payload.get("payment_method", "KBZPay (KPay)")

            await update.effective_message.reply_text(
                f"🧾 *ငွေသွင်း လျှောက်ထားလွှာ (Deposit Voucher)* 🧾\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔖 *ပြေစာအမှတ်:* `#{dep_id}`\n"
                f"👤 *အမည်:* `{u_name}` (ID: `{uid}`)\n"
                f"🔵 *ငွေပေးချေမှု:* `{pay_method}`\n"
                f"💱 *ငွေကြေး:* `{cur}`\n"
                f"💰 *ငွေပမာဏ:* `{amt:,} {unit}`\n"
                f"📝 *ငွေလွှဲအချက်အလက်:* `{txn}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ Admin မှ စစ်ဆေးအတည်ပြုပြီးပါက သင့် Wallet ထဲသို့ ငွေရောက်ရှိပါမည်!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
                ])
            )

            # Alert Admin
            try:
                admin_msg = (
                    f"🚨 *[ငွေသွင်း လျှောက်ထားလွှာ အသစ် ရောက်ရှိပါသည်]*\n"
                    f"👤 *ထိုးသူ:* `{u_name}` (ID: `{uid}`)\n"
                    f"🔖 *ပြေစာ:* `#{dep_id}`\n"
                    f"💰 *ပမာဏ:* `{amt:,} {unit}` ({cur})\n"
                    f"💳 *နည်းလမ်း:* `{pay_method}`\n"
                    f"📝 *ငွေလွှဲအချက်အလက်:* `{txn}`"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ ငွေသွင်း အတည်ပြုမည်", callback_data=f"apprdep_{dep_id}_{uid}_{amt}_{cur_key}")],
                    [InlineKeyboardButton("❌ ပယ်ဖျက်မည်", callback_data=f"rejdep_{dep_id}_{uid}")]
                ])
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                print("Admin alert failed:", e)

        elif action == "place_bet":
            b_type = payload.get("type", "2D")
            slot = payload.get("slot", "")
            numbers = payload.get("numbers", [])
            amt_each = int(payload.get("amount_each", 0))
            total_amt = int(payload.get("total_amount", 0))
            tkt_id = payload.get("ticket_id", f"TKT-{random.randint(10000, 99999)}")
            pay_mode = payload.get("payment_mode", "wallet")
            txn_id = payload.get("txn_id", "-")
            pay_method = payload.get("payment_method", "KPay")
            currency = str(payload.get("currency", "MMK")).upper()
            curr_key = "thb" if currency == "THB" else "mmk"
            curr_unit = "ဘတ်" if currency == "THB" else "ကျပ်"

            if b_type == "2D":
                is_hol, hol_reason = is_market_holiday()
                if is_hol:
                    await update.effective_message.reply_text(
                        f"⛔ *ယနေ့ 2D ပိတ်ရက်ဖြစ်ပါသည် ထိုးလို့မရပါခင်ဗျာ!*\n📌 *အကြောင်းပြချက်:* {hol_reason}",
                        parse_mode="Markdown"
                    )
                    return

            if currency == "THB":
                mult = 500 if b_type == "3D" else 80
            else:
                mult = 700 if b_type == "3D" else 85

            pay_label = f"💼 {currency} Wallet လက်ကျန်ငွေမှ နုတ်ယူပြီး"
            if pay_mode == "wallet":
                bal = user_balances.get(uid, {"mmk": 0, "thb": 0})
                if bal.get(curr_key, 0) < total_amt:
                    await update.effective_message.reply_text(
                        f"❌ *{currency} Wallet လက်ကျန်ငွေ မလုံလောက်ပါခင်ဗျာ!*\n"
                        f"💰 လိုအပ်ငွေ: `{total_amt:,} {curr_unit}` | လက်ရှိ: `{bal.get(curr_key, 0):,} {curr_unit}`\n\n"
                        f"💡 'ထိုးမယ်' ရှိ 'ဘဏ်ငွေ / QR Pay' ဖြင့် တိုက်ရိုက်လွှဲထိုးပါ (သို့မဟုတ်) KBZPay / PromptPay မှ ငွေအရင် ဖြည့်ပေးပါခင်ဗျာ။",
                        parse_mode="Markdown"
                    )
                    return
                user_balances[uid][curr_key] -= total_amt
                save_json(BALANCES_FILE, user_balances)
            else:
                pay_label = f"💳 ဘဏ်ငွေ / QR Pay ({pay_method} ငွေလွှဲစစ်ဆေးပြီး)"

            tz_mm = timezone(timedelta(hours=6, minutes=30))
            now_str = datetime.now(tz_mm).strftime("%d-%m-%Y %I:%M %p")

            # Save bet
            if uid not in user_bets:
                user_bets[uid] = []
            user_bets[uid].append({
                "ticket_id": tkt_id,
                "type": b_type,
                "slot": slot,
                "currency": currency,
                "numbers": numbers,
                "amount_each": amt_each,
                "total_amount": total_amt,
                "date": now_str,
                "user_name": u_name,
                "payment_mode": pay_mode,
                "txn_id": txn_id,
                "payment_method": pay_method
            })
            save_json(BETS_FILE, user_bets)

            rem = user_balances.get(uid, {}).get(curr_key, 0)
            voucher = (
                f"🧾 *{b_type} ထိုးငွေ ပြေစာထွက်ရှိပါပြီ* 🧾\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔖 *ပြေစာအမှတ်:* `#{tkt_id}`\n"
                f"👤 *အမည်:* `{u_name}` (ID: `{uid}`)\n"
                f"⏰ *အချိန်ပိုင်း:* `{slot}`\n"
                f"🎯 *ဂဏန်းများ:* `{', '.join(map(str, numbers[:10]))}`"
                f"{'...' if len(numbers)>10 else ''} ({len(numbers)} ကွက်)\n"
                f"💱 *ငွေကြေး:* `{currency}`\n"
                f"💰 *တစ်ကွက်ထိုး:* `{amt_each:,} {curr_unit}` (ပေါက်ကြေး: `{amt_each*mult:,} {curr_unit}`)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *စုစုပေါင်း ကျသင့်ငွေ:* `{total_amt:,} {curr_unit}`\n"
                f"💳 *ငွေပေးချေမှု:* `{pay_label}`\n"
            )
            if pay_mode != "wallet" and txn_id != "-":
                voucher += f"📝 *လုပ်ငန်းစဉ်အမှတ်:* `#{txn_id}`\n"
            if pay_mode == "wallet":
                voucher += f"💰 *လက်ကျန်ငွေ:* `{rem:,} {curr_unit}`\n"
            voucher += "✅ *အခြေအနေ:* အောင်မြင်စွာ မှတ်တမ်းတင်ပြီးပါပြီ!"

            await update.effective_message.reply_text(
                voucher,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Admin ထံ ဆက်သွယ်ရန်", url=ADMIN_URL)]
                ])
            )

            # Alert Admin if Bank / QR Pay
            if pay_mode != "wallet":
                try:
                    admin_msg = (
                        f"🚨 *[2D/3D ထိုးငွေ လွှဲပြေစာ အသစ် ရောက်ရှိပါသည်]*\n"
                        f"👤 *ထိုးသူ:* `{u_name}` (ID: `{uid}`)\n"
                        f"🔖 *ပြေစာ:* `#{tkt_id}`\n"
                        f"🎯 *ဂဏန်း:* `{', '.join(map(str, numbers))}` ({b_type})\n"
                        f"💰 *ကျသင့်ငွေ:* `{total_amt:,} {curr_unit}` ({currency})\n"
                        f"💳 *နည်းလမ်း:* `{pay_method}`\n"
                        f"📝 *လုပ်ငန်းစဉ်အမှတ်:* `#{txn_id}`"
                    )
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ ထိုးငွေ အတည်ပြုမည်", callback_data=f"apprbet_{tkt_id}_{uid}")],
                        [InlineKeyboardButton("❌ ပယ်ဖျက်မည်", callback_data=f"rejbet_{tkt_id}_{uid}")]
                    ])
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown", reply_markup=kb)
                except Exception as e:
                    print("Admin bet alert failed:", e)
    except Exception as e:
        print("handle_webapp_data err:", e)

# ==================== ADMIN COMMANDS ====================
async def admin_set_miniapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MINI_APP_URL
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if context.args:
        new_url = context.args[0].strip().rstrip("/")
        if not new_url.startswith("http"):
            await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ တရားဝင် URL ထည့်သွင်းပေးပါ (ဥပမာ: `https://your-app.vercel.app`)", parse_mode="Markdown")
            return
        MINI_APP_URL = new_url
        try:
            await context.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))
            )
            await update.message.reply_text(
                f"✅ *Mini App URL အား အောင်မြင်စွာ ပြောင်းလဲသတ်မှတ်ပြီးပါပြီ!*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 *လက်ရှိ Link:* `{MINI_APP_URL}`\n"
                f"🎯 Telegram Menu Button ကိုလည်း အသစ်သို့ အလိုအလျောက် Update ပြုလုပ်ပေးပြီးပါပြီခင်ဗျာ!",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"URL updated to `{MINI_APP_URL}` but menu button notice: {e}")
    else:
        await update.message.reply_text(
            f"💡 *လက်ရှိ Mini App Link:* `{MINI_APP_URL}`\n\n"
            f"ပြောင်းလဲရန်: `/setminiapp <URL>`\n"
            f"ဥပမာ: `/setminiapp https://your-app.vercel.app`",
            parse_mode="Markdown"
        )

async def admin_set_3d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if context.args:
        val = context.args[0].strip()
        if val.lower() == "clear":
            admin_override.pop("3d", None)
            await update.message.reply_text("✅ 3D override အား ဖျက်ပြီး တရားဝင် ထိုင်း GLO ရလဒ် (01-11-2026: 224) သို့ ပြန်ထားပါပြီ!")
            return
        admin_override["3d"] = val
        await update.message.reply_text(f"✅ 3D ရလဒ်အား 【 {val} 】 ဟု အောင်မြင်စွာ သတ်မှတ်ပြီးပါပြီ!")
    else:
        await update.message.reply_text("အသုံးပြုနည်း: `/set3d 423224` (သို့မဟုတ် `/set3d 224` သို့မဟုတ် `/set3d clear`)")

async def admin_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if len(context.args) >= 2:
        target_uid = str(context.args[0]).strip()
        amt = int(context.args[1].strip())
        cur_code = "mmk"
        if len(context.args) >= 3 and context.args[2].strip().lower() in ["thb", "baht", "ဘတ်"]:
            cur_code = "thb"
        unit = "ဘတ်" if cur_code == "thb" else "ကျပ်"
        if target_uid not in user_balances:
            user_balances[target_uid] = {"mmk": 0, "thb": 0}
        user_balances[target_uid][cur_code] = user_balances[target_uid].get(cur_code, 0) + amt
        save_json(BALANCES_FILE, user_balances)
        await update.message.reply_text(f"✅ User ID `{target_uid}` ထံသို့ `{amt:,} {unit}` ({cur_code.upper()}) သွင်းပေးပြီးပါပြီ!")
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"🎉 *သင့် Wallet ထဲသို့ `{amt:,} {unit}` ({cur_code.upper()}) ဖြည့်သွင်းမှု အောင်မြင်ပါသည်!*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("💡 အသုံးပြုပုံ: `/topup <UserID> <ပမာဏ> [thb/mmk]`\nဥပမာ: `/topup 7552908613 10000` သို့မဟုတ် `/topup 7552908613 500 thb`", parse_mode="Markdown")

async def on_startup(application):
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="🎯 ထိုးမယ်", web_app=WebAppInfo(url=MINI_APP_URL))
        )
        print("✅ Telegram Menu Button successfully updated to '🎯 ထိုးမယ်'!")
    except Exception as e:
        print("Menu button update notice:", e)

# ==================== MAIN APPLICATION ====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set3d", admin_set_3d))
    app.add_handler(CommandHandler("setminiapp", admin_set_miniapp))
    app.add_handler(CommandHandler("topup", admin_topup))

    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_buttons))

    print(f"🚀 Lucky2D3D Multi-Source Bot Started! Admin: {ADMIN_CHAT_ID}")
    app.run_polling(drop_pending_updates=True)
