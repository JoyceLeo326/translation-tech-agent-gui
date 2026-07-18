from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import agent_gui_starter.config as config_module
from agent_gui_starter.agent import AgentClient
from agent_gui_starter.config import AppConfig, write_user_config


def _config(**overrides: object) -> AppConfig:
    values: dict[str, object] = {
        "app_name": "test",
        "openai_api_key": None,
        "openai_model": "local-model",
        "openai_organization": None,
        "openai_project": None,
        "coze_api_token": None,
        "coze_workflow_id": None,
        "coze_api_base": "https://api.coze.cn",
        "coze_timeout_seconds": 30.0,
        "debug": False,
        "openai_base_url": "http://127.0.0.1:1234/v1",
        "model_api_protocol": "chat_completions",
    }
    values.update(overrides)
    return AppConfig(**values)  # type: ignore[arg-type]


class _ChatCompletions:
    def create(self, **kwargs: object) -> object:
        message = types.SimpleNamespace(content="连接成功")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class _FakeOpenAI:
    last_kwargs: dict[str, object] = {}

    def __init__(self, **kwargs: object) -> None:
        type(self).last_kwargs = kwargs
        self.chat = types.SimpleNamespace(completions=_ChatCompletions())


class ModelApiTests(unittest.TestCase):
    def test_local_compatible_api_does_not_require_key(self) -> None:
        fake_module = types.SimpleNamespace(OpenAI=_FakeOpenAI)
        with patch.dict(sys.modules, {"openai": fake_module}):
            client = AgentClient(_config())
            response = client.run("system", "ping")
        self.assertTrue(client.online)
        self.assertEqual(response.text, "连接成功")
        self.assertEqual(response.source, "model-api")
        self.assertEqual(_FakeOpenAI.last_kwargs["api_key"], "local-model")
        self.assertEqual(_FakeOpenAI.last_kwargs["base_url"], "http://127.0.0.1:1234/v1")

    def test_user_config_is_written_only_to_selected_local_env(self) -> None:
        keys = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")
        previous = {key: os.environ.get(key) for key in keys}
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / ".env"
                with patch.object(config_module, "user_env_path", return_value=env_path):
                    result = write_user_config(
                        {
                            "OPENAI_API_KEY": "private-test-key",
                            "OPENAI_BASE_URL": "https://example.invalid/v1",
                            "OPENAI_MODEL": "example-model",
                        }
                    )
                    self.assertEqual(result, env_path)
                    content = env_path.read_text(encoding="utf-8")
                    self.assertIn("OPENAI_API_KEY=private-test-key", content)
                    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
                    self.assertNotIn("private-test-key", example)

                    write_user_config({"OPENAI_API_KEY": None})
                    self.assertNotIn("OPENAI_API_KEY=", env_path.read_text(encoding="utf-8"))
                    self.assertNotIn("OPENAI_API_KEY", os.environ)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
