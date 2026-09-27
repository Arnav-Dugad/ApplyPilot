import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

if "APPLYPILOT_DB" not in os.environ:  # every module that opens the service must use a throwaway database
    os.environ["APPLYPILOT_DB"] = str(Path(tempfile.mkdtemp()) / "v05.db")

from backend.automation import countries_named, dry_run
from backend.eligibility import evaluate
from backend.requirements import extract, seniority, tags
from backend.safety import classify_field
from backend.student import profile
from backend.visa import work_rights


def fact(category, key, value, country=None):
    return {"category": category, "fact_key": key, "value": value, "status": "VERIFIED", "country_code": country}


STUDENT = [
    fact("citizenship", "countries", ["India"]),
    fact("education", "level", "BACHELOR"),
    fact("education", "degree_name", "B.Tech"),
    fact("education", "degree", "Computer Science and Engineering"),
    fact("education", "graduation_date", "2028-05"),
    fact("education", "cgpa", {"value": 8.7, "scale": 10}),
    fact("experience", "none", True),
]


class RequirementExtractionTests(unittest.TestCase):
    def test_seniority_from_title(self):
        self.assertEqual(seniority("Software Engineer Intern (Summer 2027)"), "INTERN")
        self.assertEqual(seniority("Senior Staff Engineer, Autonomy"), "SENIOR")
        self.assertEqual(seniority("New Grad Software Engineer 2027"), "NEW_GRAD")
        self.assertEqual(seniority("Early Careers & Interns Specialist"), "UNKNOWN")  # hires interns; is not one

    def test_required_experience_with_evidence(self):
        found = extract("Engineer", "Requirements:\n• 7+ years of experience of industry experience\n• Python")
        self.assertEqual(found["experience"]["min_years"], 7)
        self.assertTrue(found["experience"]["required"])
        self.assertIn("7+ years", found["experience"]["evidence"])

    def test_preferred_and_coursework_experience_is_not_required(self):
        self.assertFalse(extract("Intern", "Preferred qualifications:\n• 2+ years of experience with Go")["experience"]["required"])
        self.assertFalse(extract("Intern", "1+ years of hands-on SQL experience through coursework, projects, or prior internships")["experience"]["required"])
        self.assertNotIn("experience", extract("Intern", "Candidates should have less than 2 years of relevant full-time work experience."))

    def test_graduation_windows(self):
        cases = {
            "Expected graduation date of Winter 2027/Spring 2028": ("2027-12", "2028-05"),
            "with a graduation date between December 2027 and June 2028 (required)": ("2027-12", "2028-06"),
            "Must be planning on graduating in 2028.": ("2028-01", "2028-12"),
            "Must graduate before December 2027.": (None, "2027-12"),
            "Computer Science degree, graduating December 2027 or later": ("2027-12", None),
            "Expected graduation date 12/2027 or 5/2028": ("2027-12", "2028-05"),
        }
        for text, (earliest, latest) in cases.items():
            window = extract("Intern", text)["graduation"]
            self.assertEqual((window["earliest"], window["latest"]), (earliest, latest), text)

    def test_graduate_degree_is_not_a_graduation_date(self):
        self.assertNotIn("graduation", extract("Intern", "Pursuing an undergraduate or graduate degree and will be enrolled full-time in Fall 2027."))

    def test_gpa_citizenship_and_sponsorship(self):
        found = extract("Intern", "Must have and maintain a minimum GPA of a 2.8 or higher.\nActive US Security clearance or eligibility to obtain one.\n"
                                  "Please note the Company may not be able to employ candidates who have U.S. work authorization related to certain U.S. visa categories, or support future H-1B sponsorship at this time.")
        self.assertEqual((found["gpa"]["min"], found["gpa"]["scale"]), (2.8, 4.0))
        self.assertEqual(found["citizenship"]["countries"], ["US"])
        self.assertTrue(found["citizenship"]["clearance"])
        self.assertFalse(found["sponsorship"]["offered"])

    def test_noise_is_ignored(self):
        found = extract("Intern", "We hire regardless of race, citizenship, or age. You'll join company sponsored events. Experience navigating export control and ITAR recruiting.")
        self.assertNotIn("citizenship", found)
        self.assertNotIn("sponsorship", found)

    def test_board_listing_hints(self):
        found = extract("SWE Intern", "", {"terms": ["Summer 2027"], "sponsorship": "Offers Sponsorship", "degrees": ["Bachelor's", "Master's"]})
        self.assertTrue(found["sponsorship"]["offered"])
        self.assertEqual(found["term"]["windows"][0], {"label": "Summer 2027", "start": "2027-05", "end": "2027-08"})
        self.assertEqual(found["degree"]["accepted"], ["BACHELOR", "MASTER"])
        self.assertIn("Sponsors visas", [t["label"] for t in tags(found)])


