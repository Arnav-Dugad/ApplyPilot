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
    # Order matters: the first match wins, so narrow and "never autofill" classes come first.
    ("CREDENTIAL", (r"password", r"passcode", r"access code", r"pin code", r"security question")),
    ("RESUME", (r"\bresume\b", r"\bcv\b", r"curriculum vitae")),
    ("COVER_LETTER", (r"cover letter",)),
    ("DOCUMENT", (r"transcript", r"\bupload\b", r"\battach", r"academic record", r"writing sample", r"work sample", r"certificate", r"\bdiploma\b")),
    ("THIRD_PARTY", (r"advisor", r"adviser", r"\breference", r"\breferee", r"supervisor", r"manager s", r"hiring manager", r"emergency", r"\bparent", r"guardian", r"professor", r"alternate", r"secondary", r"\breferr")),
    ("GPA", (r"\bgpa\b", r"grade point", r"\bcgpa\b", r"class rank")),
    ("EMAIL", (r"e ?mail",)),
    ("PHONE", (r"phone", r"mobile")),
    ("FIRST_NAME", (r"first name", r"given name", r"forename", r"preferred first")),
    ("LAST_NAME", (r"last name", r"surname", r"family name")),
    ("NAME", (r"^full name", r"full legal name", r"^legal name", r"^name$", r"^your name$", r"^your full name")),
    ("LINKEDIN", (r"linkedin",)),
    ("GITHUB", (r"github",)),
    ("WEBSITE", (r"website", r"portfolio", r"personal site")),
    ("WORK_AUTHORIZATION", (r"authori[sz]ed to work", r"right to work", r"work permit", r"eligible to work", r"legally (able|permitted) to work")),
    # Visa sponsorship only: "sponsored conferences" is not about your visa.
    ("SPONSORSHIP", (r"\bsponsorship\b", r"\bsponsor (you|me|your|a|an|visa|work|employment)", r"visa sponsor", r"immigration support", r"visa support")),
    ("RELOCATION_ASSISTANCE", (r"relocation (assistance|package|support|benefit|stipend|reimbursement)", r"(assistance|help|support) (with|to|for) relocat", r"require relocation")),
    ("RELOCATION", (r"relocat",)),
    ("SALARY", (r"salary", r"compensation", r"pay expectation")),
    ("DEMOGRAPHIC", (r"gender", r"ethnicity", r"\brace\b", r"disability", r"veteran", r"sexual orientation", r"pronoun", r"hispanic")),
    ("LEGAL", (r"criminal", r"declaration", r"conflict of interest", r"restrictive covenant", r"background check", r"non compete", r"i certify", r"i agree", r"consent")),
    ("CUSTOM", (r"why (do you|are you|this|us|join|should)", r"tell us", r"\bdescribe\b", r"share with us", r"what (excites|interests|motivates)", r"what best describes", r"\bexplain\b")),
    ("GRADUATION_DATE", (r"graduat", r"completion date")),
    ("EDUCATION", (r"university", r"college", r"school", r"degree", r"education", r"institution")),
    ("POSTAL_CODE", (r"postal", r"zip", r"post code", r"postcode", r"pin ?code")),
    ("ADDRESS", (r"address",)),
    ("LOCATION", (r"current location", r"where are you (currently )?(based|located)", r"^location( city)?$", r"^city$", r"city of residence")),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


# Facts that hold text (a university, a phone number). A yes/no question can never be answered with one.
TEXT_FACTS = {"NAME", "FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE", "ADDRESS", "POSTAL_CODE", "LOCATION", "LINKEDIN", "GITHUB", "WEBSITE", "EDUCATION", "GRADUATION_DATE", "SALARY"}
YES_NO_START = re.compile(r"^(are|is|do|does|did|have|has|had|will|would|can|could|were|was|should|may) (you|your|the|this|there)\b")
YES_NO_OPTIONS = {"yes", "no", "n a", "na", "not applicable", "prefer not to say", "i don t know", "unsure", "maybe"}


def is_yes_no_question(label: str, options: list[str] | None = None) -> bool:
    text = normalize(label)
    if options and len(options) <= 4 and all(normalize(o) in YES_NO_OPTIONS or normalize(o).startswith(("yes ", "no ")) for o in options):
        return True
    return bool(YES_NO_START.match(text))


# A long sentence only counts as a profile field when it explicitly asks for "your <field>".
ASKS_FOR = re.compile(r"\byour (expected |anticipated |current |full |legal |primary |personal )?(graduation|university|school|college|degree|email|e mail|phone|mobile|name|address|zip|postal|linkedin|github|website|portfolio|city|location)\b"
                      r"|\byou (will|expect to|plan to|are expected to) graduate\b|\b(when|what year|which year) (do|will) you graduate\b|\bgraduation (date|year|month|term)\b")


def classify_field(label: str, name: str = "", field_type: str = "", options: list[str] | None = None) -> str:
    haystack = normalize(f"{label} {name} {field_type}")
    text = normalize(label)
    for classification, patterns in PATTERNS:
        if any(re.search(pattern, haystack) for pattern in patterns):
            if classification in TEXT_FACTS:
                if is_yes_no_question(label, options):
                    return "UNKNOWN"  # "Are you eligible ... based on a degree from a U.S. institution?" is not asking for your university
                if len(text.split()) > 10 and not ASKS_FOR.search(text):
                    return "UNKNOWN"  # an essay prompt that happens to mention "email" or "school"
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

