"""导出架构图与数据关系图到 docs/diagrams/（README 嵌入用）。

后端 /api/v1/monitor/arch-diagram 与 /er-diagram 是请求时实时生成；
本脚本把同一份生成器落盘为 SVG 文件，供 README/文档引用。
代码变更后运行一次即可让 README 图片同步（可挂进 CI）。

用法：python scripts/gen_diagrams.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.v1.monitor.diagrams import generate_arch_svg, generate_er_svg
from utils.data_path import root_path


def main():
    out_dir = os.path.join(root_path(), "docs", "diagrams")
    os.makedirs(out_dir, exist_ok=True)
    arch = os.path.join(out_dir, "arch.svg")
    er = os.path.join(out_dir, "er.svg")
    with open(arch, "w", encoding="utf-8") as f:
        f.write(generate_arch_svg())
    with open(er, "w", encoding="utf-8") as f:
        f.write(generate_er_svg())
    print(f"已生成:\n  {arch}\n  {er}")


if __name__ == "__main__":
    main()
