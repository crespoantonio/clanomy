# Deployment Guide: Clanomy (Render + Supabase + Groq Cloud)

This guide provides step-by-step instructions to deploy your own self-hosted **Clanomy** instance to the cloud on an **Always-Free ($0.00/month)** stack using **Render**, **Supabase**, and **Groq Cloud**.

In self-hosted mode (`ENABLE_SUBSCRIPTIONS=false`), Clanomy runs completely unrestricted with:
* **Unlimited voice & text transaction logging** (both expenses and income).
* **Multi-user family workspaces** with shared ledgers and member attribution.
* **Real-time encrypted Notion database synchronization**.
* **Zero-Knowledge AES-256 field encryption**.
* **Zero paywalls, tiers, quotas, or fees**.

---

## 🏗️ The Architecture (How It Works)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           SELF-HOSTED CLOUD ARCHITECTURE                                │
│                                                                                         │
│  [ Telegram User / Family ] ──► (Voice Notes & Text Expenses/Income)                    │
│                 │                                                                       │
│                 ▼ (HTTPS Webhook + X-Telegram-Bot-Api-Secret-Token)                     │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                            RENDER WEB SERVICE (Compute)                           │  │
│  │  • FastAPI Application (Python 3.12 / Uvicorn on Port $PORT)                      │  │
│  │  • Automatic Alembic Database Migrations on Lifespan Startup                      │  │
│  │  • Unrestricted Self-Hosted Mode (ENABLE_SUBSCRIPTIONS=false)                      │  │
│  │  • Real-time Notion Synchronizer & AI Orchestrator                                 │  │
│  └───────────────────┬─────────────────────────────────────────────┬─────────────────┘  │
│                      │ (AES-256 Encrypted Ledger)                  │ (AI Extraction)    │
│                      ▼                                             ▼                    │
│  ┌────────────────────────────────────────┐     ┌────────────────────────────────────┐  │
│  │       SUPABASE (PostgreSQL)            │     │       GROQ CLOUD (AI Engine)       │  │
│  │  • AES-256 Zero-Knowledge Encrypted DB │     │  • Whisper-Large-v3 Voice (150ms)  │  │
│  │  • IPv4 PgBouncer Connection Pooler    │     │  • Llama-3.3-70b Extraction (200ms)│  │
│  │  • Free Tier Managed Postgres          │     │  • Zero Container RAM Footprint    │  │
│  └────────────────────────────────────────┘     └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Telegram:** Chat client where you and your family log expenses and view financial insights.
* **Render:** Cloud hosting platform running the FastAPI application and webhook listener on the free tier.
* **Supabase:** Managed PostgreSQL database storing AES-256 encrypted transactions, users, and family workspaces.
* **Groq Cloud:** Ultra-fast AI inference engine executing Whisper voice transcription and Llama data extraction in <350ms with 0MB RAM burden on Render.

---

## 🛠️ Step 1: Create Your Telegram Bot (BotFather)

1. Open Telegram and search for `@BotFather` (the official bot with the blue checkmark).
2. **Create Bot:**
   * Send `/newbot`.
   * Provide a display name (e.g. `My Family Finance AI`).
   * Provide a username ending in `bot` (e.g. `MyFamilyClanomyBot`).
   * Copy the HTTP API token (e.g. `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`). Save it as `TELEGRAM_BOT_TOKEN`.
