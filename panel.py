# panel.py # panel.py # panel.py # panel.py # panel.py # panel.py # panel.py # panel.py # panel.py # panel.py 
import os
import re
import time
import requests
from db_manager import key_exists, add_key, get_active_keys, deactivate_key, get_inactive_keys

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

#KEYS = {}  
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

            if key_exists(text):
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

            add_key(
                data["key"],
                data["volume"],
                data["expire"],
                int(text)
            )
            

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

        if step == "WAIT_DELETE_KEY":
            if not key_exists(text):
                send(chat_id, "❌ چنین رمی وجود ندارد", ADMIN_KEYS_KEYBOARD)
                ADMIN_STATES.pop(chat_id, None)
                return True
        
            deactivate_key(text)
            ADMIN_STATES.pop(chat_id, None)
        
            send(
                chat_id,
                f"✅ رمز {text} حذف شد\n👥 تمام کاربران آن خارج شدند",
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

    if text == "حذف رمز":
        ADMIN_STATES[chat_id] = {"step": "WAIT_DELETE_KEY", "data": {}}
        send(chat_id, "🗑 نام رمز موردنظر برای حذف را وارد کنید\nمثال: key_abc123")
        return True
    
    # ✅ نمایش رمز های فعال
    if text == "رمز های فعال":
        active_keys = get_active_keys()

        if not active_keys:
            send(chat_id, "ℹ️ هیچ رمز فعالی وجود ندارد.", ADMIN_KEYS_KEYBOARD)
            return True

        now = int(time.time())
        message_parts = ["🔑 رمز های فعال:\n"]

        for key_name, info in active_keys.items():
            expire_ts = info.get("expire", 0)
            remaining = expire_ts - now

            # محاسبه زمان باقی‌مانده
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

            volume_limit = info.get("volume", 0)
            max_users = info.get("max_users", 0)
            users = info.get("users", {})

            active_users = len(users)
            total_used = sum(users.values()) if users else 0

            message_parts.append(
                f"\n🔑 {key_name}\n"
                f"⏳ زمان باقی‌مانده: {time_left}\n"
                f"📦 حجم کل: {volume_limit} MB\n"
                f"👥 کاربران: {active_users}/{max_users}\n"
                f"📊 مصرف کل: {total_used} MB\n"
                f"👤 کاربران متصل:"
            )

            if users:
                for user_id, used in users.items():
                    message_parts.append(f"  • user_{user_id}: {used} MB")
            else:
                message_parts.append("  • هیچ کاربری متصل نیست")

        send(chat_id, "\n".join(message_parts), ADMIN_KEYS_KEYBOARD)
        return True

    # 🚫 نمایش رمز های غیر فعال
    if text == "رمز های غیر فعال":
        inactive_keys = get_inactive_keys()
    
        if not inactive_keys:
            send(chat_id, "✅ هیچ رمز غیرفعالی وجود ندارد.", ADMIN_KEYS_KEYBOARD)
            return True
    
        now = int(time.time())
        message_parts = ["🚫 رمز های غیرفعال:\n"]
    
        for key_name, info in inactive_keys.items():
            expire_ts = info.get("expire", 0)
    
            if expire_ts <= now:
                expire_text = "⏳ منقضی شده"
            else:
                expire_text = "⛔ غیرفعال شده توسط ادمین"
    
            volume = info.get("volume", 0)
            max_users = info.get("max_users", 0)
            created_at = info.get("created_at", 0)
    
            created_time = time.strftime(
                "%Y-%m-%d %H:%M",
                time.localtime(created_at)
            ) if created_at else "نامشخص"
    
            message_parts.append(
                f"\n🔑 {key_name}\n"
                f"{expire_text}\n"
                f"📦 حجم کل: {volume} MB\n"
                f"👥 حداکثر کاربران: {max_users}\n"
                f"🕒 تاریخ ایجاد: {created_time}"
            )
    
        send(chat_id, "\n".join(message_parts), ADMIN_KEYS_KEYBOARD)
        return True
    

    if text == "بازگشت":
        ADMIN_STATES.pop(chat_id, None)
        send(chat_id, "بازگشت به منوی اصلی", ADMIN_MAIN_KEYBOARD)
        return True

    # سایر دکمه‌ها فعلاً ignore
    return True
