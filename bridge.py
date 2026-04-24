import os
import requests
import time

from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate
)

# =============================
# خواندن توکن‌ها از محیط (ENV)
# =============================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BALE_TOKEN = os.environ.get("BALE_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")  # بدون @

if not TELEGRAM_TOKEN or not BALE_TOKEN or not TELEGRAM_BOT_USERNAME:
    raise Exception("Missing env variables! (TELEGRAM_TOKEN, BALE_TOKEN, TELEGRAM_BOT_USERNAME)")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
TG_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/"

BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"


# ==========================================================
# دکمه‌های تلگرام
# ==========================================================
TG_KEYBOARD = {
    "keyboard": [
        [{"text": "قطع اتصال"}],
        [{"text": "ارسال فایل"}, {"text": "ارسال گیف / استیکر"}]
    ],
    "resize_keyboard": True
}

# ==========================================================
# دکمه‌های بله
# ==========================================================
BALE_KEYBOARD = {
    "keyboard": [
        [{"text": "قطع اتصال"}],
        [{"text": "ارسال فایل"}, {"text": "ارسال گیف / استیکر"}]
    ],
    "resize_keyboard": True
}


# ==========================================================
# Telegram send helpers
# ==========================================================
def tg_send_text(chat_id, text):
    requests.post(
        TG_API + "sendMessage",
        json={"chat_id": chat_id, "text": text, "reply_markup": TG_KEYBOARD}
    )


def tg_send_file(chat_id, file_bytes, file_name="file", caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"document": (file_name, file_bytes)}
    requests.post(TG_API + "sendDocument", data=data, files=files)


def tg_send_photo(chat_id, file_bytes, caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"photo": ("photo.jpg", file_bytes)}
    requests.post(TG_API + "sendPhoto", data=data, files=files)


def tg_send_video(chat_id, file_bytes, caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"video": ("video.mp4", file_bytes)}
    requests.post(TG_API + "sendVideo", data=data, files=files)


# ==========================================================
# Bale send helpers
# ==========================================================
def bale_send_text(chat_id, text):
    requests.post(
        BALE_API + "sendMessage",
        json={"chat_id": chat_id, "text": text, "reply_markup": BALE_KEYBOARD}
    )


def bale_send_file(chat_id, file_bytes, file_name="file", caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"file": (file_name, file_bytes)}
    requests.post(BALE_API + "sendFile", data=data, files=files)


def bale_send_photo(chat_id, file_bytes, caption=None):
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    files = {"photo": ("photo.jpg", file_bytes)}
    requests.post(BALE_API + "sendPhoto", data=data, files=files)


# ==========================================================
# Polling loops
# ==========================================================
def telegram_polling_loop():
    print("Telegram loop started.")
    offset = None
    while True:
        try:
            updates = requests.get(TG_API + "getUpdates",
                                   params={"timeout": 20, "offset": offset}).json()

            for upd in updates.get("result", []):
                offset = upd["update_id"] + 1
                handle_telegram_update(upd)

        except Exception as e:
            print("TG loop error:", e)
        time.sleep(1)


def bale_polling_loop():
    print("Bale loop started.")
    offset = None
    while True:
        try:
            r = requests.get(BALE_API + "getUpdates",
                             params={"timeout": 20, "offset": offset}).json()

            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_bale_update(upd)

        except Exception as e:
            print("Bale loop error:", e)
        time.sleep(1)


# ==========================================================
# Telegram handler
# ==========================================================
def handle_telegram_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # ---------------- /start TOKEN ----------------
    if "text" in msg and msg["text"].startswith("/start "):
        token = msg["text"].split(" ", 1)[1].strip()
        if activate_link(token, chat_id):
            pair = get_pair(token)
            bale_send_text(pair["bale_user_id"], "اتصال با تلگرام برقرار شد ✓")
            tg_send_text(chat_id, "اتصال شما با بله برقرار شد ✓")
        else:
            tg_send_text(chat_id, "لینک نامعتبر یا منقضی است.")
        return

    # ---------------- قطع اتصال ----------------
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_telegram(chat_id)
        if token:
            pair = get_pair(token)
            deactivate(token)
            tg_send_text(chat_id, "اتصال قطع شد.")
            bale_send_text(pair["bale_user_id"], "اتصال توسط تلگرام قطع شد.")
        return

    # ---------------- پیام به بله ----------------
    token = get_link_by_telegram(chat_id)
    if not token:
        tg_send_text(chat_id, "هنوز به کاربر بله متصل نیستید!")
        return

    pair = get_pair(token)
    bale_user = pair["bale_user_id"]

    # ---- متن ----
    if "text" in msg:
        bale_send_text(bale_user, msg["text"])
        return

    # ---- انواع فایل ----
    file_id = None
    file_type = None

    if "photo" in msg:
        file_id = msg["photo"][-1]["file_id"]
        file_type = "photo"

    elif "document" in msg:
        file_id = msg["document"]["file_id"]
        file_type = "document"

    elif "video" in msg:
        file_id = msg["video"]["file_id"]
        file_type = "video"

    elif "audio" in msg:
        file_id = msg["audio"]["file_id"]
        file_type = "audio"

    elif "animation" in msg:
        file_id = msg["animation"]["file_id"]
        file_type = "gif"

    elif "sticker" in msg:
        file_id = msg["sticker"]["file_id"]
        file_type = "sticker"

    elif "voice" in msg:
        file_id = msg["voice"]["file_id"]
        file_type = "voice"

    elif "video_note" in msg:
        file_id = msg["video_note"]["file_id"]
        file_type = "video_note"

    if file_id:
        file_path = requests.get(
            TG_API + "getFile", params={"file_id": file_id}
        ).json()["result"]["file_path"]

        file_bytes = requests.get(TG_FILE + file_path).content

        # ارسال فایل به بله
        bale_send_file(bale_user, file_bytes, file_name=file_path)
        return


# ==========================================================
# Bale handler
# ==========================================================
def handle_bale_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # ---------------- /start ----------------
    if "text" in msg and msg["text"] == "/start":
        token = get_link_by_bale(chat_id)
        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"
        bale_send_text(chat_id, f"برای اتصال به تلگرام روی لینک زیر بزن:\n{tg_link}")
        return

    # ---------------- قطع اتصال ----------------
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_bale(chat_id)
        if token:
            pair = get_pair(token)
            deactivate(token)
            bale_send_text(chat_id, "اتصال قطع شد.")
            if pair["tg_user_id"]:
                tg_send_text(pair["tg_user_id"], "اتصال توسط بله قطع شد.")
        return

    # ---------------- ارسال پیام ----------------
    token = get_link_by_bale(chat_id)
    if not token:
        bale_send_text(chat_id, "هنوز اتصال تلگرام شما فعال نیست.")
        return

    pair = get_pair(token)
    tg_user = pair["tg_user_id"]

    if not tg_user:
        bale_send_text(chat_id, "هنوز در تلگرام لینک را استارت نکرده‌اید.")
        return

    # ---- متن ----
    if "text" in msg:
        tg_send_text(tg_user, msg["text"])
        return

    # ---- فایل ----
    if "file_id" in msg:
        file_id = msg["file_id"]

        file_info = requests.get(
            BALE_API + "getFile", params={"file_id": file_id}
        ).json()["result"]

        file_bytes = requests.get(file_info["file_url"]).content

        tg_send_file(tg_user, file_bytes, file_name=file_info.get("file_name", "file"))
        return
