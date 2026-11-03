from datetime import date
from pathlib import Path

from app.storage import SentPaperStorage


def test_storage_init_mark_and_query(tmp_path: Path) -> None:
    db_path = tmp_path / "papers.db"
    storage = SentPaperStorage(db_path)
    storage.init_db()

    assert storage.has_sent("1234.5678") is False

    storage.mark_sent(
        arxiv_id="1234.5678",
        title="Test Paper",
        sent_date=date(2026, 4, 18),
        keyword_group="multimodal reasoning",
    )

    assert storage.has_sent("1234.5678") is True

    rows = storage.get_recent_sent(limit=5)
    assert len(rows) == 1
    assert rows[0]["arxiv_id"] == "1234.5678"
    assert rows[0]["keyword_group"] == "multimodal reasoning"
