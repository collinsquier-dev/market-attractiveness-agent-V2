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
# This model prioritizes markets where a smaller/mid-sized consulting firm
# can realistically win, not just the largest markets.
DIMENSION_WEIGHTS: Dict[str, float] = {
    "population_growth_trends": 0.06,
    "gdp_and_macro_growth": 0.10,
    "industry_concentration": 0.10,
    "target_companies": 0.10,
    "consulting_demand_signals": 0.10,
    "mid_market_fit": 0.14,
    "cost_of_living_and_operating": 0.12,
    "competitive_intensity": 0.20,
    "policy_environment": 0.06,
    "qualitative_momentum_signals": 0.12,
}
LABELS: Dict[str, str] = {
    "population_growth_trends": "Population growth trends",
    "gdp_and_macro_growth": "GDP and macro growth indicators",
    "industry_concentration": "Industry concentration",
    "target_companies": "Target company density (1,000+ employees and $500M+ revenue)",
    "consulting_demand_signals": "Consulting demand signals",
    "cost_of_living_and_operating": "Cost of living / operating cost",
    "competitive_intensity": "Market winnability / lower competitive saturation",
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
    if data.count_500m_plus is None:
        return DimensionScore(
            name=LABELS["target_companies"],
            score=None,
            weight=weight,
            confidence=0.0,
            missing=True,
            rationale=data.note or "Missing $500M+ company count.",
        )

    # 60+ companies = strong market
    score = _clamp((data.count_500m_plus / 60) * 100, 0.0, 100.0)

    confidence = 0.65 if data.confidence is None else _clamp(float(data.confidence), 0.0, 1.0)

    return DimensionScore(
        name=LABELS["target_companies"],
        score=round(score, 2),
        weight=weight,
        confidence=round(confidence, 2),
        missing=False,
        rationale=data.note or f"Based on {data.count_500m_plus} companies with $500M+ revenue.",
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


def recommend_market(scorecard: MarketScorecard) -> dict:
    if scorecard.overall_score is None:
        return {
            "decision": "INSUFFICIENT DATA",
            "reason": "Missing key dimensions or low-confidence inputs.",
        }

    score = scorecard.overall_score
    confidence = scorecard.overall_confidence

    if score >= 75 and confidence >= 0.70:
        return {
            "decision": "ENTER MARKET",
            "reason": "Strong attractiveness and strong confidence.",
        }

    if score >= 65 and confidence >= 0.55:
        return {
            "decision": "BUILD RELATIONSHIPS / TEST MARKET",
            "reason": "Promising market, but local validation is needed.",
        }

    if score >= 55:
        return {
            "decision": "MONITOR",
            "reason": "Potential exists, but signals are not strong enough yet.",
        }

    return {
        "decision": "DEPRIORITIZE",
        "reason": "Weak demand, poor winnability, or limited structural attractiveness.",
    }
