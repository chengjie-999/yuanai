# -*- coding: utf-8 -*-
"""S1.3 zip 炸弹修复测试 — 三道闸（条目数/总体积/压缩比/单成员）+ 路径穿越 + 正常包

纯离线（不依赖 MySQL/Milvus，只测解压闸门与 _run_upload 前置路径）。
运行：pytest test/test_zip_bomb.py -v
"""
import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from fastapi import HTTPException  # noqa: E402


def _make_zip(tmp_path, members: dict) -> str:
    """members: {名字: bytes} → 生成 zip 文件，返回路径"""
    zp = os.path.join(str(tmp_path), "test.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return zp


def test_entry_count_gate(tmp_path, monkeypatch):
    from api.v1.knowledge.router import _safe_extract_zip
    import sys as _sys
    kr_module = _sys.modules['api.v1.knowledge.router']
    monkeypatch.setattr(kr_module, "MAX_ENTRIES", 5)

    zp = _make_zip(tmp_path, {f"f{i}.md": b"x" for i in range(6)})
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zp, str(tmp_path / "out"))
    assert ei.value.status_code == 400
    assert "条目" in ei.value.detail


def test_total_size_gate(tmp_path, monkeypatch):
    from api.v1.knowledge.router import _safe_extract_zip
    import sys as _sys
    kr_module = _sys.modules['api.v1.knowledge.router']
    monkeypatch.setattr(kr_module, "MAX_TOTAL_UNCOMPRESSED", 10 * 1024)

    zp = _make_zip(tmp_path, {"big.md": b"0" * (100 * 1024)})
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zp, str(tmp_path / "out"))
    assert ei.value.status_code == 400
    assert "体积" in ei.value.detail


def test_ratio_gate_real_constants(tmp_path):
    """真实常量验证：5MB 全零（压缩后 ~5KB）压缩比超 100 → 400"""
    from api.v1.knowledge.router import _safe_extract_zip

    zp = _make_zip(tmp_path, {"bomb.md": b"0" * (5 * 1024 * 1024)})
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zp, str(tmp_path / "out"))
    assert ei.value.status_code == 400
    assert "压缩比" in ei.value.detail


def test_member_size_gate(tmp_path, monkeypatch):
    from api.v1.knowledge.router import _safe_extract_zip
    import sys as _sys
    kr_module = _sys.modules['api.v1.knowledge.router']
    monkeypatch.setattr(kr_module, "MAX_MEMBER", 1024)
    monkeypatch.setattr(kr_module, "MAX_RATIO", 10 ** 9)  # 关掉压缩比闸，单测成员闸

    zp = _make_zip(tmp_path, {"huge.md": b"0" * 4096})
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zp, str(tmp_path / "out"))
    assert ei.value.status_code == 400
    assert "超大" in ei.value.detail


@pytest.mark.parametrize("evil_name", [
    "../evil.md", "sub/../../evil.md", "/etc/cron.d/evil", "C:\\Windows\\evil.md",
])
def test_traversal_rejected(tmp_path, evil_name):
    """穿越成员名一律 400，且目标目录外无任何文件落盘"""
    from api.v1.knowledge.router import _safe_extract_zip

    zp = _make_zip(tmp_path, {evil_name: b"evil"})
    out_dir = tmp_path / "out"
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zp, str(out_dir))
    assert ei.value.status_code == 400
    assert "路径" in ei.value.detail
    # 越界文件未创建
    for p in (tmp_path / "evil.md", tmp_path / "sub" / "evil.md"):
        assert not p.exists(), f"越界文件被写出: {p}"


def test_normal_zip_extracts(tmp_path):
    """正常包（含图片 + md + 子目录）成功解压"""
    from api.v1.knowledge.router import _safe_extract_zip

    members = {
        "笔记/01.md": "# 标题\n内容".encode("utf-8"),
        "笔记/img.png": b"\x89PNG fake",
        "嵌套/深层/02.md": "正文".encode("utf-8"),
    }
    zp = _make_zip(tmp_path, members)
    out_dir = tmp_path / "out"
    _safe_extract_zip(zp, str(out_dir))  # 不抛即通过

    assert (out_dir / "笔记" / "01.md").read_bytes() == "# 标题\n内容".encode("utf-8")
    assert (out_dir / "笔记" / "img.png").exists()
    assert (out_dir / "嵌套" / "深层" / "02.md").exists()


def test_run_upload_traversal_zip_rejected(tmp_path):
    """_run_upload 集成：穿越包在触达解析/入库前即 400"""
    from api.v1.knowledge.router import _run_upload

    tmp_dir = str(tmp_path / "kb")
    os.makedirs(tmp_dir)
    zp = os.path.join(tmp_dir, "upload.zip")
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("../evil.md", "x")

    with pytest.raises(HTTPException) as ei:
        _run_upload(zp, "evil.zip", 0, "shared", 1)
    assert ei.value.status_code == 400
    # tmp_dir 已被清理（finally rmtree）
    assert not os.path.isdir(tmp_dir)


def test_encrypted_zip_rejected(tmp_path):
    """加密成员（zf.open 抛 RuntimeError）转 400 而非 500"""
    from api.v1.knowledge.router import _safe_extract_zip

    zp = _make_zip(tmp_path, {"a.md": b"x"})
    # 用 pyzipper 若不可用则跳过：手动构造带加密标志的 zip 太繁琐
    pyzipper = pytest.importorskip("pyzipper")
    zep = os.path.join(str(tmp_path), "enc.zip")
    with pyzipper.AESZipFile(zep, "w", compression=pyzipper.ZIP_DEFLATED) as zf:
        zf.writestr("a.md", b"secret")
    with pytest.raises(HTTPException) as ei:
        _safe_extract_zip(zep, str(tmp_path / "out"))
    assert ei.value.status_code == 400


if __name__ == "__main__":
    print("测试入口：pytest test/test_zip_bomb.py -v")
