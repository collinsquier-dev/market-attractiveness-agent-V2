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
