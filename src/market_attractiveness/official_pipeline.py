from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from .models import DimensionInput, MarketInput, TargetCompanyInput


STATE_ABBR_TO_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08",
    "CT": "09", "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15",
    "ID": "16", "IL": "17", "IN": "18", "IA": "19", "KS": "20", "KY": "21",
    "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56",
}

POLICY_STATE_SCORE = {
    "TX": 76,
    "FL": 75,
    "TN": 74,
    "NC": 72,
    "GA": 72,
    "UT": 74,
    "CO": 70,
    "CA": 63,
    "NY": 61,
    "WA": 68,
    "IL": 62,
    "MA": 67,
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


class PipelineError(RuntimeError):
    pass


def http_get_json(url: str, retries: int = 3, backoff_seconds: float = 0.8) -> Any:
    headers = {
        "User-Agent": "market-attractiveness-agent/official-data-pipeline",
        "Accept": "application/json",
    }

    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
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

        variables = [
            "NAME",
            "B01003_001E",
            "B19013_001E",
            "B25064_001E",
            "B23025_003E",
            "B23025_005E",
            "B15003_001E",
            "B15003_022E",
            "B15003_023E",
            "B15003_024E",
            "B15003_025E",
        ]

        url = f"https://api.census.gov/data/2023/acs/acs1?get={','.join(variables)}&for=state:{fips}"
        rows = http_get_json(url)

        if not isinstance(rows, list) or len(rows) < 2:
            return {}

        header, values = rows[0], rows[1]
        d = dict(zip(header, values))

        lf = float(d.get("B23025_003E", 0) or 0)
        unemp = float(d.get("B23025_005E", 0) or 0)
        edu_total = float(d.get("B15003_001E", 0) or 0)

        edu_ba_plus = sum(
            float(d.get(k, 0) or 0)
            for k in ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
        )

        unemployment_rate = (unemp / lf * 100.0) if lf > 0 else 0.0
        education_ba_plus_rate = (edu_ba_plus / edu_total * 100.0) if edu_total > 0 else 0.0

        return {
            "population": float(d.get("B01003_001E", 0) or 0),
            "median_income": float(d.get("B19013_001E", 0) or 0),
            "median_rent": float(d.get("B25064_001E", 0) or 0),
            "unemployment_rate": unemployment_rate,
            "education_ba_plus_rate": education_ba_plus_rate,
        }


class BLSFetcher:
    def fetch(self, city: ResolvedCity) -> Dict[str, float]:
        if city.country_code != "US" or not city.state_abbr:
            return {}

        state_code = STATE_ABBR_TO_FIPS.get(city.state_abbr)
        if not state_code:
            return {}

        series = f"LAUST{state_code}0000000000003"
        body = json.dumps(
            {"seriesid": [series], "startyear": "2024", "endyear": "2025"}
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "market-attractiveness-agent",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {}

        try:
            data = payload["Results"]["series"][0]["data"]
            latest = float(data[0]["value"])
            return {"bls_unemployment_rate": latest}
        except Exception:
            return {}


class FREDFetcher:
    def fetch(self, city: ResolvedCity) -> Dict[str, float]:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return {}

        url = (
            "https://api.stlouisfed.org/fred/series/observations"
            f"?series_id=UNRATE&api_key={api_key}&file_type=json&limit=1&sort_order=desc"
        )

        try:
            payload = http_get_json(url)
            obs = payload.get("observations", [])
            if not obs:
                return {}
            return {"fred_unrate": float(obs[0]["value"])}
        except Exception:
            return {}


class MetricNormalizer:
    @staticmethod
    def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, v))

    def normalize(
        self,
        city: ResolvedCity,
        acs: Dict[str, float],
        bls: Dict[str, float],
        fred: Dict[str, float],
    ) -> Dict[str, DimensionMetric]:
        d = date.today().isoformat()
        has_acs = bool(acs)
        has_bls = bool(bls)
        level = "state" if has_acs or has_bls else "resolver"

        unemp = bls.get(
            "bls_unemployment_rate",
            acs.get("unemployment_rate", fred.get("fred_unrate", 5.0)),
        )
        income = acs.get("median_income", 65000.0)
        rent = acs.get("median_rent", 1400.0)
        edu = acs.get("education_ba_plus_rate", 30.0)
        pop = acs.get("population", 1_000_000.0)

        return {
            "gdp_and_macro_growth": DimensionMetric(
                raw_value=unemp,
                normalized_score=self._clamp(84 - unemp * 4.4),
                source="BLS/ACS/FRED",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="direct" if has_bls else "proxy",
                confidence_score=0.72 if has_bls else 0.60 if has_acs else 0.45,
                explanation="Macro/labor composite from unemployment indicators.",
            ),
            "industry_concentration": DimensionMetric(
                raw_value=edu,
                normalized_score=self._clamp(40 + edu * 0.7 + city.importance * 15),
                source="ACS + resolver",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.62 if has_acs else 0.48,
                explanation="Industry proxy from BA+ education share and resolver importance.",
            ),
            "consulting_demand_signals": DimensionMetric(
                raw_value=city.importance,
                normalized_score=self._clamp(
                    22
                    + city.importance * 24
                    + income / 4200.0
                    + max(0.0, 7.5 - unemp) * 2.7
                    + edu * 0.45
                ),
                source="Resolver + ACS + BLS",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.65 if has_bls or has_acs else 0.40,
                explanation="Consulting demand proxy tuned for TGG: city prominence, income, labor tightness, and education/talent base.",
            ),
            "mid_market_fit": DimensionMetric(
                raw_value=city.importance,
                normalized_score=self._clamp(
                    85
                    - abs(city.importance - 0.55) * 85
                    + max(0.0, 8.0 - unemp) * 1.5
                    + min(15.0, edu * 0.25)
                ),
                source="Resolver + ACS + BLS",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.60 if has_acs or has_bls else 0.35,
                explanation="Mid-market fit proxy: rewards markets large enough to support consulting demand but not so large or saturated that smaller-firm winnability declines.",
            ),
            "cost_of_living_and_operating": DimensionMetric(
                raw_value=rent,
                normalized_score=self._clamp(92 - rent / 32.0 + income / 16000.0),
                source="ACS",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="direct" if has_acs else "proxy",
                confidence_score=0.68 if has_acs else 0.42,
                explanation="Cost proxy from rent-to-income relationship; lower operating cost improves smaller-firm attractiveness.",
            ),
            "competitive_intensity": DimensionMetric(
                raw_value=city.importance,
                normalized_score=self._clamp(
                    100 - (52 + city.importance * 48 + pop / 12_000_000.0)
                ),
                source="Resolver + ACS",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.50 if has_acs else 0.40,
                explanation="Winnability proxy: lower saturation and lower prominence produce higher scores for smaller-firm entry.",
            ),
            "policy_environment": DimensionMetric(
                raw_value=float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66)),
                normalized_score=float(POLICY_STATE_SCORE.get(city.state_abbr or "", 66)),
                source="State policy lookup",
                source_date=d,
                geographic_level_used="state",
                direct_vs_proxy="proxy",
                confidence_score=0.50,
                explanation="Maintainable state-level policy lookup table.",
            ),
            "qualitative_momentum_signals": DimensionMetric(
                raw_value=city.importance,
                normalized_score=self._clamp(
                    42 + city.importance * 30 + max(0.0, 8.0 - unemp) * 2.2
                ),
                source="Resolver + labor",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.55 if has_bls or has_acs else 0.35,
                explanation="Momentum proxy from resolver importance and labor conditions.",
            ),
            "target_company_estimate": DimensionMetric(
                raw_value=income,
                normalized_score=0.0,
                source="ACS + resolver",
                source_date=d,
                geographic_level_used=level,
                direct_vs_proxy="proxy",
                confidence_score=0.45,
                explanation="Supporting metric used to estimate $500M+ target company count.",
            ),
        }


