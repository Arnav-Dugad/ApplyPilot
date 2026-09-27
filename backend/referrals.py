"""LinkedIn connections import and referral matching. The CSV never leaves this computer."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from .insights import company_key

HEADER = ["First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On"]


def parse_connections_csv(text: str) -> list[dict[str, str]]:
    """LinkedIn's Connections.csv starts with a few 'Notes:' lines before the real header row."""
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("First Name,") and "Company" in line), None)
    if start is None:
        raise ValueError("This doesn't look like LinkedIn's Connections.csv (Settings → Data privacy → Get a copy of your data → Connections)")
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    rows = []
    for row in reader:
        company = (row.get("Company") or "").strip()
        first, last = (row.get("First Name") or "").strip(), (row.get("Last Name") or "").strip()
        if not (first or last):
            continue
        url = (row.get("URL") or "").strip()
        rows.append({
            "first_name": first, "last_name": last, "url": url if re.match(r"^https://(www\.)?linkedin\.com/", url) else "",
            "email": (row.get("Email Address") or "").strip(), "company": company, "company_key": company_key(company),
            "position": (row.get("Position") or "").strip(), "connected_on": (row.get("Connected On") or "").strip(),
        })
    return rows


def matches(company: str | None, connections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """People whose current company is this employer. Exact key match, or one key fully containing the other ("Google" vs "Google DeepMind")."""
    key = company_key(company)
    if not key:
        return []
    found = []
    for person in connections:
        other = person.get("company_key") or ""
        if not other:
            continue
        if other == key or (len(key) >= 4 and (f" {key} " in f" {other} " or f" {other} " in f" {key} ")):
            found.append(person)
    return sorted(found, key=lambda p: (not re.search(r"(?i)recruit|talent|hiring|university|campus", p.get("position") or ""), p.get("last_name") or ""))


def referral_message(person: dict[str, Any], job: dict[str, Any], sender: str | None) -> str:
    """A short, honest referral request. It says only what's true: the role, the link, and who's asking."""
    first = person.get("first_name") or "there"
    role, company = job.get("role") or "an internship", job.get("company") or "your company"
    link = job.get("posting_url") or ""
    sign = f"\n\nThanks so much,\n{sender}" if sender else "\n\nThanks so much!"
    return (f"Hi {first},\n\nI hope you're doing well! I'm applying for the {role} role at {company}"
            f"{' (' + link + ')' if link else ''} and would really value your perspective on the team. "
            f"If you think I could be a good fit, would you be open to referring me? I'm happy to send my CV and a short summary to make it easy.{sign}")