class VisaTests(unittest.TestCase):
    def test_citizen_free_movement_and_visa(self):
        self.assertTrue(work_rights(STUDENT, "India")["authorized"])
        self.assertTrue(work_rights(STUDENT, "Nepal")["authorized"])  # India–Nepal treaty
        germany = work_rights(STUDENT, "Germany")
        self.assertEqual((germany["authorized"], germany["needs_visa"], germany["source"]), (False, True, "CITIZENSHIP"))
        french = [fact("citizenship", "countries", ["France"])]
        self.assertTrue(work_rights(french, "Germany")["authorized"])
        self.assertFalse(work_rights(french, "US")["authorized"])

    def test_your_answer_always_wins(self):
        facts = STUDENT + [fact("work_authorization", "authorized", True, "Germany")]
        self.assertEqual(work_rights(facts, "DE")["source"], "YOUR_ANSWER")
        self.assertTrue(work_rights(facts, "DE")["authorized"])

    def test_permit_holders_are_asked(self):
        facts = STUDENT + [fact("citizenship", "work_permits", [{"country": "US", "kind": "F-1 student visa"}])]
        self.assertIsNone(work_rights(facts, "US")["authorized"])

    def test_no_citizenship_means_unknown(self):
        self.assertIsNone(work_rights([], "US")["authorized"])


class StudentProfileTests(unittest.TestCase):
    def test_year_of_study_is_worked_out(self):
        me = profile(STUDENT, today=datetime(2026, 9, 27, tzinfo=timezone.utc))
        self.assertEqual((me["year_of_study"], me["program_years"], me["enrolled"]), (3, 4, True))
        self.assertIn("year_of_study", me["derived"])
        self.assertTrue(me["experience"]["none"])

    def test_experience_months(self):
        facts = [fact("experience", "entries", [{"kind": "INTERNSHIP", "start": "2026-05", "end": "2026-07"}, {"kind": "JOB", "start": "2024-01", "end": "2025-12"}])]
        me = profile(facts)
        self.assertEqual((me["experience"]["internship_count"], me["experience"]["work_years"]), (1, 2.0))


class StudentEligibilityTests(unittest.TestCase):
    def evaluate(self, role, description, country="IN", extra=()):
        return evaluate({"role": role, "description": description, "country": country, "required_skills": [], "preferred_skills": []}, STUDENT + list(extra))

    def test_senior_role_is_not_a_fit(self):
        result = self.evaluate("Senior Software Engineer", "5+ years of experience building distributed systems.")
        self.assertEqual(result["result"], "INELIGIBLE")
        self.assertEqual({c["name"] for c in result["checks"] if c["result"] == "FAIL"}, {"Level", "Experience"})

    def test_graduation_window(self):
        self.assertEqual(self.evaluate("SWE Intern", "Must be planning on graduating in 2027.")["result"], "INELIGIBLE")
        self.assertEqual(self.evaluate("SWE Intern", "Graduating between December 2027 and June 2028.")["result"], "ELIGIBLE")

    def test_masters_only(self):
        result = self.evaluate("Research Intern", "We're looking for Masters or PhD students.")
        self.assertEqual(next(c for c in result["checks"] if c["name"] == "Degree")["result"], "FAIL")

    def test_visa_needed_is_its_own_state(self):
        self.assertEqual(self.evaluate("SWE Intern", "Build things.", "DE")["result"], "VISA_NEEDED")
        self.assertEqual(self.evaluate("SWE Intern", "We will not sponsor individuals for employment visas.", "DE")["result"], "INELIGIBLE")
        self.assertEqual(self.evaluate("SWE Intern", "Build things.", "IN")["result"], "ELIGIBLE")

    def test_citizens_only(self):
        result = self.evaluate("SWE Intern", "Must be a U.S. citizen.", "US")
        self.assertEqual(next(c for c in result["checks"] if c["name"] == "Citizenship")["result"], "FAIL")

    def test_gpa_conversion_warns_instead_of_rejecting(self):
        check = next(c for c in self.evaluate("SWE Intern", "A GPA of 3.5+")["checks"] if c["name"] == "GPA")
        self.assertEqual(check["result"], "WARN")  # 8.7/10 is about 3.48/4.0, and conversions vary
        self.assertIn("8.7/10", check["explanation"])
        check = next(c for c in self.evaluate("SWE Intern", "Minimum GPA of 3.0")["checks"] if c["name"] == "GPA")
        self.assertEqual(check["result"], "PASS")

    def test_evidence_travels_with_checks(self):
        result = self.evaluate("Engineer II", "3+ years of experience developing software.")
        self.assertIn("3+ years", next(c for c in result["checks"] if c["name"] == "Experience")["evidence"])


