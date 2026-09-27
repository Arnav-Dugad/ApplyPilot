"""Per-job CV tailoring with invention checks, and clean PDF rendering through Edge's headless printer."""
from __future__ import annotations

import html
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .skills import canonical, find_skills

HEADING = re.compile(r"^(?:[A-Z][A-Z &/+-]{2,40}|[A-Z][a-zA-Z &/+-]{2,30}:)$")
SKILLS_HEADING = re.compile(r"(?i)^(technical\s+)?skills|^core competencies|^technologies|^tools")
BULLET = re.compile(r"^\s*[•\-*–▪●◦]\s*")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")


def cv_text(path: str | Path) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages).strip()


def _reorder_list_line(line: str, required: set[str], preferred: set[str]) -> str:
    """'Languages: Java, Python, SQL' -> the job's required skills first, then preferred, then the rest.
    Within each group your original order is kept; nothing is added, removed, or reworded."""
    prefix, sep, rest = line.partition(":")
    body = rest if sep else line
    items = [i.strip() for i in re.split(r",|\s\|\s|;", body) if i.strip()]
    if len(items) < 2:
        return line

    def group(item: str) -> int:
        skills = {canonical(s) for s in find_skills(item)} or {canonical(item)}
        return 0 if skills & required else 1 if skills & preferred else 2

    ordered = ", ".join(sorted(items, key=lambda item: (group(item), items.index(item))))
    return f"{prefix.rstrip()}: {ordered}" if sep else ordered


def _join_wrapped(lines: list[str]) -> list[str]:
    """PDF text wraps long skill lists; a short line with no label that follows a list line is its continuation."""
    out: list[str] = []
    in_skills = False
    for line in lines:
        stripped = line.strip()
        if HEADING.match(stripped):
            in_skills = bool(SKILLS_HEADING.search(stripped.rstrip(":")))
            out.append(line)
            continue
        continues = (in_skills and out and stripped and ":" not in stripped and not BULLET.match(stripped)
                     and ("," in out[-1] or " | " in out[-1]) and not out[-1].rstrip().endswith("."))
        if continues:
            joiner = "" if out[-1].rstrip().endswith("-") else " "
            out[-1] = out[-1].rstrip().rstrip("-") + joiner + stripped
        else:
            out.append(line)
    return out


def tailor_deterministic(text: str, job: dict[str, Any]) -> str:
    """Moves the job's skills to the front of every skills list. Wording is otherwise untouched."""
    required = {canonical(s) for s in job.get("required_skills") or []}
    preferred = {canonical(s) for s in job.get("preferred_skills") or []} - required
    in_skills = False
    out = []
    for line in _join_wrapped(text.splitlines()):
        stripped = line.strip()
        if HEADING.match(stripped):
            in_skills = bool(SKILLS_HEADING.search(stripped.rstrip(":")))
        elif in_skills and ("," in stripped or " | " in stripped):
            line = _reorder_list_line(line, required, preferred)
        out.append(line)
    return "\n".join(out)


def invention_flags(original: str, tailored: str, verified_skills: list[str]) -> dict[str, list[str]]:
    """Anything in the tailored CV that isn't in the original (or the verified profile) is flagged."""
    known_skills = {canonical(s) for s in find_skills(original)} | {canonical(s) for s in verified_skills}
    new_skills = [s for s in find_skills(tailored) if canonical(s) not in known_skills]
    original_numbers = set(NUMBER.findall(original))
    new_numbers = sorted({n for n in NUMBER.findall(tailored) if n not in original_numbers})
    return {"skills": new_skills, "numbers": new_numbers}


def to_html(text: str, title: str) -> str:
    """Typeset plain CV text: name, contact line, section headings, bullets, and paragraphs."""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    parts: list[str] = []
    if lines:
        parts.append(f"<h1>{html.escape(lines.pop(0).strip())}</h1>")
    contact = []
    while lines and lines[0].strip() and not HEADING.match(lines[0].strip()):
        contact.append(html.escape(lines.pop(0).strip()))
    if contact:
        parts.append(f"<p class='contact'>{' · '.join(contact)}</p>")
    open_list = False
    for raw in lines:
        line = raw.strip()
        if not line:
            if open_list:
                parts.append("</ul>")
                open_list = False
            continue
        if HEADING.match(line):
            if open_list:
                parts.append("</ul>")
                open_list = False
            parts.append(f"<h2>{html.escape(line.rstrip(':'))}</h2>")
        elif BULLET.match(line):
            if not open_list:
                parts.append("<ul>")
                open_list = True
            parts.append(f"<li>{html.escape(BULLET.sub('', line))}</li>")
        else:
            if open_list:
                parts.append("</ul>")
                open_list = False
            parts.append(f"<p>{html.escape(line)}</p>")
    if open_list:
        parts.append("</ul>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
@page {{ size: A4; margin: 14mm 16mm; }}
body {{ font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.4pt; line-height: 1.42; color: #16181d; }}
h1 {{ font-size: 21pt; letter-spacing: -.3px; margin: 0 0 2pt; }}
.contact {{ color: #4a5160; margin: 0 0 10pt; font-size: 9.6pt; }}
h2 {{ font-size: 10pt; text-transform: uppercase; letter-spacing: 1.2px; color: #0f6f58; border-bottom: 1px solid #d7dde3; padding-bottom: 2pt; margin: 12pt 0 5pt; }}
p {{ margin: 0 0 3pt; }} ul {{ margin: 2pt 0 5pt; padding-left: 14pt; }} li {{ margin: 0 0 2pt; }}
</style></head><body>{''.join(parts)}</body></html>"""


def render_pdf(text: str, title: str, target: Path, edge: str) -> Path:
    """Prints the typeset CV with a throwaway Edge profile so the user's browser is never touched."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "cv.html"
        page.write_text(to_html(text, title), encoding="utf-8")
        result = subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={Path(tmp) / 'profile'}",
                                 f"--print-to-pdf={target}", page.as_uri()], capture_output=True, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not target.is_file() or target.stat().st_size < 1000:
        raise RuntimeError(f"Edge couldn't create the PDF ({result.returncode})")
    return target
