"""Idempotently integrate security.web_security into the upstream app.py.

Run from anywhere: python3 scripts/apply_security_phase1.py
Refuses to modify an app.py whose expected source lines differ.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = PROJECT_ROOT / "app.py"

# Exact source anchors from the public repository at the time this patch was built.
OLD_IMPORT = 'from werkzeug.security import check_password_hash, generate_password_hash'
NEW_IMPORT = OLD_IMPORT + '\nfrom security.web_security import configure_security'
OLD_SECRET = 'app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-real-use")'
NEW_SECRET = 'configure_security(app)'
OLD_DEBUG = 'app.run(debug=True, port=5000)'
NEW_DEBUG = 'app.run(debug=False, port=5000)'
OLD_REGISTER = '    session["uid"] = uid'
NEW_REGISTER = '    session.clear()\n    session.permanent = True\n    session["uid"] = uid'
OLD_LOGIN = '    session["uid"] = user["id"]'
NEW_LOGIN = '    session.clear()\n    session.permanent = True\n    session["uid"] = user["id"]'


def patch_text(source):
    changes = [
        (OLD_IMPORT, NEW_IMPORT),
        (OLD_SECRET, NEW_SECRET),
        (OLD_DEBUG, NEW_DEBUG),
        (OLD_REGISTER, NEW_REGISTER),
        (OLD_LOGIN, NEW_LOGIN),
    ]
    result = source
    for old, new in changes:
        if new in result:
            continue  # Already patched.
        if result.count(old) != 1:
            raise RuntimeError(f"Cannot safely patch app.py: expected exactly one {old!r}.")
        result = result.replace(old, new, 1)
    return result


def main():
    if not APP.exists():
        raise SystemExit(f"Missing {APP}")
    before = APP.read_text(encoding="utf-8")
    try:
        after = patch_text(before)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if before == after:
        print("app.py already patched; nothing changed.")
    else:
        APP.write_text(after, encoding="utf-8")
        print("app.py patched. Review with: git diff -- app.py")


if __name__ == "__main__":
    main()
