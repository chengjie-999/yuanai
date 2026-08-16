@echo off
chcp 65001 >nul

echo [0/3] Checking AGENT_TOKEN ...
%~dp0venv\Scripts\python.exe -c "import os;from dotenv import load_dotenv;load_dotenv(r'%~dp0.env');print('       OK (from .env)' if os.getenv('AGENT_TOKEN') else '       WARN: .env 缺 AGENT_TOKEN，Agent 将无法连接云端（会走云端回退）')"

echo [1/3] Starting API :8000 ...
start "" wt --title "API :8000" cmd /k "cd /d %~dp0 && %~dp0venv\Scripts\python.exe -m api.main"

echo Waiting for API to be ready...
:wait
ping -n 3 127.0.0.1 >nul
%~dp0venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >nul 2>&1
if errorlevel 1 goto wait

echo [2/3] Starting Agent ...
rem Agent 自动从 .env 读 AGENT_TOKEN（config.settings 的 load_dotenv），无需命令行传参
wt -w 0 new-tab --title "Agent" cmd /k "cd /d %~dp0 && %~dp0venv\Scripts\python.exe -m agent.main --agent-id 1"

echo [3/3] Starting Frontend :5173 ...
wt -w 0 new-tab --title "Frontend :5173" cmd /k "cd /d %~dp0frontend && npm run dev"

echo All services started.
exit
