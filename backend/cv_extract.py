"""Deterministic CV reading. Output is suggestions with evidence; nothing becomes a verified fact until accepted."""
from __future__ import annotations

import re
from typing import Any

from .skills import find_skills

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w/])(\+?\d{1,3}[\s.-]?)?(\(?\d{2,5}\)?[\s.-]?)\d{3,5}[\s.-]?\d{3,5}(?![\w/])")
LINKEDIN = re.compile(r"(?i)(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w%-]+/?")
GITHUB = re.compile(r"(?i)(?:https?://)?github\.com/[A-Za-z0-9-]{1,39}(?![\w/-])")
# Case-sensitive and single-line on purpose: institution names are capitalized words on one line.
UNIVERSITY = re.compile(r"\b((?:[A-Z][\w.&'-]*[ \t]+(?:(?:of|and|for|&)[ \t]+)?)+(?:University|Institute of Technology|Institute|College|Polytechnic)(?:[ \t]+(?:of|at)[ \t]+[A-Z][\w-]*(?:[ \t]+[A-Z][\w-]*)*)?|University of [A-Z][\w-]*(?:[ \t]+[A-Z][\w-]*)*)")
DEGREE = re.compile(r"(?i)\b(B\.?\s?Tech|B\.?\s?E\.?|B\.?\s?Sc|BSc|B\.?\s?S\.?|Bachelor(?:'s)? of [A-Za-z ]+|M\.?\s?Tech|M\.?\s?Sc|MSc|M\.?\s?S\.?|Master(?:'s)? of [A-Za-z ]+|BCA|MCA|Ph\.?\s?D)\b(?:[^\n,;|]{0,8}?(?:in|of)\s+([A-Za-z &]+?)(?=[\n,;|(]|\s{2}|\s\d|$))?")
YEAR_RANGE = re.compile(r"(?i)\b(20\d{2})\s*(?:-|–|—|to)\s*(20\d{2}|present|current|expected)")
EXPECTED = re.compile(r"(?i)(?:expected|graduat\w*|class of)[^\n]{0,20}?((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?(20\d{2})")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _line(text: str, start: int) -> str:
    begin = text.rfind("\n", 0, start) + 1
    end = text.find("\n", start)
    return text[begin:end if end != -1 else None].strip()[:160]


def extract(text: str) -> list[dict[str, Any]]:
    """Profile suggestions: {category, fact_key, value, confidence, evidence}."""
    suggestions: list[dict[str, Any]] = []
    head = text[:1500]

    def add(category: str, key: str, value: Any, confidence: float, evidence: str) -> None:
        if value and not any(s["category"] == category and s["fact_key"] == key for s in suggestions):
            suggestions.append({"category": category, "fact_key": key, "value": value, "confidence": round(confidence, 2), "evidence": evidence})

    first_lines = [line.strip() for line in text.splitlines() if line.strip()][:4]
    for line in first_lines:
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Z][a-zA-Z'.-]+|[A-Z]{2,}", w) for w in words) and not re.search(r"(?i)resume|curriculum|vitae|profile", line):
            add("personal", "full_name", " ".join(w.capitalize() if w.isupper() else w for w in words), 0.7, line)
            break
    if m := EMAIL.search(head) or EMAIL.search(text):
        add("contact", "email", m.group(0), 0.95, _line(text, m.start()))
    for m in PHONE.finditer(head):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 15 and not re.fullmatch(r"(19|20)\d{2}(19|20)\d{2}", digits):
            add("contact", "phone", re.sub(r"\s+", " ", m.group(0).strip()), 0.85, _line(text, m.start()))
            break
    if m := LINKEDIN.search(text):
        url = m.group(0)
        add("contact", "linkedin", url if url.lower().startswith("http") else f"https://{url}", 0.95, _line(text, m.start()))
    if m := GITHUB.search(text):
        url = m.group(0)
        add("contact", "github", url if url.lower().startswith("http") else f"https://{url}", 0.95, _line(text, m.start()))
    if m := UNIVERSITY.search(text):
        add("education", "university", re.sub(r"\s+", " ", m.group(0)).strip(" ,"), 0.75, _line(text, m.start()))
    if m := DEGREE.search(text):
        degree = re.sub(r"\s+", " ", m.group(0)).strip(" ,.-")
        add("education", "degree", degree, 0.7, _line(text, m.start()))
    if m := EXPECTED.search(text):
        month = MONTHS.get((m.group(1) or "").strip()[:3].lower())
        add("education", "graduation_date", f"{m.group(2)}-{month:02d}" if month else m.group(2), 0.75, _line(text, m.start()))
    elif ranges := [r for r in YEAR_RANGE.finditer(text) if UNIVERSITY.search(_line(text, r.start())) or DEGREE.search(_line(text, r.start()))]:
        r = ranges[0]
        end = r.group(2)
        if end.isdigit():
            add("education", "graduation_date", end, 0.6, _line(text, r.start()))
    skills = find_skills(re.sub(r"(?i)\S*(?:https?://|www\.|\.com/)\S*", " ", text))  # links are not skills
    if skills:
        add("skills", "verified_skills", skills[:40], 0.6, f"{len(skills)} skills mentioned in your CV")
    return suggestions
