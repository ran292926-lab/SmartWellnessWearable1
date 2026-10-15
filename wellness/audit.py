"""SR21: log logins, failed logins, logouts, authorization failures and
sensitive-data access with event type, timestamp, outcome and user ID.

SR22: entries hold no password, session token or health value.
SR24: no user can modify or delete these entries. The only changes are made by the
application itself: deletion after 12 months (SR23, retention.py) and replacing the
user ID with a random ID when an account is deleted (PR14, account.py).
"""

from .db import execute, now


def log(event_type, outcome, user_id=None):
    execute(
        "INSERT INTO audit_log (event_type, outcome, user_id, created_at) VALUES (?, ?, ?, ?)",
        (event_type, outcome, None if user_id is None else str(user_id), now()),
    )