class ClassifierV05Tests(unittest.TestCase):
    CASES = [
        ("Are you currently enrolled in an academic program?", ["Yes", "No"], "ENROLLED"),
        ("Are you currently enrolled in a Master's degree program?", ["Yes", "No"], "UNKNOWN"),
        ("Are you currently pursuing a bachelor’s degree in Accounting, Finance, or a related field?", ["Yes", "No"], "UNKNOWN"),
        ("Are you currently enrolled in a degree programme, or did you complete a degree within the last 12 months?", ["Yes", "No"], "UNKNOWN"),
        ("Are you a U.S. citizen?", ["Yes", "No"], "CITIZENSHIP"),
        ("Country of citizenship", [], "CITIZENSHIP"),
        ("Years of experience", [], "YEARS_OF_EXPERIENCE"),
        ("How many years of experience do you have with Python?", [], "UNKNOWN"),
        ("Degree", ["Bachelor's", "Master's"], "DEGREE_LEVEL"),
        ("Field of study", [], "MAJOR"),
        ("Year of study", ["1st", "2nd", "3rd", "4th"], "YEAR_OF_STUDY"),
        ("When are you available to start an internship?", [], "START_DATE"),
        ("Are you able to start on June 1?", ["Yes", "No"], "UNKNOWN"),
        ("Have you ever been subject to disciplinary action?", ["Yes", "No"], "UNKNOWN"),
        ("Expected graduation date for your degree program", [], "GRADUATION_DATE"),
    ]

    def test_cases_with_field_types(self):
        wrong = [(label, got, want) for label, options, want in self.CASES
                 if (got := classify_field(label, "", "select" if options else "text", options)) != want]
        self.assertEqual(wrong, [])

    def test_countries_named(self):
        self.assertEqual(countries_named("Are you authorized to work for us?"), set())
        self.assertEqual(countries_named("Do you require sponsorship to work in the US?"), {"US"})
        self.assertEqual(countries_named("Are you authorized to work in India?"), {"IN"})