3. **Register Bot Commands:**
* Send `/setcommands` to `@BotFather`, select your bot, and paste:
```text
start - Start Clanomy and view workspace status
month - Full monthly breakdown for the household (/month last for prior month)
me - Personal breakdown of expenses, income, and top categories
today - Summary of transactions recorded today
bills - View upcoming scheduled bills and due dates
balance - Net cash flow and savings rate overview
undo - Revert your latest recorded transaction or batch
timezone - View or update household timezone (e.g. /timezone America/Argentina/Buenos_Aires)
currency - View or update household default currency (e.g. /currency ARS)
family - Manage family members and shared ledger
invite - Generate invite link for household members
notion - Connect and mirror transactions to Notion
export - Export financial logs to CSV or JSON
help - View available commands and AI logging tips
```
---
## 💾 Step 2: Set Up Database (Supabase)
1. Go to [https://supabase.com](https://supabase.com) and click **Start your project** (sign in with GitHub).
2. Click **New Project**, choose your organization, and name your project (e.g. `clanomy-db`).
3. **Set Database Password:** Choose a strong password and save it securely.
4. **Choose Region:** Pick the region closest to you (e.g. `US East (N. Virginia)` / `us-east-1` or `South America (São Paulo)` / `sa-east-1`).
5. Click **Create new project**.
6. **Obtain the Connection Pooler URI (IPv4 Safe):**
* In the Supabase left sidebar, click **⚙️ Project Settings** ➔ **Database**.
* Scroll down to **Connection string** ➔ select **URI** tab ➔ select **Pooler** (Session or Transaction mode).
* Copy the URI template:
```text
postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```
7. **Format URI for Clanomy (Psycopg3 Driver & URL Escaping):**
* Change the prefix from `postgresql://` to `postgresql+psycopg://`.
* **URL-Encode special characters in your password** (e.g. replace `@` with `%40`, `!` with `%21`, `*` with `%2A`, `$` with `%24`).
* Append `?sslmode=require` to the end.
* **Final `DATABASE_URL` Example:**
```text
postgresql+psycopg://postgres.hwdzwrvvekaogtqtvmia:9%40ka%21FfAA778Uo8%21Wd%2A%24@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```
> [!NOTE]
> Supabase direct hostnames (`db.<ref>.supabase.co`) only resolve over IPv6. Using the **Connection Pooler URL** (`aws-0-[region].pooler.supabase.com:6543`) ensures full IPv4 compatibility with Render.
---
## 🧠 Step 3: Get AI API Key (Groq / OpenAI Cloud)
Groq provides sub-second LLM and Whisper transcription inference for free:
1. Go to [https://console.groq.com](https://console.groq.com) and log in.
2. On the left sidebar, click **API Keys**.
3. Click **Create API Key**, name it (e.g. `clanomy-selfhosted`), and copy the key (starts with `gsk_`).
4. Save this key as `AI_API_KEY`.
---
## 🔐 Step 4: Generate Security Secrets
Generate cryptographic keys locally to protect your zero-knowledge encrypted database and webhook endpoint:
1. **`ENCRYPTION_KEY` (AES-256 Fernet Key):**
Run in your terminal:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
*Save the 32-byte URL-safe base64 string.*
2. **`MESSAGING_WEBHOOK_SECRET` (Webhook Authenticity Token):**
Run in your terminal:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
*Save this 32-byte hex string.*
---
## 🚀 Step 5: Deploy Web Service (Render)
1. Ensure your latest Clanomy code is pushed to your GitHub repository:
```bash
git add .
git commit -m "feat: configure cloud deployment"
git push origin master
```
2. Log into [https://dashboard.render.com](https://dashboard.render.com).
3. Click **New +** ➔ **Web Service**.
4. Connect your GitHub repository (`clanomy`).
5. Configure the Web Service settings:
* **Name:** `clanomy-api` (or `clanomy-bot`)
* **Region:** Same region as your Supabase database (e.g. `Virginia (US East)`).
* **Branch:** `master` (or `main`).
* **Runtime:** `Python 3`.
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
* **Instance Type:** `Free`.
6. **Environment Variables Configuration:**
Expand the **Environment Variables** section and add:
| Variable Key | Recommended Self-Hosted Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.8` | Pins stable Python runtime for C-extensions |
| `PYTHONUNBUFFERED` | `1` | Real-time live log streaming in Render console |
| `DATABASE_URL` | `postgresql+psycopg://postgres.[ref]:[escaped_pwd]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | Supabase IPv4 Pooler connection URI |
| `ENCRYPTION_KEY` | *(Your 32-byte Fernet key from Step 4)* | AES-256 Zero-Knowledge DB encryption |
| `TELEGRAM_BOT_TOKEN` | *(Your BotFather HTTP API token from Step 1)* | Telegram Bot API authentication |
| `MESSAGING_WEBHOOK_SECRET` | *(Your 32-character secret from Step 4)* | Validates `X-Telegram-Bot-Api-Secret-Token` |
| `ENABLE_SUBSCRIPTIONS` | `false` | Disables paywalls and unlocks all features for free |
| `AI_API_KEY` | `gsk_...` *(From Step 3)* | Fast cloud AI extraction, queries & voice notes |
| `WHISPER_PROVIDER` | `groq` | Cloud speech-to-text via Groq Whisper Large v3 |
| `DEFAULT_CURRENCY` | `USD` | Base fallback currency (e.g. `USD`, `ARS`, `EUR`, `MXN`) |
| `DEFAULT_TIMEZONE` | `UTC` | Household default timezone (e.g. `America/Argentina/Buenos_Aires`) |
| `ALLOWED_TELEGRAM_USERS` | `""` *(or comma-separated IDs)* | Restrict bot access to your Telegram ID(s) |
| `ENABLE_DOCS` | `false` | Disables public `/docs` swagger page |

7. Click **Deploy Web Service**.
8. Render will build and deploy your service. On startup, Clanomy automatically runs `alembic upgrade head`, creating all required tables (`family`, `user`, `transaction`, `scheduled_bill`, `familyinvite`) in Supabase.
9. When the status turns green (**Live**), copy your service URL (e.g. `https://clanomy-api.onrender.com`).
---
## 🔗 Step 6: Register Webhook with Telegram
Register your live Render URL and secret token with Telegram:
### Option A: Bash / Linux / macOS
```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://<YOUR_RENDER_URL>/api/v1/telegram/webhook",
       "secret_token": "<MESSAGING_WEBHOOK_SECRET>",
       "allowed_updates": ["message"]
     }'
```
### Option B: Windows PowerShell
```powershell
curl.exe -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" `
     -H "Content-Type: application/json" `
     -d '{
       "url": "https://<YOUR_RENDER_URL>/api/v1/telegram/webhook",
       "secret_token": "<MESSAGING_WEBHOOK_SECRET>",
       "allowed_updates": ["message"]
     }'
```
*(Replace `<TELEGRAM_BOT_TOKEN>`, `<YOUR_RENDER_URL>`, and `<MESSAGING_WEBHOOK_SECRET>` with your actual values).*
### Expected Success Response:
```json
{
"ok": true,
"result": true,
"description": "Webhook was set"
}
```
---
## ✅ Step 7: Verification & Testing Checklist
1. **Health Probe:**
Visit `https://<YOUR_RENDER_URL>/health` in your browser. Verify you receive:
```json
{"status":"healthy","database":"connected"}
```
2. **Start & Household Currency Setup:**
* Open your bot in Telegram and send `/start`.
* Set your household default currency: `/currency ARS` (or `/currency MXN`, `/currency USD`, `/currency EUR`).
* Verify confirmation: `✅ Default Currency Updated to ARS!`.
3. **Bilingual Natural Language Logging:**
* Send a test text expense in English: `"Dinner with team $45"`.
* Send a test text expense in Spanish: `"Gasté 500 en helado"`.
* Verify instant response confirming the logged transaction with ISO 4217 currency format (`$45.00 USD`, `$500.00 ARS`).
4. **Voice Note Logging:**
* Send a 5-second voice message: `"Coffee 4 dollars"` or `"Café 300 pesos"`.
* Verify Groq Cloud transcribes and logs the transaction in under a second.
5. **Bilingual Financial Queries:**
* Ask in English: `"How much did we spend this month?"`.
* Ask in Spanish: `"¿Cuáles fueron mis gastos de los últimos 15 días?"`.
* Verify Clanomy responds with fluent insights matching the language of your query.
6. **Income Logging & Multi-Currency Segregation:**
* Send a text message: `"Got paid $3,000 salary from Acme Corp"`.
* Verify Clanomy records income and displays segregated cash flow totals per currency without inaccurate conversions.
7. **Family Workspace Collaboration:**
* Send `/family` to view your workspace ledger.
* Send `/invite` to generate an invite link for your partner or household members.
8. **Notion Database Synchronization:**
* Send `/notion` to connect your personal Notion database for real-time two-way mirroring.
---
## 🛡️ Production Best Practices & Troubleshooting
* **Render Free Tier Cold Starts:** Render Free web services spin down after 15 minutes of inactivity. For instant bot responses 24/7, set up a free monitor (e.g. [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org)) to ping `https://<YOUR_RENDER_URL>/health` every 10 minutes.
* **Password Encoding in Alembic:** If your database password contains special characters (`@`, `!`, `*`, `$`), the migration runner in `src/db/session.py` automatically escapes `%` signs to `%%` for Python's `configparser`.
* **Access Whitelisting:** If you want your bot to be completely private to only you and your family, put your Telegram numeric IDs in `ALLOWED_TELEGRAM_USERS` (e.g. `12345678,87654321`). Any unauthorized Telegram user will be rejected.

