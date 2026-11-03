from datetime import datetime, timezone
from pathlib import Path

from app.email_renderer import EmailRenderer
from app.models import DigestItem, Paper, PaperSummary


def test_email_renderer_contains_key_fields() -> None:
    project_root = Path(__file__).resolve().parents[1]
    renderer = EmailRenderer(project_root / "templates")

    paper = Paper(
        arxiv_id="9999.9999",
        title="Multimodal Reasoning for Sensor Time Series",
        abstract="A rich abstract about multimodal reasoning and sensor data understanding.",
        authors=["Alice", "Bob"],
        published=datetime(2026, 4, 15, tzinfo=timezone.utc),
        updated=datetime(2026, 4, 16, tzinfo=timezone.utc),
        categories=["cs.AI", "cs.LG"],
        doi="10.1000/demo",
        journal_ref="NeurIPS 2026",
        pdf_url="https://arxiv.org/pdf/9999.9999.pdf",
        abs_url="https://arxiv.org/abs/9999.9999",
        score=8.6,
        matched_keywords=["multimodal reasoning"],
    )
    summary = PaperSummary(
        research_problem="The paper addresses how to reason over multimodal sensor streams.",
        innovation=["Combines symbolic and neural reasoning", "Uses aligned cross-modal representations"],
        method="A multimodal architecture over sensor streams and language cues.",
        significance="Useful for practical sensor intelligence tasks.",
        one_sentence_takeaway="A promising multimodal approach for sensor understanding.",
    )
    html = renderer.render_digest(
        date=datetime(2026, 4, 18),
        keywords=["multimodal reasoning"],
        items=[DigestItem(paper=paper, summary=summary, score=paper.score, matched_keywords=paper.matched_keywords)],
    )

    assert "Daily arXiv Paper Digest" in html
    assert "Multimodal Reasoning for Sensor Time Series" in html
    assert "A promising multimodal approach for sensor understanding." in html
    assert "https://arxiv.org/abs/9999.9999" in html
