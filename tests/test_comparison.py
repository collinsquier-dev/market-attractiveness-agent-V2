from market_attractiveness.comparison import compare_markets
from market_attractiveness.models import DimensionInput, MarketInput, TargetCompanyInput


def _market(name: str, base: float) -> MarketInput:
    return MarketInput(
        market_name=name,
        population_growth_trends=DimensionInput(base + 5, 0.8),
        gdp_and_macro_growth=DimensionInput(base + 2, 0.8),
        industry_concentration=DimensionInput(base, 0.7),
        target_companies=TargetCompanyInput(int(base), int(base / 3), 0.7),
        compensation_benchmarks=DimensionInput(base - 5, 0.7),
        cost_of_living_and_operating=DimensionInput(base - 2, 0.7),
        competitive_intensity=DimensionInput(base - 10, 0.65),
        policy_environment=DimensionInput(base + 1, 0.75),
        qualitative_momentum_signals=DimensionInput(base + 3, 0.7),
    )


def test_compare_markets_ranks_descending_overall_score():
    high = _market("High", 80)
    medium = _market("Medium", 65)
    low = _market("Low", 50)

    ranked = compare_markets([medium, low, high])

    assert [r.market_name for r in ranked] == ["High", "Medium", "Low"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_compare_markets_ties_resolve_alphabetically():
    alpha = _market("Alpha", 70)
    beta = _market("Beta", 70)

    ranked = compare_markets([beta, alpha])

    assert ranked[0].overall_score == ranked[1].overall_score
    assert [r.market_name for r in ranked] == ["Alpha", "Beta"]


def test_compare_markets_missing_data_keeps_confidence_flag_and_dimensions():
    sparse = MarketInput(
        market_name="Sparse",
        population_growth_trends=DimensionInput(80, 0.9),
        target_companies=TargetCompanyInput(count_1000_plus=10),
    )

    ranked = compare_markets([sparse])

    assert ranked[0].confidence_flag == "LOW_DATA"
    assert ranked[0].missing_dimensions > 3
    assert ranked[0].strongest_dimension is not None
    assert ranked[0].weakest_dimension is not None
