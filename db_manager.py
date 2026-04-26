#db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py 
import json
import os
import uuid
import time
from datetime import datetime
import shutil


DB_PATH = "data/db.json"
BACKUP_DIR = "data/backups" # مخصوص بکاپ 

def ghost_id(uid):
    return f"{uid}000"


def load_db():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        save_db({
            "links": {},
            "bale_users": {},
            "tg_users": {},
            "keys": {}          # ✅ اضافه شد
        })
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def generate_token():
    return "BRIDGE-" + uuid.uuid4().hex[:12]


def create_link_for_bale(bale_user_id):
    db = load_db()
    token = generate_token()

    db["links"][token] = {
        "bale_user_id": bale_user_id,
        "tg_user_id": None,
        "active": True,
        "auto_delete": 0   # ✔ اضافه شد
    }
    db["bale_users"][str(bale_user_id)] = token

    save_db(db)
    return token


def activate_link(token, tg_user_id):
    db = load_db()
    if token not in db["links"]:
        return False

    db["links"][token]["tg_user_id"] = tg_user_id
    db["links"][token]["active"] = True
    db["tg_users"][str(tg_user_id)] = token

    save_db(db)
    return True


def get_link_by_bale(bale_user_id):
    db = load_db()
    return db["bale_users"].get(str(bale_user_id))


def get_link_by_telegram(tg_user_id):
    db = load_db()
    return db["tg_users"].get(str(tg_user_id))


def get_pair(token):
    db = load_db()
    return db["links"].get(token)


def deactivate(token):
    db = load_db()
    pair = db["links"].get(token)
    if not pair:
        return False

    # حذف mapping ها
    if pair.get("bale_user_id"):
        db["bale_users"].pop(str(pair["bale_user_id"]), None)

    if pair.get("tg_user_id"):
        db["tg_users"].pop(str(pair["tg_user_id"]), None)

    # ❌ حذف کامل لینک (نه active=false)
    del db["links"][token]

    save_db(db)
    return True



# ------------------------------------------
# ✔ قابلیت جدید: Auto Delete
# ------------------------------------------

def get_auto_delete(token):
    db = load_db()
    if token not in db["links"]:
        return 0
    return db["links"][token].get("auto_delete", 0)


def toggle_auto_delete(token):
    db = load_db()
    if token not in db["links"]:
        return 0

    current = db["links"][token].get("auto_delete", 0)
    new_val = 0 if current == 1 else 1
    db["links"][token]["auto_delete"] = new_val

    save_db(db)
    return new_val

# ==========================================
# ✅ Key Management (Admin Panel)
# ==========================================

def key_exists(key_name):
    db = load_db()
    return key_name in db.get("keys", {})


def add_key(key_name, volume, expire, max_users):
    db = load_db()

    db["keys"][key_name] = {
        "volume": volume,
        "expire": expire,
        "max_users": max_users,
        "created_at": int(time.time()),
        "is_active": 1,
        "users": {},   # user_id: used_volume
        "deactivated_reason": None,
        "warned_80": False   # ✅ جدید

    }

    save_db(db)
    make_backup("create_key") #بکاپ
    cleanup_old_backups()
    

def get_active_keys():
    db = load_db()
    return {
        k: v for k, v in db.get("keys", {}).items()
        if v.get("is_active") == 1
    }


def deactivate_key(key_name, reason="admin", do_backup=True):
    db = load_db()

    key = db.get("keys", {}).get(key_name)
    if not key:
        return False

    key["is_active"] = 0
    key["deactivated_reason"] = reason
    users = list(key.get("users", {}).keys())
    key["users"] = {}

    # cascade قطع لینک‌ها
    for bale_user_id in users:
        token = db["bale_users"].pop(str(bale_user_id), None)
        if not token:
            continue

        pair = db["links"].get(token)
        if not pair:
            continue

        del db["links"][token]
        
        if pair.get("tg_user_id"):
            db["tg_users"].pop(str(pair["tg_user_id"]), None)
        

    save_db(db)
    if do_backup:
        make_backup("deactivate_key") #بکاپ
        cleanup_old_backups()
    return True


# ==========================================
# ✅ User Join Key (Stage 3.2)
# ==========================================
def join_key(key_name, user_id):
    db = load_db()
    user_id = str(user_id)
    ghost = ghost_id(user_id)

    key = db.get("keys", {}).get(key_name)
    if not key:
        return False, "❌ این رمز وجود ندارد."

    if key.get("is_active") != 1:
        return False, "❌ این رمز غیرفعال است."

    now = int(time.time())
    if key.get("expire", 0) <= now:
        return False, "❌ این رمز منقضی شده است."

    users = key.get("users", {})

    # ✅ اگر قبلاً فعال است
    if user_id in users:
        return False, "ℹ️ شما قبلاً با این رمز وارد شده‌اید."

    # ✅ اگر نسخه 000 دار وجود دارد → ورود مجدد
    if ghost in users:
        users[user_id] = users[ghost]   # حفظ حجم
        users.pop(ghost)
        save_db(db)
        return True, "✅ دوباره وارد شدید (حجم قبلی حفظ شد)."

    # ✅ بررسی ظرفیت
    if len(users) >= key.get("max_users", 0):
        return False, "❌ ظرفیت کاربران این رمز تکمیل شده است."

    # ✅ ورود جدید
    users[user_id] = 0
    save_db(db)
    make_backup("join_key") #بکاپ
    cleanup_old_backups()
    return True, "✅ با موفقیت وارد شدید."


