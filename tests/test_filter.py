from datetime import datetime, timedelta, timezone

from app.filter import rank_papers, score_paper
from app.models import Paper


def make_paper(
    arxiv_id: str,
    title: str,
    abstract: str,
    categories: list[str],
    days_ago: int,
    doi: str | None = None,
    journal_ref: str | None = None,
) -> Paper:
    now = datetime.now(timezone.utc)
    published = now - timedelta(days=days_ago)
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=["Alice", "Bob"],
        published=published,
        updated=published,
        categories=categories,
        doi=doi,
        journal_ref=journal_ref,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
    )


def test_score_paper_prefers_recent_and_metadata_complete_paper() -> None:
    paper = make_paper(
        arxiv_id="1234.5678",
        title="Large Language Model for Time Series Forecasting",
        abstract="This paper proposes a multimodal reasoning pipeline for time series understanding and forecasting.",
        categories=["cs.LG", "cs.AI"],
        days_ago=3,
        doi="10.1000/example",
        journal_ref="ICML 2026",
    )

    score, matched = score_paper(
        paper,
        keywords=["large language model time series", "multimodal reasoning"],
        required_categories=["cs.LG", "cs.CL"],
        reference_time=datetime.now(timezone.utc),
    )

    assert score >= 7.0
    assert "large language model time series" in matched


def test_rank_papers_sorts_and_filters_by_threshold() -> None:
    high = make_paper(
        arxiv_id="1111.1111",
        title="Large Language Model for Sensor Signal Understanding",
        abstract="A detailed method for sensor signal understanding with strong experiments and rich metadata.",
        categories=["cs.AI"],
        days_ago=2,
        doi="10.1/abc",
    )
    low = make_paper(
        arxiv_id="2222.2222",
        title="A Study of Models",
        abstract="Short abstract.",
        categories=["math.OC"],
        days_ago=40,
    )

    ranked = rank_papers(
        papers=[low, high],
        keywords=["sensor signal understanding"],
        required_categories=["cs.AI"],
        min_score=2.0,
        top_n=5,
        reference_time=datetime.now(timezone.utc),
    )

    assert len(ranked) == 1
    assert ranked[0].arxiv_id == "1111.1111"
    assert ranked[0].score >= 2.0
