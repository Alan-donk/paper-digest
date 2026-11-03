from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from app.models import Paper


GENERIC_TITLE_PATTERNS = (
    re.compile(r"^a study of\b", re.IGNORECASE),
    re.compile(r"^towards\b", re.IGNORECASE),
    re.compile(r"^some notes on\b", re.IGNORECASE),
    re.compile(r"^an approach to\b", re.IGNORECASE),
    re.compile(r"^investigating\b", re.IGNORECASE),
)


def score_paper(
    paper: Paper,
    keywords: list[str],
    required_categories: list[str] | None = None,
    reference_time: datetime | None = None,
) -> tuple[float, list[str]]:
    required_categories = required_categories or []
    current_time = reference_time or datetime.now(timezone.utc)
    title_lower = paper.title.lower()
    abstract_lower = paper.abstract.lower()

    score = 0.0
    matched_keywords: list[str] = []

    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        if not keyword_lower:
            continue
        if keyword_lower in title_lower:
            score += 3.0
            matched_keywords.append(keyword)
        elif keyword_lower in abstract_lower:
            score += 1.8
            matched_keywords.append(keyword)
        else:
            token_hits = _count_token_hits(keyword_lower, title_lower, abstract_lower)
            score += min(token_hits * 0.4, 1.6)
            if token_hits >= 2:
                matched_keywords.append(keyword)

    if required_categories:
        category_hits = sum(1 for category in paper.categories if category in required_categories)
        score += min(category_hits * 1.4, 2.8)

    paper_age = current_time - max(paper.published, paper.updated)
    if paper_age <= timedelta(days=7):
        score += 2.0
    elif paper_age <= timedelta(days=30):
        score += 1.0

    if paper.doi:
        score += 1.0
    if paper.journal_ref:
        score += 0.8
    if len(paper.abstract) < 280:
        score -= 1.2
    if _is_generic_title(paper.title):
        score -= 1.0

    return round(score, 2), _unique_preserve_order(matched_keywords)


def rank_papers(
    papers: list[Paper],
    keywords: list[str],
    required_categories: list[str] | None = None,
    min_score: float = 0.0,
    top_n: int | None = None,
    reference_time: datetime | None = None,
) -> list[Paper]:
    scored_papers: list[Paper] = []
    for paper in papers:
        score, matched_keywords = score_paper(
            paper=paper,
            keywords=keywords,
            required_categories=required_categories,
            reference_time=reference_time,
        )
        if score < min_score:
            continue
        scored_papers.append(
            paper.model_copy(
                update={
                    "score": score,
                    "matched_keywords": matched_keywords,
                }
            )
        )

    scored_papers.sort(key=lambda item: (item.score, item.updated, item.published), reverse=True)
    if top_n is not None:
        return scored_papers[:top_n]
    return scored_papers


def _count_token_hits(keyword: str, title_lower: str, abstract_lower: str) -> int:
    tokens = [token for token in re.split(r"[\s\-_/,]+", keyword) if len(token) >= 4]
    unique_hits = 0
    for token in set(tokens):
        if token in title_lower:
            unique_hits += 2
        elif token in abstract_lower:
            unique_hits += 1
    return unique_hits


def _is_generic_title(title: str) -> bool:
    normalized = title.strip()
    if len(normalized.split()) <= 3:
        return True
    return any(pattern.search(normalized) for pattern in GENERIC_TITLE_PATTERNS)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
