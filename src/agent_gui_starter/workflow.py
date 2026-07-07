from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .agent import AgentClient


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class WorkflowStep:
    name: str
    system_prompt: str
    user_prompt_template: str


@dataclass(frozen=True)
class StepResult:
    name: str
    output: str
    source: str


@dataclass(frozen=True)
class WorkflowResult:
    steps: list[StepResult]

    @property
    def final_text(self) -> str:
        if not self.steps:
            return ""
        return self.steps[-1].output


DEFAULT_WORKFLOW = [
    WorkflowStep(
        name="需求理解",
        system_prompt="你是一个严谨的任务分析助手。请识别用户目标、约束、输入材料和需要交付的结果。",
        user_prompt_template="用户原始输入：\n{original}\n\n请输出结构化分析。",
    ),
    WorkflowStep(
        name="执行草稿",
        system_prompt="你是一个可执行方案生成助手。请基于已有分析产出可直接使用的初稿。",
        user_prompt_template="用户原始输入：\n{original}\n\n上一步结果：\n{previous}\n\n请生成初稿。",
    ),
    WorkflowStep(
        name="质量检查",
        system_prompt="你是一个质量检查助手。请检查准确性、完整性、可读性，并给出最终结果。",
        user_prompt_template="用户原始输入：\n{original}\n\n待检查内容：\n{previous}\n\n请输出最终版本，并列出关键检查点。",
    ),
]


def run_default_workflow(
    client: AgentClient,
    original_prompt: str,
    progress: ProgressCallback | None = None,
) -> WorkflowResult:
    return run_workflow(client, DEFAULT_WORKFLOW, original_prompt, progress)


def run_workflow(
    client: AgentClient,
    steps: list[WorkflowStep],
    original_prompt: str,
    progress: ProgressCallback | None = None,
) -> WorkflowResult:
    previous = ""
    results: list[StepResult] = []

    for index, step in enumerate(steps, start=1):
        if progress:
            progress(f"正在执行 {index}/{len(steps)}：{step.name}")

        prompt = step.user_prompt_template.format(
            original=original_prompt.strip(),
            previous=previous.strip(),
        )
        response = client.run(step.system_prompt, prompt)
        previous = response.text
        results.append(StepResult(step.name, response.text, response.source))

    if progress:
        progress("工作流完成")

    return WorkflowResult(results)


def format_workflow_result(result: WorkflowResult) -> str:
    sections: list[str] = []
    for index, step in enumerate(result.steps, start=1):
        sections.append(f"## {index}. {step.name} [{step.source}]\n\n{step.output.strip()}")
    return "\n\n".join(sections).strip()

