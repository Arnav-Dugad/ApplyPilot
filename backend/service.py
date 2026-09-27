"""Application services shared by the HTTP API and Autopilot. All state lives in the local SQLite database."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__, ai, cv_tailor, discovery, insights, requirements, shell, sources
from .automation import COUNTRY_SCOPED, FACT_MAPPING, countries_named, dry_run, field_definitions
from .cv_extract import extract as extract_cv
from .database import Database, now
from .eligibility import evaluate, extract_skills
from .job_parser import requirement_sentences
from .languages import detect as detect_languages
from . import referrals
from .safety import TEXT_FACTS, YES_NO_OPTIONS, classify_field, is_yes_no_question, normalize
from .scoring import job_country, location_match, preferred_locations, score
from .countries import country_key, country_name
from .student import get as get_fact_value, profile as student_profile
from .skills import canonical

DB = Database()
ACTIVE_STATUSES = ("QUEUED", "NEEDS_INFO", "WAITING_FOR_USER", "READY_FOR_REVIEW")

# Used when a job's real application form isn't available from its board's API.
STANDARD_FORM = [
    {"selector": "#first_name", "label": "First name", "name": "first_name", "required": True},
    {"selector": "#last_name", "label": "Last name", "name": "last_name", "required": True},
    {"selector": "#email", "label": "Email", "name": "email", "required": True},
    {"selector": "#phone", "label": "Phone", "name": "phone", "required": True},
    {"selector": "#resume", "label": "Resume/CV", "name": "resume", "field_type": "file", "required": True},
    {"selector": "#linkedin", "label": "LinkedIn profile", "name": "linkedin", "required": False},
    {"selector": "#school", "label": "University", "name": "school", "required": True},
    {"selector": "#grad", "label": "Expected graduation date", "name": "graduation", "required": True},
    {"selector": "#auth", "label": "Are you legally authorized to work in this country?", "name": "work_auth", "required": True, "options": ["Yes", "No"]},
    {"selector": "#sponsor", "label": "Will you now or in the future require visa sponsorship?", "name": "sponsorship", "required": True, "options": ["Yes", "No"]},
]


class Conflict(ValueError):
    def __init__(self, message: str, **extra: Any):
        super().__init__(message)
        self.extra = extra


class NotFound(LookupError):
    pass


def decoded(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        for key in list(row):
            if key.endswith("_json"):
                try:
                    row[key[:-5]] = json.loads(row[key]) if row[key] is not None else None
                except (json.JSONDecodeError, TypeError):
                    pass
        if "dry_run" in row:
            row["dry_run"] = bool(row["dry_run"])
    return rows


def one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    row = DB.one(sql, params)
    if not row:
        raise NotFound("Not found")
    return decoded([row])[0]


def facts() -> list[dict[str, Any]]:
    return decoded(DB.rows("SELECT * FROM profile_facts"))


def answers() -> list[dict[str, Any]]:
    return decoded(DB.rows("SELECT * FROM answer_vault"))


TOAST_KINDS = {"AUTOPILOT", "OFFER", "DEADLINE", "EMAIL", "UPDATE", "FOLLOW_UP"}


def notify(kind: str, title: str, body: str = "", page: str | None = None) -> None:
    DB.execute("INSERT INTO notifications(created_at,kind,title,body,page) VALUES(?,?,?,?,?)", (now(), kind, title, body, page))
    if kind in TOAST_KINDS:
        shell.toast(title, body)  # Windows notification when the desktop app is running


# ---------- jobs ----------

JOB_COLUMNS = ["id", "company", "role", "location", "country", "remote_status", "posting_url", "application_url", "source", "date_found", "date_posted", "deadline", "description",
               "required_skills_json", "preferred_skills_json", "degree_requirements", "graduation_requirements", "experience_requirements", "work_authorization", "sponsorship_information",
               "duration", "start_date", "compensation", "application_platform", "requisition_id", "raw_snapshot", "extraction_status", "external_id", "board_questions_json", "employment_type",
               "fingerprint", "duplicate_of", "requirements_json", "listing_json"]


def save_job(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("description") and not payload.get("required_skills") and not payload.get("preferred_skills"):
        payload["required_skills"], payload["preferred_skills"] = extract_skills(payload["description"])
    company = normalize(str(payload.get("company") or ""))
    for key in ("required_skills", "preferred_skills"):  # "Figma" in a Figma posting is the employer, not a skill
        payload[key] = [s for s in payload.get(key) or [] if normalize(s) != company]
    if payload.get("description"):
        for key, sentence in requirement_sentences(payload["description"]).items():
            payload.setdefault(key, sentence)
    if not payload.get("country"):
        payload["country"] = job_country(payload)  # from location text, e.g. "London, UK" -> GB
    existing = DB.one("SELECT id FROM jobs WHERE external_id=?", (payload["external_id"],)) if payload.get("external_id") else None
    job_id = payload.get("id") or (existing["id"] if existing else str(uuid.uuid4()))
    payload["fingerprint"] = insights.fingerprint(payload)
    original = DB.one("SELECT id FROM jobs WHERE fingerprint=? AND id != ? AND duplicate_of IS NULL AND (posting_url IS NULL OR posting_url != ?) ORDER BY date_found LIMIT 1",
                      (payload["fingerprint"], job_id, payload.get("posting_url") or ""))
    payload["duplicate_of"] = original["id"] if original else None  # the same opening posted twice (another board, or re-posted)
    listing = payload.get("listing") or {}
    payload["requirements_json"] = json.dumps(requirements.extract(str(payload.get("role") or ""), payload.get("description") or "", listing))
    payload["listing_json"] = json.dumps(listing) if listing else None
    values = {
        **payload, "id": job_id, "date_found": payload.get("date_found", now()),
        "source": payload.get("source", "MANUAL"), "description": payload.get("description") or "",
        "required_skills_json": json.dumps(payload.get("required_skills", [])),
        "preferred_skills_json": json.dumps(payload.get("preferred_skills", [])),
        "board_questions_json": json.dumps(payload["board_questions"]) if payload.get("board_questions") else None,
        "raw_snapshot": payload.get("raw_snapshot", ""), "extraction_status": payload.get("extraction_status", "UNVERIFIED"),
    }
    placeholders = ",".join("?" for _ in JOB_COLUMNS)
    updates = ",".join(f"{c}=excluded.{c}" for c in JOB_COLUMNS if c not in {"id", "date_found"})
    target = "id" if existing else "posting_url"
    DB.execute(f"INSERT INTO jobs({','.join(JOB_COLUMNS)}) VALUES({placeholders}) ON CONFLICT({target}) DO UPDATE SET {updates}", tuple(values.get(c) for c in JOB_COLUMNS))
    row = DB.one("SELECT * FROM jobs WHERE id=? OR (posting_url IS NOT NULL AND posting_url=?) LIMIT 1", (job_id, payload.get("posting_url")))
    DB.log("JOB_IMPORTED", "job", row["id"] if row else job_id, {"source": payload.get("source")})
    return decoded([row or {}])[0]


def job_detail(job_id: str) -> dict[str, Any]:
    job = one("""SELECT jobs.*, e.result AS eligibility_result, e.checks_json AS eligibility_checks_json, e.match_json AS eligibility_match_json, e.score_json AS score_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id WHERE jobs.id=?""", (job_id,))
    job.pop("raw_snapshot", None)
    job["drafts"] = DB.rows("SELECT * FROM drafts WHERE job_id=? ORDER BY updated_at DESC", (job_id,))
    job["application"] = DB.one("SELECT id,status FROM applications WHERE job_id=?", (job_id,))
    job["languages"] = detect_languages(job.get("description") or "")
    vote = DB.one("SELECT vote FROM job_feedback WHERE job_id=?", (job_id,))
    job["vote"] = vote["vote"] if vote else 0
    job["referrals"] = referrals.matches(job.get("company"), DB.rows("SELECT * FROM connections"))[:8]
    job["duplicates"] = DB.rows("SELECT id, company, role, source, posting_url FROM jobs WHERE duplicate_of=? OR id=?", (job_id, job.get("duplicate_of") or ""))
    notes = DB.one("SELECT notes FROM company_notes WHERE company_key=?", (insights.company_key(job.get("company")),))
    job["company_notes"] = notes["notes"] if notes else ""
    return job


def taste_weights() -> dict[str, float]:
    votes = decoded(DB.rows("SELECT jobs.*, job_feedback.vote FROM job_feedback JOIN jobs ON jobs.id=job_feedback.job_id"))
    return insights.learn_preferences([(v, v["vote"]) for v in votes])


def analyze_job(job_id: str, fact_rows: list[dict[str, Any]] | None = None, weights: dict[str, float] | None = None, log: bool = True) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    fact_rows = fact_rows if fact_rows is not None else facts()
    weights = weights if weights is not None else taste_weights()
    result = evaluate(job, fact_rows)
    result["score"] = score(job, result, preferred_locations(fact_rows), insights.preference_points(job, weights))
    DB.execute("""INSERT INTO eligibility_results(id,job_id,result,checks_json,match_json,score_json,evaluated_at) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(job_id) DO UPDATE SET result=excluded.result,checks_json=excluded.checks_json,match_json=excluded.match_json,score_json=excluded.score_json,evaluated_at=excluded.evaluated_at""",
               (str(uuid.uuid4()), job_id, result["result"], json.dumps(result["checks"]), json.dumps(result["match"]), json.dumps(result["score"]), now()))
    if log:
        DB.log("ELIGIBILITY_ANALYZED", "job", job_id, {"result": result["result"], "score": result["score"]["score"]})
    return result


def analyze_all() -> int:
    """Re-scores every job in one transaction; one summary line in the activity log instead of one per job."""
    fact_rows, weights = facts(), taste_weights()
    prefs = preferred_locations(fact_rows)
    rows = []
    for job in decoded(DB.rows("SELECT * FROM jobs")):
        result = evaluate(job, fact_rows)
        result["score"] = score(job, result, prefs, insights.preference_points(job, weights))
        rows.append((str(uuid.uuid4()), job["id"], result["result"], json.dumps(result["checks"]), json.dumps(result["match"]), json.dumps(result["score"]), now()))
    with DB._lock, DB.connect() as conn:
        conn.executemany("""INSERT INTO eligibility_results(id,job_id,result,checks_json,match_json,score_json,evaluated_at) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(job_id) DO UPDATE SET result=excluded.result,checks_json=excluded.checks_json,match_json=excluded.match_json,score_json=excluded.score_json,evaluated_at=excluded.evaluated_at""", rows)
    DB.log("JOBS_RESCORED", details={"jobs": len(rows)})
    return len(rows)


RESCORING_CATEGORIES = {"skills", "languages", "work_authorization", "sponsorship", "education", "preferences", "citizenship", "experience"}


def save_fact(payload: dict[str, Any]) -> dict[str, Any]:
    """Saves a profile fact; facts that affect eligibility re-score every job so rankings are never stale."""
    saved = decoded([DB.upsert_fact(payload)])[0]
    rescored = analyze_all() if payload.get("category") in RESCORING_CATEGORIES else 0
    return saved | {"reprepared": reprepare_active(), "rescored": rescored}


def backfill_requirements() -> int:
    """Re-reads every job's requirements once after the extractor improves (or for jobs saved before 0.5)."""
    if DB.setting("requirements_version") == requirements.VERSION and not DB.one("SELECT id FROM jobs WHERE requirements_json IS NULL LIMIT 1"):
        return 0
    rows = DB.rows("SELECT id, company, role, description, listing_json FROM jobs")
    updates = [(json.dumps(requirements.extract(r["role"] or "", r["description"] or "", json.loads(r["listing_json"]) if r["listing_json"] else None)), r["id"]) for r in rows]
    skill_updates = []
    for r in rows:  # the skill reader improves too (e.g. "Spring 2027" is no longer the Spring framework)
        if r["description"]:
            company = normalize(str(r["company"] or ""))
            required, preferred = extract_skills(r["description"])
            skill_updates.append((json.dumps([x for x in required if normalize(x) != company]), json.dumps([x for x in preferred if normalize(x) != company]), r["id"]))
    with DB._lock, DB.connect() as conn:
        conn.executemany("UPDATE jobs SET requirements_json=? WHERE id=?", updates)
        conn.executemany("UPDATE jobs SET required_skills_json=?, preferred_skills_json=? WHERE id=?", skill_updates)
    DB.set_setting("requirements_version", requirements.VERSION)
    analyze_all()
    return len(updates)


