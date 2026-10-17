import os
import sys
from dotenv import load_dotenv

# 安装包化（2026-10-16）：exe 模式 .env 从数据根读取
# （%LOCALAPPDATA%\XiaoYuanAI\.env，与 data 同处统一管理，不散落 exe 旁）；
# 源码/云端模式维持 cwd/.env（服务器工作目录）不变
if getattr(sys, "frozen", False):
    from utils.data_path import frozen_data_root
    load_dotenv(os.path.join(frozen_data_root(), ".env"))
else:
    load_dotenv()

# ===================== 模型配置 =====================

import json as _json
from pathlib import Path as _Path

# 2026-10-16 模型换代：
# - 豆包 Seed 2.1 已上线（pro 260628 / lite 260915）但账号尚未在方舟控制台开通
#   （ModelNotOpen）→ 暂回退 2.0，开通后把 _DOUBAO_* 换成 2.1 并在
#   yuanai_core/pure/model_upgrades.py 重新登记升级映射
# - DeepSeek V4 Flash 已退役（官方路由至 V4.1 Flash，新 ID = deepseek-flash）；
#   V4 Pro 0813 仍在服务
_DOUBAO_PRO = "doubao-seed-2-0-pro-260215"
_DOUBAO_LITE = "doubao-seed-2-0-lite-260215"
_DEEPSEEK_FLASH = "deepseek-flash"
_DEEPSEEK_PRO = "deepseek-v4-pro"

_DEFAULT_MODELS = {
    _DOUBAO_PRO: {"label": "豆包 Pro", "provider": "Doubao"},
    _DOUBAO_LITE: {"label": "豆包 Lite", "provider": "Doubao"},
    _DEEPSEEK_FLASH: {"label": "DeepSeek V4.1 Flash", "provider": "DeepSeek"},
    _DEEPSEEK_PRO: {"label": "DeepSeek V4 Pro", "provider": "DeepSeek"},
}

def _load_models() -> dict:
    models = dict(_DEFAULT_MODELS)
    try:
        from utils.data_path import root_path as _root_path
        custom_path = _Path(_root_path()) / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                custom = _json.load(f)
            if isinstance(custom, dict):
                models.update(custom)
    except Exception:
        pass
    return models

MODELS = _load_models()

MODEL_NAMES = list(MODELS.keys())
DEFAULT_MODEL = _DEEPSEEK_FLASH
VISION_MODEL = _DOUBAO_PRO  # DeepSeek 不支持图片，识图自动切豆包
DEFAULT_TEMPERATURE = 0.7

# ===================== 后台设定中心（2026-10-17） =====================
# 存储：models.json 的 `_system_config` 键（与 _agent_models/_voice_config 同构，
# models_file 单点读写原子落盘）。选择链：env 优先（保持生产语义）→
# _system_config → 代码默认。GET /admin/system-config 返回 env_override 标记，
# UI 对 env 压住的项显示黄色提示「环境变量已设置，优先级高于后台」。

_DEFAULT_SYSTEM_CONFIG = {
    # 记忆机制（MEMORY_* 12 项）
    "memory_enabled": True,
    "memory_working_window": 20,
    "memory_trigger_chars": 8000,
    "memory_fold_min_messages": 5,
    "memory_fold_min_chars": 800,
    "memory_fold_input_max_chars": 12000,
    "memory_max_items": 100,
    "memory_max_chars": 2000,
    "memory_fold_timeout_s": 120,
    "memory_fold_daily_max": 50,
    "memory_organize_delete_daily_max": 3,
    # 推理强度（DeepSeek 系列；low/medium/high）
    "reasoning_effort": "low",
    # 成本护栏
    "register_open": False,
    "daily_message_quota": 50,
    "voice_enabled": True,
    # 模型定价（dict，空=用内置默认；合并 MODEL_PRICING）
    "model_pricing": {},
    # 助手设定（提示词，模型自知的「可编辑设定」）
    "chat_system_prompt": "",
    "self_report_template": ("你当前实际运行的模型 ID 是 {model}。"
                             "当用户问「你是什么模型/哪个模型」时，如实回答这个模型 ID，"
                             "不要模糊、不要编造其他名称。"),
    # 默认能力说明（模型自知的另一半：「知道自己能干啥不能干啥」；
    # 后台「设置 → 助手设定」可改）。曾出现模型被要「打开计划页面」时回答
    # 「给不了/没权限」并编造不存在的标签页位置——界面入口由客户端提供。
    "capability_note": ("界面入口说明（重要）：计划面板、分析看板等界面由客户端提供"
                        "入口按钮，你不能直接打开页面或生成界面链接。用户问界面在哪/怎么打开时，"
                        "如实指引入口位置：① 计划面板——聊天页顶部「后台执行中」指示条、"
                        "或计划相关工具气泡里的「打开面板」按钮；② 分析看板——分析完成后"
                        "气泡里的「打开面板」按钮；③ 用户设置——页面右上角设置入口。"
                        "不要回答「这个给不了」「没有权限」之类，也不要编造不存在的"
                        "标签页或路径。"),
}

