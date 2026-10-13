# Smart Wellness Wearable — Code Snapshot 1 (Week 8)

SW 341 · Group G3 · Section O53

Week 8 scope from the project brief: **authentication, roles, API and database**.
All data is synthetic.

## Run

```bash
pip install -r requirements.txt
python app.py                      # open http://localhost:5000/register
```

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
| `wellness/templates/` | HTML pages |
| `tests/test_app.py` | Tests |

## Requirements implemented in this snapshot

| Area | Requirements | Where |
|---|---|---|
| Accounts | FR1, FR2, FR3 | `auth.py` |
| Contact ID and invitations | FR17, FR18, FR19, FR20, FR21 | `auth.py`, `pages.py` |
| Data sharing | FR22, FR23, FR24 | `pages.py`, `api.py`, `data.py` |
| Device readings | FR6, FR7 | `api.py`, `simulator.py` |
| Authentication and sessions | SR1–SR7, SR9 | `crypto.py`, `sessions.py`, `auth.py`, `api.py` |
| Authorization | SR10, SR11, SR12 | `access.py`, `sessions.py` |
| Input validation | SR2, SR13, SR14, SR15 | `validation.py`, `db.py` |
| Data protection | SR17, SR18, SR19, SR20 | `crypto.py`, `config.py`, `__init__.py` |
| Accountability | SR21, SR22, SR24 | `audit.py`, `access.py` |
| Output encoding | SR25 | templates (automatic HTML encoding) |
| Privacy | PR1, PR2, PR3, PR4, PR6, PR7, PR10, PR11 | `auth.py`, `pages.py`, `access.py` |
| Data quality | NFR4, NFR5, NFR7, NFR13 | `schema.sql`, `validation.py`, `data.py`, `config.py` |

## Not in this snapshot (later weeks)

- Dashboard, charts, calories and alerts: FR8–FR16, NFR1, NFR6, NFR8, NFR9
- Profile changes and account deletion: FR4, FR5, SR8, PR13, PR14
- Retention: PR5, PR12, SR23
- Privacy notice and user rights: PR15–PR19
- TLS: SR16 (the server runs on plain HTTP on localhost for development)
