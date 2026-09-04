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

# Product Requirements Document - Clanomy

**Author:** Tony
**Date:** 2026-08-25 (Updated: 2026-09-01)

## 1. Executive Summary
Clanomy is an "invisible" financial companion designed to solve the chronic problem of financial tracking friction for solo entrepreneurs and families. By living directly within Telegram and WhatsApp (via native API webhooks) and leveraging local AI (Ollama and Whisper) paired with resilient cloud inference (Groq Cloud AI) and deterministic offline fallback engines, Clanomy enables zero-friction, privacy-centric logging of both expenses, earnings/income, and scheduled obligations via natural language audio and text. Users manage their full cash flow through conversational interaction, receiving instant text confirmations, tracking net savings, configuring household default currencies (ISO 4217), settling upcoming bills conversationally, and querying their complete spending and earnings history without ever leaving their primary messaging app.

### Core Differentiator
The elimination of "App Fatigue" through a zero-friction entry model. While traditional finance tools require manual data entry into specialized interfaces, Clanomy allows users to record expenses, income, and bills in seconds via voice notes and messages processed locally and securely, ensuring sensitive financial data is encrypted at rest (AES-256) and never leaks across multi-tenant family workspaces.

## 2. Success Criteria

### 2.1 User Success
*   **The 3-Second Rule:** Users must complete an expense or income entry (from Telegram open to confirmation) in under 3 seconds.
*   **Conversational Clarity:** Users can query spending status, income totals, and net cash flow in natural language with a margin of error < 7%.
*   **Emotional Relief & Empowerment:** Users feel financial awareness and control without the anxiety of opening a traditional banking app, receiving positive feedback when earnings are recorded and proactive reminders before bills fall overdue.
*   **Zero-Friction Settlement:** Users can settle obligations with zero amount inputs (e.g. *"Pagué la visa"*) with automatic user-scoped matching in < 2 seconds.
*   **Frictionless Localization:** Users anywhere in the world can converse in English or Spanish and log unadorned numeric amounts that immediately resolve to their family's configured currency.

### 2.2 Business Success
*   **Initial Traction:** Achieve 50 active users logging ≥3 transactions (expenses or income) per week for 30 consecutive days.
*   **Monetization Validation (SaaS Mode):** Validate willingness to pay for Premium Tiers (Solo Pro at $4.99/mo, Duo Pro at $7.99/mo, Family Pro at $11.99/mo) and 60-day Duo trial via decoupled `BillingService` architecture with active evaluation of PayPal and Telegram bot subscription offers.
*   **Self-Hosting Sovereignty:** Ensure 100% feature and architectural parity for self-hosted community instances (`ENABLE_SUBSCRIPTIONS=false`), delivering unmetered, paywall-free operations.
*   **Global Localization Adoption:** Validate multi-currency and household timezone adoption across international households (e.g. ARS, EUR, MXN, BRL, USD).
*   **Brand Authority:** Establish a reputation in the "Privacy-First" niche leveraging open-source transparency, community funding (Ko-fi), and clean separation between open-core self-hosting and managed SaaS.

### 2.3 Technical Success
*   **Extraction Accuracy:** 90% success rate extracting Type (`income` vs `expense`), Amount, Category, and Concept from natural language.
*   **Zero-Leakage Privacy:** 100% of PII and transaction data remains within encrypted boundaries with strict multi-tenant row-level isolation and zero workspace credential inheritance.
*   **System Latency:** End-to-end processing (STT -> LLM -> DB -> Response) consistently < 3 seconds.
*   **Continuous Reliability & Coverage:** Maintain ≥85% automated test coverage across all core services, verified by automated CI/CD quality gates.
*   **Deterministic Resilience:** 100% fallback reliability via rule-based regex extraction when LLM engines are unavailable.

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

### 3.6 The Income & Cash Flow Milestone (Elena)
Elena receives her monthly paycheck and sends a quick voice note: "Just received my salary of $3,500 from Acme Corp." Clanomy extracts the intent as an income transaction, encrypts the details, and returns an upbeat confirmation with an updated monthly cash flow summary: Total Earned, Total Spent, and Net Savings (+62%).

### 3.7 The Global Multi-Currency Household (Mateo & Lucía)
Mateo and Lucía live in Buenos Aires. Upon running `/start`, the onboarding flow recommends setting their currency: Mateo types `/currency ARS`. From that moment on, whenever Mateo says *"gasté 12500 en el súper"* or Lucía texts *"5000 farmacia"*, Clanomy automatically logs the transactions in ARS without asking them to specify the currency every time. When querying monthly summaries, all totals, averages, and comparisons cleanly reflect ARS.

