from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3


class SentPaperStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS papers_sent (
                    arxiv_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    sent_date TEXT NOT NULL,
                    keyword_group TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_papers_sent_date
                ON papers_sent (sent_date DESC)
                """
            )
            conn.commit()

    def has_sent(self, arxiv_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM papers_sent WHERE arxiv_id = ? LIMIT 1",
                (arxiv_id,),
            ).fetchone()
            return row is not None

    def mark_sent(
        self,
        arxiv_id: str,
        title: str,
        sent_date: date | str,
        keyword_group: str,
    ) -> None:
        sent_date_value = sent_date.isoformat() if hasattr(sent_date, "isoformat") else str(sent_date)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO papers_sent (arxiv_id, title, sent_date, keyword_group)
                VALUES (?, ?, ?, ?)
                """,
                (arxiv_id, title, sent_date_value, keyword_group),
            )
            conn.commit()

    def get_recent_sent(self, limit: int = 20) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT arxiv_id, title, sent_date, keyword_group
                FROM papers_sent
                ORDER BY sent_date DESC, arxiv_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "arxiv_id": row[0],
                "title": row[1],
                "sent_date": row[2],
                "keyword_group": row[3],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)
