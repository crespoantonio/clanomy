# Always-Free Deployment Guide: FamFin-AI (50+ Users)

This guide provides step-by-step instructions to deploy **FamFin-AI** to the cloud on an **Always-Free ($0.00/month)** architecture capable of supporting **50 to 500+ active users** with sub-second response times.

---

## 🏗️ Architecture Options Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                  OPTION 1: Cloud-Native Micro Stack (Easiest)                │
│                                                                              │
│  [ Telegram ] ──► [ Render / Koyeb (FastAPI) ] ──► [ Supabase (PostgreSQL) ] │
│                             │                                                │
│                             ▼                                                │
│                     [ Groq Cloud API ]                                       │
│              (Whisper Large v3 + Llama 3.1 8B)                               │
│                   14,400 Free Requests/Day                                   │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                  OPTION 2: Dedicated Free VPS (Full Control)                 │
│                                                                              │
│  [ Telegram ] ──► [ Oracle Cloud Free VM (4 CPUs, 24GB RAM, 200GB SSD) ]    │
│                        ├─► [ FamFin FastAPI Container ]                      │
│                        ├─► [ PostgreSQL Container ]                          │
│                        ├─► [ Ollama / Local LLM Container ]                  │
│                        └─► [ Faster-Whisper Container ]                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Comparison of Always-Free Strategies

| Feature | Option 1: Cloud-Native Micro Stack | Option 2: Oracle Cloud Free VPS |
|---|---|---|
| **Setup Time** | **15 minutes** | **30–45 minutes** |
| **Monthly Cost** | **$0.00 / month forever** | **$0.00 / month forever** |
| **Compute Limit** | 512 MB RAM (Render / Koyeb) | **24 GB RAM, 4 OCPUs** |
| **AI Inference** | Groq Cloud Free API (0.3s latency) | Self-hosted Ollama (1.5s latency) |
| **STT (Voice)** | Groq Whisper Large-v3 | Local Faster-Whisper |
| **Database** | Supabase / Neon (Free PostgreSQL) | Self-hosted PostgreSQL |
| **Maintenance** | Zero maintenance (Serverless) | OS updates & Docker/Podman maintenance |
| **Capacity** | **500+ users** (14,400 req/day) | **500+ users** |

---

# 🚀 Strategy 1: Cloud-Native Micro Stack (Recommended)

This strategy splits the architecture across the best generous free-tier cloud providers so you never hit resource limits.

### 1. Services & Free Quotas

