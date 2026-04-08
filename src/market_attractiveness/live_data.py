from __future__ import annotations

import json
import urllib.parse
import urllib.request
from urllib.error import URLError
from typing import Any, Dict, Optional

from .models import DimensionInput, MarketInput

TELEPORT_API = "https://api.teleport.org/api"


class LiveDataError(RuntimeError):
    """Raised when live city lookup fails."""


def _get_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "market-attractiveness-agent/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise LiveDataError(f"Could not reach live data provider: {exc}") from exc


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
        except LiveDataError as exc:
            errors[city] = str(exc)
    return markets, errors
