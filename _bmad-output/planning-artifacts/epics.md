---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - c:\Users\cresp\Documents\Projectos\FamFin-AI\_bmad-output\planning-artifacts\prd.md
  - c:\Users\cresp\Documents\Projectos\FamFin-AI\_bmad-output\planning-artifacts\architecture.md
workflowType: 'epics-and-stories'
status: 'complete'
completedAt: '2026-09-01'
---

# Clanomy - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Clanomy, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Users can log transactions via natural language text in Telegram and WhatsApp.
FR2: Users can log transactions via natural language voice notes in Telegram and WhatsApp.
FR3: System extracts Amount, Category, and Concept from unstructured inputs.
FR4: System automatically timestamps all entries.
FR5: Users can specify currencies for individual transactions.
FR6: Users can query total spending for the current week via natural language.
FR7: Users can query total spending for the current month via natural language.
FR8: Users can query spending history filtered by specific categories.
FR9: System provides conversational summaries of financial history.
FR10: Users can establish shared Family Groups with invited members. (Phase 2)
FR11: All members of a Family Group can view and contribute to a shared ledger. (Phase 2)
FR12: Premium users can synchronize local records to a Notion database via a native Python background task. (Phase 2)
FR13: Users can manually trigger a synchronization to the Notion mirror via a chat command. (Phase 2)
FR14: Users can export transaction history in CSV/JSON format (GDPR Portability).
FR15: Users can permanently delete their account and data (Right to be Forgotten).
FR16: Users authenticate/register simply by initiating a chat with the bot.
FR17: Users can log earnings and income via natural language text and voice notes in Telegram and WhatsApp.
FR18: System classifies transaction intent (`expense` vs `income`) and extracts Amount, Category, Concept/Source, and Currency.
FR19: Users can query total earnings, net cash flow (`Total Income − Total Expenses`), and savings rates for specific time frames (weekly, monthly, custom).
FR20: In family groups, income can be attributed to specific members while aggregating into the family's collective cash flow.
FR21: Income records are synchronized with Notion mirrors with type discrimination and included in data exports (CSV/JSON).
FR22: Users can configure a household default currency via `/currency <ISO>` command or natural language.
FR23: Dynamic currency resolution defaults unspecified transactions to the household configured currency.
FR24: System processes inputs and generates conversational summaries bilingually in English and Spanish.
FR25: Users can schedule upcoming bills and recurring financial obligations with amounts, concepts, categories, and due dates.
FR26: Users can settle scheduled bills conversationally with zero amounts using user-scoped precedence with family fallback.
FR27: Monthly status queries proactively alert users to pending bills whose due dates are approaching or overdue.
FR28: Users leaving a family workspace are guaranteed zero-data inheritance and fresh workspace provisioning.
FR29: Outbound Telegram delivery handles formatting errors with automatic plain-text fallbacks.
FR30: AI prompt boundaries are hardened against injection using XML tag fencing.
FR31: Financial mutations serialize per-user concurrency to guarantee transactional determinism.
FR32: In-memory query decryption bounds record size to prevent resource exhaustion.
FR33: Cloudflare Origin Shield and security headers protect webhook ingress.
FR34: System supports hybrid AI inference (local Ollama/Whisper + Groq cloud inference).
FR35: Deterministic regex fallback provides zero-downtime classification and extraction when AI inference is unavailable.
FR36: Pre-built deterministic slash commands execute purely in Python/SQL in <50ms with zero AI token consumption.
FR37: `/month` generates household overview with member-by-member segregation and multi-currency isolation.
FR38: `/me` isolates caller's personal income, expenses, net savings, and category distribution.
FR39: Free tier enforces 20 monthly AI operations for natural text, while pre-built commands remain 100% free and unlimited.
FR40: Functional and architectural parity between self-hosted mode (`ENABLE_SUBSCRIPTIONS=false`) and SaaS mode (`ENABLE_SUBSCRIPTIONS=true`).
FR41: Unified pluggable LLM provider abstraction (`BaseLLMProvider`) enabling instant switching between offline and cloud inference.
FR42: Users can configure and view household timezone via `/timezone` and `/settimezone <IANA_TZ>`.
FR43: Dynamic timezone-aware relative date query resolution and scheduled bill due dates strictly in family's local timezone.
FR44: Compound batch extraction parsing multiple discrete transactions from single conversational inputs into `BatchTransactionExtractionResult`.
FR45: Compound transaction rollback via `BatchTracker` enabling atomic multi-item `/undo`.
FR46: Pluggable billing abstraction layer (`BillingService`) generating interactive deep-link upgrade options (`https://t.me/<bot>?start=upgrade_<plan>`).
FR47: Decoupled database schema (Alembic migration `0011_remove_lemonsqueezy_fields.py`) and processor evaluation (PayPal & Telegram bot offers).
FR48: Self-service billing commands (`/upgrade`, `/upgrade duo`, `/upgrade annual`) with role-aware admin verification and family graduation logic.
FR49: Universal Speech-to-Text multi-provider engine supporting local Faster-Whisper, Groq Whisper API, and OpenAI Whisper.
FR50: Multi-provider LLM inference (Groq, OpenAI, Google Gemini, Ollama) featuring static prompt caching and exponential backoff retry with jitter.
FR51: Native Google Gemini Multimodal Provider (`GeminiProvider`) with direct audio voice transcription, token usage logging, and schema translation.
FR52: Automatic detection of Gemini API keys (`AIzaSy`) with auto-configuration of `gemini-2.5-flash-lite`.
FR53: Interactive Telegram Currency Selection with paginated inline keyboards (`◀️ Prev`, `Next ▶️`) via `callback_query` webhook ingress.
FR54: Three-tier subscription architecture (`SubscriptionTier`) supporting Solo Pro ($4.99/mo), Duo Pro ($7.99/mo), and Family Pro ($11.99/mo) with annual savings.
FR55: 60-day Duo Trial experience providing full Pro features for up to 2 members.
FR56: Daily fair-use quota tracking via `Family.daily_tx_count` (migration `0010_add_family_daily_tx_count.py`) and tier limits enforcement.
FR57: Internal scheduled maintenance cron job (`/api/internal/jobs/trial-lifecycle`) protected by `CRON_SECRET` for daily quota reset and trial alerts.
FR58: Authorized message simulation and evaluation route (`/simulate/message`) protected by `SIMULATION_SECRET`.
FR59: Public bilingual landing page web app mounted at `/` in FastAPI.

### NonFunctional Requirements

NFR1: 95% of logs confirmed within 3 seconds of input reception. (Latency)
NFR2: STT/LLM pipeline must run on consumer-grade local hardware. (Efficiency)
NFR3: 100% of transaction descriptions and amounts encrypted at rest. (Encryption)
NFR4: Zero transmission of raw audio or transaction data to third-party AI APIs. (Local-Only)
NFR5: All integration tokens (Notion/Bot) stored in encrypted environment variables. (Secrets)
NFR6: Transactional DB writes to ensure zero data loss on system failure. (Persistence)
NFR7: Daily automated encrypted backups to external storage. (Backup)
NFR8: Retry mechanisms for Notion mirroring (eventual consistency). (Consistency)
NFR9: Financial aggregations segregate distinct currencies cleanly without exchange-rate corruption. (Multi-Currency Segregation)
NFR10: Untrusted user inputs stripped of markdown fences and isolated in boundary tags. (Prompt Injection Defense)
NFR11: Sequential mutations per user execute with deterministic serial ordering. (Transactional Concurrency)
NFR12: Ingress webhooks verify origin authenticity before payload processing. (Origin Verification)
NFR13: Offline regex engine achieves 100% fallback reliability during AI outages. (Zero-Downtime Fallback)
NFR14: Financial boundary aggregations resolve against configured household timezone before UTC query projection. (Timezone Boundary Consistency)
NFR15: Inbound billing webhooks cryptographically verify HMAC-SHA256 signatures before processing payloads. (Cryptographic Webhook Verification)
NFR16: System prompts and tool definitions maintain prefix invariance to maximize upstream LLM prompt caching. (Prompt Caching Invariance)
NFR17: Interactive UI callback acknowledgment and in-place message update completed in < 1.0s. (Callback Query Latency)

### Additional Requirements

- **Starter Template:** Initialize repository with Podman Compose running FastAPI and PostgreSQL using `pip install fastapi[all] sqlmodel cryptography ollama faster-whisper python-telegram-bot`.
- **Encryption:** Implement application-level AES-256 encryption using the `cryptography` library (Fernet) inside Python.
- **Inference:** Orchestrate Faster-Whisper (STT) and Ollama (LLM) inside the FastAPI app in a non-blocking `BackgroundTasks` pipeline.
- **Monitoring:** Implement a "3s Audit" instrumentation to log execution time of the AI services.
- **Tenancy:** Enforce `family_id` scoping on all database queries and models.
- **Security:** Verify standardized authentication tokens for all incoming webhook messages from Telegram.

### UX Design Requirements

(No separate UX Design specification provided for this bot-first MVP)

### FR Coverage Map

