# Story 2.2: Ollama JSON Extraction Service

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Developer,
I want to extract structured data from natural language,
so that I can store precise financial records.

## Acceptance Criteria

1. **Structured Data Extraction**: The service must extract the following fields from unstructured natural language text input:
   - `amount`: float (extracted amount, e.g. `15.0`)
   - `category`: str (mapped to one of: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other")
   - `concept`: str (the transaction description, e.g. "Starbucks")
   - `currency`: str (ISO 3-letter currency code, e.g. "USD", "EUR", "GBP", default: "USD" if not specified)
2. **Category Standardization**: The service must map unstructured categories to the standard set. If the input cannot be mapped, it must default to "Other".
3. **Flexible Currency Ingestion**: It must correctly parse multiple currencies (e.g. "10 euros" -> `amount: 10.0`, `currency: "EUR"`; "$15 coffee" -> `amount: 15.0`, `currency: "USD"`).
4. **Structured Output Enforcement**: The service must configure Ollama to return structured JSON adhering to the Pydantic schema using Ollama's schema format enforcement (i.e. passing the Pydantic model's JSON schema to the `format` parameter).
5. **Non-Blocking API Calls**: The service must interact with Ollama asynchronously (e.g., using `ollama.AsyncClient` or wrapping synchronous calls in `asyncio.to_thread`) to prevent blocking FastAPI's main event loop.
6. **Robust Validation & Error Handling**: Invalid/empty model responses or JSON parsing errors must raise a custom exception `ExtractionError`.
7. **3s Audit Logging**: Measure and log execution duration under the `[3s Audit]` prefix: `[3s Audit] Ollama extraction took X.XX seconds (model: {model})`.
8. **Configurability**: Configuration values `OLLAMA_BASE_URL` and `OLLAMA_MODEL` must be loaded from environment variables via `src/core/config.py` with safe defaults (`http://localhost:11434` and `llama3`).
9. **Unit Testing**: Include tests mocking the Ollama API calls to verify all success paths, validation logic, and extraction failures.

## Tasks / Subtasks

- [x] **Configuration Updates** (AC: 8)
  - [x] Add `OLLAMA_BASE_URL` and `OLLAMA_MODEL` to `Settings` class in `src/core/config.py` with defaults (`"http://localhost:11434"` and `"llama3"`).
  - [x] Add Pydantic field validators to ensure config values are valid.
  - [x] Update `.env.example` with the new environment variables and explanations of valid values.
- [x] **Extraction Service Implementation** (AC: 1, 2, 3, 4, 5, 6, 7, 8)
  - [x] Create `src/services/extraction_service.py`.
  - [x] Define the extraction Pydantic model `ExtractionResult` containing `amount`, `category`, `concept`, and `currency`.
  - [x] Implement `ExtractionService` as a singleton pattern.
  - [x] Implement `extract` method accepting `text: str` and returning `ExtractionResult`.
  - [x] Initialize `ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)` and use it to call the model.
  - [x] Enforce the Pydantic model's JSON schema using the `format` option in the client chat/generate method to restrict the LLM to valid JSON.
  - [x] Design a clear system prompt for the extraction, describing the fields and the allowed category values.
  - [x] Wrap API execution in a try...except block, handling network errors and parsing failures. Raise a custom exception `ExtractionError`.
  - [x] Add a `[3s Audit]` metric logger tracking the start time, end time, and outputting the duration of the Ollama request.
- [x] **Testing Suite** (AC: 9)
  - [x] Create `tests/services/test_extraction_service.py`.
  - [x] Test the happy path using a mocked Ollama client response (verify correct parsing to Pydantic object).
  - [x] Test various currency and category mappings (e.g. "10 euros for lunch" -> `amount: 10.0`, `currency: "EUR"`, `category: "Food/Drink"`).
  - [x] Test extraction error paths (Ollama offline, malformed output).

### Review Findings

- [x] [Review][Patch] Weak URL validation in config Settings [src/core/config.py:35-40]
- [x] [Review][Patch] Redundant classmethod decorators on field validators [src/core/config.py:27-47]
- [x] [Review][Patch] Non-thread-safe singleton implementation [src/services/extraction_service.py:77-84]
- [x] [Review][Patch] Missing validation on input text parameter [src/services/extraction_service.py:92]
- [x] [Review][Patch] Missing code-level category normalization and fallback mapping [src/services/extraction_service.py:73]
- [x] [Review][Patch] Missing code-level currency validation and mapping [src/services/extraction_service.py:75]
- [x] [Review][Patch] Missing bounds validation on transaction amount [src/services/extraction_service.py:72]
- [x] [Review][Patch] Missing Ollama client request timeout [src/services/extraction_service.py:107]
- [x] [Review][Patch] Mismatched timing log audit prefix string [src/services/extraction_service.py:133]
- [x] [Review][Patch] Narrow exception block on network/connection errors [src/services/extraction_service.py:123]
- [x] [Review][Defer] Missing LLM request retry/fallback mechanisms [src/services/extraction_service.py:107] — deferred, pre-existing
- [x] [Review][Defer] Lack of secondary parsing fallback on Pydantic validation failure [src/services/extraction_service.py:120] — deferred, pre-existing

## Dev Notes

- **Ollama Async Integration**: Use `ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)` to handle the communication asynchronously without blocking FastAPI.
- **Structured Outputs via JSON Schema**: Ollama Python library supports passing `ExtractionResult.model_json_schema()` to the `format` parameter of the chat/generate calls. This guarantees that Ollama restricts its response to the exact schema, making parsing extremely safe and reducing JSON formatting errors.
- **System Prompt Design**:
  Use a clear system prompt telling the model to act as a financial data extraction parser. Mention:
  - Allowed categories: "Food/Drink", "Transport", "Rent/Bills", "Shopping", "Leisure", "Other".
  - Currencies must be translated to their standard ISO 3-letter codes (e.g., "euros" -> "EUR", "dollars" -> "USD", "pounds" -> "GBP").
- **3s Audit format**: Log in this format: `[3s Audit] Ollama JSON extraction took X.XX seconds (model: {model})`.
- **Validation**: After receiving the response from Ollama, load and validate it with `ExtractionResult.model_validate_json(response.message.content)`.

### Project Structure Notes

- **Service Location**: `src/services/extraction_service.py` is the service file.
- **Config Location**: `src/core/config.py` holds settings class.
- **Tests Location**: `tests/services/test_extraction_service.py`.

### References

- [Architecture: Inference Engine](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L100)
- [Architecture: Project Directory Structure](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L196)
- [Epics: Story 2.2](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L181)
- [PRD: Latency & Local Processing](file:///C:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/prd.md#L121)

## Dev Agent Record

### Agent Model Used

Gemini 3.5 Flash (High)

### Debug Log References

### Completion Notes List

- Implemented `ExtractionService` using `ollama.AsyncClient` for asynchronous data extraction.
- Enforced JSON schema for structured output using Pydantic model `ExtractionResult`.
- Mapped extracted data to proper amounts, categories, concepts, and ISO currency codes.
- Implemented `ExtractionError` for robust error handling.
- Added comprehensive test suite with `pytest.mark.anyio` which passed successfully.

### File List
- `src/core/config.py`
- `.env.example`
- `src/services/extraction_service.py`
- `tests/services/test_extraction_service.py`
