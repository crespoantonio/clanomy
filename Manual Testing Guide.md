# Complete Manual Testing Guide: FamFin-AI (Zero to Telegram)

This guide walks you through building, configuring, and testing the **FamFin-AI** system from complete scratch (zero state) using **Podman** and **Telegram**.

---

## 🏗️ Architecture & Pipeline Overview

```
[ Telegram User ] (Text or Voice)
       │
       ▼  POST /api/v1/telegram/webhook (Header: X-Telegram-Bot-Api-Secret-Token)
 [ FamFin API ] ── Immediate 200 OK (< 3s)
       │
       ├─► (Background Task)
       │      │
       │      ├─► [ Faster-Whisper ] (Audio to text transcription)
       │      ├─► [ Ollama - Llama3 ] (JSON extraction: Amount, Concept, Category)
       │      └─► [ PostgreSQL ] (AES-256 encrypted storage)
       │
       ▼  httpx.post("https://api.telegram.org/bot<TOKEN>/sendMessage")
[ Telegram User ] ("Saved 12.50 USD for 'Lunch' under category 'Food'")
```

---

## Step 1: Prerequisites & Telegram Bot Creation

If you have **nothing set up**, follow these initial steps:

### 1.1 Ensure Podman is Running
On Windows, make sure your Podman machine is running:
```powershell
podman machine start
```
Verify Podman is accessible:
```powershell
podman version
podman-compose --version
```
*(Note: You can use either `podman-compose` or `podman compose`.)*

### 1.2 Create your Telegram Bot
1. Open the Telegram app on your phone or desktop.
2. Search for `@BotFather` and click **Start**.
3. Send the command:
   ```text
   /newbot
   ```
4. Follow the prompts:
   - **Name:** e.g., `My FamFin Assistant`
   - **Username:** e.g., `my_famfin_test_bot` (must end in `bot`)
5. BotFather will provide your **Telegram Bot Token** (e.g., `7123456789:AAF_xxxxxxx_xxxxxxx`).
6. **Save this token** — you will use it in `.env`.

---

## Step 2: Environment Configuration (`.env`)

1. In the project root, copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Generate an AES-256 Fernet encryption key:
   - **Option A (Python script in repo):**
     ```powershell
     python scripts/generate_key.py
     ```
   - **Option B (PowerShell / One-liner):**
     ```powershell
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```

3. Open `.env` and fill in the values:
   ```env
   # Database Configuration
   POSTGRES_USER=famfin_user
   POSTGRES_PASSWORD=famfin_password
   POSTGRES_DB=famfin_db

   # Security & API Keys
   ENCRYPTION_KEY=YOUR_GENERATED_FERNET_KEY_HERE
   TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_FROM_BOTFATHER

   # App Configuration
   DATABASE_URL=postgresql+psycopg://famfin_user:famfin_password@db:5432/famfin_db
   MESSAGING_WEBHOOK_SECRET=famfin_super_secret_webhook_token_123

   # Whisper Settings
   WHISPER_MODEL_SIZE=base
   WHISPER_DEVICE=cpu
   WHISPER_COMPUTE_TYPE=int8

   # Ollama Settings
   OLLAMA_BASE_URL=http://ollama:11434
   OLLAMA_MODEL=llama3
   ```

---

## Step 3: Build & Start Containers with Podman

1. Build and start the services (`db`, `app`, `ollama`):
   ```powershell
   podman-compose up -d --build
   ```

2. Verify all containers are running and healthy:
   ```powershell
   podman ps
   ```
   You should see:
   - `famfin-db` (Port `5433->5432`)
   - `famfin-app` (Port `8000->8000`)
   - `famfin-ollama` (Port `11434->11434`)

3. Verify API Health:
   Open your browser and navigate to:
   - **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## Step 4: Download Ollama LLM Model

The Ollama container starts without downloaded weights. Pull `llama3` inside the container:

1. Run:
   ```powershell
   podman exec -it famfin-ollama ollama pull llama3
   ```
2. Wait for the download to finish (approx. 4.7 GB).
3. Verify the model is available:
   ```powershell
   podman exec -it famfin-ollama ollama list
   ```

*(Note: Faster-Whisper downloads its `base` model automatically on the first audio request and caches it in the `whisper_model_cache` volume).*

---

## Step 5: Telegram Webhook Setup (via ngrok)

For Telegram to send messages to your local FastAPI backend, you must expose port `8000` to the internet.

1. **Start ngrok:**
   ```powershell
   ngrok http 8000
   ```
2. Copy the `https` forwarding URL provided by ngrok (e.g., `https://abcdef1234.ngrok-free.app`).

3. **Register the Webhook with Telegram:**
   Run the following `curl` command to link Telegram to your ngrok URL. Make sure to replace `<YOUR_BOT_TOKEN>`, `<YOUR_NGROK_URL>`, and `<YOUR_SECRET_TOKEN>`:
   ```powershell
   curl.exe -F "url=https://<YOUR_NGROK_URL>/api/v1/telegram/webhook" -F "secret_token=<YOUR_SECRET_TOKEN>" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```
   *Note: `YOUR_SECRET_TOKEN` must perfectly match the `MESSAGING_WEBHOOK_SECRET` in your `.env` file.*

