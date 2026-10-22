"""Registration, login and logout (FR1-FR3)."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, make_response, redirect, render_template, request

from . import audit, crypto, validation
from .db import execute, now, query_one
from .sessions import end_session, start_session

bp = Blueprint("auth", __name__)

PRIVACY_NOTICE_VERSION = "1.0"
MAX_FAILED = 5                    # SR7
LOCK_TIME = timedelta(minutes=15)  # SR7
LOGIN_ERROR = "Invalid email or password."


# ---- FR1: create an account ----

@bp.get("/register")
def register_page():
    return render_template("register.html")


@bp.post("/register")
def register():
    form = request.form
    try:
        display_name = validation.display_name(form.get("display_name"))
        email = validation.email(form.get("email"))
        password = validation.password(form.get("password"))
        birth_year = validation.birth_year(form.get("birth_year"))
        weight = validation.weight(form.get("weight"))
    except validation.ValidationError as e:
        return render_template("register.html", error=str(e), form=form), 400

    # PR1: the consent box starts unticked and must be ticked
    if form.get("privacy_consent") != "yes":
        return render_template("register.html", error="You must accept the privacy notice.", form=form), 400

    if query_one("SELECT 1 FROM users WHERE email = ?", (email,)):
        return render_template("register.html", error="This email is already registered.", form=form), 400

    # FR17, SR20: unique contact ID
    contact_id = crypto.new_contact_id()
    while query_one("SELECT 1 FROM users WHERE contact_id = ?", (contact_id,)):
        contact_id = crypto.new_contact_id()

    execute(
        "INSERT INTO users (display_name, email, password_hash, birth_year_enc, weight_enc, "
        "contact_id, privacy_notice_version, privacy_consent_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            display_name,
            email,
            crypto.hash_password(password),   # SR1
            crypto.encrypt(birth_year),       # SR17
            crypto.encrypt(weight),           # SR17
            contact_id,
            PRIVACY_NOTICE_VERSION,           # PR2
            now(),                            # PR2
        ),
    )
    return redirect("/login?registered=1")


# ---- FR2: log in ----

@bp.get("/login")
def login_page():
    return render_template("login.html", registered="registered" in request.args,
                           deleted="deleted" in request.args)


@bp.post("/login")
def login():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    user = query_one("SELECT * FROM users WHERE email = ?", (email,))

    if user is None:
        crypto.verify_dummy_password(password)   # F2: same Argon2id work as a real account
        audit.log("failed_login", "unknown_email")
        return render_template("login.html", error=LOGIN_ERROR), 401

    # SR7: blocked for 15 minutes after 5 consecutive failures
    if user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > datetime.now(timezone.utc):
        audit.log("failed_login", "locked", user["id"])
        return render_template("login.html", error=LOGIN_ERROR), 401

    if not crypto.verify_password(password, user["password_hash"]):
        failures = user["failed_login_count"] + 1
        locked_until = None
        if failures >= MAX_FAILED:
            locked_until = (datetime.now(timezone.utc) + LOCK_TIME).isoformat(timespec="seconds")
            failures = 0
        execute("UPDATE users SET failed_login_count = ?, locked_until = ? WHERE id = ?",
                (failures, locked_until, user["id"]))
        audit.log("failed_login", "wrong_password", user["id"])
        return render_template("login.html", error=LOGIN_ERROR), 401

    execute("UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ?", (user["id"],))
    audit.log("login", "success", user["id"])
    return start_session(make_response(redirect("/")), user["id"])   # SR4


# ---- FR3: log out ----

@bp.post("/logout")
def logout():
    if g.user_id is not None:
        audit.log("logout", "success", g.user_id)
    return end_session(make_response(redirect("/login")))            # SR6
