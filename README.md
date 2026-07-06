# Dayp

A privacy-first, local-only dashboard for tracking daily computer usage, AI news, and email summaries — with an auto-generated weekly work report.

> [中文说明](./README.zh-CN.md)

## Features

- **App Usage Tracking** — samples the foreground window every second and aggregates per-process time
- **AI News** — fetches trending AI stories from Hacker News and Chinese sources (36Kr, Leiphone, ifanr, AIbase, Huxiu), refreshed hourly
- **Email Digest** — reads recently synced emails via local Outlook COM automation
- **Weekly Report** — rule-based summary from usage + email data
- **Dashboard** — dark-themed browser UI with doughnut + stacked bar charts (Chart.js)

## Requirements

- Windows 10/11
- Python 3.12+ (native Windows CPython; MSYS2/MinGW not supported)
- Outlook desktop client (signed in and synced at least once)

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If native Python is missing, download it from https://www.python.org/downloads/ and check "Add to PATH".

## Run

A single command starts the API server, background agent (window tracker, news fetchers, mail fetcher, daily aggregator), and opens the browser automatically:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The dashboard appears at http://127.0.0.1:8000

- Closing the browser tab stops the agent and the server automatically (heartbeat-based, 15s timeout).
- Press `Ctrl+C` in the terminal to stop manually.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/usage/today` | Today's per-app time and percentage |
| GET | `/api/usage/week` | Last 7 days stacked chart data |
| GET | `/api/usage/date/{YYYY-MM-DD}` | Usage for a specific date |
| GET | `/api/emails?days=7` | Recent emails |
| GET | `/api/news?limit=50` | Latest AI news |
| GET | `/api/summary/week` | Weekly report text |
| POST | `/api/heartbeat` | Browser heartbeat (auto-stop) |
| GET | `/api/health` | Health check |

## Storage

All data is stored in `data/dayp.db` (SQLite), 4 tables:

- `app_usage` — per-second window samples
- `daily_summary` — per-process daily aggregation
- `emails` — email records (deduped by EntryID)
- `news` — AI news (deduped by id)

## Privacy

- All data stays local; nothing is uploaded.
- Emails are read via local Outlook COM, never over the network.
- The only external network requests are Hacker News API and public RSS feeds.

## Troubleshooting

**`No module named 'win32gui'`** — Use native Windows Python, not MSYS2. Run `python -c "import sys; print(sys.platform)"`; it should print `win32`, and `sys.executable` should not be under `C:\msys64`.

**Emails empty** — Ensure Outlook desktop is installed, an account is signed in, and the inbox has mail. Outlook doesn't need to be running when the agent starts, but the account must be configured.

**News empty** — Check network access to `https://hacker-news.firebaseio.com`. First fetch takes ~10-30s.
