"""计划执行器 — 本地 Agent 拉取云端计划队列、分步执行、回传进度与结果

产品闭环第③段「电脑执行」：云端建计划（draft）→ 用户说「执行」→
queued → 本机 PlanExecutor 轮询 /agent/plan/pull 认领步骤 → 执行 →
progress/done/failed 上报。融合后（2026-10-14）：步骤绑定脚本名时
registry.run 零 LLM 直跑；未绑定（云端 fallback 建的步骤）bind_tools
一次 LLM 现场选脚本。断点续跑：认领超时由云端看门狗重置，本机崩溃后
重启自动续跑（云端是唯一真相源，本地不落状态文件）。

安全边界：
- skill 白名单 PLAN_SKILLS（analysis/collection，automation 挂账）
- 托盘开关过滤（enabled_skills）；脚本参数校验沿用 ScriptRegistry
- 确定性失败（选不出脚本/参数校验失败）不重试，其余自动重试 1 次
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from yuanai_core.pure.plan import PLAN_SKILLS, build_step_prompt, parse_step_output

logger = logging.getLogger(__name__)

POLL_SECONDS = 10            # 空转轮询间隔
REPORT_RETRY = 3             # 上报失败重试次数
REPORT_RETRY_DELAY_S = 5
MAX_STEPS_PER_ROUND = 5      # 单轮最多执行步数（防一轮霸占）
PROGRESS_MIN_INTERVAL_S = 3  # 进度上报节流

# 确定性失败前缀 → 不重试（重试同结果只烧 token）。
# 实测补充：registry 的「脚本执行失败 (exit=1)」与 builtin 的「分析失败」曾被当成
# 成功结果（步骤标 done 但内容是崩溃日志）——失败前缀必须覆盖这些输出。
_NON_RETRYABLE_PREFIXES = ("无法处理", "参数校验失败", "未知脚本", "无法解析意图",
                           "未知内置操作", "脚本执行失败", "分析失败", "读取失败",
                           "转换失败", "执行失败", "已停止")


class PlanExecutor:
    """轮询执行器（后台线程驱动；run_once 可单步调用便于测试/验证脚本）"""

    def __init__(self, agent_id: str, agent_secret: str, server_base: str,
                 enabled_skills=None, status_cb=None):
        self.agent_id = str(agent_id)
        self.agent_secret = str(agent_secret or "")
        self.server_base = str(server_base).rstrip("/")
        # list 或 callable（托盘开关实时读取用）；None = 不限制
        self.enabled_skills = list(enabled_skills) if (enabled_skills is not None
                                                       and not callable(enabled_skills)) else enabled_skills
        self.status_cb = status_cb  # callback(dict) 状态上报（托盘徽标预留）
        self._stop = threading.Event()
        self._running = False
        self._last_progress: dict = {}  # step_id -> 上次进度上报时间戳

    # ---------------- HTTP（Agent 设备凭据） ----------------

    def _http(self, path: str, payload: dict = None, timeout: int = 60) -> dict:
        url = f"{self.server_base}/api/v1/agent/plan{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("X-Agent-Id", self.agent_id)
        req.add_header("X-Agent-Secret", self.agent_secret)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}

    def _report(self, path: str, payload: dict) -> bool:
        """上报（3 次重试）；最终失败返回 False——步骤停在 running 由看门狗兜底重置"""
        for i in range(REPORT_RETRY):
            try:
                self._http(path, payload, timeout=30)
                return True
            except Exception as e:
                logger.warning("计划上报失败 %s (%d/%d): %s", path, i + 1, REPORT_RETRY, e)
                if i < REPORT_RETRY - 1:
                    time.sleep(REPORT_RETRY_DELAY_S)
        return False

    # ---------------- 执行 ----------------

    def _get_registry(self, skill: str):
        """按 skill 取脚本注册表（融合后无子 Agent；脚本工具/直跑都走 registry）"""
        from agent.scripts.tools import get_registry
        return get_registry(skill)

    def _step_params(self, step: dict) -> dict:
        """步骤参数统一取值：pull 返回的是 params_json（字符串），直接透传脚本"""
        p = step.get("params")
        if isinstance(p, dict):
            return p
        try:
            p = json.loads(step.get("params_json") or "{}")
        except Exception:
            p = {}
        return p if isinstance(p, dict) else {}

    def _run_fallback_llm(self, skill: str, plan: dict, step: dict, prev: list,
                          progress_cb) -> tuple:
        """无绑定脚本的步骤：bind_tools 一次 LLM 调用现场选脚本（兜底路径）"""
        from langchain_core.messages import HumanMessage, SystemMessage
        from yuanai_core.core.lc import get_llm
        from skills import skill_registry
        from agent.scripts.tools import build_script_tools

        registry = self._get_registry(skill)
        if not registry:
            return "failed_noretry", f"技能未注册: {skill}"
        cfg = skill_registry.get(skill)
        tools = build_script_tools(registry, skill=skill, progress_cb=progress_cb)
        if not tools:
            return "failed_noretry", f"技能 {skill} 无可用脚本"
        llm = get_llm(cfg.model if cfg else "doubao-seed-2-0-lite", temperature=0)
        try:
            msg = llm.bind_tools(tools).invoke([
                SystemMessage(content=(cfg.system_prompt if cfg else "") or
                              "你是计划步骤执行器：从可用脚本工具中选最合适的一个并直接调用；确实无法完成时不要调用工具，只说明原因。"),
                HumanMessage(content=build_step_prompt(plan, step, prev)),
            ])
        except Exception as e:
            return "failed", f"脚本选择失败 {type(e).__name__}: {str(e)[:200]}"
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            return "failed_noretry", f"无法处理：未能从可用脚本中选出（{str(getattr(msg, 'content', ''))[:200]}）"
        tc = tool_calls[0]
        by_name = {t.name: t for t in tools}
        tool = by_name.get(tc.get("name", ""))
        if not tool:
            return "failed_noretry", f"无法处理：选中的工具不存在（{tc.get('name')}）"
        raw = str(tool.invoke(tc.get("args") or {}))
        return "done_script", raw

    def _execute_step(self, plan: dict, step: dict, prev: list) -> tuple:
        """执行单步 → ("done", payload) / ("failed", err) / ("failed_noretry", err)

        融合后（2026-10-14）：step.script 存在 → registry.run 零 LLM 直跑；
        无 script（云端 fallback 建的步骤）→ bind_tools 一次 LLM 现场选脚本。
        """
        skill = step.get("skill") or "analysis"
        if skill not in PLAN_SKILLS:
            return "failed_noretry", f"skill 不在执行白名单: {skill}"
        enabled = self.enabled_skills() if callable(self.enabled_skills) else self.enabled_skills
        if enabled is not None and skill not in enabled:
            return "failed_noretry", f"该技能（{skill}）在本机托盘被关闭，开启后重跑失败步骤即可"
        registry = self._get_registry(skill)
        if not registry:
            return "failed_noretry", f"技能未注册: {skill}"

        params = self._step_params(step)
        step_id = step["id"]

        def progress_cb(current, total, message):
            if not current:
                return
            if time.time() - self._last_progress.get(step_id, 0) < PROGRESS_MIN_INTERVAL_S:
                return
            self._last_progress[step_id] = time.time()
            self._report("/progress", {"step_id": step_id, "current": int(current),
                                       "total": int(total), "message": str(message)[:500]})

        bound = str(step.get("script") or "").strip()
        script_used = ""
        if bound:
            resolved = registry.resolve(bound)
            if not resolved:
                # 绑定脚本在本机不存在（跨机漂移/脚本被删）→ 降级现场选（plan_runs 标 fallback）
                logger.warning("步骤 %s 绑定脚本不存在（%s），降级现场选", step_id, bound)
                state, raw = self._run_fallback_llm(skill, plan, step, prev, progress_cb)
                if state != "done_script":
                    return state, raw
            else:
                try:
                    raw = registry.run(resolved, params, progress_cb=progress_cb)
                except Exception as e:
                    return "failed", f"执行异常 {type(e).__name__}: {str(e)[:300]}"
                script_used = resolved
        else:
            state, raw = self._run_fallback_llm(skill, plan, step, prev, progress_cb)
            if state != "done_script":
                return state, raw

        err = str(raw or "").strip()
        # 2026-10-19 修复：registry 失败带 __ERROR__: 前缀，此前未剥离导致
        # 前缀匹配全miss → 失败步骤被剥掉标记后当 done 上报（数据正确性 bug）
        is_protocol_error = err.startswith("__ERROR__:")
        if is_protocol_error:
            err = err[len("__ERROR__:"):].strip()
        for prefix in _NON_RETRYABLE_PREFIXES:
            if err.startswith(prefix):
                return "failed_noretry", err[:500]
        if is_protocol_error:
            # 协议错误其余类型（脚本执行异常/超时等）按可重试失败处理
            return "failed", err[:500]
        parsed = parse_step_output(raw)
        if not parsed["text"].strip() and not parsed["blocks"]:
            return "failed", "执行无有效输出"
        return "done", {"result_json": {"text": parsed["text"], "blocks": parsed["blocks"],
                                        "truncated": parsed["truncated"]},
                        "summary": parsed["text"][:120],
                        "script": script_used or bound}

    # ---------------- 循环 ----------------

    def run_once(self) -> dict:
        """单轮：拉取 → 执行 → 上报；返回本轮摘要"""
        try:
            r = self._http("/pull", {}, timeout=30)
        except Exception as e:
            logger.warning("计划拉取失败: %s", type(e).__name__)
            return {"idle": True, "error": str(e)}
        if not r or r.get("empty"):
            return {"idle": True}
        plan, step, prev = r.get("plan") or {}, r.get("step") or {}, r.get("prev") or []
        state, payload = self._execute_step(plan, step, prev)
        if state == "done":
            ok = self._report("/step-done", {"step_id": step["id"], **payload})
            if self.status_cb:
                try:
                    self.status_cb({"step": step.get("step_no"), "status": "done", "plan": plan.get("id")})
                except Exception:
                    pass
            return {"executed": 1, "reported": ok}
        retryable = state == "failed"
        ok = self._report("/step-failed", {"step_id": step["id"], "error": payload,
                                           "retryable": retryable})
        return {"executed": 0, "failed": payload, "retryable": retryable, "reported": ok}

    def run_loop(self, stop_flag: threading.Event = None, poll: int = POLL_SECONDS) -> None:
        """后台循环（1s 切片 + stop_flag；空闲时每 poll 秒拉取一次）"""
        stop = stop_flag or self._stop
        self._running = True
        last = 0.0
        while not stop.is_set():
            now = time.time()
            if now - last >= poll:
                last = now
                try:
                    for _ in range(MAX_STEPS_PER_ROUND):
                        if stop.is_set():
                            break
                        if self.run_once().get("idle"):
                            break
                except Exception as e:
                    logger.exception("计划执行轮异常: %s", e)
            if stop.is_set():
                break
            time.sleep(1)
        self._running = False

    def stop(self) -> None:
        self._stop.set()
