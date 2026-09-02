# Complete Manual Testing Guide: Clanomy (Zero to Telegram)

This guide walks you through building, configuring, and testing the **Clanomy** system from complete scratch (zero state) using **Podman** and **Telegram**.

---

## 🏗️ Architecture & Pipeline Overview

```
[ Telegram User ] (Text or Voice)
       │
       ▼  POST /api/v1/telegram/webhook (Header: X-Telegram-Bot-Api-Secret-Token)
 [ Clanomy API ] ── Immediate 200 OK (< 3s)
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

_(Note: You can use either `podman-compose` or `podman compose`.)_

### 1.2 Create your Telegram Bot

1. Open the Telegram app on your phone or desktop.
2. Search for `@BotFather` and click **Start**.
3. Send the command:
   ```text
   /newbot
   ```
4. Follow the prompts:
   - **Name:** e.g., `Clanomy Assistant`
   - **Username:** e.g., `clanomy_test_bot` (must end in `bot`)
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
   POSTGRES_USER=clanomy_user
   POSTGRES_PASSWORD=clanomy_password
   POSTGRES_DB=clanomy_db

   # Security & API Keys
   ENCRYPTION_KEY=YOUR_GENERATED_FERNET_KEY_HERE
   TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_FROM_BOTFATHER

   # App Configuration
   DATABASE_URL=postgresql+psycopg://clanomy_user:clanomy_password@db:5432/clanomy_db
   MESSAGING_WEBHOOK_SECRET=clanomy_super_secret_webhook_token_123

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
   - `clanomy-db` (Port `5433->5432`)
   - `clanomy-app` (Port `8000->8000`)
   - `clanomy-ollama` (Port `11434->11434`)

3. Verify API Health:
   Open your browser and navigate to:
   - **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## Step 4: Download Ollama LLM Model

The Ollama container starts without downloaded weights. Pull `llama3` inside the container:

1. Run:
   ```powershell
   podman exec -it clanomy-ollama ollama pull llama3
   ```
2. Wait for the download to finish (approx. 4.7 GB).
3. Verify the model is available:
   ```powershell
   podman exec -it clanomy-ollama ollama list
   ```

_(Note: Faster-Whisper downloads its `base` model automatically on the first audio request and caches it in the `whisper_model_cache` volume)._

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
   curl.exe -F "url=https://<YOUR_NGROK_URL>/api/v1/telegram/webhook" -F "secret_token=your_messaging_secret_token_here" https://api.telegram.org/botYOUR_TELEGRAM_BOT_TOKEN_HERE/setWebhook
   ```
   _Note: `YOUR_SECRET_TOKEN` must perfectly match the `MESSAGING_WEBHOOK_SECRET` in your `.env` file._

---

## Step 6: Step-by-Step Testing Scenarios

### 🧪 Test 1: User Registration & Onboarding (`/start`)

1. Open Telegram and search for your bot.
2. Click **Start** or send:
   ```text
   /start
   ```
3. **Expected Output:**
   Bot immediately replies with welcome message and onboarding tip:
   > _"👋 Welcome to Clanomy, [Your Name]!_
   > 
   > _💡 Quick Setup:_
   > _Set your household default currency so Clanomy knows what currency to use when you log amounts without a currency (e.g. '500 on dinner' or 'pesos'):_
   > _👉 Reply with `/currency USD`, `/currency ARS`, `/currency MXN`, `/currency EUR`, etc."_

---

### 🧪 Test 2: Household Default Currency Configuration (`/currency`)

1. Check your active currency:
   ```text
   /currency
   ```
   **Expected Output:**
   > _"💵 Household Default Currency: USD_
   > _To update your household default currency, reply with: /currency ARS, /currency MXN, /currency EUR, etc."_

2. Change your default currency to Argentine Pesos (or Mexican Pesos, Euros):
   ```text
   /currency ARS
   ```
   **Expected Output:**
   > _"✅ Default Currency Updated to ARS!_
   > _Any future expenses or income logged without specifying a currency (e.g. 'spent 500 on lunch' or '300 pesos') will now automatically default to ARS."_

---

### 🧪 Test 3: Text Expense Logging (Bilingual English & Spanish)

1. Send an ambiguous expense in Spanish:
   ```text
   Gasté 500 en helado
   ```
2. **Expected Output in Telegram:**
   Bot resolves default currency to ARS and replies:
   > _"Saved 500.00 ARS for 'helado' under category 'Food/Drink'."_

3. Send an explicit foreign currency expense:
   ```text
   Spent $45 on groceries
   ```
