"""Small, dependency-free Flask configuration hardening layer.

Call configure_security(app) after Flask(__name__) and before handling requests.
The existing Flask installation is the only runtime requirement.
"""

from datetime import timedelta
import os


def configure_security(app):
    """Require a deployment secret; tighten session cookies and responses."""
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError(
            "SECRET_KEY is missing or too short. Supply a random secret of "
            "at least 32 characters via an environment variable."
        )

    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Set COOKIE_SECURE=1 only when serving via HTTPS.
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Financial API responses and receipt downloads should not be cached.
        from flask import request
        if request.path.startswith("/api/") or request.path.startswith("/uploads/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
