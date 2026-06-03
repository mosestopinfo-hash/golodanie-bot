# db.py — работа с базой данных SQLite

import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            last_name   TEXT,
            step        TEXT DEFAULT 'start',
            paid        INTEGER DEFAULT 0,
            created_at  TEXT,
            updated_at  TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS photo_cache (
            filename    TEXT PRIMARY KEY,
            file_id     TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            direction   TEXT,  -- 'in' or 'out'
            text        TEXT,
            created_at  TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_user(user_id: int, username: str, first_name: str, last_name: str):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO users (user_id, username, first_name, last_name, step, paid, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'start', 0, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            updated_at=excluded.updated_at
    """, (user_id, username, first_name, last_name, now, now))
    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def set_step(user_id: int, step: str):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE users SET step=?, updated_at=? WHERE user_id=?", (step, now, user_id))
    conn.commit()
    conn.close()


def set_paid(user_id: int, paid: bool = True):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE users SET paid=?, updated_at=? WHERE user_id=?", (int(paid), now, user_id))
    conn.commit()
    conn.close()


def get_photo_id(filename: str) -> Optional[str]:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT file_id FROM photo_cache WHERE filename=?", (filename,))
    row = c.fetchone()
    conn.close()
    return row["file_id"] if row else None


def cache_photo(filename: str, file_id: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO photo_cache (filename, file_id) VALUES (?, ?)
    """, (filename, file_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_message(user_id: int, direction: str, text: str):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO messages (user_id, direction, text, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, direction, text, now))
    conn.commit()
    conn.close()
