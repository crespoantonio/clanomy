# FamFin-AI 💰🤖

FamFin-AI is a privacy-first, multi-tenant family financial assistant. It features a high-performance FastAPI backend, a local-first AI pipeline for voice-to-JSON expense tracking, and application-level encryption to ensure data privacy.

## 🚀 Quick Start

### 1. Prerequisites
- **Podman** & **Podman Compose** installed.
- Python 3.12+ (optional, for local development).

### 2. Environment Setup
Copy the example environment file and configure your secrets:
```bash
cp .env.example .env
```

### 3. Generate Encryption Key
The project uses application-level AES-128 encryption via the Fernet recipe. You **must** generate a valid key for your `.env` file:
```bash
# Using the provided helper script
python scripts/generate_key.py
```
Copy the output into `ENCRYPTION_KEY` in your `.env`.

### 4. Launch the Application
Start the containerized environment (FastAPI + PostgreSQL + Ollama):
```bash
podman compose up -d --build
```

- **FastAPI Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Ollama AI Inference:** [http://localhost:11434](http://localhost:11434)

### 5. Download AI Models
To prepare the system for transaction extraction and speech-to-text:
```bash
# Pull the LLM for transaction parsing
podman-compose exec ollama ollama pull llama3
```
*Note: The Faster-Whisper audio transcription model is downloaded automatically the first time an audio request is processed.*

---

## 🔗 Testing & Telegram Webhook Integration

The architecture natively integrates with the Telegram Bot API via FastAPI `BackgroundTasks`.

### Connecting Telegram

To connect Telegram with the FastAPI backend:

1. Expose your local port 8000 to the internet (e.g., using `ngrok`):
   ```bash
   ngrok http 8000
   ```
2. Register your webhook URL directly with Telegram:
   ```bash
   curl -F "url=https://<your-ngrok-url>/api/v1/telegram/webhook" -F "secret_token=your_messaging_secret_token_here" https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook
   ```
3. Send a message to your Telegram bot.
4. Watch the backend terminal logs to see the "3-second rule" async processing, transcription, Ollama extraction, and encryption!

### Usage Examples
You can query your family expenses using natural language:
- **General Summary**: "What did we spend this month?"
- **Per-Member Filter**: "How much did Tony spend on groceries this week?"
- **Comparisons**: "Did we spend more this month than last month?"

---

## 🛠 Development Commands

### Check Application Health
Verify the API and Database connectivity:
```bash
curl http://localhost:8000/health
```

### Run Tests
All unit and integration tests should be run inside the container to ensure environment parity:
```bash
podman compose exec app pytest
```

### View Logs
```bash
podman compose logs -f app
```

### Grant Lifetime Pro (VIP Access)
To bypass the free tier 30-transaction monthly limit and grant a user's family "free forever" VIP access, run the administrative script with the target Telegram ID:
```bash
# Run locally (if using venv)
python scripts/grant_lifetime_pro.py --telegram-id 123456789

# Or inside the container
podman compose exec app python scripts/grant_lifetime_pro.py --telegram-id 123456789
```
This updates the database (`plan_type = 'lifetime_pro'`) and instantly grants unlimited features to all members of that family.

---

## 🏗 Project Architecture

- **`src/`**: Core application logic.
  - **`core/`**: Security (Encryption), Configuration, and Shared Utilities.
  - **`db/`**: SQLModel sessions and database initialization.
  - **`api/`**: FastAPI routers and endpoints.
- **`tests/`**: Pytest suite organized by service and layer.
- **`scripts/`**: Development and maintenance utilities.
- **`_bmad-output/`**: Project planning, architecture, and sprint tracking artifacts.

## 🔒 Security Principles
- **Field-Level Encryption**: Sensitive financial data is encrypted before storage using `cryptography.fernet`.
- **Multi-Tenancy**: Data is strictly isolated per family/user using a multi-tenant schema.
- **Local AI**: Voice processing (Faster-Whisper) and extraction (Ollama) run locally to keep data off the public cloud.

---

## 📅 Sprint Status
The project progress is tracked in `_bmad-output/implementation-artifacts/sprint-status.yaml`.
**Epic 1: Privacy-First Foundation** and **Epic 2: Zero-Friction Expense Logging** are fully completed. The backend pipeline is fully functional!