# 键 → env 名（env 优先链；不在映射的键只走 _system_config）
_SYS_CONFIG_ENV_MAP = {
    "memory_enabled": "MEMORY_ENABLED",
    "memory_working_window": "MEMORY_WORKING_WINDOW",
    "memory_trigger_chars": "MEMORY_TRIGGER_CHARS",
    "memory_fold_min_messages": "MEMORY_FOLD_MIN_MESSAGES",
    "memory_fold_min_chars": "MEMORY_FOLD_MIN_CHARS",
    "memory_fold_input_max_chars": "MEMORY_FOLD_INPUT_MAX_CHARS",
    "memory_max_items": "MEMORY_MAX_ITEMS",
    "memory_max_chars": "MEMORY_MAX_CHARS",
    "memory_fold_timeout_s": "MEMORY_FOLD_TIMEOUT_S",
    "memory_fold_daily_max": "MEMORY_FOLD_DAILY_MAX",
    "memory_organize_delete_daily_max": "MEMORY_ORGANIZE_DELETE_DAILY_MAX",
    "reasoning_effort": "REASONING_EFFORT",
    "register_open": "REGISTER_OPEN",
    "daily_message_quota": "DAILY_MESSAGE_QUOTA",
    "voice_enabled": "VOICE_ENABLED",
}


def _load_system_config() -> dict:
    result = dict(_DEFAULT_SYSTEM_CONFIG)
    try:
        from utils.data_path import root_path as _root_path
        custom_path = _Path(_root_path()) / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                custom = data.get("_system_config", {})
                if isinstance(custom, dict):
                    result.update(custom)
    except Exception:
        pass
    return result


SYSTEM_CONFIG = _load_system_config()


def env_overrides_system_config(key: str) -> bool:
    """该键是否被环境变量压住（后台 UI 提示用）"""
    env_key = _SYS_CONFIG_ENV_MAP.get(key)
    return bool(env_key and os.getenv(env_key) is not None)


def _syscfg(key: str):
    """env 优先 → _system_config → 默认（返回原始类型）"""
    env_key = _SYS_CONFIG_ENV_MAP.get(key)
    if env_key:
        raw = os.getenv(env_key)
        if raw is not None:
            default = _DEFAULT_SYSTEM_CONFIG[key]
            if isinstance(default, bool):
                return raw.lower() == "true"
            if isinstance(default, int):
                try:
                    return int(raw)
                except ValueError:
                    return default
            return raw
    return SYSTEM_CONFIG.get(key, _DEFAULT_SYSTEM_CONFIG[key])


# 助手设定（模型自知的提示词，后台可编辑）
SELF_REPORT_TEMPLATE = str(_syscfg("self_report_template"))
CHAT_SYSTEM_PROMPT = str(_syscfg("chat_system_prompt"))
CAPABILITY_NOTE = str(_syscfg("capability_note"))


def self_report_text(model: str) -> str:
    """自报注入文案（运行时真值填充模型 ID，不可被编辑成假值）"""
    try:
        return SELF_REPORT_TEMPLATE.format(model=model)
    except Exception:
        return f"你当前实际运行的模型 ID 是 {model}。"


