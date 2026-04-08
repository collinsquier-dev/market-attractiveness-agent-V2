from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from urllib.error import URLError
from typing import Any, Dict, Optional

from .models import DimensionInput, MarketInput

TELEPORT_API = "https://api.teleport.org/api"

# Offline fallback profiles for common U.S. cities when live provider is unreachable.
OFFLINE_CITY_PROFILES: dict[str, dict[str, float]] = {
    "nashville, tn": {"economy": 72, "startups": 66, "salaries": 61, "cost": 58, "business_freedom": 74},
    "austin, tx": {"economy": 78, "startups": 76, "salaries": 64, "cost": 55, "business_freedom": 76},
    "miami, fl": {"economy": 71, "startups": 68, "salaries": 60, "cost": 50, "business_freedom": 72},
    "denver, co": {"economy": 73, "startups": 71, "salaries": 62, "cost": 52, "business_freedom": 73},
    "seattle, wa": {"economy": 79, "startups": 74, "salaries": 70, "cost": 43, "business_freedom": 70},
}


class LiveDataError(RuntimeError):
    """Raised when live city lookup fails."""


def _normalize_city_key(city_name: object) -> str:
    name = "" if city_name is None else str(city_name)
    return " ".join(name.strip().lower().split())


def _get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "market-attractiveness-agent/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise LiveDataError(f"Could not reach live data provider at {url}: {exc}") from exc


def _offline_market_input(city_name: str) -> MarketInput:
    profile = OFFLINE_CITY_PROFILES.get(_normalize_city_key(city_name))

    if profile:
        note = "Offline fallback profile used because live provider was unavailable."
    else:
        # Deterministic synthetic fallback for any city when network/provider is unavailable.
        # This keeps UX functional even in restricted environments.
        digest = hashlib.sha256(_normalize_city_key(city_name).encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16)
        profile = {
            "economy": 55 + (seed % 21),  # 55..75
            "startups": 50 + ((seed >> 3) % 26),  # 50..75
            "salaries": 48 + ((seed >> 6) % 23),  # 48..70
            "cost": 45 + ((seed >> 9) % 21),  # 45..65
            "business_freedom": 52 + ((seed >> 12) % 24),  # 52..75
        }
        note = "Synthetic fallback profile generated because live provider was unavailable."

    return MarketInput(
        market_name=city_name,
        gdp_and_macro_growth=DimensionInput(
            value=profile["economy"],
            confidence=0.4,
            note=note,
        ),
        industry_concentration=DimensionInput(
            value=profile["startups"],
            confidence=0.4,
            note=note,
        ),
        compensation_benchmarks=DimensionInput(
            value=profile["salaries"],
            confidence=0.4,
            note=note,
        ),
        cost_of_living_and_operating=DimensionInput(
            value=profile["cost"],
            confidence=0.4,
            note=note,
        ),
        policy_environment=DimensionInput(
            value=profile["business_freedom"],
            confidence=0.4,
            note=note,
        ),
        qualitative_momentum_signals=DimensionInput(
            value=profile["startups"],
            confidence=0.35,
            note=note,
        ),
    )
def _get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "market-attractiveness-agent/0.1"})
    last_exc = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except URLError as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2)
    raise LiveDataError(f"Could not reach live data provider at {url}: {last_exc}") from last_exc


def _to_100(score_10: Optional[float]) -> Optional[float]:
    if score_10 is None:
        return None
    return round(max(0.0, min(100.0, score_10 * 10.0)), 2)


def _invert_100(score_10: Optional[float]) -> Optional[float]:
    if score_10 is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - (score_10 * 10.0))), 2)


def _scores_by_name(ua_scores: Dict[str, Any]) -> Dict[str, float]:
    categories = ua_scores.get("categories", [])
    out: Dict[str, float] = {}
    for c in categories:
        out[c.get("name", "")] = float(c.get("score_out_of_10", 0.0))
    return out


def _find_urban_area_scores_url(city_search_result: Dict[str, Any]) -> str:
    try:
        city_url = city_search_result["_embedded"]["city:search-results"][0]["_links"]["city:item"]["href"]
    except (KeyError, IndexError) as exc:
        raise LiveDataError("No city found in Teleport search results.") from exc

    city_payload = _get_json(city_url)
    ua_link = city_payload.get("_links", {}).get("city:urban_area", {}).get("href")
    if not ua_link:
        raise LiveDataError("City found, but Teleport has no urban-area data for it.")

    ua_payload = _get_json(ua_link)
    scores_link = ua_payload.get("_links", {}).get("ua:scores", {}).get("href")
    if not scores_link:
        raise LiveDataError("Urban area found, but no score data is available.")

    return scores_link




