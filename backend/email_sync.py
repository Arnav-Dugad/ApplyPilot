"""Reads recent application emails over IMAP and moves Tracker cards (interview, rejection, offer).

- The app password is encrypted with Windows DPAPI for the current user; it is never stored in plain text.
- Only recent messages are read, only headers plus the start of the text body, and nothing but the
  subject, sender, and date of matched messages is kept.
- A status only moves forward (applied → interviewing → offer), or to rejected; every move can be undone.
"""
from __future__ import annotations

import base64
import email
import email.header
import email.utils
import imaplib
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .insights import company_key

PRESETS = {
    "GMAIL": {"host": "imap.gmail.com", "port": 993, "help": "Use a Google App Password (Google Account → Security → 2-Step Verification → App passwords)."},
    "YAHOO": {"host": "imap.mail.yahoo.com", "port": 993, "help": "Use a Yahoo app password (Account security → Generate app password)."},
    "ICLOUD": {"host": "imap.mail.me.com", "port": 993, "help": "Use an app-specific password from appleid.apple.com."},
    "ZOHO": {"host": "imap.zoho.com", "port": 993, "help": "Enable IMAP in Zoho Mail settings and use an app password."},
    "OUTLOOK": {"host": "outlook.office365.com", "port": 993, "help": "Work or school Microsoft 365 accounts with IMAP enabled. Personal Outlook.com accounts only allow sign-in through Microsoft's OAuth, which ApplyPilot doesn't support yet."},
    "CUSTOM": {"host": "", "port": 993, "help": "Any IMAP server over SSL."},
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OFFER", re.compile(r"(?i)\b(pleased|delighted|excited|happy) to (extend|offer you)|offer letter|(extend|extending) (you )?an offer|congratulations[^.]{0,60}\boffer\b")),
    ("REJECTED", re.compile(r"(?i)unfortunately|not (to )?(be )?mov(e|ing) forward|decided to (pursue|proceed with) other|other candidates|not been selected|won'?t be (moving|progressing)|regret to inform|position has been filled|no longer (under consideration|being considered)|will not be proceeding")),
    ("INTERVIEW", re.compile(r"(?i)\b(schedule|book|arrange)\b[^.]{0,40}\b(interview|call|chat|conversation)|\binterview (invitation|invite|request)|invite you to (an? )?(interview|call|chat)|next (step|round)|phone screen|technical (interview|screen)|(online|coding|technical) (assessment|challenge|test)|hackerrank|codesignal|codility")),
    ("RECEIVED", re.compile(r"(?i)(thank(s| you) for (applying|your application|your interest))|application (has been )?(received|submitted)|we('| ha)ve received your application")),
]
RANK = {"QUEUED": 0, "NEEDS_INFO": 0, "WAITING_FOR_USER": 0, "READY_FOR_REVIEW": 0, "APPLIED": 1, "SUBMITTED": 1, "INTERVIEWING": 2, "OFFER": 3}
TARGET = {"INTERVIEW": "INTERVIEWING", "OFFER": "OFFER", "REJECTED": "REJECTED", "RECEIVED": "APPLIED"}


# ---------- secret storage (DPAPI) ----------

def protect(secret: str) -> str:
    if sys.platform != "win32":
        raise RuntimeError("Email sync stores passwords with Windows data protection and is only available on Windows")
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    data = secret.encode("utf-8")
    blob_in = BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(blob_in), "ApplyPilot email", None, None, None, 0x1, ctypes.byref(blob_out)):
        raise RuntimeError("Windows couldn't encrypt the password")
    try:
        return "dpapi:" + base64.b64encode(ctypes.string_at(blob_out.pbData, blob_out.cbData)).decode()
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def unprotect(token: str) -> str:
    if not token.startswith("dpapi:") or sys.platform != "win32":
        raise RuntimeError("Saved email password can't be read on this computer — enter it again")
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    raw = base64.b64decode(token[6:])
    blob_in = BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw, len(raw)), ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
        raise RuntimeError("Saved email password can't be read on this computer — enter it again")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# ---------- classification & matching ----------

