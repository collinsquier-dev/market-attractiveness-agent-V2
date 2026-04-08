from market_attractiveness.live_data import market_input_from_city, market_inputs_from_cities


def test_market_input_from_city_uses_official_pipeline_when_available(monkeypatch):
    from market_attractiveness.models import MarketInput

    def fake_pipeline(city: str):
        return MarketInput(market_name=city)

    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", fake_pipeline)

    market = market_input_from_city("Nashville, TN")

    assert market.market_name == "Nashville, TN"


def test_market_input_from_city_falls_back_to_curated_profile(monkeypatch):
    def boom(_city: str):
        raise RuntimeError("pipeline down")

    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", boom)

    market = market_input_from_city("Nashville, TN")

    assert market.market_name == "Nashville, TN"
    assert "Offline curated fallback" in (market.gdp_and_macro_growth.note or "")


def test_market_input_from_city_falls_back_to_synthetic_for_unknown_city(monkeypatch):
    def boom(_city: str):
        raise RuntimeError("pipeline down")

    monkeypatch.setattr("market_attractiveness.live_data._build_from_official_pipeline", boom)

    market = market_input_from_city("Unknown City, ZZ")

    assert market.market_name == "Unknown City, ZZ"
    assert market.gdp_and_macro_growth.value is not None
    assert "Synthetic fallback" in (market.gdp_and_macro_growth.note or "")


def test_market_input_from_city_never_fails_on_empty_or_none():
    m1 = market_input_from_city("")
    m2 = market_input_from_city(None)

    assert m1.market_name == "Unknown"
    assert m2.market_name == "Unknown"


def test_market_inputs_from_cities_collects_outputs_without_crashing(monkeypatch):
    def fake_city(city: str):
        if city == "Bad":
            raise RuntimeError("unexpected")
        return market_input_from_city(city)

    monkeypatch.setattr("market_attractiveness.live_data.market_input_from_city", fake_city)
    markets, errors = market_inputs_from_cities(["Austin, TX", "Bad", "Seattle, WA"])

    assert len(markets) == 2
    assert "Bad" in errors
