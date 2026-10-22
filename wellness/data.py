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
        text = decrypt(r["value_enc"])
        by_day[_riyadh_day(r["recorded_at"])].append(int(text) if category == "steps" else float(text))

    result = []
    for day in sorted(by_day, reverse=True):
        values = by_day[day]
        if category == "heart_rate":
            result.append({"day": day, "min_bpm": min(values), "avg_bpm": round(sum(values) / len(values)),
                           "max_bpm": max(values)})
        elif category == "steps":
            # FR6: the device sends the day's cumulative count, so the largest value is the total
            result.append({"day": day, "steps": max(values)})
        elif category == "sleep":
            result.append({"day": day, "sleep_hours": values[-1]})
    return result


def dashboard(user_id, weight_kg, birth_year):
    """FR8, FR10-FR13: the wearer's own dashboard values for today (Asia/Riyadh)."""
    now_riyadh = datetime.now(RIYADH)
    today = now_riyadh.date().isoformat()
    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    rows = query_all(
        "SELECT type, value_enc, recorded_at FROM readings WHERE user_id = ? AND recorded_at >= ? "
        "ORDER BY recorded_at",
        (user_id, since),
    )
    latest_hr, hr_today, steps, sleep = None, [], None, None
    for r in rows:
        value = float(decrypt(r["value_enc"]))
        is_today = _riyadh_day(r["recorded_at"]) == today
        if r["type"] == "heart_rate":
            latest_hr = {"bpm": round(value),
                         "time": datetime.fromisoformat(r["recorded_at"]).astimezone(RIYADH).strftime("%H:%M")}
            if is_today:
                hr_today.append(value)
        elif r["type"] == "steps" and is_today:
            steps = max(steps or 0, int(value))      # FR6: cumulative count, so the largest is the total
        elif r["type"] == "sleep" and is_today:
            sleep = value                            # FR7: last night's summary arrives today

    max_hr = 220 - (now_riyadh.year - int(birth_year))                     # FR12, FR13
    return {
        "latest_hr": latest_hr,                                                # FR8
        "hr_min": round(min(hr_today)) if hr_today else None,
        "hr_max": round(max(hr_today)) if hr_today else None,
        "hr_points": [round(v) for v in hr_today[-36:]],
        "max_hr": max_hr,
        "steps": steps,                                                        # FR8
        "sleep_hours": sleep,                                                  # FR8
        "calories": round(0.00055 * steps * weight_kg) if steps is not None else None,   # FR10, FR11
    }
