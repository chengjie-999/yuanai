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
        # 注意：不打包 .env（内含 API Key，分发会泄露；运行时从 exe 同级目录读取）
        (str(ROOT / 'skills'), 'skills'),
        (str(ROOT / 'agent' / 'datanalysis' / 'scripts'), 'agent/datanalysis/scripts'),
        (str(ROOT / 'agent' / 'datanalysis' / 'crawl'), 'agent/datanalysis/crawl'),
        (str(ROOT / 'agent' / 'datanalysis' / 'tools'), 'agent/datanalysis/tools'),
    ],
    hiddenimports=[
        'yuanai_core', 'yuanai_core.core', 'yuanai_core.core.lc', 'yuanai_core.core.chat', 'yuanai_core.core.schemas',
        'yuanai_core.pure', 'yuanai_core.pure.calculate', 'yuanai_core.pure.crawl', 'yuanai_core.pure.files', 'yuanai_core.pure.stats', 'yuanai_core.pure.analysis', 'yuanai_core.pure.cookie',
        'yuanai_core.tools', 'yuanai_core.tools.calculator', 'yuanai_core.tools.crawl_tools', 'yuanai_core.tools.data_tools', 'yuanai_core.tools.file_tools',
        'skills',
        'agent', 'agent.main', 'agent.ws_client', 'agent.orchestrator', 'agent.intent_classifier',
        'agent.claude_bridge', 'agent.tools.claude_delegate',
        'agent.agents', 'agent.agents.base', 'agent.agents.analysis', 'agent.agents.collection', 'agent.agents.automation',
        'agent.tools', 'agent.tools.errors', 'agent.tools.audit_tools', 'agent.tools.browser_info_tools', 'agent.tools.cookie_tools', 'agent.tools.monitor_tools',
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
    icon=str(ROOT / 'data' / 'agent_icon.ico') if (ROOT / 'data' / 'agent_icon.ico').exists() else None,
)
