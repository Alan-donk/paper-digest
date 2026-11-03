from __future__ import annotations

import json
import logging
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.models import Paper, PaperSummary


class SummaryParseError(ValueError):
    """Raised when summary JSON cannot be parsed."""


class DeepSeekSummarizer:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout: int = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.logger = logger or logging.getLogger("paper_digest.summarizer")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def summarize_paper(self, paper: Paper) -> PaperSummary:
        if not self.api_key:
            self.logger.warning(
                "DEEPSEEK_API_KEY not configured. Falling back to local summary for paper %s",
                paper.arxiv_id,
            )
            return self._fallback_summary(paper)

        try:
            return self._request_summary_with_retry(paper)
        except Exception as exc:  # noqa: BLE001
            self.logger.exception(
                "Failed to summarize paper %s with DeepSeek. Falling back. Error: %s",
                paper.arxiv_id,
                exc,
            )
            return self._fallback_summary(paper)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((SummaryParseError, requests.RequestException)),
        reraise=True,
    )
    def _request_summary_with_retry(self, paper: Paper) -> PaperSummary:
        response = self.session.post(
            f"{self.base_url}/chat/completions",
            json=self._build_payload(paper),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return self._parse_summary_content(content)

    def _build_payload(self, paper: Paper) -> dict[str, Any]:
        system_prompt = (
            "You are a careful research assistant specialized in reading academic papers. "
            "Return only strict JSON. "
            "Do not output markdown, comments, explanations, or code fences."
        )
        user_prompt = (
            "Read the following paper title and abstract, and output exactly one valid JSON object in Chinese.\n"
            "You must only use information explicitly contained in the title and abstract.\n"
            "Do not speculate about experiments, datasets, results, or details not stated in the abstract.\n"
            "\n"
            "Return JSON only.\n"
            "Do not use markdown.\n"
            "Do not output any explanation before or after the JSON.\n"
            "Do not add extra keys.\n"
            "\n"
            "Output schema:\n"
            "{\n"
            '  "研究问题": "",\n'
            '  "核心创新点": ["", "", ""],\n'
            '  "方法": "",\n'
            '  "研究意义": "",\n'
            '  "一句话总结": ""\n'
            "}\n"
            "\n"
            "Requirements:\n"
            "- 全部内容使用简洁、专业、准确的中文\n"
            "- “研究问题”要明确指出论文想解决什么问题\n"
            "- “核心创新点”写 2 到 4 条，必须具体，避免空泛表述\n"
            "- “方法”概括核心技术路线，不要只是重复标题\n"
            "- “研究意义”说明这项工作为什么值得关注\n"
            "- “一句话总结”用一句简洁的话概括这篇工作的核心价值或结论\n"
            "- 如果摘要没有明确体现某一点，请直接说明“摘要中未明确说明”\n"
            "- 禁止编造 benchmark、实验结果、数据集或具体数值\n"
            "- 输出必须是严格合法 JSON\n"
            "\n"
            f"Title: {paper.title}\n"
            "\n"
            f"Abstract: {paper.abstract}"
        )
        return {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    def _parse_summary_content(self, content: str) -> PaperSummary:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise SummaryParseError(f"Summary JSON parse failed: {exc}") from exc
        normalized_payload = {
            "research_problem": payload.get("研究问题", payload.get("research_problem")),
            "innovation": payload.get("核心创新点", payload.get("innovation")),
            "method": payload.get("方法", payload.get("method")),
            "significance": payload.get("研究意义", payload.get("significance")),
            "one_sentence_takeaway": payload.get(
                "一句话总结",
                payload.get("可能局限", payload.get("one_sentence_takeaway")),
            ),
        }
        return PaperSummary.model_validate(normalized_payload)

    def _fallback_summary(self, paper: Paper) -> PaperSummary:
        abstract = paper.abstract.strip()
        clipped_abstract = abstract[:220].rstrip()
        if len(abstract) > 220:
            clipped_abstract += "..."
        return PaperSummary(
            research_problem=f"论文尝试研究的问题是：{paper.title}",
            innovation=[
                "未能获得结构化大模型总结，以下内容为基于标题和摘要的兜底整理。",
                "更细致的创新点仍建议结合原始摘要和论文全文进一步确认。",
            ],
            method=clipped_abstract or "摘要中未明确说明具体方法细节。",
            significance="该论文因关键词匹配、时效性和元数据质量而被筛选出来，具有一定关注价值。",
            one_sentence_takeaway="这篇工作与当前检索主题相关，建议结合摘要和全文进一步确认其具体贡献。",
        )
