from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any

from .eligibility import extract_skills
from .safety import strip_prompt_injection


class JobHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text: list[str] = []
        self.jsonld: list[dict[str, Any]] = []
        self._tag = ""
        self._script_type = ""
        self._script: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag = tag
        if tag == "script":
            self._script_type = dict(attrs).get("type") or ""
            self._script = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and "ld+json" in self._script_type:
            try:
                value = json.loads("".join(self._script))
                values = value if isinstance(value, list) else [value]
                self.jsonld.extend(x for x in values if isinstance(x, dict))
            except json.JSONDecodeError:
                pass
        self._tag = ""

    def handle_data(self, data: str) -> None:
        if self._tag == "title":
            self.title += data
        elif self._tag == "script":
            self._script.append(data)
        elif self._tag not in {"style", "noscript"} and data.strip():
            self.text.append(data.strip())


def _public_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) job URLs are allowed")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve {parsed.hostname}") from exc
    for info in addresses:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Private or local network addresses are blocked")


def _platform(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    for marker, name in (("greenhouse", "GREENHOUSE"), ("lever.co", "LEVER"), ("myworkdayjobs", "WORKDAY"), ("ashbyhq", "ASHBY"), ("smartrecruiters", "SMARTRECRUITERS")):
        if marker in host:
            return name
    return "GENERIC"


def requirement_sentences(description: str) -> dict[str, str | None]:
    """The first sentence mentioning each requirement, quoted verbatim, never paraphrased."""
    sentences = re.split(r"(?<=[.!?])\s+", description)
    first = lambda test: next((s for s in sentences if test(s.lower())), None)  # noqa: E731
    return {
        "degree_requirements": first(lambda s: "degree" in s),
        "graduation_requirements": first(lambda s: "graduat" in s),
        "work_authorization": first(lambda s: "authori" in s and "work" in s),
        "sponsorship_information": first(lambda s: "sponsor" in s),
    }


def parse_html(url: str, html: str) -> dict[str, Any]:
    parser = JobHTMLParser()
    parser.feed(html)
    posting = next((x for x in parser.jsonld if x.get("@type") == "JobPosting"), {})
    description = re.sub(r"<[^>]+>", " ", str(posting.get("description") or " ".join(parser.text)))
    description = re.sub(r"\s+", " ", description).strip()[:100_000]
    description, injections = strip_prompt_injection(description)
    title = posting.get("title") or parser.title.split("|")[0].strip() or None
    org = posting.get("hiringOrganization") or {}
    location = posting.get("jobLocation") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address", {}) if isinstance(location, dict) else {}
    country = address.get("addressCountry") if isinstance(address, dict) else None
    locality = address.get("addressLocality") if isinstance(address, dict) else None
    required, preferred = extract_skills(description)
    return {
        "company": org.get("name") if isinstance(org, dict) else None,
        "role": title,
        "location": ", ".join(x for x in (locality, country) if x) or None,
        "country": country,
        "remote_status": "REMOTE" if "remote" in description.lower() else "UNKNOWN",
        "posting_url": url,
        "application_url": url,
        "source": urllib.parse.urlparse(url).hostname or "URL_IMPORT",
        "date_posted": posting.get("datePosted"),
        "deadline": posting.get("validThrough"),
        "description": description,
        "required_skills": required,
        "preferred_skills": preferred,
        **requirement_sentences(description),
        "application_platform": _platform(url),
        "raw_snapshot": html[:500_000],
        "extraction_status": "UNVERIFIED",
        "security_warnings": injections,
    }


class _PublicOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Re-check every redirect hop so a public URL cannot bounce the importer onto the local network."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PublicOnlyRedirects)


def import_url(url: str) -> dict[str, Any]:
    url = url.strip()
    _public_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "ApplyPilot/0.2 (local personal job organizer)"})
    try:
        with _OPENER.open(request, timeout=15) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("The URL did not return an HTML page")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("Job page is too large to import safely")
            return parse_html(response.geturl(), data.decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429}:
            raise ValueError(f"This site blocked automated import (HTTP {exc.code}). Add the job manually instead.") from exc
        raise ValueError(f"The job page returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach the job page: {exc.reason}") from exc
