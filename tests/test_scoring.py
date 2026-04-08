from market_attractiveness.models import DimensionInput, MarketInput, TargetCompanyInput
from market_attractiveness.scoring import score_market


def test_score_market_complete_input():
    market = MarketInput(
        market_name="Test City",
        population_growth_trends=DimensionInput(80, 0.9),
        gdp_and_macro_growth=DimensionInput(70, 0.8),
        industry_concentration=DimensionInput(60, 0.7),
        target_companies=TargetCompanyInput(40, 12, 0.8),
        compensation_benchmarks=DimensionInput(55, 0.6),
        cost_of_living_and_operating=DimensionInput(65, 0.7),
        competitive_intensity=DimensionInput(50, 0.65),
        policy_environment=DimensionInput(72, 0.75),
        qualitative_momentum_signals=DimensionInput(68, 0.7),
    )

    scorecard = score_market(market)

    assert scorecard.overall_score is not None
    assert 0 <= scorecard.overall_score <= 100
    assert scorecard.confidence_flag in {"MEDIUM_CONFIDENCE", "HIGH_CONFIDENCE"}
    assert len(scorecard.dimension_scores) == 9


def test_score_market_target_companies_missing_is_explicit():
    market = MarketInput(
        market_name="Sparse City",
        population_growth_trends=DimensionInput(80, 0.9),
        gdp_and_macro_growth=DimensionInput(),
        industry_concentration=DimensionInput(),
        target_companies=TargetCompanyInput(count_1000_plus=10),
        compensation_benchmarks=DimensionInput(55, 0.6),
        cost_of_living_and_operating=DimensionInput(),
        competitive_intensity=DimensionInput(),
        policy_environment=DimensionInput(),
        qualitative_momentum_signals=DimensionInput(68, 0.7),
    )

    scorecard = score_market(market)

    target_dimension = next(d for d in scorecard.dimension_scores if "Target company" in d.name)
    assert target_dimension.missing is True
    assert target_dimension.score is None
    assert scorecard.confidence_flag == "LOW_DATA"


def test_score_market_no_data_returns_none_score():
    market = MarketInput(market_name="Unknown")
    scorecard = score_market(market)

    assert scorecard.overall_score is None
    assert scorecard.overall_confidence == 0.0
    assert scorecard.confidence_flag == "LOW_DATA"
