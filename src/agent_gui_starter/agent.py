from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Sequence

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

        if config.has_model_api:
            from openai import OpenAI

            kwargs: dict[str, object] = {
                "api_key": config.openai_api_key or "local-model",
                "base_url": config.openai_base_url,
                "timeout": config.model_api_timeout_seconds,
            }
            if config.openai_organization:
                kwargs["organization"] = config.openai_organization
            if config.openai_project:
                kwargs["project"] = config.openai_project

            self._client = OpenAI(**kwargs)

    @property
    def online(self) -> bool:
        return self._client is not None

    def run(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        if self._client is None:
            return AgentResponse(
                text=self._fallback_response(system_prompt, user_prompt),
                source="local-fallback",
            )

        text = self._create_text_response(system_prompt, user_prompt, temperature=0.2)
        return AgentResponse(text=text, source="model-api")

    def translate_lines(
        self,
        lines: Sequence[str],
        glossary: Sequence[tuple[str, str]] = (),
    ) -> list[str]:
        if self._client is None:
            raise RuntimeError("智能翻译需要先在左下角“模型接口”中连接在线或本地模型。")
        clean_lines = [str(line).strip() for line in lines]
        constraints = "\n".join(f"- {zh} -> {en}" for zh, en in glossary[:80])
        prompt = (
            "把下面的中国文化中文文本逐条翻译为自然、准确的英文。保持输入顺序和条目数量；"
            "儿童文学使用清晰、生动、适合儿童朗读的表达；文化术语必须优先遵守术语表。"
            "只返回 JSON 对象，格式为 {\"translations\":[\"...\"]}。\n\n"
            f"术语表：\n{constraints or '无额外术语'}\n\n"
            f"待翻译条目：\n{json.dumps(clean_lines, ensure_ascii=False)}"
        )
        text = self._create_text_response(
            "You are a senior Chinese-English cultural translation editor.",
            prompt,
            temperature=0.1,
        )
        payload = _parse_json_object(text)
        translations = payload.get("translations")
        if not isinstance(translations, list) or len(translations) != len(clean_lines):
            raise RuntimeError(
                f"智能翻译返回条目数不一致：收到 {len(translations) if isinstance(translations, list) else 0}，"
                f"预期 {len(clean_lines)}。"
            )
        return [str(item).strip() for item in translations]

    def transcribe_audio(self, audio_path: Path | str) -> str:
        if self._client is None:
            raise RuntimeError("音频转写需要先在左下角“模型接口”中连接支持转写的服务。")
        path = Path(audio_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"音频文件不存在：{path}")
        with path.open("rb") as handle:
            response = self._client.audio.transcriptions.create(
                model=self._config.transcription_model,
                file=handle,
                response_format="text",
            )
        if isinstance(response, str):
            text = response
        else:
            text = str(getattr(response, "text", ""))
        if not text.strip():
            raise RuntimeError("音频转写没有返回文本。")
        return text.strip()

    def translate_image(
        self,
        image_path: Path | str,
        glossary: Sequence[tuple[str, str]] = (),
    ) -> str:
        if self._client is None:
            raise RuntimeError("图片识别与翻译需要先在左下角“模型接口”中连接支持视觉的模型。")
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"图片文件不存在：{path}")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise RuntimeError("图片超过 20 MB，请压缩后重试。")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        system_prompt = (
            "You are a senior Chinese-English cultural translation editor. "
            "Read image text carefully and never invent text that is not visible."
        )
        constraints = "\n".join(f"- {zh} -> {en}" for zh, en in glossary[:80])
        user_prompt = (
            "提取图片中全部可见中文，按阅读顺序翻译为自然准确的英文。"
            "文化术语保持一致，儿童内容使用清晰生动的表达。"
            "请用 Markdown 表格返回：序号、中文原文、英文译文、位置说明；"
            "最后列出需要人工确认的模糊文字。\n\n"
            f"项目术语约束：\n{constraints or '无额外术语'}"
        )
        if self._config.model_api_protocol == "chat_completions":
            response = self._client.chat.completions.create(
                model=self._config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                        ],
                    },
                ],
                temperature=0.1,
            )
            return _extract_chat_text(response)
        response = self._client.responses.create(
            model=self._config.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
                    ],
                },
            ],
            temperature=0.1,
        )
        return _extract_response_text(response)

    def synthesize_speech(self, text: str, output_path: Path | str) -> Path:
        if self._client is None:
            raise RuntimeError("在线语音合成需要先在左下角“模型接口”中连接支持 TTS 的服务。")
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        response = self._client.audio.speech.create(
            model=self._config.speech_model,
            voice=self._config.speech_voice,
            input=text,
            response_format="wav",
        )
        if hasattr(response, "stream_to_file"):
            response.stream_to_file(output)
        else:
            content = getattr(response, "content", b"")
            output.write_bytes(content if isinstance(content, bytes) else bytes(content))
        if not output.exists() or output.stat().st_size < 1024:
            raise RuntimeError("在线语音服务没有生成有效 WAV 文件。")
        return output

    def _create_text_response(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        if self._config.model_api_protocol == "chat_completions":
            response = self._client.chat.completions.create(
                model=self._config.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            return _extract_chat_text(response)
        response = self._client.responses.create(
            model=self._config.openai_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return _extract_response_text(response)

    @staticmethod
    def _fallback_response(system_prompt: str, user_prompt: str) -> str:
        preview = user_prompt.strip().replace("\r\n", "\n")
        if len(preview) > 800:
            preview = preview[:800].rstrip() + "..."

        return (
            "当前没有连接模型接口，所以返回可演示的本地结果。\n\n"
            "系统提示：\n"
            f"{system_prompt.strip()}\n\n"
            "用户输入：\n"
            f"{preview}\n\n"
            "在左下角打开“模型接口”并保存配置后，这里会替换为真实模型输出。"
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


def _extract_chat_text(response: object) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return "模型没有返回可显示文本。"
    content = getattr(getattr(choices[0], "message", None), "content", "")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            value = getattr(item, "text", "")
            if not value and isinstance(item, dict):
                value = item.get("text", "")
            if value:
                parts.append(str(value))
        text = "\n".join(part.strip() for part in parts if part.strip())
        if text:
            return text
    return "模型没有返回可显示文本。"


def _parse_json_object(text: str) -> dict[str, object]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("智能翻译没有返回可解析的 JSON。") from exc
        payload = json.loads(value[start : end + 1])
    if not isinstance(payload, dict):
        raise RuntimeError("智能翻译返回格式不是 JSON 对象。")
    return payload
