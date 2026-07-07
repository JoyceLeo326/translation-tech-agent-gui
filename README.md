# Agent GUI Starter

这是一个给后续任务复用的 Windows 桌面应用模板：

- GUI：PySide6 / Qt for Python
- 智能体调用：`openai` SDK，使用 `.env` 配置 API Key 和模型
- 工作流：把多个智能体步骤串起来执行
- 打包：PyInstaller，产出 Windows exe

## 开源协议

本项目使用 MIT License。后续如果比赛或老师要求其它协议，可以再统一调整。

## 第一次准备

在 PowerShell 中进入本目录后运行：

```powershell
.\scripts\setup_env.ps1
```

这会创建 `.venv` 虚拟环境并安装所需依赖。

## 配置密钥

复制 `.env.example` 为 `.env`，填写你的 API Key：

```text
OPENAI_API_KEY=你的密钥
OPENAI_MODEL=gpt-4.1-mini
```

如果暂时不填 `OPENAI_API_KEY`，程序仍然可以启动并显示本地占位结果，方便先验证 GUI 和打包流程。

## 运行开发版

```powershell
.\scripts\run_dev.ps1
```

## 打包 exe

```powershell
.\scripts\build_exe.ps1
```

打包成功后可执行文件在：

```text
dist\AgentGuiStarter\AgentGuiStarter.exe
```

## 验证打包结果

```powershell
.\scripts\verify_build.ps1
```

## 后续改哪里

- 界面：`src\agent_gui_starter\app.py`
- 智能体连接：`src\agent_gui_starter\agent.py`
- 工作流步骤：`src\agent_gui_starter\workflow.py`
- 环境配置：`src\agent_gui_starter\config.py`
