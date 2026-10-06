"""回填 planet_notes.content_hash（存量数据一次性脚本，幂等）

迁移 0010 后存量行 content_hash 为空；读取路径已「空则现算」兼容，
本脚本把存量行回填落库（避免每次 pull index 都重算）。

用法：python scripts/backfill_note_hash.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

from db.session import get_db, PlanetNote  # noqa: E402
from yuanai_core.pure.vault_note import note_body_hash  # noqa: E402


def main():
    db = get_db()
    sess = db.Session()
    filled = 0
    try:
        rows = sess.query(PlanetNote).filter(PlanetNote.content_hash == "").all()
        for r in rows:
            if not r.content:
                continue
            r.content_hash = note_body_hash(r.content, r.map_id or 0)
            filled += 1
        sess.commit()
        print(f"回填完成：{filled}/{len(rows)} 行")
    finally:
        sess.close()


if __name__ == "__main__":
    main()