def backfill_countries() -> int:
    """Jobs saved before 0.5 without a country get one from their location ("Pittsburgh, PA" -> US)."""
    rows = DB.rows("SELECT id, location FROM jobs WHERE country IS NULL OR country = ''")
    updates = [(code, r["id"]) for r in rows if (code := job_country({"location": r["location"]})) and len(code) == 2 and code.isupper()]
    if updates:
        with DB._lock, DB.connect() as conn:
            conn.executemany("UPDATE jobs SET country=? WHERE id=?", updates)
    return len(updates)


def _background_backfill() -> None:
    try:
        countries = backfill_countries()
        if not backfill_requirements() and countries:
            analyze_all()
        if DB.setting("prepared_version") != __version__:
            reprepare_active()  # re-check every form in progress with this version's rules, once
            DB.set_setting("prepared_version", __version__)
    except Exception:
        DB.log("BACKFILL_FAILED", details={"error": traceback.format_exc()[-500:]}, level="ERROR")


def backfill_fingerprints() -> int:
    """Jobs saved before 0.4 get fingerprints so duplicates are recognised across the whole history."""
    rows = DB.rows("SELECT id, company, role, location, country FROM jobs WHERE fingerprint IS NULL ORDER BY date_found")
    for row in rows:
        fp = insights.fingerprint(row)
        original = DB.one("SELECT id FROM jobs WHERE fingerprint=? AND duplicate_of IS NULL AND id != ? LIMIT 1", (fp, row["id"]))
        DB.execute("UPDATE jobs SET fingerprint=?, duplicate_of=? WHERE id=?", (fp, original["id"] if original else None, row["id"]))
    return len(rows)


def vote_job(job_id: str, vote: int) -> dict[str, Any]:
    """Thumbs up/down on a job. Teaches the ranking; a thumbs-down also keeps Autopilot from queueing it."""
    one("SELECT id FROM jobs WHERE id=?", (job_id,))
    if vote not in (-1, 0, 1):
        raise ValueError("Vote must be -1, 0, or 1")
    if vote == 0:
        DB.execute("DELETE FROM job_feedback WHERE job_id=?", (job_id,))
    else:
        DB.execute("INSERT INTO job_feedback(job_id,vote,created_at) VALUES(?,?,?) ON CONFLICT(job_id) DO UPDATE SET vote=excluded.vote,created_at=excluded.created_at", (job_id, vote, now()))
    total = DB.one("SELECT COUNT(*) AS n FROM job_feedback")["n"]
    if total >= 3:
        analyze_all()
    else:
        analyze_job(job_id)
    return {"ok": True, "votes": total, "learning": total >= 3}


def approved_cv(cv_id: str | None = None) -> dict[str, Any] | None:
    if cv_id:
        return DB.one("SELECT id,name,path FROM cvs WHERE id=? AND approved=1", (cv_id,))
    return DB.one("SELECT id,name,path FROM cvs WHERE approved=1 ORDER BY created_at DESC LIMIT 1")


def queue_job(job_id: str, cv_id: str | None = None) -> dict[str, Any]:
    one("SELECT id FROM jobs WHERE id=?", (job_id,))
    duplicate = DB.one("""SELECT a.id FROM applications a
        JOIN jobs existing ON existing.id=a.job_id
        JOIN jobs candidate ON candidate.id=?
        WHERE existing.id=candidate.id
           OR (existing.application_url IS NOT NULL AND existing.application_url=candidate.application_url)
           OR (existing.requisition_id IS NOT NULL AND existing.company=candidate.company AND existing.requisition_id=candidate.requisition_id)
           OR (lower(existing.company)=lower(candidate.company) AND lower(existing.role)=lower(candidate.role) AND coalesce(existing.location,'')=coalesce(candidate.location,''))
        LIMIT 1""", (job_id,))
    if duplicate:
        raise Conflict("You may already have applied to this role.", application_id=duplicate["id"])
    cv = approved_cv(cv_id)
    app_id = str(uuid.uuid4())
    DB.execute("INSERT INTO applications(id,job_id,status,mode,dry_run,cv_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
               (app_id, job_id, "QUEUED", DB.setting("automation_mode"), int(bool(DB.setting("dry_run"))), cv["id"] if cv else None, now(), now()))
    DB.log("APPLICATION_QUEUED", "application", app_id)
    return {"id": app_id, "status": "QUEUED"}


def application_context(app: dict[str, Any]) -> dict[str, Any]:
    cv = approved_cv(app.get("cv_id")) or approved_cv()
    letter = DB.one("SELECT content FROM drafts WHERE job_id=? AND kind='COVER_LETTER' AND status='APPROVED' ORDER BY updated_at DESC LIMIT 1", (app["job_id"],))
    return {"cv": cv, "cover_letter": letter["content"] if letter else None, "company": app.get("company")}


def prepare_application(app_id: str, fields: list[dict[str, Any]] | None = None, source: str | None = None) -> dict[str, Any]:
    """Resolves the application's form against verified facts. Never touches a website."""
    app = one("SELECT applications.*,jobs.country,jobs.company,jobs.board_questions_json FROM applications JOIN jobs ON jobs.id=applications.job_id WHERE applications.id=?", (app_id,))
    if fields is None:
        if app.get("field_state"):
            fields, source = field_definitions(app["field_state"]), app.get("prep_source") or "STANDARD_FORM"
        elif app.get("board_questions"):
            fields, source = app["board_questions"], "BOARD_FORM"
        else:
            fields, source = STANDARD_FORM, "STANDARD_FORM"
    context = application_context(app)
    result = dry_run(fields, facts(), app.get("country"), answers(), context)
    status = result["status"] if app["status"] in ACTIVE_STATUSES else app["status"]
    DB.execute("UPDATE applications SET status=?,field_state_json=?,automation_checkpoint_json=?,prep_source=?,cv_id=coalesce(cv_id,?),updated_at=? WHERE id=?",
               (status, json.dumps(result["fields"]), json.dumps({"run_id": result["run_id"]}), source or "CUSTOM", (context["cv"] or {}).get("id"), now(), app_id))
    DB.log("DRY_RUN_COMPLETED", "application", app_id, {"filled": result["filled_count"], "paused": result["unknown_count"], "source": source})
    return {**result, "source": source}


def reprepare_active() -> int:
    ids = [r["id"] for r in DB.rows(f"SELECT id FROM applications WHERE status IN ({','.join('?' * len(ACTIVE_STATUSES))}) AND field_state_json != '[]'", ACTIVE_STATUSES)]
    for app_id in ids:
        prepare_application(app_id)
    return len(ids)


# ---------- inbox: questions, suggestions, drafts ----------

def _question_kind(classification: str) -> str:
    if classification in COUNTRY_SCOPED:
        return "COUNTRY_FACT"
    if classification in FACT_MAPPING:
        return "FACT"
    if classification in {"RESUME", "COVER_LETTER", "CREDENTIAL"}:
        return classification
    return "ANSWER"


