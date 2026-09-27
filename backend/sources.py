"""Worldwide internship sources beyond the companies you follow.

Each source is a free, public feed that allows automated reading. Sites that forbid scraping
(LinkedIn, Indeed, Internshala, Glassdoor) are never touched. Everything returned is untrusted text.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .countries import country_key
from .discovery import _get, greenhouse_questions, html_to_text, is_internship
from .scoring import job_country

REMOTE = re.compile(r"(?i)\bremote\b|\banywhere\b|\bwork from home\b")
MAX_AGE_DAYS = 120


def location_country(location: str | None) -> str | None:
    """ISO code for a location line: 'Palo Alto, CA' -> US (California, not Canada), 'Toronto, ON' -> CA."""
    text = str(location or "").strip()
    if not text:
        return None
    code = job_country({"location": text})
    return code if code and len(code) == 2 and code.isupper() else None


def _unix(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _fresh(iso: str | None, days: int = MAX_AGE_DAYS) -> bool:
    if not iso:
        return True
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - stamp <= timedelta(days=days)


def _job(**fields: Any) -> dict[str, Any]:
    locations = [l for l in fields.pop("locations", None) or [] if l]
    if locations and not fields.get("location"):
        fields["location"] = "; ".join(locations[:6]) + (f" (+{len(locations) - 6} more)" if len(locations) > 6 else "")
    fields["locations"] = locations or ([fields["location"]] if fields.get("location") else [])
    if not fields.get("remote_status") and any(REMOTE.search(l) for l in fields["locations"]):
        fields["remote_status"] = "REMOTE"
    return fields


# ---------- sources ----------

SIMPLIFY_URLS = [
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/main/.github/scripts/listings.json",
]


def simplify() -> list[dict[str, Any]]:
    """The community-maintained Simplify internship list: thousands of live openings across every company."""
    error: Exception | None = None
    for url in SIMPLIFY_URLS:
        try:
            listings = _get(url)
            break
        except ValueError as exc:
            error = exc
    else:
        raise error or ValueError("Simplify list unavailable")
    jobs = []
    for item in listings:
        if not item.get("active") or not item.get("is_visible", True) or not item.get("url"):
            continue
        posted = _unix(item.get("date_posted"))
        if not _fresh(posted, 200):
            continue
        jobs.append(_job(
            company=item.get("company_name"), role=item.get("title"), locations=item.get("locations") or [],
            posting_url=item["url"], application_url=item["url"], date_posted=posted, description="",
            external_id=f"simplify:{item.get('id') or item['url']}", employment_type="Internship",
            listing={"terms": item.get("terms") or [], "sponsorship": item.get("sponsorship"), "degrees": item.get("degrees") or [], "category": item.get("category")},
        ))
    return jobs


def hacker_news() -> list[dict[str, Any]]:
    """This month's 'Ask HN: Who is hiring?' thread — mostly startups, many remote, some hiring interns."""
    stories = _get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=5")["hits"]
    story = next((s for s in stories if "who is hiring" in s.get("title", "").lower()), None)
    if not story:
        return []
    thread = _get(f"https://hn.algolia.com/api/v1/items/{story['objectID']}")
    jobs = []
    for comment in thread.get("children") or []:
        raw = comment.get("text") or ""
        text = html_to_text(raw)
        if not re.search(r"(?i)\b(intern|interns|internship|internships|co-?op)\b", text):
            continue
        first = text.split("\n", 1)[0]
        parts = [p.strip() for p in re.split(r"\s+\|\s+", first) if p.strip()]
        if len(parts) < 2:
            continue
        company = re.sub(r"\s*\(.*?\)\s*", " ", parts[0]).strip()[:80]
        role = next((p for p in parts[1:] if re.search(r"(?i)\bintern", p)), None) or next((p for p in parts[1:] if re.search(r"(?i)engineer|developer|scientist|designer", p)), "Internship")
        if not re.search(r"(?i)\bintern", role):
            role = f"{role} (internships mentioned)"
        location = next((p for p in parts[1:] if REMOTE.search(p) or re.search(r"(?i)onsite|hybrid|,", p) or location_country(p)), None)
        link = re.search(r'href="([^"]+)"', raw)
        url = html.unescape(link.group(1)) if link else f"https://news.ycombinator.com/item?id={comment['id']}"
        jobs.append(_job(
            company=company, role=role[:140], location=location, posting_url=url if link else f"https://news.ycombinator.com/item?id={comment['id']}",
            application_url=url, date_posted=comment.get("created_at"), description=text, external_id=f"hn:{comment['id']}",
            remote_status="REMOTE" if location and REMOTE.search(location) else None,
        ))
    return jobs