class MarketInputBuilder:
    def build(self, city: ResolvedCity, metrics: Dict[str, DimensionMetric]) -> MarketInput:
        income = metrics["target_company_estimate"].raw_value
        edu = metrics["industry_concentration"].raw_value

        count_500m_plus = int(
            max(
                5,
                min(
                    120,
                    ((income / 1800) / 4) + (edu / 3) + city.importance * 6,
                ),
            )
        )

        def dim(key: str) -> DimensionInput:
            m = metrics[key]
            return DimensionInput(
                value=round(m.normalized_score, 2),
                confidence=round(m.confidence_score, 2),
                note=(
                    f"{m.explanation} "
                    f"Source={m.source}; level={m.geographic_level_used}; "
                    f"type={m.direct_vs_proxy}; date={m.source_date}."
                ),
            )

        return MarketInput(
            market_name=city.query,
            gdp_and_macro_growth=dim("gdp_and_macro_growth"),
            industry_concentration=dim("industry_concentration"),
            target_companies=TargetCompanyInput(
                count_500m_plus=count_500m_plus,
                confidence=0.45,
                note="Proxy estimate for $500M+ revenue companies using income, education, and city prominence.",
            ),
            consulting_demand_signals=dim("consulting_demand_signals"),
            mid_market_fit=dim("mid_market_fit"),
            cost_of_living_and_operating=dim("cost_of_living_and_operating"),
            competitive_intensity=dim("competitive_intensity"),
            policy_environment=dim("policy_environment"),
            qualitative_momentum_signals=dim("qualitative_momentum_signals"),
        )
