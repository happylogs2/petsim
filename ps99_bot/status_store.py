"""
Shared SQLite-backed state store. Bot processes, the API poller, and the
dashboard all touch this file. SQLite in WAL mode handles concurrent
multi-process reads/writes cleanly without needing a separate DB server -
plenty for 15 writers and one reader polling every few seconds.
"""
import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "status.db"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            serial TEXT PRIMARY KEY,
            account_name TEXT,
            roblox_username TEXT,
            current_zone TEXT,
            state TEXT,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_stats (
            roblox_username TEXT PRIMARY KEY,
            diamonds INTEGER,
            coins_json TEXT,
            rank INTEGER,
            rebirths INTEGER,
            fetched_at REAL
        )
    """)
    conn.commit()
    conn.close()


def update_bot_state(serial, account_name, roblox_username, current_zone, state):
    conn = _connect()
    conn.execute("""
        INSERT INTO bot_state (serial, account_name, roblox_username, current_zone, state, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(serial) DO UPDATE SET
            account_name=excluded.account_name,
            roblox_username=excluded.roblox_username,
            current_zone=excluded.current_zone,
            state=excluded.state,
            updated_at=excluded.updated_at
    """, (serial, account_name, roblox_username, current_zone, state, time.time()))
    conn.commit()
    conn.close()


def update_api_stats(roblox_username, diamonds, coins: dict, rank, rebirths):
    conn = _connect()
    conn.execute("""
        INSERT INTO api_stats (roblox_username, diamonds, coins_json, rank, rebirths, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(roblox_username) DO UPDATE SET
            diamonds=excluded.diamonds,
            coins_json=excluded.coins_json,
            rank=excluded.rank,
            rebirths=excluded.rebirths,
            fetched_at=excluded.fetched_at
    """, (roblox_username, diamonds, json.dumps(coins), rank, rebirths, time.time()))
    conn.commit()
    conn.close()


def get_all_status():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    bot_rows = conn.execute("SELECT * FROM bot_state").fetchall()
    api_rows = {r["roblox_username"]: r for r in conn.execute("SELECT * FROM api_stats").fetchall()}
    conn.close()

    result = []
    for b in bot_rows:
        api = api_rows.get(b["roblox_username"])
        result.append({
            "serial": b["serial"],
            "account_name": b["account_name"],
            "roblox_username": b["roblox_username"],
            "current_zone": b["current_zone"],
            "bot_state": b["state"],
            "bot_updated_at": b["updated_at"],
            "diamonds": api["diamonds"] if api else None,
            "coins": json.loads(api["coins_json"]) if api else {},
            "rank": api["rank"] if api else None,
            "rebirths": api["rebirths"] if api else None,
            "stats_fetched_at": api["fetched_at"] if api else None,
        })
    return result
