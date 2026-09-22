import json
import tempfile
import unittest
from pathlib import Path

from backend.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_defaults_are_safe(self):
        self.assertTrue(self.db.setting("strict_accuracy_mode"))
        self.assertTrue(self.db.setting("dry_run"))
        self.assertFalse(self.db.setting("actual_submission_enabled"))

    def test_profile_change_expires_dependent_answer(self):
        fact = self.db.upsert_fact({"category": "contact", "fact_key": "email", "value": "a@example.com", "status": "VERIFIED", "source": "TEST"})
        self.db.execute("INSERT INTO answer_vault(id,canonical_question,normalized_pattern,answer_type,answer_json,status,source_fact_ids_json,updated_at) VALUES(?,?,?,?,?,?,?,datetime('now'))", ("answer", "Email", "email", "EXACT", json.dumps("a@example.com"), "VERIFIED", json.dumps([fact["id"]])))
        self.db.execute("INSERT INTO fact_dependencies(fact_id,dependent_type,dependent_id,fact_revision) VALUES(?,?,?,?)", (fact["id"], "ANSWER", "answer", 1))
        self.db.upsert_fact({"category": "contact", "fact_key": "email", "value": "b@example.com", "status": "VERIFIED", "source": "TEST"})
        self.assertEqual(self.db.one("SELECT status FROM answer_vault WHERE id='answer'")["status"], "EXPIRED")


if __name__ == "__main__":
    unittest.main()

