# 🏠 Self-Hosting Clanomy

Welcome! Clanomy operates on a **Hybrid Open Core model**. While we offer a zero-friction Managed SaaS version via Telegram for those who want instant access without the hassle of servers, we believe strongly in privacy and data sovereignty. 

If you are privacy-obsessed, technically inclined, or just prefer to own your infrastructure, you can self-host the entire Clanomy stack for free!

If you find this open-source version valuable and it saves you money, consider supporting the project via [Ko-fi](https://ko-fi.com/crespoantonio) to help maintain the code and keep adding new features!

---

## 🏗️ What You Will Be Hosting
The Clanomy stack consists of three main containers:
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
git clone https://github.com/crespoantonio/clanomy.git
cd clanomy
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

# Household defaults
DEFAULT_CURRENCY=USD
DEFAULT_TIMEZONE=UTC

# AI Engine Configuration (Recommended: Gemini)
AI_PROVIDER=gemini
AI_API_KEY=AIzaSy_your_gemini_api_key_here

# Guarantee 100% unlocked self-hosted instance (never requires payment or license key)
ENABLE_SUBSCRIPTIONS=false

# (Optional) Local message simulation endpoint secret
SIMULATION_SECRET=

# (Optional) Origin Shielding token if placing behind Cloudflare proxy/tunnel
CLOUDFLARE_ORIGIN_SECRET=

# (Optional) API Documentation Stealth Mode (defaults to false to hide /docs in production)
ENABLE_DOCS=false
```

### 4. Choose Your AI Inference Mode

Clanomy features a unified modular LLM provider layer (`src/core/llm/`). You can choose between **Google Gemini (Recommended)**, **Groq / OpenAI Cloud**, or **100% Local Inference**:

#### Option A: Google Gemini (Recommended — Native Multimodal Audio & Free Tier)
- **Zero Local Hardware Requirement**: Direct native multimodal audio transcription — runs with <150MB total container RAM because you do **not** need a local Whisper or GPU instance.
- **Ultra-Fast & Generous Free Tier**: Uses `gemini-2.5-flash-lite` via Google AI Studio for fast (<300ms) bilingual extraction.
- Configuration in `.env`:
  ```env
  AI_PROVIDER=gemini
  AI_API_KEY=AIzaSy_your_google_gemini_api_key_here
  ```
  *(Note: Keys starting with `AIzaSy` are automatically detected and configured).*

#### Option B: Lightweight Cloud Inference (Groq Cloud / OpenAI)
- Extremely low memory footprint (<300MB RAM), ideal for free or cheap cloud VPS (Render, Hetzner, Fly.io).
- Uses Groq Whisper Large v3 or OpenAI Whisper-1 for audio transcription, and Llama 3.3 70B or GPT-4o-mini for text extraction.
- Configuration in `.env`:
  ```env
  AI_PROVIDER=groq
  AI_API_KEY=gsk_your_groq_api_key_here
  AI_BASE_URL=https://api.groq.com/openai/v1
  AI_MODEL=llama-3.3-70b-versatile
  ```

#### Option C: 100% Local Inference (Ollama + Local Faster-Whisper)
- Keeps all audio and text processing completely private on your own local hardware.
- Requires ~8GB RAM for running LLaMA3 and Whisper locally.
- Configuration in `.env`:
  ```env
  AI_PROVIDER=ollama
  WHISPER_PROVIDER=local
  OLLAMA_BASE_URL=http://ollama:11434
  AI_MODEL=llama3
  ```

---

### 5. Start the Stack
Spin up the containers in detached mode using Podman (recommended) or Docker:
```bash
# If using Podman (Recommended)
podman compose up -d --build

# If using Docker
docker compose up -d --build
```

*(If using Option C with local Ollama, pull the LLaMA3 model once the containers start: `podman compose exec ollama ollama pull llama3` or `docker compose exec ollama ollama pull llama3`).*

---

### 6. Connect Telegram to Your Server
Telegram needs to know where to send your messages and button clicks. You must expose port `8000` to the internet (e.g., via Cloudflare Tunnels: `https://clanomy.yourdomain.com`).

> [!IMPORTANT]
> You **must** specify `"allowed_updates": ["message", "callback_query"]` when registering your webhook. The `callback_query` update type is required for interactive inline keyboards (such as the interactive `/currency` command).

Register your webhook with Telegram:

**Option A: Linux / macOS / Bash**
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://YOUR_DOMAIN.COM/api/v1/telegram/webhook",
       "secret_token": "YOUR_MESSAGING_WEBHOOK_SECRET_FROM_ENV",
       "allowed_updates": ["message", "callback_query"]
     }'
```

**Option B: Windows PowerShell**
```powershell
curl.exe -X POST "https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook" `
     -H "Content-Type: application/json" `
     -d '{
       "url": "https://YOUR_DOMAIN.COM/api/v1/telegram/webhook",
       "secret_token": "YOUR_MESSAGING_WEBHOOK_SECRET_FROM_ENV",
       "allowed_updates": [\"message\", \"callback_query\"]
     }'
