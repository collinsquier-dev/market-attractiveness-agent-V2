from urllib.error import URLError

from market_attractiveness.live_data import _invert_100, _scores_by_name, _to_100


def test_to_100_and_invert_100_bounds():
    assert _to_100(7.5) == 75.0
    assert _to_100(12.0) == 100.0
    assert _invert_100(2.0) == 80.0
    assert _invert_100(-1.0) == 100.0


def test_scores_by_name_extracts_categories():
    payload = {
        "categories": [
            {"name": "Economy", "score_out_of_10": 6.8},
            {"name": "Salaries", "score_out_of_10": 5.1},
        ]
    }
    scores = _scores_by_name(payload)
    assert scores["Economy"] == 6.8
    assert scores["Salaries"] == 5.1


def test_market_inputs_from_cities_collects_success_and_errors(monkeypatch):
    from market_attractiveness.live_data import LiveDataError, market_inputs_from_cities
    from market_attractiveness.models import MarketInput

    def fake_fetch(city: str):
        if city == "Bad City":
            raise LiveDataError("no data")
        return MarketInput(market_name=city)

    monkeypatch.setattr("market_attractiveness.live_data.market_input_from_city", fake_fetch)

    markets, errors = market_inputs_from_cities(["Austin, TX", "Bad City", "Seattle, WA"])

    assert [m.market_name for m in markets] == ["Austin, TX", "Seattle, WA"]
    assert errors == {"Bad City": "no data"}


def test_market_input_from_city_uses_offline_fallback_when_provider_unreachable(monkeypatch):
    from market_attractiveness.live_data import market_input_from_city

    def raise_dns(*_args, **_kwargs):
        raise URLError("Temporary failure in name resolution")

    monkeypatch.setattr("market_attractiveness.live_data.urllib.request.urlopen", raise_dns)

    market = market_input_from_city("Nashville, TN")

    assert market.market_name == "Nashville, TN"
    assert market.gdp_and_macro_growth.value is not None
    assert "Offline fallback" in (market.gdp_and_macro_growth.note or "")


def test_market_input_from_city_uses_synthetic_fallback_for_unknown_city(monkeypatch):
    from market_attractiveness.live_data import market_input_from_city

    def raise_dns(*_args, **_kwargs):
        raise URLError("Temporary failure in name resolution")

    monkeypatch.setattr("market_attractiveness.live_data.urllib.request.urlopen", raise_dns)

    market = market_input_from_city("Unknown City, ZZ")

    assert market.market_name == "Unknown City, ZZ"
    assert market.gdp_and_macro_growth.value is not None
    assert "Synthetic fallback" in (market.gdp_and_macro_growth.note or "")


def test_market_input_from_city_fallback_handles_non_network_exceptions(monkeypatch):
    from market_attractiveness.live_data import market_input_from_city

    def boom(*_args, **_kwargs):
        raise ValueError("unexpected parser error")

    monkeypatch.setattr("market_attractiveness.live_data._get_json", boom)

    market = market_input_from_city("Portland, OR")

    assert market.market_name == "Portland, OR"
    assert market.gdp_and_macro_growth.value is not None


def test_market_input_from_city_never_fails_on_empty_or_none():
    from market_attractiveness.live_data import market_input_from_city

    m1 = market_input_from_city("")
    m2 = market_input_from_city(None)

    assert m1.market_name == "Unknown"
    assert m2.market_name == "Unknown"
    assert m1.gdp_and_macro_growth.value is not None
    assert m2.gdp_and_macro_growth.value is not None
