from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from .automation import DetectedField, dry_run
from .safety import classify_field


CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha", "verify you are human")
MFA_MARKERS = ("two-factor", "multi-factor", "verification code", "authenticator code", "one-time password")


def adapter_for(url: str) -> str:
    lowered = url.lower()
    for marker, name in (("greenhouse", "GREENHOUSE"), ("lever.co", "LEVER"), ("myworkdayjobs", "WORKDAY"), ("ashbyhq", "ASHBY"), ("smartrecruiters", "SMARTRECRUITERS")):
        if marker in lowered:
            return name
    return "GENERIC"


def detect_pause_reason(page_text: str) -> str | None:
    lowered = page_text.lower()
    if any(x in lowered for x in CAPTCHA_MARKERS):
        return "CAPTCHA detected. Complete it manually, then resume."
    if any(x in lowered for x in MFA_MARKERS):
        return "Authentication or MFA detected. Complete it manually, then resume."
    return None


def browser_dry_run(url: str, facts: list[dict[str, Any]], country: str | None, *, on_event: Callable[[str, dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Open and safely fill a form using Playwright when installed.

    This function intentionally has no submission path. It accepts only resolved values,
    never evaluates page-provided code, and leaves the headed browser open on a pause.
    """
    emit = on_event or (lambda _event, _detail: None)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed. Install the optional browser package before starting a browser dry run.") from exc

    emit("OPENING_APPLICATION", {"url": url, "adapter": adapter_for(url)})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=False)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        pause = detect_pause_reason(page.locator("body").inner_text(timeout=5_000))
        if pause:
            emit("AUTOMATION_PAUSED", {"reason": pause})
            return {"status": "WAITING_FOR_USER", "reason": pause, "submission_attempted": False}

        fields: list[dict[str, Any]] = []
        for index, node in enumerate(page.locator("input, select, textarea").all()):
            if not node.is_visible() or node.get_attribute("type") in {"hidden", "submit", "button", "file"}:
                continue
            node_id = node.get_attribute("id") or ""
            label = ""
            if node_id:
                label_node = page.locator(f'label[for="{node_id}"]')
                if label_node.count():
                    label = label_node.first.inner_text()
            label = label or node.get_attribute("aria-label") or node.get_attribute("placeholder") or node.get_attribute("name") or f"Unlabeled field {index + 1}"
            fields.append(asdict(DetectedField(selector=f"#{node_id}" if node_id else f"input:nth-of-type({index + 1})", label=label, name=node.get_attribute("name") or "", field_type=node.get_attribute("type") or node.evaluate("e => e.tagName.toLowerCase()"), required=node.get_attribute("required") is not None, classification=classify_field(label))))

        plan = dry_run(fields, facts, country)
        emit("FILLING_VERIFIED_FIELDS", {"count": plan["filled_count"]})
        for field in plan["fields"]:
            if field["decision"]["action"] != "FILL":
                emit("AUTOMATION_PAUSED", {"field": field["label"], "reason": field["decision"]["reason"]})
                continue
            locator = page.locator(field["selector"]).first
            value = field["decision"]["value"]
            if locator.evaluate("e => e.tagName.toLowerCase()") == "select":
                locator.select_option(label=str(value))
            elif locator.get_attribute("type") in {"checkbox", "radio"}:
                if bool(value):
                    locator.check()
            else:
                locator.fill(str(value))
        # No code path in this function locates or clicks submit.
        page.bring_to_front()
        emit("DRY_RUN_COMPLETED", {"status": plan["status"]})
        context.close()
        browser.close()
        return plan

