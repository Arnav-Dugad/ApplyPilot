"""Derived intelligence: duplicates, learned preferences, coaching, profile strength, search, health, and Today."""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .countries import _LOOKUP as _COUNTRY_ALIASES
from .eligibility import evaluate
from .safety import normalize
from .scoring import EUROPE, GCC, INTERNSHIP_TITLE, job_country
from .skills import canonical, find_skills

SEASON = re.compile(r"\b(spring|summer|fall|autumn|winter)\b|\b20\d{2}\b|\b(internship|intern|co op|placement)\b")
COMPANY_SUFFIX = re.compile(r"\b(inc|incorporated|llc|ltd|limited|plc|gmbh|ag|sa|bv|co|corp|corporation|company|group|technologies|technology|labs|holdings|india|global)\b")
TITLE_STOPWORDS = {"and", "of", "the", "for", "to", "in", "at", "a", "an", "with", "team", "role", "position", "new", "grad"}


# ---------- duplicates ----------

def company_key(name: str | None) -> str:
    key = COMPANY_SUFFIX.sub(" ", normalize(name or ""))
    return re.sub(r"\s+", " ", key).strip()


def fingerprint(job: dict[str, Any]) -> str:
    """Same company + same title (ignoring season/year/intern words) + same country = the same opening."""
    title = SEASON.sub(" ", normalize(job.get("role") or ""))
    title = " ".join(t for t in title.split() if t not in TITLE_STOPWORDS)
    return f"{company_key(job.get('company'))}|{title}|{job_country(job) or ''}"


# ---------- learned preferences ----------

def job_features(job: dict[str, Any]) -> list[str]:
    title = SEASON.sub(" ", normalize(job.get("role") or ""))
    features = [f"company:{company_key(job.get('company'))}", f"country:{job_country(job) or 'unknown'}", f"platform:{job.get('application_platform') or 'GENERIC'}"]
    features += [f"title:{t}" for t in title.split() if t not in TITLE_STOPWORDS and len(t) > 2]
    features += [f"skill:{canonical(s)}" for s in (job.get("required_skills") or [])[:8]]
    return features


def learn_preferences(votes: list[tuple[dict[str, Any], int]]) -> dict[str, float]:
    """Naive-Bayes-style log odds per feature from 👍/👎 votes, with add-one smoothing. Needs a few votes to matter."""
    if len(votes) < 3:
        return {}
    likes, dislikes = Counter(), Counter()
    for job, vote in votes:
        for feature in set(job_features(job)):
            (likes if vote > 0 else dislikes)[feature] += 1
    total_like = sum(1 for _, v in votes if v > 0) + 1
    total_dislike = sum(1 for _, v in votes if v < 0) + 1
    return {f: math.log(((likes[f] + 1) / (total_like + 1)) / ((dislikes[f] + 1) / (total_dislike + 1))) for f in set(likes) | set(dislikes)}


def preference_points(job: dict[str, Any], weights: dict[str, float], limit: float = 5.0) -> tuple[float, list[str]]:
    """Score adjustment in [-limit, +limit] plus the strongest reasons, e.g. 'you liked Stripe roles'."""
    if not weights:
        return 0.0, []
    contributions = [(weights[f], f) for f in job_features(job) if f in weights]
    if not contributions:
        return 0.0, []
    raw = sum(w for w, _ in contributions)
    points = round(limit * math.tanh(raw / 2.5), 1)
    top = sorted(contributions, key=lambda c: -abs(c[0]))[:2]
    reasons = [_reason(f, w) for w, f in top if abs(w) > 0.3]
    return points, reasons


def _reason(feature: str, weight: float) -> str:
    kind, value = feature.split(":", 1)
    verb = "You liked" if weight > 0 else "You passed on"
    if kind == "company":
        return f"{verb} {value.title()} roles"
    if kind == "country":
        return f"{verb} roles in {value}"
    if kind == "skill":
        return f"{verb} roles needing {value}"
    if kind == "platform":
        return f"{verb} {value.title()} postings"
    return f"{verb} “{value}” roles"


# ---------- coach ----------

