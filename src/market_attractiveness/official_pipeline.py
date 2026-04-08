from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from typing import Any, Dict, Optional


STATE_ABBR_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10", "DC": "11",
    "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30",
    "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}

POLICY_STATE_SCORE = {"TX": 76, "FL": 75, "TN": 74, "NC": 72, "GA": 72, "UT": 74, "CO": 70, "CA": 63, "NY": 61, "WA": 68, "IL": 62, "MA": 67}
POLICY_STATE_SCORE = {
    "TX": 76, "FL": 75, "TN": 74, "NC": 72, "GA": 72, "UT": 74, "CO": 70,
    "CA": 63, "NY": 61, "WA": 68, "IL": 62, "MA": 67,
}


@dataclass
class ResolvedCity:
    query: str
    display_name: str
    country_code: str
    state_abbr: Optional[str]
    lat: float
    lon: float
    importance: float


@dataclass
class DimensionMetric:
    raw_value: float
    normalized_score: float
    source: str
    source_date: str
    geographic_level_used: str
    direct_vs_proxy: str
    confidence_score: float
    explanation: str
    value: float
    confidence: float
    note: str


class PipelineError(RuntimeError):
    pass


def http_get_json(url: str, retries: int = 3, backoff_seconds: float = 0.8) -> Any:
    headers = {"User-Agent": "market-attractiveness-agent/official-data-pipeline", "Accept": "application/json"}
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
    raise PipelineError(f"HTTP request failed: {url}: {last_exc}")


class CityMetroResolver:
    def resolve(self, city_name: str) -> ResolvedCity:
        q = urllib.parse.quote(city_name)
        url = f"https://nominatim.openstreetmap.org/search?q={q}&format=jsonv2&addressdetails=1&limit=1"
        payload = http_get_json(url)
        if not isinstance(payload, list) or not payload:
            raise PipelineError(f"No city found for '{city_name}'.")
        top = payload[0]
        address = top.get("address", {}) if isinstance(top.get("address", {}), dict) else {}
        state_abbr = address.get("ISO3166-2-lvl4", "")
        if isinstance(state_abbr, str) and "-" in state_abbr:
            state_abbr = state_abbr.split("-")[-1]
        elif not isinstance(state_abbr, str):
            state_abbr = None

        return ResolvedCity(
            query=city_name,
            display_name=str(top.get("display_name", city_name)),
            country_code=str(address.get("country_code", "")).upper(),
            state_abbr=state_abbr.upper() if state_abbr else None,
            lat=float(top.get("lat", 0.0)),
            lon=float(top.get("lon", 0.0)),
            importance=float(top.get("importance", 0.35)),
        )


