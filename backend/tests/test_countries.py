import unittest

from backend.automation import dry_run
from backend.countries import country_key, same_country
from backend.eligibility import evaluate


def fact(category, key, value, country):
    return {"category": category, "fact_key": key, "value": value, "status": "VERIFIED", "country_code": country}


class CountryTests(unittest.TestCase):
    def test_codes_and_names_agree(self):
        self.assertEqual(country_key("IN"), country_key("India"))
        self.assertEqual(country_key("UK"), country_key("United Kingdom"))
        self.assertEqual(country_key("uae"), "AE")
        self.assertTrue(same_country("usa", "United States"))

    def test_different_countries_never_match(self):
        self.assertFalse(same_country("India", "United Arab Emirates"))
        self.assertFalse(same_country(None, "India"))
        self.assertFalse(same_country("India", None))

    def test_unlisted_countries_compare_by_name(self):
        self.assertTrue(same_country("Estonia", " estonia "))
        self.assertFalse(same_country("Estonia", "Latvia"))

    def test_authorization_matches_iso_code_on_job(self):
        job = {"country": "IN", "work_authorization": "Must be authorized to work in India", "required_skills": [], "preferred_skills": []}
        self.assertEqual(evaluate(job, [fact("work_authorization", "authorized", True, "India")])["result"], "ELIGIBLE")

    def test_dry_run_fills_sponsorship_for_matching_country_only(self):
        facts = [fact("sponsorship", "requires_sponsorship", False, "United Kingdom")]
        fields = [{"selector": "#s", "label": "Will you require visa sponsorship?", "required": True}]
        self.assertEqual(dry_run(fields, facts, "GB")["fields"][0]["decision"]["action"], "FILL")
        self.assertEqual(dry_run(fields, facts, "IE")["fields"][0]["decision"]["action"], "PAUSE")


class SponsorshipEligibilityTests(unittest.TestCase):
    job = {"country": "GB", "sponsorship_information": "We are unable to sponsor visas for this role.", "required_skills": [], "preferred_skills": []}

    def test_needing_sponsorship_where_none_offered_is_ineligible(self):
        result = evaluate(self.job, [fact("sponsorship", "requires_sponsorship", True, "GB")])
        self.assertEqual(result["result"], "INELIGIBLE")

    def test_not_needing_sponsorship_passes(self):
        facts = [fact("sponsorship", "requires_sponsorship", False, "United Kingdom"), fact("work_authorization", "authorized", True, "GB")]
        result = evaluate(self.job, facts)
        self.assertEqual(next(c for c in result["checks"] if c["name"] == "Sponsorship")["result"], "PASS")
        self.assertEqual(result["result"], "ELIGIBLE")

    def test_unknown_need_asks(self):
        self.assertEqual(evaluate(self.job, [])["result"], "NEEDS_INFORMATION")

    def test_ambiguous_wording_asks_even_when_need_is_known(self):
        job = {**self.job, "sponsorship_information": "Sponsorship considered case by case."}
        self.assertEqual(evaluate(job, [fact("sponsorship", "requires_sponsorship", True, "GB")])["result"], "NEEDS_INFORMATION")


if __name__ == "__main__":
    unittest.main()