def coach(jobs: list[dict[str, Any]], facts: list[dict[str, Any]], min_score: int) -> list[dict[str, Any]]:
    """Which single addition would unlock the most jobs: a skill you could learn, or a fact you could verify."""
    open_jobs = [j for j in jobs if j.get("eligibility_result") and not j.get("duplicate_of")]
    missing_skills: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for job in open_jobs:
        for skill in (job.get("eligibility_match") or {}).get("missing", []):
            missing_skills[skill] += 1
            if len(examples[skill]) < 3:
                examples[skill].append(f"{job.get('role')} · {job.get('company')}")
    tips: list[dict[str, Any]] = []
    for skill, count in missing_skills.most_common(12):
        unlocked = 0
        for job in open_jobs:
            match = job.get("eligibility_match") or {}
            if skill not in match.get("missing", []):
                continue
            before = job.get("eligibility_result")
            simulated = evaluate(job, facts + [{"category": "skills", "fact_key": f"coach_{skill}", "value": [skill], "status": "VERIFIED", "country_code": None}])
            if simulated["result"] == "ELIGIBLE" and before != "ELIGIBLE":
                unlocked += 1
        tips.append({"kind": "SKILL", "name": skill, "jobs": count, "unlocks": unlocked, "examples": examples[skill]})
    blocked_by: Counter[str] = Counter()
    for job in open_jobs:
        for check in job.get("eligibility_checks") or []:
            if check.get("result") == "UNKNOWN":
                label = check["name"]
                if label in {"Work authorization", "Sponsorship"}:
                    label = f"{label} in {job.get('country') or 'unknown country'}"
                blocked_by[label] += 1
    for label, count in blocked_by.most_common(6):
        tips.append({"kind": "FACT", "name": label, "jobs": count, "unlocks": count, "examples": []})
    return sorted(tips, key=lambda t: (-t["unlocks"], -t["jobs"]))[:12]


# ---------- profile strength ----------

STRENGTH_ITEMS = [
    ("personal", "full_name", "Legal name", 10), ("contact", "email", "Email", 8), ("contact", "phone", "Phone", 7), ("contact", "linkedin", "LinkedIn", 6),
    ("education", "university", "University", 8), ("education", "degree", "Field of study", 5), ("education", "degree_name", "Degree", 6), ("education", "graduation_date", "Graduation date", 8),
    ("education", "year_of_study", "Year of study", 4), ("education", "cgpa", "CGPA", 4), ("citizenship", "countries", "Citizenship", 10), ("contact", "github", "GitHub", 4),
    ("preferences", "locations", "Places you'd work", 6), ("preferences", "roles", "Kinds of roles", 4), ("preferences", "availability", "When you're free", 4),
    ("languages", "spoken", "Languages", 5), ("contact", "location", "Current city", 4),
]


def profile_strength(facts: list[dict[str, Any]], approved_cv: bool) -> dict[str, Any]:
    verified = {(f["category"], f["fact_key"]) for f in facts if f.get("status") == "VERIFIED"}
    skills = next((f.get("value") for f in facts if f["category"] == "skills" and f.get("status") == "VERIFIED" and isinstance(f.get("value"), list)), []) or []
    items = [{"label": label, "points": pts, "done": (cat, key) in verified} for cat, key, label, pts in STRENGTH_ITEMS]
    items.append({"label": "5+ verified skills", "points": 10, "done": len(skills) >= 5})
    items.append({"label": "Your experience (or “none yet”)", "points": 6, "done": any(f["category"] == "experience" and f.get("status") == "VERIFIED" for f in facts)})
    items.append({"label": "A project", "points": 5, "done": any(f["category"] == "projects" and f.get("status") == "VERIFIED" for f in facts)})
    items.append({"label": "Approved CV", "points": 8, "done": approved_cv})
    total = sum(i["points"] for i in items)
    earned = sum(i["points"] for i in items if i["done"])
    return {"percent": round(100 * earned / total), "next": [i for i in items if not i["done"]][:3], "items": items}


# ---------- natural-language search ----------

REGION_WORDS = {"europe": EUROPE, "eu": EUROPE, "gcc": GCC, "gulf": GCC, "middle east": GCC | {"JO", "LB", "EG"}, "uk": {"GB"}, "usa": {"US"}, "us": {"US"}, "asia": {"SG", "IN", "JP", "HK", "KR", "CN", "MY", "ID", "TH", "VN", "PH", "TW"}}
ROLE_WORDS = {"backend", "frontend", "front end", "back end", "full stack", "fullstack", "data", "ml", "machine learning", "ai", "security", "mobile", "ios", "android", "cloud", "devops",
              "infrastructure", "platform", "product", "design", "research", "quant", "trading", "embedded", "hardware", "firmware", "analyst", "finance", "marketing", "sales", "operations"}
FILLER = {"roles", "role", "jobs", "job", "internships", "internship", "intern", "with", "in", "at", "for", "and", "or", "the", "a", "an", "using", "that", "use", "show", "me", "find", "any", "positions", "remote"}


