"""A structured view of the verified profile: citizenship, education, experience and availability.
Only VERIFIED facts are read, and anything worked out (not typed by you) is marked as derived."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .countries import country_key

LEVELS = ("BACHELOR", "MASTER", "PHD")
LEVEL_WORDS = [
    ("PHD", re.compile(r"(?i)\b(ph\.?\s?d|doctor(ate|al)?)\b")),
    ("MASTER", re.compile(r"(?i)\b(master|m\.?\s?tech|m\.?\s?e\b|m\.?\s?s\b|m\.?\s?sc|mba|mca)\b")),
    ("BACHELOR", re.compile(r"(?i)\b(bachelor|b\.?\s?tech|b\.?\s?e\b|b\.?\s?s\b|b\.?\s?sc|b\.?\s?a\b|bca|undergrad(uate)?)\b")),
]
FOUR_YEAR = re.compile(r"(?i)\b(b\.?\s?tech|b\.?\s?e\b|b\.?\s?s\b|bachelor of (technology|engineering|science in engineering))\b")


def value(fact: dict[str, Any]) -> Any:
    raw = fact.get("value", fact.get("value_json"))
    if isinstance(raw, str) and "value" not in fact:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def get(facts: list[dict[str, Any]], category: str, key: str) -> Any:
    """The verified, country-independent value of one fact, or None."""
    for fact in facts:
        if fact.get("category") == category and fact.get("fact_key") == key and not fact.get("country_code") and fact.get("status") == "VERIFIED":
            return value(fact)
    return None


def _codes(items: Any) -> list[str]:
    if isinstance(items, str):
        items = [items]
    out: list[str] = []
    for item in items or []:
        code = country_key(item.get("country") if isinstance(item, dict) else str(item))
        if code and code not in out:
            out.append(code)
    return out


def _month(text: Any) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", str(text or "").strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def _months_between(start: Any, end: Any, today: datetime) -> int:
    a = _month(start)
    ongoing = not end or str(end).lower() in {"present", "now", "current"}
    b = (today.year, today.month) if ongoing else _month(end)
    if not a or not b:
        return 0
    return max(0, (b[0] - a[0]) * 12 + b[1] - a[1] + 1)


def level_of(text: str | None) -> str | None:
    for level, pattern in LEVEL_WORDS:
        if text and pattern.search(text):
            return level
    return None


def profile(facts: list[dict[str, Any]], today: datetime | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc)
    out: dict[str, Any] = {"derived": []}

    out["citizenships"] = _codes(get(facts, "citizenship", "countries"))
    out["permanent_residency"] = _codes(get(facts, "citizenship", "permanent_residency"))
    permits = get(facts, "citizenship", "work_permits")
    out["work_permits"] = [p for p in permits if isinstance(p, dict) and p.get("country")] if isinstance(permits, list) else []
    out["citizenship_known"] = get(facts, "citizenship", "countries") is not None

    degree_name = get(facts, "education", "degree_name")
    level = get(facts, "education", "level")
    if level not in LEVELS:
        level = level_of(degree_name) or level_of(get(facts, "education", "degree"))
        if level:
            out["derived"].append("level")
    out["level"] = level
    out["degree_name"] = degree_name
    out["major"] = get(facts, "education", "degree")
    out["graduation"] = get(facts, "education", "graduation_date")

    program_years = get(facts, "education", "program_years")
    if not isinstance(program_years, (int, float)) and degree_name and FOUR_YEAR.search(str(degree_name)):
        program_years = 4
    out["program_years"] = int(program_years) if isinstance(program_years, (int, float)) else None

    year = get(facts, "education", "year_of_study")
    grad = _month(out["graduation"])
    if not isinstance(year, (int, float)) and grad and out["program_years"]:
        # Academic years start around July: May 2028 graduation, Sept 2026 today, 4-year program -> 3rd year.
        grad_year_start = grad[0] - 1 if grad[1] <= 7 else grad[0]
        current_start = today.year if today.month >= 7 else today.year - 1
        remaining = grad_year_start - current_start
        if 0 <= remaining < out["program_years"]:
            year = out["program_years"] - remaining
            out["derived"].append("year_of_study")
    out["year_of_study"] = int(year) if isinstance(year, (int, float)) else None
    out["semester"] = get(facts, "education", "semester")

    enrolled = get(facts, "education", "enrolled")
    if not isinstance(enrolled, bool) and grad:
        enrolled = (grad[0], grad[1]) >= (today.year, today.month)
        out["derived"].append("enrolled")
    out["enrolled"] = enrolled if isinstance(enrolled, bool) else None

    cgpa = get(facts, "education", "cgpa")
    if isinstance(cgpa, dict) and isinstance(cgpa.get("value"), (int, float)) and isinstance(cgpa.get("scale"), (int, float)) and 0 < cgpa["value"] <= cgpa["scale"]:
        out["cgpa"] = {"value": float(cgpa["value"]), "scale": float(cgpa["scale"])}
    else:
        out["cgpa"] = None

    entries = get(facts, "experience", "entries")
    entries = [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
    none_yet = get(facts, "experience", "none") is True
    work_months = sum(_months_between(e.get("start"), e.get("end"), today) for e in entries if str(e.get("kind", "JOB")).upper() in {"JOB", "FULL_TIME", "PART_TIME"})
    intern_months = sum(_months_between(e.get("start"), e.get("end"), today) for e in entries if str(e.get("kind", "")).upper() in {"INTERNSHIP", "CO_OP"})
    out["experience"] = {
        "known": bool(entries) or none_yet,
        "entries": entries,
        "work_years": round(work_months / 12, 1),
        "internship_count": sum(1 for e in entries if str(e.get("kind", "")).upper() in {"INTERNSHIP", "CO_OP"}),
        "internship_months": intern_months,
        "none": none_yet and not entries,
    }
    availability = get(facts, "preferences", "availability")
    out["availability"] = [w for w in availability if isinstance(w, dict) and _month(w.get("start")) and _month(w.get("end"))] if isinstance(availability, list) else []
    out["roles"] = get(facts, "preferences", "roles") or []
    return out


def years_between(start: str, end: str) -> float:
    a, b = _month(start), _month(end)
    return ((b[0] - a[0]) * 12 + b[1] - a[1]) / 12 if a and b else 0.0


def overlaps(window: dict[str, str], availability: list[dict[str, str]]) -> bool:
    start, end = _month(window["start"]), _month(window["end"])
    return any(start <= _month(w["end"]) and _month(w["start"]) <= end for w in availability)