---

## Step 6: Step-by-Step Testing Scenarios

### 🧪 Test 1: Start Command
1. Open your bot on Telegram.
2. Click **Start** or send:
   ```text
   /start
   ```
3. **Expected Output:**
   Bot immediately replies:
   > *"Welcome to FamFin-AI, [Your Name]! Your account is ready. You can now log your first expense by simply typing it, for example: '50 for lunch' or '100 for groceries'."*

---

### 🧪 Test 2: Text Expense Logging
1. Send a text message in Telegram:
   ```text
   Spent 45.50 on groceries at Walmart
   ```
2. Check backend logs in your terminal:
   ```powershell
   podman logs -f famfin-app
   ```
   You will see:
   ```text
   INFO: ExtractionService: Parsing financial intent...
   INFO: [3s Audit] Total pipeline orchestration took 1.12 seconds
   ```
3. **Expected Output in Telegram:**
   Bot replies:
   > *"Saved 45.50 USD for 'groceries at Walmart' under category 'Food & Groceries'."*

---

### 🧪 Test 3: Voice Note Expense Logging
1. In Telegram, record and send a voice message:
   > 🎙️ *"I paid twenty four dollars and fifty cents for an Uber ride to the airport."*
2. Check backend logs:
   ```powershell
   podman logs -f famfin-app
   ```
   You will see:
   ```text
   INFO: [3s Audit] Whisper transcription took 0.84 seconds ...
   INFO: Extraction completed: amount='24.50', concept='Uber ride to the airport', category='Transport'
   INFO: Encrypted transaction saved to database.
   ```
3. **Expected Output in Telegram:**
   Bot replies:
   > *"Saved 24.50 USD for 'Uber ride to the airport' under category 'Transportation'."*

---

### 🧪 Test 4: Time-Based Aggregation Queries
1. Send a text message to your bot asking about your spending:
   ```text
   How much did I spend this week?
   ```
2. Check backend logs:
   ```powershell
   podman logs -f famfin-app
   ```
   You will see the `[3s Audit]` logs for the query:
   ```text
   INFO: [3s Audit] Aggregation query took 0.02 seconds (timeframe: this_week, family_id: ...)
   INFO: [3s Audit] Conversational summary generation took 1.24 seconds (llm_used: True)
   ```
3. **Expected Output in Telegram:**
   Bot replies with a friendly conversational summary:
   > *"Hi [Name]! You've spent 69.98 USD across 2 transactions this week. Your top spending category was groceries at Walmart!"*

---

### 🧪 Test 5: Category-Filtered Queries
1. Send a query specifically targeting a category or alias:
   ```text
   What have I spent on groceries this month?
   ```
2. **Expected Output in Telegram:**
   Bot filters down to the `Food/Drink` category (resolving the "groceries" alias) and replies:
   > *"You've spent 45.50 USD on Food/Drink this month. This was from your transaction at Walmart."*

---

### 🧪 Test 6: Period-Over-Period Comparison Queries
1. Ask the bot to compare spending between periods:
   ```text
   Compare my spending this week to last week
   ```
2. **Expected Output in Telegram:**
   Bot fetches the current week's total and compares it to last week's total, calculating the percentage difference:
   > *"You've spent 69.98 USD across 2 transactions this week. That's 15.30 USD (17.9%) less than last week (85.28 USD)!"*

---

### 🧪 Test 7: Zero-Spending Fallback Response
1. Ask the bot for a timeframe where you have not logged any expenses:
   ```text
   How much did I spend yesterday?
   ```
   *(Assuming no expenses were logged for yesterday)*
2. **Expected Output in Telegram:**
   Bot responds with a warm, encouraging zero-spending message:
   > *"You haven't logged any expenses for yesterday yet! You're sitting pretty at 0.00 USD."*

---

## Step 7: Database & Encryption Verification

Verify that data was stored and encrypted using AES-256:

1. Connect to PostgreSQL inside the Podman container:
   ```powershell
   podman exec -it famfin-db psql -U famfin_user -d famfin_db
   ```

2. Query users:
   ```sql
   SELECT id, telegram_id, username, first_name FROM users;
   ```

3. Query transactions:
   ```sql
   SELECT id, user_id, amount, concept, category, timestamp FROM transactions ORDER BY timestamp DESC LIMIT 5;
   ```
   *Notice that `amount` and `concept` columns contain secure Fernet ciphertext tokens (e.g. `gAAAAAB...`), ensuring zero plaintext leaks at rest.*

4. Exit psql:
   ```sql
   \q
   ```

---

## 🛠️ Troubleshooting & Handy Podman Commands

| Goal | Command |
|---|---|
| View App Logs | `podman logs -f famfin-app` |
| View Ollama Logs | `podman logs -f famfin-ollama` |
| Restart App Service | `podman restart famfin-app` |
| Tear down containers | `podman-compose down` |
| Rebuild all containers | `podman-compose up -d --build` |
| Test Ollama Model manually | `podman exec -it famfin-ollama ollama run llama3 "Extract amount: 20 for pizza"` |
