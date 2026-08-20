"""
Standalone process: polls the official BIG Games public player API
(ps99.biggamesapi.io) for each account's exact currency/rank data and
writes it into the shared status store. Runs independently of the bot
processes - it doesn't touch the game client at all, just HTTP.

Requires each account's "profile" view to be toggled public in-game.
Public profile reads are anonymous, never consume the per-account daily
refresh quota, and are cached server-side for ~5 minutes - polling
faster than that just re-fetches the same snapshot, so don't.
"""
import json
import time
import requests

import status_store

API_BASE = "https://ps99.biggamesapi.io/v1/players"
POLL_INTERVAL_S = 300  # matches the API's own 5-minute cache window


def fetch_profile(username: str):
    resp = requests.get(f"{API_BASE}/{username}", params={"include": "profile"}, timeout=10)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "ok":
        return None
    view = body.get("data", {}).get("views", {}).get("profile", {})
    if not view.get("available"):
        return None
    return view.get("data", {})


def extract_stats(profile_data: dict):
    currency = profile_data.get("Currency", {})
    diamonds = currency.get("Diamonds", {}).get("_am", 0)
    coins = {
        name: entry.get("_am", 0)
        for name, entry in currency.items()
        if name != "Diamonds"
    }
    rank = profile_data.get("Rank")
    rebirths = profile_data.get("Rebirths")
    return diamonds, coins, rank, rebirths


def poll_forever(usernames: list):
    while True:
        for username in usernames:
            try:
                profile = fetch_profile(username)
                if profile:
                    diamonds, coins, rank, rebirths = extract_stats(profile)
                    status_store.update_api_stats(username, diamonds, coins, rank, rebirths)
                    print(f"[{username}] diamonds={diamonds} rank={rank}")
                else:
                    print(f"[{username}] profile not public or not found")
            except Exception as e:
                print(f"[{username}] fetch failed: {e}")
            time.sleep(1)  # small stagger between accounts within one pass
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    with open("config/devices.json") as f:
        devices = json.load(f)
    usernames = [d["roblox_username"] for d in devices if d.get("roblox_username")]
    status_store.init_db()
    poll_forever(usernames)
