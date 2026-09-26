import os
import tempfile
import unittest
from pathlib import Path

if "APPLYPILOT_DB" not in os.environ:  # every module that opens the service must use a throwaway database
    os.environ["APPLYPILOT_DB"] = str(Path(tempfile.mkdtemp()) / "autopilot.db")

from backend import service  # noqa: E402
from backend.service import AUTOPILOT, DB  # noqa: E402

QUESTIONS = [
    {"selector": "#first_name", "label": "First Name", "name": "first_name", "field_type": "text", "required": True, "options": []},
    {"selector": "#email", "label": "Email", "name": "email", "field_type": "text", "required": True, "options": []},
    {"selector": "#q1", "label": "Are you legally authorized to work in the United Kingdom?", "name": "q1", "field_type": "select", "required": True, "options": ["Yes", "No"]},
    {"selector": "#q2", "label": "How did you hear about us?", "name": "q2", "field_type": "text", "required": True, "options": []},
]


def fake_board(platform, slug, internships_only=True):
    jobs = [
        {"company": "Acme", "role": "Software Engineer Intern", "location": "London, UK", "posting_url": f"https://example.com/{slug}/1", "application_url": f"https://example.com/{slug}/1/apply",
         "description": "Python and SQL required. Docker is a plus.", "external_id": f"test:{slug}:1", "date_posted": service.now(), "board_questions": QUESTIONS,
         "source": "Test board", "application_platform": platform, "extraction_status": "BOARD_API"},
        {"company": "Acme", "role": "Data Intern", "location": "Toronto, Canada", "posting_url": f"https://example.com/{slug}/2", "description": "Python required.",
         "external_id": f"test:{slug}:2", "source": "Test board", "application_platform": platform, "extraction_status": "BOARD_API"},
    ]
    return {"company": "Acme", "jobs": jobs, "total": 40}


class AutopilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DB.execute("DELETE FROM watchlist")
        DB.execute("INSERT INTO watchlist(id,platform,slug,company,created_at) VALUES('w1','GREENHOUSE','acme-test','Acme',?)", (service.now(),))
        for f in [("personal", "full_name", "Test Candidate"), ("contact", "email", "t@example.com"), ("skills", "verified_skills", ["Python", "SQL"]), ("preferences", "locations", ["UK", "India"])]:
            DB.upsert_fact({"category": f[0], "fact_key": f[1], "value": f[2], "status": "VERIFIED", "source": "TEST"})
        DB.upsert_fact({"category": "work_authorization", "fact_key": "authorized", "country_code": "United Kingdom", "value": True, "status": "VERIFIED", "source": "TEST"})
        DB.set_setting("autopilot", {**AUTOPILOT.config(), "min_score": 50})

    def run_autopilot(self):
        run_id = "run-" + service.now()
        DB.execute("INSERT INTO autopilot_runs(id,trigger,status,started_at) VALUES(?,?,?,?)", (run_id, "TEST", "RUNNING", service.now()))
        AUTOPILOT.execute(run_id, fetch=fake_board)
        return service.one("SELECT * FROM autopilot_runs WHERE id=?", (run_id,))

    def test_full_pipeline(self):
        run = self.run_autopilot()
        self.assertEqual(run["status"], "COMPLETED", run["events"])
        self.assertEqual((run["summary"]["new"], run["summary"]["filtered"]), (1, 1))  # Toronto is outside UK/India
        job = DB.one("SELECT * FROM jobs WHERE external_id='test:acme-test:1'")
        app = service.one("SELECT * FROM applications WHERE job_id=?", (job["id"],))
        self.assertEqual(app["prep_source"], "BOARD_FORM")
        decisions = {f["label"]: f["decision"]["action"] for f in app["field_state"]}
        self.assertEqual(decisions["First Name"], "FILL")
        self.assertEqual(decisions["Are you legally authorized to work in the United Kingdom?"], "FILL")
        self.assertEqual(decisions["How did you hear about us?"], "PAUSE")
        self.assertEqual(app["status"], "WAITING_FOR_USER")

        # The Inbox groups the paused question; answering once resolves the application.
        question = next(q for q in service.inbox()["questions"] if q["question"] == "How did you hear about us?")
        self.assertEqual(question["kind"], "ANSWER")
        result = service.answer_question({"question": question["question"], "value": "University careers fair", "classification": question["classification"]})
        self.assertGreaterEqual(result["applications_updated"], 1)
        app = service.one("SELECT * FROM applications WHERE id=?", (app["id"],))
        self.assertEqual(app["status"], "READY_FOR_REVIEW")

        # A second run finds nothing new and does not queue duplicates.
        again = self.run_autopilot()
        self.assertEqual(again["summary"]["new"], 0)
        self.assertEqual(DB.one("SELECT COUNT(*) AS n FROM applications WHERE job_id=?", (job["id"],))["n"], 1)
        self.assertTrue(DB.rows("SELECT * FROM notifications WHERE kind='AUTOPILOT'"))

    def test_answering_a_country_question_saves_a_scoped_fact(self):
        service.answer_question({"question": "Will you require sponsorship?", "classification": "SPONSORSHIP", "value": "No", "country": "Ireland"})
        stored = DB.one("SELECT * FROM profile_facts WHERE category='sponsorship' AND country_code='Ireland'")
        self.assertEqual((stored["value_json"], stored["status"]), ("false", "VERIFIED"))
        with self.assertRaises(ValueError):
            service.answer_question({"question": "Portfolio password", "value": "secret"})

    def test_cv_suggestions_need_acceptance(self):
        created = service.add_suggestions([{"category": "contact", "fact_key": "github", "value": "https://github.com/test", "confidence": 0.9, "evidence": "github.com/test"}], "CV: test.pdf")
        self.assertEqual(created, 1)
        self.assertIsNone(DB.one("SELECT * FROM profile_facts WHERE fact_key='github'"))
        pending = DB.one("SELECT id FROM suggestions WHERE fact_key='github' AND status='PENDING'")
        service.accept_suggestion(pending["id"])
        self.assertEqual(DB.one("SELECT status FROM profile_facts WHERE fact_key='github'")["status"], "VERIFIED")
        self.assertEqual(service.add_suggestions([{"category": "contact", "fact_key": "github", "value": "https://github.com/test", "confidence": 0.9, "evidence": ""}], "again"), 0)

    def test_employer_name_is_not_a_required_skill(self):
        job = service.save_job({"company": "Figma", "role": "Design Engineer Intern", "posting_url": "https://example.com/figma-skill", "description": "Build Figma plugins with TypeScript and React."})
        self.assertNotIn("figma", job["required_skills"])
        self.assertIn("typescript", job["required_skills"])

    def test_placeholders_block_draft_approval(self):
        draft = service._save_draft("COVER_LETTER", "Dear team, I built [add a project].", "test-model", None)
        with self.assertRaisesRegex(ValueError, "placeholders"):
            service.update_draft(draft["id"], None, True)
        service.update_draft(draft["id"], "Dear team, I built a scheduler in Python.", True)
        self.assertEqual(DB.one("SELECT status FROM drafts WHERE id=?", (draft["id"],))["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