def inbox() -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    apps = decoded(DB.rows(f"""SELECT applications.id,applications.field_state_json,applications.job_id,jobs.company,jobs.role,jobs.country FROM applications
        JOIN jobs ON jobs.id=applications.job_id WHERE applications.status IN ({','.join('?' * len(ACTIVE_STATUSES))})""", ACTIVE_STATUSES))
    for app in apps:
        for f in app.get("field_state") or []:
            if f.get("decision", {}).get("action") != "PAUSE":
                continue
            # Classified again with today's rules: a form checked by an older version may carry an outdated label.
            classification = classify_field(f["label"], f.get("name") or "", f.get("field_type") or "", f.get("options") or [])
            kind = _question_kind(classification)
            country = None
            if kind == "COUNTRY_FACT":
                named = countries_named(f["label"])
                country = next(iter(named)) if len(named) == 1 else app.get("country") if not named else None
                if not country:
                    kind = "ANSWER"  # no single country to file it under: it's saved as an answer to this exact question
            key = normalize(f["label"]) + (f"|{country}" if kind == "COUNTRY_FACT" else "")
            group = groups.setdefault(key, {"key": key, "question": f["label"], "classification": classification if kind != "ANSWER" or classification not in COUNTRY_SCOPED else "UNKNOWN",
                                            "kind": kind, "options": f.get("options") or [], "required": False, "reason": f["decision"].get("reason"), "country": country, "applications": []})
            group["required"] = group["required"] or bool(f.get("required"))
            if not any(a["id"] == app["id"] for a in group["applications"]):
                group["applications"].append({"id": app["id"], "job_id": app["job_id"], "company": app.get("company"), "role": app.get("role")})
    questions = sorted(groups.values(), key=lambda g: (not g["required"], -len(g["applications"]), g["question"]))
    suggestions = decoded(DB.rows("SELECT * FROM suggestions WHERE status='PENDING' ORDER BY confidence DESC, created_at"))
    drafts = DB.rows("SELECT drafts.*, jobs.company, jobs.role FROM drafts LEFT JOIN jobs ON jobs.id=drafts.job_id WHERE drafts.status='DRAFT' ORDER BY drafts.updated_at DESC")
    return {"questions": questions, "suggestions": suggestions, "drafts": drafts}


def answer_question(payload: dict[str, Any]) -> dict[str, Any]:
    """The user's explicit answer is the approval. Facts go to the profile; everything else to the Answer Vault."""
    question = str(payload.get("question") or "").strip()
    value = payload.get("value")
    if not question or value in (None, "", []):
        raise ValueError("Question and answer are required")
    classification = payload.get("classification") or classify_field(question, options=payload.get("options"))
    if classification in TEXT_FACTS and (is_yes_no_question(question, payload.get("options")) or normalize(str(value)) in YES_NO_OPTIONS):
        classification = "UNKNOWN"  # defence in depth: "Yes" must never overwrite a university, phone, or name
    if classification == "CREDENTIAL":
        raise ValueError("Passwords and access codes are never stored; enter them on the site yourself")
    kind = _question_kind(classification)
    if kind == "COUNTRY_FACT":
        country = payload.get("country")
        if not country:
            raise ValueError("This answer needs a country")
        category, key = COUNTRY_SCOPED[classification]
        if isinstance(value, str):
            value = {"yes": True, "no": False}.get(value.strip().lower(), value)
        if not isinstance(value, bool):
            raise ValueError("Answer Yes or No")
        DB.upsert_fact({"category": category, "fact_key": key, "country_code": country, "value": value, "status": "VERIFIED", "source": "INBOX"})
    elif kind == "FACT":
        category, key = FACT_MAPPING[classification]
        DB.upsert_fact({"category": category, "fact_key": key, "value": value, "status": "VERIFIED", "source": "INBOX"})
    else:
        scope = payload.get("scope") or "EXACT"
        company = payload.get("company") if scope == "COMPANY_SPECIFIC" else None
        answer_id = str(uuid.uuid4())
        DB.execute("INSERT INTO answer_vault(id,canonical_question,normalized_pattern,answer_type,answer_json,country_code,company,status,source_fact_ids_json,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (answer_id, question, " ".join(question.lower().split()), scope if scope in {"EXACT", "COMPANY_SPECIFIC", "COUNTRY_SPECIFIC"} else "EXACT", json.dumps(value),
                    payload.get("country") if scope == "COUNTRY_SPECIFIC" else None, company, "VERIFIED", "[]", now(), now()))
        DB.log("ANSWER_VAULT_SAVED", "answer", answer_id, {"type": scope, "status": "VERIFIED", "source": "INBOX"})
    updated = reprepare_active()
    remaining = len(inbox()["questions"])
    return {"ok": True, "applications_updated": updated, "questions_remaining": remaining}


