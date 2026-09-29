# Story 6.2: Real-Time Log Mirroring

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User,
I want every new financial log I make in Telegram to automatically appear as a new row in my connected Notion database,
so that my Notion financial dashboard and workspace are always in sync without manual entry.

## Acceptance Criteria

1. **Notion Transaction Mirroring Method (`NotionService.mirror_transaction`)**:
   - Implement `mirror_transaction` in `src/services/notion_service.py`:
     - Method signature:
       ```python
       async def mirror_transaction(
           self,
           family_id: UUID,
           amount: float,
           currency: str,
           concept: str,
           category: str,
           timestamp: datetime,
           user_name: Optional[str] = None
       ) -> Optional[Dict[str, Any]]:
       ```
     - Checks if the family has Notion connected (`family.notion_api_key` and `family.notion_database_id`). If not connected or missing credentials, returns `None` without raising an exception.
     - Decrypts `family.notion_api_key` in memory using `EncryptionService.decrypt()`.
     - Dynamically discovers or maps database schema properties to adapt to the user's Notion database structure (see AC 2).
     - Calls `await notion.pages.create(parent={"database_id": database_id}, properties=payload_properties)` using `notion_client.AsyncClient`.
     - Returns a dictionary with the created page details: `{"page_id": page["id"], "url": page.get("url"), "status": "mirrored"}`.

2. **Adaptive Notion Property Mapping**:
   - The mirroring service must construct a valid Notion page properties payload that matches the schema of the connected database:
     - **Title property** (exact property where `type == "title"`, e.g., `"Concept"`, `"Name"`, `"Title"`, `"Description"`, `"Expense"`):
       `{"title": [{"text": {"content": concept}}]}`
     - **Amount property** (property named `"Amount"`, `"Cost"`, `"Price"`, `"Value"`, `"Total"` case-insensitively):
       - If `type == "number"`: `{"number": float(amount)}`
       - If `type == "rich_text"`: `{"rich_text": [{"text": {"content": f"{amount:.2f} {currency}"}}]}`
     - **Category property** (property named `"Category"`, `"Tag"`, `"Tags"`, `"Type"` case-insensitively):
       - If `type == "select"`: `{"select": {"name": category}}`
       - If `type == "multi_select"`: `{"multi_select": [{"name": category}]}`
       - If `type == "rich_text"`: `{"rich_text": [{"text": {"content": category}}]}`
     - **Date property** (property named `"Date"`, `"Timestamp"`, `"Created"`, `"Time"` case-insensitively):
       - If `type == "date"`: `{"date": {"start": timestamp.isoformat()}}`
     - **Currency property** (property named `"Currency"` case-insensitively, if present):
       - If `type == "select"`: `{"select": {"name": currency}}`
       - If `type == "rich_text"`: `{"rich_text": [{"text": {"content": currency}}]}`
     - **Member / User property** (property named `"Member"`, `"User"`, `"Logged By"`, `"Author"`, `"Who"` case-insensitively, if present and `user_name` provided):
       - If `type == "rich_text"`: `{"rich_text": [{"text": {"content": user_name}}]}`
       - If `type == "select"`: `{"select": {"name": user_name}}`
   - If database schema details cannot be retrieved or dynamic mapping fails, fallback to standard default properties (`Concept` / `Name` as title, `Amount` as number, `Category` as select, `Date` as date, `Currency` as select).

3. **Asynchronous Non-Blocking Orchestration in `AIOrchestrator`**:
   - In `src/services/ai_orchestrator.py`:
     - When an expense transaction is successfully saved to the local PostgreSQL/SQLite database (`_persist_transaction`):
       - Check if the user's family has Notion connected.
       - If Notion is connected, trigger the mirroring operation asynchronously (e.g. via `asyncio.create_task` or non-blocking async call) so it does NOT block the Telegram confirmation message.
       - Pass decrypted transaction details (`amount`, `currency`, `concept`, `category`, `timestamp`, `user_name`).
       - Ensure `[3s Audit]` latency logging captures both the local persistence time and the background Notion mirroring time.

4. **Fault Isolation & Error Handling**:
   - If Notion API mirroring fails (due to network timeout, 401 unauthorized, 404 database not found, 429 rate limit, or Notion schema mismatches):
     - The error must be caught and logged with `[Notion Mirror]` and `[3s Audit]` prefix (e.g. `logger.error("[Notion Mirror] Failed to mirror transaction for family %s: %s", family_id, e)`).
     - Local database persistence and the user's Telegram confirmation message MUST NOT be failed or rolled back.
     - The system maintains local data integrity as the single source of truth.

