import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

if "APPLYPILOT_DB" not in os.environ:
    os.environ["APPLYPILOT_DB"] = str(Path(tempfile.mkdtemp()) / "v04.db")

from backend import __version__, maintenance, service, updater  # noqa: E402
from backend.cv_tailor import invention_flags, tailor_deterministic, to_html  # noqa: E402
from backend.database import Database  # noqa: E402
from backend.discovery import detect_board  # noqa: E402
from backend.email_sync import classify, decide  # noqa: E402
from backend.insights import fingerprint, parse_query, profile_strength, search, today  # noqa: E402
from backend.languages import detect  # noqa: E402
from backend.offers import compare, monthly  # noqa: E402
from backend.referrals import matches, parse_connections_csv  # noqa: E402

DB = service.DB


def iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- updater

def release(tag: str, data: bytes, **asset_overrides):
    name = f"ApplyPilot-Setup-{tag.lstrip('v')}.exe"
    asset = {"name": name, "size": len(data), "browser_download_url": f"https://github.com/Arnav-Dugad/ApplyPilot/releases/download/{tag}/{name}", "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
    asset.update(asset_overrides)
    return {"tag_name": tag, "draft": False, "prerelease": False, "body": "Notes", "assets": [asset], "html_url": "https://github.com/x"}


class FakeOpener:
    def __init__(self, data: bytes):
        self.data = data

    def open(self, request, timeout=None):
        return io.BytesIO(self.data)


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        updater._state.clear()
        updater._state.update({"status": "idle"})
        self.temp = tempfile.TemporaryDirectory()
        self.dir = mock.patch.object(updater, "updates_dir", lambda: Path(self.temp.name))
        self.dir.start()

    def tearDown(self):
        self.dir.stop()
        self.temp.cleanup()

    def newer(self):
        major, minor, patch = updater.parse_version(__version__)
        return f"v{major}.{minor}.{patch + 1}"

    def test_versions(self):
        self.assertGreater(updater.parse_version("v0.10.0"), updater.parse_version("0.9.9"))
        with self.assertRaises(ValueError):
            updater.parse_version("latest")

    def test_up_to_date_and_never_downgrades(self):
        self.assertEqual(updater.check(lambda _url: release(f"v{__version__}", b"x"))["status"], "up_to_date")
        self.assertEqual(updater.check(lambda _url: release("v0.0.1", b"x"))["status"], "up_to_date")

    def test_prerelease_is_ignored(self):
        self.assertEqual(updater.check(lambda _url: {**release(self.newer(), b"x"), "prerelease": True})["status"], "error")

    def test_download_verifies_checksum_and_size(self):
        data = b"MZ" + os.urandom(4096)
        state = updater.check(lambda _url: release(self.newer(), data))
        self.assertEqual(state["status"], "available")
        updater.download(FakeOpener(data), background=False)
        ready = updater.state()
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(Path(ready["installer"]).read_bytes(), data)

    def test_tampered_download_is_discarded(self):
        data = b"MZ" + os.urandom(4096)
        updater.check(lambda _url: release(self.newer(), data))
        updater.download(FakeOpener(b"MZ" + os.urandom(4096)), background=False)
        self.assertEqual(updater.state()["status"], "error")
        self.assertIn("Checksum", updater.state()["error"])
        self.assertFalse(list(Path(self.temp.name).glob("*.exe")))

    def test_oversized_download_is_discarded(self):
        data = b"MZ" + os.urandom(1024)
        updater.check(lambda _url: release(self.newer(), data))
        updater.download(FakeOpener(data + b"extra"), background=False)
        self.assertEqual(updater.state()["status"], "error")

    def test_only_official_release_urls(self):
        data = b"MZ"
        updater.check(lambda _url: release(self.newer(), data, browser_download_url="https://evil.example/ApplyPilot.exe"))
        with self.assertRaises(ValueError):
            updater.download(FakeOpener(data), background=False)
        self.assertFalse(updater._allowed_download("http://github.com/x"))
        self.assertTrue(updater._allowed_download("https://release-assets.githubusercontent.com/x"))

    def test_install_refuses_outside_installed_app(self):
        data = b"MZ" + os.urandom(64)
        updater.check(lambda _url: release(self.newer(), data))
        updater.download(FakeOpener(data), background=False)
        launched = []
        with mock.patch.object(updater, "install_mode", lambda: "portable"):
            with self.assertRaises(ValueError):
                updater.install(launcher=launched.append)
        with mock.patch.object(updater, "install_mode", lambda: "installer"):
            updater.install(launcher=launched.append)
        self.assertIn("/VERYSILENT", launched[0])
        self.assertIn("/RELAUNCH=1", launched[0])


# ---------------------------------------------------------------- backup / restore / reset

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "applypilot.db")
        self.db.upsert_fact({"category": "personal", "fact_key": "full_name", "value": "Test User", "status": "VERIFIED"})
        (Path(self.temp.name) / "uploads" / "cvs").mkdir(parents=True)
        (Path(self.temp.name) / "uploads" / "cvs" / "cv1.pdf").write_bytes(b"%PDF-1.4 test")
        self.db.execute("INSERT INTO cvs(id,name,variant,path,sha256,created_at) VALUES('cv1','cv.pdf','General','old/path.pdf','x','2026')")

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_reset_restore_round_trip(self):
        backup = maintenance.create_backup(self.db, "manual")
        self.assertTrue(backup["name"].startswith("applypilot-backup-"))
        result = maintenance.reset(self.db, backup_first=True)
        self.assertIsNotNone(result["backup"])
        self.assertEqual(self.db.rows("SELECT * FROM profile_facts"), [])
        self.assertFalse((Path(self.temp.name) / "uploads").exists())
        self.assertTrue(self.db.setting("dry_run"))
        self.assertFalse(self.db.setting("first_run_complete"))
        self.assertGreaterEqual(len(maintenance.list_backups(self.db)), 2)  # backups survive a reset
        maintenance.restore(self.db, backup["name"])
        self.assertEqual(json.loads(self.db.one("SELECT value_json FROM profile_facts")["value_json"]), "Test User")
        cv = self.db.one("SELECT path FROM cvs WHERE id='cv1'")
        self.assertTrue(Path(cv["path"]).is_file())  # CV paths re-pointed at the restored files

    def test_restore_rejects_unsafe_archives(self):
        import zipfile

        bad = maintenance.backups_dir(self.db) / "applypilot-backup-20260101-000000.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("applypilot.db", b"x")
            archive.writestr("../evil.txt", b"x")
        with self.assertRaises(ValueError):
            maintenance.restore(self.db, bad.name)
        with self.assertRaises(ValueError):
            maintenance.restore(self.db, "../../etc/passwd")


