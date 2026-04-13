from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DimensionInput:
    """Normalized dimension input.

    value: 0-100 attractiveness score for this dimension.
    confidence: 0.0-1.0 confidence in the value quality.
    note: short context from open-source data.
    """

    value: Optional[float] = None
    confidence: Optional[float] = None
    note: Optional[str] = None


@dataclass
class TargetCompanyInput:
    """Structured inputs for target-company density dimension.

    count_1000_plus: number of companies with 1,000+ employees.
    count_1b_plus: number of companies with $1B+ revenue.
    confidence: 0.0-1.0 confidence in company counts.
    note: optional context.
    """

    count_1000_plus: Optional[int] = None
    count_1b_plus: Optional[int] = None
    confidence: Optional[float] = None
    note: Optional[str] = None


@dataclass
class MarketInput:
    market_name: str
    population_growth_trends: DimensionInput = field(default_factory=DimensionInput)
    gdp_and_macro_growth: DimensionInput = field(default_factory=DimensionInput)
    industry_concentration: DimensionInput = field(default_factory=DimensionInput)
    target_companies: TargetCompanyInput = field(default_factory=TargetCompanyInput)
    consulting_demand_signals: DimensionInput = field(default_factory=DimensionInput)
    compensation_benchmarks: DimensionInput = field(default_factory=DimensionInput)
    cost_of_living_and_operating: DimensionInput = field(default_factory=DimensionInput)
    competitive_intensity: DimensionInput = field(default_factory=DimensionInput)
    policy_environment: DimensionInput = field(default_factory=DimensionInput)
    qualitative_momentum_signals: DimensionInput = field(default_factory=DimensionInput)


@dataclass
class DimensionScore:
    name: str
    score: Optional[float]
    weight: float
    confidence: float
    missing: bool
    rationale: str


@dataclass
class MarketScorecard:
    market_name: str
    overall_score: Optional[float]
    overall_confidence: float
    confidence_flag: str
    dimension_scores: List[DimensionScore]

    def as_dict(self) -> Dict[str, object]:
        return {
            "market_name": self.market_name,
            "overall_score": self.overall_score,
            "overall_confidence": self.overall_confidence,
            "confidence_flag": self.confidence_flag,
            "dimension_scores": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "confidence": d.confidence,
                    "missing": d.missing,
                    "rationale": d.rationale,
                }
                for d in self.dimension_scores
            ],
        }