# 推理强度（DeepSeek 系列 reasoning_effort，.env/后台可覆盖）：
#   low = 快答省 token（默认）；medium = 标准；high = 深度思考（复杂分析）
# 豆包系列不走此参数——思考模式由方舟接入点（火山控制台 endpoint）的 thinking 开关控制
REASONING_EFFORT = str(_syscfg("reasoning_effort"))

# 模型 API 定价（元 / 百万 token，成本面板用）。
# ⚠ 价格为占位默认值，以官方最新价为准；整体覆盖：.env 设 MODEL_PRICING_JSON
#   形如 {"deepseek-v4-pro": {"in": 2.0, "out": 8.0}, ...}；未列出的模型记 0 成本（标记未定价）
_MODEL_PRICING_DEFAULTS = {
    _DEEPSEEK_FLASH: {"in": 0.5, "out": 2.0},   # V4.1 Flash（占位，沿用 V4 Flash 价，以官方为准）
    _DEEPSEEK_PRO: {"in": 2.0, "out": 8.0},
    _DOUBAO_LITE: {"in": 0.3, "out": 0.6},      # Seed 2.1 占位价，以官方为准
    _DOUBAO_PRO: {"in": 0.8, "out": 2.0},
}
MODEL_PRICING = _MODEL_PRICING_DEFAULTS
try:
    _pricing_env = os.getenv("MODEL_PRICING_JSON", "")
    if _pricing_env:
        _pricing_custom = json.loads(_pricing_env)
        if isinstance(_pricing_custom, dict):
            MODEL_PRICING = {**_MODEL_PRICING_DEFAULTS, **_pricing_custom}
except Exception:
    pass
# 后台设定中心的 model_pricing 合并（env MODEL_PRICING_JSON 仍优先）
_pricing_syscfg = _syscfg("model_pricing")
if isinstance(_pricing_syscfg, dict) and _pricing_syscfg:
    MODEL_PRICING = {**MODEL_PRICING, **_pricing_syscfg}

# Agent 模型分配 — 统一入口，消除代码中 15+ 处硬编码。
# 模型淘汰可更换（2026-10-16）：后台「模型配置」页可编辑分配（存 models.json
# _agent_models，PUT /admin/agent-models 热更新 reload_agent_models）
_DEFAULT_AGENT_MODEL_MAP = {
    # 通用快模型 — 意图识别 / 任务路由 / 简单爬取
    "orchestrator": _DEEPSEEK_FLASH,
    "collection": _DEEPSEEK_FLASH,
    # 强推理 — 数据分析 / 复杂统计 / 图表生成
    "analysis": _DEEPSEEK_PRO,
    # 多模态 — 浏览器截图 / 视觉审核 / 图片理解
    "automation": _DOUBAO_PRO,
    "audit": _DOUBAO_PRO,
    # 辅助任务 — 记忆折叠 / 星球文章化（后台可换，env 仍优先）
    "memory_fold": _DOUBAO_LITE,
    "planet_article": _DOUBAO_LITE,
}


def _load_agent_models() -> dict:
    """从 models.json 读取自定义 Agent 模型分配，合并到默认映射"""
    result = dict(_DEFAULT_AGENT_MODEL_MAP)
    try:
        from utils.data_path import root_path as _root_path
        custom_path = _Path(_root_path()) / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                custom = data.get("_agent_models", {})
                if isinstance(custom, dict):
                    result.update(custom)
    except Exception:
        pass
    return result


AGENT_MODEL_MAP = _load_agent_models()

# Agent 角色（用户可感知的执行体）；memory_fold/planet_article 是辅助任务，
# 在分配表里可换但不作为「角色」对外（auth 端点 valid_roles 用本表）
AGENT_ROLE_KEYS = ("orchestrator", "collection", "analysis", "automation", "audit")


def _model_with_override(env_key: str, map_key: str, default: str) -> str:
    """模型选择链：env 优先 → models.json 分配覆盖 → 代码默认"""
    return os.getenv(env_key) or AGENT_MODEL_MAP.get(map_key) or default


