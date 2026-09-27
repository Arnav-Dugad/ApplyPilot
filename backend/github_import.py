"""Fills in a project from its public GitHub repository: description, languages, topics, skills, and the
highlights from its README. Only public data is read, through GitHub's official API."""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .skills import display, find_skills

API = "https://api.github.com"
HEADERS = {"User-Agent": "ApplyPilot (personal internship organizer)", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
REPO_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100}?)(?:\.git)?(?:[/?#].*)?$")
SHORT = re.compile(r"^([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})$")
USER_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})/?(?:[?#].*)?$")
# Topic and language names that GitHub spells differently from how CVs do.
ALIASES = {"javascript": "JavaScript", "typescript": "TypeScript", "cpp": "C++", "c++": "C++", "csharp": "C#", "c#": "C#", "golang": "Go", "go": "Go", "reactjs": "React", "react": "React",
           "nextjs": "Next.js", "nodejs": "Node.js", "node": "Node.js", "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mongodb": "MongoDB", "tensorflow": "TensorFlow",
           "pytorch": "PyTorch", "scikit-learn": "scikit-learn", "sklearn": "scikit-learn", "machine-learning": "Machine Learning", "deep-learning": "Deep Learning",
           "docker": "Docker", "kubernetes": "Kubernetes", "flask": "Flask", "django": "Django", "fastapi": "FastAPI", "html": "HTML", "css": "CSS", "jupyter-notebook": "Jupyter",
           "tailwindcss": "Tailwind CSS", "opencv": "OpenCV", "nlp": "NLP", "llm": "LLMs", "aws": "AWS", "gcp": "Google Cloud", "firebase": "Firebase", "flutter": "Flutter",
           "kotlin": "Kotlin", "swift": "Swift", "rust": "Rust", "java": "Java", "python": "Python", "c": "C", "shell": "Shell", "sql": "SQL", "mysql": "MySQL", "redis": "Redis"}
SKIP_LANGUAGES = {"Dockerfile", "Makefile", "Procfile", "Batchfile", "PowerShell", "CMake", "Roff", "SCSS", "Less"}


class GitHubError(ValueError):
    pass


def _get(path: str, *, raw: bool = False) -> Any:
    request = urllib.request.Request(API + path, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(5_000_001)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise GitHubError("GitHub couldn't find that. Check the link — private repositories can't be read.") from exc
        if exc.code in {403, 429} and exc.headers.get("X-RateLimit-Remaining") == "0":
            reset = exc.headers.get("X-RateLimit-Reset")
            when = datetime.fromtimestamp(int(reset), tz=timezone.utc).astimezone().strftime("%H:%M") if reset and reset.isdigit() else "an hour"
            raise GitHubError(f"GitHub allows 60 lookups an hour without signing in, and that's used up. Try again after {when}.") from exc
        raise GitHubError(f"GitHub returned an error (HTTP {exc.code}). Try again in a minute.") from exc
    except urllib.error.URLError as exc:
        raise GitHubError("Couldn't reach GitHub. Check your internet connection.") from exc
    return data if raw else json.loads(data)


def parse_repo(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    match = REPO_URL.match(text) or SHORT.match(text)
    if not match or match.group(2) in {"repositories", "settings", "orgs"}:
        raise GitHubError("Paste a repository link like https://github.com/you/project.")
    return match.group(1), match.group(2)


def parse_user(text: str) -> str:
    text = (text or "").strip().lstrip("@")
    match = USER_URL.match(text) or re.fullmatch(r"([A-Za-z0-9-]{1,39})", text)
    if not match:
        raise GitHubError("Paste your GitHub profile link or username.")
    return match.group(1)


def _clean_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)  # images and badges
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links keep their text
    text = re.sub(r"[*_`>#]+", "", text)
    return text


SETUP_HEADING = re.compile(r"(?i)install|download|setup|set up|getting started|usage|how to run|running|build|requirements|prerequisites|license|contribut|deploy|development|faq|credits|acknowledg|support|contact|changelog")
FEATURE_HEADING = re.compile(r"(?i)feature|highlight|what it does|what's inside|capabilit|overview|about")
STACK_HEADING = re.compile(r"(?i)tech|stack|built with|made with|tools|technolog|powered by|dependencies")


def readme_sections(markdown: str) -> list[tuple[str, list[str]]]:
    """[(heading, lines)] with code blocks removed."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_code = False
    for line in (markdown or "").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", line)
        if heading:
            sections.append((_clean_markdown(heading.group(1)).strip(), []))
        else:
            sections[-1][1].append(line.rstrip())
    return sections


def readme_highlights(markdown: str, limit: int = 4) -> tuple[str, list[str]]:
    """(first real paragraph, up to `limit` feature bullets) from a README. Setup and install steps are skipped."""
    paragraph = ""
    featured: list[str] = []
    other: list[str] = []
    for heading, lines in readme_sections(markdown):
        if SETUP_HEADING.search(heading) or STACK_HEADING.search(heading):
            continue
        for line in lines:
            stripped = line.strip()
            bullet = re.match(r"^[-*+]\s+(.+)$|^\d+[.)]\s+(.+)$", stripped)
            if bullet:
                item = _clean_markdown(bullet.group(1) or bullet.group(2)).strip(" :-")
                if 12 <= len(item) <= 180 and not re.search(r"(?i)^(npm|pip|git|cd|yarn|python|install|clone|run|download)\b|https?://|\.exe\b|\.zip\b", item):
                    (featured if FEATURE_HEADING.search(heading) else other).append(item)
            elif not paragraph and len(stripped) > 60 and not stripped.startswith(("|", "[!", "<", "!")):
                paragraph = re.sub(r"\s+", " ", _clean_markdown(stripped)).strip()
    return paragraph[:400], (featured or other)[:limit]


def readme_stack(markdown: str) -> str:
    """Text of the README's tech-stack section, where skill mentions are trustworthy."""
    return "\n".join("\n".join(lines) for heading, lines in readme_sections(markdown) if STACK_HEADING.search(heading))


def _skills(languages: dict[str, int], topics: list[str], text: str) -> list[str]:
    ordered: list[str] = []

    def add(name: str) -> None:
        if name and name.lower() not in {s.lower() for s in ordered}:
            ordered.append(name)

    total = sum(languages.values()) or 1
    for language, size in sorted(languages.items(), key=lambda kv: -kv[1]):
        if language not in SKIP_LANGUAGES and size / total >= 0.03:
            add(ALIASES.get(language.lower(), language))
    for topic in topics:
        if topic.lower() in ALIASES:
            add(ALIASES[topic.lower()])
    for skill in find_skills(text):
        add(ALIASES.get(skill.lower()) or display(skill))
    return ordered[:12]


def pretty_name(repo_name: str) -> str:
    """'landing-page' -> 'Landing Page', 'UsageNotch-Windows' -> 'UsageNotch Windows', 'ApplyPilot' stays."""
    words = [w for w in re.split(r"[-_\s]+", repo_name) if w]
    return " ".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words) or repo_name


def project(link: str) -> dict[str, Any]:
    """A project ready for Profile → Projects, filled in from GitHub."""
    owner, name = parse_repo(link)
    repo = _get(f"/repos/{owner}/{name}")
    languages = _get(f"/repos/{owner}/{name}/languages")
    try:
        readme_blob = _get(f"/repos/{owner}/{name}/readme")
        readme = base64.b64decode(readme_blob.get("content") or "").decode("utf-8", "replace")
    except GitHubError:
        readme = ""
    summary, bullets = readme_highlights(readme)
    topics = repo.get("topics") or []
    description = (repo.get("description") or "").strip() or summary
    return {
        "name": pretty_name(repo.get("name") or name),
        "description": description[:400],
        # README prose mentions many things; only the description and a "Tech stack" section count as skills used.
        "skills": _skills(languages, topics, f"{repo.get('description') or ''}\n{readme_stack(readme)[:8000]}"),
        "link": repo.get("html_url"),
        "homepage": repo.get("homepage") or None,
        "highlights": bullets,
        "topics": topics[:12],
        "languages": [l for l, _ in sorted(languages.items(), key=lambda kv: -kv[1]) if l not in SKIP_LANGUAGES][:6],
        "stars": repo.get("stargazers_count", 0),
        "started": (repo.get("created_at") or "")[:7] or None,
        "updated": (repo.get("pushed_at") or "")[:7] or None,
        "repo": repo.get("full_name"),
        "fork": bool(repo.get("fork")),
        "source": "GITHUB",
    }


def repositories(user: str) -> list[dict[str, Any]]:
    """Your own public repositories (no forks), most recently worked on first."""
    login = parse_user(user)
    repos = _get(f"/users/{login}/repos?per_page=100&sort=pushed&type=owner")
    return [{"repo": r["full_name"], "name": r["name"], "description": r.get("description") or "", "language": r.get("language"), "stars": r.get("stargazers_count", 0),
             "updated": (r.get("pushed_at") or "")[:10], "link": r["html_url"], "topics": (r.get("topics") or [])[:6]}
            for r in repos if not r.get("fork") and not r.get("archived")]
