# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包规格：小元AI 本地 Agent（桌面托盘程序）"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # agent/ → 项目根

a = Analysis(
    [str(ROOT / 'agent' / 'tray.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 注意：不打包 .env（内含 API Key，分发会泄露；运行时从数据根 %LOCALAPPDATA%\\XiaoYuanAI\\.env 读取）
        (str(ROOT / 'skills'), 'skills'),
        (str(ROOT / 'agent' / 'datanalysis' / 'scripts'), 'agent/datanalysis/scripts'),
        (str(ROOT / 'agent' / 'datanalysis' / 'crawl'), 'agent/datanalysis/crawl'),
        (str(ROOT / 'agent' / 'datanalysis' / 'tools'), 'agent/datanalysis/tools'),
        # 报告模板（export.py 用 FileSystemLoader 按 __file__ 定位，frozen 下需随包分发）
        (str(ROOT / 'yuanai_core' / 'pure' / 'report_template.html'), 'yuanai_core/pure'),
        # 智能体能力边界身份卡（agent_docs 加载器 frozen 下从 _MEIPASS 读）
        (str(ROOT / 'docs' / 'agents'), 'docs/agents'),
    ],
    hiddenimports=[
        'yuanai_core', 'yuanai_core.core', 'yuanai_core.core.lc', 'yuanai_core.core.chat', 'yuanai_core.core.schemas',
        'yuanai_core.core.message', 'yuanai_core.core.views',
        'yuanai_core.memory', 'yuanai_core.memory_store',
        'yuanai_core.pure', 'yuanai_core.pure.calculate', 'yuanai_core.pure.crawl', 'yuanai_core.pure.files', 'yuanai_core.pure.stats', 'yuanai_core.pure.analysis', 'yuanai_core.pure.cookie',
        'yuanai_core.pure.plan', 'yuanai_core.pure.export', 'yuanai_core.pure.ssrf',
        'yuanai_core.pure.model_upgrades', 'yuanai_core.pure.dsml',
        'yuanai_core.pure.mindmap_parser', 'yuanai_core.pure.web_search', 'yuanai_core.pure.vault_note',
        # 工具模块：由 _registry 静态字面量导入自动打包（新增工具改 _registry 即可，
        # 无需再逐个登记本清单）
        'yuanai_core.tools', 'yuanai_core.tools._registry',
        'yuanai_core.usage', 'yuanai_core.planet_convert', 'yuanai_core.rag_base',
        'yuanai_core.utils', 'yuanai_core.utils.image',
        'skills',
        'agent', 'agent.main', 'agent.ws_client', 'agent.orchestrator', 'agent.intent_classifier',
        'agent.claude_bridge', 'agent.claude_loop', 'agent.bootstrap', 'agent.bridge_policy',
        'agent.vault_sync',
        'agent.plan_executor', 'agent.pet_events',
        'agent.scripts', 'agent.scripts.registry', 'agent.scripts.tools',
        'agent.agents', 'agent.agents.base', 'agent.agents.automation',
        'agent.tools', 'agent.tools._registry', 'agent.tools.errors',
        'agent.tools.selenium_tools', 'agent.tools.selenium_tools.core', 'agent.tools.selenium_tools.xiaoyuan',
        'agent.audit', 'agent.audit.core', 'agent.audit.parser',
        'agent.rag',
        'spiderlx', 'spiderlx.core.browser_manager', 'spiderlx.core.cdp_events',
        'config', 'config.settings',
        'utils', 'utils.sensitive_data', 'utils.data_path',
        'db', 'db.session', 'db.cache', 'db.redis_client',
        'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw',
        'tkinter',
        'websockets', 'langchain_openai', 'langgraph', 'langgraph.prebuilt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='yuanai-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 纯托盘后台程序：无黑窗口，双击后只剩托盘图标
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'agent' / 'agent_icon.ico') if (ROOT / 'agent' / 'agent_icon.ico').exists() else None,
)
