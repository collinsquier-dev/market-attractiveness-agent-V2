# Market Attractiveness Agent

A simple, modular Python implementation to score a market/city using **external market conditions only**.

## Included dimensions
1. Population growth trends
2. GDP and macro growth indicators
3. Industry concentration
4. Number of target companies (1,000+ employees and $1B+ revenue)
5. Compensation benchmarks
6. Cost of living / operating cost
7. Competitive intensity
8. Pro-business reforms / policy environment
9. Qualitative open-source momentum signals (relocations, expansions, layoffs/exits, economic development investments)

## Excluded dimensions
- Leader assessment
- Internal network strength
- Partner fit
- Entry model recommendation

## Quick start

### 1) Run tests
```bash
python -m pytest -q
```

### 2) Score one market (CLI)
```bash
PYTHONPATH=src python -m market_attractiveness.cli score examples/sample_market_input.json
```

### 3) Compare many markets (CLI)
```bash
PYTHONPATH=src python -m market_attractiveness.cli compare examples/sample_markets_input.json
```

### 4) Compare top 20 cities quickly
You can start from a names-only list and progressively add data later:

```bash
PYTHONPATH=src python -m market_attractiveness.cli compare examples/top_20_us_cities_template.json
```

- In compare mode, each list item can be either:
  - a full market object (`{"market_name": "Austin, TX", ...}`), or
  - just a market name string (`"Austin, TX"`).
- Names-only entries are valid and will return `LOW_DATA` until you add dimension values.

### 5) Auto-fetch a city and score it
You can now score **any city Teleport supports** directly from the CLI:

```bash
PYTHONPATH=src python -m market_attractiveness.cli autofetch "Miami, FL"
```

Notes:
- This uses live data from the Teleport API.
- Some dimensions are proxies and some may still be missing depending on data availability.
- Live fetch is fail-safe: if Teleport is unavailable (or returns unexpected data), the app automatically uses fallback scoring instead of failing.
- Common cities (including Nashville, TN) use curated fallback profiles; any other city uses a deterministic synthetic fallback profile so **any city input still returns a score**.
- If the city is not covered by Teleport urban-area data, the command returns a clear error.

Compare output includes:
- rank by overall score (descending)
- overall score and confidence
- confidence flag
- strongest and weakest dimension
- missing dimension count

## Streamlit dashboard

### Install Streamlit
```bash
python -m pip install streamlit
```

### Launch dashboard
```bash
PYTHONPATH=src streamlit run streamlit_app.py
```

### Dashboard features
- single-market mode and compare mode
- single-market live city fetch by typing a city name
- compare-mode live city ranking from a city list
- upload JSON file or use sample files
- overall score, confidence flag, missing-data count
- strongest and weakest dimensions
- per-dimension score chart
- ranked comparison table
- narrative explanation panel

### Entering any city in Streamlit
1. Launch app:
   ```bash
   PYTHONPATH=src streamlit run streamlit_app.py
   ```
2. Choose **Single market** mode.
3. Open the **Fetch city live** tab.
4. Type a city (example: `Miami, FL`) and click **Fetch & score city**.

### Rank top 20 cities for expansion in Streamlit
1. Choose **Compare markets** mode.
2. Set input source to **Fetch cities live**.
3. Paste or edit the 20-city list (one city per line).
4. Click **Fetch & rank cities**.

The app fetches available live data, scores each city, and ranks them by overall score.

## Input model (beginner version)
- Most dimensions use:
  - `value` (0-100 attractiveness)
  - `confidence` (0.0-1.0)
  - `note` (source context)
- `target_companies` is structured:
  - `count_1000_plus`
  - `count_1b_plus`
  - `confidence`
  - `note`

## Confidence behavior
- Missing data is never invented.
- If a dimension is missing, output shows `missing=true`, `score=null`, `confidence=0.0`.
- `target_companies` requires both counts; if one is missing, the dimension is marked missing.
- Overall score uses available dimensions only.
- Confidence flag:
  - `LOW_DATA`: too many missing dimensions
  - `LOW_CONFIDENCE` / `MEDIUM_CONFIDENCE` / `HIGH_CONFIDENCE`

## Files of interest
- Scoring logic: `src/market_attractiveness/scoring.py`
- Comparison logic: `src/market_attractiveness/comparison.py`
- Dashboard helpers: `src/market_attractiveness/dashboard_utils.py`
- Models: `src/market_attractiveness/models.py`
- Narrative template: `src/market_attractiveness/narrative.py`
- Live city fetcher: `src/market_attractiveness/live_data.py`
- CLI runner: `src/market_attractiveness/cli.py`
- Streamlit app: `streamlit_app.py`
- Sample I/O: `examples/sample_market_input.json`, `examples/sample_market_output.json`, `examples/sample_markets_input.json`, `examples/sample_markets_output.json`
- Tests: `tests/test_scoring.py`, `tests/test_comparison.py`, `tests/test_dashboard_utils.py`

## Extend later
- Replace sample/manual input with data connectors.
- Keep scoring deterministic; use LLM only for narrative generation.
- Attach URLs/citations per note for traceability.


## Merge readiness checklist
Before opening or updating your PR branch:

1. Run the pre-merge script:
   ```bash
   ./scripts/premerge_check.sh
   ```
2. Push your branch to GitHub.
3. Confirm GitHub Actions `CI` workflow is green.
4. Resolve any branch conflicts shown in GitHub PR UI.
5. Re-run checks after conflict resolution.

If branch protection requires status checks, the new `CI` workflow is what needs to pass for merge.


## Troubleshooting
- If you see an `IndentationError` in `streamlit_app.py`, ensure your local branch is up to date and that your editor is configured for 4-space indentation (no tabs).
- This repo includes `.editorconfig` to enforce consistent indentation across environments.
- Run `python scripts/verify_indentation.py` to detect tabs/inconsistent indentation before running Streamlit.
