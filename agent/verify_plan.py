# -*- coding: utf-8 -*-
"""计划闭环验证脚本 — 离线断言 + 在线冒烟（照 verify_vault_sync 骨架）

用法：
  python -m agent.verify_plan              # 离线（零网络零 MySQL）
  python -m agent.verify_plan --online     # 追加在线冒烟（/health + /plan/pull）

覆盖：
  === 1. 纯函数 ===
    validate_steps（skill 白名单/步数/参数类型/协议注入防护）
    build_step_prompt（自包含：目标/参数/前序摘要）
    parse_step_output（__DASHBOARD__ blocks/剥标记/截断）
  === 2. 执行器（mock HTTP 驱动真实 run_once）===
    拉取→执行→step-done 上报 payload 正确（含 dashboard blocks 解析）
    skill 白名单外步骤拒绝执行且不重试
    确定性失败（无法处理）→ retryable=False；异常 → retryable=True
  === 3. 状态机（在线时，需 MySQL）===
    draft → execute(queued) → pull 认领(running) → step-done → 计划 done
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

FAILS = 0
CHECKS = 0


def check(name, cond, detail=""):
    global FAILS, CHECKS
    CHECKS += 1
    if cond:
        print(f"  OK  {name}")
    else:
        FAILS += 1
        print(f"  FAIL {name} {detail}")


# ==================== 1. 纯函数 ====================

def offline_pure():
    print("=== 1. 纯函数 ===")
    from yuanai_core.pure.plan import validate_steps, build_step_prompt, parse_step_output

    steps, err = validate_steps(json.dumps([
        {"skill": "collection", "desc": "抓取数据", "params": {"url": "https://x.com"}},
        {"skill": "analysis", "desc": "统计分析", "params": {"dataset_id": 1}},
    ]))
    check("validate_steps 合法步骤通过", not err and len(steps) == 2, err)
    check("automation 白名单拦截", validate_steps(
        [{"skill": "automation", "desc": "开浏览器"}])[1] != "")
    check("协议注入拦截", validate_steps(
        [{"skill": "analysis", "desc": "__DASHBOARD__:/etc/x"}])[1] != "")

    prompt = build_step_prompt(
        {"title": "每日数据", "goal": "抓取并分析", "total_steps": 2},
        {"step_no": 2, "desc": "做统计", "params": {"dataset_id": 5}},
        [{"step_no": 1, "desc": "抓取", "summary": "抓到100行"}])
    check("prompt 自包含（目标/参数/前序摘要）",
          all(x in prompt for x in ("每日数据", "dataset_id=5", "抓到100行", "不要询问确认")))

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"kpi": [{"label": "行数", "value": 100}]}, f)
        dash_path = f.name
    try:
        out = parse_step_output(f"完成\n__DASHBOARD__:{dash_path}\n结论\n__HTML__URL:/x")
        check("parse 读 dashboard blocks", out["blocks"]["kpi"][0]["value"] == 100)
        check("parse 剥协议标记", "__DASHBOARD__" not in out["text"] and "__HTML__URL" not in out["text"])
    finally:
        os.unlink(dash_path)

    # P0 回归：registry.run 接受 progress_cb（曾抛 TypeError 炸委派路径）
    from agent.scripts.registry import ScriptRegistry
    r = ScriptRegistry("agent/datanalysis/scripts")
    check("registry.run 接受 progress_cb（P0 回归）",
          "未知脚本" in r.run("不存在的脚本", None, progress_cb=lambda c, t, m: None))


# ==================== 2. 执行器（mock HTTP） ====================

def offline_executor():
    print("=== 2. 执行器（mock HTTP 驱动真实 run_once）===")
    from agent.plan_executor import PlanExecutor

    class FakeAgent:
        def __init__(self, output="结果文本", exc=None):
            self._output, self._exc, self.last_dispatch = output, exc, {"script": "测试脚本", "params": {}}

        def run(self, prompt, progress_cb=None):
            if self._exc:
                raise self._exc
            return self._output

    PLAN = {"id": 1, "title": "测试", "goal": "抓取并分析", "total_steps": 1, "status": "running"}
    STEP = {"id": 11, "plan_id": 1, "step_no": 1, "skill": "analysis",
            "desc": "做统计", "params": {"dataset_id": 5}}

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"kpi": [{"label": "行数", "value": 100}]}, f)
        dash_path = f.name
    try:
        def make_http(step, calls):
            def fake_http(path, payload=None, timeout=60):
                if path == "/pull":
                    return {"plan": PLAN, "step": step, "prev": []}
                calls.append((path, payload))
                return {"ok": True}
            return fake_http

        # 用例 A：正常完成 → step-done payload 正确
        ex = PlanExecutor("1", "s", "http://localhost:8000")
        ex._get_agent = lambda skill: FakeAgent(output=f"完成\n__DASHBOARD__:{dash_path}\n结论")
        calls = []
        ex._http = make_http(STEP, calls)
        r = ex.run_once()
        check("执行完成并上报 step-done", r["executed"] == 1 and r["reported"] is True, str(r))
        done_payload = calls[-1][1] if calls else {}
        check("done payload 含 blocks/script/summary",
              done_payload.get("result_json", {}).get("blocks", {}).get("kpi", [{}])[0].get("value") == 100
              and done_payload.get("script") == "测试脚本")

        # 用例 B：白名单外 skill → 拒绝且不重试
        ex2 = PlanExecutor("1", "s", "http://localhost:8000")
        calls2 = []
        ex2._http = make_http({**STEP, "skill": "automation"}, calls2)
        r2 = ex2.run_once()
        check("automation 步骤拒绝（不重试）", r2["retryable"] is False
              and "白名单" in calls2[-1][1]["error"])

        # 用例 C：确定性失败 → 不重试
        ex3 = PlanExecutor("1", "s", "http://localhost:8000")
        ex3._get_agent = lambda skill: FakeAgent(output="无法处理：缺少 URL")
        calls3 = []
        ex3._http = make_http(STEP, calls3)
        r3 = ex3.run_once()
        check("确定性失败不重试", r3["retryable"] is False)

        # 用例 D：执行异常 → 可重试
        ex4 = PlanExecutor("1", "s", "http://localhost:8000")
        ex4._get_agent = lambda skill: FakeAgent(exc=TimeoutError("超时"))
        calls4 = []
        ex4._http = make_http(STEP, calls4)
        r4 = ex4.run_once()
        check("异常可重试", r4["retryable"] is True)
    finally:
        os.unlink(dash_path)


# ==================== 3. 状态机（在线，需 MySQL） ====================

def online_state_machine():
    print("=== 3. 状态机（在线）===")
    from db.session import get_db, User
    db = get_db()
    u = db.register_user("__verify_plan__", "test123")
    uid = u["id"]
    try:
        r = db.create_plan(uid, "验证计划", "全链验证", [
            {"skill": "analysis", "desc": "一步验证", "params": {}}])
        check("创建计划（draft）", r.get("ok") is True, str(r))
        pid = r["plan_id"]
        from api.v1.plan import store
        store.execute_plan(pid, uid)
        check("execute → queued", db.get_plan(pid, uid)["status"] == "queued")
        claimed = db.claim_next_plan_step(uid, "verify-dev")
        check("pull 认领 → running", claimed and claimed["step"]["status"] == "running")
        sid = claimed["step"]["id"]
        db.update_plan_step(sid, uid, status="done", progress=100, result_json='{"text": "ok"}')
        db.append_plan_run(pid, sid, uid, "step_done", "running", "done", "步骤完成",
                           {"script": "verify"})  # 等价 /step-done 端点的事件落账
        from api.v1.agent.plan_sync import _finalize_plan
        _finalize_plan(db, pid, uid)
        check("step-done → 计划 done", db.get_plan(pid, uid)["status"] == "done")
        runs = [x["event"] for x in db.list_plan_runs(pid, uid)]
        check("事件溯源（created/queued/claimed/step_done/plan_done）",
              all(e in runs for e in ("created", "queued", "claimed", "step_done", "plan_done")))
        db.delete_plan_cascade(pid, uid)
    finally:
        with db.session() as sess:
            x = sess.query(User).filter_by(id=uid).first()
            if x:
                sess.delete(x)
            sess.commit()
def online_smoke():
    print("=== 在线冒烟 ===")
    import urllib.request
    identity = {}
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "agent_identity.json"),
                  encoding="utf-8") as f:
            identity = json.load(f)
    except OSError:
        pass
    server = (identity.get("server_url") or "http://localhost:8000").replace("ws://", "http://").replace("wss://", "https://")
    try:
        with urllib.request.urlopen(f"{server}/health", timeout=5) as resp:
            check("/health 200", resp.status == 200)
    except Exception as e:
        check("/health 200", False, str(e))
        return
    if identity.get("agent_id"):
        req = urllib.request.Request(f"{server}/api/v1/agent/plan/pull", data=b"{}",
                                     headers={"Content-Type": "application/json",
                                              "X-Agent-Id": str(identity["agent_id"]),
                                              "X-Agent-Secret": str(identity.get("agent_secret", ""))},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                check("/plan/pull 鉴权通过（empty 也算通过）", "empty" in body or "step" in body)
        except urllib.error.HTTPError as e:
            check("/plan/pull 鉴权通过", False, f"HTTP {e.code}: {e.read()[:100]}")
        except Exception as e:
            check("/plan/pull 鉴权通过", False, str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="追加在线冒烟（/health + /plan/pull）")
    args = ap.parse_args()

    offline_pure()
    offline_executor()
    if args.online:
        online_smoke()
        try:
            online_state_machine()
        except Exception as e:
            check("状态机（MySQL 可用则跑）", False, f"{type(e).__name__}: {e}")

    print(f"\n结果：{CHECKS - FAILS}/{CHECKS} 通过")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
