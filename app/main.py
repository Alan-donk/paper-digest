from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import sys

from app.arxiv_client import ArxivClient
from app.config import load_config
from app.email_renderer import EmailRenderer
from app.email_sender import EmailSender
from app.filter import rank_papers
from app.models import DigestItem
from app.storage import SentPaperStorage
from app.summarizer import DeepSeekSummarizer
from app.utils import now_utc, setup_logging


@dataclass
class RunStats:
    pulled_papers: int = 0
    unsent_papers: int = 0
    filtered_papers: int = 0
    pushed_papers: int = 0
    failed_summaries: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily arXiv paper digest")
    parser.add_argument("--run-once", action="store_true", help="Execute the pipeline once.")
    parser.add_argument("--dry-run", action="store_true", help="Render HTML locally without sending email.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    logger = setup_logging(config.log_file, debug=args.debug)
    logger.info("Starting paper digest pipeline")

    if args.run_once:
        logger.info("Running in --run-once mode")

    stats = RunStats()

    try:
        storage = SentPaperStorage(config.db_path)
        storage.init_db()

        arxiv_client = ArxivClient(
            timeout=config.request_timeout,
            delay_seconds=config.arxiv_delay_seconds,
            max_retry_attempts=config.arxiv_max_retry_attempts,
            retry_delay_seconds=config.arxiv_retry_delay_seconds,
            logger=logger,
        )
        papers = arxiv_client.search_papers(
            keywords=config.keywords,
            max_results=config.max_results_per_keyword,
            sort_by=config.sort_by,
            lookback_days=config.lookback_days,
        )
        stats.pulled_papers = len(papers)

        unsent_papers = [paper for paper in papers if not storage.has_sent(paper.arxiv_id)]
        stats.unsent_papers = len(unsent_papers)

        ranked_papers = rank_papers(
            papers=unsent_papers,
            keywords=config.keywords,
            required_categories=config.required_categories,
            min_score=config.min_score,
            top_n=config.top_n,
            reference_time=now_utc(),
        )
        stats.filtered_papers = len(ranked_papers)
        logger.info(
            "Papers pulled=%s unsent=%s filtered=%s",
            stats.pulled_papers,
            stats.unsent_papers,
            stats.filtered_papers,
        )

        summarizer = DeepSeekSummarizer(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model=config.deepseek_model,
            timeout=config.request_timeout,
            logger=logger,
        )
        digest_items: list[DigestItem] = []
        for paper in ranked_papers:
            try:
                summary = summarizer.summarize_paper(paper)
            except Exception:  # pragma: no cover
                stats.failed_summaries += 1
                logger.exception("Unexpected summary failure for %s", paper.arxiv_id)
                continue
            if "Fallback summary generated" in " ".join(summary.innovation):
                stats.failed_summaries += 1
            digest_items.append(
                DigestItem(
                    paper=paper,
                    summary=summary,
                    score=paper.score,
                    matched_keywords=paper.matched_keywords,
                )
            )

        renderer = EmailRenderer(config.template_dir)
        current_time = datetime.now()
        html = renderer.render_digest(
            date=current_time,
            keywords=config.keywords,
            items=digest_items,
        )

        subject = f"{config.email_subject_prefix} {current_time:%Y-%m-%d}"

        if args.dry_run:
            config.dry_run_output.write_text(html, encoding="utf-8")
            logger.info("Dry-run HTML saved to %s", config.dry_run_output)
        else:
            _validate_email_config(config)
            sender = EmailSender(
                smtp_host=config.smtp_host or "",
                smtp_port=config.smtp_port,
                smtp_user=config.smtp_user,
                smtp_pass=config.smtp_pass,
                email_from=config.email_from or "",
                logger=logger,
            )
            sender.send_html_email(
                recipients=config.email_to,
                subject=subject,
                html_body=html,
            )
            for item in digest_items:
                storage.mark_sent(
                    arxiv_id=item.paper.arxiv_id,
                    title=item.paper.title,
                    sent_date=current_time.date(),
                    keyword_group=", ".join(item.matched_keywords or config.keywords),
                )

        stats.pushed_papers = len(digest_items)
        logger.info(
            "Run finished. pulled=%s filtered=%s pushed=%s failed_summaries=%s",
            stats.pulled_papers,
            stats.filtered_papers,
            stats.pushed_papers,
            stats.failed_summaries,
        )
        print_stats(stats)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed: %s", exc)
        print_stats(stats)
        return 1


def _validate_email_config(config: object) -> None:
    required_fields = {
        "smtp_host": getattr(config, "smtp_host", None),
        "smtp_port": getattr(config, "smtp_port", None),
        "email_from": getattr(config, "email_from", None),
        "email_to": getattr(config, "email_to", None),
    }
    missing = [name for name, value in required_fields.items() if not value]
    if missing:
        raise ValueError(f"Missing email configuration fields: {', '.join(missing)}")


def print_stats(stats: RunStats) -> None:
    print(f"拉取论文数: {stats.pulled_papers}")
    print(f"过滤后论文数: {stats.filtered_papers}")
    print(f"实际推送数: {stats.pushed_papers}")
    print(f"失败总结数: {stats.failed_summaries}")


if __name__ == "__main__":
    sys.exit(main())
