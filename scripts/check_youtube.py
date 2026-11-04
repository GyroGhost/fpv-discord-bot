#!/usr/bin/env python3
"""Check FPV YouTube channels for new videos and post them to Discord."""
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

from discord import post

# Channels to watch: a channel ID (starts with UC) or an @handle.
CHANNELS = [
    "@JoshuaBardwell",
    "@UAVTech",
    "@MadsTech",
    "@ChrisRosser",
    "UCBGpbEe0G9EchyGYCRRd4hg",
]

# Where to post: (server, room)
TARGETS = [("en", "videos")]

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "youtube.json")
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (GyroGhost-fpv-bot)", "Accept-Language": "en"}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def resolve(channel, ids):
    """Turn an @handle into a channel ID (cached in state)."""
    if channel.startswith("UC"):
        return channel
    if channel in ids:
        return ids[channel]
    html = fetch(f"https://www.youtube.com/{channel}").decode("utf-8", "ignore")
    m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', html)
    if not m:
        raise ValueError("channel ID not found")
    ids[channel] = m.group(1)
    return ids[channel]


def parse_feed(xml):
    root = ET.fromstring(xml)
    author = root.findtext("a:author/a:name", default="", namespaces=NS)
    videos = []
    for e in root.findall("a:entry", NS):
        thumb = e.find("media:group/media:thumbnail", NS)
        videos.append({
            "id": e.findtext("yt:videoId", namespaces=NS),
            "title": e.findtext("a:title", namespaces=NS),
            "url": e.find("a:link", NS).get("href"),
            "published": e.findtext("a:published", namespaces=NS),
            "thumb": thumb.get("url") if thumb is not None else None,
        })
    return author, videos


def build_embed(author, v):
    embed = {
        "author": {"name": f"🎬 {author}"},
        "title": v["title"],
        "url": v["url"],
        "color": 0xFF0000,
        "timestamp": v["published"],
        "footer": {"text": "GyroGhost"},
    }
    if v["thumb"]:
        embed["image"] = {"url": v["thumb"]}
    return embed


def main():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    ids = state.setdefault("ids", {})
    seen = state.setdefault("seen", {})

    for channel in CHANNELS:
        try:
            cid = resolve(channel, ids)
            author, videos = parse_feed(
                fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"))
        except Exception as e:
            print(f"{channel}: {e}")
            continue
        if not videos:
            continue

        known = seen.get(cid)
        if known is None:
            # First run: remember current videos without posting them.
            seen[cid] = [v["id"] for v in videos]
            print(f"{channel}: seeded ({author})")
            continue

        new = [v for v in videos if v["id"] not in known]
        for v in reversed(new):  # oldest first
            for server, room in TARGETS:
                post(server, room, build_embed(author, v))
            print(f"{channel}: posted {v['title']}")
        seen[cid] = [v["id"] for v in videos]

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
