from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .agent import AgentClient
from .integration import (
    find_project_root,
    format_dashboard_markdown,
    run_group_adapter,
    scan_collaboration,
    write_integration_outputs,
)


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


def run_translation_integration_workflow(
    client: AgentClient,
    original_prompt: str,
    project_root: Path | None = None,
    progress: ProgressCallback | None = None,
) -> WorkflowResult:
    root = find_project_root(project_root)
    results: list[StepResult] = []

    if progress:
        progress("正在扫描 A/B/C 协作区")
    scan = scan_collaboration(root)
    dashboard = format_dashboard_markdown(scan)
    results.append(StepResult("协作区扫描", dashboard, "local-integration"))

    if progress:
        progress("正在运行 A/B/C 本地适配器")
    adapter_output = "\n\n".join(
        [
            run_group_adapter("A", original_prompt, root),
            run_group_adapter("B", original_prompt, root),
            run_group_adapter("C", original_prompt, root),
        ]
    )
    results.append(StepResult("A/B/C 适配器", adapter_output, "local-integration"))

    if progress:
        progress("正在生成整合输出文件")
    bundle = write_integration_outputs(scan, original_prompt)
    results.append(StepResult("整合文件输出", bundle.summary_markdown, "local-files"))

    if progress:
        progress("正在调用智能体生成总整合建议")
    response = client.run(
        "你是翻译技术大赛总整合负责人。请基于扫描结果、术语库和 A/B/C 交付状态，给出下一步可执行整合建议。",
        (
            f"用户目标：\n{original_prompt.strip() or '生成当前项目的完整整合状态与交付建议'}\n\n"
            f"协作区扫描：\n{dashboard}\n\n"
            f"适配器输出：\n{adapter_output}\n\n"
            "请输出：1. 当前是否可演示；2. GUI 接入重点；3. 仍需 A/B/C 组补充的非阻塞项；"
            "4. 最终提交前检查清单。"
        ),
    )
    results.append(StepResult("智能体总整合建议", response.text, response.source))

    if progress:
        progress("整合工作流完成")
    return WorkflowResult(results)


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
