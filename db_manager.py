import json
import os
import uuid

DB_PATH = "data/db.json"


def load_db():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        # نسخه اولیه دیتابیس با فیلد auto_delete
        save_db({"links": {}, "bale_users": {}, "tg_users": {}})
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