# 知识星球「导图 → 文章化笔记」转换模型（注意：必须显式传模型名，call_llm 默认名会炸）
# 默认豆包（火山引擎国内节点，本地直连快且稳）；DeepSeek 海外 API 本地直连实测
# 一半请求卡超时（120s×2 后走大纲兜底），故不设为默认。后台可换（分配键 planet_article）。
PLANET_ARTICLE_MODEL = _model_with_override(
    "PLANET_ARTICLE_MODEL", "planet_article", "doubao-seed-2-0-lite-260215")


def reload_agent_models() -> None:
    """后台模型分配改动后热更新：AGENT_MODEL_MAP 原地替换（所有引用方生效），
    派生字符串重算（使用处均为函数内惰性 import，取模块属性即时生效）"""
    global MEMORY_MODEL, PLANET_ARTICLE_MODEL
    AGENT_MODEL_MAP.clear()
    AGENT_MODEL_MAP.update(_load_agent_models())
    MEMORY_MODEL = _model_with_override("MEMORY_MODEL", "memory_fold", "doubao-seed-2-0-lite-260215")
    PLANET_ARTICLE_MODEL = _model_with_override(
        "PLANET_ARTICLE_MODEL", "planet_article", "doubao-seed-2-0-lite-260215")

# ===================== 记忆机制（短期工作记忆 / 长期条目化记忆） =====================
# 决策：最近 N 条原样保留；超出部分豆包 lite 后台异步折叠成条目化事实存 users.memory；
# 设置页「我的记忆」透明可编辑；点踩内容不进记忆。选择链：env 优先 → 后台设定中心
# （_system_config）→ 默认；后台改完 reload_system_config 热更新。
MEMORY_ENABLED = bool(_syscfg("memory_enabled"))                          # 压缩总开关
MEMORY_MODEL = _model_with_override("MEMORY_MODEL", "memory_fold", "doubao-seed-2-0-lite-260215")  # 折叠用模型
MEMORY_WORKING_WINDOW = int(_syscfg("memory_working_window"))             # 工作记忆条数（最近 N 条永不折叠）
MEMORY_TRIGGER_CHARS = int(_syscfg("memory_trigger_chars"))               # 触发阈值：会话总字数
MEMORY_FOLD_MIN_MESSAGES = int(_syscfg("memory_fold_min_messages"))       # 单次折叠最小条数（烧钱护栏，设 1 = 字面口径）
MEMORY_FOLD_MIN_CHARS = int(_syscfg("memory_fold_min_chars"))
MEMORY_FOLD_INPUT_MAX_CHARS = int(_syscfg("memory_fold_input_max_chars")) # 单次折叠输入上限
MEMORY_MAX_ITEMS = int(_syscfg("memory_max_items"))                       # 长期记忆条数上限（超限丢最旧）
MEMORY_MAX_CHARS = int(_syscfg("memory_max_chars"))                       # 长期记忆字数上限（每轮注入，别开大）
MEMORY_FOLD_TIMEOUT_S = int(_syscfg("memory_fold_timeout_s"))
MEMORY_FOLD_DAILY_MAX = int(_syscfg("memory_fold_daily_max"))             # 每用户每日折叠次数上限
MEMORY_ORGANIZE_DELETE_DAILY_MAX = int(_syscfg("memory_organize_delete_daily_max"))  # 自整理删除：每用户每日删条数上限（安全事故教训后设的硬护栏）

# Agent 音色分配 — 气泡朗读按消息归属 Agent 选音色（均实测有效；须为 2.0 系列配 seed-tts-2.0）
_DEFAULT_AGENT_VOICE_MAP = {
    "orchestrator": "zh_male_shaonianzixin_uranus_bigtts",   # 小元：少年梓辛（小男孩）
    "local": "zh_male_shaonianzixin_uranus_bigtts",          # 本机小元：同音
    "analysis": "zh_female_xiaohe_uranus_bigtts",            # 数据分析：小鹤（女声）
    "collection": "zh_male_kailangdidi_uranus_bigtts",       # 数据采集：开朗弟弟
    "automation": "zh_female_qingxinnvsheng_uranus_bigtts",  # 自动化：清新女生
    "claude": "zh_male_yangguangqingnian_uranus_bigtts",     # Claude Code：阳光青年
}