5. **Diagnostic & Manual Mirror Commands (`/notion test`, `/notion sync`)**:
   - Support test and manual verification commands in `AIOrchestrator`:
     - `/notion test` or `notion test`:
       - Checks if family has Notion connected. If not, returns guidance to run `/notion`.
       - If connected, creates a test entry in Notion (e.g., `Concept: "FamFin Test Entry"`, `Amount: 0.00`, `Category: "Test"`, `Date: now`).
       - Replies with confirmation: `✅ <b>Notion Mirror Test Successful!</b>\nCreated test record in database: <b>{database_name}</b>\n🔗 <a href="{page_url}">View in Notion</a>`
     - `/notion sync` or `notion sync`:
       - Confirms Notion connection is active and reports that real-time mirroring is enabled for all new transactions.

6. **Comprehensive Test Suite**:
   - `tests/services/test_notion_service.py`:
     - Test `mirror_transaction` when Notion is not connected (returns `None`).
     - Test `mirror_transaction` with successful page creation, asserting property structure (title, number, select, date, rich_text).
     - Test adaptive schema mapping when target database uses alternative property names (e.g. `"Name"` instead of `"Concept"`, `"Expense"` instead of `"Amount"`).
     - Test error handling when `notion.pages.create` raises `APIResponseError` or network error (ensures proper logging and non-crash).
     - Test `test_connection_mirror` method.
   - `tests/services/test_ai_orchestrator.py`:
     - Test expense logging when Notion is connected: verify transaction is saved locally AND mirrored to Notion.
     - Test expense logging when Notion is not connected: verify transaction is saved locally and no mirror call occurs.
     - Test expense logging when Notion mirroring raises an exception: verify local transaction is still saved and Telegram reply still succeeds.
     - Test `/notion test` command response for both connected and disconnected states.
   - Verify 100% test pass rate across the test suite (`.\venv\Scripts\python -m pytest`).

## Tasks / Subtasks

- [x] **Notion Service Mirroring Implementation** (AC: 1, 2, 4)
  - [x] Implement `mirror_transaction()` in `src/services/notion_service.py` with parameter validation and encrypted token decryption.
  - [x] Implement `_build_page_properties()` helper in `src/services/notion_service.py` to adaptively map concept, amount, category, date, currency, and member to Notion database schema.
  - [x] Implement `test_connection_mirror()` helper in `src/services/notion_service.py` for diagnostic verification.
  - [x] Add structured logging with `[Notion Mirror]` and `[3s Audit]` tags and custom error trapping.
- [x] **AI Orchestrator Real-Time Mirroring Integration** (AC: 3, 4, 5)
  - [x] Update `AIOrchestrator.orchestrate` in `src/services/ai_orchestrator.py` to trigger `mirror_transaction` after local persistence succeeds.
  - [x] Retrieve author user display name (`user.full_name` or `user.username`) to include member attribution.
  - [x] Ensure non-blocking execution using `asyncio.create_task` or safe async wrapper so Telegram reply is never delayed.
  - [x] Add command handling for `/notion test` and `/notion sync` in `AIOrchestrator`.
- [x] **Comprehensive Test Suite & Verification** (AC: 6)
  - [x] Add unit tests in `tests/services/test_notion_service.py` for `mirror_transaction`, schema adaptation, error resilience, and `test_connection_mirror`.
  - [x] Add integration tests in `tests/services/test_ai_orchestrator.py` for real-time mirroring during expense logging and `/notion test` command.
  - [x] Run full test suite with `.\venv\Scripts\python -m pytest` and verify 100% pass rate.

### Review Findings

- [x] [Review][Patch] Notion background task initialization error handling in ai_orchestrator.py [`src/services/ai_orchestrator.py:372`]

## Dev Notes

### Architecture & Service Design

- **Flow Diagram**:
  ```
  Telegram Message ("50 for groceries")
         │
         ▼
  FastAPI Webhook ──(200 OK immediate ack)
         │
         ▼ (BackgroundTasks)
  AIOrchestrator.orchestrate()
         │
         ├─► WhisperService (if audio)
         ├─► ExtractionService (Ollama JSON extraction)
         │
         ├─► _persist_transaction() ──► PostgreSQL/SQLite (Encrypted Amount & Concept)
         │
         ├─► TelegramService.send_message() ──► User gets instant confirmation
         │
         └─► (Non-blocking Task) NotionService.mirror_transaction()
                   │
                   ├─► Check Family.notion_api_key & notion_database_id
                   ├─► Decrypt token in memory via EncryptionService.decrypt()
                   ├─► Fetch/Cache database property schema
                   ├─► Build adaptive property payload
                   └─► Notion AsyncClient.pages.create() ──► Notion Database Row
  ```