FR1: Epic 2 - Users can log transactions via natural language text.
FR2: Epic 2 - Users can log transactions via natural language voice notes.
FR3: Epic 2 - System extracts Amount, Category, and Concept from unstructured inputs.
FR4: Epic 2 - System automatically timestamps all entries.
FR5: Epic 2 - Users can specify currencies for individual transactions.
FR6: Epic 3 - Users can query total spending for the current week via natural language.
FR7: Epic 3 - Users can query total spending for the current month via natural language.
FR8: Epic 3 - Users can query spending history filtered by specific categories.
FR9: Epic 3 - System provides conversational summaries of financial history.
FR10: Epic 5 - Users can establish shared Family Groups with invited members.
FR11: Epic 5 - All members of a Family Group can view and contribute to a shared ledger.
FR12: Epic 6 - Premium users can synchronize local records to a Notion database.
FR13: Epic 6 - Users can manually trigger a synchronization to the Notion mirror.
FR14: Epic 4 - Users can export transaction history in CSV/JSON format.
FR15: Epic 4 - Users can permanently delete their account and data.
FR16: Epic 1 - Users authenticate/register simply by initiating a chat with the bot.
FR17: Epic 8 - Users can log earnings and income via natural language text and voice notes.
FR18: Epic 8 - System classifies transaction intent (`expense` vs `income`) and extracts data.
FR19: Epic 8 - Users can query total earnings, net cash flow, and savings rates.
FR20: Epic 8 - In family groups, income is attributed to specific members and aggregated.
FR21: Epic 8 - Income records are synchronized with Notion and included in data exports.
FR22: Epic 9 - Users can configure a household default currency via `/currency` command or natural language.
FR23: Epic 9 - Dynamic currency resolution defaults unspecified transactions to the household currency.
FR24: Epic 9 - System processes inputs and generates conversational summaries bilingually in English and Spanish.
FR25: Epic 10 - Users can schedule upcoming bills and recurring financial obligations with due dates.
FR26: Epic 10 - Users can settle scheduled bills conversationally with zero amounts using user-scoped precedence.
FR27: Epic 10 - Monthly status queries proactively alert users to pending bills whose due dates are approaching.
FR28: Epic 11 - Users leaving a family workspace are guaranteed zero-data inheritance and fresh workspace provisioning.
FR29: Epic 11 - Outbound Telegram delivery handles formatting errors with automatic plain-text fallbacks.
FR30: Epic 11 - AI prompt boundaries are hardened against injection using XML tag fencing.
FR31: Epic 11 - Financial mutations serialize per-user concurrency to guarantee transactional determinism.
FR32: Epic 11 - In-memory query decryption bounds record size to prevent resource exhaustion.
FR33: Epic 11 - Cloudflare Origin Shield and security headers protect webhook ingress.
FR34: Epic 12 - System supports hybrid AI inference (local Ollama/Whisper + Groq cloud inference).
FR35: Epic 12 - Deterministic regex fallback provides zero-downtime classification and extraction.
FR36: Epic 14 - Pre-built deterministic slash commands execute purely in Python/SQL in <50ms with zero AI token consumption.
FR37: Epic 14 - `/month` generates household overview with member-by-member segregation and multi-currency isolation.
FR38: Epic 14 - `/me` isolates caller's personal income, expenses, net savings, and category distribution.
FR39: Epic 14 - Free tier enforces 20 monthly AI operations for natural text, while pre-built commands remain 100% free and unlimited.
FR40: Epic 14 - Functional and architectural parity between self-hosted mode (`ENABLE_SUBSCRIPTIONS=false`) and SaaS mode (`ENABLE_SUBSCRIPTIONS=true`).
FR41: Epic 14 - Unified pluggable LLM provider abstraction (`BaseLLMProvider`) enabling instant switching between offline and cloud inference.
FR42: Epic 15 - Users can configure and view household timezone via `/timezone` and `/settimezone <IANA_TZ>`.
FR43: Epic 15 - Dynamic timezone-aware relative date query resolution and scheduled bill due dates strictly in family's local timezone.
FR44: Epic 16 - Compound batch extraction parsing multiple discrete transactions from single conversational inputs into `BatchTransactionExtractionResult`.
FR45: Epic 16 - Compound transaction rollback via `BatchTracker` enabling atomic multi-item `/undo`.
FR46: Epic 17 - Lemon Squeezy Merchant of Record hosted checkout generation with custom passthrough metadata (`family_id`, `chat_id`).
FR47: Epic 17 - Lemon Squeezy HMAC-SHA256 signed webhook processing for real-time subscription lifecycle management.
FR48: Epic 17 - Self-service customer billing portal URL generation for subscription management and invoice downloads.
FR49: Epic 18 - Universal Speech-to-Text multi-provider engine supporting local Faster-Whisper, Groq Whisper API, and OpenAI Whisper.
FR50: Epic 18 - Multi-provider LLM inference (Groq, OpenAI, Google Gemini, Ollama) featuring static prompt caching and exponential backoff retry with jitter.

## Epic List

### Epic 1: Privacy-First Foundation
Establish the secure shell of the application. Users can register by simply starting a chat, and all subsequent data is protected by AES-256 encryption.
**FRs covered:** FR16, NFR3, NFR5, NFR6.

### Epic 2: Zero-Friction Expense Logging
Build the core 3-second pipeline. Users can record voice or text notes and get structured expense logs confirmed instantly.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, NFR1, NFR2, NFR4.

### Epic 3: Conversational Financial Queries (ASK)
Implement the query engine. Users can ask natural language questions about their spending history and receive summaries.
**FRs covered:** FR6, FR7, FR8, FR9.

### Epic 4: Data Portability & Rights
Ensure GDPR compliance and user control. Users can export their data or delete their entire account.
**FRs covered:** FR14, FR15.

### Epic 5: Family Shared Ledgers (Phase 2)
Enable multi-user collaboration. Families can create shared groups to track collective expenses.
**FRs covered:** FR10, FR11.

### Epic 6: Premium Notion Mirroring (Phase 2)
Integrate with external tools. Premium users can sync their local ledger to their Notion databases.
**FRs covered:** FR12, FR13, NFR8.

### Epic 7: Monetization & Subscriptions (Historical Prototype)
Initial subscription prototype using Telegram Stars (`XTR`). (Subsequently migrated to Lemon Squeezy Merchant of Record in Epic 17).
**FRs covered:** FR1, FR10, FR12 (Monetization gating for features).

### Epic 8: Family Income & Net Cash Flow Tracking
Enable dual-intent transaction processing, income voice/text logging, net cash flow calculations, savings rates, and income synchronization across Notion and data exports.
**FRs covered:** FR17, FR18, FR19, FR20, FR21, NFR1, NFR3, NFR4.

### Epic 9: Multi-Currency & Bilingual Localization
Enable per-family default currency configuration (`/currency <ISO>`), dynamic extraction defaults, multi-currency segregation in queries, and complete English/Spanish bilingual interaction.
**FRs covered:** FR22, FR23, FR24, NFR9.

### Epic 10: Scheduled Bills, Commitments & Settlement
Enable tracking of scheduled obligations with due dates, batch bill extraction, zero-amount conversational bill settlement (*"Pagué la visa"*), and proactive overdue bill alerts in status queries.
**FRs covered:** FR25, FR26, FR27, NFR1, NFR3.

### Epic 11: Enterprise Security Hardening & Infrastructure Isolation
Implement forensic audit remediations (SEC-01 through SEC-06): clean family isolation on `/leavefamily`, Telegram HTML escaping & plain-text retry, prompt injection defense, per-user concurrency locking, bounded query decryption, and Cloudflare Origin Shielding.
**FRs covered:** FR28, FR29, FR30, FR31, FR32, FR33, NFR10, NFR11, NFR12.

### Epic 12: Modular Architecture Refactoring & Resilient AI Ingress
Decompose monolithic services into decoupled domain packages (`extraction/`, `query/`, `handlers/`) with backwards-compatible shims, integrate Groq Cloud AI, and build offline regex fallback engines.
**FRs covered:** FR34, FR35, NFR2, NFR13.

### Epic 13: CI/CD Quality Automation & Open-Source Readiness
Automate quality gates with GitHub Actions, PR guardrails, 85%+ code coverage enforcement, startup Alembic migrations, and community self-hosting and funding frameworks.
**FRs covered:** NFR6, NFR12, Quality Gates.