def _load_agent_voices() -> dict:
    """从 models.json 读取自定义 Agent 音色分配，合并到默认映射"""
    result = dict(_DEFAULT_AGENT_VOICE_MAP)
    try:
        from utils.data_path import root_path as _root_path
        custom_path = _Path(_root_path()) / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                custom = data.get("_agent_voices", {})
                if isinstance(custom, dict):
                    result.update(custom)
    except Exception:
        pass
    return result


AGENT_VOICE_MAP = _load_agent_voices()

# ===================== 成本护栏（注册/配额/功能开关） =====================
REGISTER_OPEN = bool(_syscfg("register_open"))   # 公开注册开关（默认关，用户由管理员后台创建）
DAILY_MESSAGE_QUOTA = int(_syscfg("daily_message_quota"))  # 每用户每日消息配额（admin 不限；0 = 不限）
VOICE_ENABLED = bool(_syscfg("voice_enabled"))    # 语音通话/朗读功能总开关

# ===================== 鉴权配置 =====================

_jwt = os.getenv("JWT_SECRET_KEY")
if not _jwt or _jwt == "change-me-to-a-random-secret":
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("JWT_SECRET_KEY 未设置，生产环境必须设置此环境变量")
    # 持久化到文件，避免重启后 token 全部失效
    _secret_file = _Path(__file__).parent / ".jwt_secret"
    if _secret_file.exists():
        _jwt = _secret_file.read_text(encoding="utf-8").strip()
    else:
        _jwt = os.urandom(32).hex()
        _secret_file.write_text(_jwt, encoding="utf-8")
JWT_SECRET_KEY = _jwt
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# ===================== Claude Code 桥接配置 =====================

# 独立桥接进程的 agent_id（即专属云账号的 user_id；0 = 未启用）
CLAUDE_BRIDGE_AGENT_ID = int(os.getenv("CLAUDE_BRIDGE_AGENT_ID", "0"))
# 允许使用 /chat/claude-stream 的用户名（逗号分隔；为空 = 仅 admin）
CLAUDE_BRIDGE_ALLOWED_USERNAMES = [u.strip() for u in os.getenv("CLAUDE_BRIDGE_ALLOWED_USERNAMES", "").split(",") if u.strip()]
# 审批超时（秒）
CLAUDE_BRIDGE_APPROVAL_TIMEOUT = int(os.getenv("CLAUDE_BRIDGE_APPROVAL_TIMEOUT", "120"))

# ===================== 数据库配置 =====================

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "database": "ai_agent",
}

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    # S2.2：requirepass（未设置时兼容本地裸 Redis）
    "password": os.getenv("REDIS_PASSWORD") or None,
}

# ===================== 系统配置 =====================

# ===================== 云数据库配置 =====================

CLOUD_MYSQL_CONFIG = {
    "host": os.getenv("CLOUD_MYSQL_HOST", ""),
    "port": int(os.getenv("CLOUD_MYSQL_PORT", "3306")),
    "user": os.getenv("CLOUD_MYSQL_USER", "root"),
    "database": os.getenv("CLOUD_MYSQL_DATABASE", "ai_agent"),
}

# ===================== 火山引擎 TOS 配置 =====================

TOS_CONFIG = {
    "access_key_id": os.getenv("TOS_ACCESS_KEY_ID", ""),
    "access_key_secret": os.getenv("TOS_ACCESS_KEY_SECRET", ""),
    "endpoint": os.getenv("TOS_ENDPOINT", ""),
    "bucket": os.getenv("TOS_BUCKET", ""),
    "region": os.getenv("TOS_REGION", ""),
}

# ===================== 备份配置 =====================

BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backups"))
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "4"))