def arbeitnow(pages: int = 4) -> list[dict[str, Any]]:
    """Arbeitnow: jobs across Germany and Europe, many in English, including Praktikum and Werkstudent roles."""
    jobs = []
    for page in range(1, pages + 1):
        data = _get(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        for item in data.get("data") or []:
            if not is_internship(item.get("title", ""), " ".join(item.get("job_types") or [])):
                continue
            jobs.append(_job(
                company=item.get("company_name"), role=item.get("title"), location=item.get("location"), country=location_country(item.get("location")) or "DE",
                posting_url=item.get("url"), application_url=item.get("url"), date_posted=_unix(item.get("created_at")),
                description=html_to_text(item.get("description")), external_id=f"arbeitnow:{item.get('slug')}",
                remote_status="REMOTE" if item.get("remote") else None, employment_type=", ".join(item.get("job_types") or []) or None,
            ))
        if not (data.get("links") or {}).get("next"):
            break
    return jobs


def the_muse(pages: int = 12) -> list[dict[str, Any]]:
    """The Muse: internships at thousands of companies, newest first."""
    def page(n: int) -> list[dict[str, Any]]:
        try:
            return _get(f"https://www.themuse.com/api/public/jobs?level=Internship&descending=true&page={n}").get("results") or []
        except ValueError:
            return []

    with ThreadPoolExecutor(4) as pool:
        results = [r for batch in pool.map(page, range(pages)) for r in batch]
    jobs = []
    for item in results:
        if not _fresh(item.get("publication_date")):
            continue
        jobs.append(_job(
            company=(item.get("company") or {}).get("name"), role=item.get("name"), locations=[l.get("name") for l in item.get("locations") or []],
            posting_url=(item.get("refs") or {}).get("landing_page"), application_url=(item.get("refs") or {}).get("landing_page"),
            date_posted=item.get("publication_date"), description=html_to_text(item.get("contents")), external_id=f"themuse:{item.get('id')}", employment_type="Internship",
        ))
    return jobs


def himalayas(pages: int = 5) -> list[dict[str, Any]]:
    """Himalayas: remote internships, with the countries each one hires from."""
    jobs = []
    for n in range(1, pages + 1):
        data = _get(f"https://himalayas.app/jobs/api/search?q=intern&page={n}")
        items = data.get("jobs") or []
        for item in items:
            if not is_internship(item.get("title", ""), item.get("employmentType")):
                continue
            allowed = item.get("locationRestrictions") or []
            jobs.append(_job(
                company=item.get("companyName"), role=item.get("title"), location="Remote" + (f" ({', '.join(allowed[:4])})" if allowed else " (worldwide)"),
                country=country_key(allowed[0]) if len(allowed) == 1 else None, remote_status="REMOTE",
                posting_url=item.get("applicationLink") or item.get("guid"), application_url=item.get("applicationLink") or item.get("guid"),
                date_posted=_unix(item.get("pubDate")), description=html_to_text(item.get("description")), external_id=f"himalayas:{item.get('guid')}",
                employment_type=item.get("employmentType"), listing={"remote_countries": allowed},
            ))
        if len(items) < 20:
            break
    return jobs


def jobicy() -> list[dict[str, Any]]:
    """Jobicy: remote jobs, filtered to internships."""
    data = _get("https://jobicy.com/api/v2/remote-jobs?count=50&tag=intern")
    jobs = []
    for item in data.get("jobs") or []:
        if not is_internship(item.get("jobTitle", ""), " ".join(item.get("jobType") or [])) and "intern" not in str(item.get("jobLevel", "")).lower():
            continue
        jobs.append(_job(
            company=item.get("companyName"), role=item.get("jobTitle"), location=f"Remote ({item.get('jobGeo')})" if item.get("jobGeo") else "Remote",
            remote_status="REMOTE", posting_url=item.get("url"), application_url=item.get("url"), date_posted=item.get("pubDate"),
            description=html_to_text(item.get("jobDescription")), external_id=f"jobicy:{item.get('id')}",
        ))
    return jobs


def remotive() -> list[dict[str, Any]]:
    """Remotive: remote jobs, filtered to internships."""
    data = _get("https://remotive.com/api/remote-jobs?search=intern&limit=100")
    jobs = []
    for item in data.get("jobs") or []:
        if not is_internship(item.get("title", ""), item.get("job_type")):
            continue
        jobs.append(_job(
            company=item.get("company_name"), role=item.get("title"), location=f"Remote ({item.get('candidate_required_location')})",
            remote_status="REMOTE", posting_url=item.get("url"), application_url=item.get("url"), date_posted=item.get("publication_date"),
            description=html_to_text(item.get("description")), external_id=f"remotive:{item.get('id')}",
        ))
    return jobs


SOURCES: dict[str, dict[str, Any]] = {
    "SIMPLIFY": {"name": "Simplify internship list", "about": "Thousands of internships at companies worldwide, updated daily by the community.", "fetch": simplify},
    "THE_MUSE": {"name": "The Muse", "about": "Internships at thousands of companies, mostly in the US.", "fetch": the_muse},
    "ARBEITNOW": {"name": "Arbeitnow", "about": "Internships and working-student jobs across Germany and Europe.", "fetch": arbeitnow},
    "HIMALAYAS": {"name": "Himalayas", "about": "Remote internships, with the countries each one hires from.", "fetch": himalayas},
    "HN": {"name": "Hacker News hiring thread", "about": "Startups hiring this month, many remote.", "fetch": hacker_news},
    "JOBICY": {"name": "Jobicy", "about": "Remote internships.", "fetch": jobicy},
    "REMOTIVE": {"name": "Remotive", "about": "Remote internships.", "fetch": remotive},
}
SOURCE_DEFAULTS = {key: True for key in SOURCES}


def fetch(key: str) -> list[dict[str, Any]]:
    jobs = SOURCES[key]["fetch"]()
    for job in jobs:
        job["source"] = key
        job.setdefault("country", None)
    return [j for j in jobs if j.get("company") and j.get("role") and j.get("posting_url")]


# ---------- filling in full descriptions from the company's own job board ----------

GREENHOUSE_JOB = re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)/jobs/(\d+)")
LEVER_JOB = re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)/([0-9a-f-]{36})")
ASHBY_JOB = re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)/([0-9a-f-]{36})")


