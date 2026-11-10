"""Week 12: security headers on every response (fixes W1-W5 of the Week 11 testing)."""

from flask import request

# W1: scripts, styles, images and forms only from this application; no plug-ins.
# Inline style attributes are needed for the chart bar heights (style-src-attr only;
# inline <style> and <script> blocks stay blocked).
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
       "img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; "
       "frame-ancestors 'none'")


def add(response):
    h = response.headers
    h["Content-Security-Policy"] = CSP                                   # W1
    h["X-Frame-Options"] = "DENY"                                        # W2 (older browsers; CSP frame-ancestors for newer)
    h["Strict-Transport-Security"] = "max-age=31536000"                  # W3: one year, HTTPS only
    h["X-Content-Type-Options"] = "nosniff"                              # W4
    h["Referrer-Policy"] = "same-origin"
    if not request.path.startswith("/static/"):
        h["Cache-Control"] = "no-store"                                  # W5: pages and API responses are not stored
    return response
