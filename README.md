# Clanomy 💰🤖

Clanomy is an open-source, privacy-first, multi-tenant family financial assistant. It combines a high-performance FastAPI backend with a local-first AI pipeline (Faster-Whisper for voice transcription and Ollama for entity extraction) and application-level AES-256 encryption.

---

## ✨ Features

- **🎙️ Dual Natural Language Logging**: Log both expenses and income seamlessly via text or voice notes.
- **🤖 Local AI Inference**: Built-in Faster-Whisper audio transcription and Ollama (LLaMA3) transaction parsing for complete privacy.
- **👨‍👩‍👧‍👦 Family Workspaces**: Multi-user ledger with per-member attribution, shared balances, and custom roles.
- **📊 Conversational Financial Insights**: Ask queries like *"How much did we spend on groceries this month?"* or *"What is our net cash flow for February?"*.
- **🔄 Real-Time Notion Sync**: Two-way encrypted synchronization directly into your family's personal Notion database.
- **🔐 Zero-Knowledge Security**: Application-level AES-256 field encryption for all transaction amounts and concepts before database persistence.
- **📦 100% Free & Unrestricted Self-Hosting**: Deploy on your own hardware or cloud with zero paywalls, tiers, or artificial limits.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- [Podman](https://podman.io/) (or Docker) & `podman-compose` / `docker-compose`
- Python 3.12+ (optional, for local development outside containers)

### 2. Configure Environment
```bash
cp .env.example .env
```
Generate an encryption key:
```bash
python scripts/generate_key.py
```
Paste the generated key into `ENCRYPTION_KEY` in your `.env`.

### 3. Start Containers
```bash
podman compose up -d --build
```

- **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Ollama AI Server:** [http://localhost:11434](http://localhost:11434)

### 4. Pull AI Models
```bash
podman compose exec ollama ollama pull llama3
```

---

## 📖 Deployment & Self-Hosting Guides

For full, step-by-step guides on deploying Clanomy to production or home lab environments:

- **[Self-Hosting Guide (Docker / Podman / Home Lab)](docs/self-hosting.md)**: Detailed instructions on running Clanomy on your own server, configuring reverse proxies, tunnels, and connecting your Telegram bot.
- **[Cloud Deployment Guide (Always-Free Stack)](docs/deployment-guideline.md)**: Guide to hosting Clanomy on Render + Supabase + Groq with zero monthly infrastructure costs.

---

## 🛠 Testing & Development

Install development and testing dependencies:
```bash
pip install -r requirements-dev.txt
```

Run the automated test suite:
```bash
pytest
```
Or inside the container environment:
```bash
podman compose exec app pytest
```

Check application health:
```bash
curl http://localhost:8000/health
```

---

## 🔒 Security Principles

- **Field-Level Encryption**: Sensitive financial records (amounts, descriptions, notes) are encrypted at the application layer using `cryptography.fernet`.
- **Tenant Isolation**: Workspace boundaries and user data are strictly isolated per family.
- **Local AI Privacy**: Voice processing and LLM reasoning run locally, preventing financial leaks to third-party APIs.

---

## 📄 License & Architecture

Clanomy is distributed under the open-core model. For architecture and sprint planning details, see the `_bmad-output/` directory.
