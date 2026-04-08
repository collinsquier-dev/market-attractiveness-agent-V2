from __future__ import annotations

import json
from pathlib import Path
from typing import List

import streamlit as st

from market_attractiveness.cli import load_market_array_input, load_market_input
from market_attractiveness.comparison import compare_markets, compared_markets_as_dict
from market_attractiveness.dashboard_utils import (
    dimension_score_map,
    missing_dimension_count,
    strongest_weakest_dimensions,
)
from market_attractiveness.live_data import (
    LiveDataError,
    market_input_from_city,
    market_inputs_from_cities,
)
from market_attractiveness.models import MarketInput
from market_attractiveness.narrative import build_narrative_prompt, render_narrative_summary
from market_attractiveness.scoring import score_market


SAMPLE_SINGLE = "examples/sample_market_input.json"
SAMPLE_COMPARE = "examples/sample_markets_input.json"


def _load_uploaded_market(content: bytes) -> MarketInput:
    data = json.loads(content.decode("utf-8"))
    temp = Path("/tmp/uploaded_market.json")
    temp.write_text(json.dumps(data))
    return load_market_input(str(temp))


def _load_uploaded_markets(content: bytes) -> List[MarketInput]:
    data = json.loads(content.decode("utf-8"))
    temp = Path("/tmp/uploaded_markets.json")
    temp.write_text(json.dumps(data))
    return load_market_array_input(str(temp))


def _render_scorecard(market: MarketInput) -> None:
    scorecard = score_market(market)
    strongest, weakest = strongest_weakest_dimensions(scorecard)

    st.subheader(f"Market: {scorecard.market_name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall Score", "N/A" if scorecard.overall_score is None else f"{scorecard.overall_score}")
    c2.metric("Confidence Flag", scorecard.confidence_flag)
    c3.metric("Missing Dimensions", missing_dimension_count(scorecard))

    st.write(f"**Strongest dimension:** {strongest or 'N/A'}")
    st.write(f"**Weakest dimension:** {weakest or 'N/A'}")

    st.subheader("Per-dimension score chart")
    score_map = dimension_score_map(scorecard)
    if score_map:
        st.bar_chart(score_map)
    else:
        st.info("No scored dimensions available.")

    st.subheader("Narrative explanation")
    st.write(render_narrative_summary(scorecard))
    with st.expander("Prompt template used for LLM narrative"):
        st.code(build_narrative_prompt(scorecard))


def _render_comparison(markets: List[MarketInput]) -> None:
    compared = compare_markets(markets)
    st.subheader("Ranked comparison")
    st.dataframe(compared_markets_as_dict(compared)["ranked_markets"], use_container_width=True)

    selected_market_name = st.selectbox("Select market for detail view", [m.market_name for m in markets])
    selected_market = next(m for m in markets if m.market_name == selected_market_name)
    _render_scorecard(selected_market)


def main() -> None:
    st.set_page_config(page_title="Market Attractiveness Dashboard", layout="wide")
    st.title("Market Attractiveness Dashboard")
    st.caption("Deterministic scoring from external market conditions only.")

    mode = st.sidebar.radio("Mode", ["Single market", "Compare markets"])

    try:
        if mode == "Single market":
            st.subheader("Single-market input")
            tab_sample, tab_upload, tab_live = st.tabs(["Use sample", "Upload JSON", "Fetch city live"])

            with tab_sample:
                st.caption("Use built-in sample city data")
                if st.button("Score sample city", key="score_sample_city"):
                    market = load_market_input(SAMPLE_SINGLE)
                    _render_scorecard(market)

            with tab_upload:
                uploaded = st.file_uploader("Upload single-market JSON", type=["json"], key="single_upload")
                if uploaded and st.button("Score uploaded city", key="score_uploaded_city"):
                    market = _load_uploaded_market(uploaded.getvalue())
                    _render_scorecard(market)

            with tab_live:
                st.caption("Type a city and fetch live data automatically")
                city = st.text_input("City", placeholder="e.g., Austin, TX", key="live_city_name")
                if st.button("Fetch & score city", key="fetch_score_city"):
                    if not city:
                        st.info("Enter a city to fetch live data.")
                    else:
                        try:
                            market = market_input_from_city(city)
                        except LiveDataError as exc:
                            st.error(f"Could not fetch city data: {exc}")
                        else:
                            _render_scorecard(market)
        else:
            st.subheader("Compare markets")
            source = st.sidebar.radio("Input source", ["Use sample", "Upload JSON", "Fetch cities live"])
            if source == "Use sample":
                markets = load_market_array_input(SAMPLE_COMPARE)
                _render_comparison(markets)
            elif source == "Upload JSON":
                uploaded = st.file_uploader("Upload market-array JSON", type=["json"], key="compare_upload")
                if not uploaded:
                    st.info("Upload a JSON file to continue.")
                    return
                markets = _load_uploaded_markets(uploaded.getvalue())
                _render_comparison(markets)
            else:
                default_cities = """New York, NY
Los Angeles, CA
Chicago, IL
Houston, TX
Phoenix, AZ
Philadelphia, PA
San Antonio, TX
San Diego, CA
Dallas, TX
Jacksonville, FL
Austin, TX
Fort Worth, TX
San Jose, CA
Columbus, OH
Charlotte, NC
Indianapolis, IN
San Francisco, CA
Seattle, WA
Denver, CO
Washington, DC"""
                raw_cities = st.text_area(
                    "Cities to compare (one per line)",
                    value=default_cities,
                    height=260,
                    key="live_compare_cities",
                )
                if st.button("Fetch & rank cities", key="fetch_rank_cities"):
                    cities = [c.strip() for c in raw_cities.splitlines() if c.strip()]
                    if not cities:
                        st.info("Enter at least one city.")
                        return
                    with st.spinner("Fetching city data and scoring..."):
                        markets, errors = market_inputs_from_cities(cities)
                    if errors:
                        st.warning(f"Could not fetch {len(errors)} cities. Showing available results.")
                        with st.expander("Show city fetch errors"):
                            for city, err in errors.items():
                                st.write(f"- {city}: {err}")
                    if not markets:
                        st.error("No city data was fetched. Please try different cities.")
                        return
                    _render_comparison(markets)
    except Exception as exc:  # beginner-friendly UX
        st.error(f"Could not process input: {exc}")


if __name__ == "__main__":
    main()
