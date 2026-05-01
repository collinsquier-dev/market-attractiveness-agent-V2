from __future__ import annotations

import hashlib
from typing import Dict

from .models import DimensionInput, MarketInput, TargetCompanyInput
from .official_pipeline import (
    ACSFetcher,
    BLSFetcher,
    CityMetroResolver,
    FREDFetcher,
    MarketInputBuilder,
    MetricNormalizer,
)


OFFLINE_CITY_PROFILES: dict[str, dict[str, float]] = {
    "nashville, tn": {"economy": 72, "startups": 66, "cost": 58, "business_freedom": 74},
    "austin, tx": {"economy": 78, "startups": 76, "cost": 55, "business_freedom": 76},
    "chicago, il": {"economy": 70, "startups": 67, "cost": 49, "business_freedom": 62},
    "dallas, tx": {"economy": 76, "startups": 72, "cost": 57, "business_freedom": 76},
    "atlanta, ga": {"economy": 74, "startups": 70, "cost": 56, "business_freedom": 72},
    "miami, fl": {"economy": 71, "startups": 68, "cost": 50, "business_freedom": 72},
    "denver, co": {"economy": 73, "startups": 71, "cost": 52, "business_freedom": 73},
    "seattle, wa": {"economy": 79, "startups": 74, "cost": 43, "business_freedom": 70},
}


class LiveDataError(RuntimeError):
    """Raised when live city lookup fails."""
    pass


def _normalize_city_key(city_name: object) -> str:
    name = "" if city_name is None else str(city_name)
    return " ".join(name.strip().lower().split())


def _city_variation(city_name: object) -> int:
    """Stable city-specific variation so fallback scores do not all look identical."""
    key = _normalize_city_key(city_name)
    if not key:
        key = "unknown"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    h = int(digest, 16)
    return (h % 20) - 10


def _offline_market_input(city_name: str) -> MarketInput:
    key = _normalize_city_key(city_name)
    profile = OFFLINE_CITY_PROFILES.get(key)

    if profile:
        note = "Offline curated fallback profile used because live lookup was unavailable."
    else:
        variation = _city_variation(city_name)
        profile = {
            "economy": 60 + variation,
            "startups": 58 + variation,
            "cost": 55 - variation,
            "business_freedom": 60 + int(variation / 2),
        }
        note = "Synthetic fallback profile generated because live lookup was unavailable."

    return MarketInput(
        market_name=city_name,
        target_companies=TargetCompanyInput(
            count_500m_plus=max(5, int(profile["economy"] * 0.9)),
            confidence=0.30,
            note=note,
        ),
        gdp_and_macro_growth=DimensionInput(value=profile["economy"], confidence=0.35, note=note),
        industry_concentration=DimensionInput(value=profile["startups"], confidence=0.35, note=note),
        consulting_demand_signals=DimensionInput(value=profile["startups"], confidence=0.35, note=note),
        cost_of_living_and_operating=DimensionInput(value=profile["cost"], confidence=0.35, note=note),
        competitive_intensity=DimensionInput(value=max(0, min(100, 75 - profile["startups"] * 0.5)), confidence=0.30, note=note),
        policy_environment=DimensionInput(value=profile["business_freedom"], confidence=0.35, note=note),
        qualitative_momentum_signals=DimensionInput(value=profile["startups"], confidence=0.30, note=note),
    )


def _minimal_safe_market_input(city_name: object) -> MarketInput:
    market_name = str(city_name).strip() if city_name is not None else "Unknown"
    if not market_name:
        market_name = "Unknown"

    variation = _city_variation(market_name)
    base = 60 + variation
    note = "Emergency fallback profile used to guarantee non-failing scoring."

    return MarketInput(
        market_name=market_name,
        target_companies=TargetCompanyInput(
            count_500m_plus=max(5, 20 + variation),
            confidence=0.25,
            note=note,
        ),
        gdp_and_macro_growth=DimensionInput(value=base, confidence=0.25, note=note),
        industry_concentration=DimensionInput(value=base - 2, confidence=0.25, note=note),
        consulting_demand_signals=DimensionInput(value=base + 3, confidence=0.25, note=note),
        cost_of_living_and_operating=DimensionInput(value=base - 5, confidence=0.25, note=note),
        competitive_intensity=DimensionInput(value=base - 3, confidence=0.25, note=note),
        policy_environment=DimensionInput(value=base, confidence=0.25, note=note),
        qualitative_momentum_signals=DimensionInput(value=base + 1, confidence=0.25, note=note),
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
    safe_city_name = str(city_name).strip() if city_name is not None else ""

    if not safe_city_name:
        return _minimal_safe_market_input(city_name)

    try:
        return _build_from_official_pipeline(safe_city_name)
    except Exception:
        try:
            return _offline_market_input(safe_city_name)
        except Exception:
            return _minimal_safe_market_input(safe_city_name)


def market_inputs_from_cities(cities: list[str]) -> tuple[list[MarketInput], dict[str, str]]:
    markets: list[MarketInput] = []
    errors: dict[str, str] = {}

    for city in cities:
        try:
            markets.append(market_input_from_city(city))
        except Exception as exc:
            errors[str(city)] = str(exc)

    return markets, errors


def city_score_report_from_city(city_name: str) -> dict:
    """Return enriched report with dimension metadata + score summary."""
    from .dashboard_utils import missing_dimension_count, strongest_weakest_dimensions
    from .narrative import render_narrative_summary
    from .scoring import score_market

    market = market_input_from_city(city_name)
    scorecard = score_market(market)
    strong, weak = strongest_weakest_dimensions(scorecard)

    dimensions = []
    for d in scorecard.dimension_scores:
        dimensions.append(
            {
                "name": d.name,
                "raw_value": None if d.score is None else d.score,
                "normalized_score": d.score,
                "source": (d.rationale or "").split("Source=")[-1].split(";")[0] if "Source=" in (d.rationale or "") else "fallback",
                "source_date": (d.rationale or "").split("date=")[-1].split(".")[0] if "date=" in (d.rationale or "") else "n/a",
                "geographic_level_used": (d.rationale or "").split("level=")[-1].split(";")[0] if "level=" in (d.rationale or "") else "fallback",
                "direct_vs_proxy": (d.rationale or "").split("type=")[-1].split(";")[0] if "type=" in (d.rationale or "") else "fallback",
                "confidence_score": d.confidence,
                "explanation": d.rationale,
            }
        )

    return {
        "city": city_name,
        "dimensions": dimensions,
        "structural_score": scorecard.overall_score,
        "momentum_score": next(
            (x["normalized_score"] for x in dimensions if x["name"] == "Qualitative open-source momentum signals"),
            None,
        ),
        "overall_score": scorecard.overall_score,
        "overall_confidence": scorecard.overall_confidence,
        "missing_dimension_count": missing_dimension_count(scorecard),
        "strongest_dimension": strong,
        "weakest_dimension": weak,
        "narrative_summary": render_narrative_summary(scorecard),
    }
