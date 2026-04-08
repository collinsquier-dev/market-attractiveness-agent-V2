from market_attractiveness.live_data import city_score_report_from_city, market_input_from_city


def test_known_supported_city_uses_curated_fallback_when_pipeline_down(monkeypatch):
    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", lambda _c: (_ for _ in ()).throw(RuntimeError("down")))

    market = market_input_from_city("Nashville, TN")

    assert market.market_name == "Nashville, TN"
    assert "Offline curated fallback" in (market.gdp_and_macro_growth.note or "")


def test_arbitrary_city_partial_data_pipeline(monkeypatch):
    from market_attractiveness.models import DimensionInput, MarketInput, TargetCompanyInput

    def fake_pipeline(city: str):
        return MarketInput(
            market_name=city,
            gdp_and_macro_growth=DimensionInput(70, 0.7, "partial"),
            target_companies=TargetCompanyInput(count_1000_plus=20, count_1b_plus=5, confidence=0.5),
        )

    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", fake_pipeline)

    market = market_input_from_city("Boise, ID")
    assert market.market_name == "Boise, ID"
    assert market.gdp_and_macro_growth.value == 70


def test_city_with_fallback_only_path_returns_score(monkeypatch):
    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", lambda _c: (_ for _ in ()).throw(RuntimeError("down")))
    market = market_input_from_city("Unknown City, ZZ")
    assert market.market_name == "Unknown City, ZZ"
    assert market.gdp_and_macro_growth.value is not None


def test_missing_data_confidence_behavior(monkeypatch):
    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", lambda _c: (_ for _ in ()).throw(RuntimeError("down")))
    report = city_score_report_from_city("Unknown City, ZZ")
    assert report["overall_score"] is not None
    assert report["overall_confidence"] <= 0.5
    assert report["missing_dimension_count"] >= 0
