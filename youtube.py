#youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py #youtube.py 
import requests
import subprocess
import json
import os
import re
import time
import threading
import random
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# USER STATES & CACHE
# ============================================================

user_state = {}
user_search_cache = {}
user_download_cache = {}
user_video_cache = {}   # {chat_id: [list of videos]}

# ============================================================
# PROXY SYSTEM (AUTO + CACHE 10 minutes)
# ============================================================

proxy_cache = {
    "proxy": None,
    "expires": 0
}

proxy_lock = threading.Lock()


# فقط IP:PORT واقعی
PROXY_REGEX = re.compile(
    r"^("
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d):"
    r"([0-9]{1,5})$"
)

def get_free_proxies():

    urls = [
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=3000",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://www.proxyscan.io/download?type=http",
        "https://openproxy.space/list/http"
    ]

    proxies = set()

    for u in urls:
        try:
            print(f"[PROXY] Fetching from: {u}", flush=True)
            r = requests.get(u, timeout=6)

            # تبدیل نکن، فقط همان raw lines
            for line in r.text.splitlines():
                line = line.strip()

                # اگر خط فقط شامل IP:PORT بود
                if PROXY_REGEX.match(line):
                    proxies.add(line)

        except Exception as e:
            print(f"[PROXY] Error fetching {u}: {e}", flush=True)
            continue

    proxies = list(proxies)
    print(f"[PROXY] VALID proxies: {len(proxies)}", flush=True)

    # محدودیت تعداد
    random.shuffle(proxies)
    return proxies[:40]



def test_proxy(proxy):
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    try:
        r = requests.get(
            "https://www.youtube.com/favicon.ico",
            proxies=proxies,
            timeout=3   # قبلا 10 بود → Hang
        )
        return r.status_code == 200
    except:
        return False


def get_working_proxy():

    now = time.time()

    # اول بدون lock بررسی کش
    if proxy_cache["proxy"] and proxy_cache["expires"] > now:
        print(f"[CACHE] Using cached proxy: {proxy_cache['proxy']}", flush=True)
        return proxy_cache["proxy"]

    print("[PROXY] Fetching new proxy list...", flush=True)

    lst = get_free_proxies()

    for proxy in lst:

        print(f"[PROXY] Testing {proxy}", flush=True)

        if test_proxy(proxy):

            print(f"[PROXY] OK: {proxy}", flush=True)

            # فقط این قسمت lock می‌خواهد
            with proxy_lock:
                proxy_cache["proxy"] = proxy
                proxy_cache["expires"] = now + 600

            return proxy

    print("[PROXY] No working proxy found", flush=True)
    return None



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
    """
    سعی می‌کند با پروکسی سالم yt-dlp را اجرا کند.
    اگر پروکسی خراب بود → پروکسی بعدی را امتحان می‌کند.
    """

    # 3 بار تلاش با 3 پروکسی مختلف
    for attempt in range(3):

        proxy = get_working_proxy()

        if proxy is None:
            print("NO WORKING PROXY (PROXY None)", flush=True)
            return None

        print(f"[YT-DLP] Using proxy: {proxy}", flush=True)

        cmd = YTDLP_CMD + [
            "--proxy", f"http://{proxy}",
            "-J", url
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            print("YT-DLP RETURN CODE:", proc.returncode, flush=True)
            print("YT-DLP STDERR:", proc.stderr[:200], flush=True)

            if proc.returncode == 0:
                # موفق
                try:
                    data = json.loads(proc.stdout)
                    fmt_list = []
                    for f in data.get("formats", []):
                        if f.get("vcodec") == "none":
                            continue
                        h = f.get("height")
                        if not h:
                            continue
                        size = f.get("filesize") or f.get("filesize_approx") or 0
                        fmt_list.append({
                            "id": f["format_id"],
                            "quality": f"{h}p",
                            "size": round(size/(1024*1024), 2)
                        })
                    fmt_list = sorted(fmt_list, key=lambda x: int(x["quality"].replace("p","")))
                    return fmt_list[:6]
                except:
                    return None

            # اگر خطای 429 / پروکسی بلاک
            if "429" in proc.stderr or "Sign in to confirm" in proc.stderr:
                print("[PROXY] Proxy blocked. rotating...", flush=True)
                proxy_cache["expires"] = 0  # پروکسی باطل
                continue  # پروکسی بعدی

            # خطاهای دیگر
            return None

        except Exception as e:
            print("YT-DLP ERROR:", e, flush=True)

    # اگر ۳ بار تلاش شکست خورد
    return None



# ============================================================
# دانلود ویدیو
# ============================================================

def download_video(url, fmt_id, chat_id):
    """
    دانلود با پروکسی سالم + در صورت Fail پروکسی بعدی امتحان شود.
    """

    out = f"/tmp/video_{chat_id}.mp4"

    for attempt in range(3):

        proxy = get_working_proxy()

        if proxy is None:
            print("NO PROXY FOR DOWNLOAD", flush=True)
            return None

        print(f"[DOWNLOAD] Using proxy: {proxy}", flush=True)

        cmd = YTDLP_CMD + [
            "--proxy", f"http://{proxy}",
            "-f", f"{fmt_id}+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", out,
            url
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=500
            )

            print("DOWNLOAD CODE:", proc.returncode, flush=True)

            if proc.returncode == 0:
                if os.path.exists(out):
                    return out

            # خطای پروکسی بلاک
            if "429" in proc.stderr or "Sign in" in proc.stderr:
                print("[DOWNLOAD] Proxy blocked → rotate", flush=True)
                proxy_cache["expires"] = 0
                continue

        except:
            pass

    return None



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