### Epic 14: Pre-Built Fast-Path Commands & Hybrid Quota Model
Provide instant (<40ms) deterministic slash commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`) running directly in Python/SQL with zero AI token cost, full multi-currency segregation, member-by-member family transparency, personal cash-flow isolation, and a 20-operation/month Free Tier AI quota model.
**FRs covered:** FR36, FR37, FR38, FR39, FR40, FR41, NFR1, NFR9.

### Epic 15: Household Timezone Support & Dynamic Temporal Resolution
Enable per-family IANA timezone configuration (`/timezone`), database migration `0008`, and dynamic localized date resolution for relative natural language queries and scheduled obligations.
**FRs covered:** FR42, FR43, NFR14.

### Epic 16: Compound Batch Transaction Extraction & Multi-Item Undo
Support extracting multiple discrete transactions from single conversational voice/text messages, validating via `BatchTransactionExtractionResult`, and rolling back entire batches atomically with `BatchTracker`.
**FRs covered:** FR44, FR45, NFR1, NFR11.

### Epic 17: Merchant of Record (Lemon Squeezy) Subscription Engine & Cloud Billing Integration
Replace prototype Telegram Stars with Lemon Squeezy MoR hosted checkout, HMAC-SHA256 signed webhook processing, customer portal URLs, database migration `0009`, and domestic US ACH payouts direct to DolarApp USDc accounts.
**FRs covered:** FR46, FR47, FR48, NFR15.

### Epic 18: Multi-Provider AI Inference Resilience, Prompt Caching & Speech-to-Text Fallbacks
Support unified multi-provider STT (`WhisperService` across Faster-Whisper, Groq Whisper API, and OpenAI Whisper) and LLM inference (Groq, OpenAI, Google Gemini, Ollama) with static prompt caching and exponential backoff retry with jitter.
**FRs covered:** FR49, FR50, NFR1, NFR2, NFR16.


---

## Epic 1: Privacy-First Foundation

Establish the secure shell of the application. Users can register by simply starting a chat, and all subsequent data is protected by AES-256 encryption.

### Story 1.1: Project Initialization & Containerized Environment

As a Developer,
I want to initialize the repository with FastAPI and Podman Compose,
So that I have a consistent, "Cloud-Ready" development environment.

**Acceptance Criteria:**

**Given** a clean directory
**When** I run `podman-compose up`
**Then** a FastAPI server and a PostgreSQL database are running and connected.
**And** all core dependencies (`sqlmodel`, `cryptography`, `ollama`) are installed.

### Story 1.2: Application-Level AES-256 Encryption Service

As a Security-Conscious User,
I want my financial data to be encrypted before it hits the database,
So that my privacy is guaranteed even if the database is compromised.

**Acceptance Criteria:**

**Given** a plaintext string (e.g., "$15 Coffee")
**When** I pass it through the `EncryptionService`
**Then** it returns a base64-encoded ciphertext.
**And** the service can decrypt the ciphertext back to the original string using the master key in `.env`.

### Story 1.3: Multi-Tenant Database Schema (SQLModel)

As a Developer,
I want a database schema that supports families and encrypted transactions,
So that I can store data with strict isolation and security.

**Acceptance Criteria:**

**Given** the `db/models.py` file
**When** I define the `User`, `Family`, and `Transaction` models
**Then** the `Transaction` model includes a mandatory `family_id` foreign key.
**And** sensitive fields (Amount, Concept) are stored as BLOB/String to support ciphertext.

### Story 1.4: Generic Messaging API & Registration Flow

As a User,
I want to register and authenticate simply by sending a message on Telegram or WhatsApp,
So that I have a zero-friction onboarding experience.

**Acceptance Criteria:**

**Given** a request from Telegram with a standardized update payload and secret token
**When** the request hits the `/api/v1/telegram/webhook` endpoint
**Then** the system verifies the secret token.
**And** creates or retrieves the `User` and `Family` record in the database atomically.
**And** returns a standardized welcome payload via direct Telegram API if it is the user's first interaction.

## Epic 2: Zero-Friction Expense Logging

Build the core 3-second pipeline. Users can record voice or text notes and get structured expense logs confirmed instantly.

### Story 2.1: Faster-Whisper Transcription Service

As a User,
I want to log expenses via voice notes,
So that I can log expenses without typing.

**Acceptance Criteria:**

**Given** an audio payload (Telegram `file_id`) fetched directly from Telegram API
**When** the FastAPI backend processes the media through `WhisperService`
**Then** it transcribes the speech to text with high accuracy.
**And** execution time is logged for the "3s Audit."

### Story 2.2: Ollama JSON Extraction Service

As a Developer,
I want to extract structured data from natural language,
So that I can store precise financial records.

**Acceptance Criteria:**

**Given** a transaction string (e.g., "15 dollars for coffee at Starbucks")
**When** I pass it to the `ExtractionService` (Ollama)
**Then** it returns a valid JSON object with `amount: 15.0`, `category: "Food/Drink"`, and `concept: "Starbucks"`.
**And** it handles multiple currencies (e.g., "10 euros").

### Story 2.3: The "3-Second Rule" Orchestrator

As a User,
I want to receive an immediate confirmation of my log,
So that I don't have to wait for the bot to finish processing.

**Acceptance Criteria:**

**Given** an incoming message from Telegram via webhook
**When** the payload is received by the FastAPI `/api/v1/telegram/webhook` endpoint
**Then** the system triggers the AI pipeline in a `BackgroundTasks` loop.
**And** immediately returns a `200 OK` to Telegram to acknowledge receipt.
**And** pushes the final transaction confirmation (or error/clarification request) back to the user via a direct `httpx` call to the Telegram API once processing completes.

### Story 2.4: Transaction Persistence with Encryption

As a User,
I want my logs to be saved permanently and securely,
So that I can review my spending later.

**Acceptance Criteria:**

**Given** a validated JSON extraction
**When** the `ai_orchestrator` saves the record
**Then** the `amount` and `concept` are encrypted before being written to Postgres.
**And** the record is associated with the user's `family_id`.

## Epic 3: Conversational Financial Queries (ASK)

Implement the query engine. Users can ask natural language questions about their spending history and receive summaries.

### Story 3.1: Natural Language Query Processor (RAG-lite)

As a User,
I want to ask questions in plain English (e.g., "What did I spend yesterday?"),
So that I don't have to navigate complex menus.

**Acceptance Criteria:**

**Given** a user query
**When** it contains temporal or category keywords
**Then** the `QueryService` uses Ollama to translate the intent into a database query.
**And** the system retrieves the relevant (decrypted) records.

### Story 3.2: Time-Based Aggregations (Weekly/Monthly Totals)

As a User,
I want to see my total spending for specific time periods,
So that I can stay within my budget.

**Acceptance Criteria:**

**Given** a request for "this month's total"
**When** the system queries the database
**Then** it returns the sum of all transactions for the current month.
**And** the result is returned in the user's primary currency.

### Story 3.3: Category-Based Spending Filters

As a User,
I want to filter my history by category (e.g., "How much did I spend on Hardware?"),
So that I can identify specific spending leaks.

**Acceptance Criteria:**

**Given** a category name
**When** the system filters records
**Then** it returns only transactions mapped to that specific category.

### Story 3.4: Friendly Conversational Summary Generator

As a User,
I want the bot to summarize my history in a conversational tone,
So that I feel more financially aware without the stress of a spreadsheet.

**Acceptance Criteria:**

**Given** a list of recent transactions
**When** the system prepares a response
**Then** it uses the LLM to write a summary (e.g., "You've spent $45 on Coffee this week, which is 10% less than last week!").

## Epic 4: Data Portability & Rights

Ensure GDPR compliance and user control. Users can export their data or delete their entire account.

### Story 4.1: Financial Data Export (JSON/CSV)

As a User,
I want to export my complete transaction history via the bot,
So that I can import it into other tools or keep my own records.

**Acceptance Criteria:**

**Given** a request for "export my data"
**When** the system generates the export
**Then** it decrypts all user records and packages them into a CSV or JSON file.
**And** sends the file as a document via Telegram.

### Story 4.2: Account Deletion ("Right to be Forgotten")

As a User,
I want to permanently delete my account and all associated data,
So that I have total control over my digital privacy.

**Acceptance Criteria:**

**Given** a request to "delete my account"
**When** the user confirms the action
**Then** the system removes all records associated with that `user_id` and `family_id` from the database.
**And** sends a final confirmation message before closing the session.

## Epic 5: Family Shared Ledgers (Phase 2)

Enable multi-user collaboration. Families can create shared groups to track collective expenses.

### Story 5.1: Family Group Creation & Invite Link

As a User,
I want to create a Family Group and generate a unique invite link,
So that I can easily add my partner or housemates to my ledger.

**Acceptance Criteria:**

**Given** a request to "create a family"
**When** the family is created
**Then** the system generates a secure, time-limited invite link.
**And** new users joining via this link are assigned the same `family_id`.

### Story 5.2: Shared Budget Visibility

As a Family Member,
I want to see the total spending for our entire family,
So that we can stay on budget together.

**Acceptance Criteria:**

**Given** a query for "family total"
**When** the system retrieves records
**Then** it sums transactions from ALL users belonging to the same `family_id`.

### Story 5.3: Per-Member Spending Attribution

As a User,
I want to see which family member logged a specific expense,
So that we have transparency in our shared ledger.

**Acceptance Criteria:**

**Given** a transaction list or summary
**When** members are viewing the logs
**And** each record includes the name or handle of the user who created it.

## Epic 6: Premium Notion Mirroring (Phase 2)

Integrate with external tools. Premium users can sync their local ledger to their Notion databases.

### Story 6.1: Notion Workspace Connection

As a Premium User,
I want to connect my Notion account and select a target database,
So that I can link my bot records to my existing financial workspace.

**Acceptance Criteria:**

**Given** a Notion API key or OAuth token
**When** the user provides the connection details
**Then** the system validates the token and retrieves the list of available databases.
**And** stores the `notion_database_id` securely for that family.

### Story 6.2: Real-Time Log Mirroring (via Python API)

As a User,
I want every new log I make to automatically appear in Notion,
So that my dashboard is always up to date without manual effort.

**Acceptance Criteria:**

**Given** a successfully saved local transaction
**When** mirroring is enabled for the family
**Then** the FastAPI backend triggers a native async background task using the `notion-client` Python SDK.
**And** creates a new database row in Notion with the amount, category, and concept.

### Story 6.3: Retry Mechanism for Mirroring

As a User,
I want the system to retry syncing my logs if Notion is temporarily down,
So that I never lose a record in my primary dashboard.

**Acceptance Criteria:**

**Given** a temporary Notion API failure
**When** the sync is attempted via the native Python task
**Then** the system uses Python's `tenacity` library or Celery task retry logic to retry the request (with exponential backoff).
**And** logs failures to standard error for operational monitoring.

## Epic 7: Monetization & Subscriptions

Enable in-app subscriptions using Telegram Stars (XTR) with auto-renewing cycles. New users receive a 60-day Family Pro free trial with full feature access upon `/start`. Free workspaces share a 30-message/month quota across all features. Users can subscribe to Solo Pro (150 Stars/mo, 1 person) or Family Pro (300 Stars/mo, up to 5 members) for unlimited transactions. Proactive notifications trigger at Day 50 (trial ending soon) and Day 60 (reassurance of data safety + free tier limits). Supports lifetime VIP access via direct database provisioning.

### Story 7.1: Database Schema Expansion for Subscriptions & 60-Day Trials

As a Developer,
I want to expand the database models to support subscription tracking, 60-day trials, member caps, and notification states,
So that we can manage quotas, active Pro plans, and proactive lifecycle messaging reliably.

**Acceptance Criteria:**

**Given** the `src/db/models.py` file
**When** the `Family` and `User` models are updated
**Then** `Family` includes:
- `plan_type: str = Field(default="free")` (supporting `"free"`, `"trial"`, `"solo_pro"`, `"family_pro"`, `"lifetime_pro"`)
- `subscription_status: str = Field(default="active")`
- `monthly_tx_count: int = Field(default=0)`
- `max_members: int = Field(default=5)`
- `trial_ends_at: Optional[datetime] = Field(default=None)`
- `current_period_end: Optional[datetime] = Field(default=None)`
- `telegram_payment_charge_id: Optional[str] = Field(default=None)`
- `notified_day_50: bool = Field(default=False)`
- `notified_day_60: bool = Field(default=False)`
**And** `User` includes:
- `has_used_trial: bool = Field(default=False)`
**And** `lifetime_pro` is strictly reserved for manual database administration (cannot be assigned via webhooks or bot commands).

### Story 7.2: 60-Day Trial Provisioning, Onboarding Welcome & Quota Gating

As a User,
I want to be greeted with a 60-day Family Pro trial upon starting the bot, receive clear onboarding as a creator or invited member, manage my family members as an admin, and have quota limits enforced fast before AI processing,
So that I experience the full capabilities of Clanomy upfront and understand my account and family lifecycle.

**Acceptance Criteria:**

**Given** a new user runs `/start`
**When** creating their family workspace
**Then** if the user's `has_used_trial` is `False`, the family is provisioned with `plan_type="trial"`, `trial_ends_at = now() + 60 days`, and the user is marked `has_used_trial = True`.
**And** the `/start` welcome response explains all core features (voice notes, Ask cash flow questions, Notion sync, family invites) and announces the 60-day Family Pro trial.
**And** when a user joins a family via an invite link (`/start join_<token>`), the bot greets them with an invited member welcome message explaining shared family logging and the `/leavefamily` portability option.
**And** if a user who already used a trial creates a new workspace or leaves a family, their space starts directly on `"free"` with an explanation that the trial was previously consumed.
**And** for Free tier workspaces (`plan_type="free"`), the webhook performs an early fast-fail quota check (`can_log_transaction`) *before* invoking Faster-Whisper audio transcription or Ollama LLM extraction; on the 31st log, it immediately blocks the log and replies with a friendly limit notice prompting `/upgrade`.
**And** Pro tiers (`"solo_pro"`, `"family_pro"`, `"lifetime_pro"`, and active `"trial"`) bypass quota gating.
**And** provides family management commands for the admin/creator:
- `/family`: Lists all members in the family workspace.
- `/removemember @username`: Admin removes a member, detaches them into a new personal Free workspace with all their personal transactions ported, revokes admin query access to their data, and sends the removed member a polite notification.
- `/leavefamily`: Allows any member to leave independently with full transaction portability.

### Story 7.3: Telegram Stars Auto-Renewing Invoice Generation (`/upgrade`)

As a User,
I want to trigger an upgrade invoice directly in chat with auto-renewing billing,
So that I can pay seamlessly using Telegram Stars (Apple/Google Pay) for my chosen tier.

**Acceptance Criteria:**

**Given** a user types `/upgrade` in the chat
**When** the Telegram webhook receives the command
**Then** it responds with Telegram invoices (`sendInvoice` API) in `XTR` currency with `subscription_period = 2592000` (30-day auto-renewing cycle).
**And** presents:
- **Solo Pro** (150 Stars / month): Unlimited logs for 1 person (no family invites).
- **Family Pro** (300 Stars / month): Unlimited logs for up to 5 family members.
**And** if a Solo Pro user attempts to generate an invite link, the bot explains that Family Pro is required to add members.

### Story 7.4: Payment Verification & Subscription Lifecycle Webhook Handler

As a System,
I want to securely verify payments, recurring renewals, and cancellations,
So that user accounts are automatically upgraded and maintained in real time.

**Acceptance Criteria:**

**Given** a Telegram payment flow
**When** the user attempts to pay
**Then** the webhook answers the `pre_checkout_query` within 10 seconds with `ok=True`.
**And** upon receiving `successful_payment`, the system validates the payload against the whitelist (`sub_solo_pro`, `sub_family_pro`), updates `Family.plan_type`, sets `subscription_status="active"`, and sends a confirmation message.
**And** captures recurring renewal and cancellation webhook events, transitioning `subscription_status` accordingly while protecting `lifetime_pro` from external overwrites.

### Story 7.5: Proactive Trial Lifecycle Notifications Scheduler (Day 50 & Day 60)

As a User,
I want to be proactively notified 10 days before my trial ends and when my trial completes,
So that I understand my transition to the Free tier, know that my past data is safe, and have a clear option to subscribe.

**Acceptance Criteria:**

**Given** an automated daily notification scheduler
**When** checking trial workspaces:
**Then** for families where `trial_ends_at` is 10 days away (Day 50) and `notified_day_50 == False`:
- Sends a proactive notification summarizing value delivered (transactions tracked) and warning that the trial ends in 10 days, presenting the tiers and `/upgrade` CTA.
- Marks `notified_day_50 = True`.
**And** for families where `trial_ends_at` has passed (Day 60) and `notified_day_60 == False` without an active paid subscription:
- Transitions `Family.plan_type` to `"free"`.
- Sends the Day 60 transition message reassuring that all historical data, Ask queries, and Notion sync remain 100% intact, while explaining the 30-message/month shared family limit and `/upgrade` CTA.
- Marks `notified_day_60 = True`.

## Epic 8: Family Income & Net Cash Flow Tracking

Enable users to log earnings and income, classify dual intents (expense vs income) via local AI extraction, compute real-time net cash flow and savings rate, and sync income entries across Notion and GDPR exports.

### Story 8.1: Database Schema Extension for Transaction Types

As a Developer,
I want to extend the `Transaction` model with a `type` discriminator,
So that both income and expense records can be stored uniformly with application-level encryption.

**Acceptance Criteria:**

**Given** the `src/db/models.py` file
**When** the `Transaction` model is updated
**Then** it includes `type: str = Field(default="expense", index=True)` supporting `"expense"` and `"income"`.
**And** existing rows in PostgreSQL/SQLite default gracefully to `"expense"` without data corruption.
**And** all unit tests in `tests/db/test_models.py` pass with full test coverage of cascade and query behaviors.

### Story 8.2: Dual-Intent Natural Language Extraction (Income vs Expense)

As a Developer,
I want the Ollama extraction service to distinguish between income and expense intents,
So that earnings and spend are accurately categorized and extracted.

**Acceptance Criteria:**

**Given** an income statement (e.g., "Got my salary of 3200 dollars from Acme Corp" or "Sold my bike for 150 euros")
**When** processed through `ExtractionService`
**Then** it returns a structured JSON payload with `type: "income"`, `amount: 3200.0`, `currency: "USD"`, `category: "Salary"`, and `concept: "Acme Corp"`.
**And** standard expense statements continue returning `type: "expense"`.
**And** ambiguous entries default safely to `type: "expense"`.

### Story 8.3: Income Voice & Text Logging Orchestrator

As a User,
I want to log my income via voice notes and text in under 3 seconds,
So that I get an immediate, upbeat confirmation of my earnings and monthly cash flow.

**Acceptance Criteria:**

**Given** an incoming income voice note or text message
**When** processed by the AI orchestrator pipeline
**Then** the record is encrypted and saved with `type: "income"` associated with the user's `family_id`.
**And** the Telegram response provides an upbeat confirmation with income amount, monthly total earnings, and current net savings.
**And** execution conforms to the 3-second rule.

### Story 8.4: Conversational Net Cash Flow & Income Queries (ASK Engine)

As a User,
I want to ask the bot about our earnings and net balance (e.g., "How much did we make this month?" or "What's our net balance?"),
So that I can understand our household cash flow conversationally.

**Acceptance Criteria:**

**Given** a conversational query about income or net balance
**When** processed by `QueryService`
**Then** it aggregates total income, total expenses, and calculates `net_balance = total_income - total_expenses` and savings rate percentage.
**And** returns a clear, conversational summary in the user's primary currency.

### Story 8.5: Notion Mirroring & Export Updates for Income Records

As a User,
I want income records to be reflected in my Notion mirror and GDPR exports,
So that my external dashboards and data backups have a complete view of my finances.

**Acceptance Criteria:**

**Given** an income transaction
**When** Notion mirroring is triggered
**Then** the Notion database row includes the `Type` property set to `Income`.
**And** when exporting data (CSV/JSON), the export file includes the `Type` column with `"income"` or `"expense"` for every transaction.

### Story 8.6: Conversational Transaction Correction & Undo (Edit Latest Log)

As a User,
I want to send natural language corrections (e.g., "Change the last one to income", "Change last amount to 45", or "Delete the last log"),
So that I can immediately fix transcription mistakes or incorrect categories without opening a web dashboard.

**Acceptance Criteria:**

**Given** a user sends a conversational correction or undo request (via text or voice note)
**When** processed by `ExtractionService` and `AIOrchestrator`
**Then** the system identifies the user's most recent transaction (`latest_transaction`).
**And** supports updating transaction `type` (`expense` $\leftrightarrow$ `income`), `amount`, `category`, and `concept` with re-encryption at rest.
**And** supports deleting/undoing the latest transaction upon request.
**And** if Notion mirroring is connected and `notion_page_id` is present, updates or archives the Notion page in the background.
**And** replies with an upbeat confirmation of the edit alongside refreshed monthly cash flow totals.
**And** unit and integration tests in `tests/services/test_ai_orchestrator.py` and `tests/services/test_extraction_service.py` verify all correction paths.

---

## Epic 9: Multi-Currency & Bilingual Localization

Enable per-family default currency configuration, bilingual natural language financial extraction, dynamic currency defaults, and multi-currency segregation in reporting.

### Story 9.1: Database Schema & Migration for Family Default Currency

As a Developer,
I want to add a `default_currency` field to the `Family` model with a database migration,
So that each household can store and maintain its primary operating currency.

**Acceptance Criteria:**

**Given** the `src/db/models.py` file
**When** updating the `Family` table
**Then** it adds `default_currency: str = Field(default="USD", sa_column_kwargs={"server_default": "USD"}, max_length=3)`.
**And** Alembic migration `0005_add_family_default_currency.py` applies the schema revision cleanly in PostgreSQL and SQLite.
**And** existing family records default to `"USD"`.

### Story 9.2: Family Currency Configuration & `/currency` Chat Command

As a Household Admin,
I want to set or inspect our family's currency using `/currency <ISO>` or natural language,
So that our family records are denominated in our local currency.

**Acceptance Criteria:**

**Given** a user sends `/currency` or `/currency ARS`
**When** processed by `currency_handler.py` and `FamilyService`
**Then** `/currency` displays the currently active household currency.
**And** `/currency ARS` validates against ISO 4217, normalizes to uppercase, updates `Family.default_currency`, and confirms with a localized success message.
**And** natural language phrasing (*"set currency to EUR"*, *"cambiar moneda a pesos"*) triggers the same update logic.
**And** `/start` proactively advises new users to configure their currency.

### Story 9.3: Bilingual NLP & Dynamic Currency Extraction

As a User,
I want to log expenses in Spanish or English without typing the currency symbol every time,
So that my unadorned logs automatically record in our family's currency.

**Acceptance Criteria:**

**Given** a text or audio input without an explicit currency (e.g. *"gasté 1200 en pan"* or *"spent 45 on coffee"*)
**When** processed by `ExtractionService`
**Then** the extraction engine receives the family's configured default currency dynamically.
**And** outputs the transaction denominated in that currency (e.g. `currency: "ARS"`).
**And** explicitly stated currencies (*"10 dollars"*, *"50 eur"*) override the family default.
**And** bilingual categories (*"supermercado"*, *"farmacia"*, *"alquiler"*) normalize accurately into canonical English categories.

### Story 9.4: Multi-Currency Query Segregation & Formatting

As a User,
I want my spending summaries and cash flow reports to segregate different currencies cleanly,
So that figures from different currencies are never added together into meaningless totals.

**Acceptance Criteria:**

**Given** a household with transactions logged in both `USD` and `ARS`
**When** the user asks for a monthly or weekly summary
**Then** `QueryService` aggregates transactions grouped by currency.
**And** formats the summary with clear sub-totals per currency.
**And** empty state queries (0 transactions) display balance figures formatted in the family's default currency (e.g. `$0.00 ARS`).

---

## Epic 10: Scheduled Bills, Commitments & Settlement

Enable tracking of scheduled financial obligations, batch extraction, conversational zero-amount bill settlement (*"Pagué la visa"*), and proactive due date alerts.

### Story 10.1: `ScheduledBill` Database Model & Encrypted Schema Migration

As a Developer,
I want to create a `ScheduledBill` table with encrypted fields and foreign keys,
So that upcoming household obligations are stored securely with zero-knowledge privacy.

**Acceptance Criteria:**

**Given** the `src/db/models.py` file
**When** defining `ScheduledBill`
**Then** it includes `id`, `family_id`, `user_id`, `amount` (ciphertext), `concept` (ciphertext), `category`, `due_date`, `status` (`"pending"`, `"paid"`, `"cancelled"`), and `paid_transaction_id`.
**And** Alembic migration `0006_add_scheduled_bill.py` generates the table with appropriate foreign keys and cascading rules.

### Story 10.2: Due Date & Batch Bill NLP Extraction

As a User,
I want to record single or multiple upcoming bills with due dates in a single message,
So that I can register our monthly commitments quickly.

**Acceptance Criteria:**

**Given** a message like *"El 10 vence la luz 45000 y el 15 el gas 12000"* or *"Visa 1200 due on the 5th"*
**When** processed by `ExtractionService` and `ai_orchestrator.py`
**Then** the system detects upcoming obligations, parses relative/absolute due dates, and extracts all bill entities in batch.
**And** encrypts each bill and persists records with `status="pending"`.
**And** responds with a formatted confirmation card listing all scheduled commitments.

### Story 10.3: Conversational Zero-Amount Bill Settlement

As a User,
I want to say *"Pagué la visa"* or *"Paid the electric bill"* without mentioning the amount,
So that the bot marks the pending bill as paid and logs the expense under my name automatically.

**Acceptance Criteria:**

**Given** a user sends *"Pagué la visa"* without an amount
**When** processed by `AIOrchestrator._settle_bill_without_amount()`
**Then** the system performs a user-scoped lookup first (`bill.user_id == current_user.id`).
**And** if not found, performs a family fallback lookup (`bill.family_id == current_family.id`).
**And** decrypts the stored bill amount, logs a new `Transaction` under category `"Rent/Bills"`, updates bill `status="paid"`, and links `paid_transaction_id`.
**And** if no bill matches, politely asks for the amount without throwing an exception.

### Story 10.4: Proactive Due & Overdue Bill Alerts in Status Queries

As a User,
I want to be reminded of pending or overdue bills whenever I check our monthly financial status,
So that our household never misses an obligation.

**Acceptance Criteria:**

**Given** pending scheduled bills where `due_date <= now()` in the current month
**When** the user asks *"¿Cómo venimos este mes?"* or *"resumen"*
**Then** `QueryService` appends an alert block to the financial summary listing overdue and upcoming bills.
**And** includes conversational instructions to settle them (e.g. *`"Si ya pagaste alguna, solo dime 'Pagué la visa'"`*).

---

## Epic 11: Enterprise Security Hardening & Infrastructure Isolation

Implement enterprise-grade multi-tenancy isolation, prompt injection defenses, concurrency serialization, resource bounding, and infrastructure origin shielding.

### Story 11.1: Multi-Tenant Workspace Isolation & RLS

As a Security Officer,
I want strict workspace isolation when members leave a family group,
So that no orphaned data or external credentials are ever leaked across households.

**Acceptance Criteria:**

**Given** a user executes `/leavefamily`
**When** `FamilyService.leave_family()` executes
**Then** the system guarantees zero recycling of old family IDs.
**And** instantiates a fresh `Family` record with clean Notion credentials and default settings.
**And** PostgreSQL Row-Level Security (RLS) migration `0004_enable_rls_security.py` enforces tenant separation.

### Story 11.2: Telegram Message Escaping & Delivery Resilience

As a Developer,
I want outbound Telegram HTML messages to be sanitized and backed by automatic plain-text retry,
So that invalid entities never result in silent message delivery failures.

**Acceptance Criteria:**

**Given** dynamic user text containing characters like `<`, `>`, or `&`
**When** `AIOrchestrator` formats Telegram responses
**Then** all user fields are sanitized using `html.escape()`.
**And** if Telegram returns an HTTP 400 parsing error, `TelegramService.send_message()` catches the error and immediately resends the message with `parse_mode=None`.

### Story 11.3: Prompt Injection Defense & `<user_input>` XML Fencing

As a Security Engineer,
I want untrusted inputs to be stripped of markdown formatting and isolated inside XML tags,
So that malicious prompts cannot break out of their instruction context.

**Acceptance Criteria:**

**Given** user input containing markdown fences (```` ``` ````) or prompt jailbreak attempts
**When** sent to `ExtractionService` or `QueryService`
**Then** `src/core/ai_client.py:sanitize_prompt_input()` strips fences and isolates text inside `<user_input>` XML delimiters.
**And** prompts enforce anti-leakage instructions preventing system prompt disclosure.

