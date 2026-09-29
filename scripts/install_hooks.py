#!/usr/bin/env python3
"""
Install Clanomy Git Security Pre-Commit Hooks.
Ensures developers never accidentally commit .env files, SQLite databases, or raw secrets.
"""

import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = PROJECT_ROOT / ".git" / "hooks" / "pre-commit"

HOOK_CONTENT = """#!/usr/bin/env bash
# Clanomy Pre-Commit Hook: Guardrail against secret leaks and .env file commits

echo "🔍 Running pre-commit security checks..."

# 1. Block any .env files from being committed (except .env.example)
STAGED_ENV_FILES=$(git diff --cached --name-only | grep -E "(^|/)\.env(\..+)?$" | grep -v "\.env\.example$" || true)

if [ -n "$STAGED_ENV_FILES" ]; then
    echo "❌ [PRE-COMMIT BLOCKED] Attempted to commit sensitive environment file(s):"
    echo "$STAGED_ENV_FILES"
    echo ""
    echo "💡 Fix: Run 'git reset HEAD <file>' and ensure it remains in .gitignore."
    exit 1
fi

# 2. Block SQLite / DB files
STAGED_DB_FILES=$(git diff --cached --name-only | grep -E "\.(db|sqlite|sqlite3)$" || true)

if [ -n "$STAGED_DB_FILES" ]; then
    echo "❌ [PRE-COMMIT BLOCKED] Attempted to commit local database file(s):"
    echo "$STAGED_DB_FILES"
    echo ""
    echo "💡 Fix: Run 'git reset HEAD <file>' and ensure databases are never committed."
    exit 1
fi

# 3. Check staged files for live tokens, private keys, or raw DB passwords
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM || true)

SECRET_PATTERNS=(
    "pdl_sdbx_apikey_[0-9a-zA-Z_]{30,}"
    "pdl_live_apikey_[0-9a-zA-Z_]{30,}"
    "pdl_ntfset_[0-9a-zA-Z_]{30,}"
    "\\b[0-9]{8,10}:[A-Za-z0-9_-]{30,40}\\b"
    "BEGIN (RSA )?PRIVATE KEY"
    "postgresql\\+psycopg://[^:]+:[^@]+@"
)

for file in $STAGED_FILES; do
    if [[ "$file" == *".env.example"* || "$file" == *"SECURITY.md"* || "$file" == *".pre-commit"* || "$file" == *"test_"* || "$file" == *"conftest"* || "$file" == *"docker-compose"* || "$file" == *"docs/"* || "$file" == *".md" ]]; then
        continue
    fi

    if [ -f "$file" ]; then
        for pattern in "${SECRET_PATTERNS[@]}"; do
            if grep -E -q "$pattern" "$file" 2>/dev/null; then
                echo "❌ [PRE-COMMIT BLOCKED] Potential secret or credential leak detected in: $file"
                echo "   Pattern matched: $pattern"
                echo "   Please sanitize or use environment variables before committing."
                exit 1
            fi
        done
    fi
done

echo "✅ Pre-commit security checks passed cleanly."
exit 0
"""

def install_hook():
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        print("❌ Error: .git directory not found. Are you running from the repository root?")
        sys.exit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target_hook = hooks_dir / "pre-commit"

    with open(target_hook, "w", encoding="utf-8", newline="\n") as f:
        f.write(HOOK_CONTENT)

    # Ensure executable permissions on POSIX systems
    try:
        import os
        os.chmod(target_hook, 0o755)
    except Exception:
        pass

    print(f"✅ Clanomy pre-commit security hook successfully installed at: {target_hook}")

if __name__ == "__main__":
    install_hook()
