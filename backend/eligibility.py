from __future__ import annotations

import json
import re
from typing import Any

SKILL_ALIASES = {
    "js": "javascript", "ts": "typescript", "postgres": "postgresql",
    "machine learning": "ml", "artificial intelligence": "ai",
    "spring boot": "spring", "amazon web services": "aws",
}


def canonical(value: str) -> str:
    value = value.strip().lower()
    return SKILL_ALIASES.get(value, value)


def _value(row: dict[str, Any]) -> Any:
    value = row.get("value", row.get("value_json"))
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


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
    checks: list[dict[str, str]] = []

    degree_req = job.get("degree_requirements")
    degree = fact_map.get(("education", "degree", None))
    if degree_req:
        checks.append({"name": "Degree requirement", "result": "PASS" if degree and any(t in str(degree).lower() for t in ("computer", "software", "information")) else "UNKNOWN", "explanation": "Compared only with verified education."})
    country = job.get("country")
    work_text = job.get("work_authorization")
    if work_text or country:
        auth = fact_map.get(("work_authorization", "authorized", country))
        checks.append({"name": "Work authorization", "result": "PASS" if auth is True else "FAIL" if auth is False else "UNKNOWN", "explanation": f"Country-specific answer for {country or 'this location'} only."})
    checks.append({"name": "Required skills", "result": "PASS" if not missing else "PARTIAL", "explanation": f"{len(strong)} matched; {len(missing)} not present in verified profile."})
    definite_fail = any(c["result"] == "FAIL" for c in checks)
    unknown = any(c["result"] == "UNKNOWN" for c in checks)
    result = "INELIGIBLE" if definite_fail else "NEEDS_INFORMATION" if unknown else "ELIGIBLE" if not missing else "LIKELY_ELIGIBLE"
    coverage = round(100 * len(set(required) & skills) / len(set(required)), 0) if required else None
    return {"result": result, "checks": checks, "match": {"strong": strong, "partial": partial, "missing": missing, "required_coverage": coverage}}


def extract_skills(description: str) -> tuple[list[str], list[str]]:
    known = ["java", "python", "javascript", "typescript", "react", "node.js", "sql", "postgresql", "aws", "azure", "git", "docker", "kubernetes", "c++", "machine learning", "data structures", "rest api"]
    lowered = description.lower()
    found = [skill for skill in known if re.search(r"(?<![\w+])" + re.escape(skill) + r"(?!\w)", lowered)]
    preferred_markers = ("preferred", "nice to have", "bonus")
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", lowered)
    preferred = [s for s in found if any(s in sentence and any(marker in sentence for marker in preferred_markers) for sentence in sentences)]
    required = [s for s in found if s not in preferred]
    return required, preferred