# ---------------------------------------------------------------- intelligence

class IntelligenceTests(unittest.TestCase):
    def test_duplicates(self):
        a = {"company": "Stripe, Inc.", "role": "Software Engineer Intern (Summer 2027)", "location": "London, UK"}
        b = {"company": "Stripe", "role": "Software Engineer, Internship - Summer 2027", "location": "London"}
        c = {"company": "Stripe", "role": "Software Engineer Intern", "location": "Dublin, Ireland"}
        self.assertEqual(fingerprint(a), fingerprint(b))
        self.assertNotEqual(fingerprint(a), fingerprint(c))

    def test_languages(self):
        self.assertEqual(detect("Fluent German and English are required."), {"required": ["German"], "preferred": []})
        self.assertEqual(detect("You will join our German office.")["required"], [])
        self.assertEqual(detect("Arabic is a plus.")["preferred"], ["Arabic"])

    def test_query_parsing(self):
        parsed = parse_query("backend roles with Python in Europe")
        self.assertEqual((parsed["skills"], parsed["roles"]), (["python"], ["backend"]))
        self.assertIn("DE", parsed["countries"])
        self.assertEqual(parse_query("design internships in New Zealand")["countries"], ["NZ"])
        self.assertEqual(parse_query("React frontend at Stripe")["keywords"], ["stripe"])

    def test_search_filters_and_ranks(self):
        jobs = [
            {"id": "1", "company": "A", "role": "Backend Engineer Intern", "location": "Berlin, Germany", "required_skills": ["python"], "score": {"score": 50}},
            {"id": "2", "company": "B", "role": "Frontend Intern", "location": "Paris, France", "required_skills": ["react"], "score": {"score": 90}},
            {"id": "3", "company": "C", "role": "Backend Intern", "location": "Toronto", "required_skills": ["python"], "score": {"score": 99}},
            {"id": "4", "company": "A", "role": "Backend Engineer Intern", "location": "Berlin", "required_skills": ["python"], "duplicate_of": "1"},
        ]
        self.assertEqual(search(jobs, "backend roles with Python in Europe")["ids"], ["1"])

    def test_profile_strength_and_today(self):
        strength = profile_strength([{"category": "personal", "fact_key": "full_name", "status": "VERIFIED", "value": "X"}], False)
        self.assertLess(strength["percent"], 20)
        self.assertEqual(len(strength["next"]), 3)
        jobs = [{"id": "j1", "company": "Acme", "role": "Intern", "deadline": iso(1)}]
        apps = [{"id": "a1", "job_id": "j1", "status": "READY_FOR_REVIEW", "company": "Acme", "role": "Intern"}]
        actions = today(jobs, apps, {"questions": [], "suggestions": []}, 0)
        self.assertEqual(actions[0]["kind"], "DEADLINE")


