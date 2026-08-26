# Contributing to Clanomy 💰🤝

Thank you for your interest in contributing to Clanomy! We welcome community contributions to help make privacy-first, local AI financial tracking better for everyone.

---

## 🌟 Areas We Welcome Contributions For

We encourage contributions in the following areas:
- **Bug fixes & Performance Improvements**
- **New AI Extraction Prompts & Natural Language Query Enhancements**
- **Additional Data Export Formats (e.g., SQLite, Excel, OFX)**
- **Test Coverage Expansion & Edge Case Hunting**
- **Self-Hosting Guides & Non-Branded Technical Documentation**

---

## 🔒 Protected Core Areas & Policy

Clanomy operates on an **open-core model**. To protect project integrity, security, and stability:
- **Core Billing & Quotas (`src/services/subscription_service.py`)**: Maintained exclusively by the core maintainers.
- **Project Branding & Root Documentation (`README.md`, `.github/workflows/`)**: Managed by the project owner.
- Pull requests attempting to modify protected core files or internal workflows are automatically rejected by our CI guardrails.

---

## 🛠️ Local Development & Testing

### 1. Prerequisites
- **Podman** (or Docker) & `podman-compose` / `docker-compose`
- Python 3.12+

### 2. Running Tests
Always run the full test suite inside the container before opening a PR:
```bash
# Start environment
podman compose up -d

# Run test suite
podman compose exec app pytest
```

### 3. Submitting a Pull Request
1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-enhancement
   ```
2. Write clean code adhering to existing project architecture.
3. Add unit/integration tests for your changes.
4. Ensure 100% of the test suite passes and project code coverage remains **>= 85%**.
5. Push to your fork and submit a Pull Request with a clear description of the problem and solution.