### Story 11.4: Concurrency Serialization & Resource Bounding

As a System Administrator,
I want rapid sequential requests per user to be serialized and global AI calls to be throttled,
So that race conditions and server resource exhaustion are completely prevented.

**Acceptance Criteria:**

**Given** rapid concurrent requests from a single user
**When** received by `AIOrchestrator`
**Then** a per-user `asyncio.Lock` serializes execution order.
**And** global concurrent AI requests across the entire application are bounded by `GLOBAL_OLLAMA_SEMAPHORE`.
**And** in-memory query decryption is capped at `MAX_QUERY_TRANSACTIONS_LIMIT = 500`.

### Story 11.5: Origin Shielding, Security Headers & Webhook Rate Limiting

As an Operations Engineer,
I want webhook traffic to be verified against Cloudflare Origin Shield and protected by security headers,
So that untrusted network traffic is rejected at the HTTP boundary.

**Acceptance Criteria:**

**Given** incoming HTTP requests to `/api/v1/telegram/webhook`
**When** processed by FastAPI middleware in `src/main.py`
**Then** Cloudflare Origin Shield headers are verified when enabled in configuration.
**And** security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`) are attached.
**And** high-frequency spam requests trigger rate limiting before invoking downstream AI pipelines.

---

## Epic 12: Modular Architecture Refactoring & Resilient AI Ingress

Decompose monolithic services into decoupled domain sub-packages, integrate hybrid Cloud AI (Groq), and establish deterministic offline fallback engines.

### Story 12.1: Domain-Driven Decomposition of Core Services

As a Software Engineer,
I want the large monolithic services decoupled into sub-packages with backwards-compatible shims,
So that the codebase is modular, testable, and maintainable without breaking existing imports.

**Acceptance Criteria:**

**Given** monolithic files `extraction_service.py`, `query_service.py`, and `ai_orchestrator.py`
**When** refactoring into domain packages
**Then** `src/services/extraction/` contains `models.py`, `normalizers.py`, `prompts.py`, `fallback.py`, and `service.py`.
**And** `src/services/query/` contains `models.py`, `date_resolver.py`, `aggregator.py`, `formatters.py`, and `service.py`.
**And** `src/services/handlers/` contains `family_handler.py`, `notion_handler.py`, `currency_handler.py`, and `account_handler.py`.
**And** top-level shims (`extraction_service.py`, `query_service.py`) re-export classes with 100% backwards compatibility.

### Story 12.2: Hybrid Cloud & Local AI Inference Pipeline

As an Operator,
I want to configure either local Ollama or Groq Cloud AI inference seamlessly,
So that Clanomy can run on both self-hosted GPUs and lightweight VPS environments.

**Acceptance Criteria:**

**Given** a configured `GROQ_API_KEY`
**When** transcribing audio or extracting financial entities
**Then** `WhisperService` and `ExtractionService` route requests to Groq's high-speed cloud APIs.
**And** when `GROQ_API_KEY` is omitted, the system seamlessly defaults to local Faster-Whisper and Ollama without code changes.

### Story 12.3: Deterministic Fallback Extraction & Classification

As a User,
I want standard financial logs to succeed even if the AI inference engine is temporarily down,
So that my logging habit is never disrupted by service outages.

**Acceptance Criteria:**

**Given** a message like *"Spent 15 on lunch"* or *"Gasté 5000 en verdulería"*
**When** LLM inference times out or throws an error
**Then** `src/services/extraction/fallback.py` executes deterministic regex extraction.
**And** accurately resolves type, amount, category, and concept.
**And** completes the log successfully without returning an error to the user.

### Story 12.4: Atomic User & Family Provisioning Service

As a Developer,
I want user registration and family workspace creation encapsulated in a dedicated service,
So that webhook controllers remain thin and registration edge cases are handled atomically.

**Acceptance Criteria:**

**Given** a new user sending a webhook update
**When** `MessagingService.get_or_create_user_and_family()` is invoked
**Then** it atomically creates or fetches the `User` and `Family` records in a single database transaction.
**And** handles username/full-name updates and provisions trial periods without race conditions.

---

## Epic 13: CI/CD Quality Automation & Open-Source Readiness

Establish automated CI testing pipelines, protect critical repository assets with PR guardrails, automate Alembic migrations, and publish open-source community guidelines.

### Story 13.1: GitHub Actions CI & 85%+ Coverage Enforcement

As a Developer,
I want every push and pull request validated by automated tests and coverage gates,
So that regressions are caught before merging into the master branch.

**Acceptance Criteria:**

**Given** a push or PR to `master`
**When** `.github/workflows/test.yml` executes
**Then** it installs dependencies, configures environment isolation, and runs all 347 unit and integration tests.
**And** fails the build if total test coverage drops below 85%.

### Story 13.2: PR Guardrail Workflow for Protected Assets

As a Project Maintainer,
I want sensitive monetization, configuration, and CI files guarded against unauthorized modification,
So that critical system boundaries cannot be silently altered.

**Acceptance Criteria:**

**Given** a pull request modifying files matching `PROTECTED_PATTERNS` in `.github/workflows/pr-guardrail.yml`
**When** the PR guardrail workflow runs
**Then** it blocks merging unless explicitly authored or approved by project administrators.

### Story 13.3: Automated Alembic Startup Migration Lifecycle

As a System Administrator,
I want database migrations to execute automatically during application boot,
So that container deployments and upgrades require zero manual database interventions.

**Acceptance Criteria:**

**Given** a newly deployed container running `src/main.py`
**When** the FastAPI application starts up
**Then** the `lifespan` handler runs `alembic upgrade head`.
**And** verifies that all migration revisions (`0001` through `0006`) are applied before serving traffic.

### Story 13.4: Community Funding & Containerized Self-Hosting Framework

As an Open-Source Contributor,
I want comprehensive Podman deployment documentation, contribution guidelines, and funding options,
So that the community can self-host and support the project sustainably.

**Acceptance Criteria:**

**Given** the repository root
**When** reviewing documentation
**Then** `README.md` and `docs/self-hosting.md` provide verified Podman Compose setup instructions.
**And** `CONTRIBUTING.md` establishes architectural standards, test requirements, and commit conventions.
**And** `.github/FUNDING.yml` and badges support community sponsorship via Ko-fi.

---

## Epic 14: Pre-Built Fast-Path Commands & Hybrid Quota Model

Provide instant (<40ms) deterministic slash commands (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`) running directly in Python/SQL with zero AI token cost, full multi-currency segregation, member-by-member family transparency, personal cash-flow isolation, and a 20-operation/month Free Tier AI quota model.

