from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from . import __version__, ai, service
from .automation import pre_submission_validate
from .database import AUTOPILOT_DEFAULTS, ROOT, now
from .job_parser import import_url
from .service import AUTOPILOT, DB, Conflict, NotFound, decoded, save_job

LOCAL_HOSTS = {"127.0.0.1", "localhost"}
DEV_ORIGIN = "http://localhost:1420"
TRACKER_STATUSES = {"QUEUED", "NEEDS_INFO", "WAITING_FOR_USER", "READY_FOR_REVIEW", "APPLIED", "INTERVIEWING", "OFFER", "REJECTED", "WITHDRAWN"}
DELETABLE = {"profile/facts": "profile_facts", "answers": "answer_vault", "jobs": "jobs", "applications": "applications", "watchlist": "watchlist", "drafts": "drafts"}
ANSWER_TYPES = {"EXACT", "COUNTRY_SPECIFIC", "COMPANY_SPECIFIC", "ROLE_SPECIFIC", "GENERATED_WITH_APPROVAL", "MANUAL_ONLY"}
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


def _save_answer(body: dict[str, Any]) -> dict[str, Any]:
    answer_type = body.get("answer_type", "MANUAL_ONLY")
    if answer_type not in ANSWER_TYPES:
        raise ValueError("Invalid answer type")
    question = str(body["canonical_question"]).strip()
    if not question:
        raise ValueError("Question is required")
    answer_id = str(uuid.uuid4())
    status = "VERIFIED" if body.get("approved") is True else "UNVERIFIED"
    DB.execute("INSERT INTO answer_vault(id,canonical_question,normalized_pattern,answer_type,answer_json,country_code,company,role_pattern,status,source_fact_ids_json,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (answer_id, question, " ".join(question.lower().split()), answer_type, json.dumps(body.get("answer")), body.get("country_code") or None, body.get("company") or None,
                body.get("role_pattern") or None, status, json.dumps(body.get("source_fact_ids", [])), now() if status == "VERIFIED" else None, now()))
    DB.log("ANSWER_VAULT_SAVED", "answer", answer_id, {"type": answer_type, "status": status})
    if status == "VERIFIED":
        service.reprepare_active()
    return {"id": answer_id, "status": status}


def _settings(body: dict[str, Any]) -> dict[str, Any]:
    allowed = {"strict_accuracy_mode", "dry_run", "actual_submission_enabled", "automation_mode", "ollama", "first_run_complete", "autopilot"}
    for key, value in body.items():
        if key not in allowed:
            continue
        if key == "autopilot":
            current = {**AUTOPILOT_DEFAULTS, **(DB.setting("autopilot") or {})}
            value = {**current, **{k: v for k, v in dict(value).items() if k in AUTOPILOT_DEFAULTS and type(v) is type(AUTOPILOT_DEFAULTS[k])}}
            value["interval_hours"] = min(max(float(value["interval_hours"]), 1), 72) if isinstance(value["interval_hours"], (int, float)) else 6
            value["min_score"] = min(max(int(value["min_score"]), 0), 100)
        if key == "ollama":
            value = {**(DB.setting("ollama") or {}), **{k: v for k, v in dict(value).items() if k in {"provider", "endpoint", "model"}}}
            if value.get("provider") not in {"OFF", "OLLAMA"}:
                raise ValueError("Unknown AI provider")
            if not re.fullmatch(r"https?://(127\.0\.0\.1|localhost)(:\d+)?/?", str(value.get("endpoint") or "")):
                raise ValueError("Local AI must run on this computer (localhost)")
        DB.set_setting(key, value)
    DB.log("SETTINGS_UPDATED", details={"keys": list(body)})
    if "autopilot" in body and (DB.setting("autopilot") or {}).get("enabled"):
        AUTOPILOT.start_scheduler()
    return {"ok": True}


