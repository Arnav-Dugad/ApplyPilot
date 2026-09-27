from __future__ import annotations

import json
import re
from typing import Any

from .countries import country_key, country_name
from .languages import detect as detect_languages, normalize as normalize_language
from .requirements import extract as extract_requirements
from .skills import canonical, find_skills, related_credit
from .student import overlaps, profile as student_profile
from .visa import work_rights

PREFERRED_MARKERS = ("preferred", "nice to have", "nice-to-have", "bonus", "a plus", "is a plus", "desirable", "ideally")
LEVEL_NAMES = {"BACHELOR": "Bachelor's", "MASTER": "Master's", "PHD": "PhD"}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Fields close enough to computer science that "a degree in X" still fits a CS student.
CS_FIELDS = re.compile(r"(?i)\b(computer|computing|software|informatics|information (systems|technology|science)|data|machine learning|artificial intelligence|\bai\b|math\w*|statistics|electrical|electronics|engineering|technical|stem|cyber\w*|physics|quantitative)\b")
FIELD_LIST = re.compile(r"(?i)\b(?:degree|major(?:ing)?|studying|pursuing|student)\b[^.;]{0,60}?\bin\s+([^.;()]{3,140})")


def _value(row: dict[str, Any]) -> Any:
    value = row.get("value", row.get("value_json"))
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _month_label(value: str | None) -> str:
    match = re.fullmatch(r"(\d{4})-(\d{2})", str(value or ""))
    return f"{MONTH_NAMES[int(match.group(2)) - 1]} {match.group(1)}" if match else str(value)


def _window_label(earliest: str | None, latest: str | None) -> str:
    if earliest and latest:
        if earliest[:4] == latest[:4] and earliest.endswith("-01") and latest.endswith("-12"):
            return f"in {earliest[:4]}"
        return f"between {_month_label(earliest)} and {_month_label(latest)}" if earliest != latest else f"in {_month_label(earliest)}"
    return f"by {_month_label(latest)}" if latest else f"from {_month_label(earliest)} on"


def requirements_of(job: dict[str, Any]) -> dict[str, Any]:
    stored = job.get("requirements")
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except json.JSONDecodeError:
            stored = None
    return stored if isinstance(stored, dict) else extract_requirements(job.get("role") or "", job.get("description") or "")


