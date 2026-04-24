import os
import requests
import time

from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate
)

# =============================
# ENV VARIABLES
# =============================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BALE_TOKEN = os.environ.get("BALE_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")  # بدون @

if not TELEGRAM_TOKEN or not BALE_TOKEN or not TELEGRAM_BOT_USERNAME:
    raise Exception("Missing env variables!")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
TG_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/"
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"

# =============================
# KEYBOARDS
# =============================

TG_KEYBOARD = {
    "keyboard": [[{"text": "قطع اتصال"}]],
    "resize_keyboard": True
}

BALE_KEYBOARD = {
    "keyboard": [
        [{"text": "قطع اتصال"}],
        [{"text": "تغییر لینک اتصال"}]
    ],
    "resize_keyboard": True
}


# =============================
# Telegram send helpers
# =============================

def tg_send_text(chat_id, text):
    requests.post(TG_API + "sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": TG_KEYBOARD
    })


def tg_send_document(chat_id, file_bytes, file_name):
    requests.post(
        TG_API + "sendDocument",
        files={"document": (file_name, file_bytes)},
        data={"chat_id": chat_id}
    )


def tg_send_photo(chat_id, file_bytes):
    requests.post(
        TG_API + "sendPhoto",
        files={"photo": ("photo.jpg", file_bytes)},
        data={"chat_id": chat_id}
    )


def tg_send_video(chat_id, file_bytes):
    requests.post(
        TG_API + "sendVideo",
        files={"video": ("video.mp4", file_bytes)},
        data={"chat_id": chat_id}
    )


# =============================
# Bale send helpers
# =============================

def bale_send_text(chat_id, text):
    requests.post(BALE_API + "sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": BALE_KEYBOARD
    })


def bale_send_file(chat_id, file_bytes, filename):
    requests.post(
        BALE_API + "sendFile",
        files={"file": (filename, file_bytes)},
        data={"chat_id": chat_id}
    )


def bale_send_photo(chat_id, file_bytes):
    requests.post(
        BALE_API + "sendPhoto",
        files={"photo": ("photo.jpg", file_bytes)},
        data={"chat_id": chat_id}
    )


# =============================
# POLLING LOOPS
# =============================

def telegram_polling_loop():
    offset = None
    print("Telegram loop started")
    while True:
        try:
            r = requests.get(TG_API + "getUpdates",
                params={"timeout": 20, "offset": offset}).json()

            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_telegram_update(upd)

        except Exception as e:
            print("TG Error:", e)

        time.sleep(0.4)


def bale_polling_loop():
    offset = None
    print("Bale loop started")
    while True:
        try:
            r = requests.get(BALE_API + "getUpdates",
                params={"timeout": 20, "offset": offset}).json()

            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_bale_update(upd)

        except Exception as e:
            print("Bale Error:", e)

        time.sleep(0.4)


# =============================
# TELEGRAM HANDLER
# =============================

def handle_telegram_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # -----------------------------------------------
    # /start TOKEN
    # -----------------------------------------------
    if "text" in msg and msg["text"].startswith("/start "):
        token = msg["text"].split(" ", 1)[1].strip()

        if activate_link(token, chat_id):
            pair = get_pair(token)
            tg_send_text(chat_id, "اتصال با بله برقرار شد ✓")
            bale_send_text(pair["bale_user_id"], "اتصال با تلگرام برقرار شد ✓")
        else:
            tg_send_text(chat_id, "❌ لینک معتبر نیست.")

        return

    # -----------------------------------------------
    # قطع اتصال
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_telegram(chat_id)

        if token:
            pair = get_pair(token)
            deactivate(token)
            tg_send_text(chat_id, "اتصال قطع شد.")
            bale_send_text(pair["bale_user_id"], "اتصال توسط تلگرام قطع شد.")

        return

    # -----------------------------------------------
    # ارسال پیام/فایل
    # -----------------------------------------------
    token = get_link_by_telegram(chat_id)
    if not token:
        tg_send_text(chat_id, "❌ هنوز متصل نیستید.")
        return

    pair = get_pair(token)
    bale_user = pair["bale_user_id"]

    # ------ متن ------
    if "text" in msg:
        bale_send_text(bale_user, msg["text"])
        return

    # ------ فایل ------  
    file_id = None

    # تلگرام فایل‌های مختلف دارد:
    if "photo" in msg:
        file_id = msg["photo"][-1]["file_id"]

    elif "document" in msg:
        file_id = msg["document"]["file_id"]

    elif "video" in msg:
        file_id = msg["video"]["file_id"]

    elif "audio" in msg:
        file_id = msg["audio"]["file_id"]

    elif "animation" in msg:
        file_id = msg["animation"]["file_id"]

    elif "voice" in msg:
        file_id = msg["voice"]["file_id"]

    elif "sticker" in msg:
        file_id = msg["sticker"]["file_id"]

    if file_id:
        file_path = requests.get(
            TG_API + "getFile", params={"file_id": file_id}
        ).json()["result"]["file_path"]

        file_bytes = requests.get(TG_FILE + file_path).content
        bale_send_file(bale_user, file_bytes, file_path)
        return


# =============================
# BALE HANDLER
# =============================

def handle_bale_update(upd):
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]

    # -----------------------------------------------
    # /start = ایجاد یا دریافت لینک
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "/start":
        token = get_link_by_bale(chat_id)
        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"
        bale_send_text(chat_id, f"برای اتصال به تلگرام روی لینک زیر بزن:\n{tg_link}")
        return

    # -----------------------------------------------
    # تغییر لینک اتصال
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "تغییر لینک اتصال":
        token = create_link_for_bale(chat_id)
        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"
        bale_send_text(chat_id, f"🔄 لینک جدید:\n{tg_link}")
        return

    # -----------------------------------------------
    # قطع اتصال
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "قطع اتصال":
        token = get_link_by_bale(chat_id)
        if token:
            pair = get_pair(token)
            deactivate(token)
            bale_send_text(chat_id, "اتصال قطع شد.")
            if pair["tg_user_id"]:
                tg_send_text(pair["tg_user_id"], "اتصال توسط بله قطع شد.")
        return

    # -----------------------------------------------
    # ارسال پیام/فایل به تلگرام
    # -----------------------------------------------
    token = get_link_by_bale(chat_id)
    if not token:
        bale_send_text(chat_id, "❌ هنوز به تلگرام وصل نیستید.")
        return

    pair = get_pair(token)
    tg_user = pair["tg_user_id"]

    if not tg_user:
        bale_send_text(chat_id, "❌ هنوز در تلگرام استارت نزده‌اید.")
        return

    # ------ متن ------
    if "text" in msg:
        tg_send_text(tg_user, msg["text"])
        return

    # ------ فایل ------
    # بله همه فایل‌ها را اینجا می‌فرستد:
    if "file_id" in msg:
        info = requests.get(
            BALE_API + "getFile", params={"file_id": msg["file_id"]}
        ).json()["result"]

        file_bytes = requests.get(info["file_url"]).content
        tg_send_document(tg_user, file_bytes, info.get("file_name", "file"))
        return
