#db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py #db_manager.py 
import json
import os
import uuid
import time

DB_PATH = "data/db.json"


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
    if token not in db["links"]:
        return False

    pair = db["links"][token]
    pair["active"] = False

    if pair["bale_user_id"]:
        db["bale_users"].pop(str(pair["bale_user_id"]), None)
    if pair["tg_user_id"]:
        db["tg_users"].pop(str(pair["tg_user_id"]), None)

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
        "users": {}   # user_id: used_volume
    }

    save_db(db)


def get_active_keys():
    db = load_db()
    return {
        k: v for k, v in db.get("keys", {}).items()
        if v.get("is_active") == 1
    }


def deactivate_key(key_name):
    db = load_db()

    key = db.get("keys", {}).get(key_name)
    if not key:
        return False

    # تمام کاربران متصل به این key
    users = list(key.get("users", {}).keys())

    # غیرفعال کردن key
    key["is_active"] = 0
    key["users"] = {}

    # ⛔ cascade: قطع لینک همه کاربران
    for bale_user_id in users:
        token = db["bale_users"].pop(str(bale_user_id), None)
        if not token:
            continue

        pair = db["links"].get(token)
        if not pair:
            continue

        pair["active"] = False

        if pair.get("tg_user_id"):
            db["tg_users"].pop(str(pair["tg_user_id"]), None)

    save_db(db)
    return True

# ==========================================
# ✅ User Join Key (Stage 3.2)
# ==========================================

def join_key(key_name, user_id):
    db = load_db()

    key = db.get("keys", {}).get(key_name)
    if not key:
        return False, "❌ این رمز وجود ندارد."

    if key.get("is_active") != 1:
        return False, "❌ این رمز غیرفعال است."

    now = int(time.time())
    if key.get("expire", 0) <= now:
        return False, "❌ این رمز منقضی شده است."

    users = key.get("users", {})

    if str(user_id) in users:
        return False, "ℹ️ شما قبلاً با این رمز وارد شده‌اید."

    if len(users) >= key.get("max_users", 0):
        return False, "❌ ظرفیت کاربران این رمز تکمیل شده است."

    # ✅ attach user
    users[str(user_id)] = 0
    key["users"] = users

    save_db(db)
    return True, "✅ با موفقیت وارد شدید."

def user_has_valid_key(bale_user_id):
    db = load_db()
    now = int(time.time())

    for key_name, key in db.get("keys", {}).items():

        if key.get("is_active") != 1:
            continue

        if key.get("expire", 0) <= now:
            key["is_active"] = 0
            key["users"] = {}

            # ⛔ قطع همه لینک‌های مربوط
            for token, pair in db.get("links", {}).items():
                if pair.get("bale_user_id") == bale_user_id:
                    pair["active"] = False
                    if pair.get("tg_user_id"):
                        db["tg_users"].pop(str(pair["tg_user_id"]), None)
                    db["bale_users"].pop(str(bale_user_id), None)

            save_db(db)
            return False

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
    """
    used_bytes: حجم واقعی بر حسب بایت
    """
    db = load_db()
    used_mb = used_bytes / (1024 * 1024)

    for key in db.get("keys", {}).values():
        if key.get("is_active") != 1:
            continue

        users = key.get("users", {})
        uid = str(bale_user_id)

        if uid in users:
            users[uid] = round(users.get(uid, 0) + used_mb, 2)
            key["users"] = users
            save_db(db)
            return True

    return False
