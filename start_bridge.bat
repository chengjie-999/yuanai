@echo off
rem ============================================================
rem 小元AI Claude Code 桥接启动脚本（SDK 直连 DeepSeek 官方 Anthropic 端点）
rem 前置：Windows 用户环境变量已配 ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN
rem       （与 Claude Code 网关同款，无需本脚本重复配置）
rem 用法：start_bridge.bat [agent-id] [agent-token]
rem       （留空自动读 data/agent_identity.json 的注册身份）
rem 模式：auto——有凭证自动 SDK 直连（流式+审批卡+会话续接），
rem        凭证缺失自动降级 CLI 子进程模式
rem ============================================================
set CLAUDE_BRIDGE_MODEL=deepseek-flash
set CLAUDE_BRIDGE_THINKING=0
python -m agent.claude_bridge --server-url wss://cjyuanai.cn --agent-id %1 --agent-token %2