def evaluate(job: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    verified = [f for f in facts if f.get("status") == "VERIFIED"]
    me = student_profile(verified)
    req = requirements_of(job)
    checks: list[dict[str, Any]] = []

    def check(name: str, result: str, explanation: str, evidence: str | None = None) -> None:
        checks.append({"name": name, "result": result, "explanation": explanation, **({"evidence": evidence} if evidence else {})})

    exp = me["experience"]
    is_student = me["enrolled"] is True or exp["none"]

    # 1. Is this role meant for someone at your stage?
    level = req.get("seniority")
    if level == "INTERN":
        check("Level", "PASS", "An internship — made for students.")
    elif level in {"SENIOR", "MID"}:
        if exp["work_years"] >= (5 if level == "SENIOR" else 2):
            check("Level", "PASS", f"A {'senior' if level == 'SENIOR' else 'mid-level'} role, and you have {exp['work_years']:g} years of work experience.")
        elif is_student or exp["known"]:
            check("Level", "FAIL", f"A {'senior' if level == 'SENIOR' else 'mid-level'} job for people with years of full-time work experience, not an internship.")
        else:
            check("Level", "UNKNOWN", "A senior job. Add your experience in Profile so ApplyPilot can tell if it fits.")
    elif level == "NEW_GRAD" and me["enrolled"] and not req.get("graduation"):
        check("Level", "WARN", f"A full-time job for recent graduates. You graduate in {_month_label(me['graduation'])}, so check the start date.")

    # 2. Experience
    need = req.get("experience")
    if need and need.get("none_needed"):
        check("Experience", "PASS", "No previous experience needed.", need.get("evidence"))
    elif need and need.get("min_years"):
        years = need["min_years"]
        asked = f"{years:g}+ year{'s' if years != 1 else ''} of work experience"
        if not need.get("required"):
            check("Experience", "WARN", f"Would like {asked}, but it isn't a must.", need.get("evidence"))
        elif exp["work_years"] >= years:
            check("Experience", "PASS", f"Asks for {asked}; you have {exp['work_years']:g}.", need.get("evidence"))
        elif exp["known"] or is_student:
            have = "none yet" if exp["work_years"] == 0 else f"{exp['work_years']:g}"
            check("Experience", "FAIL", f"Asks for {asked}. You have {have}.", need.get("evidence"))
        else:
            check("Experience", "UNKNOWN", f"Asks for {asked}. Add your experience in Profile.", need.get("evidence"))
    prior = req.get("prior_internship")
    if prior and exp["known"] and exp["internship_count"] == 0:
        check("Past internship", "WARN", "Asks for a previous internship. Strong projects can still get you noticed.", prior.get("evidence"))

    # 3. Degree level and field
    degree = req.get("degree")
    if degree:
        accepted = degree["accepted"]
        names = " or ".join(LEVEL_NAMES[a] for a in accepted)
        if me["level"] in accepted:
            check("Degree", "PASS", f"Open to {names} students — that's you.", degree.get("evidence"))
        elif me["level"]:
            check("Degree", "FAIL", f"Only for {names} students. You're doing a {LEVEL_NAMES[me['level']]}.", degree.get("evidence"))
        else:
            check("Degree", "WARN", f"Open to {names} students. Add your degree level in Profile to check.", degree.get("evidence"))
        field = FIELD_LIST.search(degree.get("evidence") or "")
        major = str(me.get("major") or "")
        if field and major and CS_FIELDS.search(major) and not CS_FIELDS.search(field.group(1)) and not any(w in field.group(1).lower() for w in re.findall(r"[a-z]{4,}", major.lower())):
            check("Field of study", "WARN", f"Asks for a degree in {field.group(1).strip().rstrip(',')}. You study {major}.", degree.get("evidence"))

    # 4. Graduation window
    window = req.get("graduation")
    if window:
        wanted = _window_label(window.get("earliest"), window.get("latest"))
        mine = me.get("graduation")
        if not mine:
            check("Graduation date", "UNKNOWN", f"Wants people graduating {wanted}. Add your graduation date in Profile.", window.get("evidence"))
        else:
            fits = (not window.get("earliest") or mine >= window["earliest"]) and (not window.get("latest") or mine <= window["latest"])
            check("Graduation date", "PASS" if fits else "FAIL", f"Wants people graduating {wanted}. You graduate in {_month_label(mine)}.", window.get("evidence"))

    # 5. Year of study (timing is fuzzy, so a mismatch is a warning, never a rejection)
    year_req = req.get("year_of_study")
    if year_req and year_req.get("open_to_all"):
        check("Year of study", "PASS", "Open to students in any year.", year_req.get("evidence"))
    elif year_req and me["year_of_study"]:
        mine = me["year_of_study"]
        if year_req.get("kind") == "PENULTIMATE":
            fits, wanted = me["program_years"] is not None and mine == me["program_years"] - 1, "your second-to-last year"
        elif year_req.get("kind") == "FINAL":
            fits, wanted = me["program_years"] is not None and mine == me["program_years"], "your final year"
        elif year_req.get("kind") == "AT_LEAST":
            fits, wanted = mine >= min(year_req["years"]), f"at least year {min(year_req['years'])}"
        else:
            fits, wanted = mine in year_req["years"], "year " + " or ".join(str(y) for y in year_req["years"])
        check("Year of study", "PASS" if fits else "WARN", f"Wants students in {wanted}. You're in year {mine}.", year_req.get("evidence"))

    # 6. Must you be a current student?
    if req.get("enrollment"):
        if me["enrolled"] is True:
            check("Student status", "PASS", "Must be a current student — you are.", req["enrollment"].get("evidence"))
        elif me["enrolled"] is False:
            check("Student status", "FAIL", "Only for current students.", req["enrollment"].get("evidence"))
        else:
            check("Student status", "UNKNOWN", "Only for current students. Add your graduation date in Profile.", req["enrollment"].get("evidence"))

    # 7. GPA
    gpa = req.get("gpa")
    if gpa:
        asked = f"a GPA of at least {gpa['min']:g}/{gpa['scale']:g}"
        cgpa = me.get("cgpa")
        if not cgpa:
            check("GPA", "WARN", f"Asks for {asked}. Add your CGPA in Profile to check.", gpa.get("evidence"))
        else:
            converted = cgpa["value"] / cgpa["scale"] * gpa["scale"]
            same_scale = abs(cgpa["scale"] - gpa["scale"]) < 0.01
            yours = f"{cgpa['value']:g}/{cgpa['scale']:g}" + ("" if same_scale else f" (about {converted:.1f}/{gpa['scale']:g})")
            if converted + 1e-9 >= gpa["min"]:
                check("GPA", "PASS", f"Asks for {asked}. Yours is {yours}.", gpa.get("evidence"))
            elif same_scale and gpa.get("required"):
                check("GPA", "FAIL", f"Asks for {asked}. Yours is {yours}.", gpa.get("evidence"))
            else:
                check("GPA", "WARN", f"Asks for {asked}. Yours is {yours} — grade conversions vary, so check with the company.", gpa.get("evidence"))

    # 8. Citizenship or security clearance
    country = job.get("country")
    code = country_key(country) if country else None
    citizenship = req.get("citizenship")
    if citizenship:
        needed = citizenship.get("countries") or ([code] if code else [])
        names = " or ".join(country_name(c) or c for c in needed) or "the job's country"
        what = "a security clearance, which needs citizenship of " + names if citizenship.get("clearance") else f"citizens of {names}"
        if not me["citizenship_known"]:
            check("Citizenship", "UNKNOWN", f"Only open to {what}. Add your citizenship in Profile.", citizenship.get("evidence"))
        elif any(c in me["citizenships"] for c in needed) or (citizenship.get("permanent_residents_ok") and any(c in me["permanent_residency"] for c in needed)):
            check("Citizenship", "WARN" if citizenship.get("clearance") else "PASS", "Needs a security clearance — you're eligible to apply for one." if citizenship.get("clearance") else f"Only open to {what} — you are one.", citizenship.get("evidence"))
        else:
            check("Citizenship", "FAIL", f"Only open to {what}.", citizenship.get("evidence"))

    # 9. Right to work, and whether they sponsor visas
    sponsorship = req.get("sponsorship")
    sponsorship_text = job.get("sponsorship_information")
    if not sponsorship and sponsorship_text:  # jobs added by hand may only have the sponsorship sentence
        sponsorship = extract_requirements("", sponsorship_text).get("sponsorship")
    if code or job.get("work_authorization") or sponsorship_text:
        rights = work_rights(verified, country, me)
        place = country_name(country) or "this location"
        if rights["authorized"] is True or rights["needs_visa"] is False:
            check("Right to work", "PASS", rights["reason"])
        elif rights["needs_visa"] is None:
            check("Right to work", "UNKNOWN", rights["reason"] if code else "The job's country isn't clear, so ApplyPilot can't tell if you'd need a visa.")
        else:
            if sponsorship and sponsorship.get("offered") is False:
                check("Visa", "FAIL", f"You'd need a visa for {place}, and this job doesn't sponsor visas.", sponsorship.get("evidence"))
            elif sponsorship and sponsorship.get("offered"):
                check("Visa", "VISA", f"You'd need a visa for {place} — and they sponsor visas.", sponsorship.get("evidence"))
            else:
                check("Visa", "VISA", f"You'd need a visa for {place}. The posting doesn't say whether they sponsor.")

    # 10. Languages
    wanted_languages = [normalize_language(n) for n in detect_languages(job.get("description") or "")["required"]]
    if wanted_languages:
        spoken_fact = next((f for f in verified if f["category"] == "languages" and f["fact_key"] == "spoken"), None)
        spoken = {normalize_language(str(x)) for x in (_value(spoken_fact) or [])} if spoken_fact else None
        if spoken is None:
            check("Languages", "UNKNOWN", f"Requires {', '.join(wanted_languages)}. Add the languages you speak in Profile.")
        elif all(w in spoken for w in wanted_languages):
            check("Languages", "PASS", f"You speak {', '.join(wanted_languages)}.")
        elif len(wanted_languages) == 1:
            check("Languages", "FAIL", f"Requires {wanted_languages[0]}, which isn't in your languages.")
        else:
            check("Languages", "UNKNOWN", f"Mentions {', '.join(wanted_languages)} — check whether all or any one is required.")

    # 11. Dates you're free
    term = req.get("term")
    if term and me["availability"]:
        free = [w for w in term["windows"] if overlaps(w, me["availability"])]
        labels = ", ".join(w["label"] for w in term["windows"])
        check("Dates", "PASS" if free else "WARN", f"Runs {labels} — {'fits the time you said you are free' if free else 'outside the times you said you are free'}.")

    # 12. Skills
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
    listed = set(required + preferred)
    if not listed:
        check("Skills", "PASS", "The posting doesn't list specific skills.")
    else:
        check("Skills", "PASS" if not missing else "PARTIAL", f"You have {len(strong)} of the {len(listed)} skills it lists" + (f"; missing {', '.join(missing[:4])}." if missing else "."))

    results = {c["result"] for c in checks}
    if "FAIL" in results:
        result = "INELIGIBLE"
    elif "UNKNOWN" in results:
        result = "NEEDS_INFORMATION"
    elif "VISA" in results:
        result = "VISA_NEEDED"
    elif missing or "WARN" in results:
        result = "LIKELY_ELIGIBLE"
    else:
        result = "ELIGIBLE"
    coverage = round(100 * len(set(required) & skills) / len(set(required)), 0) if required else None
    # Related skills (e.g. MySQL for PostgreSQL) earn half credit in ranking only, never in eligibility.
    weighted = round(100 * (len(set(required) & skills) + 0.5 * len(related)) / len(set(required)), 0) if required else None
    sponsors = bool(sponsorship and sponsorship.get("offered"))
    return {"result": result, "checks": checks, "sponsors": sponsors,
            "match": {"strong": strong, "partial": partial, "missing": missing, "related": related, "required_coverage": coverage, "weighted_coverage": weighted}}


def extract_skills(description: str) -> tuple[list[str], list[str]]:
    """Required vs preferred skills, decided by the sentence each skill appears in."""
    found = find_skills(description)
    sentences = [x for x in re.split(r"(?<=[.!?;])\s+|\n+", description) if x.strip()]
    # Each sentence is read once: (its skills, whether it says "preferred"/"a plus").
    read = [(set(find_skills(sentence)), any(m in sentence.lower() for m in PREFERRED_MARKERS)) for sentence in sentences]
    preferred = [s for s in found if all(nice for skills, nice in read if s in skills)]
    required = [s for s in found if s not in preferred]
    return required, preferred
