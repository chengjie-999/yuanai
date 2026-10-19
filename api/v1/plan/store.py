"""计划闭环云端服务层 — 所有权校验（越权一律 404）/ 状态迁移 / 看门狗 / 结果截断"""
import json
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 结果截断上限（三层防爆：文本 20K 字符 / 结构化 blocks 200KB / 事件 payload 5KB）
RESULT_TEXT_MAX = 20_000
RESULT_BLOCKS_MAX = 200_000


def _db():
    from db.session import get_db
    return get_db()


def _require_plan(plan_id: int, user_id: int) -> dict:
    p = _db().get_plan(plan_id, user_id)
    if not p:
        raise HTTPException(status_code=404, detail="计划不存在")
    return p


def plan_agent_online(user_id: int) -> bool:
    """该用户绑定的本机 Agent 是否在线（execute 响应提示「排队中」用）

    双路径判定（2026-10-15 修复）：execute_plan 工具在本地 Agent 进程直连
    路径执行时，import 进来的 api.v1.agent.router._agents 是本进程自己的空表
    ——永远判离线（曾致「本机 Agent 未连接」误报）。回退查设备 last_seen
    心跳（云端 _heartbeat 每 30s 刷新，UTC 存储，窗口 120s）。
    """
    try:
        from api.v1.agent.router import get_agent
        if get_agent(user_id) is not None:
            return True
    except Exception:
        pass
    try:
        from datetime import datetime, timedelta
        from db.session import get_db
        last = get_db().get_bound_device_last_seen(user_id)
        if last:
            return datetime.utcnow() - last < timedelta(seconds=120)
    except Exception:
        pass
    return False


