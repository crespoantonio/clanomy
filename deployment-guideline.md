# Deployment Guide: FamFin-AI (Cloud-Native & Always-Free)

This guide provides step-by-step instructions to deploy **FamFin-AI** to the cloud on an **Always-Free ($0.00/month)** architecture. It is designed for beginners. If you follow these instructions exactly, you will have a fully functioning AI financial bot capable of supporting 500+ users for free.

## 🏗️ The Architecture (How it works)
* **Telegram:** The chat app where users interact with the bot.
* **Render:** The cloud provider that runs our application code 24/7.
* **Supabase:** The database that stores the encrypted financial records.
* **Groq:** The AI "brain" that transcribes voice notes and extracts data.

---

## 🛠️ Step 1: Create the Telegram Bot (BotFather)
First, we need to create the actual bot account on Telegram to get your secret token.

1. Open the Telegram app on your phone or computer.
2. Search for `@BotFather` (look for the one with the official blue checkmark).
3. Send the message `/newbot`.
4. BotFather will ask for a name. Send a display name (e.g., `FamFin AI`).
5. BotFather will ask for a username. It must end in "bot" (e.g., `FamFinTrackerBot`).
6. BotFather will reply with a long string of text called the **HTTP API Token** (it looks something like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`). 
7. **Copy this Token and save it in a notepad.** We will need it later. It will be called `TELEGRAM_BOT_TOKEN`.

---

## 💾 Step 2: Set Up the Database (Supabase)
We need a place to securely store your data. Supabase gives you a generous free database.

1. Go to [https://supabase.com](https://supabase.com) and click **Start your project** (sign in with GitHub).
2. Click **New Project** and choose a default organization.
3. Give your project a name (e.g., `famfin-db`).
4. **Create a strong Database Password and save it in your notepad.** You cannot recover this later.
5. Choose a region closest to you and click **Create new project**. (It takes a few minutes to set up).
6. Once the project dashboard loads, look at the left sidebar menu. Click the **⚙️ Project Settings** (gear icon) at the very bottom.
7. Click **Database** in the settings menu.
8. Scroll down to **Connection string** and click the **URI** tab.
9. Copy the URI string provided. It will look like this:
   `postgresql://postgres.xxxx:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres`
10. Paste this into your notepad. **Replace the `[YOUR-PASSWORD]` part in that string with the password you created in step 4.**
11. This final string is your `DATABASE_URL`.

---

## 🧠 Step 3: Get the AI Brain (Groq)
Groq provides blazing-fast AI inference for free.

1. Go to [https://console.groq.com](https://console.groq.com) and log in (you can use your Google or GitHub account).
2. On the left sidebar, click **API Keys**.
3. Click the **Create API Key** button.
4. Give it a name (e.g., `famfin-key`) and click Submit.
5. **Copy the key immediately.** (It usually starts with `gsk_`). 
6. Paste it into your notepad. This is your `GROQ_API_KEY`.

---

## 🔐 Step 4: Create Security Keys
To ensure all financial data is encrypted and secure, we need two secret keys.

1. **Encryption Key:** We need a strong random key to lock the database.
   * Go to this secure generator: [https://asecuritysite.com/encryption/keygen](https://asecuritysite.com/encryption/keygen) (or generate a 32-byte base64 string). 
   * Alternatively, if you have Python installed locally, run this in your terminal: 
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   * Save the output in your notepad as `ENCRYPTION_KEY`.
2. **Webhook Secret:** This proves that messages are actually coming from Telegram.
   * Just mash your keyboard to make a random string (e.g., `my_super_secret_telegram_string_2026`). No spaces.
   * Save this in your notepad as `MESSAGING_WEBHOOK_SECRET`.

---

## 🚀 Step 5: Deploy the Code (Render)
Now we will put the code on a server that runs 24/7 for free.

1. Log into your GitHub account and make sure the FamFin-AI code is pushed to a repository on your account.
2. Go to [https://dashboard.render.com](https://dashboard.render.com) and create a free account (sign up with GitHub).
3. Click the **New +** button at the top right and select **Web Service**.
4. Select **Build and deploy from a Git repository** and click Next.
5. Connect your GitHub account and select your `FamFin-AI` repository.
6. Fill out the deployment details:
   * **Name:** `famfin-ai-bot`
   * **Region:** (Pick the one closest to your Supabase region)
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port 10000`
   * **Instance Type:** Select the **Free** tier.
7. Scroll down to the **Environment Variables** section and click **Add Environment Variable**. Add all the secrets from your notepad:
   * Key: `DATABASE_URL` | Value: (Your Supabase URI with the password)
   * Key: `ENCRYPTION_KEY` | Value: (Your Fernet key)
   * Key: `TELEGRAM_BOT_TOKEN` | Value: (Your BotFather token)
   * Key: `MESSAGING_WEBHOOK_SECRET` | Value: (Your random keyboard mash)
   * Key: `GROQ_API_KEY` | Value: (Your `gsk_...` key)
   * Key: `DEFAULT_CURRENCY` | Value: `USD`
8. Click **Deploy Web Service** at the bottom.
9. Render will start building the app. Wait 5-10 minutes. When it says "Live" in green, look at the top left under your app name. You will see a URL (e.g., `https://famfin-ai-bot.onrender.com`). **Copy this URL to your notepad.**

---

## 🔗 Step 6: Connect Telegram to Your Server
Finally, we need to tell Telegram to send messages to your Render server.

1. Open a new tab in your web browser.
2. You need to build a special URL by filling in the brackets with your actual data from the notepad. Do not include the `<` or `>` brackets.

**The Template:**
`https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<RENDER_URL>/telegram/webhook&secret_token=<MESSAGING_WEBHOOK_SECRET>`

**Example of what it should look like:**
`https://api.telegram.org/bot1234567890:ABCdefGHI/setWebhook?url=https://famfin-ai-bot.onrender.com/telegram/webhook&secret_token=my_super_secret_telegram_string_2026`

3. Paste your customized URL into the address bar of your browser and hit Enter.
4. If successful, you will see a white screen with text like: `{"ok":true,"result":true,"description":"Webhook was set"}`.

## 🎉 You're Done!
Open Telegram, search for your bot, and click **Start**. Try sending it a message like "I spent $5 on coffee." It should reply instantly!
