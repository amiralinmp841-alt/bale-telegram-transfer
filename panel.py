# panel.py
import os
import re
import time
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
# FSM STATE
# =============================

ADMIN_STATES = {}  # {admin_id: {"step": ..., "data": {...}}}

# =============================
# Utils
# =============================

def is_admin(user_id):
    return user_id == ADMIN_BALE_ID


def send(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    requests.post(BALE_API + "sendMessage", json=payload)


# =============================
# Data Store (temporary)
# =============================
# 🔴 فعلاً در حافظه — در مرحله‌های بعدی میره DB + بکاپ

KEYS = {}  
# structure:
# key_name: {
#   volume: int,
#   expire: int,
#   max_users: int,
#   created_at: int
# }

# =============================
# Admin Handler
# =============================

def handle_admin_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if not is_admin(chat_id):
        return False

    state = ADMIN_STATES.get(chat_id)

    # ==================================
    # FSM STEPS
    # ==================================

    if state:
        step = state["step"]

        # -------- Step 1: Key Name --------
        if step == "WAIT_KEY_NAME":
            if not re.match(r"^key_[a-zA-Z0-9]{5,}$", text):
                send(chat_id, "❌ فرمت کلید اشتباه است\nمثال: key_abc123")
                return True

            if text in KEYS:
                send(chat_id, "❌ این کلید قبلاً وجود دارد")
                return True

            state["data"]["key"] = text
            state["step"] = "WAIT_VOLUME"
            send(chat_id, "📦 حجم مجاز را وارد کنید (MB)")
            return True

        # -------- Step 2: Volume --------
        if step == "WAIT_VOLUME":
            if not text.isdigit():
                send(chat_id, "❌ فقط عدد وارد کنید (MB)")
                return True

            state["data"]["volume"] = int(text)
            state["step"] = "WAIT_EXPIRE"
            send(chat_id, "⏳ مدت انقضا را وارد کنید (ساعت)")
            return True

        # -------- Step 3: Expire --------
        if step == "WAIT_EXPIRE":
            if not text.isdigit():
                send(chat_id, "❌ فقط عدد وارد کنید (ساعت)")
                return True

            hours = int(text)
            state["data"]["expire"] = int(time.time()) + hours * 3600
            state["step"] = "WAIT_MAX_USERS"
            send(chat_id, "👥 تعداد کاربران مجاز را وارد کنید")
            return True

        # -------- Step 4: Max Users --------
        if step == "WAIT_MAX_USERS":
            if not text.isdigit():
                send(chat_id, "❌ فقط عدد وارد کنید")
                return True

            data = state["data"]

            KEYS[data["key"]] = {
                "volume": data["volume"],
                "expire": data["expire"],
                "max_users": int(text),
                "created_at": int(time.time())
            }

            ADMIN_STATES.pop(chat_id)

            send(
                chat_id,
                f"✅ رمز ساخته شد:\n\n"
                f"🔑 {data['key']}\n"
                f"📦 حجم: {data['volume']} MB\n"
                f"⏳ انقضا: {int((data['expire'] - time.time())/3600)} ساعت\n"
                f"👥 کاربران: {text}",
                ADMIN_KEYS_KEYBOARD
            )
            return True

    # ==================================
    # Normal Admin Commands
    # ==================================

    if text == "/start":
        send(chat_id, "✅ به پنل مدیریت خوش آمدید", ADMIN_MAIN_KEYBOARD)
        return True

    if text == "مدیریت رمز ها":
        send(chat_id, "🔐 مدیریت رمز ها", ADMIN_KEYS_KEYBOARD)
        return True

    if text == "افزودن رمز":
        ADMIN_STATES[chat_id] = {"step": "WAIT_KEY_NAME", "data": {}}
        send(chat_id, "🔑 نام رمز را وارد کنید\nمثال: key_abc123")
        return True

    if text == "بازگشت":
        ADMIN_STATES.pop(chat_id, None)
        send(chat_id, "بازگشت به منوی اصلی", ADMIN_MAIN_KEYBOARD)
        return True

    # سایر دکمه‌ها فعلاً ignore
    return True
