from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from app.models import AppConfig
from app.utils import ensure_directories


def load_config(config_path: Path | None = None, env_path: Path | None = None) -> AppConfig:
    project_root = Path(__file__).resolve().parents[1]
    resolved_config_path = config_path or project_root / "config.yaml"
    resolved_env_path = env_path or project_root / ".env"

    load_dotenv(resolved_env_path)

    with resolved_config_path.open("r", encoding="utf-8") as file:
        raw_config: dict[str, Any] = yaml.safe_load(file) or {}

    template_dir = project_root / "templates"
    data_dir = project_root / "data"
    log_dir = project_root / "logs"
    ensure_directories(template_dir, data_dir, log_dir)

    config = AppConfig(
        **raw_config,
        # LLM_* is provider-neutral. DEEPSEEK_* remains supported for existing users.
        deepseek_api_key=_getenv_prefer("LLM_API_KEY", "DEEPSEEK_API_KEY"),
        deepseek_base_url=_getenv_prefer(
            "LLM_BASE_URL", "DEEPSEEK_BASE_URL", default="https://api.deepseek.com"
        ),
        deepseek_model=_getenv_prefer("LLM_MODEL", "DEEPSEEK_MODEL", default="deepseek-chat"),
        smtp_host=_getenv("SMTP_HOST"),
        smtp_port=int(_getenv("SMTP_PORT", "587")),
        smtp_user=_getenv("SMTP_USER"),
        smtp_pass=_getenv("SMTP_PASS"),
        email_from=_getenv("EMAIL_FROM"),
        email_to=_getenv("EMAIL_TO", ""),
        project_root=project_root,
        template_dir=template_dir,
        data_dir=data_dir,
        log_dir=log_dir,
        db_path=data_dir / "papers.db",
        dry_run_output=data_dir / "digest_preview.html",
        log_file=log_dir / "app.log",
    )
    return config


def _getenv(name: str, default: str | None = None) -> str | None:
    from os import getenv

    return getenv(name, default)


def _getenv_prefer(*names: str, default: str | None = None) -> str | None:
    """Return the first explicitly configured environment variable."""
    from os import getenv

    for name in names:
        value = getenv(name)
        if value is not None:
            return value
    return default