### Story 14.1: Fast-Path Deterministic Command Router (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help`)

As a User,
I want routine financial commands to execute instantly without waiting for an AI model or consuming my monthly AI allowance,
So that I can check my finances daily with zero latency and zero quota anxiety.

**Acceptance Criteria:**

**Given** an incoming message starting with a slash command (`/month`, `/me`, `/today`, `/bills`, `/balance`, `/undo`, `/help` or Spanish aliases `/resumen`, `/yo`, `/hoy`, `/vencimientos`, `/saldo`, `/deshacer`, `/ayuda`)
**When** processed at the Telegram webhook
**Then** `CommandHandler` executes the operation deterministically in Python/SQL in <40ms without invoking `AIOrchestrator` or LLMs.
**And** the operation **never** checks or increments `Family.monthly_tx_count`.
**And** returns formatted Telegram HTML responses directly.

### Story 14.2: Household Member Segregation & Personal Isolation

As a Household Member,
I want `/month` to show each person's earnings and expenses, and `/me` to isolate my personal spending,
So that my partner and I have complete budget transparency while keeping personal financial visibility.

**Acceptance Criteria:**

**Given** transactions logged by multiple family members
**When** a user runs `/month`
**Then** the output displays total household income, expenses, and net balance, followed by a `👥 Member Breakdown` displaying each member's total income, expenses, net balance, and top expense category.
**And** when a user runs `/me`, the system filters strictly by `user_id == user.id`, showing only the caller's personal income, expenses, net savings, and top 4 expense categories.

