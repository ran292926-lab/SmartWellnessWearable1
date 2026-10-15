"""SR27: HTTP 429 for more than 60 requests per minute from the same client IP address.

The counts are kept in memory only and are never written to the database or a
log, so client IP addresses are not stored (PR8).
"""

import time
from collections import defaultdict, deque

from flask import current_app, render_template, request

WINDOW = 60   # seconds
_requests = defaultdict(deque)


def check():
    """Runs before every request."""
    limit = current_app.config["RATE_LIMIT"]
    now = time.monotonic()
    times = _requests[request.remote_addr]
    while times and now - times[0] >= WINDOW:
        times.popleft()
    if len(times) >= limit:
        if request.path.startswith("/api/"):
            return {"error": "Too many requests"}, 429
        return render_template("error.html", detail="Too many requests. Try again in a minute."), 429
    times.append(now)


def reset():
    _requests.clear()
