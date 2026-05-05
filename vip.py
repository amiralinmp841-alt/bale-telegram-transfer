#vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py #vip.py 
import os
import asyncio
import requests
from telethon import TelegramClient, events
from youtube import youtube_search
import tempfile
import threading
import re
import time


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
last_bot_message = {}
pending_requests = {}   # msg_id -> bale_chat_id
vip_search_cache = {}
vip_video_cache = {}


API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION = os.environ.get("USER_SESSION","user_session")
BOT_USERNAME = os.environ.get("MEGASAVER_BOT","MegaSaverBot")

from telethon import TelegramClient
from telethon.sessions import StringSession

# "SESSION" همان رشته بلند شماست
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# =============================
# TELETHON START
# =============================

def start_telethon():
    async def main():
        await client.start()
        print("✅ Telethon Started")

    loop.create_task(main())
    threading.Thread(target=loop.run_forever, daemon=True).start()
    print("✅ Telethon loop started and handlers active!", flush=True)



# =============================
# SEARCH
# =============================

def vip_search(chat_id, query, page=0):

    videos = youtube_search(query, page=page, limit=5)

    if not videos:
        return []

    vip_search_cache[chat_id] = {
        "query": query,
        "page": page
    }

    vip_video_cache[chat_id] = videos

    return videos


def vip_next_page(chat_id):

    cache = vip_search_cache.get(chat_id)
    if not cache:
        return []

    query = cache["query"]
    page = cache["page"] + 1

    return vip_search(chat_id, query, page)


def vip_get_video(chat_id, index):

    videos = vip_video_cache.get(chat_id, [])

    if index >= len(videos):
        return None

    return videos[index]

from youtube import youtube_related  # باید در youtube.py اضافه شود؛ توضیح پایین را ببین.

def vip_related(chat_id, video_id, page=0):
    """
    دریافت ۵ ویدیو مرتبط با یک ویدیو واقعی YouTube (video_id).
    از همان منطق vip_search استفاده می‌کند ولی query ندارد.
    """
    videos = youtube_related(video_id, limit=5, page=page)
    if not videos:
        return []

    vip_search_cache[chat_id] = {
        "query": f"related:{video_id}",
        "page": page,
        "video_id": video_id
    }
    vip_video_cache[chat_id] = videos
    return videos


def vip_related_next_page(chat_id):
    cache = vip_search_cache.get(chat_id)
    if not cache or not cache.get("video_id"):
        return []
    video_id = cache["video_id"]
    page = cache["page"] + 1
    return vip_related(chat_id, video_id, page)

# =============================
# SEND LINK TO DOWNLOADER
# =============================

def send_to_downloader(bale_chat_id, url):

    async def task():
        msg = await client.send_message(BOT_USERNAME, url)
        pending_requests[msg.id] = bale_chat_id

    asyncio.run_coroutine_threadsafe(task(), loop)



# =============================
# HANDLE BOT RESPONSE
# =============================

@client.on(events.NewMessage(from_users=BOT_USERNAME))
async def handle_bot_message(event):

    msg = event.message

    # پیدا کردن bale_chat_id با fallback
    bale_chat_id = None
    if msg.reply_to_msg_id:
        bale_chat_id = pending_requests.get(msg.reply_to_msg_id)
    
    if bale_chat_id is None and pending_requests:
        # fallback به آخرین متقاضی فعال
        last_msg_id = list(pending_requests.keys())[-1]
        bale_chat_id = pending_requests[last_msg_id]
    
    if bale_chat_id is None:
        print("❌ No bale_chat_id found — message skipped.")
        return
    last_bot_message[bale_chat_id] = msg
    

    caption = msg.text or ""

    # -------- buttons --------

    inline = []

    if msg.buttons:

        for row in msg.buttons:

            line = []

            for btn in row:
                data = btn.data.decode() if btn.data else "none"
                line.append({
                    "text": btn.text,
                    "callback_data": f"vip_tg|{data}"
                })
            

            inline.append(line)

    # -------- photo --------

    photo_bytes = None

    if msg.photo:
        photo_bytes = await msg.download_media(bytes)

    # ارسال به بله

    from bridge import bale_send_photo, bale_send_text, BALE_API
    import json

    if photo_bytes:
        requests.post(
            BALE_API + "sendPhoto",
            files={"photo":("photo.jpg",photo_bytes)},
            data={
                "chat_id":bale_chat_id,
                "caption":caption,
                "reply_markup":json.dumps({
                    "inline_keyboard":inline
                })
            }
        )
    else:
        bale_send_text(
            bale_chat_id,
            caption,
            reply_markup={
                "inline_keyboard": inline
            }
        )
    # هندل دکمه کیفیت VIP
    if msg.media and hasattr(msg.media, 'document'):
        mime_type = getattr(msg.media.document, 'mime_type', "")
        if mime_type.startswith("video/") or mime_type.startswith("audio/"):
            file_bytes = await msg.download_media(bytes)

            file_name = "file.mp4"
            for attr in msg.media.document.attributes:
                if hasattr(attr, "file_name"):
                    file_name = attr.file_name

            from bridge import bale_send_text
            bale_send_text(bale_chat_id, "⏳ در حال آماده سازی فایل...")

            # همین فایل فعلی است؛ نیازی به import دوباره نیست
            process_local_file(bale_chat_id, file_bytes, file_name, mime_type)

            return