# ===================== 语音对话（火山引擎 RTC） =====================
# 前提：控制台开通「AI 音视频互动方案」→ 创建 RTC 应用（AppId/AppKey）
#      → IAM 密钥管理创建 AK/SK → 豆包语音控制台开通 ASR/TTS（各自 AppId + AccessToken）
VOLCANO_ACCESS_KEY = os.getenv("VOLCANO_ACCESS_KEY", "")        # IAM AccessKey（调用 OpenAPI）
VOLCANO_SECRET_KEY = os.getenv("VOLCANO_SECRET_KEY", "")        # IAM SecretKey
VOLCANO_RTC_APP_ID = os.getenv("VOLCANO_RTC_APP_ID", "")        # RTC 应用 AppId
VOLCANO_RTC_APP_KEY = os.getenv("VOLCANO_RTC_APP_KEY", "")      # RTC 应用 AppKey（Token 签名密钥）
VOICE_LLM_ENDPOINT_ID = os.getenv("VOICE_LLM_ENDPOINT_ID", "")  # 火山方舟推理接入点 ID（语音对话 LLM）
VOICE_ASR_APP_ID = os.getenv("VOICE_ASR_APP_ID", "")            # 豆包语音控制台 ASR AppId
VOICE_ASR_ACCESS_TOKEN = os.getenv("VOICE_ASR_ACCESS_TOKEN", "")  # 豆包语音控制台 ASR AccessToken
VOICE_TTS_APP_ID = os.getenv("VOICE_TTS_APP_ID", "")            # 豆包语音控制台 TTS AppId
VOICE_TTS_ACCESS_TOKEN = os.getenv("VOICE_TTS_ACCESS_TOKEN", "")  # 豆包语音控制台 TTS AccessToken

# 语音模型配置（易淘汰项，后台「模型配置」页可改：models.json _voice_config，
# PUT /admin/voice-config 热更新 reload_voice_config；env 优先）
_DEFAULT_VOICE_CONFIG = {
    "tts_model": "seed-tts-2.0",                             # 语音合成大模型（2026-10 官方最新；X-Api-Resource-Id）
    "tts_voice": "zh_female_xiaohe_uranus_bigtts",           # 气泡朗读默认音色（2.0 系列 uranus）
    "tts_voice_bot": "zh_male_shaonianzixin_uranus_bigtts",  # 通话机器人音色（小元：少年梓辛）
    "asr_resource": "volc.bigasr.sauc.concurrent",           # ASR 大模型资源（本地实测并发版已授权）
    "tts_resource": "volc.service_type.10029",               # TTS 双向通道资源
}


def _load_voice_config() -> dict:
    result = dict(_DEFAULT_VOICE_CONFIG)
    try:
        from utils.data_path import root_path as _root_path
        custom_path = _Path(_root_path()) / "data" / "models.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            if isinstance(data, dict):
                custom = data.get("_voice_config", {})
                if isinstance(custom, dict):
                    result.update(custom)
    except Exception:
        pass
    return result


VOICE_CONFIG = _load_voice_config()


def _voice_with_override(env_key: str, cfg_key: str, default: str) -> str:
    return os.getenv(env_key) or VOICE_CONFIG.get(cfg_key) or default


VOICE_TTS_MODEL = _voice_with_override("VOICE_TTS_MODEL", "tts_model", "seed-tts-2.0")
VOICE_TTS_VOICE = _voice_with_override("VOICE_TTS_VOICE", "tts_voice", "zh_female_xiaohe_uranus_bigtts")  # 气泡朗读音色
VOICE_TTS_VOICE_BOT = _voice_with_override("VOICE_TTS_VOICE_BOT", "tts_voice_bot", "zh_male_shaonianzixin_uranus_bigtts")  # 通话机器人音色
VOICE_ASR_RESOURCE_ID = _voice_with_override("VOICE_ASR_RESOURCE_ID", "asr_resource", "volc.bigasr.sauc.concurrent")  # ASR 资源