### 3.8 The Proactive Bill Management & Settlement (Sofía)
Sofía tracks household obligations with Clanomy. At the beginning of the month, she logs: *"El 10 vence la tarjeta Visa 85000 y el 15 internet 18000"*. Clanomy schedules both bills. Mid-month, when Sofía asks *"¿Cómo venimos este mes?"*, Clanomy delivers her spending summary and proactively appends an alert: *"⚠️ Tienes facturas pendientes: Tarjeta Visa ($85,000 ARS) — Vence en 2 días. Si ya la pagaste, solo dime 'Pagué la visa'"*. Sofía replies *"Pagué la visa"*. Clanomy instantly settles the bill, records the expense, and updates her cash flow.

### 3.9 Household Timezone Awareness & Relative Dates (Martín)
Martín lives in Buenos Aires (`America/Argentina/Buenos_Aires`). He configures his household timezone with `/timezone America/Argentina/Buenos_Aires`. At 11:30 PM on a Sunday night, Martín messages *"¿Cuánto gastamos hoy?"*. Because the server operates on UTC, UTC is already Monday morning. However, Clanomy's `DateResolver` computes the query window using `America/Argentina/Buenos_Aires`, capturing all of Martín's Sunday transactions accurately without day-boundary spillover.

### 3.10 Compound Batch Transaction Logging & Rollback (Camila)
Camila returns from running errands and sends a single audio message: *"Gasté 18500 en el supermercado y 8000 en la farmacia"*. Clanomy's extraction engine detects a compound intent, parsing two discrete transactions in a single pass. Both records are atomically written with matching batch linkage. When Camila realizes she made an error and sends `/undo`, Clanomy rolls back both transactions together, acknowledging the batch rollback cleanly.

### 3.11 Decoupled Billing Upgrade & Self-Serve Experience (SaaS User Diego)
Diego is using the hosted SaaS version of Clanomy and approaches his monthly 20-AI operation limit or wishes to add family members. He executes `/upgrade` and receives dynamic deep-link tier options for Solo Pro, Duo Pro, and Family Pro generated by `BillingService`. Diego selects Duo Pro for himself and his partner, receiving an interactive upgrade link to finalize subscription access.

### 3.12 Interactive Inline Currency Configuration (Lucía)
Lucía wants to change her family's currency. Instead of manually typing an ISO code, she types `/currency`. Clanomy responds with a paginated inline keyboard displaying major global currencies with `◀️ Prev` and `Next ▶️` navigation. Lucía taps `ARS` and the bot instantly confirms the update in place via Telegram callback queries.

### 3.13 60-Day Duo Trial Onboarding & Daily Quota Governance (Mateo & Carla)
Mateo creates a new workspace and invites Carla. They receive an automatic 60-day Duo trial with a fair-use quota of 60 daily transactions. Clanomy's internal maintenance job verifies the trial status daily, notifying them on Day 50 before expiration while daily quotas reset automatically each midnight.

## 4. Phased Development Roadmap

### Phase 1: MVP (V1) - [COMPLETED]
*   **Messaging Gateway:** Telegram voice and text note handling routed via native FastAPI webhook endpoint.
*   **Secure Core API (FastAPI):** Application-level encryption and multi-tenant ledger management.
*   **Local AI Pipeline:** Faster-Whisper (STT) + Ollama (JSON Extraction) integrated with FastAPI.
*   **"ASK" Functionality:** Conversational queries for weekly/monthly totals.
*   **Privacy Core:** Local Postgres storage with field-level encryption.
*   **Infrastructure:** Hosted on personal hardware via Podman Compose (Beta limit: first 10 users).

### Phase 2: Growth & Production Hardening (V2) - [COMPLETED]
*   **Notion Mirror:** Premium integration to push logs (both expenses and income) to user Notion databases using the official Python SDK.
*   **Family Groups:** Multi-user sync and shared ledgers (Flat permission model).
*   **Income & Net Cash Flow Tracking:** Dual-intent transaction logging, earnings summaries, and net balance calculation (Income − Expenses).
*   **Multi-Currency & Bilingual Localization:** Household default currency (`/currency`), dynamic currency resolution, and full Spanish/English support.
*   **Household Timezone Localization:** Per-family timezone setting (`/timezone`), database migration `0008`, and timezone-aware dynamic date resolution (`DateResolver`).
*   **Compound Batch Transaction Extraction:** Multi-transaction parsing from single voice/text inputs and atomic multi-item batch undo (`BatchTracker`).
*   **Scheduled Obligations & Zero-Amount Settlement:** `ScheduledBill` tracking, due dates, conversational settlement shortcuts, and proactive status alerts.
*   **Enterprise Security Hardening:** Remediation of SEC-01 through SEC-06 (clean workspace isolation on leave, HTML entity escaping, prompt injection defenses, per-user concurrency locking, bounded queries, Cloudflare Origin Shielding).
*   **Universal AI & STT:** Universal multi-provider support (Groq, OpenAI, Ollama).

