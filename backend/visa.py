"""Do you need a visa to work there? Your own answer for a country always wins; otherwise the answer is worked
out from your citizenship, permanent residency, and free-movement agreements between countries."""
from __future__ import annotations

from typing import Any

from .countries import country_key, country_name, same_country
from .student import profile as student_profile, value

EU_EEA = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "LI", "NO", "CH"}
# Citizens of any country in a group can work in every other country of that group without a visa.
FREE_MOVEMENT = [
    (EU_EEA, "EU/EEA free movement"),
    ({"GB", "IE"}, "the UK–Ireland Common Travel Area"),
    ({"AU", "NZ"}, "the Trans-Tasman Travel Arrangement"),
    ({"IN", "NP"}, "the India–Nepal treaty"),
    ({"AE", "SA", "QA", "BH", "KW", "OM"}, "the GCC common market"),
]


def _answered(facts: list[dict[str, Any]], category: str, key: str, country: str) -> Any:
    for fact in facts:
        if fact.get("category") == category and fact.get("fact_key") == key and fact.get("status") == "VERIFIED" and same_country(fact.get("country_code"), country):
            return value(fact)
    return None


def work_rights(facts: list[dict[str, Any]], country: str | None, student: dict[str, Any] | None = None) -> dict[str, Any]:
    """{authorized, needs_visa, source, reason}. authorized/needs_visa are None when it can't be known."""
    code = country_key(country) if country else None
    place = country_name(country) or "this country"
    if not code:
        return {"authorized": None, "needs_visa": None, "source": None, "reason": "The job's country isn't known."}
    authorized = _answered(facts, "work_authorization", "authorized", code)
    needs = _answered(facts, "sponsorship", "requires_sponsorship", code)
    if authorized is not None or needs is not None:
        if needs is None and authorized is True:
            needs = False
        if authorized is None and needs is True:
            authorized = False
        reason = (f"You said you can work in {place}." if authorized else f"You said you'd need a visa to work in {place}." if needs else f"You said you can't work in {place} yet.")
        return {"authorized": authorized, "needs_visa": needs, "source": "YOUR_ANSWER", "reason": reason}

    student = student or student_profile(facts)
    if not student["citizenship_known"]:
        return {"authorized": None, "needs_visa": None, "source": None, "reason": f"Add your citizenship in Profile and ApplyPilot works out {place} for you."}
    citizen = student["citizenships"]
    names = ", ".join(country_name(c) or c for c in citizen) or "no country"
    if code in citizen:
        return {"authorized": True, "needs_visa": False, "source": "CITIZENSHIP", "reason": f"You're a citizen of {place}."}
    if code in student["permanent_residency"]:
        return {"authorized": True, "needs_visa": False, "source": "CITIZENSHIP", "reason": f"You're a permanent resident of {place}."}
    for group, name in FREE_MOVEMENT:
        if code in group and any(c in group for c in citizen):
            return {"authorized": True, "needs_visa": False, "source": "CITIZENSHIP", "reason": f"As a citizen of {names}, you can work in {place} under {name}."}
    permit = next((p for p in student["work_permits"] if same_country(p.get("country"), code)), None)
    if permit:
        kind = permit.get("kind") or "visa"
        return {"authorized": None, "needs_visa": None, "source": None, "reason": f"You hold a {kind} for {place}. Whether it covers this job depends on the visa, so answer this country in Profile."}
    return {"authorized": False, "needs_visa": True, "source": "CITIZENSHIP", "reason": f"You're a citizen of {names}, so you'd need a work visa for {place}."}


def summary(facts: list[dict[str, Any]], countries: list[str]) -> list[dict[str, Any]]:
    """One row per country for the Profile page: can you work there, and why."""
    student = student_profile(facts)
    return [{"country": c, "name": country_name(c), **work_rights(facts, c, student)} for c in countries]
