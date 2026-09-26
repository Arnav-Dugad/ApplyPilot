from __future__ import annotations

import re

# ISO 3166-1 alpha-2 codes for the countries ApplyPilot users most commonly target.
# Unlisted countries still work; they are compared by their normalized name.
COUNTRY_NAMES = {
    "AE": ("united arab emirates", "uae", "emirates"),
    "AU": ("australia",),
    "BH": ("bahrain",),
    "CA": ("canada",),
    "CH": ("switzerland",),
    "DE": ("germany", "deutschland"),
    "DK": ("denmark",),
    "ES": ("spain",),
    "FI": ("finland",),
    "FR": ("france",),
    "GB": ("united kingdom", "uk", "great britain", "britain", "england", "scotland", "wales"),
    "HK": ("hong kong",),
    "IE": ("ireland",),
    "IN": ("india", "bharat"),
    "IT": ("italy",),
    "JP": ("japan",),
    "KW": ("kuwait",),
    "NL": ("netherlands", "the netherlands", "holland"),
    "NO": ("norway",),
    "NZ": ("new zealand",),
    "OM": ("oman",),
    "PL": ("poland",),
    "PT": ("portugal",),
    "QA": ("qatar",),
    "SA": ("saudi arabia", "ksa", "kingdom of saudi arabia"),
    "SE": ("sweden",),
    "SG": ("singapore",),
    "US": ("united states", "united states of america", "usa", "america"),
    "AT": ("austria",), "BE": ("belgium",), "BG": ("bulgaria",), "BR": ("brazil",), "CN": ("china",), "CY": ("cyprus",),
    "CZ": ("czech republic", "czechia"), "EE": ("estonia",), "EG": ("egypt",), "GR": ("greece",), "HR": ("croatia",),
    "HU": ("hungary",), "ID": ("indonesia",), "IL": ("israel",), "IS": ("iceland",), "JO": ("jordan",), "KR": ("south korea", "korea"),
    "LB": ("lebanon",), "LT": ("lithuania",), "LU": ("luxembourg",), "LV": ("latvia",), "MT": ("malta",), "MX": ("mexico",),
    "MY": ("malaysia",), "PH": ("philippines",), "PK": ("pakistan",), "RO": ("romania",), "SI": ("slovenia",), "SK": ("slovakia",),
    "TR": ("turkey", "turkiye"), "TW": ("taiwan",), "VN": ("vietnam",), "ZA": ("south africa",), "TH": ("thailand",), "NG": ("nigeria",),
}
_LOOKUP = {name: code for code, names in COUNTRY_NAMES.items() for name in names}


def country_key(value: str | None) -> str | None:
    """Canonical comparison key: ISO alpha-2 when recognized, otherwise the normalized name."""
    if not value:
        return None
    text = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", str(value).lower())).strip()
    if not text:
        return None
    if text.upper() in COUNTRY_NAMES:
        return text.upper()
    return _LOOKUP.get(text, text)


def same_country(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and country_key(a) == country_key(b)
