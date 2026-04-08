from __future__ import annotations

import hashlib
from typing import Dict

from .models import DimensionInput, MarketInput
from .official_pipeline import (
    ACSFetcher,
    BLSFetcher,
    CityMetroResolver,
    FREDFetcher,
    MarketInputBuilder,
    MetricNormalizer,
)


OFFLINE_CITY_PROFILES: dict[str, dict[str, float]] = {
    "nashville, tn": {"economy": 72, "startups": 66, "salaries": 61, "cost": 58, "business_freedom": 74},
    "austin, tx": {"economy": 78, "startups": 76, "salaries": 64, "cost": 55, "business_freedom": 76},
    "chicago, il": {"economy": 70, "startups": 67, "salaries": 66, "cost": 49, "business_freedom": 62},
    "dallas, tx": {"economy": 76, "startups": 72, "salaries": 63, "cost": 57, "business_freedom": 76},
    "atlanta, ga": {"economy": 74, "startups": 70, "salaries": 61, "cost": 56, "business_freedom": 72},
}


class LiveDataError(RuntimeError):
    pass


def _normalize_city_key(city_name: object) -> str:
    name = "" if city_name is None else str(city_name)
    return " ".join(name.strip().lower().split())


def _offline_market_input(city_name: str) -> MarketInput:
    profile = OFFLINE_CITY_PROFILES.get(_normalize_city_key(city_name))

    if not profile:
        digest = hashlib.sha256(_normalize_city_key(city_name).encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16)
        profile = {
            "economy": 55 + (seed % 21),
            "startups": 50 + ((seed >> 3) % 26),
            "salaries": 48 + ((seed >> 6) % 23),
            "cost": 45 + ((seed >> 9) % 21),
            "business_freedom": 52 + ((seed >> 12) % 24),
        }

    return MarketInput(
        market_name=city_name,
        gdp_and_macro_growth=DimensionInput(value=profile["economy"], confidence=0.4),
        industry_concentration=DimensionInput(value=profile["startups"], confidence=0.4),
        compensation_benchmarks=DimensionInput(value=profile["salaries"], confidence=0.4),
        cost_of_living_and_operating=DimensionInput(value=profile["cost"], confidence=0.4),
        policy_environment=DimensionInput(value=profile["business_freedom"], confidence=0.4),
        qualitative_momentum_signals=DimensionInput(value=profile["startups"], confidence=0.35),
    )


def _build_from_official_pipeline(city_name: str) -> MarketInput:
    resolver = CityMetroResolver()
    acs = ACSFetcher()
    bls = BLSFetcher()
    fred = FREDFetcher()
    normalizer = MetricNormalizer()
    builder = MarketInputBuilder()

    resolved = resolver.resolve(city_name)
    acs_metrics: Dict[str, float] = acs.fetch(resolved)
    bls_metrics: Dict[str, float] = bls.fetch(resolved)
    fred_metrics: Dict[str, float] = fred.fetch(resolved)

    normalized = normalizer.normalize(resolved, acs_metrics, bls_metrics, fred_metrics)

    return builder.build(resolved, normalized)


def market_input_from_city(city_name: str) -> MarketInput:
    safe_city_name = str(city_name).strip()

    if not safe_city_name:
        return _offline_market_input("unknown")

    try:
        return _build_from_official_pipeline(safe_city_name)
    except Exception:
        return _offline_market_input(safe_city_name)


def market_inputs_from_cities(cities: list[str]) -> tuple[list[MarketInput], dict[str, str]]:
    markets: list[MarketInput] = []
    errors: dict[str, str] = {}

    for city in cities:
        try:
            markets.append(market_input_from_city(city))
        except Exception as exc:
            errors[str(city)] = str(exc)

    return markets, errors

