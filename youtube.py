#youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py 
import requests
import subprocess
import json
import os
import re
from urllib.parse import quote_plus

# ============================================================
# USER STATES & CACHE
# ============================================================

user_state = {}
user_search_cache = {}
user_download_cache = {}
user_video_cache = {}   # {chat_id: [list of videos]}


# ============================================================
# yt-dlp command (stable for servers)
# ============================================================

YTDLP_CMD = [
    "python", "-m", "yt_dlp",
    "--no-check-certificates",
    "--geo-bypass",
    "--geo-bypass-country", "US",
    "--default-search", "ytsearch",
    "--user-agent", "Mozilla/5.0"
]

# ============================================================
# تشخیص لینک یوتیوب
# ============================================================

def is_youtube_url(text):
    return ("youtube.com" in text) or ("youtu.be" in text)

# ============================================================
# پیشنهادهای یوتیوب
# ============================================================

def youtube_suggestions(query):

    url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={quote_plus(query)}"

    try:
        r = requests.get(
            url,
            headers={"User-Agent":"Mozilla/5.0"},
            timeout=5
        )
        data = json.loads(r.text[19:-1])
        return data[1]
    except Exception as e:
        print("Suggestion error:", e)
        return []

# ============================================================
# سرچ یوتیوب
# ============================================================

def youtube_search(query, limit=10, page=0):

    try:

        url = "https://www.youtube.com/results"

        params = {
            "search_query": query
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, params=params, headers=headers, timeout=10)

        html = r.text

        # استخراج videoRenderer
        matches = re.findall(
            r'"videoId":"(.*?)".*?"title":\{"runs":\[\{"text":"(.*?)"\}\]',
            html
        )

        results = []
        seen = set()

        for vid, title in matches:

            if vid in seen:
                continue

            seen.add(vid)

            results.append({
                "id": vid,
                "title": title,
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "url": f"https://youtube.com/watch?v={vid}"
            })

        start = page * limit
        end = start + limit

        return results[start:end]

    except Exception as e:
        print("SEARCH ERROR:", e)
        return []



# ============================================================
# اطلاعات ویدیو
# ============================================================

def get_video_info(url):

    try:
        proc = subprocess.run(
            YTDLP_CMD + ["-J", url],
            capture_output=True,
            text=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        print("video info timeout")
        return None

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        print("VIDEO INFO ERROR:", proc.stderr)
        return None

    return {
        "title": data.get("title", "Unknown title"),
        "thumbnail": data.get("thumbnail"),
        "url": url
    }

# ============================================================
# گرفتن کیفیت‌ها
# ============================================================

def get_video_formats(url):

    try:
        proc = subprocess.run(
            YTDLP_CMD + ["-J", url],
            capture_output=True,
            text=True,
            timeout=60
        )
        print("YT-DLP RETURN CODE:", proc.returncode)
        print("YT-DLP STDOUT:", proc.stdout[:500])  # فقط ۵۰۰ کاراکتر اول
        print("YT-DLP STDERR:", proc.stderr)

        data = json.loads(proc.stdout)

    except:
        return []

    formats = []

    for f in data.get("formats", []):

        if f.get("vcodec") == "none":
            continue

        height = f.get("height")
        if not height:
            continue

        size = f.get("filesize") or f.get("filesize_approx") or 0
        size_mb = round(size/(1024*1024),2)

        formats.append({
            "id": f["format_id"],
            "quality": f"{height}p",
            "size": size_mb
        })

    # مرتب سازی کیفیت
    formats = sorted(formats, key=lambda x: int(x["quality"].replace("p","")))

    return formats[:6]



# ============================================================
# دانلود ویدیو
# ============================================================

def download_video(url, fmt_id, chat_id):

    out = f"/tmp/video_{chat_id}.mp4"

    try:
        subprocess.run(
            YTDLP_CMD + [
                "-f", f"{fmt_id}+bestaudio/best",
                "--merge-output-format", "mp4",
                "-o", out,
                url
            ],
            timeout=600
        )
    except subprocess.TimeoutExpired:
        print("download timeout")
        return None

    if not os.path.exists(out):
        print("download failed, file not found")
        return None

    return out


# ============================================================
# split با ffmpeg
# ============================================================

def split_video_ffmpeg(path, chat_id):

    parts = []
    output_pattern = f"/tmp/part_{chat_id}_%03d.mp4"

    file_size = os.path.getsize(path)
    file_size_mb = file_size / (1024 * 1024)

    if file_size_mb <= 20:
        return [path]

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
        print("ffprobe error:", proc.stderr)
        return []

    target_mb = 18
    ratio = target_mb / file_size_mb
    segment_time = max(5, int(duration * ratio))

    proc = subprocess.run(
        [
            "ffmpeg",
            "-i", path,
            "-c", "copy",
            "-map", "0",
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-reset_timestamps", "1",
            output_pattern
        ],
        capture_output=True
    )

    if proc.returncode != 0:
        print("FFMPEG ERROR:", proc.stderr)
        return []

    for f in sorted(os.listdir("/tmp")):
        if f.startswith(f"part_{chat_id}_") and f.endswith(".mp4"):
            parts.append("/tmp/" + f)

    return parts

# ============================================================
# پاکسازی فایل‌ها
# ============================================================

def clean_temp_files(chat_id):

    for f in os.listdir("/tmp"):
        if str(chat_id) in f:
            try:
                os.remove("/tmp/" + f)
            except Exception as e:
                print("cleanup error:", e)
