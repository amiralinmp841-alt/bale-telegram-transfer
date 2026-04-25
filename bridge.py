#bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py 
import os
import requests
import time
import threading

from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate,
    get_auto_delete, toggle_auto_delete   # ✔ اضافه شد
)
from panel import handle_admin_message, is_admin
from db_manager import join_key
from db_manager import user_has_valid_key
from db_manager import add_user_volume
from db_manager import get_user_key, get_key_used_volume, get_time_info
from db_manager import leave_key




# =============================
# ENV VARIABLES
# =============================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BALE_TOKEN = os.environ.get("BALE_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")  # بدون @
ADMIN_BALE_ID = int(os.environ.get("ADMIN_BALE_ID"))


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
        [{"text": "تغییر لینک و قطع اتصال"}],
        [{"text": "اشتراک من"}],
        [{"text": "حذف اتومات"}],   # ✔ جدید
        [{"text": "🚪 خروج از اشتراک"}]
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

def bale_send_text(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    requests.post(BALE_API + "sendMessage", json=payload)


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


def delete_after_delay(chat_id, message_id):
    time.sleep(20)
    try:
        requests.post(BALE_API + "deleteMessage", json={
            "chat_id": chat_id,
            "message_id": message_id
        })
    except:
        pass


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
        resp = requests.post(
            BALE_API + "sendMessage",
            json={"chat_id": bale_user, "text": msg["text"], "reply_markup": BALE_KEYBOARD}
        ).json()

        # 📊 ثبت مصرف حجم (متن)
        text_bytes = len(msg["text"].encode("utf-8"))
        add_user_volume(bale_user, text_bytes)
    
        # ✔ Auto Delete
        if get_auto_delete(token) == 1:
            mid = resp.get("result", {}).get("message_id")
            if mid:
                threading.Thread(target=delete_after_delay, args=(bale_user, mid), daemon=True).start()
    
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
            file_type = "gif"
    
        if not file_id:
            return
    
        file_info = requests.get(
            TG_API + "getFile",
            params={"file_id": file_id}
        ).json()["result"]
    
        file_path = file_info["file_path"]
        file_bytes = requests.get(TG_FILE + file_path).content
        # 📊 ثبت مصرف حجم فایل
        add_user_volume(bale_user, len(file_bytes))
        
    
        resp = None
    
        if file_type == "photo":
            resp = requests.post(
                BALE_API + "sendPhoto",
                files={"photo": ("photo.jpg", file_bytes)},
                data={"chat_id": bale_user, "caption": caption or ""}
            ).json()
    
        elif file_type == "video":
            resp = requests.post(
                BALE_API + "sendVideo",
                files={"video": ("video.mp4", file_bytes)},
                data={"chat_id": bale_user, "caption": caption or ""}
            ).json()
    
        elif file_type == "voice":
            resp = requests.post(
                BALE_API + "sendVoice",
                files={"voice": ("voice.ogg", file_bytes)},
                data={"chat_id": bale_user}
            ).json()
    
        elif file_type == "audio":
            resp = requests.post(
                BALE_API + "sendAudio",
                files={"audio": ("audio.mp3", file_bytes)},
                data={"chat_id": bale_user}
            ).json()
    
        elif file_type == "gif":
            resp = requests.post(
                BALE_API + "sendDocument",
                files={"document": ("file.gif", file_bytes)},
                data={"chat_id": bale_user, "caption": caption or ""}
            ).json()
    
        else:
            resp = requests.post(
                BALE_API + "sendDocument",
                files={"document": (file_path.split("/")[-1], file_bytes)},
                data={"chat_id": bale_user, "caption": caption or ""}
            ).json()
    
        # -------------------------
        # Auto Delete (20s)
        # -------------------------
        if get_auto_delete(token) == 1 and resp:
            mid = resp.get("result", {}).get("message_id")
            if mid:
                import threading
                threading.Thread(
                    target=delete_after_delay,
                    args=(bale_user, mid),
                    daemon=True
                ).start()
    
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
    text = msg.get("text", "").strip()

    # =============================
    # ADMIN PANEL HANDLER
    # =============================
    if is_admin(chat_id):
        handled = handle_admin_message(msg)
        if handled:
            return

    # -----------------------------------------------
    # ✅ اجازه ارسال کلید همیشه وجود دارد
    # -----------------------------------------------
    if text.startswith("key_"):
        # ❌ اگر لاگین است، اجازه ارسال کلید جدید ندارد
        if user_has_valid_key(chat_id):
            bale_send_text(
                chat_id,
                "⚠️ شما در حال حاضر لاگین هستید.\n\n"
                "ابتدا از اشتراک فعلی خارج شوید، سپس کلید جدید را ارسال کنید.",
                reply_markup=BALE_KEYBOARD
            )
            return
        success, message = join_key(text, chat_id)
    
        if not success:
            bale_send_text(chat_id, message, reply_markup={"remove_keyboard": True})
            return
    
        # ✅ لاگین موفق
        bale_send_text(chat_id, "✅ وارد شدید، در حال آماده‌سازی...", reply_markup=BALE_KEYBOARD)
        return

    # -----------------------------------------------
    # ❌ اگر لاگین نیست → قفل کامل + حذف دکمه‌ها
    # -----------------------------------------------
    if not user_has_valid_key(chat_id):
        bale_send_text(
            chat_id,
            "🔐 ابتدا کلید اشتراکت را ارسال کن.\n\n"
            "مثال:\n"
            "key_abc123",
            reply_markup={"remove_keyboard": True}
        )
        return

    # ===============================================
    # ✅ از اینجا به بعد: کاربر لاگین است
    # ===============================================

    # -----------------------------------------------
    # /start = ایجاد یا دریافت لینک
    # -----------------------------------------------
    if text == "/start":
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
    # ✔ دکمه جدید: حذف اتومات
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "حذف اتومات":
        token = get_link_by_bale(chat_id)

        if not token:
            bale_send_text(chat_id, "❌ هنوز وصل نیستید.")
            return

        new_state = toggle_auto_delete(token)

        if new_state == 1:
            bale_send_text(chat_id, "حذف اتومات فعال شد ✓")
        else:
            bale_send_text(chat_id, "حذف اتومات غیرفعال شد ✗")

        return

    # -----------------------------------------------
    # ✔ دکمه جدید: اشتراک من
    # -----------------------------------------------
    if "text" in msg and msg["text"] == "اشتراک من":
        key_name, key = get_user_key(chat_id)
    
        if not key:
            bale_send_text(chat_id, "❌ اشتراک فعالی برای شما یافت نشد.")
            return
    
        # -------- حجم --------
        total_volume = key.get("volume", 0)   # MB
        used_volume = get_key_used_volume(key)
        remaining_volume = round(max(0, total_volume - used_volume), 2)
    
        user_used = round(key["users"].get(str(chat_id), 0), 2)
    
        # -------- زمان (دقیقاً مثل ادمین) --------
        now = int(time.time())
        expire_ts = key.get("expire", 0)
        remaining = expire_ts - now
    
        if remaining <= 0:
            time_left = "منقضی شده"
        else:
            days = remaining // 86400
            hours = (remaining % 86400) // 3600
            minutes = (remaining % 3600) // 60
    
            time_left = ""
            if days:
                time_left += f"{days} روز "
            if hours:
                time_left += f"{hours} ساعت "
            if minutes:
                time_left += f"{minutes} دقیقه"
    
        # -------- کاربران --------
        current_users = len(key.get("users", {}))
        max_users = key.get("max_users", 1)
    
        text = f"""
    👤 **اشتراک من**
    
    🔑 **کلید:**
    `{key_name}`
    
    📦 **حجم اشتراک**
    • حجم کل: {total_volume} mb
    • مصرف کل: {used_volume} mb
    • 🔻 باقی‌مانده: {remaining_volume} mb
    
    👤 **مصرف شما**
    • {user_used} mb
    
    ⏳ **زمان اشتراک**
    • ⌛ باقی‌مانده: {time_left}
    
    👥 **کاربران**
    • کاربران متصل: {current_users}
    • حداکثر مجاز: {max_users}
    
    🟢 **وضعیت:** فعال ✅
    """
    
        bale_send_text(chat_id, text)
        return

    if text == "🚪 خروج از اشتراک":
        success, msg_text = leave_key(chat_id)
        bale_send_text(chat_id, msg_text, reply_markup={"remove_keyboard": True})
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
        text_bytes = len(msg["text"].encode("utf-8"))
        add_user_volume(chat_id, text_bytes)
        return

    # ------ FILE ------
    try:
        file_obj = None
        file_type = None
    
        if "photo" in msg:
            file_obj = msg["photo"]
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
            file_obj = msg["document"][-1]
            file_type = "document"
    
        elif "file" in msg:
            file_obj = msg["file"][-1]
            file_type = "document"
    
        if not file_obj or "file_id" not in file_obj:
            return
    
        file_id = file_obj["file_id"]
    
        info = requests.get(
            BALE_API + "getFile",
            params={"file_id": file_id}
        ).json()["result"]
    
        file_path = info["file_path"]
        file_name = info.get("file_name", "file.bin")
    
        file_url = f"https://tapi.bale.ai/file/bot{BALE_TOKEN}/{file_path}"
        file_bytes = requests.get(file_url).content
        add_user_volume(chat_id, len(file_bytes))
    
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
    
    except Exception as e:
        print("BALE → TG FILE ERROR:", e)
        bale_send_text(chat_id, "❌ ارسال فایل به تلگرام ناموفق بود.")
    
