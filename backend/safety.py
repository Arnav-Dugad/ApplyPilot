from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SENSITIVE_TYPES = {
    "WORK_AUTHORIZATION", "SPONSORSHIP", "LEGAL", "DEMOGRAPHIC", "SALARY",
    "RELOCATION", "AVAILABILITY", "GRADUATION_DATE", "ADDRESS", "PHONE",
    "CITIZENSHIP", "NATIONALITY", "DATE_OF_BIRTH", "GENDER", "DISABILITY",
    "VETERAN", "ETHNICITY", "CRIMINAL_HISTORY", "BACKGROUND_CHECK",
}

PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("EMAIL", (r"e-?mail",)),
    ("PHONE", (r"phone", r"mobile")),
    ("NAME", (r"first name", r"last name", r"full name", r"legal name")),
    ("WORK_AUTHORIZATION", (r"authori[sz]ed to work", r"right to work", r"work permit")),
    ("SPONSORSHIP", (r"sponsor", r"immigration support", r"visa support")),
    ("RELOCATION", (r"relocat",)),
    ("SALARY", (r"salary", r"compensation", r"pay expectation")),
    ("GRADUATION_DATE", (r"graduat", r"completion date")),
    ("EDUCATION", (r"university", r"college", r"degree", r"education")),
    ("DEMOGRAPHIC", (r"gender", r"ethnicity", r"race", r"disability", r"veteran")),
    ("LEGAL", (r"criminal", r"declaration", r"conflict of interest", r"restrictive covenant", r"background check")),
    ("ADDRESS", (r"address", r"postal", r"zip code")),
    ("CUSTOM", (r"why (?:do you|are you|this)", r"tell us", r"describe")),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def classify_field(label: str, name: str = "", field_type: str = "") -> str:
    haystack = normalize(f"{label} {name} {field_type}")
    for classification, patterns in PATTERNS:
        if any(re.search(pattern, haystack) for pattern in patterns):
            return classification
    return "UNKNOWN"


@dataclass(frozen=True)
class FillDecision:
    action: str
    value: Any = None
    source: str | None = None
    reason: str = ""


def decide_fill(classification: str, fact: dict[str, Any] | None, *, manual_only: bool = False) -> FillDecision:
    if manual_only:
        return FillDecision("PAUSE", reason="This answer is configured as MANUAL_ONLY.")
    if not fact:
        return FillDecision("PAUSE", reason="ApplyPilot doesn't have a verified answer for this question.")
    if fact.get("status") != "VERIFIED":
        return FillDecision("PAUSE", reason=f"The matching answer is {fact.get('status', 'UNKNOWN')}.")
    if classification == "UNKNOWN":
        return FillDecision("PAUSE", reason="Unknown fields never receive automatic answers.")
    return FillDecision("FILL", fact.get("value"), f"Profile → {fact.get('category')} → {fact.get('fact_key')}", "Exact verified fact found.")


def strip_prompt_injection(text: str) -> tuple[str, list[str]]:
    suspicious = re.compile(r"(?i)(ignore (all |any )?(previous|prior) instructions|system prompt|upload all|execute (a )?(shell|command)|read local files|reveal credentials)")
    hits = [line.strip() for line in text.splitlines() if suspicious.search(line)]
    cleaned = "\n".join(line for line in text.splitlines() if not suspicious.search(line))
    return cleaned, hits

