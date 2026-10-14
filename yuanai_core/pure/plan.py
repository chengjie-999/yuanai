"""计划闭环纯逻辑 — 校验 / 执行提示词 / 输出解析（无 DB 无 LLM 无 FastAPI）

v1 边界：步骤只声明 skill + 意图描述 + 参数（云端无脚本清单，执行机现场
LLM 选脚本）；skill 白名单 analysis/collection（automation 挂账）。
"""
import json
import re

PLAN_SKILLS = ("analysis", "collection")
# 防协议注入：步骤描述/参数不得携带脚本输出协议标记
FORBIDDEN_MARKERS = ("__DASHBOARD__:", "__RESULT__:", "__PROGRESS__:",
                     "__IMAGES__:", "__HTML__:")

MAX_STEPS = 8
MAX_DESC_LEN = 300
MAX_TITLE_LEN = 100
MAX_GOAL_LEN = 500
MAX_PARAMS_KEYS = 8
MAX_PARAM_VAL_LEN = 200
MAX_SCRIPT_LEN = 64
# script 字段字符集（中文名/ASCII key/点横线空格；不做存在性校验——云端无
# 脚本清单，存在性由执行器对 ScriptRegistry 判定）
_SCRIPT_RE = re.compile(r"^[\w\-. ]{1,64}$", re.UNICODE)

# 结果文本截断（与 api/v1/plan/store.py RESULT_TEXT_MAX 一致）
RESULT_TEXT_MAX = 20000


def validate_title_goal(title, goal) -> tuple:
    """(title, goal, err)；err 非空即不通过"""
    title = str(title or "").strip()
    goal = str(goal or "").strip()
    if not title:
        return title, goal, "标题不能为空"
    if len(title) > MAX_TITLE_LEN:
        return title, goal, f"标题超过 {MAX_TITLE_LEN} 字"
    if len(goal) > MAX_GOAL_LEN:
        return title, goal, f"目标超过 {MAX_GOAL_LEN} 字"
    return title[:MAX_TITLE_LEN], goal[:MAX_GOAL_LEN], ""


def validate_steps(steps_raw) -> tuple:
    """校验模型产出的步骤（str JSON 或 list）→ (steps, err)。
    steps: [{"skill", "desc", "params"}]；err 非空即不通过。"""
    if isinstance(steps_raw, str):
        try:
            data = json.loads(steps_raw)
        except Exception:
            return [], "步骤必须是合法 JSON 数组"
    else:
        data = steps_raw
    if not isinstance(data, list) or not (1 <= len(data) <= MAX_STEPS):
        return [], f"步骤数须为 1-{MAX_STEPS}"
    steps = []
    for s in data:
        if not isinstance(s, dict):
            return [], "每步必须是对象"
        skill = str(s.get("skill", "") or "").strip() or "analysis"
        if skill not in PLAN_SKILLS:
            return [], f"skill 仅支持 {'/'.join(PLAN_SKILLS)}（收到 {skill!r}）"
        desc = str(s.get("desc", "") or "").strip()
        if not desc:
            return [], "每步必须有 desc（说明做什么）"
        if len(desc) > MAX_DESC_LEN:
            return [], f"步骤描述超过 {MAX_DESC_LEN} 字"
        if any(m in desc for m in FORBIDDEN_MARKERS):
            return [], "步骤描述含非法协议标记"
        # 可选 script（本地统筹建计划时绑定脚本名/key；空 = 执行器现场选）
        script = str(s.get("script", "") or "").strip()
        if script:
            if len(script) > MAX_SCRIPT_LEN:
                return [], f"script 超过 {MAX_SCRIPT_LEN} 字符"
            if any(m in script for m in FORBIDDEN_MARKERS) or ".." in script:
                return [], "script 含非法标记"
            if not _SCRIPT_RE.match(script):
                return [], "script 仅允许中英文/数字/点/横线/空格"
        params = s.get("params") or {}
        if not isinstance(params, dict):
            return [], "params 必须是对象"
        if len(params) > MAX_PARAMS_KEYS:
            return [], f"每步参数不超过 {MAX_PARAMS_KEYS} 个"
        clean = {}
        for k, v in params.items():
            if not isinstance(v, (str, int, float, bool)):
                return [], f"参数 {k} 的值类型不支持"
            sv = str(v)
            if len(sv) > MAX_PARAM_VAL_LEN or any(m in sv for m in FORBIDDEN_MARKERS):
                return [], f"参数 {k} 非法"
            clean[str(k)[:50]] = v
        steps.append({"skill": skill, "script": script, "desc": desc[:MAX_DESC_LEN],
                      "params": clean})
    return steps, ""


def build_step_prompt(plan: dict, step: dict, prev_summaries: list) -> str:
    """步骤执行提示词（自包含：执行时是独立 LLM 调用，看不到对话历史）"""
    lines = [
        f"【计划】{plan.get('title', '')}",
        f"【总目标】{plan.get('goal', '')}",
        f"【当前步骤 {step.get('step_no', '')}/{plan.get('total_steps', '')}】{step.get('desc', '')}",
    ]
    params = step.get("params") or {}
    if params:
        lines.append("【已知参数（优先使用，不要编造）】"
                     + "、".join(f"{k}={v}" for k, v in params.items()))
    if prev_summaries:
        lines.append("【前序步骤结果摘要】")
        for p in prev_summaries:
            lines.append(f"- 第{p.get('step_no', '')}步（{str(p.get('desc', ''))[:40]}）："
                         f"{str(p.get('summary', ''))[:200]}")
    lines.append("请直接执行本步骤，不要询问确认、不要输出计划说明。")
    return "\n".join(lines)


def parse_step_output(raw: str) -> dict:
    """解析 skill agent 输出：读 __DASHBOARD__ 文件取结构化 blocks；
    剥离协议标记与 base64 图片。返回 {"text", "blocks", "truncated"}"""
    raw = str(raw or "")
    blocks = None
    # __DASHBOARD__:{path} → 读 JSON 取结构化数据（计划页 KPI/表格渲染用）
    m = re.search(r"__DASHBOARD__:(\S+)", raw)
    if m:
        try:
            with open(m.group(1), encoding="utf-8") as f:
                blocks = json.load(f)
        except Exception:
            pass
    # 剥离协议标记（__XXX__[:值]，如 __HTML__URL:/api/x）与 base64 图片
    # （v1 计划结果只留文本与结构化数据）
    text = re.sub(r"__\S+", "", raw)
    text = re.sub(r"data:image/\w+;base64,[A-Za-z0-9+/=]+", "[图片]", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    truncated = len(text) > RESULT_TEXT_MAX
    return {"text": text[:RESULT_TEXT_MAX], "blocks": blocks, "truncated": truncated}
