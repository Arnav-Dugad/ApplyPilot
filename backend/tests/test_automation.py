import unittest

from backend.automation import dry_run, pre_submission_validate


class AutomationTests(unittest.TestCase):
    def test_unknown_required_field_pauses_and_never_submits(self):
        result = dry_run([{"selector": "#s", "label": "Will you need sponsorship?", "required": True}], [], "GB")
        self.assertEqual(result["status"], "WAITING_FOR_USER")
        self.assertFalse(result["submission_attempted"])

    def test_captcha_and_mfa_policy_are_pause_only(self):
        for label in ("CAPTCHA", "MFA code"):
            result = dry_run([{"selector": "#x", "label": label, "required": True}], [], "IN")
            self.assertEqual(result["unknown_count"], 1)

    def test_validator_catches_wrong_or_missing_cv(self):
        result = pre_submission_validate({"cv_id": None}, [], settings={"dry_run": True, "actual_submission_enabled": False})
        self.assertTrue(result["blocked"])
        self.assertIn("No approved CV selected", result["failures"])


if __name__ == "__main__":
    unittest.main()

