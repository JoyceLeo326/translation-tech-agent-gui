from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig


@dataclass(frozen=True)
class AgentResponse:
    text: str
    source: str


class AgentClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None

        if config.has_api_key:
            from openai import OpenAI

            kwargs: dict[str, str] = {"api_key": config.openai_api_key or ""}
            if config.openai_organization:
                kwargs["organization"] = config.openai_organization
            if config.openai_project:
                kwargs["project"] = config.openai_project

            self._client = OpenAI(**kwargs)

    def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        if self._client is None:
            return AgentResponse(
                text=self._fallback_response(system_prompt, user_prompt),
                source="local-fallback",
            )

        response = self._client.responses.create(
            model=self._config.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return AgentResponse(text=_extract_response_text(response), source="openai")

    @staticmethod
    def _fallback_response(system_prompt: str, user_prompt: str) -> str:
        preview = user_prompt.strip().replace("\r\n", "\n")
        if len(preview) > 800:
            preview = preview[:800].rstrip() + "..."

        return (
            "当前没有检测到 OPENAI_API_KEY，所以返回本地占位结果。\n\n"
            "系统提示：\n"
            f"{system_prompt.strip()}\n\n"
            "用户输入：\n"
            f"{preview}\n\n"
            "后续填写 .env 后，这里会替换为真实模型输出。"
        )


def _extract_response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)

    text = "\n".join(part.strip() for part in parts if part.strip())
    return text or "模型没有返回可显示文本。"

