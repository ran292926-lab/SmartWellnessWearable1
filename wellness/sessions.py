"""Server-side sessions (SR3-SR6) and the login check (SR11)."""

import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import current_app, g, render_template, request

from . import audit, crypto
from .db import execute, now, query_one

COOKIE = "session_id"
IDLE_LIMIT = timedelta(minutes=30)  # SR5


def load_session():
    """Runs before every request and sets g.user_id.

    g.session_id is the SHA-256 hash of the cookie value; only the hash is stored (F3).
    """
    g.user_id = None
    g.csrf_token = ""
    cookie = request.cookies.get(COOKIE)
    g.session_id = crypto.hash_session_id(cookie) if cookie else None
    if not g.session_id:
        return

    row = query_one("SELECT * FROM sessions WHERE id = ?", (g.session_id,))
    if row is None:
        return

    # SR5: invalidate after 30 minutes without an authenticated request
    if datetime.now(timezone.utc) - datetime.fromisoformat(row["last_seen"]) > IDLE_LIMIT:
        execute("DELETE FROM sessions WHERE id = ?", (g.session_id,))
        return

    execute("UPDATE sessions SET last_seen = ? WHERE id = ?", (now(), g.session_id))
    g.user_id = row["user_id"]
    g.csrf_token = crypto.csrf_token(g.session_id)


def check_csrf():
    """F1: every form sent by a logged-in user must carry the session's CSRF token.

    Runs after load_session. The device API is excluded: it uses the device token in the
    Authorization header, which a browser never adds to a cross-site request.
    """
    if request.method != "POST" or g.user_id is None or request.path.startswith("/api/"):
        return None
    if not current_app.config["CSRF_CHECK"]:
        return None
    if crypto.csrf_valid(g.session_id, request.form.get("csrf_token")):
        return None
    audit.log("csrf_failure", "denied", g.user_id)
    return render_template("error.html", detail="This form has expired. Go back, reload the page and try again."), 403


def start_session(response, user_id):
    """SR4: a new random session ID at each successful login."""
    if g.session_id:
        execute("DELETE FROM sessions WHERE id = ?", (g.session_id,))
    session_id = secrets.token_urlsafe(32)
    execute("INSERT INTO sessions (id, user_id, last_seen) VALUES (?, ?, ?)",
            (crypto.hash_session_id(session_id), user_id, now()))          # F3: hash only
    # SR3: cookie marked HttpOnly and Secure; F1: SameSite=Lax blocks cross-site form posts
    response.set_cookie(COOKIE, session_id, httponly=True, secure=True, samesite="Lax")
    return response


def end_session(response):
    """SR6: invalidate the session immediately on logout."""
    if g.session_id:
        execute("DELETE FROM sessions WHERE id = ?", (g.session_id,))
    response.delete_cookie(COOKIE, httponly=True, secure=True, samesite="Lax")
    return response


def login_required(view):
    """SR11: requests without a valid session get HTTP 401 (pages show the login form)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user_id is None:
            if request.path.startswith("/api/"):
                return {"error": "Authentication required"}, 401
            return render_template("login.html", error="Please log in."), 401
        return view(*args, **kwargs)
    return wrapper
