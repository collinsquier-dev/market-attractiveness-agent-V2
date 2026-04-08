from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .comparison import compare_markets, compared_markets_as_dict
from .live_data import LiveDataError, market_input_from_city
from .models import DimensionInput, MarketInput, TargetCompanyInput
from .narrative import build_narrative_prompt, render_narrative_summary
from .scoring import score_market


def _dimension_from_dict(payload: dict) -> DimensionInput:
    return DimensionInput(
        value=payload.get("value"),
        confidence=payload.get("confidence"),
        note=payload.get("note"),
    )


def _target_companies_from_dict(payload: dict) -> TargetCompanyInput:
    return TargetCompanyInput(
        count_1000_plus=payload.get("count_1000_plus"),
        count_1b_plus=payload.get("count_1b_plus"),
        confidence=payload.get("confidence"),
        note=payload.get("note"),
    )


def _market_from_dict(data: dict) -> MarketInput:
    kwargs = {}
    for key, value in data.items():
        if key == "market_name":
            continue
        if key == "target_companies":
            kwargs[key] = _target_companies_from_dict(value)
        else:
            kwargs[key] = _dimension_from_dict(value)
    return MarketInput(market_name=data["market_name"], **kwargs)


def _market_from_item(item: dict | str) -> MarketInput:
    if isinstance(item, str):
        return MarketInput(market_name=item)
    if not isinstance(item, dict):
        raise ValueError("Each market entry must be either an object or a market-name string.")
    if "market_name" not in item:
        raise ValueError("Each market object must include 'market_name'.")
    return _market_from_dict(item)


def load_market_input(path: str) -> MarketInput:
    data = json.loads(Path(path).read_text())
    return _market_from_dict(data)


def load_market_array_input(path: str) -> List[MarketInput]:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError("Compare mode expects a JSON array of market objects.")
    return [_market_from_item(item) for item in data]


def run_score(input_path: str) -> dict:
    market = load_market_input(input_path)
    scorecard = score_market(market)
    return {
        "scorecard": scorecard.as_dict(),
        "narrative_prompt": build_narrative_prompt(scorecard),
        "narrative_summary": render_narrative_summary(scorecard),
    }


def run_compare(input_path: str) -> dict:
    markets = load_market_array_input(input_path)
    compared = compare_markets(markets)
    return compared_markets_as_dict(compared)


def run_autofetch(city_name: str) -> dict:
    market = market_input_from_city(city_name)
    scorecard = score_market(market)
    return {
        "source": "nominatim_proxy",
        "source": "teleport",
        "city": city_name,
        "scorecard": scorecard.as_dict(),
        "narrative_prompt": build_narrative_prompt(scorecard),
        "narrative_summary": render_narrative_summary(scorecard),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Market attractiveness scorer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Score one market JSON object")
    score_parser.add_argument("input", help="Path to a single-market input JSON")

    compare_parser = subparsers.add_parser("compare", help="Compare multiple markets from a JSON array")
    compare_parser.add_argument("input", help="Path to a market-array input JSON")

    autofetch_parser = subparsers.add_parser("autofetch", help="Fetch available city data and score it")
    autofetch_parser.add_argument("city", help="City name, e.g. 'Austin, TX'")

    args = parser.parse_args()

    try:
        if args.command == "score":
            output = run_score(args.input)
        elif args.command == "compare":
            output = run_compare(args.input)
        else:
            output = run_autofetch(args.city)
    except LiveDataError as exc:
        raise SystemExit(f"Autofetch error: {exc}")

    print(json.dumps(output, indent=2))
