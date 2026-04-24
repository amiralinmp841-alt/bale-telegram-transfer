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

# ✔ کیبورد جدید بله (آپشن ۲)
BALE_KEYBOARD = {
    "keyboard": [
        [{"text": "دریافت لینک"}],
        [{"text": "تغییر لینک و قطع اتصال"}]
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


def tg_send_document(chat_id, file_bytes, file_name, caption=None):
    requests.post(
        TG_API + "sendDocument",
        files={"document": (file_name, file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def tg_send_photo(chat_id, file_bytes, caption=None):
    requests.post(
        TG_API + "sendPhoto",
        files={"photo": ("photo.jpg", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def tg_send_video(chat_id, file_bytes, caption=None):
    requests.post(
        TG_API + "sendVideo",
        files={"video": ("video.mp4", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def tg_send_audio(chat_id, file_bytes, caption=None):
    requests.post(
        TG_API + "sendAudio",
        files={"audio": ("audio.mp3", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def tg_send_voice(chat_id, file_bytes, caption=None):
    requests.post(
        TG_API + "sendVoice",
        files={"voice": ("voice.ogg", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
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


def bale_send_photo(chat_id, file_bytes, caption=None):
    requests.post(
        BALE_API + "sendPhoto",
        files={"photo": ("photo.jpg", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def bale_send_video(chat_id, file_bytes, caption=None):
    requests.post(
        BALE_API + "sendVideo",
        files={"video": ("video.mp4", file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )


def bale_send_voice(chat_id, file_bytes):
    requests.post(
        BALE_API + "sendVoice",
        files={"voice": ("voice.ogg", file_bytes)},
        data={"chat_id": chat_id}
    )


def bale_send_audio(chat_id, file_bytes):
    requests.post(
        BALE_API + "sendAudio",
        files={"audio": ("audio.mp3", file_bytes)},
        data={"chat_id": chat_id}
    )


def bale_send_document(chat_id, file_bytes, file_name, caption=None):
    requests.post(
        BALE_API + "sendDocument",
        files={"document": (file_name, file_bytes)},
        data={"chat_id": chat_id, "caption": caption or ""}
    )

# =============================
# POLLING LOOPS
# =============================

def telegram_polling_loop():
    offset = None
    print("Telegram loop started")
    while True:
        try:
            r = requests.get(
                TG_API + "getUpdates",
                params={"timeout": 20, "offset": offset}
            ).json()

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
            r = requests.get(
                BALE_API + "getUpdates",
                params={"timeout": 20, "offset": offset}
            ).json()

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

        pair = get_pair(token)
        if not pair or not pair["active"]:
            tg_send_text(chat_id, "❌ لینک معتبر نیست / منسوخ شده.")
            return

        activate_link(token, chat_id)
        tg_send_text(chat_id, "اتصال با بله برقرار شد ✓")
        bale_send_text(pair["bale_user_id"], "اتصال با تلگرام برقرار شد ✓")
        return

    # -----------------------------------------------
    # قطع اتصال (از تلگرام)
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
    pair = get_pair(token) if token else None

    if not pair or not pair["active"]:
        tg_send_text(chat_id, "❌ هنوز متصل نیستید.")
        return

    bale_user = pair["bale_user_id"]
    caption = msg.get("caption")

    # ------ TEXT ------
    if "text" in msg:
        bale_send_text(bale_user, msg["text"])
        return

    # ------ FILE ------
    try:
        file_id = None
        file_type = None

        if "photo" in msg:
            file_id = msg["photo"][-1]["file_id"]
            file_type = "photo"

        elif "video" in msg:
            file_id = msg["video"]["file_id"]
            file_type = "video"

        elif "voice" in msg:
            file_id = msg["voice"]["file_id"]
            file_type = "voice"

        elif "audio" in msg:
            file_id = msg["audio"]["file_id"]
            file_type = "audio"

        elif "document" in msg:
            file_id = msg["document"]["file_id"]
            file_type = "document"

        elif "animation" in msg:
            file_id = msg["animation"]["file_id"]
            file_type = "gif"   # ✔ ارسال گیف واقعی

        if not file_id:
            return

        file_info = requests.get(TG_API + "getFile", params={"file_id": file_id}).json()["result"]
        file_path = file_info["file_path"]
        file_bytes = requests.get(TG_FILE + file_path).content

        if file_type == "photo":
            bale_send_photo(bale_user, file_bytes, caption)
        elif file_type == "video":
            bale_send_video(bale_user, file_bytes, caption)
        elif file_type == "voice":
            bale_send_voice(bale_user, file_bytes)
        elif file_type == "audio":
            bale_send_audio(bale_user, file_bytes)
        elif file_type == "gif":
            bale_send_document(bale_user, file_bytes, "file.gif", caption)
        else:
            bale_send_document(bale_user, file_bytes, file_path.split("/")[-1], caption)

    except Exception:
        tg_send_text(chat_id, "❌ ارسال فایل به بله ناموفق بود. احتمالاً حجم بیش از حد است.")

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
    # ✔ دکمه جدید: دریافت لینک
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "دریافت لینک":
        token = get_link_by_bale(chat_id)

        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"
        bale_send_text(chat_id, f"لینک فعلی اتصال شما:\n{tg_link}")
        return

    # -----------------------------------------------
    # ✔ دکمه تلفیقی: تغییر لینک و قطع اتصال
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "تغییر لینک و قطع اتصال":

        old_token = get_link_by_bale(chat_id)

        if old_token:
            pair = get_pair(old_token)
            deactivate(old_token)

            if pair and pair["tg_user_id"]:
                tg_send_text(pair["tg_user_id"], "اتصال توسط بله قطع شد.")

        # ساخت لینک جدید
        new_token = create_link_for_bale(chat_id)
        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={new_token}"

        bale_send_text(chat_id, f"🔄 لینک جدید:\n{tg_link}")
        return

    # -----------------------------------------------
    # ارسال پیام/فایل به تلگرام
    # -----------------------------------------------
    token = get_link_by_bale(chat_id)
    pair = get_pair(token) if token else None

    if not pair or not pair["active"]:
        bale_send_text(chat_id, "❌ هنوز به تلگرام وصل نیستید.")
        return

    tg_user = pair["tg_user_id"]

    caption = msg.get("caption")

    # ------ TEXT ------
    if "text" in msg:
        tg_send_text(tg_user, msg["text"])
        return

    # ------ FILE ------
    try:
        file_obj = None
        file_type = None
        
        if "photo" in msg:
            file_obj = msg["photo"][-1]
            file_type = "photo"
        
        elif "video" in msg:
            file_obj = msg["video"]
            file_type = "video"
        
        elif "voice" in msg:
            file_obj = msg["voice"]
            file_type = "voice"
        
        elif "audio" in msg:
            file_obj = msg["audio"]
            file_type = "audio"
        
        elif "document" in msg:
            file_obj = msg["document"]
            file_type = "document"
        
        elif "file" in msg:
            file_obj = msg["file"]
            file_type = "document"
        
        

        if file_obj and "file_id" in file_obj:
            file_id = file_obj["file_id"]

            info = requests.get(BALE_API + "getFile", params={"file_id": file_id}).json()["result"]
            file_url = info["file_url"]
            file_name = info.get("file_name", "file")

            file_bytes = requests.get(file_url).content

            if file_type == "photo":
                tg_send_photo(tg_user, file_bytes, caption)
            
            elif file_type == "video":
                tg_send_video(tg_user, file_bytes, caption)
            
            elif file_type == "voice":
                tg_send_voice(tg_user, file_bytes)
            
            elif file_type == "audio":
                tg_send_audio(tg_user, file_bytes)
            
            else:
                tg_send_document(tg_user, file_bytes, file_name, caption)
            

    except Exception:
        bale_send_text(chat_id, "❌ ارسال فایل به تلگرام ناموفق بود. احتمالاً حجم فایل زیاد است.")
