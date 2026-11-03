from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import logging
from time import sleep
from urllib.parse import urlencode

import feedparser
import requests

from app.models import Paper, SortBy
from app.utils import normalize_whitespace, now_utc, parse_arxiv_datetime, strip_arxiv_version


ARXIV_API_URL = "https://export.arxiv.org/api/query"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ArxivClient:
    def __init__(
        self,
        timeout: int = 20,
        delay_seconds: float = 0.6,
        max_retry_attempts: int = 2,
        retry_delay_seconds: float = 1.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.logger = logger or logging.getLogger("paper_digest.arxiv")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "paper-digest/0.1 (+https://arxiv.org/help/api/)",
            }
        )

    def search_papers(
        self,
        keywords: Iterable[str],
        max_results: int,
        sort_by: SortBy = "submittedDate",
        lookback_days: int | None = None,
    ) -> list[Paper]:
        deduped: dict[str, Paper] = {}
        cutoff = now_utc() - timedelta(days=lookback_days) if lookback_days else None

        for keyword in keywords:
            self.logger.info("Searching arXiv with keyword: %s", keyword)
            entries = self._fetch_feed(keyword=keyword, max_results=max_results, sort_by=sort_by)
            for entry in entries:
                paper = self._parse_entry(entry)
                if cutoff and paper.published < cutoff and paper.updated < cutoff:
                    continue
                existing = deduped.get(paper.arxiv_id)
                if existing is None or paper.updated > existing.updated:
                    deduped[paper.arxiv_id] = paper
            sleep(self.delay_seconds)

        papers = list(deduped.values())
        self.logger.info("Collected %s unique papers from arXiv", len(papers))
        return papers

    def _fetch_feed(self, keyword: str, max_results: int, sort_by: SortBy) -> list[object]:
        params = {
            "search_query": self._build_search_query(keyword),
            "start": 0,
            "max_results": max_results,
            "sortBy": self._map_sort_by(sort_by),
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API_URL}?{urlencode(params)}"
        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                parsed = feedparser.parse(response.text)
                return list(parsed.entries)
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code not in RETRYABLE_STATUS_CODES or attempt == self.max_retry_attempts:
                    raise
                wait_seconds = self._compute_retry_delay(exc.response, attempt)
                self.logger.warning(
                    "arXiv request hit status %s for keyword '%s' (attempt %s/%s). "
                    "Retrying in %.1f seconds.",
                    status_code,
                    keyword,
                    attempt,
                    self.max_retry_attempts,
                    wait_seconds,
                )
                sleep(wait_seconds)
            except requests.RequestException as exc:
                if attempt == self.max_retry_attempts:
                    raise
                wait_seconds = self._compute_retry_delay(None, attempt)
                self.logger.warning(
                    "arXiv request failed for keyword '%s' with %s (attempt %s/%s). "
                    "Retrying in %.1f seconds.",
                    keyword,
                    exc.__class__.__name__,
                    attempt,
                    self.max_retry_attempts,
                    wait_seconds,
                )
                sleep(wait_seconds)

        return []

    def _compute_retry_delay(self, response: requests.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(min(float(retry_after), 5.0), self.retry_delay_seconds)
                except ValueError:
                    pass
        return self.retry_delay_seconds

    def _build_search_query(self, keyword: str) -> str:
        escaped = keyword.replace('"', "")
        return f'all:"{escaped}"'

    def _map_sort_by(self, sort_by: SortBy) -> str:
        mapping = {
            "submittedDate": "submittedDate",
            "updatedDate": "lastUpdatedDate",
            "relevance": "relevance",
        }
        return mapping[sort_by]

    def _parse_entry(self, entry: object) -> Paper:
        raw_id = str(getattr(entry, "id")).rstrip("/").split("/")[-1]
        clean_id = strip_arxiv_version(raw_id)
        authors = [normalize_whitespace(author.name) for author in getattr(entry, "authors", [])]
        categories = [tag.term for tag in getattr(entry, "tags", []) if getattr(tag, "term", None)]
        abs_url = f"https://arxiv.org/abs/{clean_id}"
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        title = normalize_whitespace(getattr(entry, "title", ""))
        abstract = normalize_whitespace(getattr(entry, "summary", ""))
        doi = getattr(entry, "arxiv_doi", None)
        journal_ref = getattr(entry, "arxiv_journal_ref", None)

        return Paper(
            arxiv_id=clean_id,
            title=title,
            abstract=abstract,
            authors=authors,
            published=parse_arxiv_datetime(getattr(entry, "published")),
            updated=parse_arxiv_datetime(getattr(entry, "updated")),
            categories=categories,
            doi=normalize_whitespace(doi) if doi else None,
            journal_ref=normalize_whitespace(journal_ref) if journal_ref else None,
            pdf_url=pdf_url,
            abs_url=abs_url,
        )
