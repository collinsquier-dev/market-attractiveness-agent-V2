from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .models import DimensionScore, MarketInput
from .scoring import score_market


@dataclass
class ComparedMarket:
    rank: int
    market_name: str
    overall_score: Optional[float]
    overall_confidence: float
    confidence_flag: str
    strongest_dimension: Optional[str]
    weakest_dimension: Optional[str]
    missing_dimensions: int


def _pick_strongest(dimensions: List[DimensionScore]) -> Optional[str]:
    available = [d for d in dimensions if not d.missing and d.score is not None]
    if not available:
        return None
    best = max(available, key=lambda d: d.score)
    return best.name


def _pick_weakest(dimensions: List[DimensionScore]) -> Optional[str]:
    available = [d for d in dimensions if not d.missing and d.score is not None]
    if not available:
        return None
    worst = min(available, key=lambda d: d.score)
    return worst.name


def compare_markets(markets: List[MarketInput]) -> List[ComparedMarket]:
    scored = [score_market(m) for m in markets]

    sorted_scored = sorted(
        scored,
        key=lambda s: (
            float("-inf") if s.overall_score is None else -s.overall_score,
            s.market_name.lower(),
        ),
    )

    ranked: List[ComparedMarket] = []
    for idx, scorecard in enumerate(sorted_scored, start=1):
        ranked.append(
            ComparedMarket(
                rank=idx,
                market_name=scorecard.market_name,
                overall_score=scorecard.overall_score,
                overall_confidence=scorecard.overall_confidence,
                confidence_flag=scorecard.confidence_flag,
                strongest_dimension=_pick_strongest(scorecard.dimension_scores),
                weakest_dimension=_pick_weakest(scorecard.dimension_scores),
                missing_dimensions=sum(1 for d in scorecard.dimension_scores if d.missing),
            )
        )

    return ranked


def compared_markets_as_dict(results: List[ComparedMarket]) -> dict:
    return {
        "ranked_markets": [
            {
                "rank": r.rank,
                "market_name": r.market_name,
                "overall_score": r.overall_score,
                "overall_confidence": r.overall_confidence,
                "confidence_flag": r.confidence_flag,
                "strongest_dimension": r.strongest_dimension,
                "weakest_dimension": r.weakest_dimension,
                "missing_dimensions": r.missing_dimensions,
            }
            for r in results
        ]
    }
