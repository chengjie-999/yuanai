# -*- coding: utf-8 -*-
"""A 看板缓存测试 — hash 命中不重跑 / 看板组装 / 端点白名单

运行：pytest test/test_script_dashboard_cache.py -v
纯函数与 registry 测试离线可跑（真实子进程执行临时脚本）；端点测试需要 MySQL。
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from utils.data_path import root_path  # noqa: E402


# ---------------- 辅助：临时脚本（真实子进程，marker 计执行次数） ----------------

def _make_dashboard_script(tmp_path):
    """最小分析脚本：__RESULT__ + __HTML__（含 plotly CDN 引用），每次执行向 marker 写 x"""
    html = tmp_path / "chart.html"
    html.write_text(
        '<html><head><script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script></head>'
        '<body><div id="g1" class="plotly-graph-div"></div>'
        '<script>Plotly.newPlot("g1", [{y:[1,2,3]}], {responsive:true});</script></body></html>',
        encoding="utf-8",
    )
    marker = tmp_path / "marker.txt"
    script = tmp_path / "dash_script.py"
    script.write_text(
        '# -*- coding: utf-8 -*-\n'
        '__script_name__ = "看板缓存测试脚本"\n'
        '__script_desc__ = "A 看板缓存测试用"\n'
        '__script_params__ = [{"name": "n", "type": "int"}]\n'
        'import json, sys\n'
        f'with open({str(marker)!r}, "a", encoding="utf-8") as f:\n'
        '    f.write("x")\n'
        'n = sys.argv[1] if len(sys.argv) > 1 else "0"\n'
        'print("__RESULT__:" + json.dumps({"总用户数": 123, "均值": {"销售额": 45.6}}, ensure_ascii=False))\n'
        f'print("__HTML__:{html.as_posix()}")\n',
        encoding="utf-8",
    )
    return str(script), str(marker), str(html)


def _run_count(marker: str) -> int:
    try:
        with open(marker, encoding="utf-8") as f:
            return len(f.read())
    except OSError:
        return 0


def _dash_key(output: str):
    m = re.search(r'__DASHBOARD__:([0-9a-f]{32})', output)
    return m.group(1) if m else None


# ---------------- 缓存命中：同脚本同参数不重跑 ----------------

def test_cache_hit_skips_rerun(tmp_path, monkeypatch):
    """同脚本同参数二连跑：第二次不启动子进程，直接返回看板缓存"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path, marker, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)

    first = handle.run(n="5")
    assert _run_count(marker) == 1
    key1 = _dash_key(first)
    assert key1, f"首次执行应回传看板 key: {first!r}"
    dash_file = os.path.join(str(tmp_path), "data", "analysis", "dashboards", f"{key1}.html")
    assert os.path.isfile(dash_file), "首次执行应生成看板缓存文件"

    second = handle.run(n="5")
    assert _run_count(marker) == 1, "缓存命中不得重新启动子进程"
    assert "看板已缓存" in second
    assert _dash_key(second) == key1


def test_cache_key_params_change_reruns(tmp_path, monkeypatch):
    """参数变化 → 新 key，重新执行生成新看板"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path, marker, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)

    handle.run(n="5")
    out = handle.run(n="6")
    assert _run_count(marker) == 2
    key2 = _dash_key(out)
    assert key2

    # 参数回到 5 → 命中第一次的缓存，不重跑
    again = handle.run(n="5")
    assert _run_count(marker) == 2
    assert "看板已缓存" in again


def test_cache_key_script_change_reruns(tmp_path, monkeypatch):
    """改脚本一字节 → 新 key，重新执行生成新看板"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path, marker, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)

    out1 = handle.run(n="5")
    key1 = _dash_key(out1)
    with open(script_path, "a", encoding="utf-8") as f:
        f.write("# 修改脚本\n")
    handle._source = ""  # 强制 run 时重读源文件（发现阶段缓存会掩盖改动）

    out2 = handle.run(n="5")
    assert _run_count(marker) == 2
    key2 = _dash_key(out2)
    assert key2 and key2 != key1, "脚本更新必须生成新缓存 key"