def _set_status(app_id: str, status: Any) -> dict[str, Any]:
    if status not in TRACKER_STATUSES:
        raise ValueError("Invalid application status")
    service.one("SELECT id FROM applications WHERE id=?", (app_id,))
    stamp = now()
    DB.execute("UPDATE applications SET status=?,updated_at=?,submitted_at=CASE WHEN ?='APPLIED' THEN coalesce(submitted_at,?) ELSE submitted_at END WHERE id=?", (status, stamp, status, stamp, app_id))
    DB.log("APPLICATION_STATUS_CHANGED", "application", app_id, {"status": status})
    if status == "OFFER":
        service.notify("OFFER", "Offer recorded 🎉", "Congratulations — it's in your Tracker.", "Tracker")
    return {"id": app_id, "status": status}


def _validate(app_id: str) -> dict[str, Any]:
    app = service.one("SELECT * FROM applications WHERE id=?", (app_id,))
    settings = {"dry_run": DB.setting("dry_run"), "actual_submission_enabled": DB.setting("actual_submission_enabled")}
    result = pre_submission_validate(app, app.get("field_state") or [], settings=settings)
    DB.log("APPLICATION_VALIDATED", "application", app_id, result, "WARN" if result["blocked"] else "INFO")
    return result


_live_runs: set[str] = set()


def _live_fill(app_id: str) -> dict[str, Any]:
    """Starts filling the real form in Edge on a background thread; progress lands in browser_run_json."""
    from . import browser_runner

    app = service.one("SELECT applications.*,jobs.country,jobs.company,jobs.application_url,jobs.posting_url FROM applications JOIN jobs ON jobs.id=applications.job_id WHERE applications.id=?", (app_id,))
    url = app.get("application_url") or app.get("posting_url")
    if not url:
        raise ValueError("This job has no application link")
    if app_id in _live_runs:
        raise Conflict("Already filling this application")
    events: list[dict[str, str]] = []

    def save(status: str, extra: dict[str, Any] | None = None) -> None:
        DB.execute("UPDATE applications SET browser_run_json=?,updated_at=? WHERE id=?", (json.dumps({"status": status, "events": events, **(extra or {})}), now(), app_id))

    def emit(step: str, message: str) -> None:
        events.append({"at": now(), "step": step, "message": message})
        save("RUNNING")

    def run() -> None:
        _live_runs.add(app_id)
        try:
            plan = browser_runner.live_fill(url, service.facts(), app.get("country"), service.answers(), service.application_context(app), on_event=emit)
            if plan.get("fields"):
                status = plan["status"] if app["status"] in service.ACTIVE_STATUSES else app["status"]
                DB.execute("UPDATE applications SET status=?,field_state_json=?,prep_source='LIVE_PAGE' WHERE id=?", (status, json.dumps(plan["fields"]), app_id))
            save("DONE", {"filled": plan.get("filled_count", 0), "paused": plan.get("unknown_count", 0)})
            DB.log("LIVE_FILL_COMPLETED", "application", app_id, {"filled": plan.get("filled_count", 0), "paused": plan.get("unknown_count", 0)})
        except Exception as exc:
            events.append({"at": now(), "step": "error", "message": f"Stopped safely: {exc}"})
            save("FAILED")
            DB.log("LIVE_FILL_FAILED", "application", app_id, {"error": str(exc)[:300]}, "ERROR")
        finally:
            _live_runs.discard(app_id)

    emit("start", "Starting live fill")
    threading.Thread(target=run, name="live-fill", daemon=True).start()
    return {"ok": True}


def _delete(kind: str, item_id: str) -> dict[str, Any]:
    table = DELETABLE[kind]
    service.one(f"SELECT id FROM {table} WHERE id=?", (item_id,))
    if kind == "jobs" and DB.one("SELECT id FROM applications WHERE job_id=?", (item_id,)):
        raise ValueError("Remove this job's application from the tracker first")
    if kind == "jobs":
        DB.execute("DELETE FROM eligibility_results WHERE job_id=?", (item_id,))
        DB.execute("DELETE FROM drafts WHERE job_id=?", (item_id,))
    if kind == "applications":
        DB.execute("DELETE FROM receipts WHERE application_id=?", (item_id,))
    DB.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
    DB.log(f"{table.upper()}_DELETED", table, item_id)
    return {"ok": True}