def import_cv(filename: str, content_base64: str, variant: str | None = None) -> dict[str, Any]:
    filename = Path(filename or "resume.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF CVs are accepted")
    raw = base64.b64decode(content_base64, validate=True)
    if len(raw) > 5_000_000 or not raw.startswith(b"%PDF"):
        raise ValueError("Invalid PDF or file exceeds 5 MB")
    digest = hashlib.sha256(raw).hexdigest()
    existing = DB.one("SELECT id,name FROM cvs WHERE sha256=?", (digest,))
    if existing:
        raise ValueError(f"This exact PDF is already in your library as {existing['name']}")
    cv_id = str(uuid.uuid4())
    upload_dir = DB.path.parent / "uploads" / "cvs"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{cv_id}.pdf"
    stored.write_bytes(raw)
    extracted: dict[str, Any] = {"notice": "CV-derived facts are suggestions and remain unverified."}
    found: list[dict[str, Any]] = []
    try:
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(stored).pages)[:100_000]
        found = extract_cv(text)
        skills = next((s["value"] for s in found if s["category"] == "skills"), [])
        extracted.update({"email_candidates": [s["value"] for s in found if s["fact_key"] == "email"], "skill_candidates": skills, "text_length": len(text)})
    except Exception:
        extracted["extraction_error"] = "Text extraction unavailable; original remains imported."
    DB.execute("INSERT INTO cvs(id,name,variant,version,path,sha256,is_original,approved,extracted_profile_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (cv_id, filename, variant or "General Software Engineering", 1, str(stored), digest, 1, 0, json.dumps(extracted), now()))
    DB.log("CV_IMPORTED_UNVERIFIED", "cv", cv_id, {"name": filename, "sha256": digest})
    created = add_suggestions(found, f"CV: {filename}")
    if created:
        notify("SUGGESTIONS", f"{created} profile suggestions from {filename}", "Review them in your Inbox — nothing is verified until you accept it.", "Inbox")
    return {"id": cv_id, "name": filename, "approved": False, "extracted_profile": extracted, "suggestions": created}


def add_suggestions(found: list[dict[str, Any]], source: str) -> int:
    current = {(f["category"], f["fact_key"]): f for f in facts() if f.get("status") == "VERIFIED"}
    created = 0
    for s in found:
        existing = current.get((s["category"], s["fact_key"]))
        value = s["value"]
        if existing is not None:
            if s["category"] == "skills" and isinstance(existing.get("value"), list):
                known = {str(v).lower() for v in existing["value"]}
                value = [v for v in value if str(v).lower() not in known]
                if not value:
                    continue
            elif normalize(str(existing.get("value"))) == normalize(str(value)):
                continue
        before = DB.one("SELECT COUNT(*) AS n FROM suggestions")["n"]
        DB.execute("INSERT OR IGNORE INTO suggestions(id,source,category,fact_key,value_json,confidence,evidence,created_at) VALUES(?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), source, s["category"], s["fact_key"], json.dumps(value), s["confidence"], s["evidence"], now()))
        created += DB.one("SELECT COUNT(*) AS n FROM suggestions")["n"] - before
    return created


def accept_suggestion(suggestion_id: str, value: Any = None) -> dict[str, Any]:
    s = one("SELECT * FROM suggestions WHERE id=? AND status='PENDING'", (suggestion_id,))
    chosen = s["value"] if value in (None, "") else value
    if s["category"] == "skills":
        current = next((f for f in facts() if f["category"] == "skills" and f["fact_key"] == s["fact_key"] and f["status"] == "VERIFIED"), None)
        merged = list(dict.fromkeys([*(current["value"] if current and isinstance(current.get("value"), list) else []), *(chosen if isinstance(chosen, list) else [chosen])]))
        chosen = merged
    DB.upsert_fact({"category": s["category"], "fact_key": s["fact_key"], "value": chosen, "status": "VERIFIED", "source": s["source"]})
    DB.execute("UPDATE suggestions SET status='ACCEPTED' WHERE id=?", (suggestion_id,))
    reprepare_active()
    if s["category"] in RESCORING_CATEGORIES:
        analyze_all()
    return {"ok": True}


def derive_suggestions() -> int:
    """Profile facts ApplyPilot can work out from what you've already verified. They wait in your Inbox until you
    confirm them — nothing here is ever saved silently."""
    rows = [f for f in facts() if f.get("status") == "VERIFIED"]
    me = student_profile(rows)
    found: list[dict[str, Any]] = []
    if not me["citizenship_known"]:
        yes = [f for f in rows if f["category"] == "work_authorization" and f["fact_key"] == "authorized" and f.get("value") is True and f.get("country_code")]
        needs = [f for f in rows if f["category"] == "sponsorship" and f["fact_key"] == "requires_sponsorship" and f.get("value") is True]
        if len(yes) == 1 and len(needs) >= 3:
            home = country_key(yes[0]["country_code"])
            found.append({"category": "citizenship", "fact_key": "countries", "value": [country_name(home) or yes[0]["country_code"]], "confidence": 0.8,
                          "evidence": f"You can work in {country_name(home)} without a visa and need one in {len(needs)} other countries. Confirm your citizenship and ApplyPilot will work out every other country for you."})
    if "enrolled" in me["derived"] and me["enrolled"] is True:
        found.append({"category": "education", "fact_key": "enrolled", "value": True, "confidence": 0.9,
                      "evidence": f"You graduate in {me['graduation']}, so you're a current student."})
    if "year_of_study" in me["derived"] and me["year_of_study"]:
        found.append({"category": "education", "fact_key": "year_of_study", "value": me["year_of_study"], "confidence": 0.7,
                      "evidence": f"Worked out from your {me['graduation']} graduation and a {me['program_years']}-year degree."})
    roles = get_fact_value(rows, "preferences", "roles")
    if not roles and re.search(r"(?i)comput|software|information|data|artificial|electronic", str(me.get("major") or "")):
        found.append({"category": "preferences", "fact_key": "roles", "value": ["Software engineering", "Data science", "AI / Machine learning"], "confidence": 0.6,
                      "evidence": f"You study {me['major']}. Autopilot will then skip roles like sales or finance from worldwide lists. Edit the list before confirming if you like."})
    if "level" in me["derived"] and me["level"]:
        found.append({"category": "education", "fact_key": "level", "value": me["level"], "confidence": 0.7, "evidence": "Worked out from your degree name."})
    return add_suggestions(found, "PROFILE_RULES") if found else 0


def dismiss_suggestion(suggestion_id: str) -> dict[str, Any]:
    DB.execute("UPDATE suggestions SET status='DISMISSED' WHERE id=?", (suggestion_id,))
    return {"ok": True}


# ---------- local AI drafts ----------

def ai_config() -> dict[str, Any]:
    return DB.setting("ollama") or {}


def summarize_job(job_id: str) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    summary = ai.summarize_job(ai_config(), job)
    DB.execute("UPDATE jobs SET ai_summary_json=? WHERE id=?", (json.dumps(summary), job_id))
    return summary


def _save_draft(kind: str, content: str, model: str, job_id: str | None, question: str | None = None) -> dict[str, Any]:
    draft_id = str(uuid.uuid4())
    DB.execute("INSERT INTO drafts(id,kind,job_id,question,content,status,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (draft_id, kind, job_id, question, content, "DRAFT", model, now(), now()))
    DB.log("AI_DRAFT_CREATED", "draft", draft_id, {"kind": kind, "model": model})
    return DB.one("SELECT * FROM drafts WHERE id=?", (draft_id,)) or {}


def draft_cover_letter(job_id: str) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    result = ai.cover_letter(ai_config(), job, facts())
    return {**_save_draft("COVER_LETTER", result["content"], result["model"], job_id), "unverified_skills": result["unverified_skills"]}


def draft_answer(question: str, job_id: str | None) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,)) if job_id else None
    result = ai.draft_answer(ai_config(), question, job, facts())
    return {**_save_draft("ANSWER", result["content"], result["model"], job_id, question), "unverified_skills": result["unverified_skills"]}


def update_draft(draft_id: str, content: str | None, approve: bool) -> dict[str, Any]:
    draft = one("SELECT drafts.*, jobs.company FROM drafts LEFT JOIN jobs ON jobs.id=drafts.job_id WHERE drafts.id=?", (draft_id,))
    text = (content if content is not None else draft["content"]).strip()
    if not text:
        raise ValueError("Draft is empty")
    if approve and re.search(r"\[[^\]]{3,}\]", text):
        raise ValueError("Replace the [bracketed placeholders] before approving")
    if approve and draft["kind"] == "CV_TAILORED":
        flags = cv_tailor.invention_flags(_source_cv_text(draft), text, _verified_skills())
        if flags["skills"] or flags["numbers"]:
            found = ", ".join(flags["skills"] + flags["numbers"])
            raise ValueError(f"The tailored CV mentions things your original doesn't ({found}). Edit them out before approving.")
    DB.execute("UPDATE drafts SET content=?,status=?,updated_at=? WHERE id=?", (text, "APPROVED" if approve else "DRAFT", now(), draft_id))
    if approve and draft["kind"] == "CV_TAILORED":
        cv = finalize_tailored_cv({**draft, "content": text})
        DB.log("DRAFT_APPROVED", "draft", draft_id)
        return {"ok": True, "cv": cv}
    if approve and draft["kind"] == "FOLLOW_UP" and draft.get("application_id"):
        DB.execute("UPDATE applications SET followed_up_at=? WHERE id=?", (now(), draft["application_id"]))
        DB.log("DRAFT_APPROVED", "draft", draft_id)
        return {"ok": True}
    if approve and draft["kind"] == "ANSWER" and draft.get("question"):
        answer_question({"question": draft["question"], "value": text, "classification": "CUSTOM", "scope": "COMPANY_SPECIFIC" if draft.get("company") else "EXACT", "company": draft.get("company")})
    elif approve:
        reprepare_active()
    DB.log("DRAFT_APPROVED" if approve else "DRAFT_EDITED", "draft", draft_id)
    return {"ok": True}


# ---------- watchlist ----------

def add_watch(text: str) -> dict[str, Any]:
    board = discovery.detect_board(text)
    if not board:
        raise ValueError("Paste a Greenhouse, Lever, Ashby, or SmartRecruiters careers link (or pick a company below)")
    platform, slug = board
    if DB.one("SELECT id FROM watchlist WHERE platform=? AND lower(slug)=lower(?)", (platform, slug)):
        raise Conflict("You're already following this company")
    result = discovery.fetch_board(platform, slug)
    catalog_name = next((c["company"] for c in discovery.CATALOG if c["platform"] == platform and c["slug"].lower() == slug.lower()), None)
    watch_id = str(uuid.uuid4())
    DB.execute("INSERT INTO watchlist(id,platform,slug,company,created_at,last_status,jobs_seen,internships_seen) VALUES(?,?,?,?,?,?,?,?)",
               (watch_id, platform, slug, catalog_name or result["company"], now(), "Verified", result["total"], len(result["jobs"])))
    DB.log("WATCHLIST_ADDED", "watchlist", watch_id, {"platform": platform, "slug": slug})
    return {"id": watch_id, "company": catalog_name or result["company"], "internships": len(result["jobs"]), "total": result["total"]}


# ---------- worldwide sources ----------

ROLE_KEYWORDS = {
    "software": r"software|developer|engineer|swe\b|back ?end|front ?end|full ?stack|mobile|ios|android|web|platform|infrastructure|devops|sre\b|cloud|security|systems|programmer|coding",
    "data": r"data|analytics|analyst|\bbi\b|business intelligence",
    "ai": r"machine learning|\bml\b|\bai\b|artificial intelligence|deep learning|\bnlp\b|computer vision|\bllm|research",
    "product": r"product",
    "design": r"design|\bux\b|\bui\b",
    "quant": r"quant|trading",
    "hardware": r"hardware|embedded|firmware|electrical|fpga|asic|robotics",
    "business": r"business|sales|marketing|operations|finance|consult|strategy",
}


def role_matches(job: dict[str, Any], roles: list[str]) -> bool:
    """True when the title (or the board's category) fits one of your preferred roles. No roles set = everything fits."""
    if not roles:
        return True
    title = f"{job.get('role') or ''} {(job.get('listing') or {}).get('category') or ''}".lower()
    for role in roles:
        text = str(role).lower()
        group = next((k for k in ROLE_KEYWORDS if k in text or (k == "ai" and "machine learning" in text) or (k == "software" and "engineer" in text)), None)
        if group and re.search(ROLE_KEYWORDS[group], title):
            return True
        if not group and text and re.search(rf"\b{re.escape(text)}\b", title):
            return True
    return False


def place_job(job: dict[str, Any], prefs: list[str]) -> bool | None:
    """Picks the job's country from its locations (preferring one you'd go to) and says whether it fits your locations."""
    places = job.get("locations") or [job.get("location")]
    remote_countries = (job.get("listing") or {}).get("remote_countries") or []
    candidates = []
    for place in places:
        code = sources.location_country(place)
        candidates.append(({**job, "location": place, "country": code}, code))
    for name in remote_countries:
        code = country_key(name)
        candidates.append(({**job, "location": name, "country": code, "remote_status": None}, code))
    fits = [location_match(c, prefs)[0] for c, _ in candidates] or [None]
    chosen = next((code for (c, code), ok in zip(candidates, fits) if ok and code), None)
    job["country"] = job.get("country") or chosen or next((code for _, code in candidates if code), None)
    if True in fits:
        return True
    if remote_countries:
        return False  # remote, but only for people in other countries
    return None if None in fits else False


def discover_worldwide(cfg: dict[str, Any], prefs: list[str], roles: list[str], event: Callable[..., None], summary: dict[str, Any],
                       fetch: Callable[[str], list[dict[str, Any]]] | None = None, enrich: Callable[..., list[dict[str, Any]]] | None = None) -> list[str]:
    """Searches every enabled worldwide source, keeps internships that fit your locations and roles, and saves them."""
    fetch = fetch or sources.fetch
    enrich = enrich or sources.enrich_many
    enabled = {**{k: True for k in sources.SOURCES}, **(DB.setting("sources") or {})}
    status = DB.setting("source_status") or {}
    known_ids = {r["external_id"] for r in DB.rows("SELECT external_id FROM jobs WHERE external_id IS NOT NULL")}
    known_urls = {r["posting_url"] for r in DB.rows("SELECT posting_url FROM jobs WHERE posting_url IS NOT NULL")}
    keep: list[dict[str, Any]] = []
    for key, meta in sources.SOURCES.items():
        if not enabled.get(key):
            continue
        try:
            found = fetch(key)
        except Exception as exc:  # one broken feed never stops the run
            status[key] = {"at": now(), "error": str(exc)[:200], "found": 0, "new": 0}
            event("worldwide", f"{meta['name']}: couldn't be reached ({exc})", "WARN", source=key)
            continue
        fresh = filtered = 0
        for job in found:
            summary["found"] += 1
            if job.get("external_id") in known_ids or job.get("posting_url") in known_urls:
                continue
            if cfg["internships_only"] and not discovery.is_internship(job.get("role", ""), job.get("employment_type")):
                continue
            fits = place_job(job, prefs)
            if (cfg["location_filter"] and fits is False) or not role_matches(job, roles):
                filtered += 1
                continue
            known_urls.add(job.get("posting_url"))
            keep.append(job)
            fresh += 1
            if fresh >= 250:
                break
        summary["filtered"] += filtered
        status[key] = {"at": now(), "error": None, "found": len(found), "new": fresh}
        event("worldwide", f"{meta['name']}: {len(found)} openings, {fresh} fit you" + (f" ({filtered} skipped: other places or roles)" if filtered else ""), source=key, new=fresh)
    DB.set_setting("source_status", status)
    if keep:
        keep.sort(key=lambda j: j.get("date_posted") or "", reverse=True)
        need = sum(1 for j in keep if not j.get("description"))
        if need:
            event("worldwide", f"Reading the full posting for {min(need, 60)} listings from their company pages")
        keep = enrich(keep, 60)
    new_ids = []
    for job in keep:
        if job.get("external_id") in known_ids:
            continue  # enrichment revealed a job you already had (found through a followed company)
        known_ids.add(job.get("external_id"))
        job.pop("locations", None)
        new_ids.append(save_job(job)["id"])
    summary["new"] += len(new_ids)
    summary["worldwide"] = len(new_ids)
    return new_ids


def sources_state() -> dict[str, Any]:
    enabled = {**{k: True for k in sources.SOURCES}, **(DB.setting("sources") or {})}
    status = DB.setting("source_status") or {}
    counts = {r["source"]: r["n"] for r in DB.rows("SELECT source, COUNT(*) AS n FROM jobs GROUP BY source")}
    return {"sources": [{"key": k, "name": v["name"], "about": v["about"], "enabled": bool(enabled.get(k)), "status": status.get(k), "jobs": counts.get(k, 0)}
                        for k, v in sources.SOURCES.items()],
            "worldwide": AUTOPILOT.config().get("worldwide", True)}


# ---------- GitHub projects ----------

def _project_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40] or "project"


