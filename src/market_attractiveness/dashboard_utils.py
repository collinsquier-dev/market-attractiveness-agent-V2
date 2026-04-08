from __future__ import annotations

from typing import Dict, Optional, Tuple

from .models import MarketScorecard


def missing_dimension_count(scorecard: MarketScorecard) -> int:
    return sum(1 for d in scorecard.dimension_scores if d.missing)


def strongest_weakest_dimensions(scorecard: MarketScorecard) -> Tuple[Optional[str], Optional[str]]:
    available = [d for d in scorecard.dimension_scores if not d.missing and d.score is not None]
    if not available:
        return None, None

    strongest = max(available, key=lambda d: d.score).name
    weakest = min(available, key=lambda d: d.score).name
    return strongest, weakest


def dimension_score_map(scorecard: MarketScorecard) -> Dict[str, float]:
    return {
        d.name: d.score
        for d in scorecard.dimension_scores
        if d.score is not None and not d.missing
    }
