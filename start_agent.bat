@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo   小元AI 本机 Agent 启动中...
echo   （统筹 + Claude Code 二合一进程）
echo ========================================
call venv\Scripts\activate.bat
python -m agent.main
pause
