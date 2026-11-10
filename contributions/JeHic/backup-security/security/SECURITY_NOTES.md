# Security follow-up checklist

The following items still require integration with `app.py`; this module deliberately avoids editing shared application code.

- Remove the predictable fallback `app.secret_key` and require `SECRET_KEY` at startup. Generate a random value locally. Do not commit it.
- Never use Flask's `debug=True` on a deployed/public server.
- Configure `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, and `SESSION_COOKIE_SECURE=True` on HTTPS deployments.
- Add CSRF protection for authenticated state-changing routes, including JSON endpoints.
- Apply login rate limiting, login/logout session hardening, and careful authorization tests for household boundaries.
- Verify uploaded receipts by actual file type/content, not just extension; keep uploads non-executable and privately stored.
- Remove committed databases/real receipts from Git tracking and inspect any Git history exposure before using real accounts.
- Add automated tests verifying one household cannot read or modify another household's data.
- Restrict backup/restore commands to trusted system operators; do not expose them as unauthenticated HTTP endpoints.

Prioritize secret key and debug issues first, then CSRF and rate limiting.