def apply_plan_watchdog(plan_id: int, user_id: int) -> None:
    """读计划详情时跑：步骤认领超时 900s 回 pending；计划级 3600s 无进展判 failed"""
    from datetime import datetime, timedelta

    db = _db()
    db.reset_stale_plan_claims(user_id, timeout_s=900)
    p = db.get_plan(plan_id, user_id)
    if not p or p["status"] != "running":
        return
    try:
        upd = datetime.strptime(p["update_time"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return
    if datetime.now() - upd > timedelta(seconds=3600):
        db.update_plan(plan_id, user_id, status="failed", error="执行超时")
        db.append_plan_run(plan_id, None, user_id, "plan_failed", "running", "failed",
                           "执行超时（3600s 无进展）")


def execute_plan(plan_id: int, user_id: int, step_ids: list = None) -> dict:
    """draft/failed → queued；重跑指定失败步（置回 pending）。幂等：已运行返回 already"""
    db = _db()
    p = _require_plan(plan_id, user_id)
    if p["status"] in ("queued", "running"):
        return {"ok": True, "already": True, "agent_online": plan_agent_online(user_id)}
    if p["status"] not in ("draft", "failed"):
        raise HTTPException(status_code=409, detail=f"状态 {p['status']} 不可执行")
    if step_ids:
        reset = 0
        for sid in step_ids:
            if db.update_plan_step(sid, user_id, status="pending", error="",
                                   result_json="", progress=0):
                reset += 1
        db.append_plan_run(plan_id, None, user_id, "step_reset", "failed", "pending",
                           f"重跑 {reset} 个失败步骤", {"step_ids": step_ids})
    db.update_plan(plan_id, user_id, status="queued", error="",
                   failed_steps=0, message="等待本机执行")
    db.append_plan_run(plan_id, None, user_id, "queued", p["status"], "queued",
                       "用户触发执行")
    return {"ok": True, "already": False, "agent_online": plan_agent_online(user_id)}


def create_plan_for_user(user_id: int, title: str, goal: str, steps: list,
                         session_id: str = "", device_id: str = "") -> dict:
    """建计划（手动端点 / 工具共用）；校验失败 400 且不落库"""
    r = _db().create_plan(user_id, title, goal, steps, session_id, device_id)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("detail", "创建失败"))
    return r


def truncate_result(result_json: dict) -> dict:
    """步结果截断：text ≤20K 字符 / blocks ≤200KB；超限标记 truncated"""
    out = dict(result_json or {})
    text = out.get("text") or ""
    if len(text) > RESULT_TEXT_MAX:
        out["text"] = text[:RESULT_TEXT_MAX]
        out["truncated"] = True
    blocks = out.get("blocks")
    if isinstance(blocks, str):
        if len(blocks) > RESULT_BLOCKS_MAX:
            out["blocks"] = blocks[:RESULT_BLOCKS_MAX]
            out["truncated"] = True
    elif isinstance(blocks, (list, dict)):
        s = json.dumps(blocks, ensure_ascii=False)
        if len(s) > RESULT_BLOCKS_MAX:
            # 2026-10-19 修复：此前按字符截断后拼 '"]' 生成非法 JSON →
            # /step-done 解析 500、步骤卡 running。改为截断到合法子结构
            out["blocks"] = _truncate_json(blocks, RESULT_BLOCKS_MAX)
            out["truncated"] = True
    return out


def _truncate_json(obj, limit: int):
    """把 list/dict 截断到序列化后 ≤ limit 字节的合法 JSON（无法满足返回 None）"""
    if isinstance(obj, list):
        items = []
        for it in obj:
            items.append(it)
            if len(json.dumps(items, ensure_ascii=False)) > limit:
                items.pop()
                break
        return items
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = v
            if len(json.dumps(out, ensure_ascii=False)) > limit:
                out.pop(k)
                break
        return out
    return None


def resolve_plan_id(plan_id: int, user_id: int) -> int:
    """plan_id=0 → 该用户最近一个草稿计划；无草稿 404"""
    if plan_id:
        return int(plan_id)
    plans = _db().list_plans(user_id, status="draft", limit=1)
    if not plans:
        raise HTTPException(status_code=404, detail="没有待执行的草稿计划（先让模型 create_plan 制定计划）")
    return plans[0]["id"]


_STATUS_CN = {"draft": "草稿（未执行）", "queued": "排队中（等电脑执行）",
              "running": "执行中", "done": "已完成", "failed": "失败"}
_SKILL_CN = {"analysis": "数据分析", "collection": "数据采集"}


def format_plan_status(user_id: int, plan_id: int = 0) -> str:
    """计划状态人读文本（get_plan_status 工具 / 手机问「计划怎么样了」）"""
    db = _db()
    if plan_id:
        p = db.get_plan(int(plan_id), user_id)
        if not p:
            return "计划不存在"
        plans = [p]
    else:
        plans = db.list_plans(user_id, limit=3)
        if not plans:
            return "你还没有计划。可以说「帮我制定一个计划：…」来创建。"
    lines = []
    for p in plans[:1] if not plan_id else plans:
        st = _STATUS_CN.get(p["status"], p["status"])
        lines.append(f"计划 #{p['id']}「{p['title']}」：{st}（进度 {p['progress']}%，"
                     f"完成 {p['done_steps']}/{p['total_steps']} 步）")
        for s in db.get_plan_steps(p["id"], user_id):
            st_name = {"pending": "待执行", "running": "运行中", "done": "已完成",
                       "failed": "失败"}.get(s["status"], s["status"])
            extra = f" {s['progress']}%" if s["status"] == "running" else ""
            err = f" 错误：{s['error'][:80]}" if s["status"] == "failed" and s.get("error") else ""
            lines.append(f"  [{st_name}] 第{s['step_no']}步[{_SKILL_CN.get(s['skill'], s['skill'])}] "
                         f"{s['desc'][:40]}{extra}{err}")
    return "\n".join(lines)


def step_dict(step: dict) -> dict:
    """步骤输出归一（params 解析成对象；result 解析成对象并截断）"""
    out = dict(step)
    try:
        out["params"] = json.loads(step.get("params_json") or "{}")
    except Exception:
        out["params"] = {}
    out.pop("params_json", None)
    if step.get("result_json"):
        try:
            out["result"] = json.loads(step["result_json"])
        except Exception:
            out["result"] = {"text": str(step["result_json"])[:500]}
    out.pop("result_json", None)
    return out
