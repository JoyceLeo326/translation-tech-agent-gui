from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig


@dataclass(frozen=True)
class CozeWorkflowResponse:
    text: str
    source: str
    debug_url: str | None = None


class CozeWorkflowError(RuntimeError):
    pass


class CozeWorkflowClient:
    def __init__(
        self,
        config: AppConfig,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config
        self._opener = opener or urlopen

    def run(self, input_text: str, input_title: str = "") -> CozeWorkflowResponse:
        text = input_text.strip()
        title = input_title.strip()
        if not text:
            raise CozeWorkflowError("扣子工作流需要输入待翻译正文。")

        if not self._config.has_coze_workflow:
            return CozeWorkflowResponse(
                text=(
                    "当前未配置扣子访问令牌，因此没有向平台发送网络请求。\n\n"
                    f"- 工作流 ID：`{self._config.coze_workflow_id or '未配置'}`\n"
                    f"- 标题/来源：{title or '未填写'}\n"
                    f"- 正文预览：{_shorten(text, 500)}\n\n"
                    "在 exe 同目录的 `.env` 中配置 `COZE_API_TOKEN`，并确认 B 组已发布最新版工作流后，"
                    "此入口会直接执行真实扣子工作流。"
                ),
                source="coze-unconfigured",
            )

        parameters: dict[str, str] = {"input_text": text}
        if title:
            parameters["input_title"] = title

        body = json.dumps(
            {
                "workflow_id": self._config.coze_workflow_id,
                "parameters": parameters,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            f"{self._config.coze_api_base.rstrip('/')}/v1/workflow/run",
            data=body,
            headers={
                "Authorization": f"Bearer {self._config.coze_api_token}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self._config.coze_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise CozeWorkflowError(
                f"扣子 API 请求失败（HTTP {exc.code}）：{_shorten(detail, 400)}"
            ) from exc
        except URLError as exc:
            raise CozeWorkflowError(f"无法连接扣子 API：{exc.reason}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CozeWorkflowError("扣子 API 返回了无法解析的响应。") from exc

        code = payload.get("code", 0)
        if code not in (0, "0", None):
            message = str(payload.get("msg") or payload.get("message") or "未知错误")
            raise CozeWorkflowError(f"扣子工作流执行失败（{code}）：{message}")

        output = _extract_workflow_text(payload.get("data"))
        if not output:
            raise CozeWorkflowError("扣子工作流执行成功，但没有返回可显示的最终文本。")

        debug_url = payload.get("debug_url")
        return CozeWorkflowResponse(
            text=output,
            source="coze-workflow",
            debug_url=debug_url if isinstance(debug_url, str) and debug_url else None,
        )


def _extract_workflow_text(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        return _extract_workflow_text(decoded)

    if isinstance(value, dict):
        for key in ("final_output", "output", "final_translation", "answer", "text", "content"):
            if key in value:
                extracted = _extract_workflow_text(value[key])
                if extracted:
                    return extracted
        return json.dumps(value, ensure_ascii=False, indent=2)

    if isinstance(value, list):
        parts = [_extract_workflow_text(item) for item in value]
        return "\n".join(part for part in parts if part)

    if value is None:
        return ""
    return str(value)


def _shorten(text: str, limit: int) -> str:
    compact = text.strip().replace("\r\n", "\n")
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "..."
