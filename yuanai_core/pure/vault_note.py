"""Obsidian vault 同步纯函数 — 云边共用的内容规范化 / 哈希 / frontmatter / 三向判定

设计要点：
- 图片链接规范化：任何形式的图片 URL（云端 ?token= / vault assets/ 相对路径）
  统一为 `asset:{map_id}/{basename}` 后再算哈希——避免「各改各的链接 → 无限回环」
- frontmatter：自实现扁平标量 YAML 子集解析（不引 PyYAML）
- vault 文件名：允许中文/空格（Obsidian 笔记名即标题），不用 safe_filename
"""

import hashlib
import re

# frontmatter 锚点键（vault 侧专属产物；云端只存正文）
FM_KEYS = ("planet_note_id", "planet_id", "map_id", "updated", "source", "vault_path")

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


# ---------------- 内容规范化与哈希 ----------------

def _normalize_img_url(url: str, map_id: int) -> str:
    """图片 URL → asset:{map_id}/{basename}（云端 ?token= 与 vault 相对路径统一）"""
    u = url.strip().strip("<>")
    # 去 query（?token=...）
    u = u.split("?")[0]
    # 取 basename（最后一段；统一 / 与 \\）
    base = re.split(r"[/\\]", u)[-1]
    return f"asset:{map_id}/{base}" if map_id else f"asset:0/{base}"


def canonical_body(content: str, map_id: int = 0) -> str:
    """规范化正文：图片链接统一 + 行尾统一（\r\n→\n）+ 首尾空白剥离"""
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _IMG_RE.sub(lambda m: f"![{m.group(1)}]({_normalize_img_url(m.group(2), map_id)})",
                       text)
    return text.strip()


def note_body_hash(content: str, map_id: int = 0) -> str:
    """正文哈希（先规范化再 sha256）"""
    return hashlib.sha256(canonical_body(content, map_id).encode("utf-8")).hexdigest()


# ---------------- frontmatter（扁平标量 YAML 子集） ----------------

def parse_frontmatter(text: str) -> dict:
    """解析 --- 块内的扁平标量（key: value 一行一个；仅字符串/数字/true/false/null）。
    无 frontmatter 返回 {}。"""
    m = _FM_RE.match(text or "")
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.lower() == "true":
            out[key] = True
        elif val.lower() == "false":
            out[key] = False
        elif val.lower() in ("null", "~", ""):
            out[key] = None
        elif re.fullmatch(r"-?\d+", val):
            out[key] = int(val)
        elif val.startswith('"') and val.endswith('"'):
            out[key] = val[1:-1]
        else:
            out[key] = val
    return out


def strip_frontmatter(text: str) -> str:
    """去掉 frontmatter 块，返回正文"""
    return _FM_RE.sub("", text or "").strip()


def inject_frontmatter(body: str, fields: dict) -> str:
    """正文 → 带 frontmatter 的 vault 文件内容（flat 标量序列化）"""
    lines = ["---"]
    for k, v in fields.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + (body or "").strip()


# ---------------- vault 文件名 ----------------

_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def vault_filename(title: str) -> str:
    """标题 → vault 文件名（保留中文与空格；只剔除文件系统非法字符与首尾点）"""
    name = _FORBIDDEN_CHARS.sub("", (title or "").strip()).strip(". ")
    return (name or "未命名笔记")[:120] + ".md"


# ---------------- 三向判定 ----------------

def sync_decision(base_hash: str, vault_hash: str, cloud_hash: str) -> str:
    """三向合并判定（base = 上次同步共同版本）。

    | vault | cloud | 动作 |
    | 变    | 同    | upload |
    | 同    | 变    | download |
    | 变    | 变    | conflict（本地赢；规范化后恰好相等则视为无变化） |
    | 同    | 同    | none |
    """
    if vault_hash == base_hash and cloud_hash == base_hash:
        return "none"
    if vault_hash != base_hash and cloud_hash == base_hash:
        return "upload"
    if vault_hash == base_hash and cloud_hash != base_hash:
        return "download"
    if vault_hash != base_hash and cloud_hash != base_hash:
        # 双改：规范化后相等 = 双方改成了同一内容 → 视为无冲突
        return "none" if vault_hash == cloud_hash else "conflict"
    return "none"
