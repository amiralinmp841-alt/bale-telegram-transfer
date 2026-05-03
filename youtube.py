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
proxy_pool = []
proxy_scores = {}
building_pool = False
pool_lock = threading.Lock()

MAX_TEST_WORKERS = 25
PROXY_TEST_TIMEOUT = 3
POOL_SIZE = 10
PROXY_REFRESH_INTERVAL = 30
MIN_POOL_SIZE = 3
background_proxy_thread_started = False


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

        start = time.time()

        r = requests.get(
            "https://www.youtube.com/favicon.ico",
            proxies=proxies,
            timeout=PROXY_TEST_TIMEOUT
        )

        latency = time.time() - start

        if r.status_code == 200:
            return (proxy, latency)

    except:
        pass

    return None

def build_proxy_pool():

    global proxy_pool
    global proxy_scores
    global building_pool

    with pool_lock:
        if building_pool:
            return
        building_pool = True

    print("[PROXY] ULTRA Building proxy pool...", flush=True)

    proxies = get_free_proxies()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_TEST_WORKERS) as executor:
        futures = [executor.submit(test_proxy, p) for p in proxies]

        for future in as_completed(futures):
            res = future.result()
            if res:
                proxy, latency = res
                results.append((proxy, latency))
                print(f"[PROXY] OK {proxy} {latency:.2f}s", flush=True)

    if results:

        results.sort(key=lambda x: x[1])
        best = results[:POOL_SIZE]

        new_pool = []
        new_scores = {}

        for p, lat in best:
            new_pool.append(p)
            new_scores[p] = lat

        proxy_pool[:] = new_pool
        proxy_scores.clear()
        proxy_scores.update(new_scores)

        print(f"[PROXY] ULTRA Pool ready ({len(proxy_pool)})", flush=True)

    building_pool = False

def proxy_background_worker():

    global proxy_pool

    while True:

        try:

            if len(proxy_pool) < MIN_POOL_SIZE:

                print("[PROXY] Pool low → rebuilding...", flush=True)
                build_proxy_pool()

            else:

                print("[PROXY] Background refresh...", flush=True)
                build_proxy_pool()

        except Exception as e:

            print("[PROXY] Background error:", e, flush=True)

        time.sleep(PROXY_REFRESH_INTERVAL)


def start_proxy_background_thread():

    global background_proxy_thread_started

    if background_proxy_thread_started:
        return

    t = threading.Thread(
        target=proxy_background_worker,
        daemon=True
    )

    t.start()

    background_proxy_thread_started = True

    print("[PROXY] Background proxy refresher started", flush=True)


def get_working_proxy():

    start_proxy_background_thread()

    now = time.time()

    if proxy_cache["proxy"] and proxy_cache["expires"] > now:
        return proxy_cache["proxy"]

    if not proxy_pool:
        build_proxy_pool()
        if not proxy_pool:
            return None

    # انتخاب سریع‌ترین proxy
    sorted_proxies = sorted(proxy_pool, key=lambda p: proxy_scores.get(p, 999))
    proxy = sorted_proxies[0]

    with proxy_lock:
        proxy_cache["proxy"] = proxy
        proxy_cache["expires"] = now + 180  # کوتاه‌تر = هوشمندتر

    return proxy



def remove_bad_proxy(proxy):

    global proxy_pool
    global proxy_scores

    if proxy in proxy_pool:

        proxy_pool.remove(proxy)

        if proxy in proxy_scores:
            del proxy_scores[proxy]

        print(f"[PROXY] Removed bad proxy {proxy}", flush=True)

        if len(proxy_pool) < MIN_POOL_SIZE:

            print("[PROXY] Pool low → rebuild triggered", flush=True)

            threading.Thread(
                target=build_proxy_pool,
                daemon=True
            ).start()




# ============================================================
# yt-dlp command (stable for servers)
# ============================================================

YTDLP_CMD = [
    "python", "-m", "yt_dlp",
    "--no-check-certificates",
    "--geo-bypass",
    "--geo-bypass-country", "US",
    "--default-search", "ytsearch",
    "--user-agent", "Mozilla/5.0",
    "--concurrent-fragments", "5",
    "--socket-timeout", "15",
    "--retries", "3",
    "--no-playlist",
    "--no-warnings",
    "--quiet"
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


import re, json, requests

def youtube_search(query, limit=10, page=0):
    try:
        url = "https://www.youtube.com/results"
        params = {"search_query": query}
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, params=params, headers=headers, timeout=10)
        html = r.text

        # پیدا کردن تگ ytInitialData (داده ساختاریافته جستجو)
        data_match = re.search(r'var ytInitialData = ({.*?});', html)
        if not data_match:
            print("❌ ytInitialData not found in page")
            return []

        data = json.loads(data_match.group(1))
        # حرکت در ساختار JSON تا رسیدن به videoRenderer‌ها
        sections = (
            data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
        )

        videos = []
        seen = set()

        for section in sections:
            items = (
                section.get("itemSectionRenderer", {})
                .get("contents", [])
            )
            for item in items:
                v = item.get("videoRenderer")
                if not v:
                    continue

                vid = v.get("videoId")
                title_runs = v.get("title", {}).get("runs", [])
                title = title_runs[0].get("text", "") if title_runs else ""

                if not vid or vid in seen:
                    continue

                seen.add(vid)

                videos.append({
                    "id": vid,
                    "title": title,
                    "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={vid}"
                })

        start = page * limit
        end = start + limit

        return videos[start:end]

    except Exception as e:
        print("SEARCH ERROR:", e)
        return []

def youtube_related(video_id, limit=5, page=None):
    import requests

    YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
    base = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "type": "video",
        "maxResults": limit,
        "relatedToVideoId": video_id,
        "key": YOUTUBE_API_KEY
    }
    if page:
        params["pageToken"] = page

    r = requests.get(base, params=params)
    data = r.json()

    videos = []
    for item in data.get("items", []):
        v_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append({
            "video_id": v_id,
            "title": snippet["title"],
            "url": f"https://www.youtube.com/watch?v={v_id}",
            "thumbnail": snippet["thumbnails"]["high"]["url"]
        })
    return videos

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
                timeout=40
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
                remove_bad_proxy(proxy)
                proxy_cache["expires"] = 0
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
                timeout=300
            )

            print("DOWNLOAD CODE:", proc.returncode, flush=True)

            if proc.returncode == 0:
                if os.path.exists(out):
                    return out

            # خطای پروکسی بلاک
            if "429" in proc.stderr or "Sign in" in proc.stderr:
                print("[DOWNLOAD] Proxy blocked → rotate", flush=True)
                remove_bad_proxy(proxy)
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
    work_dir = f"/tmp/vip_{chat_id}"
    os.makedirs(work_dir, exist_ok=True)

    output_pattern = f"{work_dir}/part_%03d.mp4"

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
        ]
    )

    if proc.returncode != 0:
        return []

    for f in sorted(os.listdir(work_dir)):
        if f.startswith("part_") and f.endswith(".mp4"):
            parts.append(os.path.join(work_dir, f))

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