class InboxV05Tests(unittest.TestCase):
    def test_outdated_classification_and_missing_country_are_fixed(self):
        import json
        from backend import service
        from backend.database import now

        DB = service.DB
        job = service.save_job({"company": "InboxCo", "role": "SWE Intern", "location": "Somewhere", "posting_url": "https://example.com/inboxco", "description": "Python"})
        DB.execute("UPDATE jobs SET country=NULL WHERE id=?", (job["id"],))
        fields = [
            {"selector": "#a", "label": "After the OPT, are you eligible for a 24-month OPT extension based upon a degree from a qualifying U.S. institution?", "required": True,
             "classification": "EDUCATION", "options": ["Yes", "No"], "decision": {"action": "PAUSE", "reason": "old"}},
            {"selector": "#b", "label": "Are you authorized to work lawfully for InboxCo?", "required": True, "classification": "WORK_AUTHORIZATION", "options": ["Yes", "No"], "decision": {"action": "PAUSE", "reason": "x"}},
            {"selector": "#c", "label": "Are you authorized to work in the United States?", "required": True, "classification": "WORK_AUTHORIZATION", "options": ["Yes", "No"], "decision": {"action": "PAUSE", "reason": "x"}},
        ]
        DB.execute("INSERT INTO applications(id,job_id,status,dry_run,mode,field_state_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                   ("app-inbox-test", job["id"], "WAITING_FOR_USER", 1, "REVIEW_BEFORE_SUBMIT", json.dumps(fields), now(), now()))
        try:
            questions = {q["question"]: q for q in service.inbox()["questions"] if any(a["id"] == "app-inbox-test" for a in q["applications"])}
            self.assertEqual(questions[fields[0]["label"]]["kind"], "ANSWER")  # never "saved to your profile" as a university
            self.assertEqual(questions[fields[1]["label"]]["kind"], "ANSWER")  # no country to file it under
            us = questions[fields[2]["label"]]
            self.assertEqual((us["kind"], us["country"]), ("COUNTRY_FACT", "US"))
        finally:
            DB.execute("DELETE FROM applications WHERE id='app-inbox-test'")


class AutofillV05Tests(unittest.TestCase):
    def run_fields(self, fields, country="US", facts=None):
        rows = [{"selector": f"#{i}", "label": label, "options": options, "field_type": "select" if options else "text", "required": True} for i, (label, options) in enumerate(fields)]
        return {f["label"]: f["decision"] for f in dry_run(rows, facts or STUDENT + [fact("education", "year_of_study", 3)], country)["fields"]}

    def test_question_about_another_country_uses_that_country(self):
        facts = STUDENT + [fact("work_authorization", "authorized", True, "India")]
        out = self.run_fields([("Are you authorized to work in India?", ["Yes", "No"]), ("Are you authorized to work in the U.S. and Canada?", ["Yes", "No"])], "US", facts)
        self.assertEqual(out["Are you authorized to work in India?"]["value"], "Yes")
        self.assertEqual(out["Are you authorized to work in the U.S. and Canada?"]["action"], "PAUSE")

    def test_worked_out_visa_answers(self):
        out = self.run_fields([("Are you legally authorized to work in the United States?", ["Yes", "No"]), ("Will you now or in the future require visa sponsorship?", ["Yes", "No"])])
        self.assertEqual([d["value"] for d in out.values()], ["No", "Yes"])
        self.assertTrue(all("citizenship" in d["source"] for d in out.values()))

    def test_profile_fields(self):
        out = self.run_fields([("Are you a U.S. citizen?", ["Yes", "No"]), ("Do you hold dual citizenship?", ["Yes", "No"]), ("Degree", ["Bachelor's Degree", "Master's Degree"]),
                               ("Highest level of education", ["Bachelor's (in progress)", "Bachelor's (completed)"]), ("Current year in school", ["Freshman", "Sophomore", "Junior", "Senior"]),
                               ("Years of experience", ["0-1 years", "1-3 years", "3+ years"]), ("GPA", []), ("CGPA (out of 10)", []), ("Major", [])])
        self.assertEqual(out["Are you a U.S. citizen?"]["value"], "No")
        self.assertEqual(out["Do you hold dual citizenship?"]["action"], "PAUSE")
        self.assertEqual(out["Degree"]["value"], "Bachelor's Degree")
        self.assertEqual(out["Highest level of education"]["action"], "PAUSE")  # two Bachelor's options: you choose
        self.assertEqual(out["Current year in school"]["value"], "Junior")
        self.assertEqual(out["Years of experience"]["value"], "0-1 years")
        self.assertEqual(out["GPA"]["action"], "PAUSE")  # a 10-point CGPA never goes into a field that may expect 4.0
        self.assertEqual(out["CGPA (out of 10)"]["value"], "8.7")
        self.assertEqual(out["Major"]["value"], "Computer Science and Engineering")

    def test_worked_out_year_of_study_is_never_autofilled(self):
        out = self.run_fields([("Year of study", ["1st year", "2nd year", "3rd year", "4th year"])], facts=STUDENT)
        self.assertEqual(out["Year of study"]["action"], "PAUSE")


if __name__ == "__main__":
    unittest.main()