@client.on(events.MessageEdited(from_users=BOT_USERNAME))
async def handle_bot_message_edited(event):

    msg = event.message

    print("✏️ BOT MESSAGE EDITED:", msg.text)

    # همان منطق پیدا کردن کاربر بله
    bale_chat_id = None

    if msg.reply_to_msg_id:
        bale_chat_id = pending_requests.get(msg.reply_to_msg_id)

    if bale_chat_id is None and pending_requests:
        last_msg_id = list(pending_requests.keys())[-1]
        bale_chat_id = pending_requests[last_msg_id]

    if bale_chat_id is None:
        print("❌ No bale_chat_id found — edited message skipped.")
        return

    last_bot_message[bale_chat_id] = msg

    caption = msg.text or ""

    inline = []

    if msg.buttons:
        for row in msg.buttons:
            line = []
            for btn in row:
                data = btn.data.decode() if btn.data else "none"
                line.append({
                    "text": btn.text,
                    "callback_data": f"vip_tg|{data}"
                })
            inline.append(line)

    photo_bytes = None
    if msg.photo:
        photo_bytes = await msg.download_media(bytes)

    from bridge import bale_send_photo, bale_send_text, BALE_API
    import json

    if photo_bytes:
        requests.post(
            BALE_API + "sendPhoto",
            files={"photo":("photo.jpg",photo_bytes)},
            data={
                "chat_id":bale_chat_id,
                "caption":caption,
                "reply_markup":json.dumps({
                    "inline_keyboard":inline
                })
            }
        )
    else:
        bale_send_text(
            bale_chat_id,
            caption,
            reply_markup={
                "inline_keyboard": inline
            }
        )

    

def send_button_click(bale_chat_id, callback_data):
    async def task():
        msg = last_bot_message.get(bale_chat_id)
        if msg:
            # کلیک واقعی روی دکمه در تلگرام
            # callback_data که از بله آمده مثلا "quality_1080"
            await msg.click(data=callback_data.encode()) 
        else:
            print(f"❌ No last_bot_message for {bale_chat_id}")

    asyncio.run_coroutine_threadsafe(task(), loop)