# ---------------- 看板组装 ----------------

def test_dashboard_html_assembly(tmp_path, monkeypatch):
    """看板 HTML：KPI 卡（__RESULT__ 拍平）+ 图表内联（cdn script 剥离）+ plotly 内联自包含"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path, _, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)
    out = handle.run(n="5")
    key = _dash_key(out)
    dash_file = os.path.join(str(tmp_path), "data", "analysis", "dashboards", f"{key}.html")
    with open(dash_file, encoding="utf-8") as f:
        content = f.read()

    assert "总用户数" in content and "123" in content      # KPI 卡（嵌套均值_销售额 也应有）
    assert "均值_销售额" in content
    assert "Plotly.newPlot" in content                      # 图表脚本保留
    assert '<script src="https://cdn.plot.ly' not in content  # CDN script 标签已剥离
    assert "window.Plotly" in content                       # plotly.min.js 内联（自包含离线可看）


def test_flatten_kpis():
    from agent.scripts.registry import _flatten_kpis
    data = {"总数": 10, "分组": {"a组": 3, "b组": 4}, "名称": "测试", "开关": True, "空": {}, "列表": [1, 2]}
    out = _flatten_kpis(data)
    pairs = dict(out)
    assert pairs["总数"] == 10
    assert pairs["分组_a组"] == 3 and pairs["分组_b组"] == 4
    assert pairs["名称"] == "测试"
    assert "开关" not in pairs and "列表" not in pairs      # bool/列表跳过


def test_dashboard_html_empty_when_nothing(tmp_path, monkeypatch):
    """无 __RESULT__ 无 __HTML__ 的脚本不生成看板（不写 __DASHBOARD__:{key}）"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script = tmp_path / "plain_script.py"
    script.write_text(
        '__script_name__ = "无产物脚本"\n__script_desc__ = "无"\nprint("hello")\n',
        encoding="utf-8",
    )
    handle = reg._ScriptHandle("无产物脚本", "无", str(script))
    out = handle.run()
    assert _dash_key(out) is None
    assert not os.path.isdir(os.path.join(str(tmp_path), "data", "analysis", "dashboards"))


def test_validate_param_failure_no_cache(tmp_path, monkeypatch):
    """参数校验失败返回错误，不进入缓存路径"""
    import agent.scripts.registry as reg
    monkeypatch.setattr(reg, "PROJECT_ROOT", str(tmp_path))

    script_path, marker, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)
    # 直接构造 handle 不经发现阶段，手动解析 __script_params__ 声明
    reg._parse_params_decl('[{"name": "n", "type": "int"}]', handle)
    out = handle.run(n="not-a-number")
    assert "参数校验失败" in out
    assert _run_count(marker) == 0


# ---------------- 端点白名单（纯函数，离线） ----------------

def test_safe_dashboard_key_whitelist():
    from api.v1.data.router import _safe_dashboard_key
    assert _safe_dashboard_key("0" * 32) is True
    assert _safe_dashboard_key("a1b2c3d4e5f60718293a4b5c6d7e8f90") is True
    for bad in ["abc", "A1B2C3D4E5F60718293A4B5C6D7E8F90", "0" * 31, "0" * 33,
                "0" * 32 + ".html", "../etc/passwd", "0" * 16 + "/" + "0" * 16, "", None]:
        assert _safe_dashboard_key(bad or "") is False, f"应拒绝: {bad!r}"


# ---------------- 端点测试（需要 MySQL；不可用则跳过） ----------------

def _db_or_skip():
    try:
        from db.session import get_db
        return get_db()
    except Exception as e:
        pytest.skip(f"MySQL 不可用: {type(e).__name__}")


@pytest.fixture(scope="module")
def db():
    return _db_or_skip()


