"""Transparent 0-100 match score. Every point is attributed to a named factor the user can inspect."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .countries import COUNTRY_NAMES, country_key

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
    "sf": "US", "nyc": "US", "bay area": "US", "silicon valley": "US", "montreal": "CA", "ottawa": "CA", "waterloo": "CA", "hong kong": "HK",
    "tel aviv": "IL", "seoul": "KR", "shanghai": "CN", "beijing": "CN", "taipei": "TW", "auckland": "NZ", "cape town": "ZA", "sao paulo": "BR",
    "mexico city": "MX", "kuala lumpur": "MY", "jakarta": "ID", "manila": "PH", "bangkok": "TH", "ho chi minh": "VN", "hanoi": "VN", "istanbul": "TR",
    "cairo": "EG", "lagos": "NG", "nairobi": "KE", "karachi": "PK", "lahore": "PK", "dhaka": "BD", "colombo": "LK", "kathmandu": "NP",
    "ahmedabad": "IN", "jaipur": "IN", "kochi": "IN", "trivandrum": "IN", "thiruvananthapuram": "IN", "coimbatore": "IN", "chandigarh": "IN", "indore": "IN",
    "bhubaneswar": "IN", "mangalore": "IN", "mangaluru": "IN", "manipal": "IN", "mysore": "IN", "mysuru": "IN", "vadodara": "IN", "nagpur": "IN", "lucknow": "IN",
    "hamburg": "DE", "frankfurt": "DE", "stuttgart": "DE", "cologne": "DE", "dusseldorf": "DE", "vienna": "AT", "brussels": "BE", "copenhagen": "DK",
    "oslo": "NO", "helsinki": "FI", "prague": "CZ", "budapest": "HU", "bucharest": "RO", "athens": "GR", "rotterdam": "NL", "eindhoven": "NL",
    "geneva": "CH", "lausanne": "CH", "rome": "IT", "turin": "IT", "valencia": "ES", "porto": "PT", "krakow": "PL", "wroclaw": "PL", "tallinn": "EE",
    "vilnius": "LT", "riga": "LV", "luxembourg": "LU", "cork": "IE", "galway": "IE", "belfast": "GB", "glasgow": "GB", "bristol": "GB", "oxford": "GB",
}
US_STATES = "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
# "Pittsburgh, PA" is Pennsylvania, not Panama; "Indianapolis, IN" is Indiana, not India.
US_STATE_TAIL = re.compile(rf",\s*({US_STATES})\s*(?:\d{{5}})?\s*$")
US_WORDS = re.compile(r"\b(USA|U\.S\.A?\.?|United States|US)\b")
CA_PROVINCE = re.compile(r",\s*(ON|BC|QC|AB|MB|NS|NB|NL|PE|SK)\s*$")


def job_country(job: dict[str, Any]) -> str | None:
    """Best deterministic country for a job: explicit country field, then a known city or country in the location text."""
    if job.get("country"):
        return country_key(job["country"])
    raw = str(job.get("location") or "").strip()
    location = raw.lower()
    for city, code in CITY_COUNTRY.items():
        if re.search(rf"\b{re.escape(city)}\b", location):
            return code
    first = re.split(r"[;|]", raw)[0].strip()
    if US_STATE_TAIL.search(first) or US_WORDS.search(raw):
        return "US"
    if CA_PROVINCE.search(first):
        return "CA"
    for part in reversed([p.strip() for p in re.split(r"[,/;|-]", location) if p.strip()]):
        if len(part) <= 2 and part != "uk":
            continue  # bare two-letter tokens are usually states or provinces, not countries
        key = country_key(part)
        if key and len(key) == 2 and key.isupper():
            return key
    # "Remote in Canada", "Anywhere in Germany": a full country name anywhere in the text.
    for code, names in COUNTRY_NAMES.items():
        if any(len(name) > 3 and re.search(rf"\b{re.escape(name)}\b", location) for name in names):
            return code
    return None


def location_match(job: dict[str, Any], preferred: list[str]) -> tuple[bool | None, str]:
    """True/False when decidable, None when the job location is unknown."""
    if not preferred:
        return None, "No preferred locations set"
    wanted = {p.strip().lower() for p in preferred}
    spelled = {p.strip().lower(): p.strip() for p in preferred}  # "US" stays "US" in explanations
    remote = "remote" in str(job.get("location") or "").lower() or job.get("remote_status") == "REMOTE"
    if remote and ("remote" in wanted or "anywhere" in wanted):
        return True, "Remote role"
    code = job_country(job)
    if code is None:
        return None, "Location not stated"
    for pref in wanted:
        if pref in REGIONS and code in REGIONS[pref]:
            return True, f"In your {spelled[pref]} preference"
        if country_key(pref) == code:
            return True, f"{spelled[pref]} is one of your places"
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


def score(job: dict[str, Any], analysis: dict[str, Any], preferred_locations: list[str], taste: tuple[float, list[str]] | None = None) -> dict[str, Any]:
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
    if taste and taste[0]:
        # Learned from 👍/👎: can add or remove up to 5 points, shown as its own factor.
        factors.append({"name": "Your taste", "points": taste[0], "max": 5, "detail": "; ".join(taste[1]) or "Learned from your 👍/👎"})
        total += taste[0]
    total = max(0.0, min(100.0, total))
    result = analysis.get("result")
    if result == "INELIGIBLE":
        total, cap = min(total, 15), "Capped: something in the posting rules you out"
    elif result == "NEEDS_INFORMATION":
        total, cap = total * 0.85, "Lowered 15% until you answer the missing questions"
    elif result == "VISA_NEEDED":
        # A visa is a real hurdle; a company that says it sponsors is a much better bet.
        total, cap = (total * 0.9, "Lowered 10%: you'd need a visa, but they sponsor") if analysis.get("sponsors") else (total * 0.75, "Lowered 25%: you'd need a visa")
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
