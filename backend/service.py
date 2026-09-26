"""Application services shared by the HTTP API and Autopilot. All state lives in the local SQLite database."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__, ai, discovery
from .automation import COUNTRY_SCOPED, FACT_MAPPING, dry_run, field_definitions
from .cv_extract import extract as extract_cv
from .database import Database, now
from .eligibility import evaluate, extract_skills
from .job_parser import requirement_sentences
from .safety import classify_field, normalize
from .scoring import job_country, location_match, preferred_locations, score

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


def notify(kind: str, title: str, body: str = "", page: str | None = None) -> None:
    DB.execute("INSERT INTO notifications(created_at,kind,title,body,page) VALUES(?,?,?,?,?)", (now(), kind, title, body, page))


# ---------- jobs ----------

JOB_COLUMNS = ["id", "company", "role", "location", "country", "remote_status", "posting_url", "application_url", "source", "date_found", "date_posted", "deadline", "description",
               "required_skills_json", "preferred_skills_json", "degree_requirements", "graduation_requirements", "experience_requirements", "work_authorization", "sponsorship_information",
               "duration", "start_date", "compensation", "application_platform", "requisition_id", "raw_snapshot", "extraction_status", "external_id", "board_questions_json", "employment_type"]


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
    return job


def analyze_job(job_id: str, fact_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    job = one("SELECT * FROM jobs WHERE id=?", (job_id,))
    fact_rows = fact_rows if fact_rows is not None else facts()
    result = evaluate(job, fact_rows)
    result["score"] = score(job, result, preferred_locations(fact_rows))
    DB.execute("""INSERT INTO eligibility_results(id,job_id,result,checks_json,match_json,score_json,evaluated_at) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(job_id) DO UPDATE SET result=excluded.result,checks_json=excluded.checks_json,match_json=excluded.match_json,score_json=excluded.score_json,evaluated_at=excluded.evaluated_at""",
               (str(uuid.uuid4()), job_id, result["result"], json.dumps(result["checks"]), json.dumps(result["match"]), json.dumps(result["score"]), now()))
    DB.log("ELIGIBILITY_ANALYZED", "job", job_id, {"result": result["result"], "score": result["score"]["score"]})
    return result


def analyze_all() -> int:
    fact_rows = facts()
    ids = [r["id"] for r in DB.rows("SELECT id FROM jobs")]
    for job_id in ids:
        analyze_job(job_id, fact_rows)
    return len(ids)


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
            kind = _question_kind(f.get("classification", "UNKNOWN"))
            key = normalize(f["label"]) + (f"|{app.get('country') or ''}" if kind == "COUNTRY_FACT" else "")
            group = groups.setdefault(key, {"key": key, "question": f["label"], "classification": f.get("classification"), "kind": kind, "options": f.get("options") or [],
                                            "required": False, "reason": f["decision"].get("reason"), "country": app.get("country") if kind == "COUNTRY_FACT" else None, "applications": []})
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
    classification = payload.get("classification") or classify_field(question)
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
    return {"ok": True}


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
    DB.execute("UPDATE drafts SET content=?,status=?,updated_at=? WHERE id=?", (text, "APPROVED" if approve else "DRAFT", now(), draft_id))
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
            while not self._stop.wait(30):
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

    def execute(self, run_id: str, fetch: Callable[..., dict[str, Any]] | None = None) -> None:
        fetch = fetch or discovery.fetch_board
        events: list[dict[str, Any]] = []
        summary = {"boards": 0, "found": 0, "new": 0, "filtered": 0, "analyzed": 0, "queued": 0, "prepared": 0, "ready": 0, "needs_you": 0, "summaries": 0, "letters": 0}

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
                    WHERE e.result IN ('ELIGIBLE','LIKELY_ELIGIBLE') AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id=jobs.id)""")
                for c in sorted(candidates, key=lambda r: -json.loads(r["score_json"] or "{}").get("score", 0)):
                    s = json.loads(c["score_json"] or "{}")
                    if s.get("score", 0) < cfg["min_score"] or (cfg["internships_only"] and not s.get("is_internship")):
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

def bootstrap() -> dict[str, Any]:
    settings = {r["key"]: json.loads(r["value_json"]) for r in DB.rows("SELECT * FROM settings")}
    jobs = decoded(DB.rows("""SELECT jobs.id,company,role,location,country,remote_status,posting_url,application_url,source,date_found,date_posted,deadline,compensation,employment_type,
        substr(description,1,700) AS description,required_skills_json,preferred_skills_json,work_authorization,sponsorship_information,application_platform,extraction_status,ai_summary_json,
        CASE WHEN board_questions_json IS NULL THEN 0 ELSE json_array_length(board_questions_json) END AS question_count,
        e.result AS eligibility_result,e.checks_json AS eligibility_checks_json,e.match_json AS eligibility_match_json,e.score_json AS score_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id ORDER BY date_found DESC"""))
    apps = decoded(DB.rows("""SELECT applications.*,jobs.company,jobs.role,jobs.location,jobs.country,jobs.posting_url,jobs.application_url,cvs.name AS cv_name
        FROM applications JOIN jobs ON jobs.id=applications.job_id LEFT JOIN cvs ON cvs.id=applications.cv_id ORDER BY applications.updated_at DESC"""))
    cvs = decoded(DB.rows("SELECT id,name,variant,version,sha256,approved,extracted_profile_json,created_at FROM cvs ORDER BY created_at DESC"))
    for cv in cvs:
        cv["approved"] = bool(cv["approved"])
    box = inbox()
    return {
        "version": __version__, "settings": settings,
        "facts": decoded(DB.rows("SELECT * FROM profile_facts ORDER BY category,fact_key")),
        "jobs": jobs, "applications": apps, "cvs": cvs,
        "activity": decoded(DB.rows("SELECT * FROM activity_log ORDER BY id DESC LIMIT 200")),
        "answers": decoded(DB.rows("SELECT * FROM answer_vault ORDER BY updated_at DESC")),
        "watchlist": DB.rows("SELECT * FROM watchlist ORDER BY company"), "catalog": discovery.CATALOG,
        "inbox": box, "autopilot": autopilot_state(),
        "notifications": DB.rows("SELECT * FROM notifications ORDER BY id DESC LIMIT 30"),
    }