- **Notion SDK Page Creation (`notion_client.AsyncClient`)**:
  ```python
  from notion_client import AsyncClient, APIResponseError

  async def mirror_transaction(
      self,
      family_id: UUID,
      amount: float,
      currency: str,
      concept: str,
      category: str,
      timestamp: datetime,
      user_name: Optional[str] = None
  ) -> Optional[Dict[str, Any]]:
      family = self.session.get(Family, family_id)
      if not family or not family.notion_api_key or not family.notion_database_id:
          return None

      api_key = self.encryption.decrypt(family.notion_api_key)
      database_id = family.notion_database_id

      async with AsyncClient(auth=api_key) as notion:
          try:
              # Get db details to know property types and names
              db_details = await self.get_database_details(api_key, database_id)
              properties_payload = self._build_page_properties(
                  schema=db_details.get("properties_schema", {}),
                  concept=concept,
                  amount=amount,
                  currency=currency,
                  category=category,
                  timestamp=timestamp,
                  user_name=user_name
              )
              
              page = await notion.pages.create(
                  parent={"database_id": database_id},
                  properties=properties_payload
              )
              logger.info(f"[Notion Mirror] Mirrored transaction to page {page['id']} for family {family_id}")
              return {"page_id": page["id"], "url": page.get("url"), "status": "mirrored"}
          except Exception as e:
              logger.error(f"[Notion Mirror] Failed to mirror transaction for family {family_id}: {e}")
              return None
  ```

- **Adaptive Property Payload Construction**:
  Notion databases require exactly one `"title"` property. Other properties may vary based on how the user created their table.
  ```python
  def _build_page_properties(
      self,
      schema: Dict[str, Any],
      concept: str,
      amount: float,
      currency: str,
      category: str,
      timestamp: datetime,
      user_name: Optional[str] = None
  ) -> Dict[str, Any]:
      payload = {}
      
      # 1. Title property (mandatory for Notion page creation)
      title_prop_name = None
      for name, prop_info in schema.items():
          if isinstance(prop_info, dict) and prop_info.get("type") == "title":
              title_prop_name = name
              break
      if not title_prop_name:
          title_prop_name = "Concept" if "Concept" in schema else ("Name" if "Name" in schema else "Title")
      payload[title_prop_name] = {"title": [{"text": {"content": concept or "Expense"}}]}

      # 2. Iterate remaining properties in schema
      for name, prop_info in schema.items():
          if name == title_prop_name:
              continue
          p_type = prop_info.get("type") if isinstance(prop_info, dict) else prop_info
          name_lower = name.lower()

          # Amount
          if name_lower in ["amount", "cost", "price", "value", "total", "expense"]:
              if p_type == "number":
                  payload[name] = {"number": float(amount)}
              elif p_type == "rich_text":
                  payload[name] = {"rich_text": [{"text": {"content": f"{amount:.2f} {currency}"}}]}

          # Category
          elif name_lower in ["category", "tag", "tags", "type"]:
              if p_type == "select":
                  payload[name] = {"select": {"name": category}}
              elif p_type == "multi_select":
                  payload[name] = {"multi_select": [{"name": category}]}
              elif p_type == "rich_text":
                  payload[name] = {"rich_text": [{"text": {"content": category}}]}

          # Date
          elif name_lower in ["date", "timestamp", "created", "time", "when"]:
              if p_type == "date":
                  payload[name] = {"date": {"start": timestamp.isoformat()}}

          # Currency
          elif name_lower in ["currency"]:
              if p_type == "select":
                  payload[name] = {"select": {"name": currency}}
              elif p_type == "rich_text":
                  payload[name] = {"rich_text": [{"text": {"content": currency}}]}

          # Member / Author
          elif name_lower in ["member", "user", "logged by", "author", "person", "who"] and user_name:
              if p_type == "rich_text":
                  payload[name] = {"rich_text": [{"text": {"content": user_name}}]}
              elif p_type == "select":
                  payload[name] = {"select": {"name": user_name}}

      return payload
  ```

### Source Files to Touch

#### [MODIFY] [src/services/notion_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/notion_service.py)
- **Current State**: Contains token validation, database searching, connection and status management. `get_database_details` returns property names as a list.
- **Changes for Story 6.2**:
  - Update `get_database_details` to also return `properties_schema: Dict[str, Any]` containing property types for schema discovery.
  - Add `_build_page_properties(self, schema, concept, amount, currency, category, timestamp, user_name)` for dynamic payload generation.
  - Add `mirror_transaction(self, family_id, amount, currency, concept, category, timestamp, user_name)` to create Notion database pages asynchronously.
  - Add `test_connection_mirror(self, family_id)` to create a test database page for diagnostics.
- **Preserve**: All existing methods (`validate_token`, `search_databases`, `connect_database`, `disconnect_workspace`, `get_family_notion_status`) and exception classes (`NotionAuthError`, `NotionDatabaseNotFoundError`, `NotionServiceError`).