def classify(subject: str, body: str) -> str | None:
    text = f"{subject}\n{body[:6000]}"
    for kind, pattern in PATTERNS:
        if pattern.search(text):
            return kind
    return None


def match_application(sender: str, subject: str, body: str, apps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The one application this email is about, or None when it's ambiguous."""
    haystack = f" {company_key(sender)} {company_key(subject)} {company_key(body[:4000])} "
    domain = (re.search(r"@([\w.-]+)", sender) or [None, ""])[1].lower()
    candidates = []
    for app in apps:
        key = company_key(app.get("company"))
        if not key:
            continue
        in_text = f" {key} " in haystack
        in_domain = key.replace(" ", "") in domain.replace("-", "")
        if in_text or in_domain:
            candidates.append(app)
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    role_hits = [a for a in candidates if a.get("role") and company_key(a["role"]) and f" {company_key(a['role'])} " in haystack]
    return role_hits[0] if len(role_hits) == 1 else None


def _decode(value: str | None) -> str:
    parts = email.header.decode_header(value or "")
    return "".join(p.decode(enc or "utf-8", "replace") if isinstance(p, bytes) else p for p, enc in parts)


def _body(message: email.message.Message) -> str:
    for part in message.walk() if message.is_multipart() else [message]:
        if part.get_content_type() in {"text/plain", "text/html"} and not part.get_filename():
            payload = part.get_payload(decode=True) or b""
            text = payload[:40_000].decode(part.get_content_charset() or "utf-8", "replace")
            return re.sub(r"<[^>]+>", " ", text) if part.get_content_type() == "text/html" else text
    return ""


def fetch_recent(config: dict[str, Any], password: str, days: int = 21, limit: int = 150, connect: Callable[..., Any] = imaplib.IMAP4_SSL) -> list[dict[str, Any]]:
    client = connect(config["host"], int(config.get("port") or 993), timeout=30)
    try:
        client.login(config["address"], password)
        client.select("INBOX", readonly=True)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = client.search(None, "SINCE", since)
        if status != "OK":
            raise RuntimeError("The mail server refused the search")
        ids = (data[0] or b"").split()[-limit:]
        messages = []
        for message_id in reversed(ids):
            status, parts = client.fetch(message_id, "(BODY.PEEK[])")
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            message = email.message_from_bytes(parts[0][1][:200_000])
            messages.append({
                "message_id": (message.get("Message-ID") or f"{config['address']}:{message_id.decode()}").strip(),
                "sender": _decode(message.get("From")), "subject": _decode(message.get("Subject")), "body": _body(message),
                "date": (email.utils.parsedate_to_datetime(message["Date"]).isoformat() if message.get("Date") else None),
            })
        return messages
    finally:
        try:
            client.logout()
        except Exception:
            pass


def decide(messages: list[dict[str, Any]], apps: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    """What to do with each new message: status moves only forward, or to rejected, never out of an offer."""
    decisions = []
    for m in sorted(messages, key=lambda x: x.get("date") or ""):
        if m["message_id"] in seen:
            continue
        kind = classify(m["subject"], m["body"])
        if not kind:
            continue
        app = match_application(m["sender"], m["subject"], m["body"], apps)
        action, target = "NONE", None
        if app:
            current = app["status"]
            target = TARGET[kind]
            if current in {"OFFER", "WITHDRAWN"} or current == target:
                action = "NONE"
            elif target == "REJECTED":
                action = "MOVE" if current != "REJECTED" else "NONE"
            elif RANK.get(target, 0) > RANK.get(current, 0):
                action = "MOVE"
            if action == "MOVE":
                app["status"] = target  # later emails in this batch see the new state
        decisions.append({**{k: m[k] for k in ("message_id", "sender", "subject", "date")}, "kind": kind, "application": app, "action": action, "target": target})
    return decisions
