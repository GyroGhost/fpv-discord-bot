# FPV Discord Bot

Posts FPV news to two Discord servers (Arabic + English), each with an **updates** room and a **problems & fixes** room.

- **Auto Releases** — checks Betaflight and ExpressLRS every 3 hours and posts new releases to the updates room on both servers.
- **Post to Discord** — a manual form (Actions → Post to Discord → Run workflow) to post an update, problem, fix or tip to any server/room.

## Setup

Add these repo secrets (Settings → Secrets and variables → Actions):

| Secret | Room |
|---|---|
| `AR_WEBHOOK_UPDATES` | Arabic server – updates |
| `AR_WEBHOOK_ISSUES` | Arabic server – problems & fixes |
| `EN_WEBHOOK_UPDATES` | English server – updates |
| `EN_WEBHOOK_ISSUES` | English server – problems & fixes |

A missing secret just skips that room.

The first auto run only saves the latest release of each project, so old releases don't get spammed.

## Watched projects

Edit `REPOS` in `scripts/check_releases.py`.
