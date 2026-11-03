from pathlib import Path

from app.config import load_config


def _write_config(path: Path) -> None:
    path.write_text("keywords:\n  - test topic\n", encoding="utf-8")


def test_load_config_prefers_generic_llm_variables(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    _write_config(config_path)
    env_path.write_text(
        "LLM_API_KEY=generic-key\n"
        "LLM_BASE_URL=https://example.com/v1\n"
        "LLM_MODEL=example-model\n"
        "DEEPSEEK_API_KEY=legacy-key\n",
        encoding="utf-8",
    )
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    config = load_config(config_path, env_path)

    assert config.deepseek_api_key == "generic-key"
    assert config.deepseek_base_url == "https://example.com/v1"
    assert config.deepseek_model == "example-model"


def test_load_config_supports_legacy_deepseek_variables(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    _write_config(config_path)
    env_path.write_text("DEEPSEEK_MODEL=legacy-model\n", encoding="utf-8")
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)

    config = load_config(config_path, env_path)

    assert config.deepseek_model == "legacy-model"
