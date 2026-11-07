#!/usr/bin/env python3
"""Check FPV YouTube channels for new videos and post them to Discord."""
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from discord import post

# Channels to watch: a channel ID (starts with UC) or an @handle.
CHANNELS = [
    "@JoshuaBardwell",
    "UCxpgzA0iO-7anEAyiLMDRmg",  # Mads Tech
    "@UAVTech",
    "@ChrisRosser",
    "UCBGpbEe0G9EchyGYCRRd4hg",  # Nick Burns
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
DESC_LEN = 300
MAX_AGE = timedelta(days=2)  # only post videos newer than this
MAX_PER_RUN = 3              # per channel, per run


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


def walk(node):
    """Yield every dict inside a nested JSON structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


AGE_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400,
             "week": 604800, "month": 2592000, "year": 31536000}


def find_age(node):
    """Find a text like '3 hours ago' inside a video item and turn it into an age."""
    for d in walk(node):
        for val in d.values():
            if isinstance(val, str):
                m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", val)
                if m:
                    return timedelta(seconds=int(m.group(1)) * AGE_UNITS[m.group(2)])
    return None


def parse_page(cid):
    """Fallback: read the latest videos from the channel's Videos page."""
    html = fetch(f"https://www.youtube.com/channel/{cid}/videos").decode("utf-8", "ignore")
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise ValueError("video list not found on channel page")
    data = json.loads(m.group(1))
    author = ""
    videos, ids = [], set()
    for d in walk(data):
        if not author and "channelMetadataRenderer" in d:
            author = d["channelMetadataRenderer"].get("title", "")
        vid = title = None
        if "videoRenderer" in d:
            r = d["videoRenderer"]
            vid = r.get("videoId")
            runs = r.get("title", {}).get("runs") or [{}]
            title = runs[0].get("text") or r.get("title", {}).get("simpleText")
        elif "lockupViewModel" in d:
            r = d["lockupViewModel"]
            vid = r.get("contentId")
            title = (r.get("metadata", {}).get("lockupMetadataViewModel", {})
                     .get("title", {}).get("content"))
        if vid and title and vid not in ids:
            ids.add(vid)
            videos.append({
                "id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "published": None,
                "age": find_age(r),
                "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            })
    return author, videos[:15]


def get_videos(cid):
    try:
        return parse_feed(fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"))
    except Exception:
        return parse_page(cid)


def get_details(vid):
    """Read the publish date and a short, clean description from the video page."""
    try:
        html = fetch(f"https://www.youtube.com/watch?v={vid}").decode("utf-8", "ignore")
    except Exception:
        return None, ""
    published = None
    m = re.search(r'"(?:publishDate|uploadDate)":"([^"]+)"', html)
    if m:
        try:
            published = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
        except ValueError:
            published = None
    text = ""
    m = re.search(r'"shortDescription":("(?:[^"\\]|\\.)*")', html)
    if m:
        text = json.loads(m.group(1))
        # Only the first paragraph: the rest is usually links, sponsors and codes.
        text = re.split(r"\n\s*\n", text.strip())[0]
        lines = []
        for line in text.splitlines():
            line = re.sub(r"https?://\S+", "", line)
            line = re.sub(r"#\w+", "", line).strip(" -:|•")
            if line:
                lines.append(line)
        text = "\n".join(lines)
        if len(text) > DESC_LEN:
            text = text[:DESC_LEN].rsplit(" ", 1)[0].rstrip() + "…"
    return published, text


def build_embed(author, v):
    embed = {
        "author": {"name": f"🎬 {author}"},
        "title": v["title"],
        "url": v["url"],
        "color": 0xFF0000,
        "footer": {"text": "GyroGhost"},
    }
    if v.get("description"):
        embed["description"] = v["description"]
    if v["published"]:
        embed["timestamp"] = v["published"]
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
            author, videos = get_videos(cid)
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
        # Position of the newest video we already know (the list is newest first).
        first_known = next((i for i, v in enumerate(videos) if v["id"] in known), len(videos))
        now = datetime.now(timezone.utc)
        posted = 0
        for v in reversed(new):  # oldest first
            published, v["description"] = get_details(v["id"])
            if published is None and v.get("published"):
                published = datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
            if published is None and v.get("age") is not None:
                published = now - v["age"]
            if published is None:
                # No date at all: trust it only if it sits above every known video.
                fresh = videos.index(v) < first_known
            else:
                fresh = now - published <= MAX_AGE
            if not fresh or posted >= MAX_PER_RUN:
                print(f"{channel}: skipped old {v['title']}")
                continue
            if published is None:
                published = now
            v["published"] = published.isoformat()
            for server, room in TARGETS:
                post(server, room, build_embed(author, v))
            posted += 1
            print(f"{channel}: posted {v['title']}")
        # Keep a longer history so a video never gets posted twice.
        seen[cid] = ([v["id"] for v in new] + known)[:50]

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


if __name__ == "__main__":
    main()
