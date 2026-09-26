from __future__ import annotations

import json
import re
from typing import Any

from .countries import same_country
from .skills import canonical, find_skills, related_credit

PREFERRED_MARKERS = ("preferred", "nice to have", "nice-to-have", "bonus", "a plus", "is a plus", "desirable", "ideally")


def _value(row: dict[str, Any]) -> Any:
    value = row.get("value", row.get("value_json"))
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


NO_SPONSORSHIP = re.compile(r"(?i)\b(no|not|unable to|cannot|can't|won't|will not|does not|do not)\b[\w\s,]{0,30}\bsponsor")


def country_fact(verified: list[dict[str, Any]], category: str, key: str, country: str | None) -> Any:
    """Country-scoped facts never cross borders: only an exact country match counts."""
    match = next((f for f in verified if f["category"] == category and f["fact_key"] == key and same_country(f.get("country_code"), country)), None)
    return _value(match) if match else None


def evaluate(job: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    verified = [f for f in facts if f.get("status") == "VERIFIED"]
    fact_map = {(f["category"], f["fact_key"], f.get("country_code")): _value(f) for f in verified}
    skills: set[str] = set()
    for f in verified:
        if f["category"] == "skills":
            val = _value(f)
            skills.update(canonical(v) for v in (val if isinstance(val, list) else [str(val)]))
    required = [canonical(x) for x in job.get("required_skills", [])]
    preferred = [canonical(x) for x in job.get("preferred_skills", [])]
    strong = sorted(set(required + preferred) & skills)
    missing = sorted(set(required) - skills)
    partial = sorted(s for s in preferred if s not in skills)
    related = sorted(s for s in missing if related_credit(s, skills))
    checks: list[dict[str, str]] = []

    degree_req = job.get("degree_requirements")
    degree = fact_map.get(("education", "degree", None))
    if degree_req:
        checks.append({"name": "Degree requirement", "result": "PASS" if degree and any(t in str(degree).lower() for t in ("computer", "software", "information")) else "UNKNOWN", "explanation": "Compared only with verified education."})
    country = job.get("country")
    work_text = job.get("work_authorization")
    if work_text or country:
        auth = country_fact(verified, "work_authorization", "authorized", country)
        checks.append({"name": "Work authorization", "result": "PASS" if auth is True else "FAIL" if auth is False else "UNKNOWN", "explanation": f"Country-specific answer for {country or 'this location'} only."})
    sponsorship_text = job.get("sponsorship_information")
    if sponsorship_text:
        needs = country_fact(verified, "sponsorship", "requires_sponsorship", country)
        if needs is False:
            sponsorship, why = "PASS", "You do not require sponsorship here."
        elif needs is True and NO_SPONSORSHIP.search(sponsorship_text):
            sponsorship, why = "FAIL", "The posting says it does not sponsor, and you require sponsorship here."
        elif needs is True:
            sponsorship, why = "UNKNOWN", "Sponsorship wording is ambiguous; review it before applying."
        else:
            sponsorship, why = "UNKNOWN", f"Your sponsorship need for {country or 'this location'} is not verified."
        checks.append({"name": "Sponsorship", "result": sponsorship, "explanation": why})
    checks.append({"name": "Required skills", "result": "PASS" if not missing else "PARTIAL", "explanation": f"{len(strong)} matched; {len(missing)} not present in verified profile."})
    definite_fail = any(c["result"] == "FAIL" for c in checks)
    unknown = any(c["result"] == "UNKNOWN" for c in checks)
    result = "INELIGIBLE" if definite_fail else "NEEDS_INFORMATION" if unknown else "ELIGIBLE" if not missing else "LIKELY_ELIGIBLE"
    coverage = round(100 * len(set(required) & skills) / len(set(required)), 0) if required else None
    # Related skills (e.g. MySQL for PostgreSQL) earn half credit in ranking only, never in eligibility.
    weighted = round(100 * (len(set(required) & skills) + 0.5 * len(related)) / len(set(required)), 0) if required else None
    return {"result": result, "checks": checks, "match": {"strong": strong, "partial": partial, "missing": missing, "related": related, "required_coverage": coverage, "weighted_coverage": weighted}}


def extract_skills(description: str) -> tuple[list[str], list[str]]:
    """Required vs preferred skills, decided by the sentence each skill appears in."""
    found = find_skills(description)
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", description)
    preferred = [s for s in found if all(any(m in sentence.lower() for m in PREFERRED_MARKERS) for sentence in sentences if s in find_skills(sentence))]
    required = [s for s in found if s not in preferred]
    return required, preferred