### Story 14.3: Multi-Currency Ledger Aggregation per Member

As an Expat or Multi-Currency Family,
I want multi-currency transactions reported separately for both household and individual member totals,
So that different currencies are never incorrectly summed together.

**Acceptance Criteria:**

**Given** transactions recorded in multiple ISO currencies (e.g. USD and EUR)
**When** generating `/month`, `/me`, `/today`, or `/balance`
**Then** `MemberSpending.income_currency_totals` and `MemberSpending.expense_currency_totals` track each currency independently.
**And** output formatters list distinct amounts per currency (e.g. `3,500.00 USD · 450.00 EUR`) without cross-currency mathematical addition.

### Story 14.4: 20-Log Free Tier Quota & Context-Aware Pro-Tips

As a Free Tier User,
I want to know how many AI operations I have remaining and receive tips on instant free commands,
So that I can maximize my usage and upgrade to Pro when my household volume grows.

**Acceptance Criteria:**

**Given** a Free Tier workspace (`plan_type="free"`)
**When** transactions or queries are processed
**Then** `FREE_TIER_MONTHLY_LIMIT` enforces a 20 AI operation/month allowance for natural language inputs.
**And** `/family` displays `Monthly AI Logs: {used} / 20 (⚡ Commands are 100% free & unlimited)`.
**And** natural language queries append a plan-aware Pro-Tip:
  - Free: *💡 Pro-tip: Type /month or /me anytime for an instant response that doesn't use your monthly AI quota!*
  - Pro: *💡 Pro-tip: Type /month or /me anytime for an instant response!*