### Phase 3: Platform Evolution & Core Alignment (V3) - [COMPLETED]
*   **Billing Decoupling & Modernization:** Excised hardcoded Lemon Squeezy dependencies (migration `0011_remove_lemonsqueezy_fields.py`), abstracted checkout into pluggable `BillingService`, and initiated evaluation of PayPal and Telegram bot subscription offers.
*   **Three-Tier Pricing & Duo Trial:** Introduced Solo Pro ($4.99/mo), Duo Pro ($7.99/mo), and Family Pro ($11.99/mo), alongside an automatic 60-Day Duo Trial.
*   **Daily Fair-Use Governance:** Added `Family.daily_tx_count` (migration `0010_add_family_daily_tx_count.py`) and automated `/api/internal/jobs/trial-lifecycle` cron maintenance endpoint.
*   **Native Google Gemini Multimodal Provider:** Direct audio ingestion and schema translation via `gemini-2.5-flash-lite`, eliminating external Whisper overhead.
*   **Interactive Telegram UX:** Paginated inline keyboards for `/currency` and callback query webhook processing.
*   **Landing Page Web Application & Evaluation Suite:** Public bilingual landing page at `/` and offline extraction evaluation harness (`/simulate/message`).

### Phase 4: Vision (V4) - [UPCOMING]
*   **AI Financial Coach:** Deep behavioral learning for budget optimization advice and cash-flow forecasting.
*   **Web Dashboard:** Dedicated optional self-hosted dashboard for advanced analytics and chart visualizations.
*   **Automation:** Optional read-only bank synchronization and automated tax categorization.

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

### 5.5 Income & Net Cash Flow Tracking (Phase 2)
*   **FR17:** Users can log earnings and income via natural language text and voice notes in Telegram and WhatsApp.
*   **FR18:** System classifies transaction intent (`expense` vs `income`) and extracts Amount, Category, Concept/Source, and Currency.
*   **FR19:** Users can query total earnings, net cash flow (`Total Income − Total Expenses`), and savings rates for specific time frames (weekly, monthly, custom).
*   **FR20:** In family groups, income can be attributed to specific members while aggregating into the family's collective cash flow.
*   **FR21:** Income records are synchronized with Notion mirrors with type discrimination and included in data exports (CSV/JSON).

### 5.6 Multi-Currency & Bilingual Localization
*   **FR22:** Users can configure a household default currency via `/currency <ISO>` command or natural language (e.g., *"Set default currency to ARS"* / *"Cambiar moneda a EUR"*).
*   **FR23:** System dynamically resolves the household default currency for any transaction logged without an explicit currency symbol or code.
*   **FR24:** System processes inputs and generates conversational feedback and summaries bilingually in English and Spanish.

### 5.7 Scheduled Obligations & Proactive Settlement
*   **FR25:** Users can schedule upcoming bills and recurring financial obligations with amounts, concepts, categories, and due dates.
*   **FR26:** Users can settle scheduled bills conversationally with zero amounts (e.g. *"Pagué la visa"*), resolving bills via user-scoped precedence with family fallback.
*   **FR27:** Monthly balance and spending status queries proactively alert users to pending bills whose due dates are approaching or overdue.

### 5.8 Enterprise Security & Infrastructure Isolation
*   **FR28:** When a user leaves a family workspace (`/leavefamily`), the system provisions a fresh workspace with guaranteed zero credential or data inheritance.
*   **FR29:** Outbound messaging handles entity formatting exceptions by automatically retrying in safe plain-text mode.
*   **FR30:** AI prompt ingestion sanitizes user text and encapsulates inputs within strict `<user_input>` XML tags to defend against prompt injection.
*   **FR31:** Concurrent operations per user are serialized via per-user locks to ensure transactional determinism.
*   **FR32:** Financial query decryption enforces an in-memory record bounding limit to prevent resource exhaustion attacks.
*   **FR33:** Incoming webhooks are protected by Cloudflare Origin Shield verification, secret tokens, and security headers.

