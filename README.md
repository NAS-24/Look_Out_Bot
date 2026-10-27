<div align="center">

# 👁️ Look Out

**A background intelligence agent that watches the internet for you.**
Tell it what to watch once. It texts you when something actually matters.

![Version](https://img.shields.io/badge/Version-1.1.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Paused-orange?style=for-the-badge)

</div>

---

## 🧭 About

Staying updated on time-sensitive things (hackathon registrations, recruitment notifications, product launches) usually means checking the same pages again and again, or relying on keyword alerts that spam you with noise.

**Look Out** is a server-side, always-on daemon. You send a natural-language request to a Telegram bot, and it:

1. Validates your request
2. Finds and verifies the page worth watching
3. Scrapes it on a smart schedule
4. Compares it against what it saw last time
5. Uses an LLM to judge whether the change actually matches your intent
6. Messages you only if it does

No dashboard. No browser extension. The product lives in the notification.

> **Example prompts**
> - *"Watch this page and tell me when SBI Clerk 2026 recruitment is announced"*
> - *"Tell me when Flipkart Grid 8.0 registrations open"*

---

## ⚙️ How It Works

```
User (Telegram)
   │
   ▼
1. App Guard      → one active watch per user? (config.py limit)
2. LLM Guard      → is this a valid, single-intent, monitorable request?
3. Source Setup   → infer source timezone + active window, verify the URL
4. Initial Scan   → check if the intent is ALREADY satisfied (Day Zero)
   │
   ▼
Scheduler (sleeps until MIN(next_scrape_at))
   │
   ▼
5. Playwright     → render the page (JS-heavy sites supported)
6. BeautifulSoup  → strip nav, footer, scripts, forms → clean text
7. SHA-256 hash   → same as last time? stop. (zero LLM cost)
8. LLM Judge      → old text + new text + your intent → { is_meaningful, summary }
9. Telegram       → plain-language alert, then auto-pause the watch
```

### The dual filter

| Stage | Purpose | Cost |
|---|---|---|
| **Filter 1: SHA-256 hash** | Detects whether the visible text changed at all | Free |
| **Filter 2: LLM judge** | Decides whether the change matters *to your intent* | One API call, only when the hash differs |

This keeps visitor counters, rotating ads, and timestamps from ever reaching the LLM or your phone.

---

## ✨ Features

- **Natural-language watches**: no selectors, no keywords, no config
- **Prompt guard**: rejects trivia questions and multi-intent prompts
- **Day Zero scan**: tells you immediately if what you're waiting for already happened
- **Event-driven scheduler**: sleeps until the next due watch instead of polling the database
- **Active-window scheduling**: checks more often during the source's business hours (in the *source's* timezone), less often overnight
- **Auto-kill switch**: watches pause themselves after a successful alert
- **Circuit breaker**: if a site is down or blocks the scraper, the watch pauses and you're told why
- **Unauthenticated scraping only**: never logs in, never stores cookies or private data

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| LLM | `openai/gpt-oss-20b` via Groq |
| Scraping | Playwright (headless Chromium) |
| DOM cleaning | BeautifulSoup |
| Scheduling | Event-driven min-heap scheduler with `interruptible_sleep()` |
| Database | PostgreSQL (Neon.tech) via `psycopg2` |
| Delivery | Telegram Bot API |
| Deployment | Docker, GitHub CI/CD, Render |
| Uptime | UptimeRobot (keeps the free-tier container awake) |

---

## 🗄️ Database Schema

**users**
- `id`, `telegram_id`, `created_at`

**prompts**
- `id`, `user_id`, `raw_prompt`, `target_url`, `is_active`, `created_at`
- `active_window_start`, `active_window_end`: inferred by the LLM, user-overridable later
- `source_timezone`: IANA string, e.g. `Asia/Kolkata`
- `next_scrape_at`: the single timestamp the scheduler's `MIN()` query reads

**scrape_history**
- `id`, `prompt_id`, `content_hash`, `clean_text`, `scraped_at`

