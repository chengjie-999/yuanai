"""分析结果 API — 大屏数据 + 图表服务"""
import os
import json as _json
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from db.session import get_db

router = APIRouter(prefix="/analysis", tags=["analysis"])

SEGMENT_LABELS = {
    111: "重要价值", 110: "一般价值",
    101: "重要发展", 100: "一般发展",
    11: "重要保持", 10: "一般保持",
    1: "重要挽留", 0: "一般挽留",
}
SEGMENT_COLORS = {
    "重要价值": "#1a73e8", "一般价值": "#4285f4",
    "重要发展": "#f9a825", "一般发展": "#fbc02d",
    "重要保持": "#0d904f", "一般保持": "#34a853",
    "重要挽留": "#d93025", "一般挽留": "#ea4335",
}


@router.post("/rfm")
async def rfm_analysis(request: Request):
    body = await request.json() if await request.body() else {}
    dataset_id = body.get("dataset_id")

    if dataset_id:
        db = get_db()
        ds = db.get_dataset(int(dataset_id))
        if not ds:
            raise HTTPException(status_code=404, detail="dataset not found")
        path = ds["file_path"]
    else:
        from utils.data_path import root_path
        path = os.path.join(root_path(), "data", "user", "from", "订单明细.xlsx")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="default RFM data file not found")

    try:
        df = pd.read_excel(path) if path.endswith(".xlsx") else pd.read_csv(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"read failed: {e}")

    required = ["用户编号", "交易时间", "金额"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing columns: {missing}")

    if "交易状态" in df.columns:
        df = df[df["交易状态"] == "交易成功"]
    df["交易时间"] = pd.to_datetime(df["交易时间"])
    df = df[["用户编号", "交易时间", "金额"]].dropna()

    ref_date = df["交易时间"].max()
    r = df.groupby("用户编号")["交易时间"].max().reset_index()
    r["R"] = (ref_date - r["交易时间"]).dt.days
    r = r[["用户编号", "R"]]
    f = df.groupby("用户编号").agg(F=("交易时间", "nunique")).reset_index()
    m = df.groupby("用户编号").agg(M=("金额", "sum")).reset_index()
    rfm = r.merge(f, on="用户编号").merge(m, on="用户编号")

    mean_R, mean_F, mean_M = float(rfm["R"].mean()), float(rfm["F"].mean()), float(rfm["M"].mean())
    rfm["R_score"] = (rfm["R"] < mean_R) * 100
    rfm["F_score"] = (rfm["F"] > mean_F) * 10
    rfm["M_score"] = (rfm["M"] > mean_M) * 1
    rfm["total"] = rfm["R_score"] + rfm["F_score"] + rfm["M_score"]
    rfm["segment"] = rfm["total"].map(SEGMENT_LABELS)

    seg_counts = rfm["segment"].value_counts()
    seg_amounts = rfm.groupby("segment")["M"].sum()
    total_amount = float(seg_amounts.sum())
    total_users = len(rfm)
    segments = []
    for label in SEGMENT_LABELS.values():
        cnt = int(seg_counts.get(label, 0))
        amt = float(seg_amounts.get(label, 0))
        segments.append({
            "label": label, "count": cnt,
            "amount": round(amt, 2),
            "count_pct": f"{cnt/total_users*100:.1f}%",
            "amount_pct": f"{amt/total_amount*100:.1f}%" if total_amount > 0 else "0%",
            "color": SEGMENT_COLORS.get(label, "#999"),
        })
    segments.sort(key=lambda x: x["amount"], reverse=True)

    chart_html = _make_rfm_3d(rfm, ds_id=dataset_id or 0)

    return {
        "summary": {"users": total_users, "orders": int(len(df)), "ref_date": str(ref_date.date())},
        "means": {"R": round(mean_R, 1), "F": round(mean_F, 1), "M": round(mean_M, 0)},
        "segments": segments,
        "chart_html": chart_html,
    }


def _make_rfm_3d(rfm, ds_id: int) -> str:
    import plotly.graph_objects as go
    from utils.data_path import root_path

    sample = rfm.head(500)
    fig = go.Figure(data=[go.Scatter3d(
        x=sample["R"], y=sample["F"], z=sample["M"],
        mode="markers",
        marker=dict(size=4, color=sample["segment"].map(SEGMENT_COLORS), opacity=0.8),
        text=sample["用户编号"].astype(str) + "<br>" + sample["segment"],
        hoverinfo="text",
    )])
    fig.update_layout(
        scene=dict(xaxis_title="R", yaxis_title="F", zaxis_title="M", bgcolor="#16213e"),
        paper_bgcolor="#16213e", font_color="#eaeaea",
        height=450, margin=dict(l=0, r=0, t=0, b=0),
    )
    chart_dir = os.path.join(root_path(), "data", "analysis", "rfm")
    os.makedirs(chart_dir, exist_ok=True)
    html_path = os.path.join(chart_dir, f"rfm_3d_{ds_id or 'default'}.html")
    fig.write_html(html_path, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})
    return f"/api/v1/analysis/rfm-chart/rfm_3d_{ds_id or 'default'}"


@router.get("/rfm-chart/{filename}")
async def serve_rfm_chart(filename: str):
    from utils.data_path import root_path
    fpath = os.path.join(root_path(), "data", "analysis", "rfm", f"{filename}.html")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="not found")
    with open(fpath, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get("/dashboard/{session_id}")
async def get_dashboard_data(session_id: str):
    try:
        from db.redis_client import get_redis
        rds = get_redis()
        data = rds.get(f"dashboard:{session_id}")
        if data:
            return JSONResponse(content=_json.loads(data))
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="dashboard data not found")
