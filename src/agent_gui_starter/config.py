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
    debug: bool

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)


def load_config() -> AppConfig:
    for env_file in _candidate_env_files():
        if env_file.exists():
            load_dotenv(env_file, override=False)

    return AppConfig(
        app_name="Agent GUI Starter",
        openai_api_key=_blank_to_none(os.getenv("OPENAI_API_KEY")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_organization=_blank_to_none(os.getenv("OPENAI_ORGANIZATION")),
        openai_project=_blank_to_none(os.getenv("OPENAI_PROJECT")),
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