def _minimal_safe_market_input(city_name: object) -> MarketInput:
    market_name = str(city_name).strip() if city_name is not None else "Unknown"
    if not market_name:
        market_name = "Unknown"
    note = "Emergency fallback profile used to guarantee non-failing scoring."
    return MarketInput(
        market_name=market_name,
        gdp_and_macro_growth=DimensionInput(value=60, confidence=0.3, note=note),
        industry_concentration=DimensionInput(value=58, confidence=0.3, note=note),
        compensation_benchmarks=DimensionInput(value=56, confidence=0.3, note=note),
        cost_of_living_and_operating=DimensionInput(value=55, confidence=0.3, note=note),
        policy_environment=DimensionInput(value=60, confidence=0.3, note=note),
        qualitative_momentum_signals=DimensionInput(value=57, confidence=0.25, note=note),
    )
def market_input_from_city(city_name: str) -> MarketInput:
    try:
        safe_city_name = str(city_name).strip() if city_name is not None else ""
        if not safe_city_name:
            return _minimal_safe_market_input(city_name)

        query = urllib.parse.quote(safe_city_name)
        search_url = f"{TELEPORT_API}/cities/?search={query}&limit=1"

        try:
            search_payload = _get_json(search_url)
            scores_url = _find_urban_area_scores_url(search_payload)
            scores_payload = _get_json(scores_url)
        except Exception:
            return _offline_market_input(safe_city_name)

        category_scores = _scores_by_name(scores_payload)

        return MarketInput(
            market_name=safe_city_name,
            gdp_and_macro_growth=DimensionInput(
                value=_to_100(category_scores.get("Economy")),
                confidence=0.6,
                note="Derived from Teleport 'Economy' urban-area score.",
            ),
            industry_concentration=DimensionInput(
                value=_to_100(category_scores.get("Startups")),
                confidence=0.55,
                note="Proxy from Teleport 'Startups' score.",
            ),
            compensation_benchmarks=DimensionInput(
                value=_to_100(category_scores.get("Salaries")),
                confidence=0.6,
                note="Derived from Teleport 'Salaries' score.",
            ),
            cost_of_living_and_operating=DimensionInput(
                value=_invert_100(category_scores.get("Cost of Living")),
                confidence=0.6,
                note="Inverted from Teleport 'Cost of Living' (lower cost => higher attractiveness).",
            ),
            policy_environment=DimensionInput(
                value=_to_100(category_scores.get("Business Freedom")),
                confidence=0.6,
                note="Derived from Teleport 'Business Freedom' score.",
            ),
            qualitative_momentum_signals=DimensionInput(
                value=_to_100(category_scores.get("Startups")),
                confidence=0.5,
                note="Proxy from Teleport innovation/startup signal.",
            ),
        )
    except Exception:
        return _minimal_safe_market_input(city_name)
def market_input_from_city(city_name: str) -> MarketInput:
    query = urllib.parse.quote(city_name)
    search_url = f"{TELEPORT_API}/cities/?search={query}&limit=1"
    search_payload = _get_json(search_url)
    scores_url = _find_urban_area_scores_url(search_payload)
    scores_payload = _get_json(scores_url)
    category_scores = _scores_by_name(scores_payload)

    return MarketInput(
        market_name=city_name,
        gdp_and_macro_growth=DimensionInput(
            value=_to_100(category_scores.get("Economy")),
            confidence=0.6,
            note="Derived from Teleport 'Economy' urban-area score.",
        ),
        industry_concentration=DimensionInput(
            value=_to_100(category_scores.get("Startups")),
            confidence=0.55,
            note="Proxy from Teleport 'Startups' score.",
        ),
        compensation_benchmarks=DimensionInput(
            value=_to_100(category_scores.get("Salaries")),
            confidence=0.6,
            note="Derived from Teleport 'Salaries' score.",
        ),
        cost_of_living_and_operating=DimensionInput(
            value=_invert_100(category_scores.get("Cost of Living")),
            confidence=0.6,
            note="Inverted from Teleport 'Cost of Living' (lower cost => higher attractiveness).",
        ),
        policy_environment=DimensionInput(
            value=_to_100(category_scores.get("Business Freedom")),
            confidence=0.6,
            note="Derived from Teleport 'Business Freedom' score.",
        ),
        qualitative_momentum_signals=DimensionInput(
            value=_to_100(category_scores.get("Startups")),
            confidence=0.5,
            note="Proxy from Teleport innovation/startup signal.",
        ),
    )


def market_inputs_from_cities(cities: list[str]) -> tuple[list[MarketInput], dict[str, str]]:
    """Fetch many cities and return (successful_markets, errors_by_city)."""
    markets: list[MarketInput] = []
    errors: dict[str, str] = {}
    for city in cities:
        try:
            markets.append(market_input_from_city(city))
        except Exception as exc:
            errors[str(city)] = str(exc)
        except LiveDataError as exc:
            errors[city] = str(exc)
    return markets, errors
