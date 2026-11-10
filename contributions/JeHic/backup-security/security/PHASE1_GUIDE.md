# Phase 1: Flask security baseline

Provides app configuration hardening without changing the existing HTTP API's routes or request format.

1. Extract this archive over the existing project root **on your feature branch**.
2. Run `python3 scripts/apply_security_phase1.py` (safe to run again).
3. Generate a local untracked `.env` file:

   ```sh
   printf 'SECRET_KEY=%s\nCOOKIE_SECURE=0\n' "$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env
   chmod 600 .env
   ```
4. For each new terminal where you start the app, load the values:

   ```sh
   set -a; . ./.env; set +a
   python3 app.py
   ```
5. `python3 -m unittest discover -s tests -v`
6. `git diff -- app.py` to review what changed; no teammate files are modified in their own clone.

For deployment behind HTTPS set `COOKIE_SECURE=1`, keep the secret stable and private, and serve the site through a supported production WSGI server (not Flask's debug development server). If you change the secret, existing sessions are invalidated.

This phase adds a required random secret, 8-hour persistent login sessions, safer cookie flags, no-cache handling for sensitive responses, and baseline browser headers. It intentionally does **not** yet add CSRF defenses, rate limiting, or verification of uploaded image content. Those require another security phase and coordinated frontend changes.

IMPORTANT: `budget.db` is tracked on the public main branch. `.gitignore` does not remove it from Git history; coordinate with the repository owner before making real financial data available. Do not upload actual `.env` secrets, backups, databases, or receipt photos.