#### [MODIFY] [src/services/ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/src/services/ai_orchestrator.py)
- **Current State**: Extracts expenses, encrypts and saves them to SQLite/Postgres, handles conversational queries, family management, and `/notion connect/setdb/status/disconnect`.
- **Changes for Story 6.2**:
  - After saving an expense transaction in `orchestrate()`, retrieve `user.family_id` and `user.full_name` (or `username`), and spawn a background task:
    ```python
    asyncio.create_task(self._safe_mirror_to_notion(
        family_id=user.family_id,
        amount=result.amount,
        currency=result.currency,
        concept=result.concept,
        category=result.category,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        user_name=user_display_name
    ))
    ```
  - Implement `_safe_mirror_to_notion(...)` helper that instantiates `NotionService` with a fresh session, calls `mirror_transaction`, and catches/logs all exceptions without propagating.
  - Add handlers in `parsed_query.intent == "notion_manage"` for `/notion test` and `/notion sync`.
- **Preserve**: All existing routing for `/createfamily`, `/invite`, `/family`, `/familytotal`, export, delete account, and `/notion connect/setdb/status/disconnect`.

#### [MODIFY] [tests/services/test_notion_service.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_notion_service.py)
- **Changes for Story 6.2**:
  - Add unit tests for `mirror_transaction` covering successful page creation, property formatting, missing connection handling (returns `None`), and API error handling.
  - Add unit tests for `_build_page_properties` verifying adaptive matching of custom database schemas (e.g., `"Name"`, `"Cost"`, `"Tags"`, `"Date"`, `"Member"`).
  - Add unit tests for `test_connection_mirror`.

#### [MODIFY] [tests/services/test_ai_orchestrator.py](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_ai_orchestrator.py)
- **Changes for Story 6.2**:
  - Add integration tests verifying that when a family has Notion configured, logging an expense triggers `mirror_transaction`.
  - Add test verifying that when Notion mirroring fails, local transaction is still persisted and user still receives Telegram confirmation.
  - Add test verifying `/notion test` and `/notion sync` command responses.

### Anti-Patterns to Prevent

- **Blocking the Event Loop**: Never await Notion API calls directly in the main request handler before sending the Telegram reply. Mirroring must run in background (`asyncio.create_task` or FastAPI `BackgroundTasks`) to maintain the 3-second SLA (NFR1).
- **Session Leak / Cross-Thread Session Use**: When creating background tasks in `_safe_mirror_to_notion`, create a dedicated `Session(engine)` inside the task to avoid concurrent access on the caller's session.
- **Coupling Local Persistence to Notion Availability**: If Notion is down or API credentials expire, local expense persistence must NOT fail. Local PostgreSQL is the system of record.
- **Assuming Hardcoded Notion Properties**: Never assume a Notion database has fixed property names. Always detect the `"title"` property dynamically and match amount, category, date, and currency flexibly.
- **Exposing Decrypted Secrets in Logs**: Never log the decrypted Notion API token or raw PII in operational logs.

### References

- [Epics: Story 6.2 (Real-Time Log Mirroring)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L363-L375)
- [PRD: Integrated Dashboard (FR12, FR13, Journey 3.3)](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L63-L65)
- [Architecture: Notion Sync Worker & Boundaries](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L28-L38)
- [Story 6.1: Notion Workspace Connection](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/6-1-notion-workspace-connection.md)
- [Story 5.3: Per-Member Spending Attribution](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/implementation-artifacts/5-3-per-member-spending-attribution.md)

## Dev Agent Record

### Agent Model Used

Gemini 3.7 Flash (High)

### Debug Log References
None

### Completion Notes List
- Implemented `mirror_transaction` in `NotionService` for async page creation.
- Added adaptive mapping of properties (`_build_page_properties`) ensuring correct schema validation for user databases.
- Integrated `_safe_mirror_to_notion` in `AIOrchestrator` to seamlessly sync transactions to Notion using an asyncio background task.
- Included `/notion test` and `/notion sync` command processing.
- Verified functionality through pytest coverage updates with 100% pass rate.

### Change Log
- Added `mirror_transaction`, `_build_page_properties`, and `test_connection_mirror` methods to `src/services/notion_service.py`.
- Updated `AIOrchestrator.orchestrate` to trigger Notion mirroring without blocking the Telegram reply.
- Expanded test suites in `tests/services/test_notion_service.py` and `tests/services/test_ai_orchestrator.py`.

### File List
- src/services/notion_service.py
- src/services/ai_orchestrator.py
- tests/services/test_notion_service.py
- tests/services/test_ai_orchestrator.py
