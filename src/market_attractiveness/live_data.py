from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from typing import Any

from .models import DimensionInput, MarketInput


NOMINATIM_SEARCH_API = "https://nominatim.openstreetmap.org/search"


OFFLINE_CITY_PROFILES = {
    "nashville, tn": {"economy": 72, "startups": 66, "salaries": 61, "cost": 58, "business_freedom": 74},
    "austin, tx": {"economy": 78, "startups": 76, "salaries": 64, "cost": 55, "business_freedom": 76},
    "chicago, il": {"economy": 75, "startups": 69, "salaries": 65, "cost": 49, "business_freedom": 68},
}


class LiveDataError(RuntimeError):
    pass


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "agent"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _lookup_city(city_name: str) -> dict[str, Any]:
    query = urllib.parse.quote(city_name)
    url = f"{NOMINATIM_SEARCH_API}?q={query}&format=jsonv2&limit=1"
    data = _get_json(url)
    if not data:
        raise LiveDataError("City not found")
    return data[0]


def _offline_market(city_name: str) -> MarketInput:
    profile = OFFLINE_CITY_PROFILES.get(city_name.lower())
    if not profile:
        profile = {
            "economy": 60,
            "startups": 60,
            "salaries": 60,
            "cost": 60,
            "business_freedom": 60,
        }

    return MarketInput(
        market_name=city_name,
        gdp_and_macro_growth=DimensionInput(value=profile["economy"], confidence=0.4),
        industry_concentration=DimensionInput(value=profile["startups"], confidence=0.4),
        compensation_benchmarks=DimensionInput(value=profile["salaries"], confidence=0.4),
        cost_of_living_and_operating=DimensionInput(value=profile["cost"], confidence=0.4),
        policy_environment=DimensionInput(value=profile["business_freedom"], confidence=0.4),
        qualitative_momentum_signals=DimensionInput(value=profile["startups"], confidence=0.3),
    )


def market_input_from_city(city_name: str) -> MarketInput:
    try:
        _lookup_city(city_name)  # just validate it exists
        return _offline_market(city_name)
    except Exception:
        return _offline_market(city_name)


def market_inputs_from_cities(cities: list[str]):
    markets = []
    errors = {}

    for city in cities:
        try:
            markets.append(market_input_from_city(city))
        except Exception as e:
            errors[city] = str(e)

    return markets, errors


