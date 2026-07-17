# Local Tooling Layout

## Project-local

- Virtual environment: `.venv`
- Source code: `src\agent_gui_starter`
- Development entry: `main.py`
- Packaged executable: `dist\CultureTranslationWorkbench\CultureTranslationWorkbench.exe`

## D-drive shared tools

- Python package cache: `D:\AI_GUI_DevTools\pip-cache`
- PyInstaller cache: `D:\AI_GUI_DevTools\pyinstaller-cache`

## Already available on this machine

- Python 3.11 and 3.12
- Git
- Node.js and npm
- GitHub CLI
- VS Code on D drive

## Optional future additions

- Inno Setup or NSIS, only if we need a formal installer instead of a portable exe folder.
- Qt Designer, only if a future task requires visual `.ui` editing instead of building the interface in Python.
