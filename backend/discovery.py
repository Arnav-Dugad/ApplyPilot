"""Scans companies' public ATS job boards (Greenhouse, Lever, Ashby, SmartRecruiters) for internships.

These are the official, unauthenticated JSON feeds each platform publishes for career sites.
Everything they return is untrusted text: it is stripped of markup and prompt-injection lines
before it is stored, and it never becomes a profile fact.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from .job_parser import _OPENER
from .safety import strip_prompt_injection
from .scoring import INTERNSHIP_TITLE

USER_AGENT = "ApplyPilot/0.3 (personal internship organizer; public job board feed)"
PLATFORMS = ("GREENHOUSE", "LEVER", "ASHBY", "SMARTRECRUITERS")

# Boards verified live on 2026-09-27. Users can follow any other board by pasting its URL.
CATALOG: list[dict[str, str]] = [
    {"platform": "GREENHOUSE", "slug": s, "company": c} for s, c in [
        ("stripe", "Stripe"), ("databricks", "Databricks"), ("robinhood", "Robinhood"), ("coinbase", "Coinbase"), ("figma", "Figma"),
        ("datadog", "Datadog"), ("lyft", "Lyft"), ("affirm", "Affirm"), ("anthropic", "Anthropic"), ("cloudflare", "Cloudflare"),
        ("mongodb", "MongoDB"), ("elastic", "Elastic"), ("samsara", "Samsara"), ("toast", "Toast"), ("roblox", "Roblox"),
        ("duolingo", "Duolingo"), ("reddit", "Reddit"), ("airbnb", "Airbnb"), ("gitlab", "GitLab"), ("squarespace", "Squarespace"),
    ]
] + [
    {"platform": "LEVER", "slug": s, "company": c} for s, c in [("palantir", "Palantir"), ("shieldai", "Shield AI"), ("binance", "Binance"), ("spotify", "Spotify")]
] + [
    {"platform": "ASHBY", "slug": s, "company": c} for s, c in [("openai", "OpenAI"), ("ramp", "Ramp"), ("notion", "Notion"), ("perplexity", "Perplexity"), ("cohere", "Cohere")]
] + [
    {"platform": "SMARTRECRUITERS", "slug": s, "company": c} for s, c in [("BoschGroup", "Bosch"), ("Continental", "Continental"), ("Wise", "Wise"), ("ServiceNow", "ServiceNow"), ("Canva", "Canva")]
]

_BOARD_URLS = [
    ("GREENHOUSE", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)")),
    ("GREENHOUSE", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)")),
    ("LEVER", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)")),
    ("ASHBY", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
    ("SMARTRECRUITERS", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
]


def detect_board(text: str) -> tuple[str, str] | None:
    """(platform, slug) from a careers URL or a "platform:slug" shorthand."""
    text = text.strip()
    shorthand = re.fullmatch(r"(?i)(greenhouse|lever|ashby|smartrecruiters)\s*[:/]\s*([A-Za-z0-9_.-]+)", text)
    if shorthand:
        return shorthand.group(1).upper(), shorthand.group(2)
    for platform, pattern in _BOARD_URLS:
        match = pattern.search(text)
        if match:
            return platform, urllib.parse.unquote(match.group(1))
    return None


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(html.unescape(value))
    text = re.sub(r"(?i)<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n• ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    clean, _ = strip_prompt_injection(text)
    return clean[:60_000]


def is_internship(title: str, employment_type: str | None = None) -> bool:
    return bool(INTERNSHIP_TITLE.search(title or "")) or "intern" in str(employment_type or "").lower()


def _get(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with _OPENER.open(request, timeout=25) as response:
            data = response.read(25_000_001)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("Board not found — check the company's careers URL") from exc
        raise ValueError(f"Job board returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach the job board: {exc.reason}") from exc
    if len(data) > 25_000_000:
        raise ValueError("Job board response is too large")
    return json.loads(data)


def _iso_ms(ms: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


GREENHOUSE_TYPES = {"input_text": "text", "textarea": "textarea", "input_file": "file", "multi_value_single_select": "select", "multi_value_multi_select": "multiselect", "input_hidden": "hidden"}


def greenhouse_questions(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """Real application form fields for a Greenhouse job, in dry-run field format."""
    fields: list[dict[str, Any]] = []
    groups = [(q, False) for q in detail.get("questions") or []] + [(q, True) for q in detail.get("location_questions") or []]
    for compliance in detail.get("compliance") or []:
        groups += [(q, True) for q in compliance.get("questions") or []]
    demographic = detail.get("demographic_questions") or {}
    groups += [({"label": q.get("label"), "required": q.get("required", False), "fields": [{"name": f"demographic_{q.get('id')}", "type": "multi_value_single_select", "values": [{"label": a.get("label")} for a in q.get("answer_options") or []]}]}, True) for q in demographic.get("questions") or []]
    for question, _secondary in groups:
        for f in question.get("fields") or []:
            kind = GREENHOUSE_TYPES.get(f.get("type"), "text")
            if kind == "hidden":
                continue
            name = str(f.get("name") or "")
            fields.append({
                "selector": f"#{name}" if name else "",
                "label": html_to_text(question.get("label") or name)[:300],
                "name": name,
                "field_type": kind,
                "required": bool(question.get("required")),
                "options": [html_to_text(str(v.get("label")))[:200] for v in f.get("values") or [] if v.get("label") is not None],
            })
    return fields


def _greenhouse(slug: str, internships_only: bool) -> tuple[str, list[dict[str, Any]], int]:
    listing = _get(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}/jobs")["jobs"]
    wanted = [j for j in listing if not internships_only or is_internship(j.get("title", ""))][:60]

    def detail(job: dict[str, Any]) -> dict[str, Any]:
        d = _get(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}/jobs/{job['id']}?questions=true")
        location = (d.get("location") or {}).get("name")
        return {
            "company": d.get("company_name") or slug, "role": d.get("title"), "location": location,
            "posting_url": d.get("absolute_url"), "application_url": f"https://job-boards.greenhouse.io/{slug}/jobs/{d['id']}",
            "date_posted": d.get("first_published") or d.get("updated_at"), "deadline": d.get("application_deadline"),
            "description": html_to_text(d.get("content")), "external_id": f"greenhouse:{slug}:{d['id']}",
            "requisition_id": d.get("requisition_id") if d.get("requisition_id") not in (None, "See Opening ID") else None,
            "board_questions": greenhouse_questions(d),
        }

    with ThreadPoolExecutor(6) as pool:
        jobs = list(pool.map(detail, wanted))
    company = jobs[0]["company"] if jobs else (listing[0].get("company_name") if listing else slug)
    return company, jobs, len(listing)


def _lever(slug: str, internships_only: bool) -> tuple[str, list[dict[str, Any]], int]:
    listing = _get(f"https://api.lever.co/v0/postings/{urllib.parse.quote(slug)}?mode=json")
    jobs = []
    for j in listing:
        categories = j.get("categories") or {}
        if internships_only and not is_internship(j.get("text", ""), categories.get("commitment")):
            continue
        sections = "\n\n".join(f"{s.get('text', '')}\n{html_to_text(s.get('content'))}" for s in j.get("lists") or [])
        jobs.append({
            "company": slug.replace("-", " ").title(), "role": j.get("text"), "location": categories.get("location"), "country": j.get("country"),
            "remote_status": "REMOTE" if str(j.get("workplaceType")).lower() == "remote" else None,
            "posting_url": j.get("hostedUrl"), "application_url": j.get("applyUrl") or j.get("hostedUrl"), "date_posted": _iso_ms(j.get("createdAt")),
            "description": "\n\n".join(x for x in (j.get("descriptionPlain"), sections, j.get("additionalPlain")) if x)[:60_000],
            "employment_type": categories.get("commitment"), "external_id": f"lever:{slug}:{j.get('id')}",
        })
    return slug.replace("-", " ").title(), jobs, len(listing)


def _ashby(slug: str, internships_only: bool) -> tuple[str, list[dict[str, Any]], int]:
    listing = _get(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(slug)}?includeCompensation=true")["jobs"]
    jobs = []
    for j in listing:
        if internships_only and not is_internship(j.get("title", ""), j.get("employmentType")):
            continue
        address = ((j.get("address") or {}).get("postalAddress") or {})
        jobs.append({
            "company": slug.replace("-", " ").title(), "role": j.get("title"), "location": j.get("location"), "country": address.get("addressCountry"),
            "remote_status": "REMOTE" if j.get("isRemote") else None, "posting_url": j.get("jobUrl"), "application_url": j.get("applyUrl") or j.get("jobUrl"),
            "date_posted": j.get("publishedAt"), "description": (j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")))[:60_000],
            "compensation": (j.get("compensation") or {}).get("compensationTierSummary"), "employment_type": j.get("employmentType"),
            "external_id": f"ashby:{slug}:{j.get('id')}",
        })
    return slug.replace("-", " ").title(), jobs, len(listing)


def _smartrecruiters(slug: str, internships_only: bool) -> tuple[str, list[dict[str, Any]], int]:
    base = f"https://api.smartrecruiters.com/v1/companies/{urllib.parse.quote(slug)}/postings"
    query = "&q=intern" if internships_only else ""
    listing = _get(f"{base}?limit=100{query}")
    total = int(listing.get("totalFound") or 0)
    posts = [p for p in listing.get("content") or [] if not internships_only or is_internship(p.get("name", ""), (p.get("typeOfEmployment") or {}).get("label")) or (p.get("experienceLevel") or {}).get("id") == "internship"][:40]

    def detail(post: dict[str, Any]) -> dict[str, Any]:
        d = _get(f"{base}/{post['id']}")
        sections = (d.get("jobAd") or {}).get("sections") or {}
        location = d.get("location") or {}
        return {
            "company": (d.get("company") or {}).get("name") or slug, "role": d.get("name"), "location": location.get("fullLocation") or location.get("city"),
            "country": location.get("country"), "remote_status": "REMOTE" if location.get("remote") else None,
            "posting_url": d.get("postingUrl"), "application_url": d.get("applyUrl") or d.get("postingUrl"), "date_posted": d.get("releasedDate"),
            "description": "\n\n".join(html_to_text((sections.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications", "additionalInformation", "companyDescription")).strip(),
            "employment_type": (d.get("typeOfEmployment") or {}).get("label"), "requisition_id": d.get("refNumber"), "external_id": f"smartrecruiters:{slug}:{d.get('id')}",
        }

    with ThreadPoolExecutor(6) as pool:
        jobs = list(pool.map(detail, posts))
    company = jobs[0]["company"] if jobs else ((listing.get("content") or [{}])[0].get("company") or {}).get("name", slug)
    return company, jobs, total


FETCHERS = {"GREENHOUSE": _greenhouse, "LEVER": _lever, "ASHBY": _ashby, "SMARTRECRUITERS": _smartrecruiters}


def fetch_board(platform: str, slug: str, *, internships_only: bool = True) -> dict[str, Any]:
    """Normalized jobs from one public board: {company, jobs, total}."""
    if platform not in FETCHERS:
        raise ValueError(f"Unsupported job board: {platform}")
    company, jobs, total = FETCHERS[platform](slug, internships_only)
    for job in jobs:
        job.update({"source": f"{platform.title()} board", "application_platform": platform, "extraction_status": "BOARD_API"})
        job["description"] = (job.get("description") or "").strip()
    return {"company": company, "jobs": [j for j in jobs if j.get("role") and j.get("posting_url")], "total": total}
