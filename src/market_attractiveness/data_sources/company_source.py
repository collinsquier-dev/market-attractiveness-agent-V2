from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompanyMarketData:
    count_500m_plus: int
    confidence: float
    source: str
    note: str


CITY_COMPANY_ESTIMATES = {
    "nashville, tn": 45,
    "charlotte, nc": 70,
    "denver, co": 62,
    "austin, tx": 68,
    "new york, ny": 180,
    "chicago, il": 130,
}


def normalize_city(city: str) -> str:
    return " ".join(city.strip().lower().split())


def get_company_market_data(city: str) -> CompanyMarketData:
    key = normalize_city(city)
    count = CITY_COMPANY_ESTIMATES.get(key)

    if count is None:
        return CompanyMarketData(
            count_500m_plus=25,
            confidence=0.25,
            source="fallback_estimate",
            note="Fallback estimate used because no company data was available.",
        )

    return CompanyMarketData(
        count_500m_plus=count,
        confidence=0.65,
        source="curated_company_estimate",
        note="Curated estimate of companies with $500M+ revenue.",
    )
