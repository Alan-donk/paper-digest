import logging

import requests

from app.arxiv_client import ArxivClient


ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <updated>2026-04-20T00:00:00Z</updated>
    <published>2026-04-19T00:00:00Z</published>
    <title>Test paper</title>
    <summary>Test abstract</summary>
  </entry>
</feed>
"""


class DummyResponse:
    def __init__(self, status_code: int, text: str = "", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)


def test_fetch_feed_retries_after_429(monkeypatch) -> None:
    client = ArxivClient(delay_seconds=0.0, logger=logging.getLogger("test.arxiv"))
    responses = [
        DummyResponse(status_code=429, headers={"Retry-After": "0"}),
        DummyResponse(status_code=200, text=ATOM_FEED),
    ]
    calls: list[str] = []

    def fake_get(url: str, timeout: int) -> DummyResponse:
        calls.append(url)
        return responses[len(calls) - 1]

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("app.arxiv_client.sleep", lambda _: None)

    entries = client._fetch_feed(keyword="test", max_results=5, sort_by="submittedDate")

    assert len(calls) == 2
    assert len(entries) == 1
