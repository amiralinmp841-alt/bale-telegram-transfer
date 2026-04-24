import os
import requests
import time
import threading

# bridge database
from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate,
    get_auto_delete, toggle_auto_delete
)

# panel database
from panel import (
    check_key_valid,
    assign_key_to_user,
    get_user_key,
    remove_user,
    update_usage
)

# =============================
# ENV
# =============================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BALE_TOKEN = os.environ.get("BALE_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")

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
        [{"text": "دریافت لینک"}],
        [{"text": "تغییر لینک و قطع اتصال"}],
        [{"text": "حذف اتومات"}],
        [{"text": "خروج"}]
    ],
    "resize_keyboard": True
}

# =============================
# SEND HELPERS
# =============================

def tg_send_text(chat_id, text):
    requests.post(TG_API + "sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": TG_KEYBOARD
    })


def bale_send_text(chat_id, text):
    requests.post(BALE_API + "sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "reply_markup": BALE_KEYBOARD
    })


# =============================
# AUTO DELETE
# =============================

def delete_after_delay(chat_id, message_id):
    time.sleep(20)

    try:
        requests.post(
            BALE_API + "deleteMessage",
            json={
                "chat_id": chat_id,
                "message_id": message_id
            }
        )
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

    # ---------------------------
    # start token
    # ---------------------------

    if "text" in msg and msg["text"].startswith("/start "):

        token = msg["text"].split(" ", 1)[1]

        pair = get_pair(token)

        if not pair or not pair["active"]:
            tg_send_text(chat_id, "❌ لینک نامعتبر است.")
            return

        activate_link(token, chat_id)

        tg_send_text(chat_id, "✅ اتصال برقرار شد")

        bale_send_text(
            pair["bale_user_id"],
            "✅ اتصال با تلگرام برقرار شد"
        )

        return

    # ---------------------------
    # disconnect
    # ---------------------------

    if "text" in msg and msg["text"] == "قطع اتصال":

        token = get_link_by_telegram(chat_id)

        if token:

            pair = get_pair(token)

            deactivate(token)

            tg_send_text(chat_id, "اتصال قطع شد")

            bale_send_text(
                pair["bale_user_id"],
                "اتصال توسط تلگرام قطع شد"
            )

        return

    # ---------------------------
    # forward messages
    # ---------------------------

    token = get_link_by_telegram(chat_id)

    pair = get_pair(token) if token else None

    if not pair or not pair["active"]:
        return

    bale_user = pair["bale_user_id"]

    if "text" in msg:

        resp = requests.post(
            BALE_API + "sendMessage",
            json={
                "chat_id": bale_user,
                "text": msg["text"]
            }
        ).json()

        if get_auto_delete(token):

            mid = resp.get("result", {}).get("message_id")

            if mid:

                threading.Thread(
                    target=delete_after_delay,
                    args=(bale_user, mid),
                    daemon=True
                ).start()

        return


# =============================
# BALE HANDLER
# =============================

def handle_bale_update(upd):

    msg = upd.get("message")

    if not msg:
        return

    chat_id = msg["chat"]["id"]

    text = msg.get("text")

    # --------------------------------
    # check login key
    # --------------------------------

    user_key = get_user_key(chat_id)

    if not user_key:

        if not text:
            bale_send_text(chat_id, "🔑 لطفا ابتدا کلید خود را ارسال کنید.")
            return

        if not check_key_valid(text):
            bale_send_text(chat_id, "❌ کلید نامعتبر است.")
            return

        assign_key_to_user(chat_id, text)

        bale_send_text(chat_id, "✅ ورود موفق")

        return

    # --------------------------------
    # logout
    # --------------------------------

    if text == "خروج":

        remove_user(chat_id)

        bale_send_text(chat_id, "از سیستم خارج شدید.")

        return

    # --------------------------------
    # start
    # --------------------------------

    if text == "/start":

        token = get_link_by_bale(chat_id)

        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"

        bale_send_text(
            chat_id,
            f"لینک اتصال:\n{tg_link}"
        )

        return

    # --------------------------------
    # دریافت لینک
    # --------------------------------

    if text == "دریافت لینک":

        token = get_link_by_bale(chat_id)

        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"

        bale_send_text(chat_id, tg_link)

        return

    # --------------------------------
    # toggle auto delete
    # --------------------------------

    if text == "حذف اتومات":

        token = get_link_by_bale(chat_id)

        new_state = toggle_auto_delete(token)

        if new_state:
            bale_send_text(chat_id, "✅ حذف اتومات فعال شد")
        else:
            bale_send_text(chat_id, "❌ حذف اتومات غیرفعال شد")

        return

    # --------------------------------
    # ارسال پیام به تلگرام
    # --------------------------------

    token = get_link_by_bale(chat_id)

    pair = get_pair(token)

    if not pair or not pair["active"]:

        bale_send_text(chat_id, "❌ هنوز به تلگرام وصل نیستید")

        return

    tg_user = pair["tg_user_id"]

    # text
    if "text" in msg:

        tg_send_text(tg_user, msg["text"])

        update_usage(chat_id, len(msg["text"].encode()))

        return

    # file
    try:

        file_obj = None

        if "photo" in msg:
            file_obj = msg["photo"]

        elif "video" in msg:
            file_obj = msg["video"]

        elif "document" in msg:
            file_obj = msg["document"]

        if not file_obj:
            return

        file_id = file_obj["file_id"]

        info = requests.get(
            BALE_API + "getFile",
            params={"file_id": file_id}
        ).json()["result"]

        file_path = info["file_path"]

        file_url = f"https://tapi.bale.ai/file/bot{BALE_TOKEN}/{file_path}"

        file_bytes = requests.get(file_url).content

        requests.post(
            TG_API + "sendDocument",
            files={"document": ("file", file_bytes)},
            data={"chat_id": tg_user}
        )

        update_usage(chat_id, len(file_bytes))

    except:

        bale_send_text(chat_id, "❌ ارسال فایل ناموفق بود")


# =============================
# POLLING
# =============================

def telegram_polling_loop():

    offset = None

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

            print("TG ERROR", e)

        time.sleep(0.3)


def bale_polling_loop():

    offset = None

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

            print("BALE ERROR", e)

        time.sleep(0.3)


# =============================
# MAIN
# =============================

def main():

    print("Bridge started")

    t1 = threading.Thread(target=telegram_polling_loop)
    t2 = threading.Thread(target=bale_polling_loop)

    t1.start()
    t2.start()

    t1.join()
    t2.join()


if __name__ == "__main__":
    main()