4. **Expected Output in Telegram:**
   Bot extracts USD and replies:
   > _"Saved 45.00 USD for 'groceries' under category 'Food/Drink'."_

---

### 🧪 Test 4: Voice Note Expense Logging

1. In Telegram, record and send a voice message:
   > 🎙️ _"I paid twenty four dollars and fifty cents for an Uber ride to the airport."_
2. Check backend logs:
   ```powershell
   podman logs -f clanomy-app
   ```
   You will see:
   ```text
   INFO: [3s Audit] Whisper transcription took 0.84 seconds ...
   INFO: Extraction completed: amount='24.50', concept='Uber ride to the airport', category='Transport'
   INFO: Encrypted transaction saved to database.
   ```
3. **Expected Output in Telegram:**
   Bot replies:
   > _"Saved 24.50 USD for 'Uber ride to the airport' under category 'Transportation'."_

---

### 🧪 Test 5: Dynamic Timeframe & Spanish NLP Queries

1. Send a query in Spanish with dynamic day offset:
   ```text
   ¿Cuáles fueron mis gastos de los últimos 15 días?
   ```
2. **Expected Output in Telegram:**
   Bot responds in fluent Spanish with segregated totals per currency:
   > _"Gastaste 500.00 ARS y 69.50 USD en los últimos 15 días en 2 transacciones."_

---

### 🧪 Test 6: Category-Filtered Queries

1. Send a query specifically targeting a category or alias:
   ```text
   What have I spent on groceries this month?
   ```
2. **Expected Output in Telegram:**
   Bot filters down to the `Food/Drink` category (resolving the "groceries" alias) and replies:
   > _"You've spent 45.50 USD on Food/Drink this month. This was from your transaction at Walmart."_

---

### 🧪 Test 6: Period-Over-Period Comparison Queries

1. Ask the bot to compare spending between periods:
   ```text
   Compare my spending this week to last week
   ```
2. **Expected Output in Telegram:**
   Bot fetches the current week's total and compares it to last week's total, calculating the percentage difference:
   > _"You've spent 69.98 USD across 2 transactions this week. That's 15.30 USD (17.9%) less than last week (85.28 USD)!"_

---

### 🧪 Test 7: Zero-Spending Fallback Response

1. Ask the bot for a timeframe where you have not logged any expenses:
   ```text
   How much did I spend yesterday?
   ```
   _(Assuming no expenses were logged for yesterday)_
2. **Expected Output in Telegram:**
   Bot responds with a warm, encouraging zero-spending message:
   > _"You haven't logged any expenses for yesterday yet! You're sitting pretty at 0.00 USD."_

---

### 🧪 Test 8: Financial Data Export (CSV/JSON)

1. Send a query requesting data export to the bot:
   ```text
   export my data to csv
   ```
2. **Expected Output in Telegram:**
   - The bot replies with a generated document file named `clanomy_export_<uuid>.csv`.
   - The file contains header: `Timestamp (UTC),Amount,Currency,Category,Concept` followed by your decrypted transactions.
   - The file is accompanied by a friendly caption: `📊 Here is your exported transaction history (Total: X transactions).`
3. Try exporting to JSON:
   ```text
   download my JSON data
   ```
4. **Expected Output in Telegram:**
   - The bot replies with a generated document file named `clanomy_export_<uuid>.json`.
   - The file contains valid JSON with metadata (`family_id`, `exported_at`, `total_count`) and a `transactions` list of decrypted records.
5. Check backend logs:
   ```powershell
   podman logs -f clanomy-app
   ```
   You will see the secure cleanup verification logs:
   ```text
   INFO: [3s Audit] Data export took 0.05 seconds (format: csv, count: 12, family_id: ...)
   INFO: Purged temp export file from disk: /tmp/clanomy_export_...
   ```

---

### 🧪 Test 9: Account Deletion & Right to be Forgotten

1. Send a deletion request to the bot:
   ```text
   delete my account
   ```
2. **Expected Output in Telegram:**
   - The bot responds with a prominent warning message:
     > _"⚠️ Are you sure you want to permanently delete your account and all associated financial records? This action is irreversible._
     >
     > _To confirm, please reply with: CONFIRM DELETE"_
3. Send any other text (e.g. `cancel` or `no`):
   - The delete request is cancelled and your account remains untouched.
4. Send the confirmation trigger exactly:
   ```text
   CONFIRM DELETE
   ```
5. **Expected Output in Telegram:**
   - The bot replies with the farewell message:
     > _"✅ Your account and all associated transaction records have been permanently deleted from our database. Thank you for using Clanomy! If you ever wish to return, simply send /start."_
