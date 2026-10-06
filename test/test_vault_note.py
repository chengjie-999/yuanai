# -*- coding: utf-8 -*-
"""vault 同步纯函数测试 — 规范化 / 哈希 / frontmatter / 文件名 / 三向判定

纯离线。运行：pytest test/test_vault_note.py -v
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from yuanai_core.pure.vault_note import (  # noqa: E402
    canonical_body, note_body_hash, parse_frontmatter, strip_frontmatter,
    inject_frontmatter, vault_filename, sync_decision,
)


# ---------------- 规范化与哈希 ----------------

def test_canonical_body_normalizes_image_urls():
    content = (
        "![图A](https://cjyuanai.cn/api/v1/planet/asset/3/7/a.png?token=xyz)\r\n"
        "![图B](assets/7/b.png)\r\n"
        "![图C](./7/c.png)"
    )
    out = canonical_body(content, map_id=7)
    assert "?token" not in out
    assert "asset:7/a.png" in out
    assert "asset:7/b.png" in out
    assert "asset:7/c.png" in out
    assert "\r" not in out


def test_note_body_hash_ignores_token_and_link_style():
    """token 与链接写法不同但内容相同的正文 → 哈希一致（防无限回环的关键）"""
    a = "笔记正文\n![x](https://site/api/v1/planet/asset/1/5/a.png?token=abc)"
    b = "笔记正文\n![x](assets/5/a.png)"
    assert note_body_hash(a, 5) == note_body_hash(b, 5)
    assert note_body_hash(a, 5) != note_body_hash(a, 6)  # map 不同 → 哈希不同


# ---------------- frontmatter ----------------

def test_parse_frontmatter_flat_scalars():
    text = """---
planet_note_id: 42
map_id: 7
title: "我的 笔记"
updated: 2026-10-03 10:00:00
done: true
empty:
---
正文"""
    fm = parse_frontmatter(text)
    assert fm["planet_note_id"] == 42
    assert fm["map_id"] == 7
    assert fm["title"] == "我的 笔记"
    assert fm["done"] is True
    assert fm["empty"] is None


def test_parse_frontmatter_none():
    assert parse_frontmatter("没有 frontmatter 的正文") == {}


def test_strip_and_inject_roundtrip():
    body = "第一段\n\n第二段"
    text = inject_frontmatter(body, {"planet_note_id": 9, "map_id": 3})
    assert parse_frontmatter(text)["planet_note_id"] == 9
    assert parse_frontmatter(text)["map_id"] == 3
    assert strip_frontmatter(text) == body


# ---------------- 文件名 ----------------

def test_vault_filename_keeps_chinese_and_spaces():
    assert vault_filename("数据分析入门 笔记") == "数据分析入门 笔记.md"


def test_vault_filename_strips_forbidden_chars():
    assert vault_filename('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij.md"
    assert vault_filename("..") == "未命名笔记.md"
    assert vault_filename("") == "未命名笔记.md"


def test_vault_filename_truncates():
    assert len(vault_filename("长" * 300)) <= 124


# ---------------- 三向判定 ----------------

def test_sync_decision_matrix():
    B = "base"; V1 = "vault1"; C1 = "cloud1"
    assert sync_decision(B, B, B) == "none"          # 都没变
    assert sync_decision(B, V1, B) == "upload"       # vault 变 cloud 同
    assert sync_decision(B, B, C1) == "download"     # cloud 变 vault 同
    assert sync_decision(B, V1, C1) == "conflict"    # 双变
    assert sync_decision(B, V1, V1) == "none"        # 双变但内容相同 → 无冲突


if __name__ == "__main__":
    print("测试入口：pytest test/test_vault_note.py -v")
