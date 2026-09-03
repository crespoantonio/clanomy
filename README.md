# Clanomy 💰🤖

[![License: BSL 1.1](https://img.shields.io/badge/License-BSL--1.1-blue.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Project-F16061?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/crespoantonio)

Clanomy is an open-source, privacy-first, multi-tenant family financial assistant. It combines a high-performance FastAPI backend with AI pipeline options (local Faster-Whisper + Ollama or ultra-fast cloud inference with Groq / OpenAI) and application-level AES-256 zero-knowledge encryption.

---

## ✨ Features

- **🎙️ Dual Natural Language Logging**: Log both expenses and income seamlessly via voice notes or text in **English and Spanish** (*"Coffee $4"*, *"Spent 45 on groceries"*, *"Gané 3000 de sueldo"*, *"Gasté 500 en helado"*).
- **📦 Compound Batch Logging**: Report multiple items in a single voice note or text message (*"Gasté 18500 en el súper y 8000 en la farmacia"*); undo compound batches with a single `/undo`.
- **⚡ Instant Fast-Path Slash Commands**: Zero-latency deterministic commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`) running in Python/SQL in <40ms with $0 AI overhead.
- **🕒 Household Timezone Localization**: Set your household's local timezone with `/timezone <IANA_TZ>` (e.g. `America/Argentina/Buenos_Aires`) so queries and daily summaries align with your local calendar day.
- **🌐 Per-Family Currency & Multi-Currency Segregation**: Configure your household's default currency with `/currency <ISO_CODE>` (USD, ARS, MXN, EUR, CLP, COP, etc.). Multi-currency ledgers are strictly segregated without arbitrary exchange rate blending.
- **🤖 Flexible AI Engine**: Runs 100% locally with Faster-Whisper + Ollama (LLaMA3) or via cloud inference with a single unified `AI_API_KEY` (Groq, OpenAI, Google Gemini).
- **👨‍👩‍👧‍👦 Family Workspaces**: Multi-user ledger with per-member attribution, shared balances, and flat household transparency.
- **📊 Conversational Financial Insights**: Ask queries in Spanish or English like *"How much did we spend on groceries this month?"* or *"¿Cuáles fueron mis gastos de los últimos 15 días?"*.
- **🔄 Real-Time Notion Sync**: Two-way encrypted synchronization directly into your family's personal Notion database.
- **🔐 Zero-Knowledge Security**: Application-level AES-256 field encryption for all transaction amounts and concepts before database persistence.
- **🏠 100% Free & Unrestricted Self-Hosting**: Deploy on your own server or home lab using Podman (or Docker) with zero paywalls, tiers, or artificial restrictions.

---

## 🤖 Telegram Bot Commands

When creating your bot with `@BotFather`, register the following command list:

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

### 4. Pull AI Models (if using Local Ollama)
```bash
podman compose exec ollama ollama pull llama3
```

---

## 📖 Deployment & Self-Hosting Guides

For full, step-by-step guides on deploying Clanomy to production or home lab environments:

- **[Cloud Deployment Guide (Always-Free Stack)](docs/deployment-guideline.md)**: Guide to hosting Clanomy on Render + Supabase + Groq with zero monthly infrastructure costs.
- **[Self-Hosting Guide (Docker / Podman / Home Lab)](docs/self-hosting.md)**: Detailed instructions on running Clanomy on your own server, configuring reverse proxies, tunnels, and connecting your Telegram bot.
- **[Complete Manual Testing Guide](docs/manual-testing-guide.md)**: Step-by-step manual testing scenarios for voice logging, multi-currency, and family features.

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
- **Local / Private AI**: Voice processing and LLM reasoning run on your chosen privacy stack (local GPU/CPU or zero-data-retention cloud AI).

---

## ☕ Support the Project

Clanomy is 100% free and open-source. If this project saves you time, money, or helps your family keep finances organized, consider supporting its development:

[![Buy Me a Coffee](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/crespoantonio)

Your support helps cover testing environments, third-party AI tokens, and ongoing maintenance!

---

## 📄 License & Architecture

Clanomy is distributed under the open-core model. For architecture and sprint planning details, see the `_bmad-output/` directory.


