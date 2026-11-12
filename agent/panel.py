# -*- coding: utf-8 -*-
"""本地设置面板（2026-11-11 用户拍板：托盘原生弹窗老旧，网页化对齐网站风格）

托盘进程内置本地 HTTP 服务（127.0.0.1 随机端口，stdlib http.server 零新依赖），
提供网站风格的设置面板：状态 / Agent 开关 / Claude Code 工作目录 / 重新注册
（网页输码替代老旧 InputBox）/ 检查更新 / 退出。安全面：只绑 127.0.0.1——
本机任意进程本就同信任级（可读数据目录），无鉴权与本地服务惯例一致。

目录选择是唯一保留的原生件：浏览器拿不到目录绝对路径，网页按钮 → 托盘进程
跑 PowerShell FolderBrowserDialog（pick_directory）。
"""
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("agent.panel")

AGENT_VERSION = getattr(__import__("agent.tray", fromlist=["AGENT_VERSION"]), "AGENT_VERSION", "")

_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小元AI Agent 设置</title>
<style>
  :root {
    --bg-primary: #f8fafc; --bg-secondary: #f1f5f9; --bg-input: #ffffff;
    --bg-tertiary: #e2e8f0; --text-primary: #0f172a; --text-secondary: #475569;
    --text-muted: #64748b; --border: #cbd5e1; --border-light: #e2e8f0;
    --accent: #2563eb; --accent-light: rgba(37,99,235,.09);
    --accent-gradient: linear-gradient(135deg, #3b82f6, #2563eb, #1d4ed8);
    --danger: #dc2626; --success: #16a34a; --warning: #d97706;
    --shadow-sm: 0 1px 2px rgba(15,23,42,.05);
    --shadow-md: 0 4px 16px rgba(15,23,42,.10);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg-primary: #0b1220; --bg-secondary: #101a2c; --bg-input: #1b2942;
      --bg-tertiary: #16233a; --text-primary: #e2e8f0; --text-secondary: #94a3b8;
      --text-muted: #64748b; --border: #2b3b56; --border-light: #1f2c44;
      --accent: #60a5fa; --accent-light: rgba(96,165,250,.13);
      --accent-gradient: linear-gradient(135deg, #60a5fa, #3b82f6, #2563eb);
      --danger: #f87171; --success: #4ade80; --warning: #fbbf24;
      --shadow-sm: 0 1px 2px rgba(0,0,0,.30);
      --shadow-md: 0 4px 16px rgba(0,0,0,.50);
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'PingFang SC','Microsoft YaHei',sans-serif;
    background: var(--bg-primary); color: var(--text-primary);
    min-height: 100vh; padding: 24px 16px 48px;
  }
  .wrap { max-width: 640px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
  .head { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
  .mascot { width: 44px; height: 44px; border-radius: 50%; background: var(--accent-gradient);
            box-shadow: 0 0 18px rgba(59,130,246,.35); flex-shrink: 0;
            display: flex; align-items: center; justify-content: center; }
  .mascot-core { width: 12px; height: 12px; border-radius: 50%; background: rgba(255,255,255,.9);
                 animation: breathe 3s ease-in-out infinite; }
  @keyframes breathe { 0%,100% { transform: scale(1); opacity:.85 } 50% { transform: scale(1.25); opacity:1 } }
  h1 { font-size: 20px; font-weight: 700; }
  .sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .card { background: var(--bg-input); border: 1px solid var(--border-light);
          border-radius: 14px; padding: 16px 18px; box-shadow: var(--shadow-sm); }
  .card h2 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; }
  .row + .row { border-top: 1px solid var(--border-light); }
  .row .label { font-size: 13px; }
  .row .hint { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
  .row .value { font-size: 12px; color: var(--text-secondary); max-width: 60%; overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap; text-align: right; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
  .dot.online { background: var(--success); } .dot.offline { background: var(--text-muted); }
  .dot.working { background: var(--warning); }
  /* 开关（网页化 toggle） */
  .switch { position: relative; width: 40px; height: 22px; flex-shrink: 0; cursor: pointer; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider { position: absolute; inset: 0; background: var(--bg-tertiary); border-radius: 999px;
            transition: background .15s; }
  .slider:before { content: ''; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px;
                   background: #fff; border-radius: 50%; transition: transform .15s;
                   box-shadow: 0 1px 3px rgba(0,0,0,.25); }
  .switch input:checked + .slider { background: var(--accent); }
  .switch input:checked + .slider:before { transform: translateX(18px); }
  .btn { border: none; border-radius: 6px; padding: 7px 14px; font-size: 13px; font-weight: 600;
         cursor: pointer; transition: opacity .15s; font-family: inherit; }
  .btn:disabled { opacity: .5; cursor: default; }
  .btn-primary { background: var(--accent-gradient); color: #fff; }
  .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-primary); }
  .btn-danger { background: transparent; border: 1px solid var(--danger); color: var(--danger); }
  .input { width: 100%; border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px;
           font-size: 13px; background: var(--bg-input); color: var(--text-primary);
           font-family: inherit; margin: 6px 0 10px; }
  .input:focus { outline: none; border-color: var(--accent); }
  .msg { font-size: 12px; margin-top: 8px; min-height: 16px; }
  .msg.ok { color: var(--success); } .msg.err { color: var(--danger); } .msg.info { color: var(--text-muted); }
  .foot { text-align: center; font-size: 11px; color: var(--text-muted); margin-top: 8px; }
  @media (prefers-reduced-motion: reduce) { .mascot-core { animation: none; } }
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div class="mascot"><div class="mascot-core"></div></div>
    <div>
      <h1>小元AI Agent 设置</h1>
      <div class="sub">本机智能体 · 设置只作用于这台电脑</div>
    </div>
  </div>

  <div class="card">
    <h2>状态</h2>
    <div class="row"><div class="label">运行状态<span id="st-dot" class="dot offline"></span><span id="st-text" style="font-size:12px;color:var(--text-secondary)">离线</span></div>
      <div class="value" id="st-version">版本 —</div></div>
    <div class="row"><div class="label">绑定账号</div><div class="value" id="st-account">—</div></div>
    <div class="row"><div class="label">Claude Code 工作目录
      <div class="hint">Claude 委派的代码仓库（越界写入会被拒绝）</div></div>
      <div class="value" id="st-ws">—</div></div>
  </div>

  <div class="card">
    <h2>能力开关</h2>
    <div id="toggles"></div>
  </div>

  <div class="card">
    <h2>Claude Code 工作目录</h2>
    <button class="btn btn-outline" id="btn-pick">选择文件夹…</button>
    <div class="msg info" id="m-pick">浏览器无法获取目录绝对路径，选择时会弹出系统目录选择框（仅此一次系统件）。</div>
  </div>

  <div class="card" id="card-reinstall">
    <h2>重新注册（换安装码）</h2>
    <div class="hint" style="font-size:12px;color:var(--text-muted);margin-bottom:6px">
      账号注销/设备解绑后在这里换新安装码（小元AI网站「设置 → 本地 Agent」自取，形如 YUAN-XXXX-XXXX-XXXX）</div>
    <input class="input" id="in-code" placeholder="粘贴新的安装码" autocomplete="off">
    <button class="btn btn-primary" id="btn-reinstall">重新注册</button>
    <div class="msg" id="m-reinstall"></div>
  </div>

  <div class="card">
    <h2>更新</h2>
    <div class="row"><div class="label">当前版本</div><div class="value" id="up-ver">—</div></div>
    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
      <button class="btn btn-outline" id="btn-check">检查更新</button>
      <button class="btn btn-primary" id="btn-update" disabled>立即更新</button>
    </div>
    <div class="msg" id="m-update"></div>
  </div>

  <div class="card">
    <h2>退出</h2>
    <button class="btn btn-danger" id="btn-quit">退出 Agent</button>
    <div class="hint" style="font-size:11px;color:var(--text-muted);margin-top:6px">
      退出后云端对话将回退为云端应答；再次双击桌面图标即可恢复</div>
  </div>

  <div class="foot">小元AI Agent · 设置面板运行在本机（127.0.0.1），不联网传输</div>
</div>
<script>
  const $ = (id) => document.getElementById(id)
  const setMsg = (id, text, kind) => { const el = $(id); el.textContent = text || ''; el.className = 'msg' + (kind ? ' ' + kind : '') }
  const post = async (path, body) => {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : '{}' })
    return r.json().catch(() => ({ ok: false, error: '响应异常' }))
  }
  const AGENT_LABELS = { analysis: '数据分析', collection: '数据采集', automation: '自动化', claude: 'Claude Code' }

  async function refresh() {
    const st = await (await fetch('/api/status')).json()
    const dot = $('st-dot'); dot.className = 'dot ' + (st.status || 'offline')
    $('st-text').textContent = st.status === 'online' ? '在线' : st.status === 'working' ? '执行中' : '离线'
    $('st-version').textContent = '版本 ' + (st.version || '—')
    $('st-account').textContent = st.profile || '未绑定'
    $('st-ws').textContent = st.workspace || '—'
    $('up-ver').textContent = st.version || '—'
    const box = $('toggles'); box.innerHTML = ''
    for (const [key, label] of Object.entries(AGENT_LABELS)) {
      const row = document.createElement('div'); row.className = 'row'
      const lab = document.createElement('div'); lab.className = 'label'; lab.textContent = label
      const sw = document.createElement('label'); sw.className = 'switch'
      sw.innerHTML = `<input type="checkbox" ${st.toggles[key] ? 'checked' : ''}><span class="slider"></span>`
      sw.querySelector('input').onchange = async (e) => {
        const res = await post('/api/toggle', { key, enabled: e.target.checked })
        if (!res.ok) { setMsg('m-pick', res.error || '切换失败', 'err'); refresh() }
      }
      sw.title = '开启/关闭' + label
      row.appendChild(lab); row.appendChild(sw); box.appendChild(row)
    }
  }

  $('btn-pick').onclick = async () => {
    setMsg('m-pick', '正在打开目录选择框…', 'info')
    const res = await post('/api/pick-workspace')
    if (res.ok) { setMsg('m-pick', '已设为：' + res.path, 'ok'); refresh() }
    else setMsg('m-pick', res.error || '未选择', res.cancelled ? 'info' : 'err')
  }
  $('btn-reinstall').onclick = async () => {
    const code = $('in-code').value.trim()
    if (!code) { setMsg('m-reinstall', '请先粘贴安装码', 'err'); return }
    $('btn-reinstall').disabled = true
    setMsg('m-reinstall', '注册中…', 'info')
    const res = await post('/api/reinstall', { code })
    $('btn-reinstall').disabled = false
    if (res.ok) { setMsg('m-reinstall', '注册成功，正在重新连接云端…', 'ok'); $('in-code').value = ''; refresh() }
    else setMsg('m-reinstall', res.error || '注册失败', 'err')
  }
  $('btn-check').onclick = async () => {
    setMsg('m-update', '检查中…', 'info')
    const res = await post('/api/check-update')
    if (res.error) setMsg('m-update', res.error, 'err')
    else if (res.update_available) { setMsg('m-update', '发现新版本 v' + res.version + '，点「立即更新」自动升级', 'info'); $('btn-update').disabled = false }
    else setMsg('m-update', '已是最新版本', 'ok')
  }
  $('btn-update').onclick = async () => {
    if (!confirm('更新会下载新版并自动重启 Agent（约 200MB），确定继续？')) return
    $('btn-update').disabled = true
    setMsg('m-update', '正在下载更新（托盘图标会显示进度）…', 'info')
    await post('/api/do-update')
  }
  $('btn-quit').onclick = async () => {
    if (!confirm('确定退出小元AI Agent？云端对话将回退为云端应答。')) return
    await post('/api/quit')
    document.body.innerHTML = '<div class="wrap"><div class="card"><h2>已退出</h2>' +
      '<p style="font-size:13px;color:var(--text-secondary);margin-top:6px">小元AI Agent 已退出，可关闭本页面。' +
      '再次使用请双击桌面「小元AI Agent」图标。</p></div></div>'
  }

  refresh()
  if (location.search.includes('reinstall')) $('card-reinstall').scrollIntoView({ behavior: 'smooth' })
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    tray = None  # 由服务器构造时注入（AgentTray 实例）

    def log_message(self, *a):
        pass  # 本地面板请求不打日志

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self):
        body = _PAGE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            raw = self.rfile.read(n)
            if n > 8192:
                return {}
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        if self.path in ("/", "/panel"):
            self._html()
            return
        if self.path == "/api/status":
            self._json(self._tray_panel_status())
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if self.path == "/api/toggle":
            self._json(self._tray_toggle(body))
        elif self.path == "/api/pick-workspace":
            self._json(self._tray_pick_workspace())
        elif self.path == "/api/reinstall":
            self._json(self._tray_reinstall(body))
        elif self.path == "/api/check-update":
            self._json(self._tray_check_update())
        elif self.path == "/api/do-update":
            self._json(self._tray_do_update())
        elif self.path == "/api/quit":
            self._json({"ok": True})
            threading.Thread(target=self._tray_quit, daemon=True).start()
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    # ---- 转交托盘实例（面板 API 与菜单同一套逻辑） ----

    def _tray_panel_status(self):
        t = self.tray
        if not t:
            return {"ok": False, "error": "tray 未就绪"}
        try:
            from agent.cc_workspace import resolve_project_dir
            workspace = resolve_project_dir()
        except Exception:
            workspace = ""
        return {
            "ok": True,
            "status": getattr(t, "_status", "offline"),
            "version": AGENT_VERSION or "—",
            "profile": getattr(t, "_profile_label", None) or "",
            "toggles": {k: bool(t.toggles.get(k, True)) for k in
                        ("analysis", "collection", "automation", "claude")},
            "workspace": workspace,
        }

    def _tray_toggle(self, body):
        t = self.tray
        key = str(body.get("key", "") or "")
        if key not in ("analysis", "collection", "automation", "claude"):
            return {"ok": False, "error": "未知能力"}
        from agent.tray import save_toggles
        t.toggles[key] = bool(body.get("enabled"))
        save_toggles(t.toggles)
        t._trigger_restart()
        return {"ok": True}

    def _tray_pick_workspace(self):
        from agent import cc_workspace
        picked = cc_workspace.pick_directory("选择 Claude Code 的工作目录（代码仓库）")
        if not picked:
            return {"ok": False, "cancelled": True, "error": "未选择目录"}
        try:
            cc_workspace.set_project_dir(picked)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": picked}

    def _tray_reinstall(self, body):
        code = str(body.get("code", "") or "").strip()
        if not code:
            return {"ok": False, "error": "安装码不能为空"}
        t = self.tray
        if not t:
            return {"ok": False, "error": "tray 未就绪"}
        ok, err = t._reinstall_flow("设置面板", code)  # 与托盘逻辑同一套流程
        return {"ok": True} if ok else {"ok": False, "error": err}

    def _tray_check_update(self):
        t = self.tray
        try:
            t._check_update_once()
        except Exception as e:
            return {"error": f"检查失败：{str(e)[:120]}"}
        if t._update_available:
            return {"update_available": True, "version": t._update_available,
                    "forced": t._update_forced}
        return {"update_available": False, "version": AGENT_VERSION or "—"}

    def _tray_do_update(self):
        t = self.tray
        if not t._update_available:
            return {"ok": False, "error": "当前没有可用的新版本（先点「检查更新」）"}
        threading.Thread(target=t._do_update, daemon=True).start()
        return {"ok": True}

    def _tray_quit(self):
        try:
            from agent.bridge_policy import kill_spawned_tree
            kill_spawned_tree()
        except Exception:
            pass
        t = self.tray
        if t:
            t._running = False
            try:
                t._icon.stop()
            except Exception:
                pass


class PanelServer:
    """本地设置面板服务：AgentTray 内嵌，127.0.0.1 随机端口"""

    def __init__(self, tray):
        self._tray = tray
        self._server = None
        self._port = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}/panel"

    def start(self):
        try:
            _Handler.tray = self._tray
            self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
            self._port = self._server.server_address[1]
            threading.Thread(target=self._server.serve_forever,
                             name="agent-panel", daemon=True).start()
            logger.info("设置面板已启动: %s", self.url)
            _write_panel_url(self.url)  # 终端 /panel 命令读此文件开面板（v3.1）
        except Exception as e:
            logger.warning("设置面板启动失败: %s", e)

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        _clear_panel_url()


def _panel_url_path() -> str:
    try:
        from utils.data_path import root_path
        return os.path.join(root_path(), "data", "panel_url.json")
    except Exception:
        return ""


def _write_panel_url(url: str) -> None:
    """面板 URL 落盘（终端 /panel 命令入口用，2026-11-12）；失败静默"""
    try:
        p = _panel_url_path()
        if not p:
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"url": url}, f)
    except Exception:
        pass


def _clear_panel_url() -> None:
    try:
        p = _panel_url_path()
        if p and os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
