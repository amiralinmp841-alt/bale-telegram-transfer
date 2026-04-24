import requests
import time
from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate
)

# ----------------------------
# ⚠ توکن ربات‌ها
# ----------------------------
TELEGRAM_TOKEN = "8231574639:AAHm25poUDviMPPYryiuTK_yEvO2AnjFJsw"
BALE_TOKEN = "1092992041:X2xu7Wg1oICAR54us-s-cTsT8E0YNXhpR5c"

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
TG_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/"

BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"


# ----------------------------
# ارسال پیام به Telegram
# ----------------------------
def tg_send_text(chat_id, text):
    requests.post(TG_API + "sendMessage", json={"chat_id": chat_id, "text": text})


def tg_send_file(chat_id, file_url, caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"document": requests.get(file_url).content}
    requests.post(TG_API + "sendDocument", data=data, files=files)


# ----------------------------
# ارسال پیام به Bale
# ----------------------------
def bale_send_text(chat_id, text):
    requests.post(BALE_API + "sendMessage", json={"chat_id": chat_id, "text": text})


def bale_send_file(chat_id, file_url, caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"file": requests.get(file_url).content}
    requests.post(BALE_API + "sendFile", data=data, files=files)


# ----------------------------
# Polling Telegram
# ----------------------------
def telegram_polling_loop():
    print("Telegram loop started.")
    offset = None

    while True:
        try:
            updates = requests.get(TG_API + "getUpdates", params={"timeout": 20, "offset": offset}).json()
            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                handle_telegram_update(upd)

        except Exception as e:
            print("TG loop error:", e)

        time.sleep(1)


# ----------------------------
# Polling Bale
# ----------------------------
def bale_polling_loop():
    print("Bale loop started.")
    offset = None

    while True:
        try:
            r = requests.get(BALE_API + "getUpdates", params={"timeout": 20, "offset": offset}).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_bale_update(upd)

        except Exception as e:
            print("Bale loop error:", e)

        time.sleep(1)


# -------------------------------------------------
# هندل پیام Telegram
# -------------------------------------------------
def handle_telegram_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # /start TOKEN
    if "text" in msg and msg["text"].startswith("/start "):
        token = msg["text"].split(" ", 1)[1].strip()
        if activate_link(token, chat_id):
            pair = get_pair(token)
            bale_send_text(pair["bale_user_id"], "اتصال با تلگرام برقرار شد ✓")
            tg_send_text(chat_id, "اتصال شما با بله برقرار شد ✓")
        else:
            tg_send_text(chat_id, "لینک نامعتبر یا منقضی است.")
        return

    # قطع اتصال
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_telegram(chat_id)
        if token:
            pair = get_pair(token)
            deactivate(token)
            tg_send_text(chat_id, "اتصال قطع شد.")
            bale_send_text(pair["bale_user_id"], "اتصال توسط تلگرام قطع شد.")
        return

    # ارسال پیام به بله
    token = get_link_by_telegram(chat_id)
    if not token:
        tg_send_text(chat_id, "هنوز به کاربر بله متصل نیستید!")
        return

    pair = get_pair(token)
    bale_user = pair["bale_user_id"]

    # متن
    if "text" in msg:
        bale_send_text(bale_user, msg["text"])
        return

    # فایل‌ها
    for t in ["photo", "document", "video", "audio"]:
        if t in msg:
            file_info = msg[t][-1] if t == "photo" else msg[t]
            file_id = file_info["file_id"]

            # گرفتن لینک فایل
            file_path = requests.get(TG_API + "getFile", params={"file_id": file_id}).json()["result"]["file_path"]
            file_url = TG_FILE + file_path

            bale_send_file(bale_user, file_url)
            return


# -------------------------------------------------
# هندل پیام Bale
# -------------------------------------------------
def handle_bale_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # /start → ایجاد لینک
    if "text" in msg and msg["text"] == "/start":
        token = get_link_by_bale(chat_id)
        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/Sbmu_Transporter_bot?start={token}"

        bale_send_text(chat_id, f"برای اتصال به تلگرام روی لینک زیر بزن:\n{tg_link}")
        return

    # قطع اتصال
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_bale(chat_id)
        if token:
            pair = get_pair(token)
            deactivate(token)
            bale_send_text(chat_id, "اتصال قطع شد.")
            if pair["tg_user_id"]:
                tg_send_text(pair["tg_user_id"], "اتصال توسط بله قطع شد.")
        return

    # ارسال پیام به تلگرام
    token = get_link_by_bale(chat_id)
    if not token:
        bale_send_text(chat_id, "هنوز اتصال تلگرام شما فعال نیست.")
        return

    pair = get_pair(token)
    tg_user = pair["tg_user_id"]

    if not tg_user:
        bale_send_text(chat_id, "هنوز در تلگرام لینک را استارت نکرده‌اید.")
        return

    # متن
    if "text" in msg:
        tg_send_text(tg_user, msg["text"])
        return

    # فایل‌ها
    if "file_id" in msg:
        file_id = msg["file_id"]

        file_info = requests.get(BALE_API + "getFile", params={"file_id": file_id}).json()["result"]
        file_url = file_info["file_url"]

        tg_send_file(tg_user, file_url)
