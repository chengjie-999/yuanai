TOOL_CATEGORY = "plan"

"""计划工具 — create_plan / execute_plan / get_plan_status（双路径）

- 云端进程（统筹回退/云端直连 LLM）：直连 DB 层
- 本地 Agent 进程：经 /api/v1/agent/plan HTTP（设备凭据，身份由云端推导）
判定复用 user_memory 的 _memory_path/_agent_http（2026-10-12 修复的进程
身份判定——复制一份必埋第二处漂移，见 CLAUDE.md 教训）。
"""
import logging

from langchain_core.tools import tool
from yuanai_core.rag import current_user_id, current_session_id
from yuanai_core.tools.user_memory import _memory_path, _agent_http

logger = logging.getLogger(__name__)


def _plan_call(path: str, payload: dict) -> dict:
    """双路径：本地 Agent → HTTP；云端进程 → 直连 db/store"""
    if _memory_path() == "http":
        return _agent_http("/plan" + path, "POST", payload)
    return _plan_call_direct(path, payload)


def _plan_call_direct(path: str, payload: dict) -> dict:
    from db.session import get_db
    from yuanai_core.pure.plan import validate_steps, validate_title_goal

    db = get_db()
    uid = current_user_id.get() or int(payload.get("user_id") or 0)
    if not uid:
        return {"ok": False, "detail": "无法确定用户身份"}
    if path == "/create":
        title, goal, err = validate_title_goal(payload.get("title", ""), payload.get("goal", ""))
        if err:
            return {"ok": False, "detail": err}
        steps, err = validate_steps(payload.get("steps", []))
        if err:
            return {"ok": False, "detail": err}
        r = db.create_plan(uid, title, goal, steps,
                           session_id=payload.get("session_id", ""))
        if not r.get("ok"):
            return r
        return {"ok": True, "plan_id": r["plan_id"]}
    if path == "/execute":
        from api.v1.plan import store
        try:
            pid = store.resolve_plan_id(int(payload.get("plan_id") or 0), uid)
            return store.execute_plan(pid, uid)
        except Exception as e:
            return {"ok": False, "detail": getattr(e, "detail", str(e))}
    if path == "/status":
        from api.v1.plan import store
        return {"ok": True, "plan": store.format_plan_status(uid, int(payload.get("plan_id") or 0))}
    return {"ok": False, "detail": f"不支持的操作 {path}"}


@tool
def create_plan(title: str, goal: str, steps: str) -> str:
    """为用户创建可执行计划（手机定计划、电脑执行，只建草稿不自动执行）。
    title: 计划标题（≤100 字）
    goal: 用户的原始目标，原样记录
    steps: JSON 数组字符串，1-8 步。每项 {"skill":"analysis|collection","desc":"这一步做什么（自包含描述：执行时看不到对话历史，缺 URL/数据集 id 要写明或先问用户）","params":{...可选参数}}
    规则：只写意图与参数、不要写脚本名（本机执行时自动选脚本）；数据采集在前、分析在后；信息不足（缺 URL/数据集 id/列名）先在对话里问用户，不要猜。
    创建成功后向用户复述步骤清单，并说明：说「执行」才会开始，电脑开机且小元 Agent 在线时自动执行。"""
    from yuanai_core.pure.plan import validate_steps, validate_title_goal
    uid = current_user_id.get()
    title, goal, err = validate_title_goal(title, goal)
    if err:
        return f"标题不合法：{err}"
    steps_list, err = validate_steps(steps)
    if err:
        return f"步骤不合法：{err}"
    r = _plan_call("/create", {"user_id": uid, "title": title, "goal": goal,
                               "steps": steps_list,
                               "session_id": current_session_id.get()})
    if not r.get("ok"):
        return f"创建计划失败：{r.get('detail', '未知错误')}"
    lines = [f"计划 #{r['plan_id']}「{title}」已创建（{len(steps_list)} 步，草稿状态，尚未执行）"]
    for i, s in enumerate(steps_list, 1):
        lines.append(f"{i}. [{s['skill']}] {s['desc'][:60]}")
    lines.append("等用户说「执行」时调用 execute_plan 加入队列；不要自动执行。")
    return "\n".join(lines)


@tool
def execute_plan(plan_id: int = 0) -> str:
    """把计划加入执行队列，用户的电脑会自动拉取执行。plan_id: 0 = 最近一个草稿计划。
    只有用户明确说「执行/开始执行/跑这个计划」时才调用；计划创建后不要主动调用。"""
    uid = current_user_id.get()
    r = _plan_call("/execute", {"user_id": uid, "plan_id": int(plan_id or 0)})
    if not r.get("ok"):
        return f"执行失败：{r.get('detail', '未知错误')}"
    if r.get("already"):
        return "该计划已在执行队列中，电脑上线后会自动开始。"
    if not r.get("agent_online"):
        return ("计划已加入队列。当前你的电脑（本地小元 Agent）未连接——"
                "电脑开机且小元 Agent 在线后会自动开始执行，也可以到「计划」页查看进度。")
    return "计划已加入队列，你的电脑正在准备执行，可到「计划」页查看进度。"


@tool
def get_plan_status(plan_id: int = 0) -> str:
    """查询计划状态与各步骤进度。plan_id: 0 = 最近一个计划（用户问「计划怎么样了」时用）"""
    uid = current_user_id.get()
    r = _plan_call("/status", {"user_id": uid, "plan_id": int(plan_id or 0)})
    if not r.get("ok"):
        return f"查询失败：{r.get('detail', '未知错误')}"
    return r["plan"]