def user_has_valid_key(bale_user_id):
    db = load_db()
    now = int(time.time())

    for key_name, key in db.get("keys", {}).items():

        if key.get("is_active") != 1:
            continue

        if key.get("expire", 0) <= now:
            deactivate_key(key_name, reason="expire", do_backup=False)
            continue   
        

        if str(bale_user_id) in key.get("users", {}):
            return True

    return False

def get_inactive_keys():
    db = load_db()
    return {
        k: v for k, v in db.get("keys", {}).items()
        if v.get("is_active") == 0
    }


def add_user_volume(bale_user_id, used_bytes):
    key_name, key = get_user_key(bale_user_id)
    if not key:
        return None

    db = load_db()
    uid = str(bale_user_id)
    used_mb = used_bytes / (1024 * 1024)

    db["keys"][key_name]["users"][uid] = round(
        db["keys"][key_name]["users"].get(uid, 0) + used_mb, 2
    )

    save_db(db)

    return check_and_deactivate_key_by_volume(
        key_name,
        db["keys"][key_name]
    )



# -----------------------------------------------
# ✔ اشتراک کاربر
# -----------------------------------------------
def get_user_key(bale_user_id):
    db = load_db()
    uid = str(bale_user_id)

    for key_name, key in db.get("keys", {}).items():
        if key.get("is_active") != 1:
            continue
        if uid in key.get("users", {}):
            return key_name, key

    return None, None

def get_key_used_volume(key):
    return round(sum(key.get("users", {}).values()), 2)

import time

def get_time_info(key):
    created = key.get("created_at")
    expire = key.get("expire")

    if not created or not expire:
        return 0, 0

    total_seconds = expire - created
    total_days = total_seconds // 86400

    remaining = max(0, expire - int(time.time()))
    remaining_days = remaining // 86400

    return total_days, remaining_days

def leave_key(user_id):
    db = load_db()
    user_id = str(user_id)
    ghost = ghost_id(user_id)
    changed = False

    for key in db.get("keys", {}).values():
        users = key.get("users", {})

        if user_id in users:
            # ✅ تبدیل به ایدی روح
            users[ghost] = users[user_id]
            users.pop(user_id)
            changed = True
            break

    # 🔌 قطع لینک اتصال
    old_token = get_link_by_bale(user_id)
    if old_token:
        pair = get_pair(old_token)
        deactivate(old_token)

        if pair and pair.get("tg_user_id"):
            pass
            #tg_send_text(
            #    pair["tg_user_id"],
            #    "❌ از اشتراک خارج شدید و اتصال قطع شد."
            #)
        changed = True

    if changed:
        save_db(db)
        make_backup("leave_key") #بکاپ
        cleanup_old_backups()

    return changed


# خروجی معنایی
# None | "warn_80" | "expired"

def check_and_deactivate_key_by_volume(key_name, key):
    total = key.get("volume", 0)
    used = sum(key.get("users", {}).values())

    if total <= 0:
        return None

    percent = (used / total) * 100

    if percent >= 100:
        deactivate_key(key_name, reason="volume")
        return "expired"

    if percent >= 80 and not key.get("warned_80"):
        db = load_db()
        db["keys"][key_name]["warned_80"] = True
        save_db(db)
        return "warn_80"

    return None

# -----------------------------------------------
# سیستم بکاپ
# -----------------------------------------------
def make_backup(reason: str):
    """
    reason examples:
    - auto_30min
    - create_key
    - deactivate_key
    - join_key
    - leave_key
    """

    if not os.path.exists(DB_PATH):
        return None

    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)

    # ✅ شرط: حداقل یک key
    if not db.get("keys"):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{reason}_{timestamp}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    return backup_path


def restore_backup(file_path):
    try:
        shutil.copy(file_path, DB_PATH)
        return True
    except Exception as e:
        print("RESTORE ERROR:", e)
        return False

def cleanup_old_backups(limit=10):
    if not os.path.exists(BACKUP_DIR):
        return

    files = sorted(
        os.listdir(BACKUP_DIR),
        key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
        reverse=True
    )

    for f in files[limit:]:
        os.remove(os.path.join(BACKUP_DIR, f))


