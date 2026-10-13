"""Profile changes (FR4, SR8) and account deletion (FR5, PR13, PR14)."""

import uuid

from flask import Blueprint, g, make_response, redirect, render_template, request

from . import audit, crypto, validation
from .db import execute, query_one
from .sessions import login_required

bp = Blueprint("account", __name__)


def _page(error=None, message=None, status=200):
    me = query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    audit.log("sensitive_data_access", "success", g.user_id)   # SR21: birth year and weight are shown
    profile = {
        "display_name": me["display_name"],
        "email": me["email"],
        "contact_id": me["contact_id"],
        "birth_year": crypto.decrypt(me["birth_year_enc"]),
        "weight": crypto.decrypt(me["weight_enc"]),
    }
    return render_template("account.html", profile=profile, error=error, message=message), status


@bp.get("/account")
@login_required
def account_page():
    return _page()


# ---- FR4: change display name, birth year and weight ----

@bp.post("/account/profile")
@login_required
def update_profile():
    try:
        display_name = validation.display_name(request.form.get("display_name"))   # SR14
        birth_year = validation.birth_year(request.form.get("birth_year"))         # SR14
        weight = validation.weight(request.form.get("weight"))                     # SR14
    except validation.ValidationError as e:
        return _page(error=str(e), status=400)
    execute("UPDATE users SET display_name = ?, birth_year_enc = ?, weight_enc = ? WHERE id = ?",
            (display_name, crypto.encrypt(birth_year), crypto.encrypt(weight), g.user_id))  # SR17
    return _page(message="Profile updated.")


# ---- FR4 + SR8: change email or password after re-entering the current password ----

def _current_password_ok():
    me = query_one("SELECT password_hash FROM users WHERE id = ?", (g.user_id,))
    return crypto.verify_password(request.form.get("current_password") or "", me["password_hash"])


@bp.post("/account/email")
@login_required
def change_email():
    if not _current_password_ok():
        return _page(error="Current password is incorrect.", status=403)
    try:
        email = validation.email(request.form.get("email"))                        # SR14
    except validation.ValidationError as e:
        return _page(error=str(e), status=400)
    if query_one("SELECT 1 FROM users WHERE email = ? AND id != ?", (email, g.user_id)):
        return _page(error="This email is already registered.", status=400)
    execute("UPDATE users SET email = ? WHERE id = ?", (email, g.user_id))
    return _page(message="Email updated.")


@bp.post("/account/password")
@login_required
def change_password():
    if not _current_password_ok():
        return _page(error="Current password is incorrect.", status=403)
    try:
        password = validation.password(request.form.get("new_password"))           # SR2
    except validation.ValidationError as e:
        return _page(error=str(e), status=400)
    execute("UPDATE users SET password_hash = ? WHERE id = ?",
            (crypto.hash_password(password), g.user_id))                           # SR1
    return _page(message="Password updated.")


# ---- FR5, PR13, PR14: delete the account ----

@bp.post("/account/delete")
@login_required
def delete_account():
    if request.form.get("confirm") != "yes":
        return _page(error="Tick the box to confirm account deletion.", status=400)

    user_id = g.user_id
    # PR14: replace the user ID in audit log entries with a random version 4 UUID
    pseudonym = str(uuid.uuid4())
    execute("UPDATE audit_log SET user_id = ? WHERE user_id = ?", (pseudonym, str(user_id)))

    # PR13: deleting the user also deletes its readings, alerts, devices, sessions,
    # invitations and trusted-contact links (ON DELETE CASCADE in schema.sql)
    execute("DELETE FROM users WHERE id = ?", (user_id,))
    audit.log("account_deletion", "success", pseudonym)                              # SR21

    response = make_response(redirect("/login?deleted=1"))
    response.delete_cookie("session_id", httponly=True, secure=True)
    return response
