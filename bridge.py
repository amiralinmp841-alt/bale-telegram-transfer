#bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py #bridge.py 
import os
import requests
import time
import threading
import json
from vip import start_telethon


from db_manager import (
    create_link_for_bale, get_link_by_bale, activate_link,
    get_link_by_telegram, get_pair, deactivate,
    get_auto_delete, toggle_auto_delete, join_key,
    user_has_valid_key, add_user_volume, get_user_key,
    get_key_used_volume, get_time_info, leave_key,
    make_backup, restore_backup, cleanup_old_backups
)
from panel import handle_admin_message, is_admin

from youtube import (
    is_youtube_url,
    youtube_search,
    youtube_suggestions,
    get_video_info,
    get_video_formats,
    download_video,
    split_video_ffmpeg,
    clean_temp_files,
    user_state,
    user_search_cache,
    user_download_cache,
    user_video_cache
)

from vip import (
    vip_search,
    vip_next_page,
    vip_get_video,
    vip_search_cache,
    vip_video_cache
)


# =============================
# ENV VARIABLES
# =============================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
BALE_TOKEN = os.environ.get("BALE_TOKEN")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")  # بدون @
ADMIN_BALE_ID = int(os.environ.get("ADMIN_BALE_ID"))

# این متغیرها را اینجا مقداردهی کن (یا بهتر است از os.environ استفاده کنی)
API_ID = int(os.environ.get("API_ID", 12345))  # به جای 12345 آیدی خودت را بگذار
API_HASH = os.environ.get("API_HASH", "your_hash_here")
USER_SESSION = os.environ.get("USER_SESSION", "user_session")
MEGASAVER_BOT = os.environ.get("MEGASAVER_BOT", "MegaSaverBot")



if not TELEGRAM_TOKEN or not BALE_TOKEN or not TELEGRAM_BOT_USERNAME:
    raise Exception("Missing env variables!")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
TG_FILE = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/"
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}/"
http = requests.Session()

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
        [{"text": "🔎 جست و جوی یوتیوب"}],
        [{"text": "🔎 سرچ VIP یوتیوب"}],            # ← جدید
        [{"text": "اشتراک من"}],
        [{"text": "حذف اتومات"}],
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

def process_video_download(chat_id, url, fmt_id):
    try:
        path = download_video(url, fmt_id, chat_id)
        if not path:
            bale_send_text(chat_id, "❌ خطا در دانلود.")
            return

        bale_send_text(chat_id, "✂️ در حال تقسیم فایل...")

        parts = split_video_ffmpeg(path, chat_id)
        if not parts:
            bale_send_text(chat_id, "❌ خطا در تقسیم.")
            clean_temp_files(chat_id)
            return

        total_sent_mb = 0

        for i, part in enumerate(parts, 1):
            size = os.path.getsize(part)
            size_mb = round(size / (1024*1024), 2)
            total_sent_mb += size_mb

            with open(part, "rb") as f:
                bale_send_video(chat_id, f.read(), caption=f"📦 پارت {i}")

        clean_temp_files(chat_id)

        bale_send_text(chat_id, f"✅ تکمیل شد.\n📦 حجم: {total_sent_mb}MB")

    except Exception as e:
        print("THREAD ERROR:", e)
        bale_send_text(chat_id, "❌ خطای داخلی.")

def process_get_formats(chat_id, url):

    try:
        formats = get_video_formats(url)

        if not formats:
            bale_send_text(chat_id, "❌ کیفیتی پیدا نشد.")
            return

        buttons = []

        for f in formats[:8]:
            text_btn = f"{f['quality']} - {round(f['size'],1)}MB"
            buttons.append([{
                "text": text_btn,
                "callback_data": f"yt_quality|{f['id']}"
            }])

        bale_send_text(
            chat_id,
            "🎞 کیفیت مورد نظر را انتخاب کن:",
            reply_markup={"inline_keyboard": buttons}
        )

    except Exception as e:
        print("FORMAT THREAD ERROR:", e)
        bale_send_text(chat_id, "❌ خطا در دریافت کیفیت‌ها.")


# =============================
# POLLING LOOPS
# =============================

