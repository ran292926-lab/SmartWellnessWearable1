# Sanad · Smart Wellness Wearable

SW 341 Software Security Engineering · Group G3 · Section O53 · Topic T3

Sanad is a prototype wellness system. A simulated wearable sends heart rate, steps and sleep
readings to a Flask web application. The wearer sees a dashboard and 7-day trends and can share
selected daily summaries with trusted contacts. All data is synthetic.

Final code: commit "Week 12: security headers (W1-W5)". The full project report (Phases 1–7)
describes the requirements, design, threat model, tests and fixes.

## Requirements

- Python 3.10 or newer
- Libraries with fixed versions in `requirements.txt` (Flask 3.1.3, Werkzeug 3.1.9,
  Jinja2 3.1.6, cryptography 50.0.2)

## Run

```bash
python3 -m pip install -r requirements.txt
python3 app.py                     # then open https://localhost:5050/register
```

The server uses HTTPS on localhost only (SR16). The certificate is created in `instance/` on
the first run; the browser asks you to accept it the first time
(**Advanced → Proceed to localhost**).

Settings are read from environment variables (`wellness/config.py`, NFR13, SR18):
`DATABASE`, `DATA_KEY` or `KEY_FILE` (the AES key is kept outside the code and the database).

## Simulated wearable

Register a device on the **My device** page; the device ID and the secret token are shown once
(SR28). Then:

```bash
python3 simulator.py --device-id DEV-XXXXXXXX --token YOUR_TOKEN               # every 5 minutes (FR6)
python3 simulator.py --device-id DEV-XXXXXXXX --token YOUR_TOKEN --interval 5  # faster, for a demo
```

## Tests and checks

```bash
python3 -m unittest -v                                   # 58 automated tests
python3 -m coverage run -m unittest && python3 -m coverage report   # about 95% of wellness/
python3 -m bandit -r wellness app.py simulator.py        # static analysis: no High findings
python3 -m pip_audit -r requirements.txt                 # no known vulnerable libraries
```

`coverage`, `bandit` and `pip-audit` are installed with `python3 -m pip install coverage bandit pip-audit`.
The results are explained in Appendix A.9 of the report.

## Features

| Area | What it does | Requirements |
|---|---|---|
| Accounts | Register with consent, log in, log out, change email or password, delete the account | FR1–FR5, PR1, PR2, PR13 |
| Device | Register or replace the simulated wearable; readings sent with a secret token | FR6, FR7, SR9, SR28 |
| Dashboard | Current heart rate, steps, sleep, calories; health details and 7-day trends | FR8–FR13 |
| Sharing | Invite by contact ID, accept or decline, choose the categories each contact sees | FR17–FR24, PR3–PR7, PR10, PR20 |
| Privacy | Privacy notice on every page, My data view and JSON download | PR15–PR19 |
| Retention | Invitations, readings and logs deleted after their retention period | PR5, PR6, PR12, SR23 |

Heart-rate alerts (FR14–FR16) are not implemented.

## Security controls

| Control | Where |
|---|---|
| Argon2id password hashes; AES-256-GCM for health and profile values; SHA-256 hashes for session IDs and device tokens | `crypto.py` |
| Server-side sessions (HttpOnly, Secure, SameSite=Lax), 30-minute idle timeout, CSRF token on the forms of logged-in users | `sessions.py` |
| Login block after 5 failures, same message for every failed login | `auth.py` |
| Access check on every request for the two roles (wearer, trusted contact) | `access.py` |
| Server-side validation and parameterized queries | `validation.py`, `db.py` |
| Request limit: 60 requests per minute per client IP, kept in memory only | `ratelimit.py`, `config.py` |
| Security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Cache-Control) | `headers.py` |
| Audit log without secrets or health values | `audit.py` |
| Error pages without internal details; no IP addresses or versions in server output | `__init__.py`, `server.py` |

## Project structure

| Path | Contents |
|---|---|
| `app.py` | Starts the HTTPS server |
| `simulator.py` | Simulated wearable |
| `wellness/` | Application package (modules listed above, plus `pages.py`, `api.py`, `data.py`, `account.py`, `privacy.py`, `retention.py`, `tls.py`, `schema.sql`) |
| `wellness/templates/`, `wellness/static/` | HTML pages, style sheet and scripts |
| `tests/test_app.py` | 58 automated tests |

`instance/` (database, certificate) and `*.db` files are excluded from the repository by `.gitignore`.
