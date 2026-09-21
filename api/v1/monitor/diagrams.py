"""架构图 / 数据关系图（ER）生成器 — 纯 Python 零依赖，输出 SVG 字符串。

「随代码变化自动更新」的实现方式：图在**请求时从当前代码实时生成**，
不落缓存——db/session.py 的 ORM 模型一改，ER 图自动同步；目录结构一变，架构图数字自动同步。

- generate_er_svg():   ast 解析 db/session.py 的 SQLAlchemy 模型（表名/字段/主键/外键），
                       外键除显式 ForeignKey 外按命名约定补（user_id→users、planet_id→planets 等）
- generate_arch_svg(): 云边协同架构（层级框 + 箭头 + 实时目录统计/分支信息）
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
from utils.data_path import root_path

# ---------------- 通用 SVG 工具 ----------------

_THEME = {"bg": "#f6f8fa", "panel": "#ffffff", "border": "#d0d7de",
          "text": "#1f2328", "muted": "#656d76", "accent": "#1976d2",
          "accent_light": "rgba(25,118,210,0.08)"}

_AGENT_COLORS = {"orchestrator": "#1976d2", "analysis": "#7b1fa2",
                 "collection": "#00695c", "automation": "#e65100", "claude": "#d97757"}


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _svg(w: int, h: int, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="-apple-system, Segoe UI, sans-serif" '
            f'font-size="12" style="background:{_THEME["bg"]}">\n{body}\n</svg>')


def _box(x: int, y: int, w: int, h: int, fill: str = "", stroke: str = "",
         rx: int = 10, dash: str = "") -> str:
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill or _THEME["panel"]}" '
    s += f'stroke="{stroke or _THEME["border"]}" stroke-width="1.2"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s + '/>'


def _text(x: int, y: int, s: str, size: int = 12, fill: str = "", weight: str = "",
          anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill or _THEME["text"]}" '
            f'font-weight="{weight or 400}" text-anchor="{anchor}">{_esc(s)}</text>')


def _marker_id(color: str) -> str:
    """颜色 → 合法 marker id（去掉 # 与 rgba 括号等非法字符）"""
    return re.sub(r"[^a-zA-Z0-9]", "", color)


