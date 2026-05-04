from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketMomentumData:
    score: float
    confidence: float
    source: str
    note: str


CITY_MOMENTUM_ESTIMATES = {
    "nashville, tn": 76,
    "charlotte, nc": 74,
    "denver, co": 72,
    "austin, tx": 78,
    "new york, ny": 62,
    "chicago, il": 64,
}


def normalize_city(city: str) -> str:
    return " ".join(city.strip().lower().split())


def get_market_momentum_data(city: str) -> MarketMomentumData:
    key = normalize_city(city)
    score = CITY_MOMENTUM_ESTIMATES.get(key)

    if score is None:
        return MarketMomentumData(
            score=58,
            confidence=0.25,
            source="fallback_momentum_estimate",
            note="Fallback momentum estimate used.",
        )

    return MarketMomentumData(
        score=score,
        confidence=0.55,
        source="curated_momentum_estimate",
        note="Curated estimate based on market growth, expansion activity, and business momentum.",
    )