**And** when the 20-operation limit is reached, natural text logging is paused with an upgrade notice, but all slash commands (`/month`, `/me`, `/bills`, etc.) remain 100% operational.

---

## Epic 15: Household Timezone Support & Dynamic Temporal Resolution

Enable per-family IANA timezone configuration, database migration `0008`, and dynamic localized date resolution for relative natural language queries and scheduled obligations.

### Story 15.1: Database Schema & Migration for Family Timezone
As a System Architect,
I want the `family` table to persist each household's IANA timezone,
So that queries and scheduled obligations reflect the family's geographic reality.

**Acceptance Criteria:**
**Given** Alembic migration `0008_add_timezone_support.py`
**When** the migration runs on boot
**Then** it adds a `timezone` VARCHAR column to `family` with a default value of `"UTC"`.
**And** verifies backwards compatibility with existing workspaces.

### Story 15.2: Household Timezone Configuration & Chat Command
As a Household Admin,
I want to view and update our household timezone using `/timezone`,
So that our daily and monthly logs reset at our local midnight rather than UTC midnight.

**Acceptance Criteria:**
**Given** a user running `/timezone` or `/settimezone <IANA_TZ>` (e.g. `/timezone America/Argentina/Buenos_Aires`)
**When** processed by `CommandHandler`
**Then** the system validates the string against `zoneinfo.available_timezones()`.
**And** updates `Family.timezone` and returns localized confirmation.
**And** rejects invalid timezone strings with helpful examples.

### Story 15.3: Timezone-Aware Date Resolution & Aggregations
As a User,
I want natural language queries like *"¿Cuánto gastamos hoy?"* or *"How much did we spend yesterday?"* to evaluate according to my local clock,
So that evening transactions are never incorrectly counted towards the next day.

**Acceptance Criteria:**
**Given** a family configured with a non-UTC timezone (e.g. UTC-3)
**When** a relative date query is processed by `DateResolver`
**Then** the system converts local day/month boundaries into UTC timestamp query windows.
**And** database aggregation queries return exact transactions matching the user's localized calendar window.

---

## Epic 16: Compound Batch Transaction Extraction & Multi-Item Undo

Support extracting multiple discrete transactions from single conversational voice or text messages, validating via `BatchTransactionExtractionResult`, and rolling back entire batches atomically with `BatchTracker`.

### Story 16.1: Compound Batch Transaction Pydantic Models & Prompts
As an AI Engineer,
I want the extraction service to recognize and parse multiple financial transactions from a single sentence or audio note,
So that users do not need to send multiple messages when reporting errands.

**Acceptance Criteria:**
**Given** a user message describing multiple transactions (e.g. *"Gasté 18500 en súper y 8000 en farmacia"*)
**When** processed by `ExtractionService`
**Then** the LLM formats the response adhering to `BatchTransactionExtractionResult`.
**And** validates each sub-transaction with amount, type, concept, category, and currency.

### Story 16.2: Batch Tracker & Multi-Item Undo Orchestration
As a User,
I want to type `/undo` after logging multiple items in a single message and have all of them rolled back together,
So that my ledger is restored to its exact previous state without needing repeated undo commands.

**Acceptance Criteria:**
**Given** a compound batch transaction logged via `AIOrchestrator`
**When** `BatchTracker` records the batch transaction IDs
**Then** a subsequent `/undo` command rolls back all transactions in that batch in a single database transaction.
**And** responds to the user confirming the total count and concepts rolled back.

---

## Epic 17: Decoupled Billing Architecture & Processor Abstraction (Refactored)

*Note: Initially prototyped with Lemon Squeezy Merchant of Record (Stories 17.1–17.4), this epic was refactored in September 2026 to eliminate third-party vendor lock-in. Alembic migration `0011_remove_lemonsqueezy_fields.py` dropped proprietary Lemon Squeezy columns from the database, and billing discovery was abstracted into `BillingService` (`src/services/billing/billing_service.py`) generating deep links (`https://t.me/<bot>?start=upgrade_<plan>`) with ongoing evaluation of PayPal and Telegram bot subscription offers.*

### Story 17.1: Database Schema & Migration for Lemon Squeezy (Superseded by Migration 0011)
As a Developer,
I want the database to store Lemon Squeezy customer and subscription identifiers,
So that subscription lifecycles can be matched and managed deterministically.

**Acceptance Criteria:**
**Given** Alembic migration `0009_add_lemonsqueezy_fields.py`
**When** applied to the database
**Then** it adds `lemonsqueezy_customer_id`, `lemonsqueezy_subscription_id`, and `lemonsqueezy_variant_id` to the `family` table.
*(Superseded: Migration `0011_remove_lemonsqueezy_fields.py` removed these fields to restore schema portability).*

### Story 17.2: Lemon Squeezy Billing Service & Checkout Generation (Refactored into Pluggable BillingService)
As a SaaS User,
I want to type `/upgrade` and receive a dynamic hosted checkout link with Apple Pay / Credit Card,
So that I can upgrade without entering cryptocurrency tokens or navigating complex checkout flows.

**Acceptance Criteria:**
**Given** a user executing `/upgrade` in SaaS mode (`ENABLE_SUBSCRIPTIONS=true`)
**When** `LemonSqueezyBillingService.create_checkout_url()` is called
**Then** it requests a checkout from Lemon Squeezy with custom metadata (`family_id`, `chat_id`).
**And** returns an inline button with the secure payment URL.
*(Refactored: Replaced by `BillingService.handle_upgrade_command()` generating interactive Telegram deep links).*

### Story 17.3: Lemon Squeezy Webhook Verification & Subscription Lifecycle (Decommissioned)
As a System Administrator,
I want inbound webhooks from Lemon Squeezy to verify HMAC-SHA256 signatures and synchronize subscription states in real time,
So that user accounts are automatically activated, renewed, or cancelled securely.

**Acceptance Criteria:**
**Given** an inbound HTTP POST to `/api/webhooks/lemonsqueezy`
**When** `LemonSqueezyBillingService.verify_webhook_signature()` validates the `x-signature` header
**Then** events (`subscription_created`, `subscription_updated`, `subscription_cancelled`, `subscription_resumed`, `subscription_expired`) update the target family's `plan_type` and `subscription_status`.
**And** unauthorized requests without valid HMAC signatures are rejected with HTTP 401.

### Story 17.4: Customer Billing Portal & Tier Quota Management
As a Subscribed Customer,
I want a direct link to manage my billing, download VAT invoices, or cancel my subscription,
So that I have full self-service control over my billing relationship.

**Acceptance Criteria:**
**Given** an active subscriber running `/billing` or requesting subscription management
**When** `LemonSqueezyBillingService.get_customer_portal_url()` is invoked
**Then** it fetches the authenticated Lemon Squeezy Customer Portal URL.
**And** delivers it to the chat with privacy precautions.

---

## Epic 18: Multi-Provider AI Inference Resilience, Prompt Caching & Speech-to-Text Fallbacks

Support unified multi-provider Speech-to-Text (`WhisperService` across Faster-Whisper, Groq Whisper API, and OpenAI Whisper) and LLM inference (Groq, OpenAI, Google Gemini, Ollama) featuring static prompt caching and exponential backoff retry with jitter.