class ReferralEmailOfferTests(unittest.TestCase):
    def test_connections(self):
        text = 'Notes:\n"x"\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\nPriya,Shah,https://www.linkedin.com/in/p,,Stripe,Recruiter,1 Jan 2025\nBo,Kim,javascript:alert(1),,Striped Bass Co,Chef,1 Jan 2020\n'
        rows = parse_connections_csv(text)
        self.assertEqual([p["first_name"] for p in matches("Stripe", rows)], ["Priya"])
        self.assertEqual(rows[1]["url"], "")
        with self.assertRaises(ValueError):
            parse_connections_csv("a,b\n1,2")

    def test_email_moves_only_forward(self):
        self.assertEqual(classify("Interview invitation", "We would like to invite you to an interview"), "INTERVIEW")
        self.assertIsNone(classify("Newsletter", "Our product update"))
        apps = [{"id": "a1", "company": "Stripe", "role": "SWE Intern", "status": "APPLIED"}, {"id": "a2", "company": "Figma", "role": "Design Intern", "status": "OFFER"}]
        msgs = [{"message_id": "1", "sender": "careers@stripe.com", "subject": "Interview", "body": "We'd like to schedule an interview", "date": "2026-09-20"},
                {"message_id": "2", "sender": "careers@figma.com", "subject": "Update", "body": "Unfortunately we will not be proceeding", "date": "2026-09-21"}]
        result = {d["message_id"]: (d["action"], d["target"]) for d in decide(msgs, apps, set())}
        self.assertEqual(result, {"1": ("MOVE", "INTERVIEWING"), "2": ("NONE", "REJECTED")})

    def test_offer_maths(self):
        self.assertAlmostEqual(monthly({"amount": 10, "period": "HOUR", "hours_per_week": 40}), 10 * 40 * 52 / 12)
        rows = compare([{"company": "A", "amount": 1000, "currency": "USD", "period": "MONTH", "duration_months": 3},
                        {"company": "B", "amount": 3672.5, "currency": "AED", "period": "MONTH", "duration_months": 3}], "USD", {"USD": 1.0, "AED": 3.6725})
        self.assertEqual([r["monthly_base"] for r in rows], [1000.0, 1000.0])