1. **AI Inference & Audio Transcription:** **[Groq Cloud](https://console.groq.com)**
   * **Free Tier Quota:** 14,400 requests/day, 30 requests/min.
   * **Models:** Llama 3.3 70B / Llama 3.1 8B + Whisper Large-v3.
   * **Speed:** ~0.3 seconds per response.
2. **Managed Database:** **[Supabase](https://supabase.com)** or **[Neon](https://neon.tech)**
   * **Free Tier Quota:** 500 MB persistent PostgreSQL (enough for 200,000+ encrypted transactions).
   * **Backups:** Automatic daily backups included.
3. **Application Hosting:** **[Render](https://render.com)** or **[Koyeb](https://koyeb.com)**
   * **Free Tier Quota:** 512 MB RAM, free public HTTPS domain.

---

### Step-by-Step Deployment Instructions (Strategy 1)

#### Step 1.1: Obtain Free Groq API Key
1. Go to [https://console.groq.com](https://console.groq.com) and create a free account.
2. Navigate to **API Keys** and click **Create API Key**.
3. Copy the key (e.g. `gsk_xxxxxxxxxxxxxxxxxxxx`).

#### Step 1.2: Create Free PostgreSQL Database on Supabase
1. Go to [https://supabase.com](https://supabase.com) and create a new free project.
2. Set your database password.
3. Navigate to **Project Settings > Database** and copy your **Connection String (URI)**.
   * Format: `postgresql+psycopg://postgres.xxxx:your_password@aws-0-region.pooler.supabase.com:6543/postgres`

#### Step 1.3: Generate Application Encryption Key
Generate your AES-256 Fernet key in your local terminal:
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### Step 1.4: Deploy to Render (or Koyeb)
1. Push your repository to **GitHub**.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New + > Web Service** and connect your GitHub repository.
4. Set the build parameters:
   * **Runtime:** `Python 3` (or `Docker` using `Containerfile`)
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port 10000`
   * **Instance Type:** `Free`
5. Under **Environment Variables**, add:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres.xxxx:your_password@aws-0-region.pooler.supabase.com:6543/postgres
   ENCRYPTION_KEY=your_generated_fernet_key
   MESSAGING_WEBHOOK_SECRET=your_super_secret_webhook_token
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
   GROQ_API_KEY=gsk_your_groq_key_here
   DEFAULT_CURRENCY=USD  # Optional: Primary currency code (defaults to USD)
   ```
6. Click **Deploy Web Service**. Render will give you a public HTTPS URL (e.g. `https://famfin-ai.onrender.com`).

#### Step 1.5: Register Telegram Webhook
Point Telegram directly to your deployed service (one-time setup in your browser or terminal):
```text
https://api.telegram.org/bot<YOUR_TELEGRAM_BOT_TOKEN>/setWebhook?url=https://famfin-ai.onrender.com/api/v1/telegram/webhook&secret_token=<YOUR_MESSAGING_WEBHOOK_SECRET>
```

---

# 🖥️ Strategy 2: Oracle Cloud Always-Free Dedicated VPS

If you want **100% self-hosted privacy** with all containers (FastAPI, Ollama, Whisper, PostgreSQL) running on a single dedicated virtual machine without third-party AI APIs.

### 1. Free Quota from Oracle
* **VM Shape:** Ampere A1 (ARM64)
* **Specs:** **4 OCPUs, 24 GB RAM, 200 GB NVMe Storage**
* **Price:** **$0.00 / month for life**

---

### Step-by-Step Deployment Instructions (Strategy 2)

#### Step 2.1: Provision Oracle Cloud VM
1. Sign up at [https://www.oracle.com/cloud/free/](https://www.oracle.com/cloud/free/).
2. In the Oracle Console, go to **Compute > Instances > Create Instance**.
3. Under **Image and shape**:
   * Image: `Ubuntu 22.04 LTS (AArch64)`
   * Shape: `Ampere VM.Standard.A1.Flex` (Allocate `4 OCPUs` and `24 GB RAM`).
4. Add your SSH Key and click **Create**.

#### Step 2.2: Configure Firewall & Ports
In the Oracle Cloud Console (and in `iptables` inside Ubuntu):
* Open ingress ports: `80` (HTTP), `443` (HTTPS), `22` (SSH).

#### Step 2.3: Install Podman and Git
Connect to your VPS via SSH:
```bash
ssh ubuntu@YOUR_VM_IP
sudo apt update && sudo apt install -y podman podman-compose git caddy
```

#### Step 2.4: Deploy FamFin-AI Stack
```bash
git clone https://github.com/your-username/FamFin-AI.git
cd FamFin-AI
cp .env.example .env
nano .env  # Fill in DB passwords, Fernet key, and Telegram Bot Token
podman-compose up -d --build
podman exec -it famfin-ollama ollama pull llama3.2
```

#### Step 2.5: Setup Automatic Free SSL with Caddy
Configure `/etc/caddy/Caddyfile`:
```caddy
yourdomain.com {
    reverse_proxy localhost:8000
}
```
Reload Caddy:
```bash
sudo systemctl restart caddy
```
*(Caddy automatically provisions and auto-renews free Let's Encrypt SSL certificates).*

---

## 🔒 Security & Privacy Best Practices for Production

1. **Fernet Key Backup:**
   * Store your `ENCRYPTION_KEY` in a secure password manager (e.g. 1Password/Bitwarden). If this key is lost, all database ciphertext cannot be recovered.
2. **Secret Header Validation:**
   * Always enforce `MESSAGING_WEBHOOK_SECRET` / Telegram secret token on incoming webhooks to reject spoofed requests.
3. **Database Isolation:**
   * Disable public PostgreSQL access once deployed or restrict IP allowlists to the application host.

---

## 📈 Capacity & Scaling Math for 50 Users

* **Daily Volume:** 50 users × 4 messages/day = **200 transactions / day**.
* **Monthly DB Storage:** 200 tx/day × 30 days × 1 KB/tx = **~6 MB / month** (Years of storage on a 500 MB free database).
* **AI API Quota Consumption:** 200 / 14,400 daily limit = **~1.4% of free tier utilized**.
* **Total Cost:** **$0.00**