class ACSFetcher:
    def fetch(self, city: ResolvedCity) -> Dict[str, float]:
        if city.country_code != "US" or not city.state_abbr:
            return {}
        fips = STATE_ABBR_TO_FIPS.get(city.state_abbr)
        if not fips:
            return {}
        vars_ = ["B01003_001E", "B19013_001E", "B25064_001E", "B23025_003E", "B23025_005E", "B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]

        vars_ = [
            "NAME",
            "B01003_001E",  # population
            "B19013_001E",  # median income
            "B25064_001E",  # median rent
            "B23025_003E",  # labor force
            "B23025_005E",  # unemployed
            "B15003_001E",  # education total
            "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E",  # bachelor's+
        ]
        url = f"https://api.census.gov/data/2023/acs/acs1?get={','.join(vars_)}&for=state:{fips}"
        rows = http_get_json(url)
        if not isinstance(rows, list) or len(rows) < 2:
            return {}

        variables = "NAME,B19013_001E,B25064_001E,B23025_003E,B23025_005E"
        url = f"https://api.census.gov/data/2023/acs/acs1?get={variables}&for=state:{fips}"
        rows = http_get_json(url)
        if not isinstance(rows, list) or len(rows) < 2:
            return {}
        hdr, val = rows[0], rows[1]
        d = dict(zip(hdr, val))
        lf = float(d.get("B23025_003E", 0) or 0)
        unemp = float(d.get("B23025_005E", 0) or 0)
        edu_total = float(d.get("B15003_001E", 0) or 0)
        edu_ba_plus = sum(float(d.get(k, 0) or 0) for k in ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"])

        return {
            "population": float(d.get("B01003_001E", 0) or 0),
            "median_income": float(d.get("B19013_001E", 0) or 0),
            "median_rent": float(d.get("B25064_001E", 0) or 0),
            "unemployment_rate": (unemp / lf * 100.0) if lf > 0 else 0.0,
            "education_ba_plus_rate": (edu_ba_plus / edu_total * 100.0) if edu_total > 0 else 0.0,
        unemployment_rate = (unemp / lf * 100.0) if lf > 0 else None
        return {
            "median_income": float(d.get("B19013_001E", 0) or 0),
            "median_rent": float(d.get("B25064_001E", 0) or 0),
            "unemployment_rate": unemployment_rate if unemployment_rate is not None else 0.0,
        }


class BLSFetcher:
    def fetch(self, city: ResolvedCity) -> Dict[str, float]:
        if city.country_code != "US" or not city.state_abbr:
            return {}
        state_code = STATE_ABBR_TO_FIPS.get(city.state_abbr)
        if not state_code:
            return {}
        series = f"LAUST{state_code}0000000000003"
        body = json.dumps({"seriesid": [series], "startyear": "2024", "endyear": "2025"}).encode("utf-8")
        req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body, headers={"Content-Type": "application/json", "User-Agent": "market-attractiveness-agent"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            latest = float(payload["Results"]["series"][0]["data"][0]["value"])

        # State unemployment series (LAUS)
        state_code = STATE_ABBR_TO_FIPS.get(city.state_abbr)
        if not state_code:
            return {}
        series = f"LAUST{state_code}0000000000003"
        body = json.dumps({"seriesid": [series], "startyear": "2024", "endyear": "2025"}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "market-attractiveness-agent"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

        try:
            data = payload["Results"]["series"][0]["data"]
            latest = float(data[0]["value"])
            return {"bls_unemployment_rate": latest}
        except Exception:  # noqa: BLE001
            return {}


class FREDFetcher:
    def fetch(self, city: ResolvedCity) -> Dict[str, float]:
        key = os.getenv("FRED_API_KEY")
        if not key:
            return {}
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&api_key={key}&file_type=json&limit=1&sort_order=desc"
        try:
            payload = http_get_json(url)
            obs = payload.get("observations", [])
            return {"fred_unrate": float(obs[0]["value"])} if obs else {}
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return {}
        # Optional simple national series as macro proxy.
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&api_key={api_key}&file_type=json&limit=1&sort_order=desc"
        try:
            payload = http_get_json(url)
            obs = payload.get("observations", [])
            if not obs:
                return {}
            return {"fred_unrate": float(obs[0]["value"])}
        except Exception:  # noqa: BLE001
            return {}


class MetricNormalizer:
    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, v))

    def normalize(self, city: ResolvedCity, acs: Dict[str, float], bls: Dict[str, float], fred: Dict[str, float]) -> Dict[str, DimensionMetric]:
        d = date.today().isoformat()
        has_acs, has_bls = bool(acs), bool(bls)
        level = "state" if has_acs or has_bls else "resolver"
    def _clamp(v: float, lo: float = 0, hi: float = 100) -> float:
        return max(lo, min(hi, v))

    def normalize(self, city: ResolvedCity, acs: Dict[str, float], bls: Dict[str, float], fred: Dict[str, float]) -> Dict[str, DimensionMetric]:
        has_acs = bool(acs)
        has_bls = bool(bls)

        unemp = bls.get("bls_unemployment_rate", acs.get("unemployment_rate", fred.get("fred_unrate", 5.0)))
        income = acs.get("median_income", 65000.0)
        rent = acs.get("median_rent", 1400.0)
        edu = acs.get("education_ba_plus_rate", 30.0)
        pop = acs.get("population", 1_000_000.0)

        metrics = {
            "population_growth_trends": DimensionMetric(pop, self._clamp(35 + city.importance * 35), "ACS/Resolver", d, level, "proxy", 0.55 if has_acs else 0.35, "Population proxy from ACS state population + city prominence."),
            "gdp_and_macro_growth": DimensionMetric(unemp, self._clamp(84 - unemp * 4.4), "BLS/ACS/FRED", d, level, "direct" if has_bls else "proxy", 0.72 if has_bls else 0.6 if has_acs else 0.45, "Macro/labor composite from unemployment indicators."),
            "industry_concentration": DimensionMetric(edu, self._clamp(40 + edu * 0.7 + city.importance * 20), "ACS + resolver", d, level, "proxy", 0.62 if has_acs else 0.48, "Industry proxy from BA+ education share and resolver importance."),
            "compensation_benchmarks": DimensionMetric(income, self._clamp(30 + income / 2200.0), "ACS", d, level, "direct" if has_acs else "proxy", 0.68 if has_acs else 0.45, "Compensation proxy from median household income."),
            "cost_of_living_and_operating": DimensionMetric(rent, self._clamp(88 - rent / 35.0 + income / 15000.0), "ACS", d, level, "direct" if has_acs else "proxy", 0.68 if has_acs else 0.42, "Cost proxy from rent-to-income relationship."),
            "competitive_intensity": DimensionMetric(city.importance, self._clamp(45 + city.importance * 40 + (pop / 20_000_000.0)), "Resolver + ACS", d, level, "proxy", 0.5 if has_acs else 0.4, "Competitive intensity proxy from city prominence and population scale."),
            "policy_environment": DimensionMetric(float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66)), float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66)), "State policy lookup", d, "state", "proxy", 0.5, "Maintainable state-level policy lookup table."),
            "qualitative_momentum_signals": DimensionMetric(city.importance, self._clamp(42 + city.importance * 34 + max(0.0, 8.0 - unemp) * 2.2), "Resolver + labor", d, level, "proxy", 0.55 if has_bls or has_acs else 0.35, "Momentum proxy from resolver importance and labor conditions."),
        }
        return metrics

        gdp_macro = self._clamp(84 - (unemp * 4.4))
        industry = self._clamp(40 + (edu * 0.7) + city.importance * 20)
        compensation = self._clamp(30 + (income / 2200.0))
        cost = self._clamp(88 - (rent / 35.0) + (income / 15000.0))
        policy = float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66))
        momentum = self._clamp(42 + city.importance * 34 + (max(0.0, 8.0 - unemp) * 2.2))

        return {
            "gdp_and_macro_growth": DimensionMetric(
                value=round(gdp_macro, 2),
                confidence=0.72 if has_bls else 0.6 if has_acs else 0.45,
                note="Macro/labor composite from BLS unemployment (preferred), ACS labor proxy, and optional FRED.",
            ),
            "industry_concentration": DimensionMetric(
                value=round(industry, 2),
                confidence=0.62 if has_acs else 0.48,
                note="Industry proxy from ACS education mix (BA+) and resolver importance.",
            ),
            "compensation_benchmarks": DimensionMetric(
                value=round(compensation, 2),
                confidence=0.68 if has_acs else 0.45,
                note="Compensation proxy from ACS median household income.",
            ),
            "cost_of_living_and_operating": DimensionMetric(
                value=round(cost, 2),
                confidence=0.68 if has_acs else 0.42,
                note="Cost proxy from ACS median rent and income ratio.",
            ),
            "policy_environment": DimensionMetric(
                value=round(policy, 2),
                confidence=0.5,
                note="Maintainable state-level policy lookup table.",
            ),
            "qualitative_momentum_signals": DimensionMetric(
                value=round(momentum, 2),
                confidence=0.55 if has_bls or has_acs else 0.35,
                note="Momentum proxy from city importance and labor conditions.",
            ),
    def normalize(self, city: ResolvedCity, acs: Dict[str, float], bls: Dict[str, float], fred: Dict[str, float]) -> Dict[str, float]:
        unemp = bls.get("bls_unemployment_rate", acs.get("unemployment_rate", fred.get("fred_unrate", 5.0)))
        median_income = acs.get("median_income", 65000.0)
        median_rent = acs.get("median_rent", 1400.0)

        gdp_macro = self._clamp(82 - (unemp * 4.2))
        industry = self._clamp(50 + city.importance * 30 + (abs(city.lon) % 8))
        comp = self._clamp(35 + (median_income / 2000.0))
        cost = self._clamp(92 - (median_rent / 35.0) + (median_income / 12000.0))
        policy = float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66))
        momentum = self._clamp(45 + city.importance * 35)

        return {
            "gdp_and_macro_growth": round(gdp_macro, 2),
            "industry_concentration": round(industry, 2),
            "compensation_benchmarks": round(comp, 2),
            "cost_of_living_and_operating": round(cost, 2),
            "policy_environment": round(policy, 2),
            "qualitative_momentum_signals": round(momentum, 2),
        }


