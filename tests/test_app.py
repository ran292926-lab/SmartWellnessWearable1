"""Tests for Code Snapshot 1.   Run:  python -m unittest -v"""

import base64
import os
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from wellness import create_app

THIS_YEAR = datetime.now(ZoneInfo("Asia/Riyadh")).year


class AppTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.db_path,
            "DATA_KEY": base64.b64encode(os.urandom(32)).decode(),
        })

    def tearDown(self):
        self.tmp.cleanup()

    # ---- helpers ----

    def client(self):
        c = self.app.test_client()
        c.environ_base["wsgi.url_scheme"] = "https"   # Secure cookies need HTTPS
        return c

    def sql(self, query, params=()):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchall()

    def register(self, c, email="sara@example.com", **extra):
        form = {"display_name": "Sara", "email": email, "password": "correct-horse",
                "birth_year": str(THIS_YEAR - 30), "weight": "60.5", "privacy_consent": "yes"}
        form.update(extra)
        return c.post("/register", data=form)

    def login(self, c, email="sara@example.com", password="correct-horse"):
        return c.post("/login", data={"email": email, "password": password})

    def user(self, email):
        return self.sql("SELECT * FROM users WHERE email = ?", (email,))[0]

    def new_user(self, name, email):
        c = self.client()
        self.register(c, email=email, display_name=name)
        self.login(c, email=email)
        return c, self.user(email)

    def device(self, c):
        html = c.post("/device", follow_redirects=True).get_data(as_text=True)
        token = re.search(r"copy it now\): <code>([^<]+)</code>", html).group(1)
        device_id = re.search(r"Device ID: <code>([^<]+)</code>", html).group(1)
        return device_id, token

    def send(self, c, device_id, token, reading_type, value, timestamp=None):
        body = {"device_id": device_id, "type": reading_type, "value": value,
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")}
        return c.post("/api/readings", json=body, headers={"Authorization": "Bearer " + token})

    def link(self, wearer_client, contact_client, contact_email):
        """Wearer invites the contact; the contact accepts."""
        contact_id = self.user(contact_email)["contact_id"]
        wearer_client.post("/invitations", data={"contact_id": contact_id})
        inv = self.sql("SELECT id FROM invitations ORDER BY id DESC LIMIT 1")[0]["id"]
        contact_client.post(f"/invitations/{inv}/accept")
        return inv

    # ---- FR1, SR1, SR14, SR17, SR20, PR1, PR2 ----

    def test_register_stores_safe_values(self):
        r = self.register(self.client())
        self.assertEqual(r.status_code, 302)
        u = self.user("sara@example.com")
        self.assertTrue(u["password_hash"].startswith("$argon2id$v=19$m=19456,t=2,p=1$"))   # SR1
        self.assertNotIn(str(THIS_YEAR - 30).encode(), bytes(u["birth_year_enc"]))                                 # SR17
        self.assertNotIn(b"60.5", bytes(u["weight_enc"]))                                     # SR17
        self.assertRegex(u["contact_id"], r"^[A-Z0-9]{8}$")                                    # SR20
        self.assertEqual(u["privacy_notice_version"], "1.0")                                   # PR2
        self.assertTrue(u["privacy_consent_time"])                                             # PR2

    def test_register_rejects_invalid_input(self):
        c = self.client()
        cases = [
            {"display_name": " "}, {"display_name": "x" * 51},       # SR14
            {"email": "not-an-email"},                                # SR14
            {"birth_year": str(THIS_YEAR - 17)},                      # SR14
            {"birth_year": str(THIS_YEAR - 101)},                     # SR14
            {"weight": "19"}, {"weight": "301"},                      # SR14
            {"password": "short"}, {"password": "x" * 129},           # SR2
            {"privacy_consent": ""},                                  # PR1
        ]
        for extra in cases:
            self.assertEqual(self.register(c, **extra).status_code, 400, extra)
        self.assertEqual(len(self.sql("SELECT * FROM users")), 0)

    def test_registration_form_consent_box_unticked(self):
        html = self.client().get("/register").get_data(as_text=True)
        box = re.search(r'<input type="checkbox" name="privacy_consent"[^>]*>', html).group(0)
        self.assertNotIn("checked", box)                                                      # PR1

    # ---- FR2, FR3, SR3-SR6, SR11, SR21 ----

    def test_login_logout_and_session_cookie(self):
        c = self.client()
        self.register(c)
        r = self.login(c)
        cookie = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)                                                     # SR3
        self.assertIn("Secure", cookie)                                                       # SR3
        self.assertEqual(c.get("/").status_code, 200)

        session_id = c.get_cookie("session_id").value
        c.post("/logout")
        self.assertEqual(self.sql("SELECT * FROM sessions WHERE id = ?", (session_id,)), [])  # SR6
        self.assertEqual(c.get("/api/wearers/1/steps").status_code, 401)                     # SR11

        events = [r["event_type"] for r in self.sql("SELECT event_type FROM audit_log")]
        self.assertEqual(events, ["login", "logout"])                                         # SR21

    def test_new_session_id_at_each_login(self):
        c = self.client()
        self.register(c)
        self.login(c)
        first = c.get_cookie("session_id").value
        self.login(c)
        second = c.get_cookie("session_id").value
        self.assertNotEqual(first, second)                                                    # SR4
        self.assertEqual(self.sql("SELECT * FROM sessions WHERE id = ?", (first,)), [])

    def test_session_expires_after_30_idle_minutes(self):
        c = self.client()
        self.register(c)
        self.login(c)
        old = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sessions SET last_seen = ?", (old,))
        self.assertEqual(c.get("/").status_code, 401)                                        # SR5, SR11

    def test_lockout_after_5_failures(self):
        c = self.client()
        self.register(c)
        for _ in range(5):
            self.assertEqual(self.login(c, password="wrong-password").status_code, 401)
        r = self.login(c)                                       # correct password, but locked
        self.assertEqual(r.status_code, 401)                                                  # SR7
        self.assertIn("Invalid email or password.", r.get_data(as_text=True))

        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE users SET locked_until = ?", (past,))
        self.assertEqual(self.login(c).status_code, 302)

    def test_logs_have_no_secrets_or_health_values(self):
        c = self.client()
        self.register(c)
        self.login(c, password="wrong-password")
        self.login(c)
        device_id, token = self.device(c)
        self.send(c, device_id, token, "heart_rate", 187)
        dump = str([dict(r) for r in self.sql("SELECT * FROM audit_log")])
        for secret in ("wrong-password", "correct-horse", token, c.get_cookie("session_id").value, "187"):
            self.assertNotIn(secret, dump)                                                    # SR22

    # ---- FR6, FR7, SR9, SR13, SR17, NFR4 ----

    def test_device_token_is_hashed_and_required(self):
        c = self.client()
        self.register(c)
        self.login(c)
        device_id, token = self.device(c)
        stored = self.sql("SELECT token_hash FROM devices")[0]["token_hash"]
        self.assertNotEqual(stored, token)                                                    # SR9

        self.assertEqual(self.send(c, device_id, token, "heart_rate", 72).status_code, 201)
        self.assertEqual(self.send(c, device_id, "wrong", "heart_rate", 72).status_code, 401)
        self.assertEqual(self.send(c, "DEV-00000000", token, "heart_rate", 72).status_code, 401)
        value = bytes(self.sql("SELECT value_enc FROM readings")[0]["value_enc"])
        self.assertNotIn(b"72", value)                                                        # SR17

    def test_token_is_bound_to_its_wearer(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        id_a, token_a = self.device(a)
        id_b, _ = self.device(b)
        self.assertEqual(self.send(a, id_b, token_a, "steps", 100).status_code, 401)          # SR9

    def test_invalid_readings_rejected(self):
        c = self.client()
        self.register(c)
        self.login(c)
        device_id, token = self.device(c)
        bad = [("heart_rate", 29), ("heart_rate", 221), ("sleep", -1), ("sleep", 25),
               ("steps", -5), ("steps", 10.5), ("unknown", 1)]
        for reading_type, value in bad:
            r = self.send(c, device_id, token, reading_type, value)
            self.assertEqual(r.status_code, 400, (reading_type, value))                       # SR13
        r = c.post("/api/readings", json={"device_id": device_id, "type": "steps", "value": 5},
                   headers={"Authorization": "Bearer " + token})
        self.assertEqual(r.status_code, 400)                                    # missing timestamp
        self.assertEqual(len(self.sql("SELECT * FROM readings")), 0)

    def test_out_of_range_timestamp_rejected(self):
        c = self.client()
        self.register(c)
        self.login(c)
        device_id, token = self.device(c)
        r = self.send(c, device_id, token, "steps", 5, "0001-01-01T00:00:00+03:00")
        self.assertEqual(r.status_code, 400)                                                  # SR13

    def test_account_page_access_is_logged(self):
        c = self.client()
        self.register(c)
        self.login(c)
        c.get("/account")
        events = [r["event_type"] for r in self.sql("SELECT event_type FROM audit_log")]
        self.assertIn("sensitive_data_access", events)                                        # SR21

    def test_duplicate_reading_stored_once(self):
        c = self.client()
        self.register(c)
        self.login(c)
        device_id, token = self.device(c)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.assertEqual(self.send(c, device_id, token, "steps", 500, ts).status_code, 201)
        self.assertEqual(self.send(c, device_id, token, "steps", 500, ts).status_code, 200)
        self.assertEqual(len(self.sql("SELECT * FROM readings")), 1)                          # NFR4

    # ---- FR18-FR24, SR10, SR12, PR3, PR4, PR6, PR7, PR10, PR11 ----

    def test_contact_id_shown_only_to_owner(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        self.link(a, b, "noura@example.com")
        self.assertIn(user_a["contact_id"], a.get("/").get_data(as_text=True))                # FR18
        self.assertNotIn(user_a["contact_id"], b.get("/").get_data(as_text=True))             # PR11
        self.assertNotIn(user_a["contact_id"], b.get(f"/wearers/{user_a['id']}").get_data(as_text=True))

    def test_trusted_contact_sees_only_selected_categories(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        device_id, token = self.device(a)
        self.send(a, device_id, token, "heart_rate", 80)
        self.send(a, device_id, token, "steps", 1200)

        # FR19, FR20: pending invitation shows the wearer's display name
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        self.assertIn("Sara invited you", b.get("/").get_data(as_text=True))
        inv = self.sql("SELECT id FROM invitations")[0]["id"]

        # PR3: no access while pending
        self.assertEqual(b.get(f"/api/wearers/{user_a['id']}/steps").status_code, 403)

        b.post(f"/invitations/{inv}/accept")                                                  # FR21
        # PR4: accepted but nothing selected yet
        self.assertEqual(b.get(f"/api/wearers/{user_a['id']}/steps").status_code, 403)

        a.post(f"/contacts/{inv}/categories", data={"category": ["steps"]})                   # FR22
        r = b.get(f"/api/wearers/{user_a['id']}/steps")
        self.assertEqual(r.status_code, 200)                                                  # FR23
        self.assertEqual(r.json["days"][0]["steps"], 1200)
        self.assertEqual(b.get(f"/api/wearers/{user_a['id']}/heart_rate").status_code, 403)  # PR10, SR12

        # PR7: deselecting takes effect on the next request
        a.post(f"/contacts/{inv}/categories", data={})
        self.assertEqual(b.get(f"/api/wearers/{user_a['id']}/steps").status_code, 403)

        # FR24, PR7: removing the contact
        a.post(f"/contacts/{inv}/categories", data={"category": ["steps"]})
        a.post(f"/contacts/{inv}/remove")
        self.assertEqual(b.get(f"/api/wearers/{user_a['id']}/steps").status_code, 403)

        failures = self.sql("SELECT * FROM audit_log WHERE event_type = 'authorization_failure'")
        self.assertGreaterEqual(len(failures), 4)                                             # SR21

    def test_wearer_reads_own_data_but_not_others(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        self.assertEqual(a.get(f"/api/wearers/{user_a['id']}/steps").status_code, 200)       # SR10
        self.assertEqual(a.get(f"/api/wearers/{user_b['id']}/steps").status_code, 403)       # SR12
        self.assertEqual(a.get(f"/wearers/{user_b['id']}").status_code, 403)

    def test_decline_deletes_invitation(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        inv = self.sql("SELECT id FROM invitations")[0]["id"]
        b.post(f"/invitations/{inv}/decline")
        self.assertEqual(self.sql("SELECT * FROM invitations"), [])                           # PR6

    def test_only_the_invited_user_can_accept(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        c, user_c = self.new_user("Huda", "huda@example.com")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        inv = self.sql("SELECT id FROM invitations")[0]["id"]
        self.assertEqual(c.post(f"/invitations/{inv}/accept").status_code, 403)              # SR12
        self.assertEqual(c.post(f"/contacts/{inv}/categories", data={"category": ["steps"]}).status_code, 403)
        self.assertEqual(self.sql("SELECT status FROM invitations")[0]["status"], "pending")

    # ---- SR15, SR19, SR25 ----

    def test_sql_injection_in_login_is_harmless(self):
        c = self.client()
        self.register(c)
        r = self.login(c, email="' OR '1'='1", password="' OR '1'='1")
        self.assertEqual(r.status_code, 401)                                                  # SR15

    def test_error_pages_reveal_nothing(self):
        r = self.client().get("/no-such-page")
        text = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 404)
        for leak in ("Traceback", "sqlite", ".py"):
            self.assertNotIn(leak, text)                                                      # SR19

    def test_display_name_is_html_encoded(self):
        a, user_a = self.new_user("<script>alert(1)</script>", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        html = b.get("/").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)                                   # SR25
        self.assertIn("&lt;script&gt;", html)

    # ---- device token shown once (refresh does not create a new device) ----

    def test_device_token_shown_once(self):
        c = self.client()
        self.register(c)
        self.login(c)
        device_id, token = self.device(c)
        html = c.get("/").get_data(as_text=True)
        self.assertNotIn(token, html)
        self.assertIn(device_id, html)
        self.assertEqual(len(self.sql("SELECT * FROM devices")), 1)

    # ---- FR4, SR8 ----

    def test_profile_update_is_validated_and_encrypted(self):
        c = self.client()
        self.register(c)
        self.login(c)
        r = c.post("/account/profile", data={"display_name": "Sara A", "birth_year": str(THIS_YEAR - 40), "weight": "70"})
        self.assertEqual(r.status_code, 302)                                                  # FR4
        self.assertIn("Profile updated.", c.get("/account").get_data(as_text=True))
        u = self.user("sara@example.com")
        self.assertEqual(u["display_name"], "Sara A")
        self.assertNotIn(b"70", bytes(u["weight_enc"]))                                       # SR17
        r = c.post("/account/profile", data={"display_name": "Sara", "birth_year": str(THIS_YEAR - 10), "weight": "70"})
        self.assertEqual(r.status_code, 400)                                                  # SR14

    def test_email_and_password_change_need_current_password(self):
        c = self.client()
        self.register(c)
        self.login(c)
        r = c.post("/account/email", data={"email": "new@example.com", "current_password": "wrong-password"})
        self.assertEqual(r.status_code, 403)                                                  # SR8
        r = c.post("/account/password", data={"new_password": "new-password-1", "current_password": "wrong-password"})
        self.assertEqual(r.status_code, 403)                                                  # SR8

        self.assertEqual(c.post("/account/email", data={"email": "new@example.com",
                         "current_password": "correct-horse"}).status_code, 302)              # FR4
        self.assertEqual(c.post("/account/password", data={"new_password": "new-password-1",
                         "current_password": "correct-horse"}).status_code, 302)              # FR4
        self.assertEqual(self.login(self.client(), "new@example.com", "new-password-1").status_code, 302)

    # ---- FR5, PR13, PR14 ----

    def test_account_deletion(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        device_id, token = self.device(a)
        self.send(a, device_id, token, "steps", 100)
        self.link(a, b, "noura@example.com")

        self.assertEqual(a.post("/account/delete", data={}).status_code, 400)                # needs confirmation
        a.post("/account/delete", data={"confirm": "yes"})                                    # FR5

        for table in ("users WHERE id = ?", "readings WHERE user_id = ?", "devices WHERE user_id = ?",
                      "sessions WHERE user_id = ?"):
            self.assertEqual(self.sql("SELECT * FROM " + table, (user_a["id"],)), [])         # PR13
        self.assertEqual(self.sql("SELECT * FROM invitations"), [])                           # PR13

        refs = {r["user_id"] for r in self.sql("SELECT user_id FROM audit_log")}
        self.assertNotIn(str(user_a["id"]), refs)                                              # PR14
        uuids = [r for r in refs if r and len(r) == 36]
        self.assertTrue(uuids and all(r[14] == "4" for r in uuids))                           # version 4 UUID

    # ---- PR5, PR12, SR23 ----

    def test_retention_rules(self):
        from wellness import retention
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        device_id, token = self.device(a)
        old = lambda days: (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        self.send(a, device_id, token, "steps", 100, old(91))
        self.send(a, device_id, token, "steps", 200, old(1))
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE invitations SET created_at = ?", (old(8),))
            conn.execute("INSERT INTO audit_log (event_type, outcome, user_id, created_at) VALUES ('login', 'success', '1', ?)", (old(366),))

        with self.app.app_context():
            retention.apply()
        self.assertEqual(len(self.sql("SELECT * FROM readings")), 1)                          # PR12
        self.assertEqual(self.sql("SELECT * FROM invitations"), [])                           # PR5
        self.assertEqual(self.sql("SELECT * FROM audit_log WHERE created_at < ?", (old(365),)), [])  # SR23

    # ---- SR16 ----

    def test_tls_certificate_created(self):
        from wellness.tls import ensure_certificate
        cert, key = ensure_certificate(self.tmp.name)
        self.assertTrue(os.path.exists(cert) and os.path.exists(key))                        # SR16

    # ---- review fixes ----

    def test_pages_without_session_return_401(self):
        c = self.client()
        for path in ("/", "/account"):
            self.assertEqual(c.get(path).status_code, 401)                                    # SR11
        self.assertEqual(c.post("/device").status_code, 401)

    def test_categories_cannot_be_set_while_pending(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        inv = self.sql("SELECT id FROM invitations")[0]["id"]
        r = a.post(f"/contacts/{inv}/categories", data={"category": ["heart_rate", "steps"]})
        self.assertEqual(r.status_code, 403)                                                  # PR4
        b.post(f"/invitations/{inv}/accept")
        row = self.sql("SELECT * FROM invitations")[0]
        self.assertEqual((row["share_heart_rate"], row["share_steps"]), (0, 0))               # PR4

    def test_expired_invitation_cannot_be_accepted(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE invitations SET created_at = ?", (old,))
        inv = self.sql("SELECT id FROM invitations")[0]["id"]
        self.assertEqual(b.post(f"/invitations/{inv}/accept").status_code, 403)              # PR5

    def test_odd_device_id_and_huge_steps_do_not_crash(self):
        c, user = self.new_user("Sara", "sara@example.com")
        device_id, token = self.device(c)
        r = c.post("/api/readings", data='{"device_id":"\\ud800","type":"steps","value":1,"timestamp":"2026-01-01T00:00:00Z"}',
                   content_type="application/json", headers={"Authorization": "Bearer " + token})
        self.assertEqual(r.status_code, 400)                                                  # SR13, SR19
        self.assertEqual(self.send(c, device_id, token, "steps", 10 ** 400).status_code, 201)
        r = c.get(f"/api/wearers/{user['id']}/steps")
        self.assertEqual(r.status_code, 200)                                                  # FR23, SR19

    def test_deletions_are_logged(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        self.device(a)
        self.device(a)                                                       # replaces the device
        inv = self.link(a, b, "noura@example.com")
        a.post(f"/contacts/{inv}/remove")
        a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        inv2 = self.sql("SELECT id FROM invitations")[0]["id"]
        b.post(f"/invitations/{inv2}/decline")
        events = {r["event_type"] for r in self.sql("SELECT event_type FROM audit_log")}
        for e in ("device_deletion", "contact_deletion", "invitation_deletion"):
            self.assertIn(e, events)                                                          # SR21

    def test_expired_sessions_are_removed(self):
        from wellness import retention
        c = self.client()
        self.register(c)
        self.login(c)
        old = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sessions SET last_seen = ?", (old,))
        with self.app.app_context():
            retention.apply()
        self.assertEqual(self.sql("SELECT * FROM sessions"), [])

    def test_invitation_redirects_and_safe_405_page(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        r = a.post("/invitations", data={"contact_id": user_b["contact_id"]})
        self.assertEqual(r.status_code, 302)                       # reload does not resend the form
        self.assertIn("Invitation sent.", a.get("/").get_data(as_text=True))
        r = a.get("/invitations")
        self.assertEqual(r.status_code, 405)
        self.assertNotIn("Traceback", r.get_data(as_text=True))                               # SR19

    def test_existing_key_file_is_made_owner_only(self):
        from wellness import crypto
        key_file = os.path.join(self.tmp.name, "data.key")
        with open(key_file, "wb") as f:
            f.write(base64.b64encode(os.urandom(32)))
        os.chmod(key_file, 0o644)
        crypto.load_key({"DATA_KEY": None, "KEY_FILE": key_file})
        self.assertEqual(os.stat(key_file).st_mode & 0o777, 0o600)                            # SR18

    def test_sharing_summary_edit_and_saved_message(self):
        a, user_a = self.new_user("Sara", "sara@example.com")
        b, user_b = self.new_user("Noura", "noura@example.com")
        inv = self.link(a, b, "noura@example.com")
        html = a.get("/").get_data(as_text=True)
        self.assertIn("Shared: nothing yet", html)
        self.assertNotIn('name="category"', html)                  # checkboxes only in edit mode
        self.assertIn('name="category"', a.get(f"/?edit={inv}").get_data(as_text=True))
        r = a.post(f"/contacts/{inv}/categories", data={"category": ["steps"]})
        self.assertEqual(r.status_code, 302)
        html = a.get("/").get_data(as_text=True)
        self.assertIn("Sharing settings saved.", html)
        self.assertIn("Shared: Daily step summary", html)


if __name__ == "__main__":
    unittest.main()