6. Connect to PostgreSQL and query users and transactions:
   ```sql
   SELECT * FROM users WHERE id = '<deleted_user_id>';
   SELECT * FROM transactions WHERE user_id = '<deleted_user_id>';
   ```

   - Verify that **0** records are returned (user, family, and transaction tables are completely purged).
7. Send a message to the bot:
   - The bot treats you as a new user requiring `/start` registration.

---

### 🧪 Test 10: Family Group Creation & Invite Links

1. Send the family creation command to the bot in Telegram:
   ```text
   /createfamily
   ```
2. **Expected Output:**
   - The bot replies:
     > `✅ Family group created successfully!`
     > `Invite your partner/roommates using this link:`
     > `https://t.me/<bot_username>?start=join_<token>`
     > `This link is valid for 1 hour.`
3. Note the generated link containing the secret joining token.

---

### 🧪 Test 11: Multi-Member Family Shared Ledgers & Attribution

1. Open a second Telegram client or simulate a second user starting a conversation with the bot by clicking the invite link: `https://t.me/<bot_username>?start=join_<token>`.
2. **Expected Output:**
   - The bot replies confirming the join:
     > `✅ You have successfully joined the family group!`
   - _(Database Verification)_: Verify that the joining user's previous single-member family record has been cleaned up/purged from the database to avoid orphan records.
3. As the second user, log an expense:
   ```text
   Spent 30 on pizza
   ```
4. As the first user, log an expense:
   ```text
   Spent 15 on coffee
   ```
5. Query the family spending:
   ```text
   /family
   ```
   or ask in natural language:
   ```text
   How much did our family spend this week?
   ```
6. **Expected Output in Telegram:**
   - The bot sums transactions from ALL users belonging to the same family and displays the breakdown:
     > `📊 Family Spending Summary:`
     > `Total spending: 45.00 USD`
     > `• [User 1 Name]: 15.00 USD`
     > `• [User 2 Name]: 30.00 USD`
7. Request a data export as either user:
   ```text
   export my data to csv
   ```
8. Verify in the exported CSV that a `"Logged By"` column exists, showing which family member logged each transaction.

---

### 🧪 Test 12: Notion Workspace Connection (Discovery & Configuration)

1. Prepare your Notion integration:
   - Go to `https://www.notion.so/my-integrations` and create an **Internal Integration**.
   - Copy the **Internal Integration Secret**.
   - Open a target database in Notion, click `•••` (top right) -> `Add connections`, and add your integration.
2. Send the setup command to the bot:
   ```text
   /notion
   ```
3. **Expected Output:**
   - The bot replies with step-by-step setup guidance.
4. Connect the workspace:
   ```text
   /notion connect <your_integration_secret>
   ```
5. **Expected Output:**
   - The bot validates the token, queries the Notion API, and displays a numbered list of available databases:
     > `📋 Found X Notion Database(s):`
     > `1. 📊 Family Expenses (ID: abc...)`
     > `2. 💰 Personal Ledgers (ID: def...)`
     > `Reply with: /notion setdb <number or ID>`
6. Select your target database:
   ```text
   /notion setdb 1
   ```
7. **Expected Output:**
   - The bot binds the database to the family and replies:
     > `✅ Notion workspace connected!`
     > `📁 Target Database: Family Expenses`
     > `Your transactions are now ready to be mirrored!`
8. Send status query:
   ```text
   /notion status
   ```
9. **Expected Output:**
   - The bot replies with current connection status:
     > `📊 Notion Connection Status: Connected ✅`
     > `📁 Target Database: Family Expenses`
     > `Connected: [Timestamp]`
10. Verify disconnection:
    - Send: `/notion disconnect`
    - Bot replies: `🔌 Notion disconnected successfully.`

---

### 🧪 Test 13: Notion Real-Time Mirroring & Adaptive Mapping

1. Connect the Notion database again using `/notion connect` and `/notion setdb`.
2. Run a diagnostic test to verify the write connection:
   ```text
   /notion test
   ```
3. **Expected Output:**
   - The bot replies:
     > `✅ Notion Mirror Test Successful!`
     > `Created test record in database: Family Expenses`
     > `🔗 View in Notion (clickable link)`
   - Open the link in a browser and verify a test row with `Clanomy Test Entry` was created under the `Test` category with `0.00` amount.
4. Send a real transaction message:
   ```text
   Spent 55 USD for dinner at Olive Garden under Food
   ```
5. **Expected Output:**
   - The bot responds instantly (< 3s) confirming the local save.
   - Mirroring is triggered asynchronously in the background.
