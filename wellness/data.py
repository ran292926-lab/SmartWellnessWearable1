"""Reading wellness data back out of the database.

Values are decrypted only here (SR17). Daily values use the Asia/Riyadh
calendar day (NFR7).
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .crypto import decrypt
from .db import query_all

RIYADH = ZoneInfo("Asia/Riyadh")


def _riyadh_day(utc_text):
    return datetime.fromisoformat(utc_text).astimezone(RIYADH).date().isoformat()


def daily_summary(wearer_id, category, days=7):
    """FR22/FR23: daily summaries for the last `days` days, newest first."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

    if category == "alerts":
        rows = query_all(
            "SELECT content_enc, created_at FROM alerts WHERE user_id = ? AND created_at >= ? "
            "ORDER BY created_at DESC",
            (wearer_id, since),
        )
        return [{"time": r["created_at"], "alert": decrypt(r["content_enc"])} for r in rows]

    rows = query_all(
        "SELECT value_enc, recorded_at FROM readings WHERE user_id = ? AND type = ? AND recorded_at >= ? "
        "ORDER BY recorded_at",
        (wearer_id, category, since),
    )
    by_day = defaultdict(list)
    for r in rows:
        by_day[_riyadh_day(r["recorded_at"])].append(float(decrypt(r["value_enc"])))

    result = []
    for day in sorted(by_day, reverse=True):
        values = by_day[day]
        if category == "heart_rate":
            result.append({"day": day, "min_bpm": min(values), "avg_bpm": round(sum(values) / len(values)),
                           "max_bpm": max(values)})
        elif category == "steps":
            # FR6: the device sends the day's cumulative count, so the largest value is the total
            result.append({"day": day, "steps": int(max(values))})
        elif category == "sleep":
            result.append({"day": day, "sleep_hours": values[-1]})
    return result
