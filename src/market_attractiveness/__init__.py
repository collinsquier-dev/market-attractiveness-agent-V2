"""Market attractiveness scoring package."""

from .comparison import compare_markets
from .live_data import market_input_from_city
from .models import (
    DimensionInput,
    DimensionScore,
    MarketInput,
    MarketScorecard,
    TargetCompanyInput,
)
from .narrative import build_narrative_prompt, render_narrative_summary
from .scoring import score_market

__all__ = [
    "DimensionInput",
    "DimensionScore",
    "MarketInput",
    "MarketScorecard",
    "TargetCompanyInput",
    "score_market",
    "compare_markets",
    "build_narrative_prompt",
    "render_narrative_summary",
    "market_input_from_city",
]