class TailoringTests(unittest.TestCase):
    CV = "Test User\ntest@example.com\n\nEXPERIENCE\n• Cut build time by 35% with Docker\n\nSKILLS\nLanguages: Java, C++, Python, SQL\n"

    def test_reorders_without_adding(self):
        tailored = tailor_deterministic(self.CV, {"required_skills": ["python"], "preferred_skills": ["sql"]})
        self.assertIn("Languages: Python, SQL, Java, C++", tailored)
        self.assertEqual(invention_flags(self.CV, tailored, []), {"skills": [], "numbers": []})

    def test_flags_invented_skills_and_numbers(self):
        flags = invention_flags(self.CV, self.CV.replace("35%", "60%") + "\n• Led a Rust rewrite", [])
        self.assertEqual(flags, {"skills": ["rust"], "numbers": ["60%"]})

    def test_html_is_escaped(self):
        html = to_html("Name\n<script>alert(1)</script>", "CV")
        self.assertNotIn("<script>", html)


class BoardDetectionTests(unittest.TestCase):
    def test_new_boards(self):
        self.assertEqual(detect_board("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x"), ("WORKDAY", "nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"))
        self.assertEqual(detect_board("https://apply.workable.com/blueground/"), ("WORKABLE", "blueground"))
        self.assertEqual(detect_board("https://bunq.recruitee.com/o/x"), ("RECRUITEE", "bunq"))
        self.assertEqual(detect_board("teamtailor:career"), ("TEAMTAILOR", "career"))


# ---------------------------------------------------------------- service integration

