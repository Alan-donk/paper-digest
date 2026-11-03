from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import DigestItem


class EmailRenderer:
    def __init__(self, template_dir: Path) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_digest(
        self,
        date: datetime,
        keywords: list[str],
        items: list[DigestItem],
    ) -> str:
        template = self.env.get_template("daily_digest.html")
        return template.render(
            digest_date=date.strftime("%Y-%m-%d"),
            keywords=keywords,
            total_items=len(items),
            items=items,
        )