def download_and_send_parts(bale_chat_id, file_url, file_name=None, caption=None):
    try:
        r = requests.get(file_url, stream=True)
        r.raise_for_status()

        content_type = (r.headers.get("Content-Type") or "").lower()

        # تشخیص صوت
        is_audio = (
            content_type.startswith("audio/")
            or (file_name and file_name.lower().endswith((".mp3", ".ogg", ".m4a", ".wav")))
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        with temp_file as f:
            for chunk in r.iter_content(2 * 1024 * 1024):
                if chunk:
                    f.write(chunk)

        local_path = temp_file.name
        file_size = os.path.getsize(local_path)
        MAX_PART_SIZE = 20 * 1024 * 1024  # 20MB

        # اگر صوت بود: مستقیم بفرست (تقسیم‌بندی لازم نیست)
        if is_audio:
            from bridge import bale_send_audio, bale_send_text
            with open(local_path, "rb") as f:
                bale_send_audio(bale_chat_id, f.read())
            os.unlink(local_path)
            bale_send_text(bale_chat_id, "✅ ارسال وویس تکمیل شد.")
            return

        # وگرنه ویدیو فرض می‌کنیم:
        base_name = file_name or "video.mp4"
        if not base_name.lower().endswith(".mp4"):
            base_name += ".mp4"

        if file_size <= MAX_PART_SIZE:
            from bridge import bale_send_video, bale_send_text
            with open(local_path, "rb") as f:
                bale_send_video(bale_chat_id, f.read(), caption or "")
            os.unlink(local_path)
            bale_send_text(bale_chat_id, "✅ ارسال فایل تکمیل شد.")
            return

        from bridge import bale_send_text
        bale_send_text(bale_chat_id, "✂️ فایل بزرگ است، در حال تقسیم...")

        from youtube import split_video_ffmpeg, clean_temp_files
        parts = split_video_ffmpeg(local_path, bale_chat_id)
        if not parts:
            bale_send_text(bale_chat_id, "❌ تقسیم فایل شکست خورد.")
            clean_temp_files(bale_chat_id)
            os.unlink(local_path)
            return

        from bridge import bale_send_video
        for i, part in enumerate(parts, 1):
            with open(part, "rb") as f:
                bale_send_video(bale_chat_id, f.read(), caption=f"📦 پارت {i}")

        clean_temp_files(bale_chat_id)
        os.unlink(local_path)
        bale_send_text(bale_chat_id, "✅ ارسال فایل تکمیل شد.")

    except Exception as e:
        from bridge import bale_send_text
        bale_send_text(bale_chat_id, f"❌ خطا در دانلود/ارسال: {e}")




def process_local_file(bale_chat_id, file_bytes, file_name, mime_type=None, caption=None):

    import tempfile
    from bridge import bale_send_video, bale_send_audio, bale_send_text
    from youtube import split_video_ffmpeg, clean_temp_files

    # اگر فایل صوتی بود
    if mime_type and mime_type.startswith("audio/"):
        bale_send_audio(bale_chat_id, file_bytes)
        return
    

    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write(file_bytes)
    temp.close()

    local_path = temp.name
    file_size = os.path.getsize(local_path)
    MAX_PART_SIZE = 20*1024*1024

    # اطمینان از mp4
    base_name = file_name or "video.mp4"
    if not base_name.lower().endswith(".mp4"):
        base_name += ".mp4"

    if file_size <= MAX_PART_SIZE:
        bale_send_video(bale_chat_id, file_bytes, caption or "")
        os.unlink(local_path)
        return

    bale_send_text(bale_chat_id, "✂️ فایل بزرگ است، در حال تقسیم...")

    parts = split_video_ffmpeg(local_path, bale_chat_id)

    if not parts:
        bale_send_text(bale_chat_id, "❌ خطا در تقسیم فایل")
        clean_temp_files(bale_chat_id)
        return

    for i, part in enumerate(parts, 1):
        with open(part, "rb") as f:
            bale_send_video(
                bale_chat_id,
                f.read(),
                caption=f"📦 پارت {i}"
            )

    clean_temp_files(bale_chat_id)
    os.unlink(local_path)

    bale_send_text(bale_chat_id, "✅ ارسال کامل شد.")


def download_video_by_user(telegram_msg, bale_chat_id, caption=None):
    bale_send_text(bale_chat_id, str(telegram_msg))
    return
    
    async def task():
        from bridge import bale_send_text, bale_send_video

        chat_id = telegram_msg["chat"]["id"]
        
        if "reply_to_message" not in telegram_msg:
            bale_send_text(bale_chat_id, "❗ لطفاً روی پیام حاوی ویدیو ریپلای کنید.")
            return
        
        msg_id = telegram_msg["reply_to_message"]["message_id"]
        
        try:
            entity = await client.get_entity(int(chat_id))
            msg = await client.get_messages(entity, ids=int(msg_id))
        except Exception as e:
            bale_send_text(bale_chat_id, f"❌ خطا در دریافت پیام تلگرام: {e}")
            return
        
        if not msg:
            bale_send_text(bale_chat_id, "❌ پیام پیدا نشد.")
            return
        
        media = None
        
        # اگر ویدیوی معمولی باشد
        if msg.video:
            media = msg.video
        
        # اگر فایل ویدیویی باشد
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video"):
            media = msg.document
        
        if not media:
            bale_send_text(bale_chat_id, "❌ این پیام ویدیو نیست.")
            return
        

        bale_send_text(bale_chat_id, "📥 شروع دانلود از تلگرام...")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")

        last_reported = 0
        start_time = time.time()

        async def progress_callback(current, total):
            nonlocal last_reported
            if total == 0:
                return

            percent = int(current * 100 / total)

            # فقط هر 10 درصد گزارش بده
            if percent >= last_reported + 10:
                elapsed = time.time() - start_time
                speed = current / 1024 / 1024 / elapsed if elapsed > 0 else 0
                bale_send_text(
                    bale_chat_id,
                    f"⬇️ دانلود: {percent}%\n🚀 سرعت: {speed:.2f} MB/s"
                )
                last_reported = percent

        try:
            path = await client.download_media(
                media,
                file=tmp.name,
                part_size_kb=4096,
                progress_callback=progress_callback
            )
                 
        except Exception as e:
            bale_send_text(bale_chat_id, f"❌ خطا هنگام دانلود: {e}")
            return

        if not path or not os.path.exists(path):
            bale_send_text(bale_chat_id, "❌ فایل دانلود نشد.")
            return

        bale_send_text(bale_chat_id, "✅ دانلود کامل شد.")

        file_size = os.path.getsize(path)
        MAX_SIZE = 20 * 1024 * 1024

        # اگر کوچکتر از 20MB بود مستقیم ارسال شود
        if file_size <= MAX_SIZE:
            with open(path, "rb") as f:
                bale_send_video(bale_chat_id, f.read(), caption or "🎬 ویدیو")
            os.unlink(path)
            bale_send_text(bale_chat_id, "✅ ارسال تکمیل شد.")
            return

        bale_send_text(bale_chat_id, "✂️ در حال تقسیم فایل به پارت‌های زیر ۲۰MB...")

        parts = split_video_ffmpeg(path, bale_chat_id)

        if not parts:
            bale_send_text(bale_chat_id, "❌ تقسیم فایل شکست خورد.")
            clean_temp_files(bale_chat_id)
            os.unlink(path)
            return

        total = len(parts)
        title = caption or "🎬 ویدیو"

        for i, part in enumerate(parts, 1):
            bale_send_text(bale_chat_id, f"⬆️ ارسال پارت {i}/{total} ...")
            with open(part, "rb") as f:
                bale_send_video(
                    bale_chat_id,
                    f.read(),
                    caption=f"{title}\n📦 پارت {i}/{total}"
                )

        clean_temp_files(bale_chat_id)
        os.unlink(path)

        bale_send_text(bale_chat_id, "✅ همهٔ پارت‌ها ارسال شدند.")
        
    asyncio.run_coroutine_threadsafe(task(), loop)




def find_bale_chat_id(msg):

    # اگر پاسخ به پیام ما باشد
    if msg.reply_to_msg_id:
        if msg.reply_to_msg_id in pending_requests:
            return pending_requests[msg.reply_to_msg_id]

    # fallback → آخرین درخواست
    if pending_requests:
        return list(pending_requests.values())[-1]

    return None

def handle_callback(bale_chat_id, data):
    """
    هندل همه callback های VIP از بله (search, more, related, ...)
    """
    from bridge import bale_send_text
    if data == "vip_related":
        # پیدا کردن video_id از آخرین پیام ربات تلگرام
        msg = last_bot_message.get(bale_chat_id)
        if not msg or not msg.text:
            bale_send_text(bale_chat_id, "❌ عنوانی یافت نشد.")
            return

        title = msg.text.replace("\n", " ").strip()

        # سرچ مانند vip_search ولی بر اساس ID واقعی ویدیو نیست
        videos = vip_search(bale_chat_id, title)
        if not videos:
            bale_send_text(bale_chat_id, "❌ ویدیوی مرتبطی یافت نشد.")
            return

        from bridge import send_vip_results
        send_vip_results(bale_chat_id, videos)
        return

    # وقتی روی دکمه 🎯 خاص هر ویدیو (در جزئیات) کلیک شد
    if data.startswith("vip_related_"):
        index = int(data.split("_")[-1])
        video = vip_get_video(bale_chat_id, index)
        if not video:
            bale_send_text(bale_chat_id, "❌ ویدیو پیدا نشد.")
            return

        v_id = video.get("video_id") or extract_youtube_id(video["url"])
        if not v_id:
            bale_send_text(bale_chat_id, "❌ شناسه ویدیو پیدا نشد.")
            return
        bale_send_text(bale_chat_id, f"🎯 در حال یافتن ویدیوهای مرتبط با: {video['title']}")
        videos = vip_related(bale_chat_id, v_id)
        if not videos:
            bale_send_text(bale_chat_id, "❌ ویدیوی مرتبطی یافت نشد.")
            return

        from bridge import send_vip_results
        send_vip_results(bale_chat_id, videos)
        return

    if data == "vip_more":
        cache = vip_search_cache.get(bale_chat_id)
        if cache and "video_id" in cache:  # اگر در حالت related هستیم
            videos = vip_related_next_page(bale_chat_id)
        else:
            videos = vip_next_page(bale_chat_id)

        if not videos:
            bale_send_text(bale_chat_id, "❌ ویدیوی بیشتری نیست.")
            return

        from bridge import send_vip_results
        send_vip_results(bale_chat_id, videos)
        return


def extract_youtube_id(url):
    patterns = [
        r"v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"shorts/([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None
