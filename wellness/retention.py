"""Retention rules (PR5, PR12, SR23).

The rules run when the server starts and then at most once an hour, before a request.
"""

import time
from datetime import datetime, timedelta, timezone

from . import audit
from .db import execute

_last_run = 0.0


def _ago(**kwargs):
    return (datetime.now(timezone.utc) - timedelta(**kwargs)).isoformat(timespec="seconds")


def apply():
    deleted = 0
    # PR5: invitations not accepted within 7 days
    deleted += execute("DELETE FROM invitations WHERE status = 'pending' AND created_at < ?",
                       (_ago(days=7),)).rowcount
    # PR12: raw readings and alerts 90 days after their recorded time
    deleted += execute("DELETE FROM readings WHERE recorded_at < ?", (_ago(days=90),)).rowcount
    deleted += execute("DELETE FROM alerts WHERE created_at < ?", (_ago(days=90),)).rowcount
    # SR23: audit log entries 12 months after the event time
    deleted += execute("DELETE FROM audit_log WHERE created_at < ?", (_ago(days=365),)).rowcount
    if deleted:
        audit.log("retention_deletion", "success")                                   # SR21
    return deleted


def apply_hourly():
    global _last_run
    if time.time() - _last_run >= 3600:
        _last_run = time.time()
        apply()
