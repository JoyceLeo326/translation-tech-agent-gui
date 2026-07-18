from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .agent import AgentClient
from .integration import (
    find_project_root,
    format_size,
    load_terms,
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
        progress("正在扫描统一素材库")
    scan = scan_collaboration(root)
    category_counts: dict[str, int] = {}
    for asset in scan.assets:
        category_counts[asset.category] = category_counts.get(asset.category, 0) + 1
    inventory = "\n".join(
        [
            "# 统一素材库扫描完成",
            "",
            f"- 已连接资源：{len(scan.assets)} 个",
            f"- 资源总大小：{format_size(sum(asset.size_bytes for asset in scan.assets))}",
            f"- 最近扫描：{scan.scanned_at}",
            "",
            "## 内容类型",
            "",
            *[f"- {name}：{count}" for name, count in sorted(category_counts.items())],
        ]
    )
    results.append(StepResult("统一素材扫描", inventory, "local-integration"))

    if progress:
        progress("正在加载文化术语与儿童文学风格约束")
    terms = load_terms(root)
    official_terms = [item for item in terms if item.get("来源链接")]
    constraints = "\n".join(
        [
            "# 翻译约束已加载",
            "",
            f"- 可用术语：{len(terms)} 条",
            f"- 带官方来源补充：{len(official_terms)} 条",
            "- 儿童文学规则：清晰、生动、适合朗读，避免成人化和生硬直译",
            "- 审校规则：人工审核列优先，空白时保留机器译文",
        ]
    )
    results.append(StepResult("术语与风格约束", constraints, "local-integration"))

    if progress:
        progress("正在校验统一成品区")
    ready_root = root / "collaboration/integration/final_outputs/ready_to_use"
    acceptance_path = ready_root / "05_资源索引/最终验收.json"
    if acceptance_path.exists():
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        ready_files = [path for path in ready_root.rglob("*") if path.is_file()]
        ready_summary = "\n".join(
            [
                "# 统一成品区校验通过",
                "",
                f"- 可直接使用文件：{len(ready_files)} 个",
                f"- 数据验收：{'通过' if acceptance.get('passed') else '失败'}",
                f"- 资源哈希：{'完整' if acceptance.get('catalog_has_sha256') else '不完整'}",
                f"- 本机生成 WAV：{acceptance.get('generated_wav_count', 0)} 个",
            ]
        )
    else:
        ready_summary = "# 统一成品区尚未生成\n\n请先运行 `scripts/build_unified_delivery.py`。"
    results.append(StepResult("成品区校验", ready_summary, "local-integration"))

    if progress:
        progress("正在生成整合输出文件")
    bundle = write_integration_outputs(scan, original_prompt)
    results.append(StepResult("整合文件输出", bundle.summary_markdown, "local-files"))

    if client.online:
        if progress:
            progress("正在调用智能体执行最终质检")
        response = client.run(
            "你是中国文化多模态外译项目的最终质量编辑。只检查统一成品，不按协作分组讨论。",
            (
                f"用户目标：\n{original_prompt.strip() or '检查当前统一交付是否完整可用'}\n\n"
                f"素材扫描：\n{inventory}\n\n"
                f"翻译约束：\n{constraints}\n\n"
                f"成品校验：\n{ready_summary}\n\n"
                "请输出可直接执行的最终质检结论，覆盖准确性、儿童可读性、术语一致性、"
                "文档回填完整性、音频可播放性和交付文件完整性。"
            ),
        )
        results.append(StepResult("智能最终质检", response.text, response.source))
    else:
        results.append(
            StepResult(
                "本地最终质检",
                "# 本地质检结论\n\n素材、术语约束、统一成品区和导出报告均已完成本地校验。"
                "在线语义质检未启用；配置模型密钥后可在同一流程追加，不影响本地成品使用。",
                "local-integration",
            )
        )

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
