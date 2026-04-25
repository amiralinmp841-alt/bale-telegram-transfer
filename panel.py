# panel.py
import os
from bale import InlineKeyboardMarkup, InlineKeyboardButton

# =====================
# Admin Config
# =====================
ADMIN_BALE_ID = int(os.environ.get("ADMIN_BALE_ID", 0))


# =====================
# Utils
# =====================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_BALE_ID


# =====================
# Keyboards
# =====================
def admin_main_menu():
    keyboard = [
        [InlineKeyboardButton("مدیریت رمز ها", callback_data="admin_keys")],
        [InlineKeyboardButton("مدیریت کاربران", callback_data="admin_users")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_keys_menu():
    keyboard = [
        [InlineKeyboardButton("افزودن رمز", callback_data="key_add")],
        [InlineKeyboardButton("حذف رمز", callback_data="key_remove")],
        [InlineKeyboardButton("رمز های فعال", callback_data="key_active")],
        [InlineKeyboardButton("رمز های غیر فعال", callback_data="key_inactive")]
    ]
    return InlineKeyboardMarkup(keyboard)


# =====================
# Handlers
# =====================
async def handle_start(bot, message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        # فعلاً هیچ کاری برای یوزر عادی انجام نمی‌دهیم
        await bot.send_message(
            chat_id=user_id,
            text="لطفاً رمز خود را جهت استفاده از ربات ارسال کنید."
        )
        return

    await bot.send_message(
        chat_id=user_id,
        text="✅ به پنل مدیریت خوش آمدید",
        reply_markup=admin_main_menu()
    )


async def handle_admin_callbacks(bot, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if not is_admin(user_id):
        return

    # ===== Main Menus =====
    if data == "admin_keys":
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=callback_query.message.message_id,
            text="🔐 مدیریت رمز ها",
            reply_markup=admin_keys_menu()
        )

    elif data == "admin_users":
        await bot.answer_callback_query(
            callback_query.id,
            text="مدیریت کاربران بعداً اضافه می‌شود"
        )

    # ===== Key Management (Skeleton) =====
    elif data == "key_add":
        await bot.send_message(
            chat_id=user_id,
            text="➕ افزودن رمز (مرحله‌ای) — بزودی فعال می‌شود"
        )

    elif data == "key_remove":
        await bot.send_message(
            chat_id=user_id,
            text="➖ حذف رمز — بزودی فعال می‌شود"
        )

    elif data == "key_active":
        await bot.send_message(
            chat_id=user_id,
            text="✅ لیست رمز های فعال — بزودی فعال می‌شود"
        )

    elif data == "key_inactive":
        await bot.send_message(
            chat_id=user_id,
            text="⛔ رمز های غیر فعال — فعلاً غیرفعال است"
        )
