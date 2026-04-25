# panel.py
import os
import requests

ADMIN_BALE_ID = int(os.environ.get("ADMIN_BALE_ID"))

BALE_TOKEN = os.environ.get("BALE_TOKEN")
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"


# =============================
# Keyboards
# =============================

ADMIN_MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "مدیریت رمز ها"}],
        [{"text": "مدیریت کاربران"}]
    ],
    "resize_keyboard": True
}

ADMIN_KEYS_KEYBOARD = {
    "keyboard": [
        [{"text": "افزودن رمز"}],
        [{"text": "حذف رمز"}],
        [{"text": "رمز های فعال"}],
        [{"text": "رمز های غیر فعال"}],
        [{"text": "بازگشت"}]
    ],
    "resize_keyboard": True
}


# =============================
# Utils
# =============================

def is_admin(user_id):
    return user_id == ADMIN_BALE_ID


def send_admin_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    requests.post(BALE_API + "sendMessage", json=payload)


# =============================
# Admin Handler
# =============================

def handle_admin_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if not is_admin(chat_id):
        return False  # یعنی ادمین نیست

    # -------------------------
    # /start
    # -------------------------
    if text == "/start":
        send_admin_message(
            chat_id,
            "✅ به پنل مدیریت خوش آمدید",
            ADMIN_MAIN_KEYBOARD
        )
        return True

    # -------------------------
    # مدیریت رمز ها
    # -------------------------
    if text == "مدیریت رمز ها":
        send_admin_message(
            chat_id,
            "🔐 مدیریت رمز ها:",
            ADMIN_KEYS_KEYBOARD
        )
        return True

    # -------------------------
    # دکمه‌ها (فعلاً اسکلت)
    # -------------------------
    if text == "افزودن رمز":
        send_admin_message(chat_id, "➕ بخش افزودن رمز بزودی فعال می‌شود")
        return True

    if text == "حذف رمز":
        send_admin_message(chat_id, "➖ بخش حذف رمز بزودی فعال می‌شود")
        return True

    if text == "رمز های فعال":
        send_admin_message(chat_id, "✅ نمایش رمز های فعال بزودی فعال می‌شود")
        return True

    if text == "رمز های غیر فعال":
        send_admin_message(chat_id, "⛔ این بخش فعلاً غیرفعال است")
        return True

    if text == "بازگشت":
        send_admin_message(
            chat_id,
            "بازگشت به منوی اصلی",
            ADMIN_MAIN_KEYBOARD
        )
        return True

    return True  # هر پیام ادمین هندل شود