class MarketInputBuilder:
    def build(self, city: ResolvedCity, metrics: Dict[str, DimensionMetric]):
        from .models import DimensionInput, MarketInput, TargetCompanyInput

        # Proxy target-company counts from population/income scale.
        pop = metrics["population_growth_trends"].raw_value
        income = metrics["compensation_benchmarks"].raw_value
        count_1000_plus = int(max(5, min(220, pop / 350000)))
        count_1b_plus = int(max(2, min(90, (income / 2000) / 5)))

        def dim(key: str) -> DimensionInput:
            m = metrics[key]
            return DimensionInput(value=round(m.normalized_score, 2), confidence=round(m.confidence_score, 2), note=f"{m.explanation} Source={m.source}; level={m.geographic_level_used}; type={m.direct_vs_proxy}; date={m.source_date}.")

        return MarketInput(
            market_name=city.query,
            population_growth_trends=dim("population_growth_trends"),
            gdp_and_macro_growth=dim("gdp_and_macro_growth"),
            industry_concentration=dim("industry_concentration"),
            target_companies=TargetCompanyInput(count_1000_plus=count_1000_plus, count_1b_plus=count_1b_plus, confidence=0.45, note="Proxy from population/income scale due sparse direct company registry in default pipeline."),
            compensation_benchmarks=dim("compensation_benchmarks"),
            cost_of_living_and_operating=dim("cost_of_living_and_operating"),
            competitive_intensity=dim("competitive_intensity"),
            policy_environment=dim("policy_environment"),
            qualitative_momentum_signals=dim("qualitative_momentum_signals"),
    def build(self, city: ResolvedCity, normalized: Dict[str, float], source_note: str):
        from .models import DimensionInput, MarketInput

        return MarketInput(
            market_name=city.query,
            gdp_and_macro_growth=DimensionInput(value=metrics["gdp_and_macro_growth"].value, confidence=metrics["gdp_and_macro_growth"].confidence, note=metrics["gdp_and_macro_growth"].note),
            industry_concentration=DimensionInput(value=metrics["industry_concentration"].value, confidence=metrics["industry_concentration"].confidence, note=metrics["industry_concentration"].note),
            compensation_benchmarks=DimensionInput(value=metrics["compensation_benchmarks"].value, confidence=metrics["compensation_benchmarks"].confidence, note=metrics["compensation_benchmarks"].note),
            cost_of_living_and_operating=DimensionInput(value=metrics["cost_of_living_and_operating"].value, confidence=metrics["cost_of_living_and_operating"].confidence, note=metrics["cost_of_living_and_operating"].note),
            policy_environment=DimensionInput(value=metrics["policy_environment"].value, confidence=metrics["policy_environment"].confidence, note=metrics["policy_environment"].note),
            qualitative_momentum_signals=DimensionInput(value=metrics["qualitative_momentum_signals"].value, confidence=metrics["qualitative_momentum_signals"].confidence, note=metrics["qualitative_momentum_signals"].note),
            gdp_and_macro_growth=DimensionInput(value=normalized["gdp_and_macro_growth"], confidence=0.62, note=source_note),
            industry_concentration=DimensionInput(value=normalized["industry_concentration"], confidence=0.56, note=source_note),
            compensation_benchmarks=DimensionInput(value=normalized["compensation_benchmarks"], confidence=0.62, note=source_note),
            cost_of_living_and_operating=DimensionInput(value=normalized["cost_of_living_and_operating"], confidence=0.58, note=source_note),
            policy_environment=DimensionInput(value=normalized["policy_environment"], confidence=0.7, note=source_note),
            qualitative_momentum_signals=DimensionInput(value=normalized["qualitative_momentum_signals"], confidence=0.5, note=source_note),
        )