def import_github_projects(links: list[str]) -> dict[str, Any]:
    """Saves several GitHub repositories as projects at once. Skills they use that aren't in your verified
    skills are returned as suggestions, never added silently."""
    from . import github_import
    if not links:
        raise ValueError("Pick at least one repository")
    if len(links) > 20:
        raise ValueError("Import up to 20 repositories at a time")
    saved, errors = [], []
    for link in links:
        try:
            project = github_import.project(link)
        except github_import.GitHubError as exc:
            errors.append({"link": link, "error": str(exc)})
            if "60 lookups" in str(exc):
                break
            continue
        DB.upsert_fact({"category": "projects", "fact_key": _project_key(project["name"]), "value": project, "status": "VERIFIED", "source": "GITHUB"})
        saved.append(project)
    known = {canonical(s) for f in facts() if f["category"] == "skills" and f.get("status") == "VERIFIED" for s in (f.get("value") if isinstance(f.get("value"), list) else [f.get("value")]) if s}
    new_skills = sorted({s for p in saved for s in p["skills"] if canonical(s) not in known}, key=str.lower)
    if saved:
        DB.log("GITHUB_PROJECTS_IMPORTED", details={"count": len(saved)})
    return {"saved": saved, "errors": errors, "new_skills": new_skills}


def student_summary(fact_rows: list[dict[str, Any]]) -> dict[str, Any]:
    me = student_profile(fact_rows)
    me["experience"] = {k: v for k, v in me["experience"].items() if k != "entries"}
    return me