class ServiceV04Tests(unittest.TestCase):
    def job(self, **over):
        payload = {"company": "Globex", "role": "Software Engineer Intern", "location": "London, UK", "posting_url": f"https://example.com/{os.urandom(4).hex()}", "description": "Python required."}
        payload.update(over)
        return service.save_job(payload)

    def test_duplicates_are_linked_and_not_auto_queued(self):
        first = self.job(company="Dupe Co", role="Data Intern (Summer 2027)")
        second = self.job(company="Dupe Co", role="Data Intern - Summer 2027", source="Other board")
        self.assertIsNone(first["duplicate_of"])
        self.assertEqual(second["duplicate_of"], first["id"])

    def test_votes_teach_the_ranking(self):
        liked = [self.job(company="Likeable", role=f"Backend Intern {i}") for i in range(2)]
        disliked = self.job(company="Nope Inc", role="Sales Intern", location="Toronto")
        for j in liked:
            service.vote_job(j["id"], 1)
        result = service.vote_job(disliked["id"], -1)
        self.assertTrue(result["learning"])
        fresh = self.job(company="Likeable", role="Backend Intern 9")
        analysis = service.analyze_job(fresh["id"])
        taste = next((f for f in analysis["score"]["factors"] if f["name"] == "Your taste"), None)
        self.assertIsNotNone(taste)
        self.assertGreater(taste["points"], 0)

    def test_bootstrap_never_exposes_email_secret(self):
        DB.set_setting("email_sync", {**(DB.setting("email_sync") or {}), "secret": "dpapi:SECRETVALUE", "address": "me@example.com"})
        boot = service.bootstrap()
        self.assertNotIn("SECRETVALUE", json.dumps(boot, default=str))
        self.assertTrue(boot["settings"]["email_sync"]["has_password"])
        for key in ("update", "strength", "today", "health", "offers"):
            self.assertIn(key, boot)

    def test_deadline_alert_fires_once(self):
        job = self.job(company="Deadline Co", deadline=iso(1))
        app = service.queue_job(job["id"])
        service.housekeeping()
        service.housekeeping()
        alerts = DB.rows("SELECT * FROM notifications WHERE kind='DEADLINE' AND title LIKE 'Deadline Co%'")
        self.assertEqual(len(alerts), 1)
        DB.execute("DELETE FROM applications WHERE id=?", (app["id"],))

    def test_follow_up_drafted_after_two_weeks(self):
        job = self.job(company="Followup Co")
        app = service.queue_job(job["id"])
        DB.execute("UPDATE applications SET status='APPLIED', submitted_at=? WHERE id=?", (iso(-15), app["id"]))
        self.assertGreaterEqual(service.draft_follow_ups(), 1)
        draft = DB.one("SELECT * FROM drafts WHERE application_id=? AND kind='FOLLOW_UP'", (app["id"],))
        self.assertIn("Followup Co", draft["content"])
        self.assertEqual(service.draft_follow_ups(), 0)  # never twice
        service.update_draft(draft["id"], None, True)
        self.assertIsNotNone(DB.one("SELECT followed_up_at FROM applications WHERE id=?", (app["id"],))["followed_up_at"])

    def test_email_sync_moves_and_undoes(self):
        job = self.job(company="Mailco", role="Platform Intern")
        app = service.queue_job(job["id"])
        DB.execute("UPDATE applications SET status='APPLIED' WHERE id=?", (app["id"],))
        DB.set_setting("email_sync", {**(DB.setting("email_sync") or {}), "secret": "dpapi:x", "address": "me@example.com"})
        messages = [{"message_id": "<m1@mailco>", "sender": "jobs@mailco.com", "subject": "Interview invitation", "body": "We would like to invite you to an interview", "date": "2026-09-20"}]
        with mock.patch("backend.email_sync.unprotect", lambda _t: "pw"):
            result = service.sync_email(fetch=lambda _c, _p: messages)
            self.assertEqual(result["moved"], 1)
            self.assertEqual(service.sync_email(fetch=lambda _c, _p: messages)["moved"], 0)  # same email never applied twice
        self.assertEqual(DB.one("SELECT status FROM applications WHERE id=?", (app["id"],))["status"], "INTERVIEWING")
        event = DB.one("SELECT id FROM email_events WHERE message_id='<m1@mailco>'")
        service.undo_email_move(event["id"])
        self.assertEqual(DB.one("SELECT status FROM applications WHERE id=?", (app["id"],))["status"], "APPLIED")

    def test_companies_notes_connections_prep_offers(self):
        job = self.job(company="Initech", role="ML Intern", description="Python and SQL required.")
        service.import_connections("First Name,Last Name,URL,Email Address,Company,Position,Connected On\nAna,Ruiz,https://www.linkedin.com/in/ana,,Initech Ltd,Engineer,1 Jan 2025\n")
        detail = service.job_detail(job["id"])
        self.assertEqual([p["first_name"] for p in detail["referrals"]], ["Ana"])
        key = next(c["key"] for c in service.companies() if c["name"] == "Initech")
        service.save_company_notes(key, "Initech", "Great mentorship.")
        company = service.company_detail(key)
        self.assertEqual((company["notes"], company["connections"], len(company["roles"])), ("Great mentorship.", 1, 1))
        pack = service.prep_pack(job["id"])
        self.assertTrue(pack["technical"])
        self.assertIn("Initech", pack["company_questions"][0])
        with self.assertRaises(ValueError):
            service.save_offer({"company": "X", "amount": -5, "currency": "USD"})
        service.save_offer({"company": "Initech", "amount": 2000, "currency": "USD", "period": "MONTH"})
        with mock.patch("backend.offers.fetch_rates", lambda: {"rates": {"USD": 1.0}, "source": "test"}):
            self.assertEqual(service.offers_overview("USD")["rows"][0]["monthly_base"], 2000.0)

    @unittest.skipUnless(sys.platform == "win32", "Windows data protection")
    def test_email_password_encrypted(self):
        service.save_email_settings({"provider": "GMAIL", "address": "me@example.com", "password": "abcd efgh ijkl mnop"})
        stored = DB.setting("email_sync")
        self.assertTrue(stored["secret"].startswith("dpapi:"))
        self.assertNotIn("abcd", stored["secret"])
        from backend.email_sync import unprotect
        self.assertEqual(unprotect(stored["secret"]), "abcdefghijklmnop")  # Gmail app passwords are shown with spaces


if __name__ == "__main__":
    unittest.main()