def parse_query(query: str) -> dict[str, Any]:
    text = " " + normalize(query) + " "
    skills = find_skills(query)
    countries: set[str] = set()
    labels: list[str] = []
    for word, codes in REGION_WORDS.items():
        if f" {word} " in text:
            countries |= codes
            labels.append(word.upper() if len(word) <= 3 else word.title())
            text = text.replace(f" {word} ", " ")
    place_words: set[str] = set()
    for name in sorted(_COUNTRY_ALIASES, key=len, reverse=True):  # longest first: "new zealand" before "zealand"
        if f" {name} " in text:
            countries.add(_COUNTRY_ALIASES[name])
            place_words.update(name.split())
            text = text.replace(f" {name} ", " ")
            label = name.upper() if len(name) <= 3 else name.title()
            if label not in labels:
                labels.append(label)
    roles = sorted({w for w in ROLE_WORDS if f" {w} " in f" {normalize(query)} "})
    skill_words = {w for s in skills for w in normalize(s).split()}
    role_words = {r for role in roles for r in role.split()}
    region_words = {w for region in REGION_WORDS for w in region.split()}
    words = [w for w in normalize(query).split() if w not in FILLER | skill_words | role_words | place_words | region_words]
    return {"skills": skills, "countries": sorted(countries), "places": labels, "roles": roles, "remote": " remote " in f" {normalize(query)} ", "keywords": words}


def search(jobs: list[dict[str, Any]], query: str) -> dict[str, Any]:
    parsed = parse_query(query)
    results = []
    for job in jobs:
        if job.get("duplicate_of"):
            continue
        haystack = normalize(f"{job.get('role')} {job.get('company')} {job.get('location')} {job.get('description', '')[:3000]}")
        title = normalize(job.get("role") or "")
        job_skills = {canonical(s) for s in (job.get("required_skills") or []) + (job.get("preferred_skills") or [])}
        code = job_country(job)
        if parsed["countries"] and code not in parsed["countries"] and not (parsed["remote"] and "remote" in haystack):
            continue
        if parsed["remote"] and not parsed["countries"] and "remote" not in haystack:
            continue
        relevance = 0.0
        for skill in parsed["skills"]:
            relevance += 3 if skill in job_skills else 1 if skill in haystack else 0
        for role in parsed["roles"]:
            relevance += 4 if role in title else 1.5 if role in haystack else 0
        for word in parsed["keywords"]:
            relevance += 2 if word in title else 0.5 if word in haystack else 0
        wanted = len(parsed["skills"]) + len(parsed["roles"]) + len(parsed["keywords"])
        if wanted and relevance == 0:
            continue
        results.append((relevance + (job.get("score") or {}).get("score", 0) / 50, job["id"]))
    results.sort(reverse=True)
    return {"parsed": parsed, "ids": [job_id for _, job_id in results]}


# ---------- health & today ----------