def reload_voice_config() -> None:
    """后台语音配置改动后热更新（voice router 均为函数内惰性 import，即时生效）"""
    global VOICE_TTS_MODEL, VOICE_TTS_VOICE, VOICE_TTS_VOICE_BOT, VOICE_ASR_RESOURCE_ID, VOICE_TTS_RESOURCE_ID
    VOICE_CONFIG.clear()
    VOICE_CONFIG.update(_load_voice_config())
    VOICE_TTS_MODEL = _voice_with_override("VOICE_TTS_MODEL", "tts_model", "seed-tts-2.0")
    VOICE_TTS_VOICE = _voice_with_override("VOICE_TTS_VOICE", "tts_voice", "zh_female_xiaohe_uranus_bigtts")
    VOICE_TTS_VOICE_BOT = _voice_with_override("VOICE_TTS_VOICE_BOT", "tts_voice_bot", "zh_male_shaonianzixin_uranus_bigtts")
    VOICE_ASR_RESOURCE_ID = _voice_with_override("VOICE_ASR_RESOURCE_ID", "asr_resource", "volc.bigasr.sauc.concurrent")
    VOICE_TTS_RESOURCE_ID = _voice_with_override("VOICE_TTS_RESOURCE_ID", "tts_resource", "volc.service_type.10029")

# ---- 语音调参（原散落在 voice/router.py 的字面量，统一下沉至此，.env 可覆盖） ----
VOICE_ASR_VOLUME_GAIN = float(os.getenv("VOICE_ASR_VOLUME_GAIN", "1"))
VOICE_ASR_STREAM_MODE = int(os.getenv("VOICE_ASR_STREAM_MODE", "1"))
VOICE_ASR_END_WINDOW_SIZE = int(os.getenv("VOICE_ASR_END_WINDOW_SIZE", "500"))
VOICE_ASR_FORCE_TO_SPEECH_TIME = int(os.getenv("VOICE_ASR_FORCE_TO_SPEECH_TIME", "500"))
VOICE_TTS_PITCH_RATE = float(os.getenv("VOICE_TTS_PITCH_RATE", "1"))
VOICE_TTS_SPEECH_RATE = float(os.getenv("VOICE_TTS_SPEECH_RATE", "1"))
# 气泡朗读语速（int [-50,100]，100=2.0x；火山 v3 unidirectional 的 speech_rate 语义，
# 与上面 RTC 双向通道的 float 倍率 SPEECH_RATE 完全不同，勿混用）
VOICE_TTS_SPEECH_RATE_BUBBLE = int(os.getenv("VOICE_TTS_SPEECH_RATE_BUBBLE", "0"))
# 气泡朗读单请求最大字数（前端已按句分段，正常不会触发；0=不限）
VOICE_TTS_MAX_CHARS = int(os.getenv("VOICE_TTS_MAX_CHARS", "3000"))
# 流式帧聚合阈值：音频累计到该字节数才发一帧（≈1s @24kHz/64kbps；太小=碎帧断续）
VOICE_TTS_CHUNK_BYTES = int(os.getenv("VOICE_TTS_CHUNK_BYTES", "8192"))
VOICE_TTS_RESOURCE_ID = _voice_with_override("VOICE_TTS_RESOURCE_ID", "tts_resource", "volc.service_type.10029")
VOICE_LLM_MAX_TOKENS = int(os.getenv("VOICE_LLM_MAX_TOKENS", "1024"))
VOICE_LLM_TEMPERATURE = float(os.getenv("VOICE_LLM_TEMPERATURE", "0.1"))
VOICE_LLM_TOP_P = float(os.getenv("VOICE_LLM_TOP_P", "0.3"))
VOICE_LLM_PREFILL = os.getenv("VOICE_LLM_PREFILL", "true").lower() == "true"
VOICE_LLM_HISTORY_LENGTH = int(os.getenv("VOICE_LLM_HISTORY_LENGTH", "3"))


# ===================== 后台设定中心：热更新函数（2026-10-17） =====================
# 消费侧多为函数内惰性 import，重赋模块属性即热生效；lc 的模块级快照由
# reload 主动同步刷新。

