#!/usr/bin/env bash
set -euo pipefail

printf '\n==> Running unit tests\n'
python -m pytest -q

printf '\n==> Verifying indentation safety\n'
python scripts/verify_indentation.py

printf '\n==> Verifying Python syntax\n'
python -m py_compile streamlit_app.py src/market_attractiveness/*.py

printf '\n==> Verifying CLI sample workflows\n'
PYTHONPATH=src python -m market_attractiveness.cli score examples/sample_market_input.json > /tmp/score.json
PYTHONPATH=src python -m market_attractiveness.cli compare examples/sample_markets_input.json > /tmp/compare.json
python -m json.tool /tmp/score.json >/dev/null
python -m json.tool /tmp/compare.json >/dev/null

printf '\n✅ Pre-merge checks passed.\n'
