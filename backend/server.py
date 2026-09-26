from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .automation import dry_run, pre_submission_validate
from .database import ROOT, Database, now
from .eligibility import evaluate, extract_skills
from .job_parser import import_url, requirement_sentences

DB = Database()
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
DEV_ORIGIN = "http://localhost:1420"
TRACKER_STATUSES = {"QUEUED", "NEEDS_INFO", "WAITING_FOR_USER", "READY_FOR_REVIEW", "APPLIED", "INTERVIEWING", "OFFER", "REJECTED", "WITHDRAWN"}
DELETABLE = {"profile/facts": "profile_facts", "answers": "answer_vault", "jobs": "jobs", "applications": "applications"}
# The Windows registry can map .js to text/plain, which browsers refuse to execute as a module.
for _type, _ext in (("text/javascript", ".js"), ("text/css", ".css"), ("image/svg+xml", ".svg"), ("image/x-icon", ".ico"), ("image/png", ".png"), ("font/woff2", ".woff2")):
    mimetypes.add_type(_type, _ext)
CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"


def static_dir() -> Path | None:
    """Built UI served alongside the API. Packaged builds carry it inside the bundle."""
    if os.environ.get("APPLYPILOT_STATIC"):
        candidate = Path(os.environ["APPLYPILOT_STATIC"])
    elif getattr(sys, "frozen", False):
        candidate = Path(getattr(sys, "_MEIPASS", ROOT)) / "dist"
    else:
        candidate = ROOT / "dist"
    return candidate if (candidate / "index.html").is_file() else None


