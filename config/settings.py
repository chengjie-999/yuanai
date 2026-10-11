import os
from dotenv import load_dotenv

load_dotenv()

# ===================== 模型配置 =====================

import json as _json
from pathlib import Path as _Path

_DEFAULT_MODELS = {
    "doubao-seed-2-0-pro-260215": {"label": "豆包 Pro", "provider": "Doubao"},
    "doubao-seed-2-0-lite-260215": {"label": "豆包 Lite", "provider": "Doubao"},
    "deepseek-v4-flash": {"label": "DeepSeek V4 Flash", "provider": "DeepSeek"},
    "deepseek-v4-pro": {"label": "DeepSeek V4 Pro", "provider": "DeepSeek"},
}

def _load_models() -> dict:
    models = dict(_DEFAULT_MODELS)
    try:
        custom_path = _Path(__file__).parent.parent / "data" / "models.json"
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
DEFAULT_MODEL = "deepseek-v4-flash"
VISION_MODEL = "doubao-seed-2-0-pro-260215"  # DeepSeek V4 不支持图片，识图自动切豆包
DEFAULT_TEMPERATURE = 0.7

# 推理强度（DeepSeek 系列 reasoning_effort，.env 可覆盖）：
#   low = 快答省 token（默认）；medium = 标准；high = 深度思考（复杂分析）
# 豆包系列不走此参数——思考模式由方舟接入点（火山控制台 endpoint）的 thinking 开关控制
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")

