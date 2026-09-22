import unittest

from backend.browser_runner import adapter_for, detect_pause_reason


class BrowserRunnerTests(unittest.TestCase):
    def test_adapters(self):
        expected = {
            "https://boards.greenhouse.io/acme/jobs/1": "GREENHOUSE",
            "https://jobs.lever.co/acme/1": "LEVER",
            "https://acme.wd1.myworkdayjobs.com/job": "WORKDAY",
            "https://jobs.ashbyhq.com/acme/1": "ASHBY",
            "https://jobs.smartrecruiters.com/acme/1": "SMARTRECRUITERS",
            "https://careers.example.com/apply": "GENERIC",
        }
        for url, adapter in expected.items():
            self.assertEqual(adapter_for(url), adapter)

    def test_captcha_pauses(self):
        self.assertIn("CAPTCHA", detect_pause_reason("Please complete the hCaptcha"))

    def test_mfa_pauses(self):
        self.assertIn("MFA", detect_pause_reason("Enter your authenticator code"))


if __name__ == "__main__":
    unittest.main()