6. Open the Notion database and verify the row was created:
   - Check the adaptive mapping columns. The system dynamically maps:
     - **Title** (Concept/Name/Title/Expense) -> `dinner at Olive Garden`
     - **Amount** (Amount/Cost/Price/Value) -> `55.00`
     - **Currency** (Currency) -> `USD`
     - **Category** (Category/Tag/Tags) -> `Food`
     - **Member** (Member/User/Logged By) -> `[Your Telegram display name]`
     - **Date** (Date/Timestamp) -> `[Current Date]`

---

### 🧪 Test 14: Notion Resilience (Retry & Catch-Up Sync)

1. **Test Transient Retry:**
   - Block network access or mock a transient Notion API failure (such as rate limits or server errors).
   - Log a new transaction:
     ```text
     Spent 12.00 for Netflix
     ```
   - Verify Telegram reply is still sent instantly.
   - Check backend container logs:
     ```powershell
     podman logs clanomy-app
     ```
     Verify that `[Notion Mirror] [Retry]` warnings are printed, attempting retries with exponential wait times.
   - Restore connection. The system eventually completes mirroring successfully, updating `notion_page_id` in the local database.
2. **Test Catch-Up Sync:**
   - Simulate a prolonged Notion outage (e.g. disconnect token).
   - Log a couple of new transactions:
     ```text
     10 for apps
     15 for games
     ```
   - Verify in the database that these transactions are persisted locally but have `notion_page_id = NULL`:
     ```sql
     SELECT id, concept, notion_page_id FROM transactions WHERE notion_page_id IS NULL;
     ```
   - Restore connection.
   - Send:
     ```text
     /notion sync
     ```
   - **Expected Output:**
     The bot performs a catch-up sync, updating local transactions and mirroring them to Notion:
     > `✅ Notion Sync Complete!`
     > `Successfully synchronized 2 pending transaction(s) to Family Expenses.`

---

### 🧪 Test 15: Granting Lifetime Pro (VIP Access)

1. Verify the 30-transaction limit for free users:
   - Exhaust the limit (or artificially increase `monthly_tx_count` to 30 via DB).
   - Attempt to log a new transaction.
   - **Expected Output:** The bot replies with a warning and upgrade prompt (`/upgrade`).
2. Run the administrative script to grant `lifetime_pro`:
   - Obtain your Telegram ID (which you can query from the database or BotFather logs).
   - Execute the script inside the container (or your local venv):
     ```bash
     podman compose exec app python scripts/grant_lifetime_pro.py --telegram-id <YOUR_TELEGRAM_ID>
     ```
3. **Expected Output:**
   - The script outputs:
     > `Success! Family has been upgraded to lifetime_pro.`
4. Verify the upgrade:
   - Log another transaction in Telegram.
   - **Expected Output:** The transaction is accepted instantly, bypassing the quota.
5. Verify DB state (Optional):
   - Connect to PostgreSQL (`podman exec -it clanomy-db psql -U clanomy_user -d clanomy_db`).
   - Run: `SELECT plan_type, subscription_status FROM family;`
   - Should yield `lifetime_pro` and `active`.

---

## Step 7: Database & Encryption Verification

Verify that data was stored and encrypted using AES-256:

1. Connect to PostgreSQL inside the Podman container:

   ```powershell
   podman exec -it clanomy-db psql -U clanomy_user -d clanomy_db
   ```

2. Query users:

   ```sql
   SELECT id, telegram_id, username, first_name FROM users;
   ```

3. Query transactions:

   ```sql
   SELECT id, user_id, amount, concept, category, timestamp FROM transactions ORDER BY timestamp DESC LIMIT 5;
   ```

   _Notice that `amount` and `concept` columns contain secure Fernet ciphertext tokens (e.g. `gAAAAAB...`), ensuring zero plaintext leaks at rest._

4. Exit psql:
   ```sql
   \q
   ```

---

## 🛠️ Troubleshooting & Handy Podman Commands

| Goal                       | Command                                                                          |
| -------------------------- | -------------------------------------------------------------------------------- |
| View App Logs              | `podman logs -f clanomy-app`                                                      |
| View Ollama Logs           | `podman logs -f clanomy-ollama`                                                   |
| Restart App Service        | `podman restart clanomy-app`                                                      |
| Tear down containers       | `podman-compose down`                                                            |
| Rebuild all containers     | `podman-compose up -d --build`                                                   |
| Test Ollama Model manually | `podman exec -it clanomy-ollama ollama run llama3 "Extract amount: 20 for pizza"` |
