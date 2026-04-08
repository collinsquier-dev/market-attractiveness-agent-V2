from __future__ import annotations

from .models import MarketScorecard


def build_narrative_prompt(scorecard: MarketScorecard) -> str:
    """Build a prompt/template for narrative generation from scored data."""
    lines = [
        "You are an analyst writing a market attractiveness summary.",
        f"Market: {scorecard.market_name}",
        f"Overall score (0-100): {scorecard.overall_score}",
        f"Overall confidence (0-1): {scorecard.overall_confidence}",
        f"Confidence flag: {scorecard.confidence_flag}",
        "",
        "Dimension details:",
    ]

    for d in scorecard.dimension_scores:
        lines.append(
            f"- {d.name}: score={d.score}, confidence={d.confidence}, missing={d.missing}, rationale={d.rationale}"
        )

    lines.extend(
        [
            "",
            "Write output with these sections:",
            "1) Market attractiveness verdict (short)",
            "2) Top structural strengths",
            "3) Structural risks / constraints",
            "4) Data quality caveats using confidence_flag",
            "5) Momentum narrative from qualitative signals",
            "Do not include leadership, internal network, partner fit, or entry model recommendations.",
        ]
    )

    return "\n".join(lines)


def render_narrative_summary(scorecard: MarketScorecard) -> str:
    """Simple deterministic narrative for local runs without an LLM call."""
    strengths = [d for d in scorecard.dimension_scores if (d.score or 0) >= 70 and not d.missing]
    risks = [d for d in scorecard.dimension_scores if (d.score or 100) < 50 and not d.missing]
    missing = [d for d in scorecard.dimension_scores if d.missing]

    verdict = "Attractive" if (scorecard.overall_score or 0) >= 70 else "Moderately attractive" if (scorecard.overall_score or 0) >= 55 else "Challenging"

    lines = [
        f"Verdict: {verdict} (score={scorecard.overall_score}, confidence={scorecard.overall_confidence}).",
        "Strengths: " + (", ".join(d.name for d in strengths) if strengths else "No clear strengths identified from current inputs."),
        "Risks: " + (", ".join(d.name for d in risks) if risks else "No major low-scoring constraints identified from current inputs."),
        f"Data quality: {scorecard.confidence_flag}. Missing dimensions: {len(missing)}.",
    ]

    q = next((d for d in scorecard.dimension_scores if "Qualitative" in d.name), None)
    if q:
        lines.append(f"Momentum narrative: {q.rationale}")

    return "\n".join(lines)
