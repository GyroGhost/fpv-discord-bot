"""Shared Discord helpers for both servers (Arabic + English)."""
import json
import os
import urllib.error
import urllib.request

# Webhook secrets per server and room. A missing secret = that room is skipped.
WEBHOOKS = {
    "ar": {
        "updates": os.environ.get("AR_WEBHOOK_UPDATES", ""),
        "issues": os.environ.get("AR_WEBHOOK_ISSUES", ""),
    },
    "en": {
        "updates": os.environ.get("EN_WEBHOOK_UPDATES", ""),
        "issues": os.environ.get("EN_WEBHOOK_ISSUES", ""),
    },
}

BOT_NAMES = {"ar": "FPV Arabia", "en": "GyroGhost"}


def post(server, room, embed):
    url = WEBHOOKS[server][room]
    if not url:
        print(f"skip {server}/{room}: webhook not set")
        return False
    payload = {"username": BOT_NAMES[server], "embeds": [embed]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json",
        "User-Agent": "GyroGhost-fpv-bot",
    })
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.URLError as e:
        print(f"failed {server}/{room}: {e}")
        return False
    print(f"posted {server}/{room}")
    return True
