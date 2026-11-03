from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


SortBy = Literal["submittedDate", "updatedDate", "relevance"]


class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str] = Field(default_factory=list)
    published: datetime
    updated: datetime
    categories: list[str] = Field(default_factory=list)
    doi: str | None = None
    journal_ref: str | None = None
    pdf_url: str
    abs_url: str
    score: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)

    @field_validator("title", "abstract", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return " ".join(str(value).split())

    @field_validator("authors", "categories", mode="before")
    @classmethod
    def normalize_string_list(cls, value: list[str] | tuple[str, ...] | None) -> list[str]:
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]


class PaperSummary(BaseModel):
    research_problem: str
    innovation: list[str] = Field(default_factory=list)
    method: str
    significance: str
    one_sentence_takeaway: str

    @field_validator("innovation", mode="before")
    @classmethod
    def ensure_innovation_list(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator(
        "research_problem",
        "method",
        "significance",
        "one_sentence_takeaway",
        mode="before",
    )
    @classmethod
    def ensure_non_empty_text(cls, value: str) -> str:
        text = " ".join(str(value).split()).strip()
        return text or "Not available."


class DigestItem(BaseModel):
    paper: Paper
    summary: PaperSummary
    score: float
    matched_keywords: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    keywords: list[str]
    max_results_per_keyword: int = 20
    top_n: int = 5
    min_score: float = 4.0
    lookback_days: int = 7
    required_categories: list[str] = Field(default_factory=list)
    email_subject_prefix: str = "[Daily Paper Digest]"
    sort_by: SortBy = "submittedDate"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    email_from: str | None = None
    email_to: list[str] = Field(default_factory=list)
    project_root: Path
    template_dir: Path
    data_dir: Path
    log_dir: Path
    db_path: Path
    dry_run_output: Path
    log_file: Path
    request_timeout: int = 20
    arxiv_delay_seconds: float = 0.6
    arxiv_max_retry_attempts: int = 2
    arxiv_retry_delay_seconds: float = 1.0

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("keywords must not be empty")
        return cleaned

    @field_validator("required_categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: list[str] | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value if item.strip()]

    @field_validator("email_to", mode="before")
    @classmethod
    def normalize_email_to(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def validate_ranges(self) -> "AppConfig":
        if self.max_results_per_keyword <= 0:
            raise ValueError("max_results_per_keyword must be > 0")
        if self.top_n <= 0:
            raise ValueError("top_n must be > 0")
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be > 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")
        if self.arxiv_max_retry_attempts <= 0:
            raise ValueError("arxiv_max_retry_attempts must be > 0")
        if self.arxiv_retry_delay_seconds < 0:
            raise ValueError("arxiv_retry_delay_seconds must be >= 0")
        return self