### Story 18.1: Multi-Provider Whisper Speech-to-Text Engine
As a User,
I want voice notes transcribed reliably whether running locally on personal hardware or in lightweight cloud environments,
So that voice logging works seamlessly across all deployment targets.

**Acceptance Criteria:**
**Given** an incoming audio voice note
**When** processed by `WhisperService`
**Then** it routes transcription according to `WHISPER_PROVIDER` (`local`, `groq`, `openai`).
**And** enforces audio payload validation (<25MB) and securely deletes temporary files.

### Story 18.2: OpenAI-Compatible Provider & Gemini Support
As an AI Engineer,
I want a unified provider capable of interfacing with Groq Cloud, OpenAI, Together AI, and Google Gemini,
So that the application can switch cloud LLM providers via simple environment variables without code modifications.

**Acceptance Criteria:**
**Given** configuration with `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL`
**When** `get_llm_provider()` is initialized
**Then** it instantiates `OpenAICompatibleProvider`.
**And** supports structured Pydantic schema extraction and natural language query completion.

### Story 18.3: Static Prompt Caching & Exponential Backoff Resilience
As a Platform Operator,
I want LLM requests to leverage upstream prefix prompt caching and handle transient rate limits gracefully,
So that operating costs are minimized and transient provider outages do not disrupt user operations.

**Acceptance Criteria:**
**Given** repetitive system prompt templates for extraction and query generation
**When** messages are sent to OpenAI-compatible endpoints
**Then** static system prompt prefixes maintain byte invariance to maximize prompt cache hits.
**And** upstream HTTP 429 and 5xx errors trigger jittered exponential backoff retries before falling back to deterministic regex extraction.

---

## Epic 19: Native Google Gemini Multimodal Provider & Direct Audio Engine

Introduce a dedicated `GeminiProvider` interfacing directly with the Google Generative AI REST and SDK APIs, providing direct multimodal voice note transcription (eliminating the need for Faster-Whisper or cloud Whisper services), token usage logging, and structured schema mapping.

### Story 19.1: Dedicated Gemini Provider Implementation
As an AI Engineer,
I want a native Google Gemini provider that translates internal tool definitions into Gemini function declarations and parses responses cleanly,
So that we have first-class support for Google's latest models without intermediary OpenAI-compatibility layers.

**Acceptance Criteria:**
**Given** `AI_PROVIDER=gemini` and a valid `AI_API_KEY`
**When** `GeminiProvider.extract_transaction()` is executed
**Then** it dispatches calls to the Google Generative AI API with structured function calling.
**And** logs token consumption (`prompt_tokens`, `candidates_tokens`, `total_tokens`).

### Story 19.2: Direct Native Audio Transcription
As a Self-Hoster or SaaS Operator,
I want voice notes processed directly by Gemini without running a local Whisper container or external speech-to-text API,
So that server memory consumption remains <150MB and voice note transcription latency is reduced to <300ms.

**Acceptance Criteria:**
**Given** an incoming `.ogg` voice note from Telegram
**When** `GeminiProvider` processes the audio payload
**Then** it encodes the audio directly in the multimodal prompt content.
**And** extracts financial transactions in a single inference pass without invoking Faster-Whisper or Groq Whisper.

### Story 19.3: Automatic Key Detection & Model Resolution
As a System Administrator,
I want API keys starting with `AIzaSy` to automatically configure the Gemini provider and resolve default models to `gemini-2.5-flash-lite`,
So that setup friction is minimized.

**Acceptance Criteria:**
**Given** `AI_API_KEY` starting with `AIzaSy` and unset `AI_PROVIDER`
**When** `Settings.resolve_ai_defaults()` runs
**Then** `AI_PROVIDER` automatically resolves to `"gemini"`.
**And** `AI_MODEL` and `AI_WHISPER_MODEL` default to `"gemini-2.5-flash-lite"`.

---

## Epic 20: Interactive Telegram Currency Selection & Callback Query Pipeline

Enhance Telegram user experience with interactive inline keyboards, paginated navigation, and Telegram webhook expansion to process `callback_query` updates.

### Story 20.1: Telegram Webhook Callback Query Processing
As a Backend Developer,
I want the Telegram webhook endpoint to receive and process `callback_query` updates,
So that users can interact with inline buttons without experiencing silent timeouts.

**Acceptance Criteria:**
**Given** an incoming webhook payload containing a `callback_query` object
**When** received at `/api/v1/telegram/webhook`
**Then** `TelegramService.answer_callback_query` acknowledges the callback within <1.0 second.
**And** the action is routed to the corresponding handler.

### Story 20.2: Paginated Currency Inline Keyboard
As a User,
I want to type `/currency` and select my household currency from an interactive paginated menu,
So that I don't have to memorize or look up three-letter ISO currency codes.

**Acceptance Criteria:**
**Given** a user typing `/currency` without arguments
**When** `CurrencyHandler.handle_currency_command()` executes
**Then** it responds with an inline keyboard showing popular global currencies (USD, EUR, ARS, GBP, BRL, MXN, etc.) with `◀️ Prev` and `Next ▶️` buttons.
**And** clicking a currency updates the household default currency immediately and edits the message in place.

---

## Epic 21: Three-Tier Pricing Architecture, 60-Day Duo Trial & Daily Fair-Use Quotas

Implement a structured 3-tier subscription model (Solo Pro, Duo Pro, Family Pro), introduce an automatic 60-day Duo Trial for new workspaces, and enforce daily fair-use transaction limits via database tracking and internal maintenance cron jobs.

### Story 21.1: Centralized Subscription Tier Configuration Registry
As a Product Manager,
I want all subscription tier specifications (pricing, member limits, quotas, features) centralized in code,
So that pricing logic is consistent across `/upgrade` menus, landing page displays, and quota validation.

**Acceptance Criteria:**
**Given** `src/core/subscription_config.py`
**When** queried for `solo_pro`, `duo_pro`, or `family_pro`
**Then** it returns structured `SubscriptionTier` objects defining USD prices ($4.99, $7.99, $11.99), annual rates (17% savings), member caps (1, 2, 5), and daily limits (60, 120, 300).

### Story 21.2: 60-Day Duo Trial Experience
As a New User,
I want my new workspace to automatically receive a 60-day Duo trial for up to 2 members,
So that I can test shared budgeting with my partner before deciding to subscribe.

**Acceptance Criteria:**
**Given** a newly registered family workspace in SaaS mode
**When** created by `FamilyService`
**Then** `plan_type` is set to `"trial"` with `trial_ends_at = now() + 60 days`.
**And** allows up to 2 members to join the shared ledger.

### Story 21.3: Daily Transaction Quotas & Internal Maintenance Cron
As a Platform Operator,
I want daily transaction counts tracked per workspace and reset at midnight via an authenticated internal HTTP endpoint,
So that runaway loops or abuse are throttled and trial lifecycles are monitored.

**Acceptance Criteria:**
**Given** Alembic migration `0010_add_family_daily_tx_count.py` adding `daily_tx_count` to `family`
**When** a user logs a transaction, `daily_tx_count` increments.
**And** when `POST /api/internal/jobs/trial-lifecycle` is triggered with `CRON_SECRET`, it resets all counts to 0 and dispatches Day 50 / Day 60 notifications.

---

## Epic 22: Landing Page Web App, Simulation Endpoint & E2E LLM Evaluation Suite

Deploy a public bilingual landing page served by FastAPI, expose an authorized offline message simulation route for testing without Telegram webhooks, and provide an automated LLM evaluation suite.

### Story 22.1: Public Bilingual Landing Page Web Application
As a Visitor,
I want to visit the Clanomy web URL and explore its features, live interactive demo, pricing, and self-hosting documentation in English and Spanish,
So that I understand the value proposition before initiating the Telegram bot.

**Acceptance Criteria:**
**Given** a web browser visiting `/` on the Clanomy FastAPI server
**When** the root route responds
**Then** it serves `landing/index.html` with responsive styles (`landing/styles.css`), dynamic demo script (`landing/script.js`), and bilingual translations (`landing/translations.js`).

### Story 22.2: Authorized Message Simulation Route
As an AI Engineer or Self-Hoster,
I want an HTTP endpoint to test natural language message extraction without configuring Telegram webhooks,
So that I can verify my AI provider configuration and debug prompt handling offline.

**Acceptance Criteria:**
**Given** `POST /simulate/message` with a valid `X-Simulation-Secret` header
**When** a payload with `{"text": "Lunch 15 USD"}` is submitted
**Then** it returns structured JSON with the extraction result, bot response, and execution duration.
**And** unauthorized requests are rejected with HTTP 403.

### Story 22.3: Multilingual LLM Evaluation Harness & Dataset
As a Quality Engineer,
I want an automated evaluation script that tests extraction accuracy across standard financial inputs,
So that we can benchmark LLM providers and detect extraction regressions.

**Acceptance Criteria:**
**Given** `scripts/run_llm_eval.py` and `tests/data/llm_extraction_dataset.py`
**When** executed against a configured LLM provider
**Then** it benchmarks accuracy across expenses, incomes, multi-currency inputs, and compound batches, reporting overall pass rates and token latency.