### 5.9 Hybrid AI & Resilient Fallback
*   **FR34:** System supports hybrid AI inference, allowing seamless routing between local Ollama/Faster-Whisper and Groq Cloud AI.
*   **FR35:** System provides a deterministic, rule-based regex extraction and classification engine to guarantee zero-downtime operation when AI inference fails.

### 5.10 Pre-Built Fast-Path Commands & Hybrid Quota Model
*   **FR36:** System provides pre-built deterministic slash commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`) that execute purely in Python/SQL in <50ms with zero AI token consumption.
*   **FR37:** The `/month` command generates a comprehensive household overview with full member-by-member segregation (individual incomes, expenses, net savings, and top categories), maintaining strict multi-currency isolation.
*   **FR38:** The `/me` command isolates the caller's personal income, expenses, net savings, and category distribution regardless of household size.
*   **FR39:** The Free Tier enforces a hard monthly limit of 20 AI operations for natural language logging and queries, while pre-built commands remain 100% free and unlimited. Natural language queries in free tier append a contextual shortcut pro-tip.

### 5.11 Hybrid Open-Core & Self-Hosting Parity
*   **FR40:** System guarantees functional and architectural parity between Self-Hosted mode (`ENABLE_SUBSCRIPTIONS=false`) and Multi-Tenant SaaS mode (`ENABLE_SUBSCRIPTIONS=true`). Self-hosted deployments run completely unlocked with zero paywalls, unlimited transactions, and bot allowlisting (`ALLOWED_TELEGRAM_USERS`).
*   **FR41:** System provides a unified pluggable LLM provider abstraction (`BaseLLMProvider`) enabling instant switching between offline local Ollama and cloud OpenAI-compatible APIs (e.g. Groq, OpenAI) via standard environment variables.

### 5.12 Household Timezone Support & Dynamic Temporal Resolution
*   **FR42:** Users can configure and view their household's IANA timezone via `/timezone` and `/settimezone <IANA_TZ>` (e.g., `America/Argentina/Buenos_Aires`, `UTC`, `Europe/Madrid`), validating against standard timezone databases.
*   **FR43:** System dynamically resolves natural language relative date queries (*"today"*, *"yesterday"*, *"last week"*, *"this month"*, *"el lunes pasado"*) and scheduled bill due dates strictly in the family's configured timezone before database UTC projection.

### 5.13 Compound Batch Extraction & Atomic Multi-Transaction Rollback
*   **FR44:** System extracts multiple discrete transactions (expenses or incomes) from a single compound voice note or text message, returning a validated `BatchTransactionExtractionResult` schema.
*   **FR45:** System tracks transaction batches via `BatchTracker` and rolls back all transactions within the caller's most recent batch when `/undo` is triggered.

### 5.14 Decoupled Billing Engine & Payment Abstraction (SaaS Mode)
*   **FR46:** When running with `ENABLE_SUBSCRIPTIONS=true`, the system presents plan options and generates interactive upgrade deep links (`https://t.me/<bot>?start=upgrade_<plan>`) via pluggable `BillingService`. Hardcoded Lemon Squeezy dependencies have been decoupled and stripped from the database schema via Alembic migration `0011_remove_lemonsqueezy_fields.py`.
*   **FR47:** System provides payment processor abstraction supporting active evaluation of PayPal and direct Telegram Bot Subscription Offers with cryptographic verification and automated family tier activation.
*   **FR48:** System provides self-service billing management and upgrade command menus (`/upgrade`, `/upgrade duo`, `/upgrade annual`) with role-aware admin checks and graduation workflows for family members.

### 5.15 Universal AI & Speech-to-Text Resilience
*   **FR49:** System supports multiple Speech-to-Text backends via `WhisperProvider` (`local` Faster-Whisper, `groq` Whisper Large v3, and `openai` Whisper-1) with automatic audio validation and secure temporary file lifecycle.
*   **FR50:** System supports structured OpenAI-compatible LLM providers (Groq, OpenAI, Google Gemini) featuring static prompt caching optimizations and exponential backoff retry with jitter on upstream 429/5xx errors.

### 5.16 Native Google Gemini Multimodal AI Provider
*   **FR51:** System provides a native `GeminiProvider` utilizing Google GenAI REST/SDK APIs with native multimodal audio transcription (bypassing external Whisper containers), automatic token usage logging, and structured JSON translation with resilient fallback.
*   **FR52:** System automatically detects Gemini API keys starting with `AIzaSy` and auto-configures `gemini-2.5-flash-lite` as the primary extraction and voice transcription model with zero local GPU/RAM overhead.

