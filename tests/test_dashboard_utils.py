from market_attractiveness.dashboard_utils import (
    dimension_score_map,
    missing_dimension_count,
    strongest_weakest_dimensions,
)
from market_attractiveness.models import DimensionInput, MarketInput, TargetCompanyInput
from market_attractiveness.scoring import score_market


def test_dashboard_utils_missing_dimension_count_and_extremes():
    market = MarketInput(
        market_name="Test",
        population_growth_trends=DimensionInput(80, 0.8),
        gdp_and_macro_growth=DimensionInput(70, 0.8),
        target_companies=TargetCompanyInput(count_1000_plus=20),
    )
    scorecard = score_market(market)

    strongest, weakest = strongest_weakest_dimensions(scorecard)

    assert missing_dimension_count(scorecard) > 1
    assert strongest is not None
    assert weakest is not None


def test_dashboard_utils_dimension_score_map_excludes_missing():
    market = MarketInput(
        market_name="Test",
        population_growth_trends=DimensionInput(80, 0.8),
        gdp_and_macro_growth=DimensionInput(),
    )
    scorecard = score_market(market)

    score_map = dimension_score_map(scorecard)

    assert "Population growth trends" in score_map
    assert "GDP and macro growth indicators" not in score_map
