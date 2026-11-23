---
name: secrets-review
description: Check staged changes, the diff, and git history for leaked credentials before committing or pushing. Use before every commit, or when asked about secrets or credential leaks.
---

# Secrets and credentials review

## Scan
1. Staged and unstaged changes: `git diff --cached` and `git diff`.
2. Branch commits not yet on main: `git log -p main..HEAD`.
3. If available, run `gitleaks detect --source . --verbose` (or `detect-secrets scan`). If neither is
   installed, say so and suggest adding one as a pre-commit hook. Do not install it without asking.

## Look for
- Connection strings with embedded passwords (`postgresql://user:pass@...`)
- API keys and tokens (Linear `lin_api_...`, AWS `AKIA...`, generic `api_key=`, `token=`, `secret=`)
- Private keys (`-----BEGIN ... PRIVATE KEY-----`)
- `.env` files, `*.pem`, `*.key`, credential JSON files being tracked
- Hard-coded passwords in `docker-compose.yml`. Use `${POSTGRES_PASSWORD}` from `.env` instead
- Secrets in notebooks, logs, test fixtures, or Streamlit `secrets.toml`

## Verify
- `.gitignore` covers `.env`, `.streamlit/secrets.toml`, `*.pem`, `*.key`.
- `.env.example` exists with placeholder values only.

## Report
List each finding as `file:line — what was found (value masked) — fix`.
If a secret is already in a commit, say so clearly: it must be **rotated**, not just deleted, and
history rewritten before pushing. Do not rewrite history without explicit approval.
End with **Clean** or **Leak found — do not commit**.
