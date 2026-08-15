---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - c:\Users\cresp\Documents\Projectos\FamFin-AI\_bmad-output\planning-artifacts\prd.md
  - c:\Users\cresp\Documents\Projectos\FamFin-AI\_bmad-output\planning-artifacts\architecture.md
workflowType: 'epics-and-stories'
status: 'complete'
completedAt: '2026-05-09'
---

# FamFin-AI - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for FamFin-AI, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

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

### NonFunctional Requirements

NFR1: 95% of logs confirmed within 3 seconds of input reception. (Latency)
NFR2: STT/LLM pipeline must run on consumer-grade local hardware. (Efficiency)
NFR3: 100% of transaction descriptions and amounts encrypted at rest. (Encryption)
NFR4: Zero transmission of raw audio or transaction data to third-party AI APIs. (Local-Only)
NFR5: All integration tokens (Notion/Bot) stored in encrypted environment variables. (Secrets)
NFR6: Transactional DB writes to ensure zero data loss on system failure. (Persistence)
NFR7: Daily automated encrypted backups to external storage. (Backup)
NFR8: Retry mechanisms for Notion mirroring (eventual consistency). (Consistency)

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