def _days_until(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (stamp - datetime.now(timezone.utc)).total_seconds() / 86400


def health(watchlist: list[dict[str, Any]], jobs: list[dict[str, Any]], apps: list[dict[str, Any]], facts: list[dict[str, Any]], answers: list[dict[str, Any]], has_cv: bool, email: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    failing = [w["company"] for w in watchlist if str(w.get("last_status") or "").startswith("Error")]
    if failing:
        issues.append({"level": "warn", "title": f"{len(failing)} job board{'s' if len(failing) > 1 else ''} failing", "detail": ", ".join(failing[:5]), "page": "Autopilot"})
    queued = {a["job_id"]: a for a in apps if a["status"] in {"QUEUED", "NEEDS_INFO", "WAITING_FOR_USER", "READY_FOR_REVIEW"}}
    closed = [j for j in jobs if j["id"] in queued and (_days_until(j.get("deadline")) or 1) < 0]
    if closed:
        issues.append({"level": "bad", "title": f"{len(closed)} queued job{'s' if len(closed) > 1 else ''} past the deadline", "detail": ", ".join(f"{j['company']}" for j in closed[:4]), "page": "Queue"})
    stale = [j for j in jobs if (_days_until(j.get("date_posted")) or 0) < -45 and j["id"] in queued]
    if stale:
        issues.append({"level": "info", "title": f"{len(stale)} queued posting{'s' if len(stale) > 1 else ''} older than 45 days", "detail": "They may have closed quietly — check before applying.", "page": "Queue"})
    grad = next((f for f in facts if f["category"] == "education" and f["fact_key"] == "graduation_date" and f.get("status") == "VERIFIED"), None)
    if grad and isinstance(grad.get("value"), str) and re.fullmatch(r"20\d{2}(-\d{2})?", grad["value"]) and (_days_until(grad["value"] + ("-28" if len(grad["value"]) == 7 else "-12-31")) or 1) < 0:
        issues.append({"level": "warn", "title": "Your graduation date has passed", "detail": f"Verified as {grad['value']}. Update it if your plans changed.", "page": "Profile"})
    old = [f for f in facts if f.get("status") == "VERIFIED" and (_days_until(f.get("last_confirmed")) or 0) < -365]
    if old:
        issues.append({"level": "info", "title": f"{len(old)} fact{'s' if len(old) > 1 else ''} not confirmed in over a year", "detail": ", ".join(f["fact_key"].replace("_", " ") for f in old[:4]), "page": "Profile"})
    expired = [a for a in answers if a.get("status") in {"EXPIRED", "UNVERIFIED"}]
    if expired:
        issues.append({"level": "info", "title": f"{len(expired)} saved answer{'s' if len(expired) > 1 else ''} not in use", "detail": "Expired or never approved.", "page": "Answer Vault"})
    if not has_cv:
        issues.append({"level": "warn", "title": "No approved CV", "detail": "Résumé fields pause until you approve one.", "page": "CV Library"})
    if email.get("enabled") and email.get("last_error"):
        issues.append({"level": "warn", "title": "Email sync failing", "detail": email["last_error"], "page": "Settings"})
    return issues


def today(jobs: list[dict[str, Any]], apps: list[dict[str, Any]], inbox: dict[str, Any], drafts_due: int) -> list[dict[str, Any]]:
    """The five highest-value things to do right now, most valuable first."""
    by_id = {j["id"]: j for j in jobs}
    actions: list[dict[str, Any]] = []
    for app in apps:
        job = by_id.get(app["job_id"], {})
        days = _days_until(job.get("deadline"))
        if app["status"] in {"READY_FOR_REVIEW", "WAITING_FOR_USER", "QUEUED", "NEEDS_INFO"} and days is not None and 0 <= days <= 3:
            actions.append({"value": 100 - days * 10, "kind": "DEADLINE", "title": f"{job.get('company')} closes in {max(1, round(days * 24))}h", "detail": job.get("role"), "page": "Queue", "job_id": job.get("id")})
    # Never suggest submitting something the posting now rules you out of.
    ready = [a for a in apps if a["status"] == "READY_FOR_REVIEW" and by_id.get(a["job_id"], {}).get("eligibility_result") != "INELIGIBLE"]
    for app in ready[:3]:
        actions.append({"value": 80 + (by_id.get(app["job_id"], {}).get("score") or {}).get("score", 0) / 10, "kind": "SUBMIT", "title": f"Submit {app.get('role')}", "detail": f"{app.get('company')} · every field is filled", "page": "Queue", "job_id": app["job_id"]})
    required = [q for q in inbox.get("questions", []) if q.get("required")]
    if required:
        unlocks = len({a["id"] for q in required for a in q["applications"]})
        actions.append({"value": 70 + unlocks * 3, "kind": "INBOX", "title": f"Answer {len(required)} question{'s' if len(required) > 1 else ''}", "detail": f"Unlocks {unlocks} application{'s' if unlocks != 1 else ''}", "page": "Inbox"})
    interviews = [a for a in apps if a["status"] == "INTERVIEWING"]
    for app in interviews[:2]:
        actions.append({"value": 75, "kind": "PREP", "title": f"Prepare for {app.get('company')}", "detail": "Open your interview prep pack", "page": "Tracker", "job_id": app["job_id"]})
    if drafts_due:
        actions.append({"value": 55, "kind": "FOLLOW_UP", "title": f"Send {drafts_due} follow-up{'s' if drafts_due > 1 else ''}", "detail": "Two weeks since you applied", "page": "Inbox"})
    if inbox.get("suggestions"):
        actions.append({"value": 40, "kind": "SUGGESTIONS", "title": f"Confirm {len(inbox['suggestions'])} profile suggestion{'s' if len(inbox['suggestions']) > 1 else ''}", "detail": "From your CV", "page": "Inbox"})
    strong = [j for j in jobs if (j.get("score") or {}).get("score", 0) >= 80 and not j.get("duplicate_of") and j["id"] not in {a["job_id"] for a in apps}]
    if strong:
        actions.append({"value": 50, "kind": "DISCOVER", "title": f"Review {len(strong)} strong match{'es' if len(strong) > 1 else ''}", "detail": "Score 80+ and not queued yet", "page": "Discover"})
    return sorted(actions, key=lambda a: -a["value"])[:5]


def deadline_alerts(jobs: list[dict[str, Any]], apps: list[dict[str, Any]], hours: float = 72) -> list[dict[str, Any]]:
    by_id = {j["id"]: j for j in jobs}
    alerts = []
    for app in apps:
        if app["status"] not in {"QUEUED", "NEEDS_INFO", "WAITING_FOR_USER", "READY_FOR_REVIEW"}:
            continue
        job = by_id.get(app["job_id"]) or {}
        days = _days_until(job.get("deadline"))
        if days is not None and 0 <= days * 24 <= hours:
            alerts.append({"application_id": app["id"], "company": job.get("company"), "role": job.get("role"), "hours": round(days * 24)})
    return alerts


def is_internship(job: dict[str, Any]) -> bool:
    return bool(INTERNSHIP_TITLE.search(job.get("role") or "")) or "intern" in str(job.get("employment_type") or "").lower()


def as_json(value: Any) -> str:
    return json.dumps(value, default=str)
