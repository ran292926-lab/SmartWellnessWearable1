"""Account page: contact ID, device, invitations and data sharing (FR17-FR24)."""

import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, redirect, render_template, request

from . import access, audit, crypto
from .data import daily_summary
from .db import execute, now, query_all, query_one
from .sessions import login_required

bp = Blueprint("pages", __name__)

# Plain device tokens waiting to be shown once; kept in memory only, never in the database (SR28).
_pending_tokens = {}
# One-time success messages shown after a redirect, so a page reload does not resend a form.
_pending_messages = {}

CATEGORY_NAMES = {
    "heart_rate": "Daily heart-rate summary",
    "steps": "Daily step summary",
    "sleep": "Daily sleep summary",
    "alerts": "Alerts",
}


@bp.get("/")
@login_required
def home(message=None, error=None):
    # The device token is shown once, on the first page load after it is created.
    new_token = _pending_tokens.pop(g.session_id, None)
    message = message or _pending_messages.pop(g.session_id, None)
    me = query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    device = query_one("SELECT device_id FROM devices WHERE user_id = ?", (g.user_id,))

    # FR20: pending invitations with the inviting wearer's display name
    received = query_all(
        "SELECT i.id, u.display_name FROM invitations i JOIN users u ON u.id = i.wearer_id "
        "WHERE i.contact_user_id = ? AND i.status = 'pending'",
        (g.user_id,),
    )
    # The wearer's own contacts and their selected categories (FR22)
    my_contacts = query_all(
        "SELECT i.*, u.display_name FROM invitations i JOIN users u ON u.id = i.contact_user_id "
        "WHERE i.wearer_id = ? ORDER BY i.created_at",
        (g.user_id,),
    )
    # Wearers who share data with this user (FR23)
    sharing_with_me = query_all(
        "SELECT u.id, u.display_name FROM invitations i JOIN users u ON u.id = i.wearer_id "
        "WHERE i.contact_user_id = ? AND i.status = 'accepted'",
        (g.user_id,),
    )
    return render_template(
        "home.html", me=me, device=device, received=received, my_contacts=my_contacts,
        sharing_with_me=sharing_with_me, categories=CATEGORY_NAMES,
        new_token=new_token, message=message, error=error,
        editing=request.args.get("edit", type=int),
    )


# ---- SR9: register the simulated wearable and give it a secret token ----

@bp.post("/device")
@login_required
def register_device():
    token = crypto.new_token()
    device_id = "DEV-" + secrets.token_hex(4).upper()
    if execute("DELETE FROM devices WHERE user_id = ?", (g.user_id,)).rowcount:
        audit.log("device_deletion", "success", g.user_id)                          # SR21
    execute("INSERT INTO devices (user_id, device_id, token_hash) VALUES (?, ?, ?)",
            (g.user_id, device_id, crypto.hash_token(token)))
    _pending_tokens[g.session_id] = token
    return redirect("/")


# ---- FR19: send an invitation by contact ID ----

@bp.post("/invitations")
@login_required
def send_invitation():
    contact_id = (request.form.get("contact_id") or "").strip().upper()
    invited = query_one("SELECT id FROM users WHERE contact_id = ?", (contact_id,))
    if (invited is not None and invited["id"] != g.user_id and not query_one(
            "SELECT 1 FROM invitations WHERE wearer_id = ? AND contact_user_id = ?",
            (g.user_id, invited["id"]))):
        # PR3: no access until accepted; PR4: all categories unselected
        execute("INSERT INTO invitations (wearer_id, contact_user_id, status, created_at) "
                "VALUES (?, ?, 'pending', ?)", (g.user_id, invited["id"], now()))
        audit.log("invitation_sent", "success", g.user_id)                          # SR29
    else:
        audit.log("invitation_sent", "not_sent", g.user_id)                         # SR29
    # SR30: the same confirmation whether or not the contact ID belongs to an account
    _pending_messages[g.session_id] = "Invitation sent."
    return redirect("/")


# ---- FR21: accept or decline ----

def _received_invitation(invitation_id):
    # PR5: an invitation older than 7 days can no longer be accepted
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    return query_one("SELECT * FROM invitations WHERE id = ? AND contact_user_id = ? AND status = 'pending' "
                     "AND created_at >= ?", (invitation_id, g.user_id, week_ago))


@bp.post("/invitations/<int:invitation_id>/accept")
@login_required
def accept(invitation_id):
    if _received_invitation(invitation_id) is None:
        audit.log("authorization_failure", "denied", g.user_id)
        return home(error="Invitation not found."), 403
    execute("UPDATE invitations SET status = 'accepted' WHERE id = ?", (invitation_id,))
    audit.log("invitation_response", "accepted", g.user_id)                         # SR29
    return redirect("/")


@bp.post("/invitations/<int:invitation_id>/decline")
@login_required
def decline(invitation_id):
    if _received_invitation(invitation_id) is None:
        audit.log("authorization_failure", "denied", g.user_id)
        return home(error="Invitation not found."), 403
    execute("DELETE FROM invitations WHERE id = ?", (invitation_id,))   # PR6
    audit.log("invitation_response", "declined", g.user_id)                         # SR29
    audit.log("invitation_deletion", "declined", g.user_id)                          # SR21
    return redirect("/")


# ---- FR22: select categories; FR24: remove a contact ----

def _own_link(invitation_id):
    return query_one("SELECT * FROM invitations WHERE id = ? AND wearer_id = ?",
                     (invitation_id, g.user_id))


@bp.post("/contacts/<int:invitation_id>/categories")
@login_required
def set_categories(invitation_id):
    link = _own_link(invitation_id)
    # PR4: categories can be selected only after the contact has accepted
    if link is None or link["status"] != "accepted":
        audit.log("authorization_failure", "denied", g.user_id)
        return home(error="Contact not found."), 403
    chosen = request.form.getlist("category")
    values = [1 if c in chosen else 0 for c in access.CATEGORIES]
    execute("UPDATE invitations SET share_heart_rate = ?, share_steps = ?, share_sleep = ?, "
            "share_alerts = ? WHERE id = ?", (*values, invitation_id))
    audit.log("sharing_change", "success", g.user_id)                               # SR29
    _pending_messages[g.session_id] = "Sharing settings saved."
    return redirect("/")


@bp.post("/contacts/<int:invitation_id>/remove")
@login_required
def remove_contact(invitation_id):
    if _own_link(invitation_id) is None:
        audit.log("authorization_failure", "denied", g.user_id)
        return home(error="Contact not found."), 403
    execute("DELETE FROM invitations WHERE id = ?", (invitation_id,))
    audit.log("contact_deletion", "success", g.user_id)                              # SR21
    return redirect("/")


# ---- FR23: a trusted contact views the selected categories ----

@bp.get("/wearers/<int:wearer_id>")
@login_required
def view_wearer(wearer_id):
    if not access.can_read(g.user_id, wearer_id, "display_name"):
        audit.log("authorization_failure", "denied", g.user_id)
        return render_template("error.html", detail="You do not have access to this page."), 403

    wearer = query_one("SELECT display_name FROM users WHERE id = ?", (wearer_id,))
    sections = []
    for category in access.CATEGORIES:
        if access.can_read(g.user_id, wearer_id, category):
            audit.log("sensitive_data_access", "success", g.user_id)
            sections.append((CATEGORY_NAMES[category], category, daily_summary(wearer_id, category)))
    return render_template("wearer.html", wearer=wearer, sections=sections)
