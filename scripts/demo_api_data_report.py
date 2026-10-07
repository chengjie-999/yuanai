"""接单样品 1 号：API 数据接入 + 分析报告（量化路线图第一步）

数据源：东方财富官方公开行情接口（push2his，免费、无需注册、非爬虫）
产出：data/cases/案例1-行情数据接入/
  - 沪深300_日线.csv      干净数据表（交付物）
  - 沪深300_分析报告.html  自包含报告（图表 base64 内嵌，双击即看）
  - 沪深300_走势.png       走势图

用法：python scripts/demo_api_data_report.py
"""
import base64
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "cases", "案例1-行情数据接入")

# 东方财富官方行情接口（公开；secid: 1.000300 = 沪深300，klt=101 日线，fqt=1 前复权）
KLINE_URL = ("http://push2his.eastmoney.com/api/qt/stock/kline/get"
             "?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
             "&klt=101&fqt=1&beg={beg}&end={end}")


def fetch_kline(secid: str, beg: str, end: str) -> pd.DataFrame:
    """官方接口 → DataFrame（日期/开/收/高/低/量/额）"""
    url = KLINE_URL.format(secid=secid, beg=beg, end=end)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    klines = (data.get("data") or {}).get("klines") or []
    rows = [k.split(",") for k in klines]
    df = pd.DataFrame(rows, columns=["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"])
    for col in ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def make_chart(df: pd.DataFrame) -> str:
    """走势图（收盘价 + 20/60 日均线）→ PNG base64"""
    df = df.copy()
    df["MA20"] = df["收盘"].rolling(20).mean()
    df["MA60"] = df["收盘"].rolling(60).mean()
    fig, ax = plt.subplots(figsize=(10, 5), dpi=110)
    ax.plot(df.index, df["收盘"], label="收盘价", color="#1f77b4", linewidth=1.4)
    ax.plot(df.index, df["MA20"], label="20 日均线", color="#ff7f0e", linewidth=1)
    ax.plot(df.index, df["MA60"], label="60 日均线", color="#2ca02c", linewidth=1)
    ax.set_title("沪深 300 近一年走势（前复权）", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    every = max(1, len(df) // 8)
    ax.set_xticks(range(0, len(df), every))
    ax.set_xticklabels([str(d) for d in df["日期"].iloc[::every]], rotation=30, fontsize=8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build_report(df: pd.DataFrame, img_b64: str, source: str) -> str:
    stats = {
        "样本天数": len(df),
        "区间涨跌幅": f"{(df['收盘'].iloc[-1] / df['收盘'].iloc[0] - 1) * 100:.2f}%",
        "最高收盘": f"{df['收盘'].max():.2f}",
        "最低收盘": f"{df['收盘'].min():.2f}",
        "日均成交额": f"{df['成交额'].mean() / 1e8:.1f} 亿元",
        "最新收盘": f"{df['收盘'].iloc[-1]:.2f}",
    }
    table = df.tail(10).to_html(index=False, border=0, classes="tbl")
    stat_html = "".join(
        f'<div class="stat"><div class="v">{v}</div><div class="k">{k}</div></div>'
        for k, v in stats.items())
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>沪深300 数据接入分析报告（样品）</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #f5f7fa; color: #222; }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 20px; }}
  h1 {{ font-size: 22px; }} h2 {{ font-size: 16px; margin-top: 28px; }}
  .meta {{ color: #888; font-size: 12px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }}
  .stat {{ background: #fff; border-radius: 10px; padding: 14px 18px; min-width: 130px;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .stat .v {{ font-size: 18px; font-weight: 700; color: #1f77b4; }}
  .stat .k {{ font-size: 11px; color: #888; margin-top: 4px; }}
  img {{ width: 100%; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
  .tbl {{ border-collapse: collapse; width: 100%; font-size: 12px; background: #fff; }}
  .tbl th, .tbl td {{ padding: 7px 10px; border-bottom: 1px solid #eee; text-align: right; }}
  .tbl th {{ background: #fafbfc; color: #666; }}
  .foot {{ margin-top: 28px; font-size: 11px; color: #aaa; }}
</style></head><body><div class="wrap">
  <h1>沪深 300 行情数据接入 · 分析报告</h1>
  <div class="meta">数据来源：{source}（官方公开接口，每日自动更新） · 生成于 {pd.Timestamp.now():%Y-%m-%d}</div>
  <div class="stats">{stat_html}</div>
  <h2>近一年走势</h2>
  <img src="data:image/png;base64,{img_b64}" alt="走势图">
  <h2>最近 10 个交易日</h2>
  {table}
  <div class="foot">样品报告 · 小元AI 数据服务：API 数据接入 / 数据分析 / 定时监控</div>
</div></body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    beg = (pd.Timestamp.now() - pd.Timedelta(days=365)).strftime("%Y%m%d")
    end = pd.Timestamp.now().strftime("%Y%m%d")
    try:
        df = fetch_kline("1.000300", beg, end)
        source = "东方财富官方行情接口 push2his"
    except Exception as e:
        print(f"行情接口拉取失败（{e}），使用演示数据生成样品")
        dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq="B")
        import numpy as np
        close = 3800 + np.cumsum(np.random.default_rng(7).normal(2, 30, len(dates)))
        df = pd.DataFrame({
            "日期": [d.strftime("%Y-%m-%d") for d in dates],
            "开盘": close - 8, "收盘": close, "最高": close + 20, "最低": close - 25,
            "成交量": 8e7, "成交额": 2.4e10,
        })
        source = "演示数据（离线兜底）"

    csv_path = os.path.join(OUT_DIR, "沪深300_日线.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    png_path = os.path.join(OUT_DIR, "沪深300_走势.png")
    img_b64 = make_chart(df)
    with open(png_path, "wb") as f:
        f.write(base64.b64decode(img_b64))

    html_path = os.path.join(OUT_DIR, "沪深300_分析报告.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_report(df, img_b64, source))

    print("=" * 50)
    print("样品生成完毕：")
    print(f"  数据表: {csv_path}")
    print(f"  走势图: {png_path}")
    print(f"  报告:   {html_path}  ← 双击用浏览器打开")
    print("=" * 50)


if __name__ == "__main__":
    main()