def enrich(job: dict[str, Any], ashby_cache: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Adds the full description (and Greenhouse's form questions) for listings that only have a title.
    The external id becomes the board's own, so the same opening found by a followed company isn't saved twice."""
    url = job.get("posting_url") or ""
    if (m := GREENHOUSE_JOB.search(url)):
        slug, job_id = m.groups()
        d = _get(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}/jobs/{job_id}?questions=true")
        return {**job, "description": html_to_text(d.get("content")), "board_questions": greenhouse_questions(d), "external_id": f"greenhouse:{slug}:{job_id}",
                "application_url": f"https://job-boards.greenhouse.io/{slug}/jobs/{job_id}", "deadline": d.get("application_deadline")}
    if (m := LEVER_JOB.search(url)):
        slug, job_id = m.groups()
        d = _get(f"https://api.lever.co/v0/postings/{urllib.parse.quote(slug)}/{job_id}?mode=json")
        sections = "\n\n".join(f"{s.get('text', '')}\n{html_to_text(s.get('content'))}" for s in d.get("lists") or [])
        text = "\n\n".join(x for x in (d.get("descriptionPlain"), sections, d.get("additionalPlain")) if x)
        return {**job, "description": text[:60_000], "external_id": f"lever:{slug}:{job_id}", "application_url": d.get("applyUrl") or job.get("application_url")}
    if (m := ASHBY_JOB.search(url)):
        slug, job_id = m.groups()
        cache = ashby_cache if ashby_cache is not None else {}
        if slug not in cache:
            cache[slug] = _get(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(slug)}")["jobs"]
        d = next((j for j in cache[slug] if j.get("id") == job_id), None)
        if d:
            return {**job, "description": (d.get("descriptionPlain") or html_to_text(d.get("descriptionHtml")))[:60_000], "external_id": f"ashby:{slug}:{job_id}"}
    return job


def enrich_many(jobs: list[dict[str, Any]], limit: int = 60, progress: Callable[[int], None] | None = None) -> list[dict[str, Any]]:
    """Enriches up to `limit` title-only listings in parallel; failures keep the listing as it was."""
    cache: dict[str, list[dict[str, Any]]] = {}
    todo = [i for i, j in enumerate(jobs) if not j.get("description")][:limit]

    def one(i: int) -> tuple[int, dict[str, Any]]:
        try:
            return i, enrich(jobs[i], cache)
        except (ValueError, KeyError, TypeError):
            return i, jobs[i]

    out = list(jobs)
    with ThreadPoolExecutor(6) as pool:
        for n, (i, job) in enumerate(pool.map(one, todo), 1):
            out[i] = job
            if progress:
                progress(n)
    return out
