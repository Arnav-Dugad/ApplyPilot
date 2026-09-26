"""Fills a real application form in the user's own Edge window, then stops before submit.

ApplyPilot starts a dedicated Edge profile with a local debugging port and attaches to it with
Playwright. The window stays open after filling so the user can review, finish paused fields,
and press submit themselves. No code path here locates or clicks a submit button.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .automation import dry_run
from .database import data_dir

CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha", "verify you are human")
MFA_MARKERS = ("two-factor", "multi-factor", "verification code", "authenticator code", "one-time password")
FIELD_SELECTOR = "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]), select, textarea"

# Our own read-only scan script (never page-provided code). Returns one entry per question.
SCAN_FIELDS = r"""(selector) => {
  const clean = t => (t || '').replace(/[*✱]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300);
  const text = el => el ? clean(el.innerText || el.textContent) : '';
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const own = el => {
    const aria = el.getAttribute('aria-label'); if (aria) return clean(aria);
    const by = el.getAttribute('aria-labelledby');
    if (by) { const t = by.split(/\s+/).map(id => text(document.getElementById(id))).join(' '); if (t) return clean(t); }
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return text(l); }
    const wrap = el.closest('label'); if (wrap) return text(wrap);
    return '';
  };
  const question = el => {
    const box = el.closest('fieldset, [role=radiogroup], [role=group], .application-question, li.application-question, [class*=question], [class*=Question], [class*=field], .form-group');
    if (box) { const t = box.querySelector('legend, .application-label, [class*=label], label'); if (t) return text(t); }
    return '';
  };
  const all = Array.from(document.querySelectorAll(selector));
  const out = []; const groups = {};
  all.forEach((el, index) => {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    const shown = visible(el);
    if (!shown && type !== 'file') return;
    const required = el.required || el.getAttribute('aria-required') === 'true';
    if (type === 'radio' || (type === 'checkbox' && el.name && document.querySelectorAll(`input[name="${CSS.escape(el.name)}"]`).length > 1)) {
      const key = type + ':' + (el.name || index);
      if (!groups[key]) { groups[key] = { kind: type === 'radio' ? 'radio' : 'checkboxes', label: question(el) || el.name, name: el.name || '', required, options: [], indexes: [] }; out.push(groups[key]); }
      groups[key].options.push(own(el) || el.value); groups[key].indexes.push(index); groups[key].required = groups[key].required || required;
      return;
    }
    const kind = el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea' : type === 'file' ? 'file' : type === 'checkbox' ? 'checkbox' : (el.getAttribute('role') === 'combobox' || el.getAttribute('aria-autocomplete')) ? 'combobox' : 'text';
    const options = kind === 'select' ? Array.from(el.options).map(o => clean(o.textContent)).filter(o => o && !/^(select|choose|please select|--)/i.test(o)) : [];
    out.push({ kind, label: own(el) || question(el) || clean(el.getAttribute('placeholder')) || el.name || el.id, name: el.name || el.id || '', required, options, indexes: [index] });
  });
  return out;
}"""


def adapter_for(url: str) -> str:
    lowered = url.lower()
    for marker, name in (("greenhouse", "GREENHOUSE"), ("lever.co", "LEVER"), ("myworkdayjobs", "WORKDAY"), ("ashbyhq", "ASHBY"), ("smartrecruiters", "SMARTRECRUITERS")):
        if marker in lowered:
            return name
    return "GENERIC"


def display_value(value: Any) -> str:
    """Yes/No questions are stored as booleans; forms expect the words."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def detect_pause_reason(page_text: str) -> str | None:
    lowered = page_text.lower()
    if any(x in lowered for x in CAPTCHA_MARKERS):
        return "CAPTCHA detected. Complete it manually, then resume."
    if any(x in lowered for x in MFA_MARKERS):
        return "Authentication or MFA detected. Complete it manually, then resume."
    return None


