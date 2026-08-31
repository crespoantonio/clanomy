# Deployment Guide: Clanomy (Render + Supabase + Groq + Telegram Stars)

This guide provides step-by-step instructions to deploy **Clanomy** to the cloud on an **Always-Free ($0.00/month)** architecture with native **Telegram Stars In-App Subscriptions & AI Logging**. It is designed to be beginner-friendly, rigorous, and production-ready.

---

## 🏗️ The Architecture (How It Works)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                CLANOMY CLOUD ARCHITECTURE                               │
│                                                                                         │
│  [ Telegram User / Client ] ──► (Voice Notes / Text / In-App Stars Payments)            │
│                 │                                                                       │
│                 ▼ (HTTPS Webhook + X-Telegram-Bot-Api-Secret-Token)                     │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                            RENDER WEB SERVICE (Compute)                           │  │
│  │  • FastAPI Application (Python 3.12 / Uvicorn on Port $PORT)                      │  │
│  │  • Automatic Alembic Database Migrations on Lifespan Startup                      │  │
│  │  • Quota Gating Engine (ENABLE_SUBSCRIPTIONS=true)                                │  │
│  │  • Pre-Checkout Query & Successful Payment Handlers                               │  │
│  └───────────────────┬─────────────────────────────────────────────┬─────────────────┘  │
│                      │ (Encrypted Ledger & Quotas)                 │ (AI Extraction)    │
│                      ▼                                             ▼                    │
│  ┌────────────────────────────────────────┐     ┌────────────────────────────────────┐  │
│  │       SUPABASE (PostgreSQL)            │     │       GROQ CLOUD (AI Engine)       │  │
│  │  • AES-256 Zero-Knowledge Encrypted DB │     │  • Whisper-Large-v3 Voice (150ms)  │  │
│  │  • IPv4 PgBouncer Connection Pooler    │     │  • Llama-3.3-70b Extraction (200ms)│  │
│  │  • Auto-Managed Tables & Subscriptions │     │  • Zero Container RAM Footprint    │  │
│  └────────────────────────────────────────┘     └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Telegram:** Chat client where users log transactions and purchase Pro subscriptions via Apple Pay / Google Pay / Telegram Stars (`XTR`).
* **Render:** Cloud hosting platform running the FastAPI application and webhook listener.
* **Supabase:** Managed PostgreSQL database storing AES-256 encrypted financial transactions, families, and subscription quotas.
* **Groq:** Ultra-fast cloud AI inference engine executing Whisper voice transcription and Llama data extraction in <350ms with 0MB RAM burden on Render.

---

## 🛠️ Step 1: Create Telegram Bot & Enable Stars Payments (BotFather)

1. Open Telegram and search for `@BotFather` (official bot with the blue checkmark).
2. **Create Bot:**
   * Send `/newbot`.
   * Provide a display name (e.g. `Clanomy AI`).
   * Provide a username ending in `bot` (e.g. `ClanomyFinanceBot`).
   * Copy the HTTP API token (e.g. `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`). Save it as `TELEGRAM_BOT_TOKEN`.
3. **Enable Telegram Stars Payments:**
   * Send `/mybots` to `@BotFather`.
   * Select your bot ➔ **Bot Settings** ➔ **Payments**.
   * Select **Telegram Stars** (available with 0 registration fees).
   * Enable Test Mode if testing in Sandbox, or Live Mode for production billing.
4. **Register Bot Commands:**
   * Send `/setcommands` to `@BotFather`, select your bot, and paste:
     ```text
     start - Start Clanomy and view workspace status
     upgrade - View Pro subscription tiers and upgrade with Telegram Stars
     family - Manage family members and shared ledger
     invite - Generate invite link for household members
     notion - Connect and mirror transactions to Notion
     export - Export financial logs to CSV or JSON
     help - View available commands and AI logging tips
     ```

---

## 💾 Step 2: Set Up Database & Connection Pooler (Supabase)

