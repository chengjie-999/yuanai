"""接单样品 2 号：每日数据自动报表（API 数据接入 + 定时更新能力展示）

数据源（均为免费公开官方接口，无需注册）：
- 汇率：frankfurter.app（欧洲央行每日汇率）
- 天气：open-meteo.com（开放气象数据）

产出：data/cases/案例2-每日数据自动报表/
  - 每日数据快照.csv    每日一份（脚本可挂 Windows 任务计划/托盘定时跑）
  - 每日数据报表.html   自包含报告（双击即看）

用法：python scripts/demo_api_daily_report.py
定时：Windows 任务计划每天 08:00 运行本脚本即实现「每日自动更新」
"""
import base64
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "cases", "案例2-每日数据自动报表")

# 汇率（ECB 官方每日价，免费无 key；CNY 基准的 6 个主要币种）
FX_URL = "https://api.frankfurter.app/latest?from=CNY&to=USD,EUR,JPY,GBP,HKD,AUD"
# 天气（open-meteo 开放接口，免费无 key；地点=杭州 30.29,120.16）
WEATHER_URL = ("https://api.open-meteo.com/v1/forecast?latitude=30.29&longitude=120.16"
               "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
               "&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FShanghai&forecast_days=1")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect() -> dict:
    """拉汇率 + 天气 → 快照 dict（失败字段留空不崩）"""
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    fx = {}
    try:
        data = fetch_json(FX_URL)
        fx = {k: round(1 / v, 4) for k, v in (data.get("rates") or {}).items()}  # CNY→X
        fx = {"汇率 CNY→" + k: v for k, v in fx.items()}
    except Exception as e:
        print(f"汇率接口失败: {e}")
    weather = {}
    try:
        data = fetch_json(WEATHER_URL)
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        weather = {
            "当前温度(°C)": cur.get("temperature_2m"),
            "湿度(%)": cur.get("relative_humidity_2m"),
            "风速(km/h)": cur.get("wind_speed_10m"),
            "今日最高(°C)": (daily.get("temperature_2m_max") or [None])[0],
            "今日最低(°C)": (daily.get("temperature_2m_min") or [None])[0],
        }
    except Exception as e:
        print(f"天气接口失败: {e}")
    return {"日期": today, **fx, **weather}


def build_report(snap: dict) -> str:
    rows = "".join(
        f'<tr><td>{k}</td><td class="v">{v if v is not None else "—"}</td></tr>'
        for k, v in snap.items())
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>每日数据自动报表（样品）</title>
<style>
  body {{ font-family: "Microsoft YaHei", sans-serif; margin: 0; background: #f5f7fa; color: #222; }}
  .wrap {{ max-width: 640px; margin: 0 auto; padding: 32px 20px; }}
  h1 {{ font-size: 22px; }} .meta {{ color: #888; font-size: 12px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 18px 24px; margin-top: 20px;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #f0f0f0; }}
  .v {{ text-align: right; font-weight: 600; color: #1f77b4; }}
  .foot {{ margin-top: 28px; font-size: 11px; color: #aaa; }}
</style></head><body><div class="wrap">
  <h1>每日数据快报</h1>
  <div class="meta">数据来源：欧洲央行官方汇率（frankfurter）+ 开放气象接口（open-meteo） · 自动更新</div>
  <div class="card"><table>{rows}</table></div>
  <div class="foot">样品报告 · 小元AI 数据服务：API 数据接入 / 每日自动更新 / 自定义指标</div>
</div></body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    snap = collect()

    csv_path = os.path.join(OUT_DIR, "每日数据快照.csv")
    df = pd.DataFrame([snap])
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    html_path = os.path.join(OUT_DIR, "每日数据报表.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_report(snap))

    print("=" * 50)
    print("样品生成完毕：")
    print(f"  快照 CSV: {csv_path}")
    print(f"  报表:     {html_path}  ← 双击浏览器打开")
    print("  定时: Windows 任务计划每天 08:00 运行本脚本即「每日自动更新」")
    print("=" * 50)


if __name__ == "__main__":
    main()
