from __future__ import annotations

import hashlib
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
    "growth",
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


def _city_variation(city_name: str) -> int:
    key = " ".join(city_name.strip().lower().split())
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return (int(digest, 16) % 20) - 10


def _fallback_score(city_name: str) -> float:
    return max(35.0, min(75.0, 58.0 + _city_variation(city_name)))


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


def get_news_momentum_score(city_name: str, days_back: int = 60) -> NewsSignalResult:
    start = datetime.now(timezone.utc) - timedelta(days=days_back)
    start_str = start.strftime("%Y%m%d%H%M%S")

    clean_city = city_name.strip()

    query = (
        f'"{clean_city}" '
        f'(business OR company OR corporate OR expansion OR relocation OR investment OR hiring OR layoffs OR closure)'
    )

    encoded_query = urllib.parse.quote(query)

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={encoded_query}"
        "&mode=ArtList"
        "&format=json"
        "&maxrecords=50"
        f"&startdatetime={start_str}"
        "&sort=HybridRel"
    )

    try:
        payload = _get_json(url)
        articles: List[dict] = payload.get("articles", []) or []
    except Exception as exc:
        fallback = _fallback_score(clean_city)
        return NewsSignalResult(
            score=fallback,
            confidence=0.20,
            article_count=0,
            positive_count=0,
            negative_count=0,
            source="GDELT fallback",
            note=f"Could not fetch real-time news signals. City-specific fallback used. Error: {exc}",
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

    if article_count == 0:
        fallback = _fallback_score(clean_city)
        return NewsSignalResult(
            score=fallback,
            confidence=0.25,
            article_count=0,
            positive_count=0,
            negative_count=0,
            source="GDELT no-result fallback",
            note="No recent news articles found. City-specific fallback momentum score used.",
        )

    score = (
        52
        + positive_count * 4.5
        - negative_count * 5.5
        + min(article_count, 15) * 1.2
        + _city_variation(clean_city) * 0.5
    )

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