def reload_system_config() -> None:
    """_system_config 改动后热更新：重算全部覆盖链派生量 + 同步 lc 快照"""
    global SYSTEM_CONFIG, SELF_REPORT_TEMPLATE, CHAT_SYSTEM_PROMPT, CAPABILITY_NOTE
    global REASONING_EFFORT, MEMORY_ENABLED, MEMORY_WORKING_WINDOW, MEMORY_TRIGGER_CHARS
    global MEMORY_FOLD_MIN_MESSAGES, MEMORY_FOLD_MIN_CHARS, MEMORY_FOLD_INPUT_MAX_CHARS
    global MEMORY_MAX_ITEMS, MEMORY_MAX_CHARS, MEMORY_FOLD_TIMEOUT_S
    global MEMORY_FOLD_DAILY_MAX, MEMORY_ORGANIZE_DELETE_DAILY_MAX
    global REGISTER_OPEN, DAILY_MESSAGE_QUOTA, VOICE_ENABLED, MODEL_PRICING

    SYSTEM_CONFIG.clear()
    SYSTEM_CONFIG.update(_load_system_config())
    SELF_REPORT_TEMPLATE = str(_syscfg("self_report_template"))
    CHAT_SYSTEM_PROMPT = str(_syscfg("chat_system_prompt"))
    CAPABILITY_NOTE = str(_syscfg("capability_note"))
    REASONING_EFFORT = str(_syscfg("reasoning_effort"))
    MEMORY_ENABLED = bool(_syscfg("memory_enabled"))
    MEMORY_WORKING_WINDOW = int(_syscfg("memory_working_window"))
    MEMORY_TRIGGER_CHARS = int(_syscfg("memory_trigger_chars"))
    MEMORY_FOLD_MIN_MESSAGES = int(_syscfg("memory_fold_min_messages"))
    MEMORY_FOLD_MIN_CHARS = int(_syscfg("memory_fold_min_chars"))
    MEMORY_FOLD_INPUT_MAX_CHARS = int(_syscfg("memory_fold_input_max_chars"))
    MEMORY_MAX_ITEMS = int(_syscfg("memory_max_items"))
    MEMORY_MAX_CHARS = int(_syscfg("memory_max_chars"))
    MEMORY_FOLD_TIMEOUT_S = int(_syscfg("memory_fold_timeout_s"))
    MEMORY_FOLD_DAILY_MAX = int(_syscfg("memory_fold_daily_max"))
    MEMORY_ORGANIZE_DELETE_DAILY_MAX = int(_syscfg("memory_organize_delete_daily_max"))
    REGISTER_OPEN = bool(_syscfg("register_open"))
    DAILY_MESSAGE_QUOTA = int(_syscfg("daily_message_quota"))
    VOICE_ENABLED = bool(_syscfg("voice_enabled"))
    MODEL_PRICING = dict(_MODEL_PRICING_DEFAULTS)
    try:
        _pricing_env = os.getenv("MODEL_PRICING_JSON", "")
        if _pricing_env:
            MODEL_PRICING = {**MODEL_PRICING, **json.loads(_pricing_env)}
    except Exception:
        pass
    _pricing_syscfg = _syscfg("model_pricing")
    if isinstance(_pricing_syscfg, dict) and _pricing_syscfg:
        MODEL_PRICING = {**MODEL_PRICING, **_pricing_syscfg}
    # 同步 lc 模块级快照（REASONING_EFFORT / dsllm / seed）
    try:
        import yuanai_core.core.lc as _lc
        _lc.REASONING_EFFORT = REASONING_EFFORT
    except Exception:
        pass


def reload_models_registry() -> None:
    """模型清单热更新：MODELS + MODEL_NAMES + lc.dsllm/seed 全链路刷新
    （修「新加模型走不了 DeepSeek/豆包通道，重启才生效」的缺口）"""
    global MODELS, MODEL_NAMES
    MODELS.clear()
    MODELS.update(_load_models())
    MODEL_NAMES[:] = list(MODELS.keys())
    try:
        import yuanai_core.core.lc as _lc
        _lc.refresh_model_lists()
    except Exception:
        pass


def reload_agent_voices() -> None:
    """Agent 音色分配热更新（修「用户设置页改音色写盘但内存不刷新」的缺口）"""
    AGENT_VOICE_MAP.clear()
    AGENT_VOICE_MAP.update(_load_agent_voices())
