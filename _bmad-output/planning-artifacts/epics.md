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

### Epic 7: Monetization & Subscriptions
Enable in-app subscriptions using Telegram Stars. Free users can upgrade to Solo Pro or Family Pro to unlock unlimited transactions and premium features.
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
