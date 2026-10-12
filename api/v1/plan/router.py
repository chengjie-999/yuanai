"""计划闭环用户侧 API（JWT）— 手机端计划页 /chat/plan 的数据源

- GET  /plan/list                 计划卡列表（不含大字段）
- GET  /plan/{pid}                详情（plan + steps + runs；读时跑看门狗）
- POST /plan/{pid}/execute        触发执行 / 重跑失败步（body: {step_ids: []}）
- DELETE /plan/{pid}              删除（仅 draft/done/failed）
- POST /plan                      手动建档（兜底 / 测试；对话创建走工具）
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.v1.middleware import get_user_id
from api.v1.plan import store

router = APIRouter(prefix="/api/v1/plan", tags=["plan"])


def _uid(request: Request) -> int:
    uid = get_user_id(request)
    if not uid:
        raise HTTPException(status_code=401, detail="未登录")
    return uid


class CreatePlanBody(BaseModel):
    title: str = ""
    goal: str = ""
    steps: list = []
    session_id: str = ""


class ExecuteBody(BaseModel):
    step_ids: list = []


@router.get("/list")
def list_plans(request: Request, status: str = "", limit: int = 50):
    uid = _uid(request)
    return {"plans": store._db().list_plans(uid, status=status or None,
                                            limit=min(max(limit, 1), 100))}


@router.get("/{plan_id}")
def get_plan_detail(request: Request, plan_id: int):
    uid = _uid(request)
    plan = store._require_plan(plan_id, uid)
    store.apply_plan_watchdog(plan_id, uid)
    plan = store._db().get_plan(plan_id, uid)
    steps = [store.step_dict(s) for s in store._db().get_plan_steps(plan_id, uid)]
    runs = store._db().list_plan_runs(plan_id, uid, limit=100)
    plan["steps"] = steps
    plan["runs"] = runs
    plan["agent_online"] = store.plan_agent_online(uid)
    return plan


@router.post("/{plan_id}/execute")
def execute(request: Request, plan_id: int, body: ExecuteBody):
    uid = _uid(request)
    return store.execute_plan(plan_id, uid, body.step_ids or None)


@router.delete("/{plan_id}")
def delete_plan(request: Request, plan_id: int):
    uid = _uid(request)
    store._require_plan(plan_id, uid)
    if not store._db().delete_plan_cascade(plan_id, uid):
        raise HTTPException(status_code=409, detail="执行中的计划不能删除")
    return {"ok": True}


@router.post("")
def create_plan(request: Request, body: CreatePlanBody):
    uid = _uid(request)
    return store.create_plan_for_user(uid, body.title, body.goal, body.steps,
                                      body.session_id)
