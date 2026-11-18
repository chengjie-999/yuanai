# -*- coding: utf-8 -*-
"""PWA 图标生成（T17，2026-11-18）：把 public/mascot.svg 的吉祥物形象用 PIL
重绘为 PNG——192/512（manifest）、180（apple-touch-icon，不透明底）、
512-maskable（Android 自适应图标，实底安全区）。

画法与 agent/tray.py _make_icon 同套（扫描线渐变球），按 mascot.svg 的
viewBox 0 0 100 100 逐元素比例缩放。改吉祥物形象时同步改这里 + mascot.svg。

用法：python scripts/gen_pwa_icons.py
"""
import math
import os

from PIL import Image, ImageDraw

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "frontend", "public", "icons")

TOP = (0x60, 0xA5, 0xFA)   # #60a5fa
BOTTOM = (0x1D, 0x4E, 0xD8)  # #1d4ed8
LINE = (0x3B, 0x82, 0xF6)   # #3b82f6 轨道线
DOT = (0x93, 0xC5, 0xFD)   # #93c5fd 轨道点


def _gradient_ball(draw: ImageDraw.ImageDraw, cx, cy, r, top, bottom, alpha=255):
    """扫描线渐变球（tray._make_icon 同款算法，比例缩放版）"""
    for i in range(int(2 * r)):
        t = i / max(2 * r - 1, 1)
        col = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (alpha,)
        y = cy - r + i
        half = math.sqrt(max(r * r - (i - r) ** 2, 0))
        draw.line([(cx - half, y), (cx + half, y)], fill=col)


def _round_cap_line(draw: ImageDraw.ImageDraw, p1, p2, width, fill):
    """PIL line 无圆头端点——两端补圆模拟 round caps（mascot.svg stroke-linecap）"""
    draw.line([p1, p2], fill=fill, width=int(width))
    for p in (p1, p2):
        rr = width / 2
        draw.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=fill)


def draw_mascot(size: int, background=None) -> Image.Image:
    """按 mascot.svg（100 单位画布）等比重绘吉祥物；background=None 透明底"""
    img = Image.new("RGBA", (size, size), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 100.0 * 0.92          # 留 4% 边距
    o = (size - 100 * s) / 2.0

    def P(x, y):
        return (o + x * s, o + y * s)

    # 光晕底座（opacity 0.15）
    _gradient_ball(draw, *P(50, 50), 44 * s, TOP, BOTTOM, alpha=38)
    # 核心球
    _gradient_ball(draw, *P(50, 52), 32 * s, TOP, BOTTOM)
    # 球描边（白色 20%）
    draw.ellipse((P(18, 20), P(82, 84)), outline=(255, 255, 255, 51), width=max(1, int(1.5 * s)))
    # 高光
    draw.ellipse((P(41, 43), P(59, 61)), fill=(255, 255, 255, 140))
    # 四条轨道线 + 端点圆点
    for (x1, y1, x2, y2) in ((26, 40, 12, 30), (74, 40, 88, 30),
                             (34, 62, 20, 76), (66, 62, 80, 76)):
        _round_cap_line(draw, P(x1, y1), P(x2, y2), max(1.5, 3 * s), LINE + (255,))
    for (x, y) in ((12, 30), (88, 30), (20, 76), (80, 76)):
        draw.ellipse((P(x - 4.5, y - 4.5), P(x + 4.5, y + 4.5)), fill=DOT + (255,))
    return img


def _gradient_bg(size: int) -> Image.Image:
    """maskable 图标实底：品牌蓝对角渐变（安全区适配，图形缩在中间 80%）"""
    base = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(base)
    for i in range(size):
        t = i / max(size - 1, 1)
        col = tuple(int(TOP[k] + (BOTTOM[k] - TOP[k]) * t) for k in range(3)) + (255,)
        draw.line([(i, 0), (size - 1 - i, size - 1)], fill=col)
    return base


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    targets = [
        ("icon-192.png", 192, None),
        ("icon-512.png", 512, None),
        ("icon-180.png", 180, (0xF6, 0xF8, 0xFA, 255)),   # Apple 要求不透明底
        ("icon-512-maskable.png", 512, "gradient"),        # Android 自适应图标
    ]
    for fname, size, bg in targets:
        img = draw_mascot(size)
        if bg == "gradient":
            merged = _gradient_bg(size)
            art = draw_mascot(int(size * 0.80))            # 安全区：图形缩到 80%
            merged.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2))
            img = merged
        elif bg:
            base = Image.new("RGBA", (size, size), bg)
            base.alpha_composite(img)
            img = base
        path = os.path.join(OUT_DIR, fname)
        img.save(path, "PNG")
        print(f"generated {path} ({size}x{size})")


if __name__ == "__main__":
    main()