def decoded(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        for key in list(row):
            if key.endswith("_json"):
                try:
                    row[key[:-5]] = json.loads(row[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        if "dry_run" in row:
            row["dry_run"] = bool(row["dry_run"])
    return rows


def save_job(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("description") and not payload.get("required_skills") and not payload.get("preferred_skills"):
        payload["required_skills"], payload["preferred_skills"] = extract_skills(payload["description"])
    if payload.get("description"):
        for key, sentence in requirement_sentences(payload["description"]).items():
            payload.setdefault(key, sentence)
    job_id = payload.get("id") or str(uuid.uuid4())
    columns = ["id","company","role","location","country","remote_status","posting_url","application_url","source","date_found","date_posted","deadline","description","required_skills_json","preferred_skills_json","degree_requirements","graduation_requirements","experience_requirements","work_authorization","sponsorship_information","duration","start_date","compensation","application_platform","requisition_id","raw_snapshot","extraction_status"]
    values = {
        **payload, "id": job_id, "date_found": payload.get("date_found", now()),
        "source": payload.get("source", "MANUAL"), "description": payload.get("description") or "",
        "required_skills_json": json.dumps(payload.get("required_skills", [])),
        "preferred_skills_json": json.dumps(payload.get("preferred_skills", [])),
        "raw_snapshot": payload.get("raw_snapshot", ""), "extraction_status": payload.get("extraction_status", "UNVERIFIED"),
    }
    placeholders = ",".join("?" for _ in columns)
    updates = ",".join(f"{c}=excluded.{c}" for c in columns if c != "id")
    DB.execute(f"INSERT INTO jobs({','.join(columns)}) VALUES({placeholders}) ON CONFLICT(posting_url) DO UPDATE SET {updates}", tuple(values.get(c) for c in columns))
    row = DB.one("SELECT * FROM jobs WHERE posting_url=? OR id=? LIMIT 1", (payload.get("posting_url"), job_id))
    DB.log("JOB_IMPORTED", "job", row["id"] if row else job_id, {"source": payload.get("source")})
    return decoded([row or {}])[0]


def bootstrap() -> dict[str, Any]:
    settings = {r["key"]: json.loads(r["value_json"]) for r in DB.rows("SELECT * FROM settings")}
    facts = decoded(DB.rows("SELECT * FROM profile_facts ORDER BY category,fact_key"))
    jobs = decoded(DB.rows("""SELECT jobs.id,company,role,location,country,remote_status,posting_url,application_url,source,date_found,date_posted,deadline,
        description,required_skills_json,preferred_skills_json,work_authorization,sponsorship_information,application_platform,extraction_status,
        e.result AS eligibility_result,e.checks_json AS eligibility_checks_json,e.match_json AS eligibility_match_json
        FROM jobs LEFT JOIN eligibility_results e ON e.job_id=jobs.id ORDER BY date_found DESC"""))
    apps = decoded(DB.rows("""SELECT applications.*,jobs.company,jobs.role,jobs.location,jobs.country,jobs.posting_url,cvs.name AS cv_name
        FROM applications JOIN jobs ON jobs.id=applications.job_id LEFT JOIN cvs ON cvs.id=applications.cv_id ORDER BY applications.updated_at DESC"""))
    activity = decoded(DB.rows("SELECT * FROM activity_log ORDER BY id DESC LIMIT 200"))
    cvs = decoded(DB.rows("SELECT id,name,variant,version,sha256,approved,extracted_profile_json,created_at FROM cvs ORDER BY created_at DESC"))
    for cv in cvs:
        cv["approved"] = bool(cv["approved"])
    answers = decoded(DB.rows("SELECT * FROM answer_vault ORDER BY updated_at DESC"))
    return {"version": __version__, "settings": settings, "facts": facts, "jobs": jobs, "applications": apps, "activity": activity, "cvs": cvs, "answers": answers}


class Handler(BaseHTTPRequestHandler):
    server_version = f"ApplyPilotLocal/{__version__}"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("APPLYPILOT_HTTP_LOG") == "1":
            super().log_message(fmt, *args)

    def _json(self, status: int, value: Any) -> None:
        data = json.dumps(value, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("Origin") == DEV_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", DEV_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _trusted(self) -> bool:
        """Only this app's own pages may call the service: blocks DNS rebinding and cross-site requests."""
        host_header = self.headers.get("Host") or ""
        if urlparse(f"//{host_header}").hostname not in LOCAL_HOSTS:
            return False
        origin = self.headers.get("Origin")
        if origin and origin != DEV_ORIGIN and urlparse(origin).netloc != host_header:
            return False
        if self.command in {"POST", "DELETE"} and not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return False
        return True

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 8_000_000:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def _static(self, path: str) -> None:
        root = static_dir()
        if root is None:
            return self._json(404, {"error": "UI not built. Run `npm run build`, or use `npm run dev` on port 1420."})
        target = (root / path.lstrip("/")).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            target = root / "index.html"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if target.name == "index.html" else "public, max-age=31536000, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        if self.headers.get("Origin") != DEV_ORIGIN:
            return self._json(403, {"error": "Forbidden"})
        self._json(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not self._trusted():
            return self._json(403, {"error": "Forbidden"})
        if not (path.startswith("/api/") or path == "/health"):
            return self._static(path)
        try:
            if path == "/health":
                return self._json(200, {"status": "ok", "version": __version__, "database": str(DB.path), "strict": DB.setting("strict_accuracy_mode")})
            if path == "/api/bootstrap":
                return self._json(200, bootstrap())
            return self._json(404, {"error": "Not found"})
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._trusted():
            return self._json(403, {"error": "Forbidden"})
        try:
            body = self._body()
            if path == "/api/profile/facts":
                return self._json(200, decoded([DB.upsert_fact(body)])[0])
            if path == "/api/answers":
                answer_type = body.get("answer_type", "MANUAL_ONLY")
                allowed_types = {"EXACT","COUNTRY_SPECIFIC","COMPANY_SPECIFIC","ROLE_SPECIFIC","GENERATED_WITH_APPROVAL","MANUAL_ONLY"}
                if answer_type not in allowed_types:
                    raise ValueError("Invalid answer type")
                question = str(body["canonical_question"]).strip()
                if not question:
                    raise ValueError("Question is required")
                answer_id = str(uuid.uuid4())
                status = "VERIFIED" if body.get("approved") is True else "UNVERIFIED"
                DB.execute("INSERT INTO answer_vault(id,canonical_question,normalized_pattern,answer_type,answer_json,country_code,company,role_pattern,status,source_fact_ids_json,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (answer_id, question, " ".join(question.lower().split()), answer_type, json.dumps(body.get("answer")), body.get("country_code") or None, body.get("company") or None, body.get("role_pattern") or None, status, json.dumps(body.get("source_fact_ids", [])), now() if status == "VERIFIED" else None, now()))
                DB.log("ANSWER_VAULT_SAVED", "answer", answer_id, {"type": answer_type, "status": status})
                return self._json(201, {"id": answer_id, "status": status})
            match = re.fullmatch(r"/api/answers/([^/]+)/approve", path)
            if match:
                if not DB.one("SELECT id FROM answer_vault WHERE id=?", (match.group(1),)):
                    return self._json(404, {"error": "Answer not found"})
                DB.execute("UPDATE answer_vault SET status='VERIFIED',approved_at=?,updated_at=? WHERE id=?", (now(), now(), match.group(1)))
                DB.log("ANSWER_VAULT_APPROVED", "answer", match.group(1))
                return self._json(200, {"id": match.group(1), "status": "VERIFIED"})
            if path == "/api/settings":
                allowed = {"strict_accuracy_mode", "dry_run", "actual_submission_enabled", "automation_mode", "ollama", "first_run_complete"}
                for key, value in body.items():
                    if key in allowed:
                        DB.set_setting(key, value)
                DB.log("SETTINGS_UPDATED", details={"keys": list(body)})
                return self._json(200, {"ok": True})
            if path == "/api/jobs/import":
                return self._json(201, save_job(import_url(str(body["url"]))))
            if path == "/api/jobs/manual":
                body = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in body.items()}
                if not body.get("company") or not body.get("role"):
                    raise ValueError("Company and role are required")
                body.update({"source": "MANUAL", "extraction_status": "USER_ENTERED", "application_url": body.get("application_url") or body.get("posting_url")})
                return self._json(201, save_job(body))
            if path == "/api/cvs/import":
                filename = Path(body.get("filename", "resume.pdf")).name
                if not filename.lower().endswith(".pdf"):
                    raise ValueError("Only PDF CVs are accepted")
                raw = base64.b64decode(body["content_base64"], validate=True)
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
                try:
                    from pypdf import PdfReader
                    text = "\n".join(page.extract_text() or "" for page in PdfReader(stored).pages)[:100_000]
                    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
                    skills, preferred = extract_skills(text)
                    extracted.update({"email_candidates": emails[:3], "skill_candidates": sorted(set(skills + preferred)), "text_length": len(text)})
                except Exception:
                    extracted["extraction_error"] = "Text extraction unavailable; original remains imported."
                DB.execute("INSERT INTO cvs(id,name,variant,version,path,sha256,is_original,approved,extracted_profile_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (cv_id, filename, body.get("variant") or "General Software Engineering", 1, str(stored), digest, 1, 0, json.dumps(extracted), now()))
                DB.log("CV_IMPORTED_UNVERIFIED", "cv", cv_id, {"name": filename, "sha256": digest})
                return self._json(201, {"id": cv_id, "name": filename, "approved": False, "extracted_profile": extracted})
            match = re.fullmatch(r"/api/cvs/([^/]+)/approve", path)
            if match:
                if not DB.one("SELECT id FROM cvs WHERE id=?", (match.group(1),)):
                    return self._json(404, {"error": "CV not found"})
                approved = body.get("approved", True) is True
                DB.execute("UPDATE cvs SET approved=? WHERE id=?", (int(approved), match.group(1)))
                if approved:
                    DB.execute("UPDATE applications SET cv_id=?,updated_at=? WHERE cv_id IS NULL AND status IN ('QUEUED','NEEDS_INFO','WAITING_FOR_USER','READY_FOR_REVIEW')", (match.group(1), now()))
                DB.log("CV_APPROVED" if approved else "CV_UNAPPROVED", "cv", match.group(1))
                return self._json(200, {"id": match.group(1), "approved": approved})
            match = re.fullmatch(r"/api/jobs/([^/]+)/analyze", path)
            if match:
                job = decoded([DB.one("SELECT * FROM jobs WHERE id=?", (match.group(1),)) or {}])[0]
                if not job:
                    return self._json(404, {"error": "Job not found"})
                result = evaluate(job, decoded(DB.rows("SELECT * FROM profile_facts")))
                result_id = str(uuid.uuid4())
                DB.execute("INSERT INTO eligibility_results(id,job_id,result,checks_json,match_json,evaluated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET result=excluded.result,checks_json=excluded.checks_json,match_json=excluded.match_json,evaluated_at=excluded.evaluated_at", (result_id, job["id"], result["result"], json.dumps(result["checks"]), json.dumps(result["match"]), now()))
                DB.log("ELIGIBILITY_ANALYZED", "job", job["id"], {"result": result["result"]})
                return self._json(200, result)
            match = re.fullmatch(r"/api/jobs/([^/]+)/queue", path)
            if match:
                if not DB.one("SELECT id FROM jobs WHERE id=?", (match.group(1),)):
                    return self._json(404, {"error": "Job not found"})
                duplicate = DB.one("""SELECT a.id FROM applications a
                    JOIN jobs existing ON existing.id=a.job_id
                    JOIN jobs candidate ON candidate.id=?
                    WHERE existing.id=candidate.id
                       OR (existing.application_url IS NOT NULL AND existing.application_url=candidate.application_url)
                       OR (existing.requisition_id IS NOT NULL AND existing.company=candidate.company AND existing.requisition_id=candidate.requisition_id)
                       OR (lower(existing.company)=lower(candidate.company) AND lower(existing.role)=lower(candidate.role) AND coalesce(existing.location,'')=coalesce(candidate.location,''))
                    LIMIT 1""", (match.group(1),))
                if duplicate:
                    return self._json(409, {"error": "You may already have applied to this role.", "application_id": duplicate["id"]})
                cv = DB.one("SELECT id FROM cvs WHERE id=? AND approved=1", (body["cv_id"],)) if body.get("cv_id") else DB.one("SELECT id FROM cvs WHERE approved=1 ORDER BY created_at DESC LIMIT 1")
                app_id = str(uuid.uuid4())
                DB.execute("INSERT INTO applications(id,job_id,status,mode,dry_run,cv_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (app_id, match.group(1), "QUEUED", DB.setting("automation_mode"), int(bool(DB.setting("dry_run"))), cv["id"] if cv else None, now(), now()))
                DB.log("APPLICATION_QUEUED", "application", app_id)
                return self._json(201, {"id": app_id, "status": "QUEUED"})
            match = re.fullmatch(r"/api/applications/([^/]+)/dry-run", path)
            if match:
                app = DB.one("SELECT applications.*,jobs.country FROM applications JOIN jobs ON jobs.id=applications.job_id WHERE applications.id=?", (match.group(1),))
                if not app:
                    return self._json(404, {"error": "Application not found"})
                result = dry_run(body.get("fields", []), decoded(DB.rows("SELECT * FROM profile_facts")), app.get("country"), decoded(DB.rows("SELECT * FROM answer_vault")))
                DB.execute("UPDATE applications SET status=?,field_state_json=?,automation_checkpoint_json=?,updated_at=? WHERE id=?", (result["status"], json.dumps(result["fields"]), json.dumps({"run_id": result["run_id"]}), now(), app["id"]))
                DB.log("DRY_RUN_COMPLETED", "application", app["id"], {"filled": result["filled_count"], "unknown": result["unknown_count"]})
                return self._json(200, result)
            match = re.fullmatch(r"/api/applications/([^/]+)/status", path)
            if match:
                status = body.get("status")
                if status not in TRACKER_STATUSES:
                    raise ValueError("Invalid application status")
                if not DB.one("SELECT id FROM applications WHERE id=?", (match.group(1),)):
                    return self._json(404, {"error": "Application not found"})
                stamp = now()
                DB.execute("UPDATE applications SET status=?,updated_at=?,submitted_at=CASE WHEN ?='APPLIED' THEN coalesce(submitted_at,?) ELSE submitted_at END WHERE id=?", (status, stamp, status, stamp, match.group(1)))
                DB.log("APPLICATION_STATUS_CHANGED", "application", match.group(1), {"status": status})
                return self._json(200, {"id": match.group(1), "status": status})
            match = re.fullmatch(r"/api/applications/([^/]+)/validate", path)
            if match:
                app = DB.one("SELECT * FROM applications WHERE id=?", (match.group(1),))
                if not app:
                    return self._json(404, {"error": "Application not found"})
                fields = json.loads(app.get("field_state_json") or "[]")
                settings = {"dry_run": DB.setting("dry_run"), "actual_submission_enabled": DB.setting("actual_submission_enabled")}
                result = pre_submission_validate(app, fields, settings=settings)
                DB.log("APPLICATION_VALIDATED", "application", match.group(1), result, "WARN" if result["blocked"] else "INFO")
                return self._json(200, result)
            return self._json(404, {"error": "Not found"})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:
            DB.log("FAILED_SAFELY", details={"path": path, "error": str(exc)}, level="ERROR")
            return self._json(500, {"error": str(exc)})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not self._trusted():
            return self._json(403, {"error": "Forbidden"})
        try:
            match = re.fullmatch(r"/api/(profile/facts|answers|jobs|applications)/([^/]+)", path)
            if not match:
                return self._json(404, {"error": "Not found"})
            kind, item_id = match.groups()
            table = DELETABLE[kind]
            if not DB.one(f"SELECT id FROM {table} WHERE id=?", (item_id,)):
                return self._json(404, {"error": "Not found"})
            if kind == "jobs" and DB.one("SELECT id FROM applications WHERE job_id=?", (item_id,)):
                raise ValueError("Remove this job's application from the tracker first")
            if kind == "jobs":
                DB.execute("DELETE FROM eligibility_results WHERE job_id=?", (item_id,))
            if kind == "applications":
                DB.execute("DELETE FROM receipts WHERE application_id=?", (item_id,))
            DB.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            DB.log(f"{table.upper()}_DELETED", table, item_id)
            return self._json(200, {"ok": True})
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:
            DB.log("FAILED_SAFELY", details={"path": path, "error": str(exc)}, level="ERROR")
            return self._json(500, {"error": str(exc)})


def create_server(host: str = "127.0.0.1", port: int = 4817) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve(host: str = "127.0.0.1", port: int = 4817) -> None:
    server = create_server(host, port)
    ui = " (serving built UI)" if static_dir() else ""
    print(f"ApplyPilot local service: http://{host}:{server.server_port}{ui}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve(port=int(os.environ.get("APPLYPILOT_PORT", "4817")))