def find_edge() -> str | None:
    candidates = [shutil.which("msedge")] + [str(Path(os.environ.get(root, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe") for root in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    return next((c for c in candidates if c and Path(c).is_file()), None)


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _debug_port_file() -> Path:
    return data_dir() / "browser" / "debug-port"


def ensure_browser(url: str) -> int:
    """Reuses ApplyPilot's Edge window if it is open, otherwise starts it. Returns the debugging port."""
    port_file = _debug_port_file()
    port_file.parent.mkdir(parents=True, exist_ok=True)
    if port_file.exists():
        port = int(port_file.read_text() or 0)
        if port and _port_open(port):
            return port
    edge = find_edge()
    if not edge:
        raise RuntimeError("Microsoft Edge was not found. Install Edge to use live form filling.")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    profile = data_dir() / "browser" / "profile"
    subprocess.Popen([edge, f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", "--new-window", url],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(100):
        if _port_open(port):
            port_file.write_text(str(port))
            return port
        time.sleep(0.1)
    raise RuntimeError("Edge did not start its automation port")


def live_fill(url: str, facts: list[dict[str, Any]], country: str | None, answers: list[dict[str, Any]], context: dict[str, Any], *, on_event: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    """Opens the application in Edge, fills verified answers, highlights what needs the user, and leaves the window open."""
    emit = on_event or (lambda _step, _message: None)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Live filling needs the Playwright package") from exc

    emit("open", f"Opening {adapter_for(url).title()} application in Edge")
    port = ensure_browser(url)
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        browser_context = browser.contexts[0]
        page = next((p for p in browser_context.pages if p.url.split("#")[0] == url.split("#")[0]), None) or browser_context.new_page()
        if page.url.split("#")[0] != url.split("#")[0]:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.bring_to_front()
        try:
            page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            pass
        _reveal_application_form(page, emit)
        pause = detect_pause_reason(page.locator("body").inner_text(timeout=5_000))
        if pause:
            emit("pause", pause)
            return {"status": "WAITING_FOR_USER", "reason": pause, "fields": [], "filled_count": 0, "unknown_count": 0, "submission_attempted": False}

        scanned = page.evaluate(SCAN_FIELDS, FIELD_SELECTOR)
        fields = [{"selector": f"{FIELD_SELECTOR}>>nth={item['indexes'][0]}", "label": item["label"] or item["name"] or "Unlabeled field", "name": item["name"],
                   "field_type": "file" if item["kind"] == "file" else item["kind"], "required": bool(item["required"]), "options": item["options"]} for item in scanned]
        emit("scan", f"Found {len(fields)} questions on the page")
        plan = dry_run(fields, facts, country, answers, context)
        nodes = page.locator(FIELD_SELECTOR)
        filled = failed = 0
        for item, field in zip(scanned, plan["fields"]):
            decision = field["decision"]
            first = nodes.nth(item["indexes"][0])
            if decision["action"] != "FILL":
                _mark(first, "pause")
                continue
            try:
                _fill(page, nodes, item, decision, context)
                _mark(first, "fill")
                filled += 1
            except Exception as exc:
                failed += 1
                decision.update({"action": "PAUSE", "reason": f"Couldn't fill automatically ({type(exc).__name__}); please complete this one."})
                _mark(first, "pause")
        plan["filled_count"], plan["unknown_count"] = filled, len(plan["fields"]) - filled
        plan["blocking_count"] = sum(1 for f in plan["fields"] if f["required"] and f["decision"]["action"] != "FILL")
        plan["status"] = "WAITING_FOR_USER" if plan["blocking_count"] else "READY_FOR_REVIEW"
        emit("fill", f"Filled {filled} fields from verified facts; {plan['unknown_count']} highlighted for you" + (f" ({failed} couldn't be set automatically)" if failed else ""))
        emit("done", "Review the highlighted fields in Edge, then press submit yourself. ApplyPilot never submits.")
        page.bring_to_front()
        # Leaving this block disconnects Playwright; the Edge window stays open for the user.
        return plan


def _reveal_application_form(page: Any, emit: Callable[[str, str], None]) -> None:
    """Some boards show the description first; click an obvious 'Apply' link (never a submit button)."""
    if page.locator("input[type=file], input[name*=email i], input[type=email]").count():
        return
    link = page.locator("a:has-text('Apply for this job'), a:has-text('Apply now'), a:has-text('Apply'), button:has-text('Apply for this job')").first
    if link.count():
        emit("open", "Opening the application form")
        link.click(timeout=5_000)
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass


def _fill(page: Any, nodes: Any, item: dict[str, Any], decision: dict[str, Any], context: dict[str, Any]) -> None:
    value = decision.get("value")
    kind = item["kind"]
    first = nodes.nth(item["indexes"][0])
    if kind == "file":
        cv = context.get("cv")
        if not decision.get("upload") or not cv or not Path(cv["path"]).is_file():
            raise RuntimeError("No approved CV file")
        first.set_input_files(cv["path"])
    elif kind == "select":
        first.select_option(label=display_value(value))
    elif kind in {"radio", "checkboxes"}:
        wanted = display_value(value).strip().lower()
        index = next(i for i, option in zip(item["indexes"], item["options"]) if option.strip().lower() == wanted)
        nodes.nth(index).check()
    elif kind == "checkbox":
        if value is True or str(value).strip().lower() in {"yes", "true"}:
            first.check()
    elif kind == "combobox":
        first.click()
        first.fill(display_value(value))
        page.keyboard.press("Enter")
    else:
        first.fill(display_value(value))


def _mark(locator: Any, state: str) -> None:
    """Visual cue in the user's window: green for filled, amber for needs-you. Only styles; no page logic runs."""
    color = "#1fbf8f" if state == "fill" else "#f5a524"
    try:
        locator.evaluate("(el, c) => { const t = el.type === 'file' || el.type === 'radio' || el.type === 'checkbox' ? (el.closest('label, fieldset, div') || el) : el; t.style.outline = `2px solid ${c}`; t.style.outlineOffset = '2px'; t.style.borderRadius = '6px'; }", color)
    except Exception:
        pass
