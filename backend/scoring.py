"""Transparent 0-100 match score. Every point is attributed to a named factor the user can inspect."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .countries import country_key

INTERNSHIP_TITLE = re.compile(r"(?i)\b(intern|interns|internship|internships|co-?op|placement|trainee|working student|apprentice(ship)?|summer (analyst|associate|engineer))\b")
EUROPE = {"AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT", "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK"}
GCC = {"AE", "SA", "QA", "BH", "KW", "OM"}
REGIONS = {"europe": EUROPE, "eu": EUROPE, "gcc": GCC, "middle east": GCC | {"JO", "LB", "EG"}}
CITY_COUNTRY = {
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "cambridge uk": "GB", "dublin": "IE", "paris": "FR", "berlin": "DE", "munich": "DE",
    "amsterdam": "NL", "zurich": "CH", "stockholm": "SE", "madrid": "ES", "barcelona": "ES", "warsaw": "PL", "lisbon": "PT", "milan": "IT",
    "dubai": "AE", "abu dhabi": "AE", "riyadh": "SA", "jeddah": "SA", "doha": "QA", "manama": "BH", "kuwait city": "KW", "muscat": "OM",
    "singapore": "SG", "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN", "delhi": "IN", "new delhi": "IN", "gurgaon": "IN", "gurugram": "IN",
    "hyderabad": "IN", "pune": "IN", "chennai": "IN", "noida": "IN", "kolkata": "IN", "tokyo": "JP", "sydney": "AU", "melbourne": "AU", "toronto": "CA",
    "vancouver": "CA", "new york": "US", "san francisco": "US", "seattle": "US", "boston": "US", "austin": "US", "chicago": "US", "los angeles": "US",
}


def job_country(job: dict[str, Any]) -> str | None:
    """Best deterministic country for a job: explicit country field, then a known city or country in the location text."""
    if job.get("country"):
        return country_key(job["country"])
    location = str(job.get("location") or "").lower()
    for city, code in CITY_COUNTRY.items():
        if re.search(rf"\b{re.escape(city)}\b", location):
            return code
    for part in reversed([p.strip() for p in re.split(r"[,/;|-]", location) if p.strip()]):
        key = country_key(part)
        if key and len(key) == 2 and key.isupper():
            return key
    return None


def location_match(job: dict[str, Any], preferred: list[str]) -> tuple[bool | None, str]:
    """True/False when decidable, None when the job location is unknown."""
    if not preferred:
        return None, "No preferred locations set"
    wanted = {p.strip().lower() for p in preferred}
    remote = "remote" in str(job.get("location") or "").lower() or job.get("remote_status") == "REMOTE"
    if remote and ("remote" in wanted or "anywhere" in wanted):
        return True, "Remote role"
    code = job_country(job)
    if code is None:
        return None, "Location not stated"
    for pref in wanted:
        if pref in REGIONS and code in REGIONS[pref]:
            return True, f"In your {pref.title()} preference"
        if country_key(pref) == code:
            return True, f"{pref.title()} is a preferred location"
    return False, f"{job.get('location') or code} is outside your preferred locations"


def _days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds() / 86400


def score(job: dict[str, Any], analysis: dict[str, Any], preferred_locations: list[str]) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []

    def add(name: str, points: float, maximum: int, detail: str) -> None:
        factors.append({"name": name, "points": round(max(0.0, min(points, maximum)), 1), "max": maximum, "detail": detail})

    match = analysis.get("match", {})
    required = len(set(job.get("required_skills") or []))
    if required:
        weighted = match.get("weighted_coverage") or 0
        add("Required skills", 40 * weighted / 100, 40, f"{len(match.get('strong', []))} verified, {len(match.get('related', []))} related, {len(match.get('missing', []))} missing")
    else:
        add("Required skills", 20, 40, "No specific skills listed")
    preferred = len(set(job.get("preferred_skills") or []))
    if preferred:
        have = preferred - len(match.get("partial", []))
        add("Preferred skills", 10 * have / preferred, 10, f"{have} of {preferred} nice-to-haves")
    else:
        add("Preferred skills", 5, 10, "None listed")

    fits, why = location_match(job, preferred_locations)
    add("Location", 15 if fits else 7 if fits is None else 0, 15, why)

    title = str(job.get("role") or "")
    is_intern = bool(INTERNSHIP_TITLE.search(title)) or "intern" in str(job.get("employment_type") or "").lower()
    add("Internship", 15 if is_intern else 0, 15, "Internship role" if is_intern else "Not labelled as an internship")

    age = _days_since(job.get("date_posted"))
    if age is None:
        add("Freshness", 5, 10, "Posting date unknown")
    else:
        add("Freshness", 10 if age <= 7 else 10 * max(0.0, 1 - (age - 7) / 53), 10, f"Posted {int(age)} day{'s' if int(age) != 1 else ''} ago")

    deadline = _days_since(job.get("deadline"))
    if deadline is None:
        add("Deadline", 5, 5, "No deadline listed")
    elif deadline > 0:
        add("Deadline", 0, 5, "Deadline has passed")
    else:
        add("Deadline", 5, 5, f"Closes in {int(-deadline)} days")

    total = sum(f["points"] for f in factors)
    result = analysis.get("result")
    if result == "INELIGIBLE":
        total, cap = min(total, 15), "Capped: a definite eligibility check failed"
    elif result == "NEEDS_INFORMATION":
        total, cap = total * 0.85, "Reduced 15% until missing facts are verified"
    else:
        cap = None
    value = int(round(total))
    grade = "A+" if value >= 90 else "A" if value >= 80 else "B" if value >= 65 else "C" if value >= 50 else "D"
    return {"score": value, "grade": grade, "factors": factors, "adjustment": cap, "location_ok": fits, "is_internship": is_intern}


def preferred_locations(facts: list[dict[str, Any]]) -> list[str]:
    for fact in facts:
        if fact.get("category") == "preferences" and fact.get("fact_key") == "locations" and fact.get("status") == "VERIFIED":
            value = fact.get("value", fact.get("value_json"))
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = [value]
            return [str(v) for v in value or []]
    return []
