from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field as dc_field
from typing import Any

from .countries import same_country
from .safety import FillDecision, classify_field, decide_fill, normalize, question_similarity


@dataclass
class DetectedField:
    selector: str
    label: str
    name: str = ""
    field_type: str = "text"
    required: bool = False
    classification: str = "UNKNOWN"
    options: list[str] = dc_field(default_factory=list)


class ATSAdapter(ABC):
    name = "BASE"

    @abstractmethod
    def recognizes(self, url: str) -> bool: ...

    def detect_fields(self, page: Any) -> list[DetectedField]:
        """Concrete Playwright adapters override this. Page text is always untrusted."""
        raise NotImplementedError


class HostAdapter(ATSAdapter):
    def __init__(self, name: str, hosts: tuple[str, ...]):
        self.name, self.hosts = name, hosts

    def recognizes(self, url: str) -> bool:
        return any(host in url.lower() for host in self.hosts)


ADAPTERS = [
    HostAdapter("GREENHOUSE", ("greenhouse.io", "boards.greenhouse")),
    HostAdapter("LEVER", ("lever.co",)),
    HostAdapter("WORKDAY", ("myworkdayjobs.com", "workday.com")),
    HostAdapter("ASHBY", ("ashbyhq.com",)),
    HostAdapter("SMARTRECRUITERS", ("smartrecruiters.com",)),
    HostAdapter("GENERIC", ("http://", "https://")),
]


FACT_MAPPING = {
    "NAME": ("personal", "full_name"),
    "FIRST_NAME": ("personal", "first_name"),
    "LAST_NAME": ("personal", "last_name"),
    "EMAIL": ("contact", "email"),
    "PHONE": ("contact", "phone"),
    "ADDRESS": ("contact", "address"),
    "POSTAL_CODE": ("contact", "postal_code"),
    "LOCATION": ("contact", "location"),
    "LINKEDIN": ("contact", "linkedin"),
    "GITHUB": ("contact", "github"),
    "WEBSITE": ("contact", "website"),
    "EDUCATION": ("education", "university"),
    "GRADUATION_DATE": ("education", "graduation_date"),
    "RELOCATION": ("preferences", "relocation"),
    "SALARY": ("preferences", "salary"),
}
COUNTRY_SCOPED = {"WORK_AUTHORIZATION": ("work_authorization", "authorized"), "SPONSORSHIP": ("sponsorship", "requires_sponsorship")}
ANSWER_MATCH_THRESHOLD = 0.75


def _value(fact: dict[str, Any]) -> Any:
    if "value" in fact:
        return fact["value"]
    try:
        return json.loads(fact.get("value_json") or "null")
    except json.JSONDecodeError:
        return fact.get("value_json")


def _fact(facts: list[dict[str, Any]], category: str, key: str, country: str | None = None) -> dict[str, Any] | None:
    for f in facts:
        if f["category"] == category and f["fact_key"] == key and (country is None or same_country(f.get("country_code"), country)):
            return {**f, "value": _value(f)}
    return None


def _derived_name_part(facts: list[dict[str, Any]], part: str) -> dict[str, Any] | None:
    """First/last name from a verified two-word legal name only. Longer names are ambiguous, so they pause."""
    full = _fact(facts, "personal", "full_name")
    if not full or full.get("status") != "VERIFIED" or not isinstance(full["value"], str):
        return None
    tokens = full["value"].split()
    if len(tokens) != 2:
        return None
    return {**full, "value": tokens[0] if part == "first" else tokens[1], "source_label": f"Profile → personal → full_name ({part} word)", "reason": "Derived from a verified two-word legal name."}


def best_answer(label: str, answers: list[dict[str, Any]], country: str | None, company: str | None) -> tuple[dict[str, Any] | None, float]:
    """Closest approved Answer Vault entry in scope, with its similarity score."""
    best, best_score = None, 0.0
    for answer in answers:
        if answer.get("status") != "VERIFIED":
            continue
        if answer.get("country_code") and not same_country(answer.get("country_code"), country):
            continue
        if answer.get("company") and normalize(answer["company"]) != normalize(company or ""):
            continue
        exact = answer.get("normalized_pattern") == " ".join(label.lower().split())
        # "Have you worked for Stripe?" must never reuse an answer written about another employer.
        if not exact and company and normalize(company) in normalize(label) and normalize(company) not in normalize(answer.get("canonical_question", "")):
            continue
        similarity = 1.0 if exact else question_similarity(label, answer.get("canonical_question", ""))
        if similarity > best_score:
            best, best_score = answer, similarity
    return (best, best_score) if best_score >= ANSWER_MATCH_THRESHOLD else (None, best_score)


def _fit_to_options(value: Any, options: list[str]) -> tuple[bool, Any]:
    """Selects must receive one of their own options; booleans map to Yes/No."""
    if not options:
        return True, value
    wanted = ("yes" if value else "no") if isinstance(value, bool) else normalize(str(value))
    for option in options:
        if normalize(option) == wanted:
            return True, option
    date = re.fullmatch(r"(20\d{2})(?:-(\d{2}))?", str(value).strip()) if isinstance(value, str) else None
    if date:  # a verified "2027-05" picks "May 2027" / "05/2027" / "2027" — never a different month or year
        year, month = date.group(1), int(date.group(2) or 0)
        names = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        for option in options:
            text = normalize(option)
            if year not in text.split():
                continue
            mentioned = [i + 1 for i, name in enumerate(names) if name in text.split() or name[:3] in text.split()] or [int(m) for m in re.findall(r"(?<!\d)(0?[1-9]|1[0-2])(?= 20\d{2})", text)]
            if (month and mentioned == [month]) or (not mentioned and len(text.split()) == 1):
                return True, option
    for option in options:  # "Yes, I am authorized" style options
        if isinstance(value, bool) and re.match(rf"{wanted}( |$)", normalize(option)):
            return True, option
    return False, value