def test_dashboard_html_endpoint(client, db):
    """dashboard-html 端点：非法 key 404 / 不存在 404 / 存在 200 + 沙箱头（sse token 鉴权）"""
    from db.session import User
    from api.v1.auth.utils import create_token

    sess = db.Session()
    try:
        old = sess.query(User).filter_by(username="__dash_board_test__").first()
        if old:
            sess.delete(old)
            sess.commit()
    finally:
        sess.close()

    r = db.register_user("__dash_board_test__", "test123")
    assert "error" not in r, r
    jwt = create_token(r["id"], "user")

    def mint_sse():
        resp = client.get("/api/v1/auth/sse-token",
                          headers={"Authorization": f"Bearer {jwt}"})
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]

    ddir = os.path.join(root_path(), "data", "analysis", "dashboards")
    os.makedirs(ddir, exist_ok=True)
    good_key = "f" * 32
    fpath = os.path.join(ddir, f"{good_key}.html")
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("<html><body>dashboard</body></html>")

        for bad in ("abc", "A" * 32, "0" * 31):
            resp = client.get(f"/api/v1/data/dashboard-html/{bad}", params={"token": mint_sse()})
            assert resp.status_code == 404, bad

        resp = client.get(f"/api/v1/data/dashboard-html/{'0' * 32}", params={"token": mint_sse()})
        assert resp.status_code == 404, "不存在的 key 应 404"

        resp = client.get(f"/api/v1/data/dashboard-html/{good_key}", params={"token": mint_sse()})
        assert resp.status_code == 200
        assert "dashboard" in resp.text
        assert "sandbox allow-scripts" in resp.headers.get("content-security-policy", "")
        assert "nosniff" in resp.headers.get("x-content-type-options", "")
    finally:
        if os.path.exists(fpath):
            os.remove(fpath)
        sess = db.Session()
        try:
            u = sess.query(User).filter_by(id=r["id"]).first()
            if u:
                sess.delete(u)
                sess.commit()
        finally:
            sess.close()


# ---------------- B1 挂账：数据集指纹 + 停止联动 ----------------

def test_cache_key_includes_dataset_fingerprint(tmp_path, monkeypatch):
    """数据集文件内容变化（同名覆盖）→ 看板 key 变化 → 旧看板自然失效"""
    import agent.scripts.registry as reg
    import db.session as dbs

    ds_file = tmp_path / "ds.csv"
    ds_file.write_text("aaa", encoding="utf-8")

    class FakeDB:
        def get_dataset(self, ds_id):
            return {"file_path": str(ds_file)}

    monkeypatch.setattr(dbs, "get_db", lambda: FakeDB())

    script_path, _, _ = _make_dashboard_script(tmp_path)
    handle = reg._ScriptHandle("看板缓存测试脚本", "测试", script_path)

    k1 = handle._dashboard_cache_key({"dataset_id": 1, "n": "5"})
    ds_file.write_text("bbbb", encoding="utf-8")  # 内容与大小变化（模拟上传覆盖）
    k2 = handle._dashboard_cache_key({"dataset_id": 1, "n": "5"})
    assert k1 and k2 and k1 != k2, "数据集文件变化后 key 必须变化"

    k3 = handle._dashboard_cache_key({"dataset_id": 1, "n": "5"})
    assert k3 == k2, "文件未变时 key 应稳定"


def test_cancel_running_kills_proc():
    """B1-12：cancel_running 按 request_id 只终止所属子进程"""
    import agent.scripts.registry as reg
    import subprocess

    p1 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    p2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with reg._procs_lock:
        reg._running_procs[id(p1)] = p1
        reg._proc_rid[id(p1)] = "req-a"
        reg._running_procs[id(p2)] = p2
        reg._proc_rid[id(p2)] = "req-b"

    try:
        n = reg.cancel_running("req-a")
        assert n == 1
        assert p1.wait(timeout=10) is not None, "被标记的进程应被终止"
        assert p2.poll() is None, "其他请求的子进程不应被波及"
    finally:
        for p in (p1, p2):
            if p.poll() is None:
                p.kill()
            p.wait()
        reg._cleanup_proc(id(p1))
        reg._cleanup_proc(id(p2))


if __name__ == "__main__":
    print("测试入口：pytest test/test_script_dashboard_cache.py -v")