```

---

### 7. Zero Limits Out-of-the-Box
In self-hosted mode (`ENABLE_SUBSCRIPTIONS=false`, default), Clanomy runs completely unrestricted:
- **Unlimited transaction logging** (voice & text, including compound batch logging).
- **Instant fast-path slash commands** (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/timezone`, `/currency`) with <40ms response time.
- **Interactive `/currency` picker**: Paginated Telegram inline keyboard allows browsing and selecting currencies interactively.
- **Unlimited multi-member family workspaces** with shared ledger access and member attribution.
- **Notion real-time ledger synchronization**.
- **Natural language conversational cash-flow queries & exports (CSV/JSON)**.
- **Zero subscription paywalls, artificial quotas, or trial timeouts**.

---

### 8. Hardening Your Bot & User Allowlisting (Recommended)
By default in Telegram, any bot created via BotFather is globally searchable. If a stranger searches for your bot handle, they could send messages or voice notes to it.

To prevent unauthorized users from using your GPU/CPU compute, AI inference, or database:

1. **Configure User Allowlisting in `.env`:**
   Add your Telegram username (or numeric Telegram ID) to `ALLOWED_TELEGRAM_USERS`:
   ```env
   # Restrict bot usage to you and your family members:
   ALLOWED_TELEGRAM_USERS=my_username, my_spouse_username, 123456789
   ```
   *Any user not in this list will be rejected immediately in < 1ms before any AI or database processing occurs.*

2. **Ingress Resource Abuse Guardrails (Pre-Inference Gatekeeping):**
   Clanomy prevents resource exhaustion by inspecting metadata before downloading audio or invoking AI inference models:
   ```env
   # Maximum voice note duration in seconds (default: 35)
   MAX_VOICE_DURATION_SECONDS=35

   # Maximum text message length in characters (default: 350)
   MAX_TEXT_LENGTH=350
   ```
   * **Voice Duration Cap:** Voice recordings exceeding `MAX_VOICE_DURATION_SECONDS` are rejected synchronously before downloading or transcribing.
   * **Text Length Cap:** Text inputs exceeding `MAX_TEXT_LENGTH` are rejected immediately before invoking the LLM.
   * **Strict Media Filter:** Documents (PDFs), images, videos, audio files, and stickers are rejected early with friendly feedback, ensuring only native voice notes and text are processed.

3. **Verify AI Extraction Offline via Simulation Route (`/simulate/message`):**
   To test that your AI provider is extracting transactions correctly without needing to send a message via Telegram, configure `SIMULATION_SECRET` in `.env`:
   ```bash
   curl -X POST "http://localhost:8000/simulate/message" \
        -H "Content-Type: application/json" \
        -H "X-Simulation-Secret: your_simulation_secret" \
        -d '{"text": "Spent 15 on lunch at cafe", "default_currency": "USD"}'
   ```
   This returns the structured JSON extraction result, duration, and formatted bot response directly.

4. **Harden Privacy via BotFather:**
   - Open `@BotFather` on Telegram.
   - Send `/mybots` > Select your bot > **Bot Settings**.
   - **Group Privacy:** Ensure it is **Enabled** so the bot only reads messages directed at it if added to a group.
   - **Allow Groups? / `join_groups`:** Set to **Turn groups off** if you only plan to use private chats with your household.

5. **Origin Shielding & Stealth API:**
   - Set `CLOUDFLARE_ORIGIN_SECRET` if using Cloudflare Tunnels/Proxy to prevent direct port-8000 access.
   - Keep `ENABLE_DOCS=false` to prevent automated scanners from introspecting `/docs` or `/openapi.json`.

---

## 🔒 Security Best Practices
- **Strict Environment Enforcement**: `ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`, and `MESSAGING_WEBHOOK_SECRET` are strictly required with no insecure fallback defaults. The container fails fast at startup if any variable is missing.
- **HTTP Security Headers Middleware**: Responses automatically include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and HSTS headers while stripping the `Server` identity header.
- **Never expose your PostgreSQL database to the internet.** Ensure port `5432` is firewalled or bound only to localhost/container network.
- **Keep your `ENCRYPTION_KEY` safe.** If you lose this key, your transaction amounts and concepts will be permanently unreadable, even to you. Back it up securely.
- **Set `ALLOWED_TELEGRAM_USERS`** to prevent strangers from triggering local Whisper/Ollama inference.
- **Tune `MAX_VOICE_DURATION_SECONDS` and `MAX_TEXT_LENGTH`** based on your server capacity and user habits.
- **Health Probes**: The `/health` endpoint returns `200 OK` when healthy and `503 Service Unavailable` if the database connection fails, allowing reverse proxies and container orchestrators to route traffic safely.
- **Cloudflare Edge Defense**: When self-hosting on a public IP, place Cloudflare in front with **Full (Strict)** SSL and WAF rules to drop non-Telegram scanner bots before they reach your server.

Enjoy true zero-friction, privacy-first financial tracking! 💸🤖