GET_ROUTES: list[tuple[str, Callable[..., Any]]] = [
    (r"/api/bootstrap", lambda _b: service.bootstrap()),
    (r"/api/jobs/([^/]+)", lambda _b, job_id: service.job_detail(job_id)),
    (r"/api/autopilot", lambda _b: service.autopilot_state()),
    (r"/api/ai/status", lambda _b: ai.status(service.ai_config())),
]

POST_ROUTES: list[tuple[str, Callable[..., Any], int]] = [
    (r"/api/profile/facts", lambda b: decoded([DB.upsert_fact(b)])[0] | {"reprepared": service.reprepare_active()}, 200),
    (r"/api/answers", _save_answer, 201),
    (r"/api/answers/([^/]+)/approve", lambda _b, i: (DB.execute("UPDATE answer_vault SET status='VERIFIED',approved_at=?,updated_at=? WHERE id=?", (now(), now(), service.one("SELECT id FROM answer_vault WHERE id=?", (i,))["id"])), service.reprepare_active(), {"id": i, "status": "VERIFIED"})[-1], 200),
    (r"/api/settings", _settings, 200),
    (r"/api/jobs/import", lambda b: save_job(import_url(str(b["url"]))), 201),
    (r"/api/jobs/manual", lambda b: _manual_job(b), 201),
    (r"/api/jobs/analyze-all", lambda _b: {"analyzed": service.analyze_all()}, 200),
    (r"/api/jobs/([^/]+)/analyze", lambda _b, i: service.analyze_job(i), 200),
    (r"/api/jobs/([^/]+)/queue", lambda b, i: service.queue_job(i, b.get("cv_id")), 201),
    (r"/api/jobs/([^/]+)/summary", lambda _b, i: service.summarize_job(i), 200),
    (r"/api/jobs/([^/]+)/cover-letter", lambda _b, i: service.draft_cover_letter(i), 201),
    (r"/api/cvs/import", lambda b: service.import_cv(b.get("filename", "resume.pdf"), b["content_base64"], b.get("variant")), 201),
    (r"/api/cvs/([^/]+)/approve", lambda b, i: _approve_cv(i, b.get("approved", True) is True), 200),
    (r"/api/applications/([^/]+)/prepare", lambda _b, i: service.prepare_application(i), 200),
    (r"/api/applications/([^/]+)/dry-run", lambda b, i: service.prepare_application(i, b.get("fields") or None, "CUSTOM" if b.get("fields") else None), 200),
    (r"/api/applications/([^/]+)/live-fill", lambda _b, i: _live_fill(i), 202),
    (r"/api/applications/([^/]+)/status", lambda b, i: _set_status(i, b.get("status")), 200),
    (r"/api/applications/([^/]+)/validate", lambda _b, i: _validate(i), 200),
    (r"/api/inbox/answer", lambda b: service.answer_question(b), 200),
    (r"/api/inbox/draft-answer", lambda b: service.draft_answer(str(b.get("question") or ""), b.get("job_id")), 201),
    (r"/api/suggestions/([^/]+)/accept", lambda b, i: service.accept_suggestion(i, b.get("value")), 200),
    (r"/api/suggestions/([^/]+)/dismiss", lambda _b, i: service.dismiss_suggestion(i), 200),
    (r"/api/drafts/([^/]+)", lambda b, i: service.update_draft(i, b.get("content"), b.get("approve") is True), 200),
    (r"/api/watchlist", lambda b: service.add_watch(str(b.get("url") or "")), 201),
    (r"/api/autopilot/run", lambda _b: {"run_id": AUTOPILOT.start("MANUAL")}, 202),
    (r"/api/notifications/read", lambda _b: (DB.execute("UPDATE notifications SET read=1 WHERE read=0"), {"ok": True})[-1], 200),
    (r"/api/ai/pull", lambda b: (ai.pull_model(service.ai_config(), str(b.get("model") or "")), {"ok": True})[-1], 202),
]


