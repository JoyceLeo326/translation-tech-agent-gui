from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    openai_api_key: str | None
    openai_model: str
    openai_organization: str | None
    openai_project: str | None
    coze_api_token: str | None
    coze_workflow_id: str | None
    coze_api_base: str
    coze_timeout_seconds: float
    debug: bool

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_coze_workflow(self) -> bool:
        return bool(self.coze_api_token and self.coze_workflow_id)


def load_config() -> AppConfig:
    for env_file in _candidate_env_files():
        if env_file.exists():
            load_dotenv(env_file, override=False)

    return AppConfig(
        app_name="文澜 · 中国文化多模态外译",
        openai_api_key=_blank_to_none(os.getenv("OPENAI_API_KEY")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_organization=_blank_to_none(os.getenv("OPENAI_ORGANIZATION")),
        openai_project=_blank_to_none(os.getenv("OPENAI_PROJECT")),
        coze_api_token=_blank_to_none(os.getenv("COZE_API_TOKEN")),
        coze_workflow_id=_blank_to_none(
            os.getenv("COZE_WORKFLOW_ID", "7661678571702747178")
        ),
        coze_api_base=os.getenv("COZE_API_BASE", "https://api.coze.cn").strip().rstrip("/"),
        coze_timeout_seconds=_positive_float(os.getenv("COZE_TIMEOUT_SECONDS"), 300.0),
        debug=os.getenv("APP_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
    )


def _candidate_env_files() -> list[Path]:
    candidates = [Path.cwd() / ".env"]

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    else:
        candidates.append(Path(__file__).resolve().parents[2] / ".env")

    return list(dict.fromkeys(candidates))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _positive_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default