1. Go to [https://supabase.com](https://supabase.com) and click **Start your project** (sign in with GitHub).
2. Click **New Project**, choose your organization, and name your project (e.g. `clanomy-db`).
3. **Set Database Password:** Choose a strong password and save it in your notepad.
4. **Choose Region:** Pick the region closest to your users (e.g. `US East (N. Virginia)` / `us-east-1` or `South America (São Paulo)` / `sa-east-1`).
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

## 🧠 Step 3: Get AI Brain API Key (Groq)

Groq provides sub-second LLM and Whisper transcription inference for free:

1. Go to [https://console.groq.com](https://console.groq.com) and log in.
2. On the left sidebar, click **API Keys**.
3. Click **Create API Key**, name it (e.g. `clanomy-prod`), and copy the key (starts with `gsk_`).
4. Save this key as `GROQ_API_KEY`.

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
   * **Instance Type:** `Free` (or `Starter`).
6. **Environment Variables Configuration:**
   Expand the **Environment Variables** section and add:

| Variable Key | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.8` | Pins stable Python runtime for C-extensions |
| `DATABASE_URL` | `postgresql+psycopg://postgres.[ref]:[escaped_pwd]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | Supabase IPv4 Pooler connection URI |
| `ENCRYPTION_KEY` | *(Your 32-byte Fernet key from Step 4)* | AES-256 Zero-Knowledge DB encryption |
| `TELEGRAM_BOT_TOKEN` | *(Your BotFather HTTP API token from Step 1)* | Telegram Bot API authentication |
| `MESSAGING_WEBHOOK_SECRET` | *(Your 32-character secret from Step 4)* | Validates `X-Telegram-Bot-Api-Secret-Token` |
| `ENABLE_SUBSCRIPTIONS` | `true` | Enables quotas, tiers, and Telegram Stars billing |
| `GROQ_API_KEY` | `gsk_...` *(From Step 3)* | Fast cloud AI extraction & voice notes |
| `DEFAULT_CURRENCY` | `USD` | Base default currency (e.g. `USD`, `EUR`, `BRL`) |
| `ALLOWED_TELEGRAM_USERS` | `""` | Empty string allows public commercial signups |
| `ENABLE_DOCS` | `false` | Disables `/docs` and `/openapi.json` from public crawlers |

7. Click **Deploy Web Service**.
8. Render will build and deploy your service. On startup, Clanomy automatically runs `alembic upgrade head`, creating all required tables (`families`, `users`, `transactions`, `subscriptions`) in Supabase.
9. When the status turns green (**Live**), copy your service URL (e.g. `https://clanomy-api.onrender.com`).

---

## 🔗 Step 6: Register Webhook with Telegram

Register your live Render URL and secret token with Telegram's servers:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://<YOUR_RENDER_URL>/api/v1/telegram/webhook",
       "secret_token": "<MESSAGING_WEBHOOK_SECRET>",
       "allowed_updates": ["message", "pre_checkout_query"]
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
2. **Start & Ledger Logging:**
   * Open your bot in Telegram and send `/start`.
   * Send a test text expense: `"Dinner with team $45"`.
   * Verify instant response confirming the logged transaction with category `Food/Drink`.
3. **Voice Note Logging:**
   * Send a 5-second voice message: `"Coffee 4 dollars"`.
   * Verify Groq transcribes and logs the transaction.
4. **Subscription Quotas & Upgrade Invoice Flow:**
   * Send `/upgrade` to the bot.
   * Verify the bot issues 1-tap invoices for **Solo Pro (150 Stars)** and **Family Pro (300 Stars)**.
   * In sandbox/live mode, tap Pay to complete checkout. Verify instant confirmation and account tier upgrade.
5. **Admin VIP Override (Optional):**
   To grant lifetime VIP status to your own user account without charging Stars, run from Render Shell or locally:
   ```bash
   python scripts/grant_lifetime_pro.py --telegram-id <YOUR_TELEGRAM_NUMERIC_ID>
   ```

---

## 🛡️ Production Best Practices & Troubleshooting

* **Render Free Tier Cold Starts:** Render Free web services spin down after 15 minutes of inactivity. For 100% instant responses and 0-delay `pre_checkout_query` validation, set up an external free monitor (e.g. [UptimeRobot](https://uptimerobot.com)) to ping `https://<YOUR_RENDER_URL>/health` every 10 minutes, or upgrade to Render Starter ($7/mo).
* **Password Encoding in Alembic:** If your database password contains special characters (`@`, `!`, `*`, `$`), the migration runner in `src/db/session.py` automatically escapes `%` signs to `%%` for Python's `configparser`.
* **Zero Card Storage (PCI-DSS):** Clanomy never sees or stores card numbers; payments are settled natively through Apple Pay / Google Pay / Telegram Stars and verified cryptographically via `pre_checkout_query` webhooks.
