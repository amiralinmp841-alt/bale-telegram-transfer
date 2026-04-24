import sqlite3
import time
import json
import zipfile
import os

DB_NAME = "panel.db"
BACKUP_JSON = "panel_backup.json"
BACKUP_ZIP = "panel_backup.zip"

ADMIN_ID = int(os.environ.get("ADMIN_BALE_ID"))

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        volume_limit INTEGER,
        expire_at INTEGER,
        max_users INTEGER,
        active INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        bale_id INTEGER,
        key TEXT,
        used_volume INTEGER,
        joined_at INTEGER
    )
    """)

    conn.commit()
    conn.close()


# ---------------- KEY ---------------- #

def create_key(key, volume_mb, expire_days, max_users):

    expire_at = int(time.time()) + expire_days * 86400

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO keys VALUES (?,?,?,?,1)",
        (key, volume_mb, expire_at, max_users)
    )

    conn.commit()
    conn.close()


def delete_key(key):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM keys WHERE key=?", (key,))
    c.execute("DELETE FROM users WHERE key=?", (key,))

    conn.commit()
    conn.close()


def get_key(key):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT * FROM keys WHERE key=?", (key,))
    row = c.fetchone()

    conn.close()
    return row


def count_users(key):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users WHERE key=?", (key,))
    count = c.fetchone()[0]

    conn.close()
    return count


# ---------------- USER ---------------- #

def assign_key_to_user(bale_id, key):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "INSERT INTO users VALUES (?,?,0,?)",
        (bale_id, key, int(time.time()))
    )

    conn.commit()
    conn.close()


def remove_user(bale_id):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM users WHERE bale_id=?", (bale_id,))

    conn.commit()
    conn.close()


def get_user_key(bale_id):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT key FROM users WHERE bale_id=?", (bale_id,))
    row = c.fetchone()

    conn.close()

    return row[0] if row else None


def update_usage(bale_id, bytes_used):

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute(
        "UPDATE users SET used_volume = used_volume + ? WHERE bale_id=?",
        (bytes_used, bale_id)
    )

    conn.commit()
    conn.close()


# ---------------- VALIDATION ---------------- #

def check_key_valid(key):

    row = get_key(key)

    if not row:
        return False

    expire_at = row[2]
    max_users = row[3]

    if expire_at < int(time.time()):
        return False

    if count_users(key) >= max_users:
        return False

    return True


# ---------------- BACKUP ---------------- #

def generate_backup():

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT * FROM keys")
    keys = c.fetchall()

    c.execute("SELECT * FROM users")
    users = c.fetchall()

    conn.close()

    data = {
        "keys": keys,
        "users": users
    }

    with open(BACKUP_JSON, "w") as f:
        json.dump(data, f)

    with zipfile.ZipFile(BACKUP_ZIP, "w") as z:
        z.write(BACKUP_JSON)

    return BACKUP_ZIP


def restore_backup(zip_path):

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall()

    with open(BACKUP_JSON) as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("DELETE FROM keys")
    c.execute("DELETE FROM users")

    for k in data["keys"]:
        c.execute("INSERT INTO keys VALUES (?,?,?,?,?)", tuple(k))

    for u in data["users"]:
        c.execute("INSERT INTO users VALUES (?,?,?,?)", tuple(u))

    conn.commit()
    conn.close()
