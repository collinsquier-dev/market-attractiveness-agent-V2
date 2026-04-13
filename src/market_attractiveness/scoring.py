from __future__ import annotations

from typing import Dict

from .models import (
    DimensionInput,
    DimensionScore,
    MarketInput,
    MarketScorecard,
    TargetCompanyInput,
)

# TGG-specific weighting logic:
# - Prioritize enterprise demand and transformation opportunity
# - Heavier weight on target company density, macro health, industry concentration,
#   and momentum/activity signals
# - Lighter weight on population growth and pure cost factors
DIMENSION_WEIGHTS: Dict[str, float] = {
    "population_growth_trends": 0.06,
    "gdp_and_macro_growth": 0.12,
    "industry_concentration": 0.12,
    "target_companies": 0.16,
    "consulting_demand_signals": 0.16,
    "compensation_benchmarks": 0.07,
    "cost_of_living_and_operating": 0.07,
    "competitive_intensity": 0.08,
    "policy_environment": 0.06,
    "qualitative_momentum_signals": 0.10,
}

LABELS: Dict[str, str] = {
    "population_growth_trends": "Population growth trends",
    "gdp_and_macro_growth": "GDP and macro growth indicators",
    "industry_concentration": "Industry concentration",
    "target_companies": "Target company density (1,000+ employees and $1B+ revenue)",
    "consulting_demand_signals": "Consulting demand signals",
    "compensation_benchmarks": "Compensation benchmarks",
    "cost_of_living_and_operating": "Cost of living / operating cost",
    "competitive_intensity": "Competitive intensity",
    "policy_environment": "Pro-business reforms / policy environment",
    "qualitative_momentum_signals": "Qualitative open-source momentum signals",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _score_dimension(name: str, data: DimensionInput, weight: float) -> DimensionScore:
    if data.value is None:
        return DimensionScore(
            name=LABELS[name],
            score=None,
            weight=weight,
            confidence=0.0,
            missing=True,
            rationale=data.note or "No data provided for this dimension.",
        )

    score = _clamp(float(data.value), 0.0, 100.0)
    confidence = 0.65 if data.confidence is None else _clamp(float(data.confidence), 0.0, 1.0)
    return DimensionScore(
        name=LABELS[name],
        score=round(score, 2),
        weight=weight,
        confidence=round(confidence, 2),
        missing=False,
        rationale=data.note or "Scored from normalized input.",
    )


def _score_target_companies(data: TargetCompanyInput, weight: float) -> DimensionScore:
    if data.count_1000_plus is None or data.count_1b_plus is None:
        return DimensionScore(
            name=LABELS["target_companies"],
            score=None,
            weight=weight,
            confidence=0.0,
            missing=True,
            rationale=data.note or "Missing one or both target-company counts.",
        )

    employee_subscore = _clamp((data.count_1000_plus / 100) * 100, 0.0, 100.0)
    revenue_subscore = _clamp((data.count_1b_plus / 30) * 100, 0.0, 100.0)
    score = 0.55 * employee_subscore + 0.45 * revenue_subscore
    confidence = 0.65 if data.confidence is None else _clamp(float(data.confidence), 0.0, 1.0)

    rationale = data.note or (
        f"Derived from counts: 1000+ employees={data.count_1000_plus}, "
        f"$1B+ revenue={data.count_1b_plus}."
    )

    return DimensionScore(
        name=LABELS["target_companies"],
        score=round(score, 2),
        weight=weight,
        confidence=round(confidence, 2),
        missing=False,
        rationale=rationale,
    )


def _confidence_flag(overall_confidence: float, missing_ratio: float) -> str:
    if missing_ratio > 0.33:
        return "LOW_DATA"
    if overall_confidence < 0.5:
        return "LOW_CONFIDENCE"
    if overall_confidence < 0.75:
        return "MEDIUM_CONFIDENCE"
    return "HIGH_CONFIDENCE"


def score_market(market: MarketInput) -> MarketScorecard:
    dimension_scores = []
    weighted_sum = 0.0
    weighted_conf = 0.0
    used_weight = 0.0

    for key, weight in DIMENSION_WEIGHTS.items():
        dim_score = (
            _score_target_companies(market.target_companies, weight)
            if key == "target_companies"
            else _score_dimension(key, getattr(market, key), weight)
        )
        dimension_scores.append(dim_score)

        if dim_score.missing or dim_score.score is None:
            continue

        weighted_sum += dim_score.score * weight
        weighted_conf += dim_score.confidence * weight
        used_weight += weight

    missing_count = sum(1 for d in dimension_scores if d.missing)
    total_dims = len(dimension_scores)

    if used_weight == 0:
        overall_score = None
        overall_confidence = 0.0
    else:
        overall_score = round(weighted_sum / used_weight, 2)
        overall_confidence = round(weighted_conf / used_weight, 2)

    confidence_flag = _confidence_flag(overall_confidence, missing_count / total_dims)
    return MarketScorecard(
        market_name=market.market_name,
        overall_score=overall_score,
        overall_confidence=overall_confidence,
        confidence_flag=confidence_flag,
        dimension_scores=dimension_scores,
    )
def recommend_market(scorecard: MarketScorecard) -> str:
    if scorecard.overall_score is None:
        return "Insufficient data"

    score = scorecard.overall_score
    confidence = scorecard.overall_confidence

    if score > 75 and confidence > 0.7:
        return "ENTER MARKET NOW"
    elif score > 65:
        return "BUILD RELATIONSHIPS / TEST MARKET"
    elif score > 55:
        return "MONITOR MARKET"
    else:
        return "DEPRIORITIZE"
