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
56: 3. **Register Bot Commands:**
57:    * Send `/setcommands` to `@BotFather`, select your bot, and paste:
58:      ```text
59:      start - Start Clanomy and view workspace status
60:      currency - View or update household default currency (e.g. /currency ARS)
61:      family - Manage family members and shared ledger
62:      invite - Generate invite link for household members
63:      notion - Connect and mirror transactions to Notion
64:      export - Export financial logs to CSV or JSON
65:      help - View available commands and AI logging tips
66:      ```
67: 
68: ---
69: 
70: ## 💾 Step 2: Set Up Database (Supabase)
71: 
72: 1. Go to [https://supabase.com](https://supabase.com) and click **Start your project** (sign in with GitHub).
73: 2. Click **New Project**, choose your organization, and name your project (e.g. `clanomy-db`).
74: 3. **Set Database Password:** Choose a strong password and save it securely.
75: 4. **Choose Region:** Pick the region closest to you (e.g. `US East (N. Virginia)` / `us-east-1` or `South America (São Paulo)` / `sa-east-1`).
76: 5. Click **Create new project**.
77: 6. **Obtain the Connection Pooler URI (IPv4 Safe):**
78:    * In the Supabase left sidebar, click **⚙️ Project Settings** ➔ **Database**.
79:    * Scroll down to **Connection string** ➔ select **URI** tab ➔ select **Pooler** (Session or Transaction mode).
80:    * Copy the URI template:
81:      ```text
82:      postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
83:      ```
84: 7. **Format URI for Clanomy (Psycopg3 Driver & URL Escaping):**
85:    * Change the prefix from `postgresql://` to `postgresql+psycopg://`.
86:    * **URL-Encode special characters in your password** (e.g. replace `@` with `%40`, `!` with `%21`, `*` with `%2A`, `$` with `%24`).
87:    * Append `?sslmode=require` to the end.
88:    * **Final `DATABASE_URL` Example:**
89:      ```text
90:      postgresql+psycopg://postgres.hwdzwrvvekaogtqtvmia:9%40ka%21FfAA778Uo8%21Wd%2A%24@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
91:      ```
92: 
93: > [!NOTE]
94: > Supabase direct hostnames (`db.<ref>.supabase.co`) only resolve over IPv6. Using the **Connection Pooler URL** (`aws-0-[region].pooler.supabase.com:6543`) ensures full IPv4 compatibility with Render.
95: 
96: ---
97: 
98: ## 🧠 Step 3: Get AI API Key (Groq / OpenAI Cloud)
99: 
100: Groq provides sub-second LLM and Whisper transcription inference for free:
101: 
102: 1. Go to [https://console.groq.com](https://console.groq.com) and log in.
103: 2. On the left sidebar, click **API Keys**.
104: 3. Click **Create API Key**, name it (e.g. `clanomy-selfhosted`), and copy the key (starts with `gsk_`).
105: 4. Save this key as `AI_API_KEY`.
106: 
107: ---
108: 
109: ## 🔐 Step 4: Generate Security Secrets
110: 
111: Generate cryptographic keys locally to protect your zero-knowledge encrypted database and webhook endpoint:
112: 
113: 1. **`ENCRYPTION_KEY` (AES-256 Fernet Key):**
114:    Run in your terminal:
115:    ```bash
116:    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
117:    ```
118:    *Save the 32-byte URL-safe base64 string.*
119: 
120: 2. **`MESSAGING_WEBHOOK_SECRET` (Webhook Authenticity Token):**
121:    Run in your terminal:
122:    ```bash
123:    python -c "import secrets; print(secrets.token_hex(32))"
124:    ```
125:    *Save this 32-byte hex string.*
126: 
127: ---
128: 
129: ## 🚀 Step 5: Deploy Web Service (Render)
130: 
131: 1. Ensure your latest Clanomy code is pushed to your GitHub repository:
132:    ```bash
133:    git add .
134:    git commit -m "feat: configure cloud deployment"
135:    git push origin master
136:    ```
137: 2. Log into [https://dashboard.render.com](https://dashboard.render.com).
138: 3. Click **New +** ➔ **Web Service**.
139: 4. Connect your GitHub repository (`clanomy`).
140: 5. Configure the Web Service settings:
141:    * **Name:** `clanomy-api` (or `clanomy-bot`)
142:    * **Region:** Same region as your Supabase database (e.g. `Virginia (US East)`).
143:    * **Branch:** `master` (or `main`).
144:    * **Runtime:** `Python 3`.
145:    * **Build Command:** `pip install -r requirements.txt`
146:    * **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
147:    * **Instance Type:** `Free`.
148: 6. **Environment Variables Configuration:**
149:    Expand the **Environment Variables** section and add:
150: 
151: | Variable Key | Recommended Self-Hosted Value | Description |
152: | :--- | :--- | :--- |
153: | `PYTHON_VERSION` | `3.12.8` | Pins stable Python runtime for C-extensions |
154: | `PYTHONUNBUFFERED` | `1` | Real-time live log streaming in Render console |
155: | `DATABASE_URL` | `postgresql+psycopg://postgres.[ref]:[escaped_pwd]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | Supabase IPv4 Pooler connection URI |
156: | `ENCRYPTION_KEY` | *(Your 32-byte Fernet key from Step 4)* | AES-256 Zero-Knowledge DB encryption |
157: | `TELEGRAM_BOT_TOKEN` | *(Your BotFather HTTP API token from Step 1)* | Telegram Bot API authentication |
158: | `MESSAGING_WEBHOOK_SECRET` | *(Your 32-character secret from Step 4)* | Validates `X-Telegram-Bot-Api-Secret-Token` |
159: | `ENABLE_SUBSCRIPTIONS` | `false` | Disables paywalls and unlocks all features for free |
160: | `AI_API_KEY` | `gsk_...` *(From Step 3)* | Fast cloud AI extraction, queries & voice notes |
161: | `DEFAULT_CURRENCY` | `USD` | Base fallback currency (e.g. `USD`, `ARS`, `EUR`, `MXN`) |
162: | `ALLOWED_TELEGRAM_USERS` | `""` *(or comma-separated IDs)* | Restrict bot access to your Telegram ID(s) |
163: | `ENABLE_DOCS` | `false` | Disables public `/docs` swagger page |
164: 
165: 7. Click **Deploy Web Service**.
166: 8. Render will build and deploy your service. On startup, Clanomy automatically runs `alembic upgrade head`, creating all required tables (`family`, `user`, `transaction`, `familyinvite`) in Supabase.
167: 9. When the status turns green (**Live**), copy your service URL (e.g. `https://clanomy-api.onrender.com`).
168: 
169: ---
170: 
171: ## 🔗 Step 6: Register Webhook with Telegram
172: 
173: Register your live Render URL and secret token with Telegram:
174: 
175: ### Option A: Bash / Linux / macOS
176: ```bash
177: curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
178:      -H "Content-Type: application/json" \
179:      -d '{
180:        "url": "https://<YOUR_RENDER_URL>/api/v1/telegram/webhook",
181:        "secret_token": "<MESSAGING_WEBHOOK_SECRET>",
182:        "allowed_updates": ["message", "pre_checkout_query"]
183:      }'
184: ```
185: 
186: ### Option B: Windows PowerShell
187: ```powershell
188: curl.exe -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" `
189:   -H "Content-Type: application/json" `
190:   -d '{
191:     "url": "https://<YOUR_RENDER_URL>/api/v1/telegram/webhook",
192:     "secret_token": "<MESSAGING_WEBHOOK_SECRET>",
193:     "allowed_updates": ["message", "pre_checkout_query"]
194:   }'
195: ```
196: 
197: *(Replace `<TELEGRAM_BOT_TOKEN>`, `<YOUR_RENDER_URL>`, and `<MESSAGING_WEBHOOK_SECRET>` with your actual values).*
198: 
199: ### Expected Success Response:
200: ```json
201: {
202:   "ok": true,
203:   "result": true,
204:   "description": "Webhook was set"
205: }
206: ```
207: 
208: ---
209: 
210: ## ✅ Step 7: Verification & Testing Checklist
211: 
212: 1. **Health Probe:**
213:    Visit `https://<YOUR_RENDER_URL>/health` in your browser. Verify you receive:
214:    ```json
215:    {"status":"healthy","database":"connected"}
216:    ```
217: 2. **Start & Household Currency Setup:**
218:    * Open your bot in Telegram and send `/start`.
219:    * Set your household default currency: `/currency ARS` (or `/currency MXN`, `/currency USD`, `/currency EUR`).
220:    * Verify confirmation: `✅ Default Currency Updated to ARS!`.
221: 3. **Bilingual Natural Language Logging:**
222:    * Send a test text expense in English: `"Dinner with team $45"`.
223:    * Send a test text expense in Spanish: `"Gasté 500 en helado"`.
224:    * Verify instant response confirming the logged transaction with ISO 4217 currency format (`$45.00 USD`, `$500.00 ARS`).
225: 4. **Voice Note Logging:**
226:    * Send a 5-second voice message: `"Coffee 4 dollars"` or `"Café 300 pesos"`.
227:    * Verify Groq Cloud transcribes and logs the transaction in under a second.
228: 5. **Bilingual Financial Queries:**
229:    * Ask in English: `"How much did we spend this month?"`.
230:    * Ask in Spanish: `"¿Cuáles fueron mis gastos de los últimos 15 días?"`.
231:    * Verify Clanomy responds with fluent insights matching the language of your query.
232: 6. **Income Logging & Multi-Currency Segregation:**
233:    * Send a text message: `"Got paid $3,000 salary from Acme Corp"`.
234:    * Verify Clanomy records income and displays segregated cash flow totals per currency without inaccurate conversions.
235: 7. **Family Workspace Collaboration:**
236:    * Send `/family` to view your workspace ledger.
237:    * Send `/invite` to generate an invite link for your partner or household members.
238: 8. **Notion Database Synchronization:**
239:    * Send `/notion` to connect your personal Notion database for real-time two-way mirroring.
240: 
241: ---
242: 
243: ## 🛡️ Production Best Practices & Troubleshooting
244: 
245: * **Render Free Tier Cold Starts:** Render Free web services spin down after 15 minutes of inactivity. For instant bot responses 24/7, set up a free monitor (e.g. [UptimeRobot](https://uptimerobot.com) or [Cron-Job.org](https://cron-job.org)) to ping `https://<YOUR_RENDER_URL>/health` every 10 minutes.
246: * **Password Encoding in Alembic:** If your database password contains special characters (`@`, `!`, `*`, `$`), the migration runner in `src/db/session.py` automatically escapes `%` signs to `%%` for Python's `configparser`.
247: * **Access Whitelisting:** If you want your bot to be completely private to only you and your family, put your Telegram numeric IDs in `ALLOWED_TELEGRAM_USERS` (e.g. `12345678,87654321`). Any unauthorized Telegram user will be rejected.

