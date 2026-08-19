# 🏠 Self-Hosting FamFin-AI

Welcome! FamFin-AI operates on a **Hybrid Open Core model**. While we offer a zero-friction Managed SaaS version via Telegram for those who want instant access without the hassle of servers, we believe strongly in privacy and data sovereignty. 

If you are privacy-obsessed, technically inclined, or just prefer to own your infrastructure, you can self-host the entire FamFin-AI stack for free!

If you find this open-source version valuable and it saves you money, consider supporting the project via [Patreon/Ko-fi] (link coming soon) to help us keep maintaining the code and adding new features!

---

## 🏗️ What You Will Be Hosting
The FamFin-AI stack consists of three main containers:
1. **App**: The FastAPI Python backend that handles Telegram webhooks and business logic.
2. **Database**: A PostgreSQL instance where all your financial data is stored with AES-256 application-level encryption.
3. **Ollama**: A local AI server running LLaMA3 to parse your natural language expenses into structured JSON data.

*(Note: The Faster-Whisper model for voice transcriptions runs directly inside the App container).*

---

## 📋 Prerequisites
Before you begin, ensure your server or local machine has:
- **Docker** or **Podman** installed with `docker-compose` / `podman-compose`.
- At least 8GB of RAM (required for running the local LLaMA3 and Whisper models).
- A domain name, reverse proxy, or tunnel (like Ngrok or Cloudflare Tunnels) to expose port `8000` to the internet securely.
- A Telegram account.

---

## 🚀 Step-by-Step Deployment Guide

### 1. Create a Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to name your bot.
3. BotFather will give you an API Token (e.g., `123456789:ABCDEF...`). Save this!

### 2. Clone the Repository
```bash
git clone https://github.com/yourusername/FamFin-AI.git
cd FamFin-AI
```

### 3. Configure the Environment
Copy the example `.env` file to set up your secrets:
```bash
cp .env.example .env
```

Generate a secure AES-256 encryption key. Run the following command and copy the output:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Open `.env` and configure the following essential variables:
```env
# Paste the key you just generated
ENCRYPTION_KEY=YOUR_GENERATED_FERNET_KEY_HERE

# Paste your Telegram Token
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_FROM_BOTFATHER

# Create a strong secret for Telegram to authenticate webhooks
MESSAGING_WEBHOOK_SECRET=a_very_long_secure_random_string
```

### 4. Start the Stack
Spin up the containers in detached mode:
```bash
# If using Podman
podman compose up -d --build

# If using Docker
docker compose up -d --build
```

### 5. Pull the Local AI Model
The application requires the LLaMA3 model to understand your expenses. Pull it into the Ollama container:
```bash
podman compose exec ollama ollama pull llama3
```

### 6. Connect Telegram to Your Server
Telegram needs to know where to send your messages. You must expose port `8000` to the internet (e.g., via Cloudflare Tunnels: `https://famfin.yourdomain.com`).

Once exposed, register your webhook with Telegram by running this `curl` command:
```bash
curl -F "url=https://YOUR_DOMAIN.COM/api/v1/telegram/webhook" \
     -F "secret_token=YOUR_MESSAGING_WEBHOOK_SECRET_FROM_ENV" \
     https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook
```

### 7. Claim VIP / Lifetime Pro Access
By default, the application enforces a 30-transaction free tier limit. Since you are the server owner, you can bypass this and grant your family unrestricted access.

1. Send any message to your newly created Telegram bot (e.g., "Hello").
2. Run the administrative script on your server, providing your Telegram ID (you can find your ID using bots like `@userinfobot` or checking the app logs):
   ```bash
   podman compose exec app python scripts/grant_lifetime_pro.py --telegram-id YOUR_TELEGRAM_ID
   ```
3. You now have permanent, free-forever VIP access with no limits!

---

## 🔒 Security Best Practices
- **Never expose your PostgreSQL database to the internet.** Ensure port `5432` is firewalled or bound only to localhost.
- **Keep your `ENCRYPTION_KEY` safe.** If you lose this key, your transaction amounts and concepts will be permanently unreadable, even to you. Back it up securely.
- Only share your Bot link with family members you trust.

Enjoy true zero-friction, privacy-first financial tracking! 💸🤖