def _arrow(x1: int, y1: int, x2: int, y2: int, color: str = "", dash: str = "",
           label: str = "") -> str:
    """三次贝塞尔箭头（水平出、水平入）"""
    color = color or _THEME["muted"]
    mid = (x1 + x2) // 2
    d = f'M {x1} {y1} C {mid} {y1}, {mid} {y2}, {x2} {y2}'
    s = f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.4"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    s += f' marker-end="url(#arrow-{_marker_id(color)})"/>'
    return s


def _defs(colors: list[str]) -> str:
    out = ["<defs>"]
    for c in colors:
        out.append(
            f'<marker id="arrow-{_marker_id(c)}" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>')
    out.append("</defs>")
    return "\n".join(out)


# ---------------- ER 图：ast 解析 db/session.py ----------------

def _col_type(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Constant):
        return str(node.value)
    if isinstance(node, ast.Call):
        fn = getattr(node.func, "id", "") or ""
        arg0 = node.args[0] if node.args else None
        inner = ""
        if isinstance(arg0, ast.Constant):
            inner = str(arg0.value)
        # String(50) / Text().with_variant(MEDIUMTEXT, 'mysql')
        for kw in node.keywords:
            if kw.arg == "with_variant":
                if isinstance(kw.value, ast.Call):
                    vf = getattr(kw.value.func, "id", "") or ""
                    inner += f"/{vf}"
        return f"{fn}({inner})" if inner else fn
    if isinstance(node, ast.Attribute):
        return node.attr
    return type(node).__name__


# 命名约定外键：字段名 → 目标表
_FK_HEURISTICS = {
    "user_id": "users",
    "planet_id": "planets",
    "map_id": "planet_maps",
    "note_id": "planet_notes",
    "session_id": "chat_session",
    "dataset_id": "datasets",
}


def _parse_models() -> list[dict]:
    src = open(os.path.join(root_path(), "db", "session.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    tables = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [getattr(b, "id", "") for b in node.bases]
        if "Base" not in bases:
            continue
        tablename = ""
        cols = []
        for item in node.body:
            if isinstance(item, ast.Assign) and item.targets and isinstance(item.targets[0], ast.Name):
                t = item.targets[0].id
                if t == "__tablename__" and isinstance(item.value, ast.Constant):
                    tablename = item.value.value
                elif isinstance(item.value, ast.Call) and getattr(item.value.func, "id", "") == "Column":
                    pk = any(k.arg == "primary_key" and getattr(k.value, "value", None) is True
                             for k in item.value.keywords)
                    fk = next((str(k.value.value) for k in item.value.keywords
                               if k.arg == "ForeignKey"), "")
                    cols.append({"name": t, "type": _col_type(item.value.args[0] if item.value.args else None),
                                 "pk": pk, "fk": fk})
        if tablename:
            tables.append({"class": node.name, "table": tablename, "cols": cols})
    return tables


def generate_er_svg() -> str:
    """数据关系图：每表一个盒子（字段列表，PK 高亮），外键画边（显式 ForeignKey + 命名约定）"""
    tables = _parse_models()
    if not tables:
        return _svg(400, 100, _text(20, 40, "未解析到 ORM 模型"))

    BOX_W, ROW_H, TITLE_H, GAP_X, GAP_Y = 240, 16, 26, 30, 34
    COLS = 4
    # 布局：按行排布，行高取该行最大字段数（避免溢出）
    rows_count = (len(tables) + COLS - 1) // COLS
    row_heights = []
    for r in range(rows_count):
        chunk = tables[r * COLS:(r + 1) * COLS]
        row_heights.append(TITLE_H + ROW_H * max(len(t["cols"]) for t in chunk))
    positions = {}
    y = 30
    for r in range(rows_count):
        chunk = tables[r * COLS:(r + 1) * COLS]
        for col, t in enumerate(chunk):
            positions[t["table"]] = (20 + col * (BOX_W + GAP_X), y)
        y += row_heights[r] + GAP_Y

    max_h = y + 20
    w = 20 + COLS * (BOX_W + GAP_X)

    body = [_defs([_THEME["muted"], _THEME["accent"]])]
    body.append(_text(20, 18, f"数据库数据关系（{len(tables)} 表 · 实时解析 db/session.py）",
                      14, _THEME["text"], "600"))

    # 边（先画，压底）
    for t in tables:
        x, y = positions[t["table"]]
        for i, c in enumerate(t["cols"]):
            target = ""
            if c["fk"]:
                target = c["fk"].split(".")[0]
            elif c["name"] in _FK_HEURISTICS and _FK_HEURISTICS[c["name"]] != t["table"]:
                target = _FK_HEURISTICS[c["name"]]
            if target and target in positions:
                tx, ty = positions[target]
                x1 = x + BOX_W
                y1 = y + TITLE_H + i * ROW_H + ROW_H // 2
                x2 = tx
                y2 = ty + TITLE_H // 2
                body.append(_arrow(x1, y1, x2, y2))

    # 表盒子
    for t in tables:
        x, y = positions[t["table"]]
        n = len(t["cols"])
        h = TITLE_H + n * ROW_H
        body.append(_box(x, y, BOX_W, h))
        body.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{TITLE_H}" rx="10" '
                    f'fill="{_THEME["accent"]}" stroke="none"/>')
        body.append(f'<rect x="{x}" y="{y + TITLE_H - 10}" width="{BOX_W}" height="10" '
                    f'fill="{_THEME["accent"]}" stroke="none"/>')
        body.append(_text(x + 12, y + 17, t["table"], 12.5, "#ffffff", "600"))
        for i, c in enumerate(t["cols"]):
            cy = y + TITLE_H + i * ROW_H + ROW_H // 2 + 4
            body.append(_text(x + 12, cy, c["name"], 11.5,
                              _THEME["accent"] if c["pk"] else _THEME["text"],
                              "600" if c["pk"] else ""))
            body.append(_text(x + BOX_W - 10, cy, c["type"], 10.5, _THEME["muted"], "", "end"))
    return _svg(w, max_h, "\n".join(body))


# ---------------- 架构图 ----------------

def _dir_stats(rel: str) -> int:
    d = os.path.join(root_path(), rel)
    if not os.path.isdir(d):
        return 0
    return sum(len(fs) for _, _, fs in os.walk(d))


def _git_branch() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, cwd=root_path(), timeout=5)
        return out.stdout.decode().strip()
    except Exception:
        return "?"


def generate_arch_svg() -> str:
    """云边协同架构图：请求时实时生成（目录文件数为活数据）"""
    api_files = _dir_stats("api")
    agent_files = _dir_stats("agent")
    fe_files = _dir_stats(os.path.join("frontend", "src"))
    core_files = _dir_stats("yuanai_core")
    branch = _git_branch()

    body = [_defs(list(_AGENT_COLORS.values()) + [_THEME["muted"]])]
    body.append(_text(20, 22, f"小元AI 云边协同架构（分支 {branch} · 实时生成）",
                      15, _THEME["text"], "700"))

    # 第一层：用户
    body.append(_box(60, 60, 170, 52, _THEME["accent_light"], _THEME["accent"]))
    body.append(_text(145, 90, "用户浏览器", 13, _THEME["accent"], "600", "middle"))
    body.append(_text(145, 106, f"React 前端（{fe_files} 文件）", 10.5, _THEME["muted"], "", "middle"))

    # 第二层：云端
    body.append(_box(300, 60, 260, 130))
    body.append(_text(430, 80, "云端 Web（火山引擎）", 13, _THEME["text"], "700", "middle"))
    body.append(_text(430, 97, "Nginx → FastAPI :8000", 11.5, _THEME["muted"], "", "middle"))
    body.append(_text(430, 113, f"SSE 对话 · JWT · 限流（api/ {api_files} 文件）", 10.5, _THEME["muted"], "", "middle"))
    body.append(_box(315, 125, 74, 30, _THEME["panel"]))
    body.append(_text(352, 144, "MySQL", 11))
    body.append(_box(393, 125, 74, 30, _THEME["panel"]))
    body.append(_text(430, 144, "Redis", 11))
    body.append(_box(471, 125, 76, 30, _THEME["panel"]))
    body.append(_text(509, 144, "Milvus", 11))

    # 第三层：本地 Agent
    body.append(_box(630, 60, 260, 130))
    body.append(_text(760, 80, "本地 Agent（二合一进程）", 13, _THEME["text"], "700", "middle"))
    body.append(_text(760, 97, f"WebSocket 自动重连（agent/ {agent_files} 文件）", 10.5, _THEME["muted"], "", "middle"))
    body.append(_text(760, 113, "统筹 Agent（意图路由）· Claude Code 桥接", 10.5, _THEME["muted"], "", "middle"))
    body.append(_box(645, 125, 100, 30, _AGENT_COLORS["orchestrator"]))
    body.append(_text(695, 144, "统筹", 11, "#fff", "600", "middle"))
    body.append(_box(749, 125, 100, 30, _AGENT_COLORS["claude"]))
    body.append(_text(799, 144, "Claude Code", 11, "#fff", "600", "middle"))

    # 第四层：子 Agent
    body.append(_box(960, 60, 220, 130))
    body.append(_text(1070, 80, "专业子 Agent", 13, _THEME["text"], "700", "middle"))
    sub = [("数据分析", _AGENT_COLORS["analysis"]), ("数据采集", _AGENT_COLORS["collection"]),
           ("自动化", _AGENT_COLORS["automation"])]
    for i, (label, color) in enumerate(sub):
        body.append(_box(975, 100 + i * 26, 86, 22, color))
        body.append(_text(1018, 115 + i * 26, label, 10.5, "#fff", "600", "middle"))
    body.append(_text(1070, 178, f"yuanai_core {core_files} 文件 · 工具 80+", 10, _THEME["muted"], "", "middle"))

    # 底部：数据层
    body.append(_box(300, 230, 620, 52))
    body.append(_text(610, 250, "数据层", 12, _THEME["text"], "700", "middle"))
    body.append(_text(610, 268, "MySQL（会话/数据集/知识星球四表） · Milvus 向量知识库 · data/ 文件存储", 11, _THEME["muted"], "", "middle"))

    # 连线
    body.append(_arrow(230, 86, 300, 100, label="HTTPS"))
    body.append(_arrow(560, 110, 630, 100, label="WS"))
    body.append(_arrow(890, 100, 960, 100, label="委派"))
    body.append(_arrow(430, 190, 430, 230, dash="4 3", label="读写"))
    body.append(_arrow(760, 190, 620, 240, dash="4 3", label=""))
    # 云端直连回退
    body.append(_text(300, 200, "Agent 离线 → 云端直连 LLM 回退", 10.5, _THEME["muted"], "", "middle"))

    return _svg(1210, 310, "\n".join(body))
