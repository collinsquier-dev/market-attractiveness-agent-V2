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
- upload JSON file or use sample files
- overall score, confidence flag, missing-data count
- strongest and weakest dimensions
- per-dimension score chart
- ranked comparison table
- narrative explanation panel

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
- CLI runner: `src/market_attractiveness/cli.py`
- Streamlit app: `streamlit_app.py`
- Sample I/O: `examples/sample_market_input.json`, `examples/sample_market_output.json`, `examples/sample_markets_input.json`, `examples/sample_markets_output.json`
- Tests: `tests/test_scoring.py`, `tests/test_comparison.py`, `tests/test_dashboard_utils.py`

## Extend later
- Replace sample/manual input with data connectors.
- Keep scoring deterministic; use LLM only for narrative generation.
- Attach URLs/citations per note for traceability.
