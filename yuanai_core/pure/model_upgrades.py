"""模型升级知识表 + 升级计划纯函数（云边共用，零框架依赖）

「模型淘汰自动检查更新，确认后自动添加和更换」的落地：
- 模型换代时由 AI 维护本表（MODEL_UPGRADES / UPSTREAM_MODELS / VOICE_UPGRADES 三处登记）
- 后台「模型配置」页调 /admin/models/upgrade-plan 出升级清单（检查）
- 管理员一键确认 → /admin/models/upgrade 自动执行：加新模型 + 切分配 + 移旧模型 + 热更新
- 纯函数只做计划与数据变换；读写 models.json / 热更新 / 审计在 admin 端点

系列推断说明：豆包 ID 带日期后缀（-YYMMDD）；DeepSeek V4.1 Flash 官方新 ID 为
deepseek-flash（旧 deepseek-v4-flash 已路由至它，deepseek-chat 别名 2026-07-24 停用）。
"""

# 旧模型 ID → 新模型 ID（在用即提示升级）
# 2026-10-16：豆包 2.0→2.1 条目暂不登记——2.1 需先在方舟控制台开通（ModelNotOpen），
# 账号开通后把下面注释的两条解回 MODEL_UPGRADES 并同步 UPSTREAM_MODELS 即可一键升级
MODEL_UPGRADES = {
    # "doubao-seed-2-0-pro-260215": {"new": "doubao-seed-2-1-pro-260628", "label": "豆包 Pro"},
    # "doubao-seed-2-0-lite-260215": {"new": "doubao-seed-2-1-lite-260915", "label": "豆包 Lite"},
    "deepseek-v4-flash": {"new": "deepseek-flash", "label": "DeepSeek V4.1 Flash"},
    "deepseek-chat": {"new": "deepseek-flash", "label": "DeepSeek V4.1 Flash"},
}

# 上游当前有效清单（本地没有的模型列为「可添加的新模型」，不自动添加）
UPSTREAM_MODELS = {
    "DeepSeek": {"deepseek-flash", "deepseek-v4-pro"},
    "Doubao": {"doubao-seed-2-0-pro-260215", "doubao-seed-2-0-lite-260215"},
}

# 语音合成模型升级（seed-tts-2.0 为 2026-10 官方最新；出新版时在此登记）
VOICE_UPGRADES = {
    # "seed-tts-2.0": {"new": "seed-tts-3.0", "label": "豆包语音合成 3.0"},
}


def plan_model_upgrades(agent_models: dict) -> list:
    """在用模型命中升级映射 → [{old, new, label, used_by}]；无则空列表"""
    used = set(agent_models.values())
    plans = []
    for old, info in MODEL_UPGRADES.items():
        if old in used and old != info["new"]:
            used_by = sorted(k for k, v in agent_models.items() if v == old)
            plans.append({"old": old, "new": info["new"], "label": info["label"],
                          "used_by": used_by})
    return plans


def plan_new_models(local_models: dict) -> list:
    """上游清单中本地没有的模型 → [{model_id, label, provider}]（仅展示，不自动加）"""
    local = {k for k in (local_models or {}) if not str(k).startswith("_")}
    out = []
    for provider, ids in UPSTREAM_MODELS.items():
        for mid in sorted(ids):
            if mid not in local:
                out.append({"model_id": mid, "label": f"{provider} 新模型", "provider": provider})
    return out


def plan_voice_upgrades(voice_config: dict) -> list:
    """语音模型命中升级映射 → [{old, new, label, key}]（key = _voice_config 的配置键）"""
    plans = []
    for key, val in (voice_config or {}).items():
        info = VOICE_UPGRADES.get(str(val))
        if info:
            plans.append({"old": val, "new": info["new"], "label": info["label"], "key": key})
    return plans


def provider_of(model_id: str) -> str:
    """模型 ID → 供应商（用于登记新模型时的 provider 字段）"""
    for provider, ids in UPSTREAM_MODELS.items():
        if model_id in ids:
            return provider
    return "Custom"
