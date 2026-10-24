@echo off
rem XiaoYuanAI terminal chat CLI - one-click launcher (uses project venv, ignores default python)
cd /d %~dp0
venv\Scripts\python.exe -m agent.terminal %*