All queries are parameterised (`%s` placeholders) to prevent SQL injection.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A [Groq](https://console.groq.com) API key
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A PostgreSQL database (Neon's free tier works)

### Local setup

```bash
# 1. Clone
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

# 2. Install dependencies
pip install -r requirements.txt
playwright install --with-deps chromium

# 3. Configure environment
cp .env.example .env   # then fill in the values below

# 4. Create tables
psql "$DATABASE_URL" -f database/schema.sql

# 5. Run
./start.sh
```

### Environment variables

```env
GROQ_API_KEY=your_groq_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://user:password@host/dbname
```

> Never commit your `.env` file.

### Docker

```bash
docker build -t look-out .
docker run --env-file .env -p 8000:8000 look-out
```

`start.sh` boots the bot, the scraping engine, and a tiny HTTP server so free-tier hosts see an open port.

---

## 📁 Project Structure

```
look_out/
├── bot.py               # Telegram interface: intake, guards, conversation flow
├── main.py              # Daemon: scheduler, scrape → hash → judge → notify
├── manager.py           # Database layer
├── config.py            # Limits and settings (e.g. MAX_ACTIVE_WATCHES_PER_USER)
├── scraper/
│   ├── engine.py        # Playwright renderer
│   └── cleaner.py       # BeautifulSoup sanitiser
├── intelligence/
│   └── evaluator.py     # LLM guard, parameter extraction, diff judge
├── utils/
│   └── hasher.py        # SHA-256 fingerprinting
├── database/
│   └── schema.sql
├── start.sh             # Ignition script
├── Dockerfile
└── requirements.txt
```

---

## 🧯 Production Edge Cases Solved

Real problems hit during live deployment:

| Problem | Fix |
|---|---|
| Free tier requires an open web port | Dummy HTTP server in `start.sh` |
| Free tier sleeps after 15 min idle | UptimeRobot pings every 5 min |
| Default `/healthz` check returned 404 | Health check path set to `/` |
| Windows vs Linux filename casing | Corrected file reference in `start.sh` |
| Ephemeral disk wiped SQLite on restart | Migrated to cloud PostgreSQL |
| SQL injection and concurrent writes | Parameterised queries, `SERIAL` keys |
| `time.sleep()` froze the whole daemon | Min-heap scheduler with wake-flag interrupt |
| Event already happened before the watch was set | Day Zero initial scan |
| Finished watches kept burning API calls | Auto-kill switch |
| Blocked or offline target sites | Circuit breaker with user alert |
| Users flooding the system with watches | Configurable per-user limit |
| Live counters triggering false alerts | Hash filter + LLM judge |
| Neon compute exhausted by 10-second polling | Event-driven scheduler (v1.1.0) |
| Groq deprecated Llama 3.3 70B | Migrated to `gpt-oss-20b` (v1.1.0) |

---

## ⚠️ Known Limitations

- **Intent matching is not reliable yet.** In live tests, the judge missed a phone becoming available to buy and a new recruitment listing appearing. The evaluator prompt needs work.
- **Heavily protected sites** (Amazon, some e-commerce) may block headless browsers.
- **One active watch per user**, by design for v1.
- **Telegram only** for now.
- **Free-tier infrastructure** can sleep or hit quotas. Monitor Neon and Render usage.

---

## 🗺️ Roadmap

- [x] Deterministic core: scraper, cleaner, hashing
- [x] Intelligence layer: guard, judge, parameter inference
- [x] Telegram delivery, Docker, CI/CD
- [x] Event-driven scheduler and active windows
- [ ] Fix intent matching in the evaluator
- [ ] Web interface for managing watches
- [ ] Multiple watches per user
- [ ] Phone-number-linked notifications beyond Telegram

---

## 📌 Status

Look Out is currently **paused**. The architecture is documented above and the codebase is deployable, but active development is on hold.

---

## 📄 License

MIT. See [LICENSE](LICENSE).

---

<div align="center">
Built by <b>Naman Sinha</b>
</div>
