# A/B/C 接入适配器

主程序适配逻辑集中在 `src/agent_gui_starter/integration.py`，避免把可执行逻辑重复维护在多个目录。

| 组别 | 主入口 | 当前读取内容 |
| --- | --- | --- |
| A 组 | `run_group_adapter("A", ...)` | 修正版翻译清单、最终 DOCX、图片总览 |
| B 组 | `run_group_adapter("B", ...)` | 共享术语库、儿童文学风格提示词、Coze 工作流交付状态 |
| C 组 | `run_group_adapter("C", ...)` | DOCX 二次交付、音视频二次交付与验收说明 |

GUI 的 B 组工作入口另通过 `src/agent_gui_starter/coze.py` 调用已发布的 Coze 工作流。没有配置令牌时只返回明确的离线说明，不伪造在线执行结果。
