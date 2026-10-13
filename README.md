# Smart Wellness Wearable — Code Snapshot 1 (Week 8)

SW 341 · Group G3 · Section O53

Week 8 scope from the project brief: **authentication, roles, API and database**.
All data is synthetic.

## Run

```bash
pip install -r requirements.txt
python app.py                      # open https://localhost:5050/register
```

The server uses HTTPS with a self-signed certificate for localhost (SR16), created in
`instance/` on first run. The browser shows a warning the first time: choose
**Advanced → Proceed to localhost**.

Simulated wearable (after you register a device on the home page):

```bash
python simulator.py --device-id DEV-XXXXXXXX --token YOUR_TOKEN               # every 5 minutes (FR6)
python simulator.py --device-id DEV-XXXXXXXX --token YOUR_TOKEN --interval 5  # faster, for a demo
```

Tests:

```bash
python -m unittest -v
```

## Project structure

| File | Contents |
|---|---|
| `app.py` | Starts the server |
| `simulator.py` | Simulated wearable (FR6, FR7) |
| `wellness/schema.sql` | Database tables |
| `wellness/db.py` | Database access with parameterized queries |
| `wellness/config.py` | Settings from environment variables |
| `wellness/crypto.py` | Argon2id, AES-256, device-token hash, contact ID |
| `wellness/sessions.py` | Server-side sessions and login check |
| `wellness/validation.py` | Server-side input validation |
| `wellness/auth.py` | Register, log in, log out |
| `wellness/access.py` | Authorization check for the two roles |
| `wellness/pages.py` | Home page, device, invitations, data sharing |
| `wellness/api.py` | Device readings API and wearer data API |
| `wellness/data.py` | Daily summaries |
| `wellness/audit.py` | Audit log |
| `wellness/account.py` | Profile changes and account deletion |
| `wellness/retention.py` | Retention rules |
| `wellness/tls.py` | Local TLS certificate |
| `wellness/templates/` | HTML pages |
| `tests/test_app.py` | Tests |

## Requirements implemented in this snapshot

| Area | Requirements | Where |
|---|---|---|
| Accounts | FR1, FR2, FR3, FR4, FR5 | `auth.py`, `account.py` |
| Contact ID and invitations | FR17, FR18, FR19, FR20, FR21 | `auth.py`, `pages.py` |
| Data sharing | FR22, FR23, FR24 | `pages.py`, `api.py`, `data.py` |
| Device readings | FR6, FR7 | `api.py`, `simulator.py` |
| Authentication and sessions | SR1–SR9 | `crypto.py`, `sessions.py`, `auth.py`, `account.py`, `api.py` |
| Authorization | SR10, SR11, SR12 | `access.py`, `sessions.py` |
| Input validation | SR2, SR13, SR14, SR15 | `validation.py`, `db.py` |
| Data protection | SR16, SR17, SR18, SR19, SR20 | `tls.py`, `crypto.py`, `config.py`, `__init__.py` |
| Accountability | SR21–SR24 | `audit.py`, `access.py`, `retention.py` |
| Output encoding | SR25 | templates (automatic HTML encoding) |
| Privacy | PR1–PR7, PR10–PR14 | `auth.py`, `pages.py`, `access.py`, `account.py`, `retention.py` |
| Data quality | NFR4, NFR5, NFR7, NFR13 (database setting only; alert thresholds come with FR14) | `schema.sql`, `validation.py`, `data.py`, `config.py` |

## Notes and limitations

- **Retention (PR5, PR12, SR23):** the rules run once when the server starts and then at most
  once an hour, triggered by an incoming request. They are not a separate scheduled job, so if
  the server receives no requests, expired data stays until the next request.
- **Privacy notice (PR15, PR16):** not written yet. The registration form already has the
  consent box (PR1) and records the notice version and time (PR2), but the notice it refers to
  is not available yet, so the privacy part is not complete in this snapshot.
- **NFR4:** readings are unique per account, type and timestamp. Each account has one device,
  so this is the same as per device ID while the device is not replaced.
- **Device timestamps:** the device chooses the timestamp. No requirement limits it, so a
  reading dated far in the future would never reach the 90-day limit (PR12). Recorded for review.
- **CSRF:** not covered by the current requirements and not implemented; recorded for the
  secure coding review.

## Not in this snapshot (later weeks)

- Dashboard, charts, calories and alerts: FR8–FR16, NFR1, NFR6, NFR8, NFR9
- Privacy notice and user rights: PR15–PR19
