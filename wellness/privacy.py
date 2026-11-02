"""Privacy notice (PR15, PR16), own-data view (PR17) and data download (PR18, PR19)."""

import json
from datetime import datetime, timezone

from flask import Blueprint, Response, g, render_template, request

from . import audit, crypto
from .auth import PRIVACY_NOTICE_VERSION
from .data import RIYADH
from .db import query_all, query_one
from .pages import CATEGORY_NAMES
from .sessions import login_required

bp = Blueprint("privacy", __name__)

NOTICE_DATE = "2026-10-28"
READING_TYPES = {"heart_rate": "Heart rate (bpm)", "steps": "Steps (cumulative)", "sleep": "Sleep (hours)"}


# ---- PR15: the privacy notice, open to everyone (also before registration) ----

@bp.get("/privacy")
def notice():
    return render_template("privacy.html", version=PRIVACY_NOTICE_VERSION, date=NOTICE_DATE)


# ---- shared by the view and the download: only the logged-in user's own data ----

def _riyadh(utc_text):
    return datetime.fromisoformat(utc_text).astimezone(RIYADH).strftime("%Y-%m-%d %H:%M")


def _profile(me):
    device = query_one("SELECT device_id FROM devices WHERE user_id = ?", (g.user_id,))
    return {
        "display_name": me["display_name"],
        "email": me["email"],
        "birth_year": int(crypto.decrypt(me["birth_year_enc"])),
        "weight_kg": float(crypto.decrypt(me["weight_enc"])),
        "contact_id": me["contact_id"],
        "device_id": device["device_id"] if device else None,
        "privacy_notice": {"version": me["privacy_notice_version"], "accepted_at_utc": me["privacy_consent_time"]},
    }


def _account(me):
    """Account ID and login-block data (SR7), shown so the user sees everything kept about them (PR17)."""
    return {"account_id": me["id"], "failed_login_count": me["failed_login_count"],
            "locked_until_utc": me["locked_until"]}


def _security_log():
    """The user's own audit log entries: event, outcome and time only (SR22 keeps secrets out of the log)."""
    rows = query_all("SELECT event_type, outcome, created_at FROM audit_log WHERE user_id = ? ORDER BY id",
                     (str(g.user_id),))
    return [{"event": r["event_type"], "outcome": r["outcome"], "time_utc": r["created_at"]} for r in rows]


def _contacts():
    """The wearer's trusted contacts: display name, status and selected categories only (PR19)."""
    rows = query_all(
        "SELECT i.*, u.display_name FROM invitations i JOIN users u ON u.id = i.contact_user_id "
        "WHERE i.wearer_id = ? ORDER BY i.created_at", (g.user_id,))
    return [{"display_name": r["display_name"], "status": r["status"],
             "shared_categories": [CATEGORY_NAMES[c] for c in CATEGORY_NAMES if r["share_" + c]]} for r in rows]


def _readings(day=None):
    rows = query_all("SELECT type, value_enc, recorded_at FROM readings WHERE user_id = ? ORDER BY recorded_at",
                     (g.user_id,))
    out = []
    for r in rows:
        local = _riyadh(r["recorded_at"])
        if day and not local.startswith(day):
            continue
        value = crypto.decrypt(r["value_enc"])
        out.append({"type": r["type"], "value": int(value) if r["type"] == "steps" else float(value),
                    "recorded_at_utc": r["recorded_at"], "recorded_at_riyadh": local})
    return out


def _alerts():
    rows = query_all("SELECT content_enc, created_at FROM alerts WHERE user_id = ? ORDER BY created_at",
                     (g.user_id,))
    return [{"alert": crypto.decrypt(r["content_enc"]), "created_at_utc": r["created_at"]} for r in rows]


# ---- PR17: view all own data ----

@bp.get("/my-data")
@login_required
def my_data():
    me = query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    all_readings = _readings()
    days = sorted({r["recorded_at_riyadh"][:10] for r in all_readings}, reverse=True)
    day = request.args.get("day")
    if day not in days:                      # only a day that exists in the user's own readings is used
        day = days[0] if days else None
    counts = {t: sum(1 for r in all_readings if r["type"] == t) for t in READING_TYPES}
    audit.log("sensitive_data_access", "success", g.user_id)                          # SR21
    log = _security_log()
    return render_template("my_data.html", profile=_profile(me), account=_account(me),
                           log_count=len(log), log=log[-20:][::-1], accepted=_riyadh(me["privacy_consent_time"]), contacts=_contacts(), alerts=_alerts(),
                           days=days, day=day, counts=counts, types=READING_TYPES,
                           readings=[r for r in all_readings if r["recorded_at_riyadh"].startswith(day)] if day else [])


# ---- PR18, PR19: download own data as JSON ----

@bp.get("/my-data/download")
@login_required
def download():
    me = query_one("SELECT * FROM users WHERE id = ?", (g.user_id,))
    export = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": _profile(me),
        "account": _account(me),
        "trusted_contacts": _contacts(),
        "readings": [{k: r[k] for k in ("type", "value", "recorded_at_utc")} for r in _readings()],
        "alerts": _alerts(),
        "security_log": _security_log(),
    }
    audit.log("data_export", "success", g.user_id)                                    # SR21
    body = json.dumps(export, indent=2, ensure_ascii=False)
    return Response(body, mimetype="application/json", headers={
        "Content-Disposition": "attachment; filename=my-wellness-data.json",
        "Cache-Control": "no-store",
    })
