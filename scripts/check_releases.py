#!/usr/bin/env python3
"""Check FPV projects for new GitHub releases and post them to both servers."""
import json
import os
import re
import urllib.error
import urllib.request

from discord import post

# Projects to watch. Add or remove repos here.
REPOS = {
    "betaflight/betaflight": "Betaflight Firmware",
    "betaflight/betaflight-configurator": "Betaflight Configurator",
    "ExpressLRS/ExpressLRS": "ExpressLRS Firmware",
    "ExpressLRS/ExpressLRS-Configurator": "ExpressLRS Configurator",
    "iNavFlight/inav": "INAV Firmware",
    "iNavFlight/inav-configurator": "INAV Configurator",
    "EdgeTX/edgetx": "EdgeTX",
    "am32-firmware/AM32": "AM32 ESC Firmware",
}

# Skip auto-built releases so the channel doesn't get spammed every night.
SKIP_TAGS = ("nightly", "latest", "dev")

COLORS = {
    "betaflight": 0xFFBB00,
    "ExpressLRS": 0x1E90FF,
    "iNavFlight": 0x2ECC71,
    "EdgeTX": 0x9B59B6,
    "am32-firmware": 0xE74C3C,
}

LABELS = {
    "ar": {"type": "النوع", "Release": "Release", "Pre-release": "Pre-release (تجريبي)",
           "new": "إصدار جديد"},
    "en": {"type": "Type", "Release": "Release", "Pre-release": "Pre-release",
           "new": "New release"},
}

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state", "releases.json")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SUMMARY_LEN = 600


def gh_get(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GyroGhost-fpv-bot"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def clean_notes(body):
    if not body:
        return ""
    text = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > SUMMARY_LEN:
        text = text[:SUMMARY_LEN].rsplit("\n", 1)[0].rstrip() + "\n…"
    return text


def build_embed(server, name, rel, org):
    L = LABELS[server]
    kind = "Pre-release" if rel.get("prerelease") else "Release"
    return {
        "author": {"name": L["new"]},
        "title": f"{name} {rel['tag_name']}",
        "url": rel["html_url"],
        "description": clean_notes(rel.get("body")),
        "color": COLORS.get(org, 0x888888),
        "fields": [{"name": L["type"], "value": L[kind], "inline": True}],
        "timestamp": rel.get("published_at"),
        "footer": {"text": "GyroGhost"},
    }


def main():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}

    changed = False
    for repo, name in REPOS.items():
        try:
            releases = gh_get(f"https://api.github.com/repos/{repo}/releases?per_page=5")
        except urllib.error.HTTPError as e:
            print(f"{repo}: {e}")
            continue
        if not releases:
            continue

        last_seen = state.get(repo)
        if last_seen is None:
            # First run: remember the latest release without posting old ones.
            state[repo] = releases[0]["id"]
            changed = True
            print(f"{repo}: seeded at {releases[0]['tag_name']}")
            continue

        new = [
            r for r in releases
            if r["id"] > last_seen
            and not r.get("draft")
            and not any(k in r["tag_name"].lower() for k in SKIP_TAGS)
        ]
        for rel in sorted(new, key=lambda r: r["id"]):
            org = repo.split("/")[0]
            for server in ("ar", "en"):
                post(server, "updates", build_embed(server, name, rel, org))
            state[repo] = rel["id"]
            changed = True

    if changed:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")


if __name__ == "__main__":
    main()
