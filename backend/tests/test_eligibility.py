import unittest

from backend.eligibility import evaluate, extract_skills


class EligibilityTests(unittest.TestCase):
    def test_missing_authorization_is_needs_information(self):
        job = {"country": "United Arab Emirates", "work_authorization": "Must be authorized", "required_skills": ["Python"], "preferred_skills": []}
        facts = [{"category": "skills", "fact_key": "verified_skills", "value_json": '["Python"]', "status": "VERIFIED", "country_code": None}]
        result = evaluate(job, facts)
        self.assertEqual(result["result"], "NEEDS_INFORMATION")

    def test_country_authorization_does_not_cross_border(self):
        job = {"country": "United Arab Emirates", "work_authorization": "Must be authorized", "required_skills": [], "preferred_skills": []}
        facts = [{"category": "work_authorization", "fact_key": "authorized", "value_json": "true", "status": "VERIFIED", "country_code": "India"}]
        self.assertEqual(evaluate(job, facts)["result"], "NEEDS_INFORMATION")

    def test_false_ai_skill_never_enters_profile(self):
        job = {"required_skills": ["Kubernetes"], "preferred_skills": []}
        facts = [{"category": "skills", "fact_key": "verified_skills", "value_json": '["Python"]', "status": "VERIFIED", "country_code": None}]
        self.assertIn("kubernetes", evaluate(job, facts)["match"]["missing"])

    def test_deterministic_skill_extraction(self):
        required, preferred = extract_skills("Python and Git required. Docker is nice to have.")
        self.assertIn("python", required)
        self.assertIn("docker", preferred)


if __name__ == "__main__":
    unittest.main()

