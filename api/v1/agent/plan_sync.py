"""计划同步 REST — 本地 Agent 专用（agent/plan_executor.py 走这里）

鉴权链（端点自带，中间件豁免 /api/v1/agent/plan 前缀）：
X-Agent-Id + X-Agent-Secret → _verify_agent_secret → resolve_agent_uid
（设备一对一绑定）→ 未绑定 403。body 一律不带 user_id，身份由设备推导
（比 memory 端点更严：伪造他人 step_id 会被 user_id 冗余校验 404 拦截）。

端点：
- POST /create     对话建计划（create_plan 工具 HTTP 通道）
- POST /execute    用户说「执行」→ queued（execute_plan 工具 HTTP 通道）
- POST /pull       拉取认领下一个待执行步骤（含看门狗重置 + CAS 认领）
- POST /progress   步内进度（节流：同一步 ≥3s 才落库，事件 ≥10s 或 Δ5%）
- POST /step-done  步骤完成（幂等；全完成 → 计划 done）
- POST /step-failed 步骤失败（retryable 且 attempt<2 → 回 pending 自动重试一次）
"""
import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.v1.agent.planet_sync import _agent_uid
from api.v1.plan import store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent/plan", tags=["agent-plan"])

PROGRESS_HTTP_MIN_S = 3       # 同一步 HTTP 上报最小间隔
PROGRESS_EVENT_MIN_S = 10     # 事件表进度落库最小间隔（或 Δ5%）
PROGRESS_EVENT_DELTA = 5

# 进程内节流状态（单进程部署；重启即丢，无损——事件表少几条而已）
_progress_state: dict = {}


class CreateBody(BaseModel):
    title: str = ""
    goal: str = ""
    steps: list = []
    session_id: str = ""


class ExecuteBody(BaseModel):
    plan_id: int = 0


class PullBody(BaseModel):
    pass


class ProgressBody(BaseModel):
    step_id: int = 0
    current: int = 0
    total: int = 0
    message: str = ""


class StepDoneBody(BaseModel):
    step_id: int = 0
    summary: str = ""
    script: str = ""
    result_json: dict = {}


class StepFailedBody(BaseModel):
    step_id: int = 0
    error: str = ""
    retryable: bool = True


def _db():
    from db.session import get_db
    return get_db()


def _step_or_404(step_id: int, uid: int) -> dict:
    # user_id 冗余校验：伪造他人 step_id 一律 404（设备绑定 + 行归属双保险）
    s = _db().get_plan_step(step_id, uid)
    if not s:
        raise HTTPException(status_code=404, detail="步骤不存在")
    return s


@router.post("/create")
def agent_create_plan(request: Request, body: CreateBody):
    """对话建计划（create_plan 工具 HTTP 通道；校验失败 400 不落库）"""
    uid = _agent_uid(request)
    return store.create_plan_for_user(uid, body.title, body.goal, body.steps,
                                      body.session_id)


@router.post("/execute")
def agent_execute_plan(request: Request, body: ExecuteBody):
    """execute_plan 工具 HTTP 通道；plan_id=0 → 最近一个草稿（云端解析）"""
    uid = _agent_uid(request)
    pid = store.resolve_plan_id(body.plan_id, uid)
    return store.execute_plan(pid, uid)


class StatusBody(BaseModel):
    plan_id: int = 0


@router.post("/status")
def agent_plan_status(request: Request, body: StatusBody):
    """get_plan_status 工具 HTTP 通道"""
    uid = _agent_uid(request)
    return {"ok": True, "plan": store.format_plan_status(uid, int(body.plan_id or 0))}


@router.post("/pull")
def agent_pull(request: Request, body: PullBody):
    """拉取认领下一步（执行器 10s 空转轮询）。先重置本设备超时认领（断点续跑）。"""
    uid = _agent_uid(request)
    device_id = request.headers.get("X-Agent-Id", "")
    db = _db()
    db.reset_stale_plan_claims(uid, device_id=device_id, timeout_s=900)
    claimed = db.claim_next_plan_step(uid, device_id)
    if not claimed:
        return {"empty": True}
    return {"empty": False, **claimed}


@router.post("/progress")
def agent_progress(request: Request, body: ProgressBody):
    uid = _agent_uid(request)
    if not body.step_id:
        raise HTTPException(status_code=400, detail="缺少 step_id")
    s = _step_or_404(body.step_id, uid)
    if s["status"] != "running":
        return {"ok": True, "throttled": True}  # 非 running 静默忽略（看门狗竞态）

    now = time.time()
    st = _progress_state.get(body.step_id)
    if st and now - st[0] < PROGRESS_HTTP_MIN_S:
        return {"ok": True, "throttled": True}

    db = _db()
    total = max(body.total or 0, 1)
    pct = min(max(int(body.current / total * 100), 0), 100) if body.current else 0
    db.update_plan_step(body.step_id, uid, progress=pct,
                        last_message=(body.message or "")[:500])
    plan = db.get_plan(s["plan_id"], uid)
    if plan:
        step_no = s["step_no"] or 1
        db.update_plan(s["plan_id"], uid,
                       message=f"正在执行第 {step_no}/{plan['total_steps']} 步："
                               f"{(body.message or '')[:60]}",
                       progress=_plan_progress(db, s["plan_id"], uid))
    # 事件表节流：≥10s 或 Δ5% 才 append（事件溯源只记关键变化）
    if not st or now - st[1] >= PROGRESS_EVENT_MIN_S or abs(pct - st[2]) >= PROGRESS_EVENT_DELTA:
        db.append_plan_run(s["plan_id"], body.step_id, uid, "progress", "", "",
                           f"{body.message or ''}（{body.current}/{total}）",
                           {"current": body.current, "total": body.total, "pct": pct})
        st = (st[0] if st else now, now, pct)
    else:
        st = (st[0] if st else now, st[1] if st else now, st[2] if st else pct)
    _progress_state[body.step_id] = st
    return {"ok": True, "throttled": False}


