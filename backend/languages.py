"""Spoken-language requirements in job postings. Only explicit requirement wording counts."""
from __future__ import annotations

import re
from functools import lru_cache

LANGUAGES = ["Arabic", "Chinese", "Mandarin", "Cantonese", "Czech", "Danish", "Dutch", "Finnish", "French", "German", "Greek", "Hebrew", "Hindi", "Hungarian",
             "Italian", "Japanese", "Korean", "Malay", "Norwegian", "Polish", "Portuguese", "Romanian", "Russian", "Spanish", "Swedish", "Tamil", "Thai",
             "Turkish", "Ukrainian", "Urdu", "Vietnamese", "Indonesian", "Bengali", "Marathi", "Telugu", "Kannada", "Gujarati", "Punjabi", "Persian", "Swahili"]
# English is assumed: requiring every student to confirm it would flag almost every posting.
_NAME = "(" + "|".join(LANGUAGES) + ")"
_LIST = rf"{_NAME}(?:\s*(?:,|/|and|or|&)\s*{_NAME})*"
_LEVEL = r"(?:fluent|fluency|fluently|proficient|proficiency|native|mother[- ]tongue|business[- ](?:level|fluent|fluency)|professional(?: working)?|full professional|excellent|strong|advanced|C1|C2|B2)"
_REQUIRED_AFTER = r"(?:is|are)?\s*(?:required|mandatory|essential|a must|necessary|needed|compulsory)"
_OPTIONAL = r"(?:a plus|a bonus|an advantage|advantageous|preferred|desirable|nice[- ]to[- ]have|beneficial|helpful|an asset|is a plus|would be great|ideally)"

REQUIRED_PATTERNS = [
    re.compile(rf"{_LEVEL}\s+(?:\w+\s+){{0,3}}?(?:in\s+|of\s+)?(?:both\s+)?{_LIST}", re.I),
    re.compile(rf"{_LIST}\s+(?:language\s+)?(?:skills\s+|proficiency\s+|fluency\s+)?{_REQUIRED_AFTER}", re.I),
    re.compile(rf"(?:must|need to|required to|you will need to)\s+(?:be able to\s+)?(?:speak|write|communicate)\s+(?:\w+\s+){{0,3}}?(?:in\s+)?{_LIST}", re.I),
    re.compile(rf"{_LIST}\s*(?:\(|-|:)?\s*{_LEVEL}", re.I),
]
OPTIONAL_PATTERN = re.compile(rf"{_LIST}[^.;\n]{{0,40}}?{_OPTIONAL}|{_OPTIONAL}[^.;\n]{{0,25}}?{_LIST}", re.I)


def _names(text: str) -> list[str]:
    return [m.group(0).title() for m in re.finditer(_NAME, text, re.I)]


_ANY = re.compile(_NAME, re.I)


def detect(description: str) -> dict[str, list[str]]:
    """{'required': [...], 'preferred': [...]} — a language in an optional sentence is never required."""
    if not description or not _ANY.search(description):  # most postings never name a language
        return {"required": [], "preferred": []}
    cached = _detect_cached(description)
    return {"required": list(cached[0]), "preferred": list(cached[1])}


@lru_cache(maxsize=2048)
def _detect_cached(description: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    required: list[str] = []
    preferred: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", description or ""):
        optional = [n for m in OPTIONAL_PATTERN.finditer(sentence) for n in _names(m.group(0))]
        for name in optional:
            if name not in preferred:
                preferred.append(name)
        for pattern in REQUIRED_PATTERNS:
            for match in pattern.finditer(sentence):
                for name in _names(match.group(0)):
                    if name not in optional and name not in required:
                        required.append(name)
    return tuple(required), tuple(p for p in preferred if p not in required)


def normalize(name: str) -> str:
    name = name.strip().title()
    return {"Mandarin": "Chinese", "Farsi": "Persian"}.get(name, name)
