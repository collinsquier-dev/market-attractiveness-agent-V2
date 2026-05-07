from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List


@dataclass
class NewsSignalResult:
    score: float
    confidence: float
    article_count: int
    positive_count: int
    negative_count: int
    source: str
    note: str


POSITIVE_TERMS = [
    "expansion",
    "relocation",
    "headquarters",
    "new office",
    "investment",
    "economic development",
    "hiring",
    "job growth",
    "facility expansion",
    "corporate expansion",
]

NEGATIVE_TERMS = [
    "layoffs",
    "closure",
    "bankruptcy",
    "downsizing",
    "restructuring",
    "plant closure",
    "job cuts",
    "exits",
]


def _get_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "market-attractiveness-agent/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _article_text(article: dict) -> str:
    return " ".join(
        str(article.get(k, "") or "")
        for k in ["title", "seendate", "sourceCountry", "domain", "url"]
    ).lower()


def get_news_momentum_score(city_name: str, days_back: int = 45) -> NewsSignalResult:
    start = datetime.now(timezone.utc) - timedelta(days=days_back)
    start_str = start.strftime("%Y%m%d%H%M%S")

    query = (
        f'"{city_name}" '
        f'(expansion OR relocation OR headquarters OR investment OR hiring OR layoffs OR closure OR restructuring)'
    )

    encoded_query = urllib.parse.quote(query)

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={encoded_query}"
        "&mode=ArtList"
        "&format=json"
        "&maxrecords=25"
        f"&startdatetime={start_str}"
        "&sort=HybridRel"
    )

    try:
        payload = _get_json(url)
        articles: List[dict] = payload.get("articles", []) or []
    except Exception as exc:
        return NewsSignalResult(
            score=58.0,
            confidence=0.20,
            article_count=0,
            positive_count=0,
            negative_count=0,
            source="GDELT fallback",
            note=f"Could not fetch real-time news signals; fallback used. Error: {exc}",
        )

    positive_count = 0
    negative_count = 0

    for article in articles:
        text = _article_text(article)

        if any(term in text for term in POSITIVE_TERMS):
            positive_count += 1

        if any(term in text for term in NEGATIVE_TERMS):
            negative_count += 1

    article_count = len(articles)

    score = 55 + positive_count * 4 - negative_count * 5 + min(article_count, 10) * 1.5
    score = max(0.0, min(100.0, score))

    confidence = 0.35
    if article_count >= 5:
        confidence = 0.50
    if article_count >= 10:
        confidence = 0.65

    note = (
        f"Real-time qualitative momentum from GDELT news search. "
        f"Articles={article_count}; positive signals={positive_count}; negative signals={negative_count}."
    )

    return NewsSignalResult(
        score=round(score, 2),
        confidence=round(confidence, 2),
        article_count=article_count,
        positive_count=positive_count,
        negative_count=negative_count,
        source="GDELT DOC API",
        note=note,
    )
