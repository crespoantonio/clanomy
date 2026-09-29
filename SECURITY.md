# Security Policy & Vulnerability Disclosure

Clanomy is committed to ensuring the highest standards of security, privacy, and data sovereignty for individuals and families managing household finances. We believe in proactive, transparent, and collaborative security practices and deeply value the contributions of the ethical security research community.

---

## 🛡️ Supported Versions

Only the latest release on the primary branch is actively maintained with security patches. Users running self-hosted instances should ensure they are pulling the latest release tags or container images.

| Version | Status | Security Updates |
| :--- | :--- | :--- |
| `1.0.x` (Latest Release) | Active | :white_check_mark: Supported |
| `< 1.0.0` (Development/Pre-release) | End of Life | :x: Not Supported (Please upgrade) |

---

## 🔒 Reporting a Vulnerability or Issue

Vulnerabilities, security concerns, and issues must be reported directly through **GitHub Issues** or via our direct security contact.

### 1. GitHub Issues
To submit a vulnerability report or security issue:
1. Navigate to the **[Issues tab](https://github.com/crespoantonio/clanomy/issues)** of the repository.
2. Click **"New Issue"**.
3. Fill out the report with clear reproduction steps, affected components, and potential impact.

*(Note: Please do not submit reports via the GitHub Security Tab; all reports should be filed via GitHub Issues or direct email).*

### 2. Direct Security Contact
If you prefer direct communication or require confidential handling, send an email to:
- **Security Contact:** `support@clanomy.com`
- **Subject Line:** `[SECURITY / ISSUE] Clanomy Vulnerability Disclosure - <Component/Route>`

---

## 📋 What to Include in Your Report

To help us rapidly triage and remediate the issue, please include as much of the following as possible:
- **Type of Issue:** (e.g., Remote Code Execution, Authentication Bypass, Secret Leakage, SQL/Command Injection, Path Traversal, SSRF, Insecure Direct Object Reference).
- **Affected Component:** Exact file paths, routes, API endpoints, or database queries.
- **Proof of Concept (PoC):** Step-by-step instructions or non-destructive reproduction steps.
- **Impact Assessment:** What an attacker could achieve if the vulnerability were exploited in production.
- **Suggested Remediation:** Any recommended code diffs, architectural changes, or configuration hardening.

---

## ⏱️ Response & Triage SLA

We treat security disclosures with the highest priority and commit to the following response timeline:

- **Initial Acknowledgment:** Within **48 hours** of receiving the report.
- **Triage & Impact Assessment:** Within **5 business days**, confirming whether the issue is reproducible and establishing severity using CVSS v3.1.
- **Remediation & Patch:** Target fix delivered within **14 calendar days** for Critical/High severity issues, and within **30 days** for Medium/Low issues.
- **Coordinated Resolution:** Once a fix is verified and deployed, we will update the relevant issue/release notes crediting the reporter.

---

## 🎯 Scope & Boundaries

### In Scope
- Core FastAPI application logic, route handlers, and middleware (`src/`).
- Telegram Webhook authentication and callback processing (`/api/v1/telegram/`).
- Paddle Billing webhook verification, checkout generation, and subscription tier lifecycles (`/api/v1/paddle/`).
- Internal background maintenance jobs and authentication (`/api/internal/jobs/`).
- Cryptographic implementations: AES-256 field encryption (`Fernet`), constant-time signature verifications, and key management.
- Multi-tenancy isolation and database row-level security (RLS).
- Containerization security (`Containerfile`, `docker-compose.yaml`, `.dockerignore`).
- GitHub Actions CI/CD workflows and supply-chain dependencies.

### Out of Scope
- Distributed Denial of Service (DDoS) attacks against hosting infrastructure (e.g., Render, Cloudflare, Telegram servers).
- Spam or rate-limit probing without demonstrable security bypass.
- Social engineering, phishing, or physical attacks against maintainers or users.
- Vulnerabilities in third-party services (Telegram Bot API, Paddle, Supabase, Groq, Google Gemini) unless directly caused by our integration implementation.

---

## ⚖️ Safe Harbor / Researcher Protection

We consider security research conducted under this policy to be authorized. We pledge that:
- We will not pursue legal action against researchers who make a good-faith effort to comply with this disclosure policy.
- We will work collaboratively with you to understand and resolve the issue.
- We will acknowledge your responsible disclosure publicly in our release notes or issue tracker (unless you prefer to remain anonymous).

*Guidelines for Safe Harbor compliance:*
- Act in good faith to avoid privacy violations, data destruction, and service degradation.
- Only interact with accounts, family workspaces, or instances that you own or have explicit permission to test against.
- Do not access, modify, or exfiltrate another user's financial transactions or personal records.
- Provide reasonable time for maintainers to remediate the vulnerability before disclosing details publicly.

---

## 🔐 Architectural Security Highlights

For researchers and enterprise users auditing our architecture, Clanomy implements the following defensive controls by default:
- **Zero-Knowledge Encryption at Rest:** Financial transaction amounts, concepts, and sensitive notes are encrypted with application-layer AES-256 (`Fernet`) before being written to PostgreSQL.
- **Row-Level Security (RLS):** All database tables have RLS enabled with schema-level revocation from untrusted roles.
- **Timing Attack Resistance:** All webhook verification tokens, job secrets, and origin keys use constant-time comparison (`secrets.compare_digest`).
- **Formula & Injection Neutralization:** CSV data exports neutralize spreadsheet formula injection (`=`, `+`, `-`, `@`, `\t`).
- **Prompt Injection Defense:** Natural language query and extraction pipelines sanitize Markdown code fences and strip XML boundary tokens (`<user_input>`, `<system_context>`) before LLM inference.
- **Least Privilege Pipelines:** GitHub Actions workflows run with minimal read-only permissions (`contents: read`) and enforce integrity guardrails on protected files.
