@echo off
setlocal
chcp 65001 >nul
set "DIR=%~dp0"

rem 本地离线依赖目录（存在时加入 PYTHONPATH；未提交 Git）
if exist "%DIR%.deps" set "PYTHONPATH=%DIR%.deps"

if exist "%DIR%.venv\Scripts\pythonw.exe" (
  set "PYTHON=%DIR%.venv\Scripts\pythonw.exe"
) else (
  set "PYTHON=pythonw"
)

start "" "%PYTHON%" "%DIR%gui.py"
