"""SR27: HTTP 429 for more than 60 requests per minute from the same client IP address.

Client IP addresses and request times are kept in server memory only. They are
never written to the database or logs, and they are cleared when the server restarts.
"""

import time
from collections import defaultdict, deque

from flask import current_app, render_template, request

WINDOW = 60   # seconds
_requests = defaultdict(deque)
_last_sweep = 0.0


def _sweep(now):
    """F8: forget addresses with no request in the last minute, so memory does not grow."""
    global _last_sweep
    if now - _last_sweep < WINDOW:
        return
    _last_sweep = now
    for address in [a for a, times in _requests.items() if not times or now - times[-1] >= WINDOW]:
        del _requests[address]


def check():
    """Runs before every request."""
    limit = current_app.config["RATE_LIMIT"]
    now = time.monotonic()
    _sweep(now)
    times = _requests[request.remote_addr]
    while times and now - times[0] >= WINDOW:
        times.popleft()
    if len(times) >= limit:
        if request.path.startswith("/api/"):
            return {"error": "Too many requests"}, 429
        return render_template("error.html", detail="Too many requests. Try again in a minute."), 429
    times.append(now)


def reset():
    global _last_sweep
    _requests.clear()
    _last_sweep = 0.0
