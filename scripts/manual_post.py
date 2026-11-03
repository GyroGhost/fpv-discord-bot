#!/usr/bin/env python3
"""Post a manual FPV update or problem/fix to the chosen server(s) and room."""
import os
import sys

from discord import post

SERVER = os.environ.get("SERVER", "")
ROOM = os.environ.get("ROOM", "")
KIND = os.environ.get("KIND", "")
TITLE = os.environ.get("TITLE", "").strip()
DETAILS = os.environ.get("DETAILS", "").strip().replace("\\n", "\n")
LINK = os.environ.get("LINK", "").strip()
IMAGE = os.environ.get("IMAGE", "").strip()

# kind -> (icon, color, Arabic label, English label)
KINDS = {
    "مشكلة": ("⚠️", 0xE53935, "مشكلة", "Problem"),
    "حل": ("✅", 0x43A047, "حل", "Fix"),
    "نصيحة": ("💡", 0x1E90FF, "نصيحة", "Tip"),
    "تحديث": ("📢", 0xFFBB00, "تحديث", "Update"),
}

SERVERS = {"العربي": ["ar"], "الانجليزي": ["en"], "الاثنين": ["ar", "en"]}
ROOMS = {"تحديثات": "updates", "مشاكل وحلول": "issues"}

if not TITLE:
    sys.exit("Title is required")

icon, color, ar_label, en_label = KINDS.get(KIND, ("📌", 0x888888, KIND, KIND))
room = ROOMS.get(ROOM, "issues")

sent = 0
for server in SERVERS.get(SERVER, ["ar"]):
    label = ar_label if server == "ar" else en_label
    embed = {
        "title": f"{icon} {label} | {TITLE}",
        "description": DETAILS,
        "color": color,
        "footer": {"text": "GyroGhost"},
    }
    if LINK:
        embed["url"] = LINK
    if IMAGE:
        embed["image"] = {"url": IMAGE}
    sent += post(server, room, embed)

if not sent:
    sys.exit("Nothing was sent: check the webhook secrets")
