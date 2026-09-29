# Story 1.2: Application-Level AES-256 Encryption Service

Status: done

## Story

As a Security-Conscious User,
I want my financial data to be encrypted before it hits the database,
so that my privacy is guaranteed even if the database is compromised.

## Acceptance Criteria

1. **Given** a plaintext string (e.g., "$15 Coffee"), **when** I pass it through the `EncryptionService.encrypt()` method, **then** it returns a base64-encoded ciphertext string.
2. **And** the `EncryptionService.decrypt()` method correctly reverts the ciphertext back to the original plaintext string.
3. **And** the service uses the `ENCRYPTION_KEY` from the `.env` file (loaded via `src/core/config.py`).
4. **And** the implementation uses the `cryptography` library's `Fernet` recipe as specified in the Architecture Decision Document.
5. **And** the service handles `InvalidToken` errors gracefully (e.g., when trying to decrypt with the wrong key).

## Tasks / Subtasks

- [x] **Service Implementation** (AC: 1, 2, 4)
  - [x] Implement `EncryptionService` class in `src/core/encryption.py`.
  - [x] Initialize `Fernet` using the key from `settings.ENCRYPTION_KEY`.
  - [x] Implement `encrypt(plaintext: str) -> str` method (handling string-to-bytes conversion).
  - [x] Implement `decrypt(ciphertext: str) -> str` method (handling bytes-to-string conversion).
- [x] **Configuration Integration** (AC: 3)
  - [x] Ensure `src/core/config.py` correctly exposes `ENCRYPTION_KEY`.
  - [x] Provide a helper method or CLI command to generate a valid Fernet key for `.env` setup.
- [x] **Unit Testing** (AC: 1, 2, 5)
  - [x] Create `tests/services/test_encryption.py`.
  - [x] Test round-trip encryption/decryption for strings and special characters.
  - [x] Test decryption failure when using an incorrect key.
- [x] **Verification** (AC: 4)
  - [x] Verify that stored ciphertext in the database (simulated in tests) is not human-readable.

### Review Findings

- [x] [Review][Patch] Unhandled `InvalidToken` Exception [`src/core/encryption.py`:28]
- [x] [Review][Patch] Missing `None` type guard on `encrypt()` [`src/core/encryption.py`:13]
- [x] [Review][Patch] Unhandled `ValueError` for non-base64 ciphertext [`src/core/encryption.py`:28]
- [x] [Review][Patch] Application crash on invalid `ENCRYPTION_KEY` [`src/core/encryption.py`:7]
- [x] [Review][Patch] Missing standalone CLI key generation script [`src/core/encryption.py`:32]
- [x] [Review][Patch] Brittle test string in `test_encryption_invalid_token` [`tests/services/test_encryption.py`:27]
- [x] [Review][Patch] Unused import in `test_encryption.py` [`tests/services/test_encryption.py`:3]

## Dev Notes

- **Library Choice:** As per `architecture.md`, use `cryptography.fernet.Fernet`. Note: While the PRD mentions "AES-256", Fernet specifically uses AES-128 in CBC mode with HMAC-SHA256 for authenticated encryption. We follow the explicit instruction to use Fernet for its high-level security guarantees.
- **Service Layer:** The class should be stateless or initialized once with the key.
- **Key Format:** Fernet keys MUST be 32 URL-safe base64-encoded bytes.
- **Testing:** Use `pytest` for the service tests.

### Project Structure Notes

- **Location:** `src/core/encryption.py` (placeholder already exists).
- **Naming:** `EncryptionService` (PascalCase), `encrypt`/`decrypt` (snake_case).
- **Dependencies:** `cryptography` is already in `requirements.txt`.

### References

- [Architecture: Data Architecture](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L112)
- [Architecture: Project Structure](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/architecture.md#L192)
- [Epics: Story 1.2](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/_bmad-output/planning-artifacts/epics.md#L124)

## Dev Agent Record

### Agent Model Used

Gemini 1.5 Pro

### Debug Log References

- [pytest results](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/tests/services/test_encryption.py) - 3 tests passed.
- [Key generation](file:///c:/Users/cresp/Documents/Projectos/FamFin-AI/.env) - Validated Fernet key added.

### Completion Notes List

- Implemented `EncryptionService` using `cryptography.fernet.Fernet`.
- Added `generate_key` static method for easier setup.
- Updated `.env` and `.env.example` with instructions.
- Verified round-trip encryption/decryption including special characters (emoji, accents).
- Verified `InvalidToken` handling for corrupted/incorrect tokens.

### File List
- `src/core/encryption.py`
- `tests/services/test_encryption.py`
- `.env`
- `.env.example`