def _plan_progress(db, plan_id: int, uid: int) -> int:
    """计划进度 = (done + 运行中步的步内进度) / total * 100"""
    steps = db.get_plan_steps(plan_id, uid)
    if not steps:
        return 0
    acc = 0
    for s in steps:
        if s["status"] == "done":
            acc += 100
        elif s["status"] == "running":
            acc += s["progress"] or 0
    return min(int(acc / len(steps)), 100)


@router.post("/step-done")
def agent_step_done(request: Request, body: StepDoneBody):
    uid = _agent_uid(request)
    if not body.step_id:
        raise HTTPException(status_code=400, detail="缺少 step_id")
    s = _step_or_404(body.step_id, uid)
    if s["status"] == "done":
        return {"ok": True, "already": True}  # 幂等
    if s["status"] != "running":
        raise HTTPException(status_code=409, detail=f"步骤状态 {s['status']} 不可完成")

    db = _db()
    result = store.truncate_result(body.result_json or {})
    result["script"] = (body.script or "")[:50]
    result["summary"] = (body.summary or "")[:500]
    import json as _json
    db.update_plan_step(body.step_id, uid, status="done", progress=100,
                        finished_at=datetime.now(),
                        result_json=_json.dumps(result, ensure_ascii=False),
                        error="", last_message="完成")
    db.append_plan_run(s["plan_id"], body.step_id, uid, "step_done", "running", "done",
                       f"第 {s['step_no']} 步完成{(('：' + body.script) if body.script else '')}",
                       {"script": body.script or ""})
    _finalize_plan(db, s["plan_id"], uid)
    return {"ok": True}


@router.post("/step-failed")
def agent_step_failed(request: Request, body: StepFailedBody):
    uid = _agent_uid(request)
    if not body.step_id:
        raise HTTPException(status_code=400, detail="缺少 step_id")
    s = _step_or_404(body.step_id, uid)
    if s["status"] not in ("running", "pending"):
        return {"ok": True, "already": True}

    db = _db()
    err = (body.error or "执行失败")[:1000]
    # 自动重试一次：retryable 且 attempt < 2 → 回 pending（同一 Agent 下轮重跑）
    if body.retryable and (s["attempt"] or 0) < 2:
        db.update_plan_step(body.step_id, uid, status="pending", claimed_at=None,
                            claimed_by="", error=err, progress=0)
        db.append_plan_run(s["plan_id"], body.step_id, uid, "step_retry",
                           "running", "pending", f"第 {s['step_no']} 步失败，自动重试：{err[:80]}",
                           {"attempt": s["attempt"], "error": err[:200]})
        return {"ok": True, "retry": True}
    db.update_plan_step(body.step_id, uid, status="failed", error=err,
                        finished_at=datetime.now())
    db.append_plan_run(s["plan_id"], body.step_id, uid, "step_failed",
                       "running", "failed", f"第 {s['step_no']} 步失败：{err[:80]}",
                       {"attempt": s["attempt"], "error": err[:200]})
    _finalize_plan(db, s["plan_id"], uid, failed=True, error=err)
    return {"ok": True, "retry": False}


def _finalize_plan(db, plan_id: int, uid: int, failed: bool = False, error: str = "") -> None:
    """重算计划计数器；全 done → plan done；有失败 → plan failed（保留其余步骤可重跑）"""
    steps = db.get_plan_steps(plan_id, uid)
    done = sum(1 for s in steps if s["status"] == "done")
    failed_n = sum(1 for s in steps if s["status"] == "failed")
    pending = sum(1 for s in steps if s["status"] in ("pending", "running"))
    if failed and failed_n > 0:
        db.update_plan(plan_id, uid, status="failed", failed_steps=failed_n,
                       error=(error or "")[:1000], progress=_plan_progress(db, plan_id, uid),
                       message=f"有步骤执行失败（{failed_n}/{len(steps)}）")
        db.append_plan_run(plan_id, None, uid, "plan_failed", "running", "failed",
                           f"计划失败：{error[:80]}")
        return
    if done >= len(steps):
        db.update_plan(plan_id, uid, status="done", done_steps=done,
                       failed_steps=failed_n, progress=100, message="全部步骤完成")
        db.append_plan_run(plan_id, None, uid, "plan_done", "running", "done",
                           f"计划完成（{done} 步）")
        return
    db.update_plan(plan_id, uid, status="running", done_steps=done,
                   failed_steps=failed_n, progress=_plan_progress(db, plan_id, uid),
                   message=f"已完成 {done}/{len(steps)} 步，剩余 {pending} 步")