# 模型 API 定价（元 / 百万 token，成本面板用）。
# ⚠ 价格为占位默认值，以官方最新价为准；整体覆盖：.env 设 MODEL_PRICING_JSON
#   形如 {"deepseek-v4-pro": {"in": 2.0, "out": 8.0}, ...}；未列出的模型记 0 成本（标记未定价）
_MODEL_PRICING_DEFAULTS = {
    "deepseek-v4-flash": {"in": 0.5, "out": 2.0},
    "deepseek-v4-pro": {"in": 2.0, "out": 8.0},
    "deepseek-reasoner": {"in": 4.0, "out": 16.0},
    "doubao-seed-2-0-lite-260215": {"in": 0.3, "out": 0.6},
    "doubao-seed-2-0-pro-260215": {"in": 0.8, "out": 2.0},
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

# 知识星球「导图 → 文章化笔记」转换模型（注意：必须显式传模型名，call_llm 默认名会炸）
# 默认豆包（火山引擎国内节点，本地直连快且稳）；DeepSeek 海外 API 本地直连实测
# 一半请求卡超时（120s×2 后走大纲兜底），故不设为默认，可 .env 覆盖
PLANET_ARTICLE_MODEL = os.getenv("PLANET_ARTICLE_MODEL", "doubao-seed-2-0-lite-260215")

# Agent 模型分配 — 统一入口，消除代码中 15+ 处硬编码
_DEFAULT_AGENT_MODEL_MAP = {
    # 通用快模型 — 意图识别 / 任务路由 / 简单爬取
    "orchestrator": "deepseek-v4-flash",
    "collection": "deepseek-v4-flash",
    # 强推理 — 数据分析 / 复杂统计 / 图表生成
    "analysis": "deepseek-v4-pro",
    # 多模态 — 浏览器截图 / 视觉审核 / 图片理解
    "automation": "doubao-seed-2-0-pro-260215",
    "audit": "doubao-seed-2-0-pro-260215",
}


def _load_agent_models() -> dict:
    """从 models.json 读取自定义 Agent 模型分配，合并到默认映射"""
    result = dict(_DEFAULT_AGENT_MODEL_MAP)
    try:
        custom_path = _Path(__file__).parent.parent / "data" / "models.json"
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

# ===================== 记忆机制（短期工作记忆 / 长期条目化记忆） =====================
# 决策：最近 N 条原样保留；超出部分豆包 lite 后台异步折叠成条目化事实存 users.memory；
# 设置页「我的记忆」透明可编辑；点踩内容不进记忆。全部可 .env 覆盖。
MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "true").lower() == "true"     # 压缩总开关
MEMORY_MODEL = os.getenv("MEMORY_MODEL", "doubao-seed-2-0-lite-260215")    # 折叠用模型（豆包 lite）
MEMORY_WORKING_WINDOW = int(os.getenv("MEMORY_WORKING_WINDOW", "20"))      # 工作记忆条数（最近 N 条永不折叠）
MEMORY_TRIGGER_CHARS = int(os.getenv("MEMORY_TRIGGER_CHARS", "8000"))      # 触发阈值：会话总字数
MEMORY_FOLD_MIN_MESSAGES = int(os.getenv("MEMORY_FOLD_MIN_MESSAGES", "5")) # 单次折叠最小条数（烧钱护栏，设 1 = 字面口径）
MEMORY_FOLD_MIN_CHARS = int(os.getenv("MEMORY_FOLD_MIN_CHARS", "800"))
MEMORY_FOLD_INPUT_MAX_CHARS = int(os.getenv("MEMORY_FOLD_INPUT_MAX_CHARS", "12000"))  # 单次折叠输入上限
MEMORY_MAX_ITEMS = int(os.getenv("MEMORY_MAX_ITEMS", "100"))               # 长期记忆条数上限（超限丢最旧）
MEMORY_MAX_CHARS = int(os.getenv("MEMORY_MAX_CHARS", "2000"))              # 长期记忆字数上限（每轮注入，别开大）
MEMORY_FOLD_TIMEOUT_S = int(os.getenv("MEMORY_FOLD_TIMEOUT_S", "120"))
MEMORY_FOLD_DAILY_MAX = int(os.getenv("MEMORY_FOLD_DAILY_MAX", "50"))      # 每用户每日折叠次数上限

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
        custom_path = _Path(__file__).parent.parent / "data" / "models.json"
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
REGISTER_OPEN = os.getenv("REGISTER_OPEN", "false").lower() == "true"   # 公开注册开关（默认关，用户由管理员后台创建）
DAILY_MESSAGE_QUOTA = int(os.getenv("DAILY_MESSAGE_QUOTA", "50"))       # 每用户每日消息配额（admin 不限；0 = 不限）
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"    # 语音通话/朗读功能总开关

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
VOICE_TTS_VOICE = os.getenv("VOICE_TTS_VOICE", "zh_female_xiaohe_uranus_bigtts")  # 气泡朗读音色（须为 2.0 系列，配 seed-tts-2.0 资源）
VOICE_TTS_VOICE_BOT = os.getenv("VOICE_TTS_VOICE_BOT", "zh_male_shaonianzixin_uranus_bigtts")  # 通话机器人音色（主智能体小元：少年梓辛小男孩；uranus 音色在 bidirection 通道待通话实测，无声则回退 mars 系列）
VOICE_ASR_RESOURCE_ID = os.getenv("VOICE_ASR_RESOURCE_ID", "volc.bigasr.sauc.concurrent")  # ASR 大模型资源（本地实测：并发版已授权、时长版 403）

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
VOICE_TTS_RESOURCE_ID = os.getenv("VOICE_TTS_RESOURCE_ID", "volc.service_type.10029")
VOICE_LLM_MAX_TOKENS = int(os.getenv("VOICE_LLM_MAX_TOKENS", "1024"))
VOICE_LLM_TEMPERATURE = float(os.getenv("VOICE_LLM_TEMPERATURE", "0.1"))
VOICE_LLM_TOP_P = float(os.getenv("VOICE_LLM_TOP_P", "0.3"))
VOICE_LLM_PREFILL = os.getenv("VOICE_LLM_PREFILL", "true").lower() == "true"
VOICE_LLM_HISTORY_LENGTH = int(os.getenv("VOICE_LLM_HISTORY_LENGTH", "3"))
