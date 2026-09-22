from __future__ import annotations

import json
import os
import re
import threading
import uuid
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .automation import dry_run, pre_submission_validate
from .database import Database, now
from .eligibility import evaluate
from .job_parser import import_url

DB = Database()


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
    job_id = payload.get("id") or str(uuid.uuid4())
    columns = ["id","company","role","location","country","remote_status","posting_url","application_url","source","date_found","date_posted","deadline","description","required_skills_json","preferred_skills_json","degree_requirements","graduation_requirements","experience_requirements","work_authorization","sponsorship_information","duration","start_date","compensation","application_platform","requisition_id","raw_snapshot","extraction_status"]
    values = {
        **payload, "id": job_id, "date_found": payload.get("date_found", now()),
        "source": payload.get("source", "MANUAL"), "description": payload.get("description", ""),
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


class Handler(BaseHTTPRequestHandler):
    server_version = "ApplyPilotLocal/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("APPLYPILOT_HTTP_LOG") == "1":
            super().log_message(fmt, *args)

    def _json(self, status: int, value: Any) -> None:
        data = json.dumps(value, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:1420")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self) -> None:
        self._json(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/health":
                return self._json(200, {"status": "ok", "database": str(DB.path), "strict": DB.setting("strict_accuracy_mode")})
            if path == "/api/bootstrap":
                settings = {r["key"]: json.loads(r["value_json"]) for r in DB.rows("SELECT * FROM settings")}
                facts = decoded(DB.rows("SELECT * FROM profile_facts ORDER BY category,fact_key"))
                jobs = decoded(DB.rows("SELECT * FROM jobs ORDER BY date_found DESC"))
                apps = decoded(DB.rows("SELECT applications.*,jobs.company,jobs.role,jobs.location FROM applications JOIN jobs ON jobs.id=applications.job_id ORDER BY applications.updated_at DESC"))
                activity = decoded(DB.rows("SELECT * FROM activity_log ORDER BY id DESC LIMIT 30"))
                cvs = decoded(DB.rows("SELECT * FROM cvs ORDER BY created_at DESC"))
                answers = decoded(DB.rows("SELECT * FROM answer_vault ORDER BY updated_at DESC"))
                return self._json(200, {"settings": settings, "facts": facts, "jobs": jobs, "applications": apps, "activity": activity, "cvs": cvs, "answers": answers})
            return self._json(404, {"error": "Not found"})
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
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
                DB.execute("INSERT INTO answer_vault(id,canonical_question,normalized_pattern,answer_type,answer_json,country_code,company,role_pattern,status,source_fact_ids_json,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (answer_id, question, " ".join(question.lower().split()), answer_type, json.dumps(body.get("answer")), body.get("country_code"), body.get("company"), body.get("role_pattern"), status, json.dumps(body.get("source_fact_ids", [])), now() if status == "VERIFIED" else None, now()))
                DB.log("ANSWER_VAULT_SAVED", "answer", answer_id, {"type": answer_type, "status": status})
                return self._json(201, {"id": answer_id, "status": status})
            if path == "/api/settings":
                allowed = {"strict_accuracy_mode", "dry_run", "actual_submission_enabled", "automation_mode", "ollama", "first_run_complete"}
                for key, value in body.items():
                    if key in allowed:
                        DB.set_setting(key, value)
                DB.log("SETTINGS_UPDATED", details={"keys": list(body)})
                return self._json(200, {"ok": True})
            if path == "/api/jobs/import":
                return self._json(201, save_job(import_url(body["url"])))
            if path == "/api/cvs/import":
                filename = Path(body.get("filename", "resume.pdf")).name
                if not filename.lower().endswith(".pdf"):
                    raise ValueError("Only PDF CVs are accepted")
                raw = base64.b64decode(body["content_base64"], validate=True)
                if len(raw) > 5_000_000 or not raw.startswith(b"%PDF"):
                    raise ValueError("Invalid PDF or file exceeds 5 MB")
                digest = hashlib.sha256(raw).hexdigest()
                cv_id = str(uuid.uuid4())
                upload_dir = DB.path.parent / "uploads" / "cvs"
                upload_dir.mkdir(parents=True, exist_ok=True)
                stored = upload_dir / f"{cv_id}.pdf"
                stored.write_bytes(raw)
                extracted = {"notice": "CV-derived facts are suggestions and remain unverified."}
                try:
                    from pypdf import PdfReader
                    text = "\n".join(page.extract_text() or "" for page in PdfReader(stored).pages)[:100_000]
                    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
                    extracted.update({"email_candidates": emails[:3], "text_length": len(text)})
                except Exception:
                    extracted["extraction_error"] = "Text extraction unavailable; original remains imported."
                DB.execute("INSERT INTO cvs(id,name,variant,version,path,sha256,is_original,approved,extracted_profile_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (cv_id, filename, body.get("variant", "General Software Engineering"), 1, str(stored), digest, 1, 0, json.dumps(extracted), now()))
                DB.log("CV_IMPORTED_UNVERIFIED", "cv", cv_id, {"name": filename, "sha256": digest})
                return self._json(201, {"id": cv_id, "name": filename, "approved": False, "extracted_profile": extracted})
            if path == "/api/jobs/manual":
                return self._json(201, save_job(body))
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
                app_id = str(uuid.uuid4())
                DB.execute("INSERT INTO applications(id,job_id,status,mode,dry_run,cv_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (app_id, match.group(1), "QUEUED", DB.setting("automation_mode"), int(bool(DB.setting("dry_run"))), body.get("cv_id"), now(), now()))
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
            match = re.fullmatch(r"/api/applications/([^/]+)/validate", path)
            if match:
                app = DB.one("SELECT * FROM applications WHERE id=?", (match.group(1),)) or {}
                fields = json.loads(app.get("field_state_json", "[]"))
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


def serve(host: str = "127.0.0.1", port: int = 4817) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ApplyPilot local service: http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve(port=int(os.environ.get("APPLYPILOT_PORT", "4817")))
