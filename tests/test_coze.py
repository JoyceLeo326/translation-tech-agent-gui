from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from agent_gui_starter.config import AppConfig, load_config
from agent_gui_starter.coze import CozeWorkflowClient, CozeWorkflowError


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _config(token: str | None = "coze-test-token") -> AppConfig:
    return AppConfig(
        app_name="test",
        openai_api_key=None,
        openai_model="gpt-test",
        openai_organization=None,
        openai_project=None,
        coze_api_token=token,
        coze_workflow_id="7661678571702747178",
        coze_api_base="https://api.coze.cn",
        coze_timeout_seconds=45.0,
        debug=False,
    )


class CozeWorkflowTests(unittest.TestCase):
    def test_environment_configuration_enables_coze_channel(self) -> None:
        values = {
            "COZE_API_TOKEN": "configured-token",
            "COZE_WORKFLOW_ID": "workflow-123",
            "COZE_API_BASE": "https://example.invalid/",
            "COZE_TIMEOUT_SECONDS": "42",
        }
        with patch.dict(os.environ, values, clear=False):
            config = load_config()

        self.assertTrue(config.has_coze_workflow)
        self.assertEqual(config.coze_workflow_id, "workflow-123")
        self.assertEqual(config.coze_api_base, "https://example.invalid")
        self.assertEqual(config.coze_timeout_seconds, 42.0)

    def test_run_sends_declared_start_parameters_and_extracts_final_output(self) -> None:
        captured: dict[str, object] = {}

        def opener(request: object, timeout: float) -> _FakeResponse:
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "code": 0,
                    "data": json.dumps({"final_output": "A child-friendly translation."}),
                    "debug_url": "https://www.coze.cn/work_flow?execute_id=test",
                }
            )

        response = CozeWorkflowClient(_config(), opener=opener).run("孔融让梨", "儿童故事")
        request = captured["request"]
        body = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]

        self.assertEqual(request.full_url, "https://api.coze.cn/v1/workflow/run")  # type: ignore[attr-defined]
        self.assertEqual(request.get_header("Authorization"), "Bearer coze-test-token")  # type: ignore[attr-defined]
        self.assertEqual(captured["timeout"], 45.0)
        self.assertEqual(body["workflow_id"], "7661678571702747178")
        self.assertEqual(body["parameters"], {"input_text": "孔融让梨", "input_title": "儿童故事"})
        self.assertEqual(response.text, "A child-friendly translation.")
        self.assertEqual(response.source, "coze-workflow")
        self.assertIn("execute_id=test", response.debug_url or "")

    def test_missing_token_returns_explicit_offline_result_without_network(self) -> None:
        def fail_if_called(*_: object, **__: object) -> _FakeResponse:
            raise AssertionError("network opener should not be called")

        response = CozeWorkflowClient(_config(token=None), opener=fail_if_called).run("仁者爱人")
        self.assertEqual(response.source, "coze-unconfigured")
        self.assertIn("未配置扣子访问令牌", response.text)
        self.assertIn("仁者爱人", response.text)

    def test_api_error_is_reported_as_workflow_error(self) -> None:
        def opener(*_: object, **__: object) -> _FakeResponse:
            return _FakeResponse({"code": 4001, "msg": "workflow is not published"})

        with self.assertRaisesRegex(CozeWorkflowError, "workflow is not published"):
            CozeWorkflowClient(_config(), opener=opener).run("测试")


if __name__ == "__main__":
    unittest.main()
