from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

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
    openai_base_url: str = "https://api.openai.com/v1"
    model_api_protocol: str = "responses"
    model_api_timeout_seconds: float = 120.0
    transcription_model: str = "whisper-1"
    speech_model: str = "gpt-4o-mini-tts"
    speech_voice: str = "alloy"

    @property
    def has_api_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_model_api(self) -> bool:
        return self.has_api_key or _is_local_api_url(self.openai_base_url)

    @property
    def has_coze_workflow(self) -> bool:
        return bool(self.coze_api_token and self.coze_workflow_id)


def load_config() -> AppConfig:
    for env_file in _candidate_env_files():
        if env_file.exists():
            load_dotenv(env_file, override=False)

    return AppConfig(
        app_name="译述 YISHU · 中国文化多模态外译工作台",
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
        openai_base_url=(
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
            or "https://api.openai.com/v1"
        ),
        model_api_protocol=_api_protocol(os.getenv("MODEL_API_PROTOCOL")),
        model_api_timeout_seconds=_positive_float(os.getenv("MODEL_API_TIMEOUT_SECONDS"), 120.0),
        transcription_model=os.getenv("TRANSCRIPTION_MODEL", "whisper-1").strip() or "whisper-1",
        speech_model=os.getenv("SPEECH_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts",
        speech_voice=os.getenv("SPEECH_VOICE", "alloy").strip() or "alloy",
    )


def _candidate_env_files() -> list[Path]:
    candidates = [user_env_path(), Path.cwd() / ".env"]
    return list(dict.fromkeys(candidates))


def user_env_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path(__file__).resolve().parents[2] / ".env"


def write_user_config(updates: Mapping[str, str | None]) -> Path:
    """Persist non-empty settings beside the source project or packaged EXE."""
    path = user_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    normalized = {str(key).strip(): _clean_env_value(value) for key, value in updates.items()}
    output: list[str] = []
    written: set[str] = set()

    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key not in normalized:
            output.append(line)
            continue
        if key in written:
            continue
        value = normalized[key]
        if value is not None:
            output.append(f"{key}={value}")
        written.add(key)

    if output and output[-1].strip():
        output.append("")
    for key, value in normalized.items():
        if key in written or value is None:
            continue
        output.append(f"{key}={value}")

    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    temp_path.replace(path)

    for key, value in normalized.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return path


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


def _api_protocol(value: str | None) -> str:
    normalized = (value or "responses").strip().lower().replace("-", "_")
    if normalized in {"chat", "chat_completion", "chat_completions"}:
        return "chat_completions"
    return "responses"


def _is_local_api_url(value: str) -> bool:
    try:
        host = (urlparse(value).hostname or "").lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace("\r", "").replace("\n", "")
    return cleaned or None