def resolve_field(field: DetectedField, facts: list[dict[str, Any]], country: str | None = None, answers: list[dict[str, Any]] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    classification = classify_field(field.label, field.name, field.field_type, field.options)
    field.classification = classification
    match: dict[str, Any] | None = None
    user_answer = False

    if classification == "RESUME":
        cv = context.get("cv")
        match = {"status": "VERIFIED", "value": cv["name"], "source_label": "CV Library → approved CV", "reason": "Your approved CV will be attached."} if cv else None
        decision = decide_fill(classification, match) if cv else FillDecision("PAUSE", reason="Approve a CV in the CV Library first.")
        return {**asdict(field), "decision": {**asdict(decision), "upload": bool(cv)}}
    if classification == "COVER_LETTER":
        letter = context.get("cover_letter")
        if letter and field.field_type != "file":
            decision = FillDecision("FILL", letter, "Drafts → approved cover letter", "You approved this cover letter.")
        else:
            decision = FillDecision("PAUSE", reason="Approve a cover letter draft for this job, or attach one yourself." if not letter else "Cover letter uploads are attached manually.")
        return {**asdict(field), "decision": asdict(decision)}

    if classification in COUNTRY_SCOPED:
        category, key = COUNTRY_SCOPED[classification]
        match = _fact(facts, category, key, country) if country else None
    elif classification in FACT_MAPPING:
        match = _fact(facts, *FACT_MAPPING[classification])
        if (not match or match.get("status") != "VERIFIED") and classification in {"FIRST_NAME", "LAST_NAME"}:
            match = _derived_name_part(facts, "first" if classification == "FIRST_NAME" else "last") or match

    answer, similarity = best_answer(field.label, answers or [], country, context.get("company"))
    if answer and (not match or match.get("status") != "VERIFIED"):
        exact = similarity >= 0.999
        match = {"status": "VERIFIED", "value": answer.get("answer"), "source_label": f"Answer Vault → {answer.get('canonical_question')}",
                 "reason": "Your approved answer to this question." if exact else f"Your approved answer to a similar question ({int(similarity * 100)}% match)."}
        user_answer = True

    manual_only = classification in {"CREDENTIAL", "DOCUMENT"} or (classification in {"LEGAL", "DEMOGRAPHIC", "CUSTOM", "THIRD_PARTY"} and not user_answer)
    decision = decide_fill(classification, match, manual_only=manual_only, user_answer=user_answer)
    if decision.action == "FILL" and classification == "GRADUATION_DATE" and isinstance(decision.value, str) and re.fullmatch(r"20\d{2}-\d{2}", decision.value):
        text = normalize(field.label)
        year, month = decision.value.split("-")
        if "month" in text and "year" not in text:  # "Please confirm the month that you will graduate" -> "May"
            decision = FillDecision("FILL", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][int(month) - 1], decision.source, decision.reason)
        elif "year" in text and "month" not in text:
            decision = FillDecision("FILL", year, decision.source, decision.reason)
    if decision.action == "FILL" and field.options:
        fits, option = _fit_to_options(decision.value, field.options)
        decision = FillDecision("FILL", option, decision.source, decision.reason) if fits else FillDecision("PAUSE", reason=f"Your answer “{decision.value}” isn't one of this question's options.")
    if decision.action == "FILL" and not field.required and decision.value in (None, "", []):
        decision = FillDecision("SKIP", reason="Optional and you have no value for it.")
    return {**asdict(field), "decision": asdict(decision)}


def dry_run(fields: list[dict[str, Any]], facts: list[dict[str, Any]], country: str | None, answers: list[dict[str, Any]] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    known = {f.name for f in DetectedField.__dataclass_fields__.values()}
    resolved = [resolve_field(DetectedField(**{k: v for k, v in field.items() if k in known}), facts, country, answers, context) for field in fields]
    pauses = [x for x in resolved if x["decision"]["action"] == "PAUSE"]
    blocking = [x for x in pauses if x["required"]]
    return {
        "run_id": str(uuid.uuid4()),
        "status": "WAITING_FOR_USER" if blocking else "READY_FOR_REVIEW",
        "fields": resolved,
        "filled_count": sum(1 for x in resolved if x["decision"]["action"] == "FILL"),
        "unknown_count": len(pauses),
        "blocking_count": len(blocking),
        "submission_attempted": False,
        "message": "Dry Run never presses submit.",
    }


def field_definitions(field_state: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip previous decisions so a stored form can be re-resolved after new answers."""
    keep = ("selector", "label", "name", "field_type", "required", "options")
    return [{k: f[k] for k in keep if k in f} for f in field_state]


def pre_submission_validate(application: dict[str, Any], fields: list[dict[str, Any]], *, settings: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    for field in fields:
        action = field.get("decision", {}).get("action")
        if field.get("required") and action != "FILL":
            failures.append(f"Required field needs review: {field.get('label')}")
        elif field.get("classification") == "UNKNOWN" and action not in {"FILL", "SKIP"}:
            warnings.append(f"Optional field left for you: {field.get('label')}")
    if not fields:
        failures.append("No form has been checked yet")
    if not application.get("cv_id"):
        failures.append("No approved CV selected")
    if settings.get("dry_run"):
        warnings.append("Dry Run is active; submission is disabled")
    if not settings.get("actual_submission_enabled"):
        failures.append("Actual submissions are not enabled")
    return {"valid": not failures, "blocked": bool(failures), "failures": failures, "warnings": warnings}