### 5.17 Interactive Telegram UX & Pagination
*   **FR53:** System provides an interactive, paginated inline keyboard for `/currency`, allowing users to page through and select currencies directly in Telegram via `callback_query` webhook updates.
*   **FR54:** Telegram gateway supports interactive callback queries (`answer_callback_query` and `edit_message_text`) alongside standard text and voice messages.

### 5.18 Three-Tier Pricing Governance & Daily Fair-Use Quotas
*   **FR55:** System centralizes subscription plans into a structured registry (`SubscriptionTier`): Solo Pro ($4.99/mo, $49.99/yr, 1 user), Duo Pro ($7.99/mo, $79.99/yr, 2 users), and Family Pro ($11.99/mo, $119.99/yr, 5 users).
*   **FR56:** System automatically grants new SaaS workspaces a 60-Day Duo Trial supporting up to 2 members, Notion database syncing, and a fair-use quota of 60 daily extractions.
*   **FR57:** System tracks daily transactions via `Family.daily_tx_count` (migration `0010_add_family_daily_tx_count.py`) and enforces tier-specific daily limits (Solo: 60, Duo: 120, Family: 300, Trial: 60) to protect against runaway cloud API costs.
*   **FR58:** System provides an authenticated maintenance cron endpoint (`/api/internal/jobs/trial-lifecycle`) protected by `CRON_SECRET` that resets daily quotas at midnight and dispatches Day 50 alerts and Day 60 transition notices.

### 5.19 Message Simulation & Public Web Showcase
*   **FR59:** System provides an authorized `/simulate/message` endpoint protected by `SIMULATION_SECRET` enabling offline and automated evaluation of LLM extraction models without requiring live Telegram webhooks.
*   **FR60:** System serves a responsive bilingual (EN/ES) static landing page directly from FastAPI on `/` showcasing features, live interactive previews, and pricing.

## 6. Non-Functional Requirements

### 6.1 Performance
*   **Latency:** 95% of logs confirmed within 3 seconds of input reception.
*   **Efficiency:** STT/LLM pipeline must run on consumer-grade local hardware or lightweight cloud inference (<150MB container RAM with Gemini).
*   **NFR17 (Interactive UI Callback Latency):** Telegram `callback_query` acknowledgment and in-place message updates must execute in < 1.0 second.

### 6.2 Security & Privacy
*   **Encryption:** 100% of transaction descriptions, amounts, and scheduled obligations encrypted at rest using AES-256 (Fernet).
*   **Local-First / Private Processing:** Zero persistent storage of raw audio or unencrypted financial data on third-party infrastructure.
*   **Secrets:** All integration tokens (Notion/Bot/Groq/Gemini/JobSecret) stored in encrypted environment variables.
*   **NFR9 (Multi-Currency Segregation):** Summaries and aggregations must cleanly segregate distinct currencies to prevent corrupt exchange-rate mixing.
*   **NFR10 (Prompt Boundary Defense):** Untrusted user inputs must be stripped of markdown delimiters and fenced inside boundary tags.
*   **NFR11 (Transactional Concurrency):** Rapid sequential mutations (`/undo`, corrections, rapid logs) must execute with deterministic ordering.
*   **NFR12 (Origin Verification):** All webhook requests must prove origin authenticity before any payload processing occurs.
*   **NFR14 (Timezone Boundary Consistency):** All financial boundary queries (start-of-day, start-of-month) must resolve against the household's configured timezone before database UTC projection to prevent time-shift errors.
*   **NFR15 (Cryptographic Webhook Verification):** 100% of external billing webhooks and cron maintenance triggers must cryptographically verify signatures or secrets before reading or acting upon request payloads.
*   **NFR16 (Prompt Caching Invariance):** System prompts and tool definitions must maintain prefix stability to optimize upstream LLM prompt cache hit rates and reduce latency/cost.

### 6.3 Reliability & Quality
*   **Persistence:** Transactional DB writes to ensure zero data loss on system failure.
*   **Backup:** Daily automated encrypted backups to external storage.
*   **Consistency:** Retry mechanisms for Notion mirroring (eventual consistency).
*   **NFR13 (Zero-Downtime Fallback):** Offline regex extraction must achieve 100% fallback reliability for standard financial formats during AI outages.
*   **Quality Gate:** Codebase must maintain ≥85% automated test coverage verified via CI.


