import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

TEMP = tempfile.TemporaryDirectory()
STATIC = Path(TEMP.name) / "dist"
STATIC.mkdir()
(STATIC / "index.html").write_text("<!doctype html><title>ApplyPilot</title>", encoding="utf-8")
(STATIC / "app.js").write_text("console.log('ok')", encoding="utf-8")
os.environ.setdefault("APPLYPILOT_DB", str(Path(TEMP.name) / "server.db"))
os.environ["APPLYPILOT_STATIC"] = str(STATIC)

from backend import server  # noqa: E402  (environment must be set before the module opens its database)
from backend.job_parser import _public_url, import_url  # noqa: E402


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.create_server("127.0.0.1", 0)
        cls.port = cls.httpd.server_port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def call(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = None if body is None else json.dumps(body)
        sent = {"Content-Type": "application/json"} if body is not None else {}
        sent.update(headers or {})
        conn.request(method, path, body=payload, headers=sent)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            return response.status, json.loads(raw)
        except json.JSONDecodeError:
            return response.status, raw.decode()

    def manual_job(self, **overrides):
        job = {"company": "Acme", "role": "Software Intern", "location": "London", "country": "United Kingdom", "description": "Python and Git required. Docker is nice to have. We are unable to offer visa sponsorship."}
        job.update(overrides)
        status, body = self.call("POST", "/api/jobs/manual", job)
        self.assertEqual(status, 201, body)
        return body

    def test_serves_ui_and_falls_back_to_index(self):
        self.assertIn("ApplyPilot", self.call("GET", "/")[1])
        self.assertIn("ApplyPilot", self.call("GET", "/profile")[1])
        self.assertEqual(self.call("GET", "/app.js")[1], "console.log('ok')")

    def test_static_paths_cannot_escape_the_ui_folder(self):
        status, body = self.call("GET", "/../server.db")
        self.assertEqual(status, 200)
        self.assertIn("ApplyPilot", body)

    def test_rejects_cross_site_requests(self):
        status, _ = self.call("POST", "/api/settings", {"actual_submission_enabled": True}, {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertFalse(server.DB.setting("actual_submission_enabled"))

    def test_rejects_simple_form_posts(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/settings", body='{"actual_submission_enabled": true}', headers={"Content-Type": "text/plain"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()
        self.assertFalse(server.DB.setting("actual_submission_enabled"))

    def test_rejects_dns_rebinding_host(self):
        status, _ = self.call("GET", "/api/bootstrap", headers={"Host": "attacker.example:4817"})
        self.assertEqual(status, 403)

    def test_accepts_dev_server_origin(self):
        status, _ = self.call("GET", "/api/bootstrap", headers={"Origin": "http://localhost:1420", "Host": "localhost:1420"})
        self.assertEqual(status, 200)

    def test_manual_job_requires_company_and_role_and_extracts_skills(self):
        self.assertEqual(self.call("POST", "/api/jobs/manual", {"company": " ", "role": "Intern"})[0], 400)
        job = self.manual_job(company="SkillCo", posting_url="https://example.com/skillco")
        self.assertIn("python", job["required_skills"])
        self.assertIn("docker", job["preferred_skills"])
        self.assertEqual(job["extraction_status"], "USER_ENTERED")
        self.assertEqual(job["sponsorship_information"], "We are unable to offer visa sponsorship.")

    def test_queue_attaches_latest_approved_cv(self):
        pdf = base64.b64encode(b"%PDF-1.4\n% queue test\n").decode()
        status, cv = self.call("POST", "/api/cvs/import", {"filename": "cv.pdf", "content_base64": pdf})
        self.assertEqual(status, 201, cv)
        self.assertEqual(self.call("POST", "/api/cvs/import", {"filename": "copy.pdf", "content_base64": pdf})[0], 400)
        self.assertEqual(self.call("POST", f"/api/cvs/{cv['id']}/approve", {"approved": True})[0], 200)
        job = self.manual_job(company="QueueCo", posting_url="https://example.com/queueco")
        status, app = self.call("POST", f"/api/jobs/{job['id']}/queue", {})
        self.assertEqual(status, 201)
        self.assertEqual(server.DB.one("SELECT cv_id FROM applications WHERE id=?", (app["id"],))["cv_id"], cv["id"])
        self.assertEqual(self.call("POST", f"/api/jobs/{job['id']}/queue", {})[0], 409)

    def test_tracker_status_and_deletes(self):
        job = self.manual_job(company="TrackCo", posting_url="https://example.com/trackco")
        app = self.call("POST", f"/api/jobs/{job['id']}/queue", {})[1]
        self.assertEqual(self.call("POST", f"/api/applications/{app['id']}/status", {"status": "SUBMITTED_BY_BOT"})[0], 400)
        self.assertEqual(self.call("POST", f"/api/applications/{app['id']}/status", {"status": "APPLIED"})[0], 200)
        self.assertIsNotNone(server.DB.one("SELECT submitted_at FROM applications WHERE id=?", (app["id"],))["submitted_at"])
        self.assertEqual(self.call("DELETE", f"/api/jobs/{job['id']}", {})[0], 400)
        self.assertEqual(self.call("DELETE", f"/api/applications/{app['id']}", {})[0], 200)
        self.assertEqual(self.call("DELETE", f"/api/jobs/{job['id']}", {})[0], 200)
        self.assertEqual(self.call("DELETE", f"/api/jobs/{job['id']}", {})[0], 404)

    def test_bootstrap_includes_saved_eligibility(self):
        job = self.manual_job(company="EligCo", posting_url="https://example.com/eligco")
        self.call("POST", f"/api/jobs/{job['id']}/analyze", {})
        saved = next(j for j in self.call("GET", "/api/bootstrap")[1]["jobs"] if j["id"] == job["id"])
        self.assertEqual(saved["eligibility_result"], "NEEDS_INFORMATION")
        self.assertIn("missing", saved["eligibility_match"])

    def test_answer_vault_approval(self):
        status, answer = self.call("POST", "/api/answers", {"canonical_question": "Are you over 18?", "answer": "Yes", "answer_type": "EXACT"})
        self.assertEqual((status, answer["status"]), (201, "UNVERIFIED"))
        self.assertEqual(self.call("POST", f"/api/answers/{answer['id']}/approve", {})[1]["status"], "VERIFIED")


class ImporterTests(unittest.TestCase):
    def test_private_addresses_blocked(self):
        for url in ("http://127.0.0.1/admin", "http://localhost:4817/api/bootstrap", "file:///etc/passwd"):
            with self.assertRaises(ValueError):
                _public_url(url)

    def test_redirect_to_private_network_is_blocked(self):
        from backend import job_parser

        handler = job_parser._PublicOnlyRedirects()
        with self.assertRaises(ValueError):
            handler.redirect_request(mock.Mock(), None, 302, "Found", {}, "http://127.0.0.1:4817/api/bootstrap")

    def test_blocked_sites_give_actionable_message(self):
        import urllib.error

        from backend import job_parser

        error = urllib.error.HTTPError("https://example.com/job", 403, "Forbidden", {}, None)
        with mock.patch.object(job_parser, "_public_url"), mock.patch.object(job_parser._OPENER, "open", side_effect=error):
            with self.assertRaisesRegex(ValueError, "Add the job manually"):
                import_url("https://example.com/job")


if __name__ == "__main__":
    unittest.main()
