"""API endpoints: readings from the simulated wearable and wellness data reads."""

import hmac

from flask import Blueprint, g, request

from . import access, crypto, validation
from .data import daily_summary
from .db import get_db, query_one
from .sessions import login_required

bp = Blueprint("api", __name__, url_prefix="/api")


# ---- FR6, FR7: readings from the simulated wearable ----

@bp.post("/readings")
def receive_reading():
    # SR9: only devices authenticated with their secret token
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""

    data = request.get_json(silent=True)
    try:
        device_id, reading_type, value, recorded_at = validation.reading(data)   # SR13
    except validation.ValidationError as e:
        return {"error": str(e)}, 400

    device = query_one("SELECT * FROM devices WHERE device_id = ?", (device_id,))
    if device is None or not hmac.compare_digest(device["token_hash"], crypto.hash_token(token)):
        return {"error": "Device authentication failed"}, 401

    # The token is bound to one wearer account, so the reading is stored for that account only.
    db = get_db()
    cursor = db.execute(
        "INSERT OR IGNORE INTO readings (user_id, type, value_enc, recorded_at) VALUES (?, ?, ?, ?)",
        (device["user_id"], reading_type, crypto.encrypt(value), recorded_at),   # SR17, NFR4
    )
    db.commit()
    if cursor.rowcount == 0:
        return {"stored": False, "reason": "duplicate reading"}, 200
    return {"stored": True}, 201


# ---- FR23: a wearer's data, checked by SR10 on every request ----

@bp.get("/wearers/<int:wearer_id>/<category>")
@login_required
def wearer_data(wearer_id, category):
    if category not in access.CATEGORIES:
        return {"error": "Unknown data category"}, 404
    denied = access.check(g.user_id, wearer_id, category)
    if denied:
        return denied
    return {"wearer_id": wearer_id, "category": category, "days": daily_summary(wearer_id, category)}