def visa_overview(fact_rows: list[dict[str, Any]], jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Can you work there? For your citizenship countries, your preferred countries, and where your jobs are."""
    from . import visa
    me = student_profile(fact_rows)
    codes: list[str] = list(me["citizenships"])
    for place in preferred_locations(fact_rows):
        code = country_key(place)
        if code and len(code) == 2 and code.isupper():
            codes.append(code)
    counts: dict[str, int] = {}
    for job in jobs:
        if job.get("country_code"):
            counts[job["country_code"]] = counts.get(job["country_code"], 0) + 1
    codes += [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:10]]
    seen: list[str] = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    rows = visa.summary(fact_rows, seen[:24])
    for row in rows:
        row["jobs"] = counts.get(row["country"], 0)
    return rows


# ---------- Autopilot ----------

class Autopilot:
    """Discover → analyze → rank → queue → prepare, on a schedule. Never presses submit."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.running_id: str | None = None
        self._scheduler: threading.Thread | None = None
        self._stop = threading.Event()

    def config(self) -> dict[str, Any]:
        from .database import AUTOPILOT_DEFAULTS
        return {**AUTOPILOT_DEFAULTS, **(DB.setting("autopilot") or {})}

    def last_run(self) -> dict[str, Any] | None:
        row = DB.one("SELECT * FROM autopilot_runs ORDER BY started_at DESC LIMIT 1")
        return decoded([row])[0] if row else None

    def next_run_at(self) -> str | None:
        cfg = self.config()
        if not cfg["enabled"]:
            return None
        last = self.last_run()
        if not last:
            return now()
        started = datetime.fromisoformat(last["started_at"])
        return (started + timedelta(hours=float(cfg["interval_hours"]))).isoformat()

    def start_scheduler(self) -> None:
        if self._scheduler and self._scheduler.is_alive():
            return

        def loop() -> None:
            last_housekeeping = 0.0
            while not self._stop.wait(30):
                try:
                    if time.time() - last_housekeeping > 600:
                        last_housekeeping = time.time()
                        housekeeping()
                except Exception:
                    DB.log("HOUSEKEEPING_ERROR", details={"error": traceback.format_exc()[-500:]}, level="ERROR")
                try:
                    due = self.next_run_at()
                    if due and datetime.fromisoformat(due) <= datetime.now(timezone.utc) and not self.running_id:
                        self.start("SCHEDULE")
                except Exception:
                    DB.log("AUTOPILOT_SCHEDULER_ERROR", details={"error": traceback.format_exc()[-500:]}, level="ERROR")

        self._scheduler = threading.Thread(target=loop, name="autopilot-scheduler", daemon=True)
        self._scheduler.start()

    def start(self, trigger: str = "MANUAL") -> str:
        with self._lock:
            if self.running_id:
                raise Conflict("Autopilot is already running", run_id=self.running_id)
            run_id = str(uuid.uuid4())
            self.running_id = run_id
            DB.execute("INSERT INTO autopilot_runs(id,trigger,status,started_at) VALUES(?,?,?,?)", (run_id, trigger, "RUNNING", now()))
        threading.Thread(target=self.execute, args=(run_id,), name="autopilot-run", daemon=True).start()
        return run_id

    def run_sync(self, trigger: str = "MANUAL") -> dict[str, Any]:
        with self._lock:
            if self.running_id:
                raise Conflict("Autopilot is already running")
            run_id = str(uuid.uuid4())
            self.running_id = run_id
            DB.execute("INSERT INTO autopilot_runs(id,trigger,status,started_at) VALUES(?,?,?,?)", (run_id, trigger, "RUNNING", now()))
        self.execute(run_id)
        return one("SELECT * FROM autopilot_runs WHERE id=?", (run_id,))

    def execute(self, run_id: str, fetch: Callable[..., dict[str, Any]] | None = None, source_fetch: Callable[[str], list[dict[str, Any]]] | None = None) -> None:
        # Tests inject a board fetcher; the worldwide search then only runs if they inject one for it too (no network in tests).
        worldwide_fetch = source_fetch or (None if fetch else sources.fetch)
        fetch = fetch or discovery.fetch_board
        events: list[dict[str, Any]] = []
        summary = {"boards": 0, "found": 0, "new": 0, "worldwide": 0, "filtered": 0, "analyzed": 0, "queued": 0, "prepared": 0, "ready": 0, "needs_you": 0, "summaries": 0, "letters": 0}

        def event(step: str, message: str, level: str = "INFO", **data: Any) -> None:
            events.append({"at": now(), "step": step, "message": message, "level": level, **data})
            DB.execute("UPDATE autopilot_runs SET events_json=?,summary_json=? WHERE id=?", (json.dumps(events), json.dumps(summary), run_id))

        cfg = self.config()
        try:
            fact_rows = facts()
            prefs = preferred_locations(fact_rows)
            watch = DB.rows("SELECT * FROM watchlist ORDER BY company")
            event("scan", f"Scanning {len(watch)} job board{'s' if len(watch) != 1 else ''}" if watch else "No companies followed yet — add some in Autopilot to discover jobs automatically")
            new_ids: list[str] = []
            for board in watch:
                try:
                    result = fetch(board["platform"], board["slug"], internships_only=cfg["internships_only"])
                except Exception as exc:
                    DB.execute("UPDATE watchlist SET last_scanned_at=?,last_status=? WHERE id=?", (now(), f"Error: {exc}"[:200], board["id"]))
                    event("scan", f"{board['company']}: {exc}", "WARN", company=board["company"])
                    continue
                summary["boards"] += 1
                fresh = 0
                for job in result["jobs"]:
                    summary["found"] += 1
                    if DB.one("SELECT id FROM jobs WHERE external_id=? OR posting_url=?", (job.get("external_id"), job.get("posting_url"))):
                        continue
                    if cfg["location_filter"] and location_match(job, prefs)[0] is False:
                        summary["filtered"] += 1
                        continue
                    job["company"] = board["company"]
                    new_ids.append(save_job(job)["id"])
                    fresh += 1
                summary["new"] += fresh
                DB.execute("UPDATE watchlist SET last_scanned_at=?,last_status=?,jobs_seen=?,internships_seen=? WHERE id=?", (now(), "OK", result["total"], len(result["jobs"]), board["id"]))
                event("scan", f"{board['company']}: {len(result['jobs'])} internship{'s' if len(result['jobs']) != 1 else ''}, {fresh} new", company=board["company"], new=fresh)

            if cfg.get("worldwide", True) and worldwide_fetch:
                event("worldwide", "Searching worldwide internship lists")
                new_ids += discover_worldwide(cfg, prefs, student_profile(fact_rows)["roles"], event, summary, worldwide_fetch,
                                              None if source_fetch is None else (lambda jobs, limit: jobs))

            summary["analyzed"] = analyze_all()
            event("analyze", f"Scored {summary['analyzed']} jobs against your verified profile")

            ai_on = ai.status(ai_config())["enabled"]
            if ai_on and cfg["ai_summaries"]:
                for job_id in new_ids[:12]:
                    try:
                        summarize_job(job_id)
                        summary["summaries"] += 1
                    except Exception as exc:
                        event("ai", f"Summary skipped: {exc}", "WARN")
                        break
                if summary["summaries"]:
                    event("ai", f"Local AI summarized {summary['summaries']} new jobs")

            queued_now: list[str] = []
            if cfg["auto_queue"]:
                candidates = DB.rows("""SELECT jobs.id, jobs.company, jobs.role, jobs.deadline, e.result, e.score_json FROM jobs JOIN eligibility_results e ON e.job_id=jobs.id
                    WHERE e.result IN ('ELIGIBLE','LIKELY_ELIGIBLE') AND jobs.duplicate_of IS NULL
                      AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id=jobs.id)
                      AND NOT EXISTS (SELECT 1 FROM job_feedback f WHERE f.job_id=jobs.id AND f.vote < 0)""")
                for c in sorted(candidates, key=lambda r: -json.loads(r["score_json"] or "{}").get("score", 0)):
                    s = json.loads(c["score_json"] or "{}")
                    if s.get("score", 0) < cfg["min_score"] or (cfg["internships_only"] and not s.get("is_internship")):
                        continue
                    if c.get("deadline") and c["deadline"] < now():
                        continue
                    try:
                        app = queue_job(c["id"])
                    except Conflict:
                        continue
                    queued_now.append(app["id"])
                    summary["queued"] += 1
                    event("queue", f"Queued {c['role']} at {c['company']} (score {s.get('score')})", job_id=c["id"])
                if not summary["queued"]:
                    event("queue", f"No new jobs met your bar (eligible and score ≥ {cfg['min_score']})")

            if cfg["auto_prepare"]:
                pending = DB.rows(f"SELECT id FROM applications WHERE status IN ({','.join('?' * len(ACTIVE_STATUSES))})", ACTIVE_STATUSES)
                for app in pending:
                    result = prepare_application(app["id"])
                    summary["prepared"] += 1
                    summary["ready" if result["status"] == "READY_FOR_REVIEW" else "needs_you"] += 1
                event("prepare", f"Checked {summary['prepared']} application forms: {summary['ready']} ready, {summary['needs_you']} need your answers")

            if ai_on and cfg["ai_cover_letters"]:
                for app_id in queued_now[:5]:
                    job_id = DB.one("SELECT job_id FROM applications WHERE id=?", (app_id,))["job_id"]
                    if DB.one("SELECT id FROM drafts WHERE job_id=? AND kind='COVER_LETTER'", (job_id,)):
                        continue
                    try:
                        draft_cover_letter(job_id)
                        summary["letters"] += 1
                    except Exception as exc:
                        event("ai", f"Cover letter skipped: {exc}", "WARN")
                        break
                if summary["letters"]:
                    event("ai", f"Drafted {summary['letters']} cover letters for your review")

            questions = len(inbox()["questions"])
            headline = f"{summary['new']} new internship{'s' if summary['new'] != 1 else ''}, {summary['queued']} queued"
            body = f"{summary['ready']} ready to review" + (f" · {questions} question{'s' if questions != 1 else ''} waiting in your Inbox" if questions else "")
            event("done", f"{headline}. {body}.")
            if summary["new"] or summary["queued"] or questions:
                notify("AUTOPILOT", headline, body, "Inbox" if questions else "Queue")
            DB.execute("UPDATE autopilot_runs SET status='COMPLETED',finished_at=?,events_json=?,summary_json=? WHERE id=?", (now(), json.dumps(events), json.dumps(summary), run_id))
            DB.log("AUTOPILOT_RUN_COMPLETED", "autopilot", run_id, {k: v for k, v in summary.items() if v})
        except Exception as exc:
            events.append({"at": now(), "step": "error", "message": f"Stopped safely: {exc}", "level": "ERROR"})
            DB.execute("UPDATE autopilot_runs SET status='FAILED',finished_at=?,events_json=?,summary_json=? WHERE id=?", (now(), json.dumps(events), json.dumps(summary), run_id))
            DB.log("AUTOPILOT_RUN_FAILED", "autopilot", run_id, {"error": str(exc)}, "ERROR")
        finally:
            self.running_id = None


AUTOPILOT = Autopilot()


def autopilot_state() -> dict[str, Any]:
    runs = decoded(DB.rows("SELECT * FROM autopilot_runs ORDER BY started_at DESC LIMIT 8"))
    return {"config": AUTOPILOT.config(), "running": AUTOPILOT.running_id, "next_run_at": AUTOPILOT.next_run_at(), "runs": runs}


# ---------- bootstrap ----------

def public_settings() -> dict[str, Any]:
    """Settings for the UI. Secrets (the encrypted email password) never leave the service."""
    settings = {r["key"]: json.loads(r["value_json"]) for r in DB.rows("SELECT * FROM settings")}
    mail = dict(settings.get("email_sync") or {})
    mail["has_password"] = bool(mail.pop("secret", None))
    settings["email_sync"] = mail
    settings.pop("deadline_alerts", None)
    return settings


_backfilled = False


def bootstrap() -> dict[str, Any]:
    global _backfilled
    if not _backfilled:
        _backfilled = True
        backfill_fingerprints()
        derive_suggestions()
        # Re-reading every posting after an update takes a few seconds, so the window opens straight away.
        threading.Thread(target=_background_backfill, name="requirements-backfill", daemon=True).start()
    settings = public_settings()
    jobs = decoded(DB.rows("""SELECT jobs.id,company,role,location,country,remote_status,posting_url,application_url,source,date_found,date_posted,deadline,compensation,employment_type,
        substr(description,1,700) AS description,required_skills_json,preferred_skills_json,work_authorization,sponsorship_information,application_platform,extraction_status,ai_summary_json,
        duplicate_of, requirements_json, (SELECT vote FROM job_feedback f WHERE f.job_id=jobs.id) AS vote,
        CASE WHEN board_questions_json IS NULL THEN 0 ELSE json_array_length(board_questions_json) END AS question_count,
        e.result AS eligibility_result,e.checks_json AS eligibility_checks_json,e.match_json AS eligibility_match_json,e.score_json AS score_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id ORDER BY date_found DESC"""))
    for job in jobs:
        code = job_country(job)
        job["country_code"] = code if code and len(code) == 2 and code.isupper() else None
        job.pop("requirements_json", None)
        job["tags"] = requirements.tags(job.pop("requirements", None) or {})
    apps = decoded(DB.rows("""SELECT applications.*,jobs.company,jobs.role,jobs.location,jobs.country,jobs.posting_url,jobs.application_url,jobs.deadline,cvs.name AS cv_name,
        (SELECT e.id FROM email_events e WHERE e.application_id=applications.id AND e.action='MOVE' ORDER BY e.created_at DESC LIMIT 1) AS email_event_id
        FROM applications JOIN jobs ON jobs.id=applications.job_id LEFT JOIN cvs ON cvs.id=applications.cv_id ORDER BY applications.updated_at DESC"""))
    cvs = decoded(DB.rows("SELECT id,name,variant,version,sha256,approved,extracted_profile_json,original_id,created_at FROM cvs ORDER BY created_at DESC"))
    for cv in cvs:
        cv["approved"] = bool(cv["approved"])
    box = inbox()
    fact_rows = decoded(DB.rows("SELECT * FROM profile_facts ORDER BY category,fact_key"))
    from . import updater
    follow_ups = DB.one("SELECT COUNT(*) AS n FROM drafts WHERE kind='FOLLOW_UP' AND status='DRAFT'")["n"]
    return {
        "version": __version__, "settings": settings, "facts": fact_rows,
        "jobs": jobs, "applications": apps, "cvs": cvs,
        "activity": decoded(DB.rows("SELECT * FROM activity_log ORDER BY id DESC LIMIT 200")),
        "answers": decoded(DB.rows("SELECT * FROM answer_vault ORDER BY updated_at DESC")),
        "watchlist": DB.rows("SELECT * FROM watchlist ORDER BY company"), "catalog": discovery.CATALOG,
        "inbox": box, "autopilot": autopilot_state(),
        "notifications": DB.rows("SELECT * FROM notifications ORDER BY id DESC LIMIT 30"),
        "update": updater.state(),
        "strength": insights.profile_strength(fact_rows, any(c["approved"] for c in cvs)),
        "today": insights.today(jobs, apps, box, follow_ups),
        "health": insights.health(DB.rows("SELECT * FROM watchlist"), jobs, apps, fact_rows, decoded(DB.rows("SELECT * FROM answer_vault")), any(c["approved"] for c in cvs), settings["email_sync"]),
        "connections": DB.one("SELECT COUNT(*) AS n FROM connections")["n"],
        "offers": offers_overview(settings.get("base_currency") or "USD"),
        "student": student_summary(fact_rows),
        "visa": visa_overview(fact_rows, jobs),
    }


# ---------- housekeeping: deadlines, follow-ups, email ----------

def housekeeping() -> dict[str, Any]:
    jobs = decoded(DB.rows("SELECT id, company, role, deadline FROM jobs"))
    apps = DB.rows("SELECT id, job_id, status FROM applications")
    alerted = set(DB.setting("deadline_alerts") or [])
    fired = 0
    for alert in insights.deadline_alerts(jobs, apps):
        if alert["application_id"] in alerted:
            continue
        alerted.add(alert["application_id"])
        fired += 1
        notify("DEADLINE", f"{alert['company']} closes in {alert['hours']}h", f"{alert['role']} — finish it in your Queue before it closes.", "Queue")
    if fired:
        DB.set_setting("deadline_alerts", sorted(alerted))
    drafted = draft_follow_ups()
    synced = None
    mail = DB.setting("email_sync") or {}
    if mail.get("enabled") and mail.get("secret"):
        last = mail.get("last_sync")
        if not last or datetime.fromisoformat(last) < datetime.now(timezone.utc) - timedelta(minutes=30):
            try:
                synced = sync_email()
            except Exception:
                synced = None
    return {"deadline_alerts": fired, "follow_ups": drafted, "email": synced}


FOLLOW_UP_DAYS = 14


def draft_follow_ups() -> int:
    """Two weeks after applying with no reply, a polite follow-up is drafted for review. Nothing is sent."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FOLLOW_UP_DAYS)).isoformat()
    due = DB.rows("""SELECT applications.id, applications.job_id, applications.submitted_at, jobs.company, jobs.role FROM applications JOIN jobs ON jobs.id=applications.job_id
        WHERE applications.status IN ('APPLIED','SUBMITTED') AND applications.submitted_at IS NOT NULL AND applications.submitted_at < ?
          AND applications.followed_up_at IS NULL AND NOT EXISTS (SELECT 1 FROM drafts d WHERE d.application_id=applications.id AND d.kind='FOLLOW_UP')""", (cutoff,))
    name = next((f["value"] for f in facts() if f["category"] == "personal" and f["fact_key"] == "full_name" and f.get("status") == "VERIFIED"), None)
    for app in due:
        applied = datetime.fromisoformat(app["submitted_at"]).strftime("%d %B")
        text = (f"Subject: Following up on my {app['role']} application\n\nHi {app['company']} recruiting team,\n\n"
                f"I applied for the {app['role']} position on {applied} and wanted to follow up. I'm still very interested in the role and in {app['company']}'s work, "
                f"and I'd be glad to share anything else that would help with your review.\n\nThank you for your time,\n{name or 'Your name'}")
        draft_id = str(uuid.uuid4())
        DB.execute("INSERT INTO drafts(id,kind,job_id,application_id,content,status,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (draft_id, "FOLLOW_UP", app["job_id"], app["id"], text, "DRAFT", "ApplyPilot", now(), now()))
    if due:
        notify("FOLLOW_UP", f"{len(due)} follow-up{'s' if len(due) > 1 else ''} ready", "Two weeks since you applied — review the drafts in your Inbox.", "Inbox")
    return len(due)


# ---------- email sync ----------

def save_email_settings(payload: dict[str, Any]) -> dict[str, Any]:
    from . import email_sync

    current = DB.setting("email_sync") or {}
    provider = str(payload.get("provider") or current.get("provider") or "GMAIL").upper()
    if provider not in email_sync.PRESETS:
        raise ValueError("Unknown email provider")
    host = str(payload.get("host") or email_sync.PRESETS[provider]["host"] or current.get("host") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", host):
        raise ValueError("Enter your mail server's IMAP host, e.g. imap.example.com")
    address = str(payload.get("address") if payload.get("address") is not None else current.get("address") or "").strip()
    if address and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
        raise ValueError("Enter a valid email address")
    updated = {**current, "provider": provider, "host": host, "port": int(payload.get("port") or email_sync.PRESETS[provider]["port"]), "address": address,
               "enabled": bool(payload.get("enabled", current.get("enabled", False))), "last_error": None}
    if payload.get("password"):
        updated["secret"] = email_sync.protect(str(payload["password"]).replace(" ", "") if provider == "GMAIL" else str(payload["password"]))
    if updated["enabled"] and not (updated.get("secret") and address):
        raise ValueError("Add your email address and app password to turn on sync")
    DB.set_setting("email_sync", updated)
    return {"ok": True}


def sync_email(fetch: Callable[..., list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    from . import email_sync

    config = DB.setting("email_sync") or {}
    try:
        if not config.get("secret") or not config.get("address"):
            raise ValueError("Email sync isn't set up")
        password = email_sync.unprotect(config["secret"])
        messages = (fetch or email_sync.fetch_recent)(config, password)
        seen = {r["message_id"] for r in DB.rows("SELECT message_id FROM email_events")}
        apps = DB.rows("SELECT applications.id, applications.status, jobs.company, jobs.role FROM applications JOIN jobs ON jobs.id=applications.job_id")
        moved = 0
        for d in email_sync.decide(messages, apps, seen):
            app = d["application"]
            previous = None
            if d["action"] == "MOVE" and app:
                previous = DB.one("SELECT status FROM applications WHERE id=?", (app["id"],))["status"]
                stamp = now()
                DB.execute("UPDATE applications SET previous_status=?, status=?, status_note=?, updated_at=?, submitted_at=CASE WHEN ? IN ('APPLIED','INTERVIEWING','OFFER','REJECTED') THEN coalesce(submitted_at, ?) ELSE submitted_at END WHERE id=?",
                           (previous, d["target"], f"From email: {d['subject'][:120]}", stamp, d["target"], stamp, app["id"]))
                moved += 1
                label = {"INTERVIEWING": "Interview", "OFFER": "Offer", "REJECTED": "Rejection", "APPLIED": "Application received"}[d["target"]]
                notify("EMAIL", f"{label}: {app['company']}", d["subject"][:140], "Tracker")
            DB.execute("INSERT OR IGNORE INTO email_events(id,message_id,received_at,sender,subject,kind,application_id,action,previous_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (str(uuid.uuid4()), d["message_id"], d.get("date"), d["sender"][:200], d["subject"][:300], d["kind"], app["id"] if app else None, d["action"], previous, now()))
        DB.set_setting("email_sync", {**config, "last_sync": now(), "last_error": None})
        DB.log("EMAIL_SYNCED", details={"messages": len(messages), "moved": moved})
        return {"ok": True, "messages": len(messages), "moved": moved}
    except Exception as exc:
        DB.set_setting("email_sync", {**config, "last_sync": now(), "last_error": str(exc)[:300]})
        raise ValueError(f"Email sync failed: {exc}") from exc


def undo_email_move(event_id: str) -> dict[str, Any]:
    event = one("SELECT * FROM email_events WHERE id=? AND action='MOVE'", (event_id,))
    DB.execute("UPDATE applications SET status=?, status_note=NULL, updated_at=? WHERE id=?", (event["previous_status"], now(), event["application_id"]))
    DB.execute("UPDATE email_events SET action='UNDONE' WHERE id=?", (event_id,))
    return {"ok": True}


def email_events() -> list[dict[str, Any]]:
    return DB.rows("""SELECT email_events.*, jobs.company, jobs.role FROM email_events LEFT JOIN applications ON applications.id=email_events.application_id
        LEFT JOIN jobs ON jobs.id=applications.job_id ORDER BY email_events.created_at DESC LIMIT 60""")


# ---------- companies, referrals, prep ----------

def companies() -> list[dict[str, Any]]:
    jobs = decoded(DB.rows("SELECT jobs.id, company, role, duplicate_of, date_found, date_posted, e.score_json FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id"))
    apps = DB.rows("SELECT applications.status, jobs.company FROM applications JOIN jobs ON jobs.id=applications.job_id")
    watch = {insights.company_key(w["company"]): w for w in DB.rows("SELECT * FROM watchlist")}
    people = {}
    for c in DB.rows("SELECT company_key FROM connections"):
        people[c["company_key"]] = people.get(c["company_key"], 0) + 1
    notes = {n["company_key"] for n in DB.rows("SELECT company_key FROM company_notes WHERE notes != ''")}
    grouped: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key = insights.company_key(job.get("company"))
        if not key:
            continue
        g = grouped.setdefault(key, {"key": key, "name": job.get("company"), "jobs": 0, "best_score": 0, "applications": 0, "statuses": {}, "last_seen": "", "seasons": [0] * 12})
        if not job.get("duplicate_of"):
            g["jobs"] += 1
            stamp = job.get("date_posted") or job.get("date_found")
            if stamp and re.match(r"\d{4}-\d{2}", stamp):
                g["seasons"][int(stamp[5:7]) - 1] += 1  # when this company posts, for the card's hiring-season side
        g["best_score"] = max(g["best_score"], (job.get("score") or {}).get("score", 0))
        g["last_seen"] = max(g["last_seen"], job.get("date_found") or "")
    for key, w in watch.items():
        grouped.setdefault(key, {"key": key, "name": w["company"], "jobs": 0, "best_score": 0, "applications": 0, "statuses": {}, "last_seen": w.get("last_scanned_at") or "", "seasons": [0] * 12})
    for app in apps:
        key = insights.company_key(app["company"])
        if key in grouped:
            grouped[key]["applications"] += 1
            grouped[key]["statuses"][app["status"]] = grouped[key]["statuses"].get(app["status"], 0) + 1
    for key, g in grouped.items():
        g.update({"followed": key in watch, "platform": (watch.get(key) or {}).get("platform"), "watch_id": (watch.get(key) or {}).get("id"),
                  "connections": sum(n for k, n in people.items() if k == key or (len(key) >= 4 and (f" {key} " in f" {k} " or f" {k} " in f" {key} "))), "has_notes": key in notes})
    return sorted(grouped.values(), key=lambda g: (-g["applications"], -g["best_score"], g["name"] or ""))


def company_detail(key: str) -> dict[str, Any]:
    overview = next((c for c in companies() if c["key"] == key), None)
    if not overview:
        raise NotFound("Company not found")
    jobs = [j for j in decoded(DB.rows("""SELECT jobs.id, company, role, location, date_posted, date_found, deadline, posting_url, duplicate_of, e.result AS eligibility_result, e.score_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id ORDER BY date_found DESC""")) if insights.company_key(j.get("company")) == key]
    ids = {j["id"] for j in jobs}
    apps = [a for a in DB.rows("SELECT applications.id, applications.job_id, applications.status, applications.submitted_at, applications.updated_at, jobs.role FROM applications JOIN jobs ON jobs.id=applications.job_id") if a["job_id"] in ids]
    seasons = [0] * 12
    for j in jobs:
        stamp = j.get("date_posted") or j.get("date_found")
        if stamp:
            seasons[int(stamp[5:7]) - 1] += 1
    notes = DB.one("SELECT notes FROM company_notes WHERE company_key=?", (key,))
    return {**overview, "roles": jobs, "application_history": apps, "people": referrals.matches(overview["name"], DB.rows("SELECT * FROM connections")), "notes": notes["notes"] if notes else "", "seasons": seasons}


def save_company_notes(key: str, name: str, notes: str) -> dict[str, Any]:
    DB.execute("INSERT INTO company_notes(company_key,company,notes,updated_at) VALUES(?,?,?,?) ON CONFLICT(company_key) DO UPDATE SET notes=excluded.notes,updated_at=excluded.updated_at",
               (key, name, notes[:20_000], now()))
    return {"ok": True}


def import_connections(csv_text: str) -> dict[str, Any]:
    rows = referrals.parse_connections_csv(csv_text)
    DB.execute("DELETE FROM connections")
    for r in rows:
        DB.execute("INSERT INTO connections(id,first_name,last_name,url,email,company,company_key,position,connected_on,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), r["first_name"], r["last_name"], r["url"], r["email"], r["company"], r["company_key"], r["position"], r["connected_on"], now()))
    companies_known = {insights.company_key(j["company"]) for j in DB.rows("SELECT DISTINCT company FROM jobs")}
    matched = {r["company_key"] for r in rows if r["company_key"] in companies_known}
    DB.log("CONNECTIONS_IMPORTED", details={"connections": len(rows), "matched_companies": len(matched)})
    return {"connections": len(rows), "matched_companies": len(matched)}


def referral_message(job_id: str, connection_id: str) -> dict[str, Any]:
    job = one("SELECT company, role, posting_url FROM jobs WHERE id=?", (job_id,))
    person = one("SELECT * FROM connections WHERE id=?", (connection_id,))
    name = next((f["value"] for f in facts() if f["category"] == "personal" and f["fact_key"] == "full_name" and f.get("status") == "VERIFIED"), None)
    return {"message": referrals.referral_message(person, job, name), "url": person.get("url")}


def prep_pack(job_id: str) -> dict[str, Any]:
    from .prep import build_pack

    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    notes = DB.one("SELECT notes FROM company_notes WHERE company_key=?", (insights.company_key(job.get("company")),))
    pack = build_pack(job, facts(), notes["notes"] if notes else "")
    pack["people"] = referrals.matches(job.get("company"), DB.rows("SELECT * FROM connections"))[:5]
    return pack


# ---------- offers ----------

def offers_overview(base: str) -> dict[str, Any]:
    from .offers import CURRENCIES, compare, fetch_rates

    rows = decoded(DB.rows("SELECT * FROM offers ORDER BY created_at"))
    if not rows:
        return {"base": base, "rows": [], "currencies": CURRENCIES, "rates_source": None}
    rates = fetch_rates()
    return {"base": base, "rows": compare(rows, base, rates["rates"]), "currencies": CURRENCIES, "rates_source": rates.get("source"), "rates_updated": rates.get("updated")}


def save_offer(payload: dict[str, Any]) -> dict[str, Any]:
    from .offers import CURRENCIES

    company = str(payload.get("company") or "").strip()
    if not company:
        raise ValueError("Company is required")
    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        raise ValueError("Enter the stipend or salary as a number") from None
    if amount <= 0 or amount > 10_000_000:
        raise ValueError("Enter a realistic amount")
    currency = str(payload.get("currency") or "").upper()
    if currency not in CURRENCIES:
        raise ValueError("Choose a currency")
    period = str(payload.get("period") or "MONTH").upper()
    if period not in {"HOUR", "WEEK", "MONTH", "YEAR", "TOTAL"}:
        raise ValueError("Choose how the amount is paid")
    perks = {k: float(v) for k, v in (payload.get("perks") or {}).items() if str(v).strip() and re.fullmatch(r"[a-z_]{2,20}", k)}
    offer_id = payload.get("id") or str(uuid.uuid4())
    DB.execute("""INSERT INTO offers(id,application_id,company,role,location,amount,currency,period,hours_per_week,duration_months,perks_json,decision_deadline,notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET company=excluded.company,role=excluded.role,location=excluded.location,amount=excluded.amount,currency=excluded.currency,
        period=excluded.period,hours_per_week=excluded.hours_per_week,duration_months=excluded.duration_months,perks_json=excluded.perks_json,decision_deadline=excluded.decision_deadline,notes=excluded.notes,updated_at=excluded.updated_at""",
               (offer_id, payload.get("application_id"), company, str(payload.get("role") or ""), str(payload.get("location") or ""), amount, currency, period,
                float(payload.get("hours_per_week") or 40), float(payload.get("duration_months") or 3), json.dumps(perks), payload.get("decision_deadline") or None, str(payload.get("notes") or ""), now(), now()))
    return {"id": offer_id}


# ---------- calendar, insights, search ----------

def calendar() -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for j in DB.rows("SELECT id, company, role, date_posted, deadline FROM jobs WHERE duplicate_of IS NULL"):
        if j.get("date_posted"):
            events.append({"date": j["date_posted"][:10], "kind": "POSTED", "title": f"{j['company']} opened {j['role']}", "job_id": j["id"]})
        if j.get("deadline"):
            events.append({"date": j["deadline"][:10], "kind": "DEADLINE", "title": f"{j['company']} closes {j['role']}", "job_id": j["id"]})
    for a in DB.rows("SELECT applications.job_id, applications.submitted_at, jobs.company, jobs.role FROM applications JOIN jobs ON jobs.id=applications.job_id WHERE submitted_at IS NOT NULL"):
        events.append({"date": a["submitted_at"][:10], "kind": "APPLIED", "title": f"Applied to {a['company']}", "job_id": a["job_id"]})
    for log in DB.rows("SELECT timestamp, entity_id, details_json FROM activity_log WHERE action='APPLICATION_STATUS_CHANGED' AND details_json LIKE '%INTERVIEWING%'"):
        job = DB.one("SELECT jobs.id, company FROM applications JOIN jobs ON jobs.id=applications.job_id WHERE applications.id=?", (log["entity_id"],))
        if job:
            events.append({"date": log["timestamp"][:10], "kind": "INTERVIEW", "title": f"Interview stage at {job['company']}", "job_id": job["id"]})
    seasons = []
    for w in DB.rows("SELECT company FROM watchlist ORDER BY company"):
        key = insights.company_key(w["company"])
        months = [0] * 12
        for j in DB.rows("SELECT company, date_posted, date_found FROM jobs"):
            if insights.company_key(j["company"]) == key:
                stamp = j.get("date_posted") or j.get("date_found")
                if stamp:
                    months[int(stamp[5:7]) - 1] += 1
        seasons.append({"company": w["company"], "months": months})
    return {"events": sorted(events, key=lambda e: e["date"]), "seasons": seasons}


def insights_overview() -> dict[str, Any]:
    jobs = decoded(DB.rows("""SELECT jobs.*, e.result AS eligibility_result, e.checks_json AS eligibility_checks_json, e.match_json AS eligibility_match_json
        FROM jobs JOIN eligibility_results e ON e.job_id=jobs.id WHERE jobs.duplicate_of IS NULL"""))
    return {"coach": insights.coach(jobs, facts(), AUTOPILOT.config()["min_score"])}


def search_jobs(query: str) -> dict[str, Any]:
    jobs = decoded(DB.rows("""SELECT jobs.id, company, role, location, country, description, required_skills_json, preferred_skills_json, duplicate_of, application_platform, e.score_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id"""))
    result = insights.search(jobs, query)
    config = ai_config()
    if result["ids"] and ai.status(config).get("available"):
        try:  # optional semantic re-rank with a local embedding model
            top = {j["id"]: j for j in jobs if j["id"] in set(result["ids"][:60])}
            order = [i for i in result["ids"][:60]]
            vectors = ai.embed(config, [query] + [f"{top[i]['role']} at {top[i]['company']}. {(top[i].get('description') or '')[:600]}" for i in order])
            if vectors:
                q = vectors[0]
                norm = lambda v: sum(x * x for x in v) ** 0.5 or 1.0  # noqa: E731
                sims = {i: sum(a * b for a, b in zip(q, v)) / (norm(q) * norm(v)) for i, v in zip(order, vectors[1:])}
                result["ids"] = sorted(order, key=lambda i: -sims[i]) + result["ids"][60:]
                result["semantic"] = True
        except Exception:
            pass
    return result


# ---------- tailored CVs ----------

def _verified_skills() -> list[str]:
    for f in facts():
        if f["category"] == "skills" and f.get("status") == "VERIFIED" and isinstance(f.get("value"), list):
            return [str(v) for v in f["value"]]
    return []


def _source_cv_text(draft: dict[str, Any]) -> str:
    source_id = str(draft.get("question") or "").removeprefix("cv:")
    cv = one("SELECT path FROM cvs WHERE id=?", (source_id,))
    return cv_tailor.cv_text(cv["path"])


def tailor_cv(job_id: str, use_ai: bool) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    cv = approved_cv()
    if not cv:
        raise ValueError("Approve a CV in the CV Library first")
    original = cv_tailor.cv_text(cv["path"])
    if len(original) < 200:
        raise ValueError("ApplyPilot couldn't read enough text from your CV PDF (is it a scanned image?)")
    if use_ai:
        result = ai.tailor_cv(ai_config(), original, job)
        tailored, model = result["content"], result["model"]
    else:
        tailored, model = cv_tailor.tailor_deterministic(original, job), "ApplyPilot"
    draft_id = str(uuid.uuid4())
    DB.execute("INSERT INTO drafts(id,kind,job_id,question,content,status,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
               (draft_id, "CV_TAILORED", job_id, f"cv:{cv['id']}", tailored, "DRAFT", model, now(), now()))
    return {"id": draft_id, "original": original, "content": tailored, "model": model, "flags": cv_tailor.invention_flags(original, tailored, _verified_skills())}


def tailored_diff(draft_id: str) -> dict[str, Any]:
    draft = one("SELECT drafts.*, jobs.company, jobs.role FROM drafts LEFT JOIN jobs ON jobs.id=drafts.job_id WHERE drafts.id=? AND kind='CV_TAILORED'", (draft_id,))
    original = _source_cv_text(draft)
    return {**draft, "original": original, "flags": cv_tailor.invention_flags(original, draft["content"], _verified_skills())}


def finalize_tailored_cv(draft: dict[str, Any]) -> dict[str, Any]:
    from .browser_runner import find_edge

    source_id = str(draft.get("question") or "").removeprefix("cv:")
    source = one("SELECT * FROM cvs WHERE id=?", (source_id,))
    job = one("SELECT company, role FROM jobs WHERE id=?", (draft["job_id"],))
    edge = find_edge()
    if not edge:
        raise ValueError("Microsoft Edge is needed to create the PDF")
    cv_id = str(uuid.uuid4())
    path = DB.path.parent / "uploads" / "cvs" / f"{cv_id}.pdf"
    cv_tailor.render_pdf(draft["content"], f"CV — {job['company']}", path, edge)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    version = (DB.one("SELECT MAX(version) AS v FROM cvs WHERE id=? OR original_id=?", (source["original_id"] or source_id, source["original_id"] or source_id))["v"] or 1) + 1
    name = f"{Path(source['name']).stem} — {job['company']}.pdf"
    DB.execute("INSERT INTO cvs(id,name,variant,original_id,version,path,sha256,is_original,approved,extracted_profile_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (cv_id, name, f"Tailored for {job['company']} · {job['role']}", source["original_id"] or source_id, version, str(path), digest, 0, 1, "{}", now()))
    DB.execute("UPDATE applications SET cv_id=?, updated_at=? WHERE job_id=? AND status IN ('QUEUED','NEEDS_INFO','WAITING_FOR_USER','READY_FOR_REVIEW')", (cv_id, now(), draft["job_id"]))
    reprepare_active()
    DB.log("CV_TAILORED", "cv", cv_id, {"job": job["company"], "version": version})
    return {"id": cv_id, "name": name}