def _manual_job(body: dict[str, Any]) -> dict[str, Any]:
    body = {k: (v.strip() or None) if isinstance(v, str) else v for k, v in body.items()}
    if not body.get("company") or not body.get("role"):
        raise ValueError("Company and role are required")
    body.update({"source": "MANUAL", "extraction_status": "USER_ENTERED", "application_url": body.get("application_url") or body.get("posting_url")})
    job = save_job(body)
    service.analyze_job(job["id"])
    return job


def _approve_cv(cv_id: str, approved: bool) -> dict[str, Any]:
    service.one("SELECT id FROM cvs WHERE id=?", (cv_id,))
    DB.execute("UPDATE cvs SET approved=? WHERE id=?", (int(approved), cv_id))
    if approved:
        DB.execute("UPDATE applications SET cv_id=?,updated_at=? WHERE cv_id IS NULL AND status IN ('QUEUED','NEEDS_INFO','WAITING_FOR_USER','READY_FOR_REVIEW')", (cv_id, now()))
    DB.log("CV_APPROVED" if approved else "CV_UNAPPROVED", "cv", cv_id)
    service.reprepare_active()
    return {"id": cv_id, "approved": approved}


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
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        return body

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

    def _dispatch(self, routes: list[tuple[str, Callable[..., Any]]] | list[tuple[str, Callable[..., Any], int]], path: str, body: dict[str, Any]) -> None:
        for route in routes:
            pattern, handler, status = (route + (200,))[:3] if len(route) == 2 else route  # type: ignore[operator]
            match = re.fullmatch(pattern, path)
            if match:
                return self._json(status, handler(body, *match.groups()))
        return self._json(404, {"error": "Not found"})

    def _handle(self, method: str) -> None:
        path = urlparse(self.path).path
        if not self._trusted():
            # Drain a small body first so the client receives the 403 instead of a connection reset.
            length = int(self.headers.get("Content-Length") or 0)
            if 0 < length <= 1_000_000:
                self.rfile.read(length)
            self.close_connection = True
            return self._json(403, {"error": "Forbidden"})
        if method == "GET" and not (path.startswith("/api/") or path == "/health"):
            return self._static(path)
        try:
            if method == "GET":
                if path == "/health":
                    return self._json(200, {"status": "ok", "version": __version__, "database": str(DB.path), "strict": DB.setting("strict_accuracy_mode")})
                return self._dispatch(GET_ROUTES, path, {})
            body = self._body()
            if method == "DELETE":
                match = re.fullmatch(r"/api/(profile/facts|answers|jobs|applications|watchlist|drafts)/([^/]+)", path)
                return self._json(200, _delete(*match.groups())) if match else self._json(404, {"error": "Not found"})
            return self._dispatch(POST_ROUTES, path, body)
        except Conflict as exc:
            return self._json(409, {"error": str(exc), **exc.extra})
        except NotFound as exc:
            return self._json(404, {"error": str(exc)})
        except ai.AIUnavailable as exc:
            return self._json(503, {"error": str(exc)})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:
            DB.log("FAILED_SAFELY", details={"path": path, "error": str(exc)}, level="ERROR")
            return self._json(500, {"error": str(exc)})

    def do_OPTIONS(self) -> None:
        if self.headers.get("Origin") != DEV_ORIGIN:
            return self._json(403, {"error": "Forbidden"})
        self._json(204, {})

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_DELETE(self) -> None:
        self._handle("DELETE")


def create_server(host: str = "127.0.0.1", port: int = 4817) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def serve(host: str = "127.0.0.1", port: int = 4817) -> None:
    server = create_server(host, port)
    AUTOPILOT.start_scheduler()
    ui = " (serving built UI)" if static_dir() else ""
    print(f"ApplyPilot local service: http://{host}:{server.server_port}{ui}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve(port=int(os.environ.get("APPLYPILOT_PORT", "4817")))
