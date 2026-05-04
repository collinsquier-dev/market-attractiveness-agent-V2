from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import MarketInput
from .scoring import score_market, demand_score, winnability_score


@dataclass
class IndustryOpportunity:
    industry: str
    score: float
    rationale: str


INDUSTRY_WEIGHTS: Dict[str, Dict[str, float]] = {
    "Healthcare": {
        "industry_concentration": 0.30,
        "consulting_demand_signals": 0.30,
        "target_companies": 0.25,
        "mid_market_fit": 0.15,
    },
    "Technology / SaaS": {
        "industry_concentration": 0.35,
        "consulting_demand_signals": 0.30,
        "qualitative_momentum_signals": 0.20,
        "mid_market_fit": 0.15,
    },
    "Financial Services": {
        "target_companies": 0.35,
        "consulting_demand_signals": 0.25,
        "industry_concentration": 0.25,
        "policy_environment": 0.15,
    },
    "Manufacturing / Industrial": {
        "target_companies": 0.30,
        "cost_of_living_and_operating": 0.25,
        "policy_environment": 0.20,
        "mid_market_fit": 0.25,
    },
    "Retail / Consumer": {
        "target_companies": 0.25,
        "qualitative_momentum_signals": 0.25,
        "cost_of_living_and_operating": 0.20,
        "mid_market_fit": 0.30,
    },
    "Public Sector / Education": {
        "policy_environment": 0.30,
        "cost_of_living_and_operating": 0.20,
        "industry_concentration": 0.25,
        "mid_market_fit": 0.25,
    },
}


def _dimension_scores_by_key(market: MarketInput) -> Dict[str, float]:
    scorecard = score_market(market)

    # Map display labels back to rough model keys.
    out: Dict[str, float] = {}

    for d in scorecard.dimension_scores:
        name = d.name.lower()
        if d.score is None:
            continue

        if "gdp" in name or "macro" in name:
            out["gdp_and_macro_growth"] = d.score
        elif "industry" in name:
            out["industry_concentration"] = d.score
        elif "target" in name:
            out["target_companies"] = d.score
        elif "consulting demand" in name:
            out["consulting_demand_signals"] = d.score
        elif "mid-market" in name:
            out["mid_market_fit"] = d.score
        elif "cost" in name:
            out["cost_of_living_and_operating"] = d.score
        elif "winnability" in name or "competitive" in name:
            out["competitive_intensity"] = d.score
        elif "policy" in name:
            out["policy_environment"] = d.score
        elif "momentum" in name:
            out["qualitative_momentum_signals"] = d.score

    return out


def score_industry_opportunities(market: MarketInput) -> List[IndustryOpportunity]:
    scores = _dimension_scores_by_key(market)
    opportunities: List[IndustryOpportunity] = []

    for industry, weights in INDUSTRY_WEIGHTS.items():
        weighted_sum = 0.0
        used_weight = 0.0

        for key, weight in weights.items():
            value = scores.get(key)
            if value is None:
                continue

            weighted_sum += value * weight
            used_weight += weight

        if used_weight == 0:
            final_score = 0.0
        else:
            final_score = round(weighted_sum / used_weight, 2)

        rationale = _industry_rationale(industry, final_score)

        opportunities.append(
            IndustryOpportunity(
                industry=industry,
                score=final_score,
                rationale=rationale,
            )
        )

    return sorted(opportunities, key=lambda x: x.score, reverse=True)


def _industry_rationale(industry: str, score: float) -> str:
    if score >= 75:
        strength = "strong"
    elif score >= 65:
        strength = "promising"
    elif score >= 55:
        strength = "moderate"
    else:
        strength = "limited"

    return f"{industry} shows {strength} fit based on market demand, winnability, and relevant operating conditions."


def estimate_revenue_opportunity(market: MarketInput) -> Dict[str, object]:
    scorecard = score_market(market)
    demand = demand_score(scorecard) or 0
    winnability = winnability_score(scorecard) or 0

    target_company_count = 0
    if market.target_companies and market.target_companies.count_500m_plus is not None:
        target_company_count = market.target_companies.count_500m_plus

    # Conservative consulting assumptions.
    average_contract_value_low = 150_000
    average_contract_value_high = 350_000

    # Smaller consulting firm penetration assumption.
    # Higher winnability improves realistic capture.
    penetration_rate = max(0.01, min(0.05, winnability / 2000))

    low_revenue = target_company_count * penetration_rate * average_contract_value_low
    high_revenue = target_company_count * penetration_rate * average_contract_value_high

    return {
        "target_company_count": target_company_count,
        "penetration_rate": round(penetration_rate * 100, 2),
        "low_revenue": round(low_revenue, 0),
        "high_revenue": round(high_revenue, 0),
        "demand_score": demand,
        "winnability_score": winnability,
        "summary": (
            f"Estimated annual opportunity is ${low_revenue:,.0f}–${high_revenue:,.0f}, "
            f"based on {target_company_count} estimated $500M+ companies and a "
            f"{penetration_rate * 100:.2f}% assumed capture rate."
        ),
    }
