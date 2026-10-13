"""SR21: log logins, failed logins, logouts, authorization failures and
sensitive-data access with event type, timestamp, outcome and user ID.

SR22: entries hold no password, session token or health value.
SR24: no route in the application modifies or deletes these entries.
"""

from .db import execute, now


def log(event_type, outcome, user_id=None):
    execute(
        "INSERT INTO audit_log (event_type, outcome, user_id, created_at) VALUES (?, ?, ?, ?)",
        (event_type, outcome, None if user_id is None else str(user_id), now()),
    )
