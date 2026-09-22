from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from .safety import classify_field, decide_fill


@dataclass
class DetectedField:
    selector: str
    label: str
    name: str = ""
    field_type: str = "text"
    required: bool = False
    classification: str = "UNKNOWN"


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
    "EMAIL": ("contact", "email"),
    "PHONE": ("contact", "phone"),
    "ADDRESS": ("contact", "address"),
    "EDUCATION": ("education", "university"),
    "GRADUATION_DATE": ("education", "graduation_date"),
    "RELOCATION": ("preferences", "relocation"),
    "SALARY": ("preferences", "salary"),
}


def resolve_field(field: DetectedField, facts: list[dict[str, Any]], country: str | None = None, answers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    classification = classify_field(field.label, field.name, field.field_type)
    field.classification = classification
    if classification in {"WORK_AUTHORIZATION", "SPONSORSHIP"}:
        key = "authorized" if classification == "WORK_AUTHORIZATION" else "requires_sponsorship"
        category = "work_authorization" if classification == "WORK_AUTHORIZATION" else "sponsorship"
        match = next((f for f in facts if f["category"] == category and f["fact_key"] == key and f.get("country_code") == country), None)
    else:
        mapping = FACT_MAPPING.get(classification)
        match = next((f for f in facts if mapping and (f["category"], f["fact_key"]) == mapping), None)
    if match and "value" not in match and "value_json" in match:
        match = dict(match)
        match["value"] = json.loads(match["value_json"])
    matching_answer = next((a for a in (answers or []) if a.get("status") == "VERIFIED" and a.get("normalized_pattern") == " ".join(field.label.lower().split()) and (not a.get("country_code") or a.get("country_code") == country)), None)
    if matching_answer and not match:
        match = {"category": "Answer Vault", "fact_key": matching_answer.get("canonical_question", field.label), "value": matching_answer.get("answer"), "status": matching_answer.get("status")}
    manual_only = classification in {"LEGAL", "DEMOGRAPHIC", "CUSTOM"} and not matching_answer
    decision = decide_fill(classification, match, manual_only=manual_only)
    return {**asdict(field), "decision": asdict(decision)}


def dry_run(fields: list[dict[str, Any]], facts: list[dict[str, Any]], country: str | None, answers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    resolved = [resolve_field(DetectedField(**field), facts, country, answers) for field in fields]
    pauses = [x for x in resolved if x["decision"]["action"] == "PAUSE"]
    return {
        "run_id": str(uuid.uuid4()),
        "status": "WAITING_FOR_USER" if pauses else "READY_FOR_REVIEW",
        "fields": resolved,
        "filled_count": len(resolved) - len(pauses),
        "unknown_count": len(pauses),
        "submission_attempted": False,
        "message": "Dry Run never presses submit.",
    }


def pre_submission_validate(application: dict[str, Any], fields: list[dict[str, Any]], *, settings: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    for field in fields:
        if field.get("required") and field.get("decision", {}).get("action") != "FILL":
            failures.append(f"Required field needs review: {field.get('label')}")
        if field.get("classification") == "UNKNOWN":
            failures.append(f"Unknown field: {field.get('label')}")
    if not application.get("cv_id"):
        failures.append("No approved CV selected")
    if settings.get("dry_run"):
        warnings.append("Dry Run is active; submission is disabled")
    if not settings.get("actual_submission_enabled"):
        failures.append("Actual submissions are not enabled")
    return {"valid": not failures, "blocked": bool(failures), "failures": failures, "warnings": warnings}
