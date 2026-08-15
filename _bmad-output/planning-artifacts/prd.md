---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
releaseMode: phased
inputDocuments:
  - c:\Users\cresp\Documents\Projectos\FamFin-AI\_bmad-output\planning-artifacts\product_brief_famfin_ai.md
classification:
  projectType: SaaS (Messaging Bot Platform)
  domain: Fintech (Micro-Accounting)
  complexity: High
  projectContext: greenfield
workflowType: prd
---

# Product Requirements Document - FamFin AI

**Author:** Tony
**Date:** 2026-05-08

## 1. Executive Summary
FamFin AI is an "invisible" financial companion designed to solve the chronic problem of expense tracking friction for solo entrepreneurs and families. By living directly within Telegram and WhatsApp (via native API webhooks) and leveraging local AI (Ollama and Whisper), FamFin AI enables zero-friction, privacy-centric expense logging via natural language audio and text. Users manage their finances through conversational interaction, receiving instant text confirmations and querying their spending history without ever leaving their primary messaging app.

### Core Differentiator
The elimination of "App Fatigue" through a zero-friction entry model. While traditional finance tools require manual data entry into specialized interfaces, FamFin AI allows users to record expenses in seconds via voice notes processed locally, ensuring sensitive financial data never leaves the user's controlled infrastructure.

## 2. Success Criteria

### 2.1 User Success
*   **The 3-Second Rule:** Users must complete an expense entry (from Telegram open to confirmation) in under 3 seconds.
*   **Conversational Clarity:** Users can query spending status in natural language with a margin of error < 7%.
*   **Emotional Relief:** Users feel financial awareness without the anxiety of opening a traditional banking app.

### 2.2 Business Success
*   **Initial Traction:** Achieve 50 active users logging ≥3 expenses per week for 30 consecutive days.
*   **Monetization Validation:** Validate willingness to pay for Premium Tiers (Family Groups, Notion Mirroring).
*   **Brand Authority:** Establish a reputation in the "Privacy-First" niche leveraging Estonian e-Residency trust.

### 2.3 Technical Success
*   **Extraction Accuracy:** 90% success rate extracting Amount, Category, and Concept from natural language.
*   **Zero-Leakage Privacy:** 100% of PII and transaction data remains within the private local infrastructure.
*   **System Latency:** End-to-end processing (STT -> LLM -> DB -> Response) consistently < 3 seconds.

## 3. User Journeys

### 3.1 The Zero-Friction Entry (Sam)
Sam is leaving a meeting and records a $15 coffee expense via voice note. The local AI transcribes and extracts the data immediately. Sam receives a confirmation within 3 seconds, including his remaining weekly budget.

### 3.2 The Conversational Inquiry (Quinton)
Quinton asks, "How much did I spend on hardware this month?" The bot queries the local database and uses the LLM to provide a conversational summary and comparison to last month.

### 3.3 The Integrated Dashboard (Noah)
Noah connects his Notion account. Every log he makes in Telegram or WhatsApp is processed locally and then mirrored to his Notion workspace for high-level visualization.

### 3.4 The Shared Reality (Paula)
Paula asks the shared family bot for the grocery balance. The bot aggregates data from all family members and confirms they have $80 remaining for the month.

### 3.5 The Failure Recovery
In a noisy environment, the AI fails to extract an amount. The bot conversationally asks for clarification ("Was it $15 or $50?"), allowing Sam to fix the log with a single word.

## 4. Phased Development Roadmap

### Phase 1: MVP (V1)
*   **Messaging Gateway:** Telegram voice and text note handling routed via native FastAPI webhook endpoint.
*   **Secure Core API (FastAPI):** Application-level encryption and multi-tenant ledger management.
*   **Local AI Pipeline:** Faster-Whisper (STT) + Ollama (JSON Extraction) integrated with FastAPI.
*   **"ASK" Functionality:** Conversational queries for weekly/monthly totals.
*   **Privacy Core:** Local Postgres storage with field-level encryption.
*   **Infrastructure:** Hosted on personal hardware via Podman Compose (Beta limit: first 10 users).

### Phase 2: Growth (V2)
*   **Notion Mirror:** Premium integration to push logs to user Notion databases using the official Python SDK.
*   **Family Groups:** Multi-user sync and shared ledgers (Flat permission model).
*   **Proactive Insights:** Behavioral nudges and spending trend alerts.
*   **Infrastructure Scaling:** Migration to a secure, containerized HA-VPS.

### Phase 3: Vision (V3)
*   **AI Financial Coach:** Deep behavioral learning for budget optimization advice.
*   **Web Dashboard:** Dedicated dashboard for advanced analytics.
*   **Automation:** Optional bank synchronization and tax categorization.

## 5. Functional Requirements

### 5.1 Expense Logging
*   **FR1:** Users can log transactions via natural language text in Telegram and WhatsApp.
*   **FR2:** Users can log transactions via natural language voice notes in Telegram and WhatsApp.
*   **FR3:** System extracts Amount, Category, and Concept from unstructured inputs.
*   **FR4:** System automatically timestamps all entries.
*   **FR5:** Users can specify currencies for individual transactions.

### 5.2 Conversational Queries ("ASK")
*   **FR6:** Users can query total spending for the current week/month via natural language.
*   **FR7:** Users can query total spending for the current month via natural language.
*   **FR8:** Users can query spending history filtered by specific categories.
*   **FR9:** System provides conversational summaries of financial history.

### 5.3 Family & Mirroring (Phase 2)
*   **FR10:** Users can establish shared Family Groups with invited members.
*   **FR11:** All members of a Family Group can view and contribute to a shared ledger.
*   **FR12:** Premium users can synchronize local records to a Notion database via a native Python background task.
*   **FR13:** Users can manually trigger a synchronization to the Notion mirror.

### 5.4 Privacy & Data Rights
*   **FR14:** Users can export transaction history in CSV/JSON format (GDPR Portability).
*   **FR15:** Users can permanently delete their account and data (Right to be Forgotten).
*   **FR16:** Users authenticate/register simply by initiating a chat with the bot.

## 6. Non-Functional Requirements

### 6.1 Performance
*   **Latency:** 95% of logs confirmed within 3 seconds of input reception.
*   **Efficiency:** STT/LLM pipeline must run on consumer-grade local hardware.

### 6.2 Security & Privacy
*   **Encryption:** 100% of transaction descriptions and amounts encrypted at rest.
*   **Local-Only Processing:** Zero transmission of raw audio or transaction data to third-party AI APIs.
*   **Secrets:** All integration tokens (Notion/Bot) stored in encrypted environment variables.

### 6.3 Reliability
*   **Persistence:** Transactional DB writes to ensure zero data loss on system failure.
*   **Backup:** Daily automated encrypted backups to external storage.
*   **Consistency:** Retry mechanisms for Notion mirroring (eventual consistency).
