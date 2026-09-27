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
    "NP": ("nepal",), "BD": ("bangladesh",), "LK": ("sri lanka",), "BT": ("bhutan",), "MV": ("maldives",), "AF": ("afghanistan",), "IR": ("iran",),
    "IQ": ("iraq",), "KZ": ("kazakhstan",), "UZ": ("uzbekistan",), "UA": ("ukraine",), "RU": ("russia", "russian federation"), "BY": ("belarus",),
    "RS": ("serbia",), "BA": ("bosnia and herzegovina", "bosnia"), "AL": ("albania",), "MK": ("north macedonia", "macedonia"), "ME": ("montenegro",),
    "MD": ("moldova",), "GE": ("georgia",), "AM": ("armenia",), "AZ": ("azerbaijan",), "LI": ("liechtenstein",), "MC": ("monaco",),
    "AR": ("argentina",), "CL": ("chile",), "CO": ("colombia",), "PE": ("peru",), "VE": ("venezuela",), "EC": ("ecuador",), "UY": ("uruguay",),
    "PY": ("paraguay",), "BO": ("bolivia",), "CR": ("costa rica",), "PA": ("panama",), "GT": ("guatemala",), "DO": ("dominican republic",),
    "JM": ("jamaica",), "KE": ("kenya",), "TZ": ("tanzania",), "UG": ("uganda",), "ET": ("ethiopia",), "GH": ("ghana",), "MA": ("morocco",),
    "DZ": ("algeria",), "TN": ("tunisia",), "RW": ("rwanda",), "SN": ("senegal",), "CM": ("cameroon",), "ZW": ("zimbabwe",), "ZM": ("zambia",),
    "MU": ("mauritius",), "KH": ("cambodia",), "MM": ("myanmar",), "MN": ("mongolia",), "MO": ("macau", "macao")
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


DISPLAY = {"US": "the United States", "GB": "the United Kingdom", "AE": "the UAE", "NL": "the Netherlands", "CZ": "Czechia", "KR": "South Korea", "PH": "the Philippines"}


def country_name(value: str | None) -> str | None:
    """Readable country name for explanations: 'us' -> 'the United States', 'India' -> 'India'."""
    key = country_key(value)
    if not key:
        return None
    if key in DISPLAY:
        return DISPLAY[key]
    if key in COUNTRY_NAMES:
        return COUNTRY_NAMES[key][0].title()
    return str(value).strip()
