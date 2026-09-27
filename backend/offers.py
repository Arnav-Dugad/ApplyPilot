"""Offer comparison: normalises stipends to a monthly amount in one currency, with live exchange rates."""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

WEEKS_PER_MONTH = 52 / 12
# Gulf currencies are officially pegged to the US dollar; these are exact central-bank pegs.
USD_PEGS = {"AED": 3.6725, "SAR": 3.75, "QAR": 3.64, "BHD": 0.376, "OMR": 0.3845}
CURRENCIES = ["USD", "EUR", "GBP", "INR", "AED", "SAR", "QAR", "BHD", "OMR", "KWD", "SGD", "CHF", "CAD", "AUD", "JPY", "CNY", "HKD", "SEK", "NOK", "DKK", "PLN", "NZD", "MYR", "ZAR", "BRL"]
_cache: dict[str, Any] = {}


def fetch_rates(base: str = "USD", fetch: Any = None) -> dict[str, Any]:
    """USD-based rates from open.er-api.com (free, no key), cached for 12 hours; Gulf pegs as fallback."""
    if _cache.get("at", 0) > time.time() - 12 * 3600 and _cache.get("rates"):
        return _cache
    try:
        if fetch:
            data = fetch()
        else:
            request = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={"User-Agent": "ApplyPilot/0.4"})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.load(response)
        rates = {k: float(v) for k, v in (data.get("rates") or {}).items()}
        if not rates.get("EUR"):
            raise ValueError("Rates unavailable")
        _cache.update({"rates": {**rates, **USD_PEGS, "USD": 1.0}, "at": time.time(), "source": "open.er-api.com", "updated": data.get("time_last_update_utc")})
    except Exception:
        if not _cache.get("rates"):
            _cache.update({"rates": {"USD": 1.0, **USD_PEGS}, "at": 0, "source": "offline (pegged currencies only)", "updated": None})
    return _cache


def monthly(offer: dict[str, Any]) -> float:
    amount, period = float(offer["amount"]), offer["period"]
    hours = float(offer.get("hours_per_week") or 40)
    months = max(float(offer.get("duration_months") or 1), 0.25)
    return {"HOUR": amount * hours * WEEKS_PER_MONTH, "WEEK": amount * WEEKS_PER_MONTH, "MONTH": amount, "YEAR": amount / 12, "TOTAL": amount / months}[period]


def convert(amount: float, source: str, target: str, rates: dict[str, float]) -> float | None:
    if source == target:
        return amount
    if source not in rates or target not in rates:
        return None
    return amount / rates[source] * rates[target]


def compare(offers: list[dict[str, Any]], base: str, rates: dict[str, float]) -> list[dict[str, Any]]:
    rows = []
    for offer in offers:
        per_month = monthly(offer)
        in_base = convert(per_month, offer["currency"], base, rates)
        perks = offer.get("perks") or {}
        perk_value = sum(float(v) for v in perks.values() if isinstance(v, (int, float)))  # user-entered monthly values, in the offer's currency
        perks_base = convert(perk_value, offer["currency"], base, rates) if perk_value else 0.0
        total_months = max(float(offer.get("duration_months") or 1), 0.25)
        rows.append({**offer, "monthly": round(per_month, 2), "monthly_base": round(in_base, 2) if in_base is not None else None,
                     "total_base": round(((in_base or 0) + (perks_base or 0)) * total_months, 2) if in_base is not None else None,
                     "perks_base": round(perks_base or 0, 2), "hourly_base": round(in_base / (float(offer.get("hours_per_week") or 40) * WEEKS_PER_MONTH), 2) if in_base else None})
    best = max((r["monthly_base"] or 0 for r in rows), default=0)
    for r in rows:
        r["best"] = bool(best) and r["monthly_base"] == best
    return sorted(rows, key=lambda r: -(r["monthly_base"] or 0))
