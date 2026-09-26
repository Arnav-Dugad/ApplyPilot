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
    ("CREDENTIAL", (r"password", r"passcode", r"access code", r"pin code", r"security question")),
    ("EMAIL", (r"e ?mail",)),
    ("RESUME", (r"\bresume\b", r"\bcv\b", r"curriculum vitae")),
    ("COVER_LETTER", (r"cover letter",)),
    ("PHONE", (r"phone", r"mobile")),
    ("FIRST_NAME", (r"first name", r"given name", r"forename", r"preferred first")),
    ("LAST_NAME", (r"last name", r"surname", r"family name")),
    ("NAME", (r"full name", r"legal name", r"^name$", r"^your name$")),
    ("LINKEDIN", (r"linkedin",)),
    ("GITHUB", (r"github",)),
    ("WEBSITE", (r"website", r"portfolio", r"personal site")),
    ("WORK_AUTHORIZATION", (r"authori[sz]ed to work", r"right to work", r"work permit", r"eligible to work", r"legally (able|permitted) to work")),
    ("SPONSORSHIP", (r"sponsor", r"immigration support", r"visa support")),
    ("RELOCATION", (r"relocat",)),
    ("SALARY", (r"salary", r"compensation", r"pay expectation")),
    ("DEMOGRAPHIC", (r"gender", r"ethnicity", r"\brace\b", r"disability", r"veteran", r"sexual orientation", r"pronoun", r"hispanic")),
    ("LEGAL", (r"criminal", r"declaration", r"conflict of interest", r"restrictive covenant", r"background check", r"non compete", r"i certify", r"i agree", r"consent")),
    ("GRADUATION_DATE", (r"graduat", r"completion date")),
    ("EDUCATION", (r"university", r"college", r"school", r"degree", r"education")),
    ("ADDRESS", (r"address", r"postal", r"zip code", r"post code")),
    ("LOCATION", (r"current location", r"where are you (currently )?(based|located)", r"^location( |$)", r"^city( |$)", r"city of residence")),
    ("CUSTOM", (r"why (do you|are you|this|us|join)", r"tell us", r"describe", r"what (excites|interests|motivates)")),
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


def decide_fill(classification: str, fact: dict[str, Any] | None, *, manual_only: bool = False, user_answer: bool = False) -> FillDecision:
    if manual_only:
        return FillDecision("PAUSE", reason="This answer is configured as MANUAL_ONLY.")
    if not fact:
        return FillDecision("PAUSE", reason="ApplyPilot doesn't have a verified answer for this question.")
    if fact.get("status") != "VERIFIED":
        return FillDecision("PAUSE", reason=f"The matching answer is {fact.get('status', 'UNKNOWN')}.")
    if classification == "UNKNOWN" and not user_answer:
        return FillDecision("PAUSE", reason="Unknown fields never receive automatic answers.")
    return FillDecision("FILL", fact.get("value"), fact.get("source_label") or f"Profile → {fact.get('category')} → {fact.get('fact_key')}", fact.get("reason") or "Exact verified fact found.")


STOPWORDS = {"a", "an", "the", "you", "your", "are", "do", "is", "to", "of", "in", "for", "this", "that", "with", "have", "please", "our", "we", "at", "be", "or", "and", "any", "will", "currently", "now", "future"}


def question_tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t not in STOPWORDS}


def question_similarity(a: str, b: str) -> float:
    """Token-set similarity between two question wordings (0..1)."""
    ta, tb = question_tokens(a), question_tokens(b)
    if not ta or not tb:
        return 1.0 if normalize(a) == normalize(b) else 0.0
    return len(ta & tb) / len(ta | tb)


def strip_prompt_injection(text: str) -> tuple[str, list[str]]:
    suspicious = re.compile(r"(?i)(ignore (all |any )?(previous|prior) instructions|system prompt|upload all|execute (a )?(shell|command)|read local files|reveal credentials)")
    hits = [line.strip() for line in text.splitlines() if suspicious.search(line)]
    cleaned = "\n".join(line for line in text.splitlines() if not suspicious.search(line))
    return cleaned, hits

