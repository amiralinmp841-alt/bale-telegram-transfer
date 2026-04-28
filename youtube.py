#youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py 


import requests
import subprocess
import json
import os
import re
from urllib.parse import quote_plus

# ============================================================
# USER STATES & CACHE
# ============================================================

user_state = {}          # chat_id → "youtube_search" | "choose_quality" | "downloading"
user_search_cache = {}   # chat_id → { query, page, results }
user_download_cache = {} # chat_id → { url }

# ============================================================
# تشخیص لینک یوتیوب
# ============================================================

def is_youtube_url(text):
    return ("youtube.com" in text) or ("youtu.be" in text)

# ============================================================
# پیشنهادهای یوتیوب (autocomplete API)
# ============================================================

def youtube_suggestions(query):
    """Returns search suggestions from YouTube"""

    url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={quote_plus(query)}"

    try:
        r = requests.get(url, timeout=5)
        data = json.loads(r.text[19:-1])  # یوتیوب داخل callback می‌دهد → باید برش بزنیم

        return data[1]  # لیست پیشنهادها

    except:
        return []

# ============================================================
# سرچ یوتیوب با yt-dlp
# ============================================================

def youtube_search(query, limit=10, page=0):
    """Search YouTube videos using yt-dlp"""

    search_str = f"ytsearch{limit}:{query}"

    proc = subprocess.run(
        ["yt-dlp", "--dump-json", search_str],
        capture_output=True,
        text=True
    )

    # اگر yt-dlp خطا داد
    if proc.returncode != 0:
        print("YT-DLP ERROR:", proc.stderr)
        return []

    if not proc.stdout.strip():
        print("YT-DLP returned empty output")
        return []

    videos = []

    for line in proc.stdout.splitlines():
        try:
            d = json.loads(line)

            videos.append({
                "id": d.get("id"),
                "title": d.get("title"),
                "duration": d.get("duration", 0),
                "thumbnail": d.get("thumbnail"),
                "url": d.get("webpage_url")
            })
        except Exception as e:
            print("JSON parse error:", e)

    start = page * limit
    return videos[start:start + limit]


# ============================================================
# اطلاعات ویدیو برای لینک مستقیم
# ============================================================

def get_video_info(url):
    proc = subprocess.run(
        ["yt-dlp", "-J", url],
        capture_output=True,
        text=True
    )

    try:
        data = json.loads(proc.stdout)
    except:
        return None
    

    return {
        "title": data["title"],
        "thumbnail": data["thumbnail"],
        "url": url
    }

# ============================================================
# گرفتن کیفیت + حجم دقیق (MB)
# ============================================================

def get_video_formats(url):
    proc = subprocess.run(
        ["yt-dlp", "-F", url],
        capture_output=True,
        text=True
    )

    formats = []

    for line in proc.stdout.splitlines():
        if ("mp4" in line) and ("video only" not in line):
            parts = line.split()

            fmt_id = parts[0]

            # استخراج رزولوشن
            match = re.search(r"(\d{3,4}p)", line)
            if not match:
                continue

            quality = match.group(1)

            # استخراج حجم MB
            size_match = re.search(r"~?(\d+(\.\d+)?)MiB", line)
            size_mb = float(size_match.group(1)) if size_match else 0

            formats.append({
                "id": fmt_id,
                "quality": quality,
                "size": size_mb
            })

    return formats

# ============================================================
# دانلود ویدیو
# ============================================================

def download_video(url, fmt_id, chat_id):
    out = f"/tmp/video_{chat_id}.mp4"

    subprocess.run([
        "yt-dlp",
        "-f", fmt_id,
        "-o", out,
        url
    ])

    if not os.path.exists(out):
        return None

    return out


# ============================================================
# split با ffmpeg → هر پارت حداکثر 20MB (کاملاً صحیح)
# ============================================================

def split_video_ffmpeg(path, chat_id):

    parts = []
    output_pattern = f"/tmp/part_{chat_id}_%03d.mp4"

    # ---------- گرفتن حجم فایل ----------
    file_size = os.path.getsize(path)  # bytes
    file_size_mb = file_size / (1024 * 1024)

    # اگر فایل خودش زیر 20MB است
    if file_size_mb <= 20:
        return [path]

    # ---------- گرفتن duration ----------
    proc = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ],
        capture_output=True,
        text=True
    )

    try:
        duration = float(proc.stdout.strip())
    except:
        return []

    # ---------- محاسبه زمان هر پارت ----------
    target_mb = 18  # کمی کمتر از 20 برای امنیت

    ratio = target_mb / file_size_mb
    segment_time = max(5, int(duration * ratio))

    # ---------- split ----------
    subprocess.run([
        "ffmpeg",
        "-i", path,
        "-c", "copy",
        "-map", "0",
        "-f", "segment",
        "-segment_time", str(segment_time),
        "-reset_timestamps", "1",
        output_pattern
    ])

    # ---------- جمع آوری فایل ها ----------
    for f in sorted(os.listdir("/tmp")):
        if f.startswith(f"part_{chat_id}_") and f.endswith(".mp4"):
            parts.append(f"/tmp/" + f)

    return parts


# ============================================================
# پاکسازی فایل‌ها
# ============================================================

def clean_temp_files(chat_id):
    for f in os.listdir("/tmp"):
        if str(chat_id) in f:
            try:
                os.remove("/tmp/" + f)
            except:
                pass