start_telethon()

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

        time.sleep(1)


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

        time.sleep(1)


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
        result = add_user_volume(bale_user, text_bytes)
        if result == "warn_80":
            send_backup_to_admin("warn_80")
        
        elif result == "expired":
            send_backup_to_admin("expired")
        
        if result == "warn_80":
            bale_send_text(
                bale_user,
                "⚠️ هشدار مصرف حجم\n\n"
                "شما به 80٪ از حجم اشتراک خود رسیده‌اید."
            )
        
        elif result == "expired":
            bale_send_text(
                bale_user,
                "📦 حجم اشتراک شما به پایان رسید.\n"
                "❌ اتصال شما قطع شد."
            )
        
    
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
        file_bytes = requests.get(TG_FILE + file_path, timeout=30).content
        # 📊 ثبت مصرف حجم فایل
        result = add_user_volume(bale_user, len(file_bytes))

        if result == "warn_80":
            send_backup_to_admin("warn_80")
        
        elif result == "expired":
            send_backup_to_admin("expired")
        
        
        if result == "warn_80":
            bale_send_text(
                bale_user,
                "⚠️ هشدار مصرف حجم\n\n"
                "شما به 80٪ از حجم اشتراک خود رسیده‌اید."
            )
        
        elif result == "expired":
            bale_send_text(
                bale_user,
                "📦 حجم اشتراک شما به پایان رسید.\n"
                "❌ اتصال شما قطع شد."
            )
        
        
    
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


    # -----------------------------------------------
    # ✅ HANDLE INLINE BUTTONS (Callback Queries)
    # -----------------------------------------------
    if "callback_query" in upd:
        cb = upd["callback_query"]
        data = cb.get("data", "")
        print("RAW CALLBACK:", repr(data), flush=True)   # ← همینجا
        chat_id = cb["message"]["chat"]["id"]

        # ✅ کلیک روی پیشنهاد
        if data.startswith("yt_suggest|"):
            query = data.split("|",1)[1]
        
            user_search_cache[chat_id] = {
                "query": query,
                "page": 0
            }
        
            videos = youtube_search(query)
            
            if not videos:
                bale_send_text(chat_id,"❌ نتیجه‌ای یافت نشد.")
                return
            
            user_video_cache[chat_id] = videos   # ذخیره کل لیست
            
            for i, v in enumerate(videos):
            
                title = v["title"]
            
                requests.post(
                    BALE_API + "sendPhoto",
                    files={
                        "photo":(
                            "photo.jpg",
                            http.get(v["thumbnail"], timeout=10).content
                        )
                    },
                    data={
                        "chat_id": chat_id,
                        "caption": title,
                        "reply_markup": json.dumps({
                            "inline_keyboard":[[
                                {
                                    "text":"⬇️ دریافت ویدیو",
                                    "callback_data":f"yt_download|{i}"    # دیگر URL کامل نیست → فقط index
                                }
                            ]]
                        })
                    }
                )
            
                    
            
            bale_send_text(
                chat_id,
                "ویدیوهای بیشتر:",
                reply_markup={
                    "inline_keyboard":[[
                        {"text":"▶️ ویدیوهای بعدی","callback_data":"yt_next"}
                    ]]
                }
            )
            return
            
    
    
        # ✅ دانلود ویدیو
        if data.startswith("yt_download|"):
        
            try:
                idx = int(data.split("|", 1)[1])
            except:
                bale_send_text(chat_id, "❌ خطای نامعتبر.")
                return
                    
            videos = user_video_cache.get(chat_id, [])
            if idx >= len(videos):
                bale_send_text(chat_id, "❌ خطا! لینک پیدا نشد.")
                return
        
            url = videos[idx]["url"]   # URL واقعی از کش گرفته می‌شود
        
            user_download_cache[chat_id] = {"url": url}
        
            bale_send_text(chat_id, "⏳ در حال دریافت کیفیت‌ها...")
            
            threading.Thread(
                target=process_get_formats,
                args=(chat_id, url),
                daemon=True
            ).start()
            
            return
            
    
            buttons = []
            for f in formats[:8]:  # حداکثر ۸ کیفیت
                text_btn = f"{f['quality']} - {round(f['size'],1)}MB"
                buttons.append([{
                    "text": text_btn,
                    "callback_data": f"yt_quality|{f['id']}"
                }])
    
            bale_send_text(
                chat_id,
                "🎞 کیفیت مورد نظر را انتخاب کن:",
                reply_markup={"inline_keyboard": buttons}
            )
            return
    
        # ✅ انتخاب کیفیت
        if data.startswith("yt_quality|"):
            fmt_id = data.split("|", 1)[1]
    
            info = user_download_cache.get(chat_id)
            if not info:
                bale_send_text(chat_id, "❌ خطا، دوباره تلاش کن.")
                return
    
            url = info["url"]
    
            threading.Thread(
                target=process_video_download,
                args=(chat_id, url, fmt_id),
                daemon=True
            ).start()
            
            bale_send_text(chat_id, "⏳ دانلود در صف انجام شد...\nمی‌تونی همزمان از ربات استفاده کنی ✅")
            return   # ✅✅✅ خیلی مهم
            
    
        # ✅ ویدیوهای بعدی
        if data == "yt_next":
            cache = user_search_cache.get(chat_id)
            if not cache:
                return
    
            cache["page"] += 1
            query = cache["query"]
            page = cache["page"]
    
            videos = youtube_search(query, page=page)
    
            if not videos:
                bale_send_text(chat_id, "❌ ویدیوی بیشتری یافت نشد.")
                return
    
            user_video_cache[chat_id] = videos
            
            for i, v in enumerate(videos):
                title = v["title"]
            
                requests.post(
                    BALE_API + "sendPhoto",
                    files={
                        "photo":(
                            "photo.jpg",
                            http.get(v["thumbnail"], timeout=10).content
                        )
                    },
                    data={
                        "chat_id": chat_id,
                        "caption": title,
                        "reply_markup": json.dumps({
                            "inline_keyboard":[[
                                {
                                    "text":"⬇️ دریافت ویدیو",
                                    "callback_data":f"yt_download|{i}"
                                }
                            ]]
                        })
                    }
                )
            
                
            
            # ✅ فقط یک بار
            bale_send_text(
                chat_id,
                "ویدیوهای بیشتر:",
                reply_markup={
                    "inline_keyboard":[[
                        {"text":"▶️ ویدیوهای بعدی","callback_data":"yt_next"}
                    ]]
                }
            )
            return

        # ✅ ویدیوهای بیشتر VIP
        if data == "vip_more":
        
            videos = vip_next_page(chat_id)
        
            if not videos:
                bale_send_text(chat_id, "❌ ویدیوی بیشتری یافت نشد.")
                return
        
            for i, v in enumerate(videos):
        
                inline_keyboard = [[
                    {
                        "text": "👁 نمایش جزییات",
                        "callback_data": f"vip_details|{i}"
                    }
                ]]
        
                if i == len(videos) - 1:
                    inline_keyboard[0].append({
                        "text": "▶️ ویدیوهای بیشتر",
                        "callback_data": "vip_more"
                    })
        
                requests.post(
                    BALE_API + "sendPhoto",
                    files={
                        "photo": (
                            "photo.jpg",
                            requests.get(v["thumbnail"], timeout=10).content
                        )
                    },
                    data={
                        "chat_id": chat_id,
                        "caption": v["title"],
                        "reply_markup": json.dumps({
                            "inline_keyboard": inline_keyboard
                        })
                    }
                )
        
            return
        
        # ✅ نمایش جزییات VIP
        if data.startswith("vip_details|"):
        
            try:
                idx = int(data.split("|")[1])
            except:
                bale_send_text(chat_id, "❌ خطا.")
                return
        
            video = vip_get_video(chat_id, idx)
        
            if not video:
                bale_send_text(chat_id, "❌ ویدیو پیدا نشد.")
                return
        
            url = video["url"]
        
            bale_send_text(chat_id, "⏳ در حال دریافت اطلاعات از دانلودر...")
        
            # این تابع در مرحله بعد کامل میشه
            from vip import send_to_downloader
        
            threading.Thread(
                target=send_to_downloader,
                args=(chat_id, url),
                daemon=True
            ).start()
        
            return
        
        # ================================
        # VIP TELEGRAM BUTTONS
        # ================================
        if data.startswith("vip_tg|"):
            payload = data.split("|",1)[1]
        
            # اگر لینک مستقیم بود
            if payload.startswith("http"):
                from vip import download_and_send_parts
                threading.Thread(
                    target=download_and_send_parts,
                    args=(chat_id, payload),
                    daemon=True
                ).start()
                return
        
            # اگر دکمه عادی بود
            from vip import send_button_click
            threading.Thread(
                target=send_button_click,
                args=(chat_id, payload),
                daemon=True
            ).start()
        
            bale_send_text(chat_id,"⏳ در حال دریافت...")
            return

        if data == "vip_related":
            from vip import send_button_click
            threading.Thread(
                target=send_button_click,
                args=(chat_id, "related"),
                daemon=True
            ).start()
            return
        
        
    msg = upd.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    ## -----------------------------------------------
    ## 🔐 ADMIN BACKUP COMMAND: /getdb
    ## -----------------------------------------------
    #if text == "/getdb":
    #    if not is_admin(chat_id):
    #        bale_send_text(chat_id, "⛔ دسترسی ندارید.")
    #        return    #
    #    try:
    #        with open("data/db.json", "rb") as f:
    #            bale_send_document(
    #                chat_id,
    #                f.read(),
    #                "db.json",
    #                caption="📦 بکاپ دیتابیس"
    #            )
    #    except Exception as e:
    #        bale_send_text(chat_id, f"❌ Error: {e}")    #
    #    return


    # -----------------------------------------------
    # ♻️ RESTORE BACKUP (ADMIN ONLY)
    # -----------------------------------------------
    if is_admin(chat_id) and "document" in msg:
        file_id = msg["document"]["file_id"]
    
        info = requests.get(
            BALE_API + "getFile",
            params={"file_id": file_id}
        ).json()["result"]
    
        file_path = info["file_path"]
        file_url = f"https://tapi.bale.ai/file/bot{BALE_TOKEN}/{file_path}"
    
        file_bytes = requests.get(file_url, timeout=20).content
    
        temp_path = "data/_restore_backup.json"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
    
        if restore_backup(temp_path):
            bale_send_text(chat_id, "✅ بکاپ با موفقیت بازیابی شد.")
        else:
            bale_send_text(chat_id, "❌ خطا در بازیابی بکاپ.")
    
        return
    

    # =============================
    # ADMIN PANEL HANDLER
    # =============================
    if is_admin(chat_id):
        handled = handle_admin_message(msg, send_backup_to_admin)
        if handled:
            return

    # ==================================
    # 🚪 خروج از اشتراک (باید اینجا باشد)
    # ==================================
    if text == "🚪 خروج از اشتراک":
        if leave_key(chat_id):
            send_backup_to_admin("leave_key")
            bale_send_text(
                chat_id,
                "✅ از اشتراک خارج شدید.\n"
                "🔌 اتصال شما به تلگرام به‌طور کامل قطع شد."
            )
            token = get_link_by_bale(chat_id)
            if token:
                pair = get_pair(token)
                
                if pair and pair["tg_user_id"]:
                    tg_send_text(pair["tg_user_id"], "شما از اشتراک خود در بله خارج شدید بنابرین لینک اتصال شما غیرفعال شده و اتصال شما با بله قطع شده است! ")
                
        else:
            bale_send_text(chat_id, "⚠️ شما اشتراک فعالی نداشتید.")
    
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
        send_backup_to_admin("join_key")
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
    
    ## ✅ نمایش کیبورد بدون پیام قابل‌مشاهده
    #bale_send_text(
    #    chat_id,
    #    "\u200b",  # Zero‑Width Space (نامرئی)
    #    reply_markup=BALE_KEYBOARD
    #)
    
    # -----------------------------------------------
    # /start = ایجاد یا دریافت لینک
    # -----------------------------------------------
    if text == "/start":
        token = get_link_by_bale(chat_id)
        if not token:
            token = create_link_for_bale(chat_id)

        tg_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={token}"
        bale_send_text(chat_id, f"برای اتصال به تلگرام روی لینک زیر بزن:\n{tg_link}", reply_markup=BALE_KEYBOARD)
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

    if text == "🔎 جست و جوی یوتیوب":
    
        user_state[chat_id] = "youtube_search"
    
        bale_send_text(
            chat_id,
            "🔎 متن جستجوی یوتیوب یا لینک ویدیو را ارسال کن.\n\nبرای خروج /cancel بزن."
        )
    
        return

    if user_state.get(chat_id) == "youtube_search":

        if text == "/cancel":
            user_state.pop(chat_id, None)
            user_search_cache.pop(chat_id, None)
            user_download_cache.pop(chat_id, None)
            bale_send_text(chat_id, "❌ عملیات لغو شد.", reply_markup=BALE_KEYBOARD)
            return

        query = text
        user_state.pop(chat_id)

        # لینک مستقیم
        if is_youtube_url(query):
    
            info = get_video_info(query)
    
            bale_send_photo(
                chat_id,
                requests.get(info["thumbnail"], timeout=10).content,
                caption=info["title"]
            )
    
            bale_send_text(
                chat_id,
                "🎬 برای دانلود روی دکمه زیر بزن",
                reply_markup={
                    "inline_keyboard":[[
                        {"text":"دریافت ویدیو","callback_data":f"yt_download|{query}"}
                    ]]
                }
            )
    
            return

        # ✅ پیشنهادها
        suggestions = youtube_suggestions(query)
        
        if suggestions:
            buttons = []
            for s in suggestions[:5]:
                buttons.append([{
                    "text": s,
                    "callback_data": f"yt_suggest|{s}"
                }])
        
            bale_send_text(
                chat_id,
                "🔎 پیشنهادهای مشابه:",
                reply_markup={"inline_keyboard": buttons}
            )
        
        # سرچ
        videos = youtube_search(query)
        
        if not videos:
            bale_send_text(chat_id,"❌ نتیجه‌ای یافت نشد.")
            return

        user_video_cache[chat_id] = videos
        for i, v in enumerate(videos):
        
            title = v["title"]
        
            requests.post(
                BALE_API + "sendPhoto",
                files={
                    "photo":(
                        "photo.jpg",
                        http.get(v["thumbnail"], timeout=10).content
                    )
                },
                data={
                    "chat_id": chat_id,
                    "caption": title,
                    "reply_markup": json.dumps({
                        "inline_keyboard":[[
                            {
                                "text":"⬇️ دریافت ویدیو",
                                "callback_data": f"yt_download|{i}"
                            }
                        ]]
                    })
                }
            )
            
        
        bale_send_text(
            chat_id,
            "ویدیوهای بیشتر:",
            reply_markup={
                "inline_keyboard":[[
                    {"text":"▶️ ویدیوهای بعدی","callback_data":"yt_next"}
                ]]
            }
        )
        
        user_search_cache[chat_id] = {
            "query": query,
            "page": 0
        }
        
        return
    
    # ================================
    # 🔎 سرچ VIP یوتیوب (جدید)
    # ================================
    if text == "🔎 سرچ VIP یوتیوب":
        user_state[chat_id] = "youtube_vip"

        bale_send_text(
            chat_id,
            "🔎 متن جستجوی یوتیوب یا لینک ویدیو را بفرست.\n\nبرای لغو /cancel رو بزن."
        )
        return

    # ================================
    # 🔎 پردازش سرچ VIP یوتیوب
    # ================================
    if user_state.get(chat_id) == "youtube_vip":
    
        if text == "/cancel":
            user_state.pop(chat_id, None)
            user_search_cache.pop(chat_id, None)
            user_download_cache.pop(chat_id, None)
            bale_send_text(chat_id, "❌ عملیات لغو شد.", reply_markup=BALE_KEYBOARD)
            return
    
        query = text
        user_state.pop(chat_id, None)
    
        videos = vip_search(chat_id, query)
    
        if not videos:
            bale_send_text(chat_id, "❌ نتیجه‌ای یافت نشد.")
            return
    
        user_video_cache[chat_id] = videos
    
        for i, v in enumerate(videos):
    
            inline_keyboard = [[
                {
                    "text": "👁 نمایش جزییات",
                    "callback_data": f"vip_details|{i}"
                }
            ]]
    
            if i == len(videos) - 1:
                inline_keyboard[0].append({
                    "text": "▶️ ویدیوهای بیشتر",
                    "callback_data": "vip_more"
                })
    
            requests.post(
                BALE_API + "sendPhoto",
                files={
                    "photo":(
                        "photo.jpg",
                        requests.get(v["thumbnail"], timeout=10).content
                    )
                },
                data={
                    "chat_id": chat_id,
                    "caption": v["title"],
                    "reply_markup": json.dumps({
                        "inline_keyboard": inline_keyboard
                    })
                }
            )
    
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
            file_obj = msg["document"]
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
        file_bytes = requests.get(file_url, timeout=20).content
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
    


# ===============================================
# ===== BACKUP SYSTEM ===========================
# ===============================================
def send_backup_to_admin(reason):
    path = make_backup(reason)
    if not path:
        return

    caption_map = {
        "auto_30min": "⏱ بکاپ اتوماتیک ۳۰ دقیقه‌ای",
        "create_key": "🔑 بکاپ بعد از ساخت کلید",
        "deactivate_key": "🗑 بکاپ بعد از حذف کلید",
        "join_key": "👤 بکاپ بعد از ورود کاربر",
        "leave_key": "🚪 بکاپ بعد از خروج کاربر",
        "warn_80": "⚠️ بکاپ پس از رسیدن مصرف به ۸۰٪",
        "expired": "❌ بکاپ پس از پایان حجم کلید",
    }

    caption = caption_map.get(reason, "📦 بکاپ دیتابیس")

    with open(path, "rb") as f:
        bale_send_document(
            ADMIN_BALE_ID,
            f.read(),
            os.path.basename(path),
            caption=caption
        )
    cleanup_old_backups()


def backup_scheduler():
    while True:
        time.sleep(1800)  # 30 دقیقه
        send_backup_to_admin("auto_30min")

threading.Thread(
    target=backup_scheduler,
    daemon=True
).start()

