"""数据分析核心 — 纯函数，无框架依赖。plotly 图表 + pandas 统计。"""
import os
import json
import base64
from utils.data_path import root_path

ANALYSIS_DIR = os.path.join(root_path(), "data", "analysis")


def run_analysis(ds: dict, ds_id: int, charts: bool = True) -> dict:
    import pandas as pd

    path = ds["file_path"]
    ft = ds["file_type"]
    if ft == "csv":
        df = pd.read_csv(path)
    elif ft in ("xlsx", "xls"):
        df = pd.read_excel(path)
    elif ft == "json":
        df = pd.read_json(path)
    else:
        raise ValueError(f"unsupported type: {ft}")

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = df.select_dtypes(include=["datetime64", "datetimetz"]).columns.tolist()
    if not date_cols:
        date_cols = _detect_date_columns(df)

    desc = df[num_cols].describe().round(2).to_dict() if num_cols else {}
    missing = {k: int(v) for k, v in df.isnull().sum().to_dict().items() if v > 0}
    corr_data = df[num_cols].corr().round(2).values.tolist() if len(num_cols) >= 2 else []
    col_info = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]

    chart_data = []
    if charts:
        chart_dir = os.path.join(ANALYSIS_DIR, str(ds_id))
        os.makedirs(chart_dir, exist_ok=True)

        if num_cols:
            _make_distribution(df, num_cols, chart_dir, ds_id, chart_data)
        if len(num_cols) >= 2:
            _make_heatmap(df, num_cols, chart_dir, ds_id, chart_data)
        if num_cols:
            _make_boxplot(df, num_cols, chart_dir, ds_id, chart_data)
        if len(num_cols) >= 2:
            _make_scatter(df, num_cols, chart_dir, ds_id, chart_data)
        if date_cols and num_cols:
            _make_line(df, date_cols[0], num_cols, chart_dir, ds_id, chart_data)
        if cat_cols:
            _make_bar(df, cat_cols, chart_dir, ds_id, chart_data)

    ts_result = None
    if date_cols and num_cols and charts:
        ts_result = _run_time_series(df, date_cols[0], num_cols, chart_dir, ds_id, chart_data)

    return {
        "id": ds_id, "name": ds["name"], "row_count": len(df),
        "columns": col_info, "num_cols": num_cols,
        "describe": desc, "missing": missing,
        "corr_labels": num_cols, "corr": corr_data,
        "charts": chart_data,
        "time_series": ts_result,
    }


def _detect_date_columns(df) -> list:
    """Auto-detect date columns by name pattern or string content."""
    import pandas as pd
    date_cols = []
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ("date", "time", "日期", "时间", "timestamp")):
            try:
                df[col] = pd.to_datetime(df[col])
                date_cols.append(col)
            except Exception:
                pass
    return date_cols


def _make_chart(fig, name: str, chart_dir: str, ds_id: int, chart_data: list):
    """Save plotly figure as PNG and HTML, append to chart_data."""
    import plotly.io as pio

    # PNG (base64 for chat embedding)
    png_bytes = pio.to_image(fig, format="png", width=800, height=400, scale=1)
    png_b64 = base64.b64encode(png_bytes).decode()

    # HTML (self-contained for iframe)
    html_path = os.path.join(chart_dir, f"{name}.html")
    fig.write_html(html_path, include_plotlyjs="cdn", full_html=True,
                   config={"displayModeBar": True, "responsive": True})

    chart_data.append({
        "name": name,
        "url": f"/api/v1/data/analysis-image/{ds_id}/{name}",
        "html_url": f"/api/v1/data/analysis-html/{ds_id}/{name}",
        "data": png_b64,
    })


def _make_distribution(df, num_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = min(len(num_cols), 9)
    cols = 3
    rows = (n + cols - 1) // cols
    fig = make_subplots(rows=rows, cols=cols,
                        subplot_titles=[str(c)[:30] for c in num_cols[:n]])

    for i, col in enumerate(num_cols[:n]):
        row, col_idx = i // cols + 1, i % cols + 1
        fig.add_trace(
            go.Histogram(x=df[col].dropna(), name=str(col), marker_color="#589df6",
                         nbinsx=30, opacity=0.8),
            row=row, col=col_idx,
        )

    fig.update_layout(height=220 * rows, showlegend=False, margin=dict(l=20, r=20, t=40, b=20),
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "distribution", chart_dir, ds_id, chart_data)


def _make_heatmap(df, num_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    corr = df[num_cols].corr().round(2)
    labels = [str(c)[:20] for c in num_cols]

    fig = go.Figure(data=go.Heatmap(
        z=corr.values, x=labels, y=labels,
        colorscale="RdBu_r", zmin=-1, zmax=1,
        text=corr.values, texttemplate="%{text:.2f}",
        hovertemplate="%{x} × %{y}: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(height=500, margin=dict(l=60, r=20, t=30, b=80),
                      xaxis_tickangle=-45,
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "heatmap", chart_dir, ds_id, chart_data)


def _make_boxplot(df, num_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    sample_cols = num_cols[:min(len(num_cols), 10)]
    fig = go.Figure()
    for col in sample_cols:
        fig.add_trace(go.Box(y=df[col].dropna(), name=str(col)[:20],
                             marker_color="#589df6"))

    fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=30, b=80),
                      xaxis_tickangle=-45,
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "boxplot", chart_dir, ds_id, chart_data)


def _make_scatter(df, num_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    x, y = num_cols[0], num_cols[1]
    fig = go.Figure(data=go.Scatter(
        x=df[x].dropna(), y=df[y].dropna(),
        mode="markers", marker=dict(size=6, color="#589df6", opacity=0.5),
        hovertemplate=f"{x}: %{{x}}<br>{y}: %{{y}}<extra></extra>",
    ))
    fig.update_layout(height=400, margin=dict(l=50, r=20, t=30, b=60),
                      xaxis_title=str(x), yaxis_title=str(y),
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "scatter", chart_dir, ds_id, chart_data)


def _make_line(df, date_col, num_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    df_sorted = df.sort_values(date_col).copy()
    sample_cols = num_cols[:min(len(num_cols), 5)]

    fig = go.Figure()
    for col in sample_cols:
        fig.add_trace(go.Scatter(
            x=df_sorted[date_col], y=df_sorted[col].dropna() if df_sorted[col].dropna else [],
            mode="lines", name=str(col)[:20],
        ))

    fig.update_layout(height=400, margin=dict(l=20, r=20, t=30, b=60),
                      legend=dict(orientation="h", yanchor="top", y=-0.2),
                      xaxis_title=str(date_col),
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "line", chart_dir, ds_id, chart_data)


def _make_bar(df, cat_cols, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    col = cat_cols[0]
    top = df[col].value_counts().head(10)
    fig = go.Figure(data=go.Bar(
        x=top.index.astype(str), y=top.values,
        marker_color="#589df6", opacity=0.8,
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=80),
                      xaxis_title=str(col), yaxis_title="count",
                      xaxis_tickangle=-45,
                      template="plotly_dark" if _is_dark_friendly() else "plotly_white")
    _make_chart(fig, "bar", chart_dir, ds_id, chart_data)


def _run_time_series(df, date_col, num_cols, chart_dir, ds_id, chart_data):
    """Run time series analysis and return structured TS data."""
    import numpy as np
    import pandas as pd

    df_ts = df[[date_col] + [c for c in num_cols if c != date_col]].copy()
    df_ts[date_col] = pd.to_datetime(df_ts[date_col])
    df_ts = df_ts.sort_values(date_col).dropna(subset=[date_col])

    primary_col = [c for c in num_cols if c != date_col][0] if num_cols else None
    if not primary_col:
        return None

    series = df_ts.set_index(date_col)[primary_col].dropna()
    if len(series) < 14:
        return None

    result = {"date_col": date_col}

    # rolling stats
    rolling_7 = series.rolling(7, min_periods=1)
    roll_dates = [d.isoformat() for d in series.index][-50:]
    roll_mean = [float(v) for v in rolling_7.mean().values][-50:]
    roll_std = [float(v) for v in rolling_7.std().values][-50:]
    result["rolling"] = {"date": roll_dates, "mean_7d": roll_mean, "std_7d": roll_std}
    _make_rolling_chart(df_ts, date_col, primary_col, chart_dir, ds_id, chart_data)

    # STL decomposition
    try:
        from statsmodels.tsa.seasonal import STL
        period = min(7, max(2, len(series) // 4))
        stl = STL(series.dropna(), period=period, robust=True).fit()
        result["decomposition"] = {
            "date": [d.isoformat() for d in series.index],
            "trend": [float(v) if not np.isnan(v) else None for v in stl.trend.values],
            "seasonal": [float(v) if not np.isnan(v) else None for v in stl.seasonal.values],
            "resid": [float(v) if not np.isnan(v) else None for v in stl.resid.values],
        }
        _make_decomposition_chart(series, stl, chart_dir, ds_id, chart_data)
    except Exception:
        pass

    # anomaly detection (rolling z-score)
    try:
        roll_m = series.rolling(14, min_periods=7).mean()
        roll_s = series.rolling(14, min_periods=7).std().replace(0, np.nan)
        z_scores = ((series - roll_m) / roll_s).dropna()
        anomalies = z_scores[z_scores.abs() > 3]
        if len(anomalies) > 0 and len(anomalies) <= 50:
            result["anomalies"] = [
                {"date": d.isoformat(), "value": float(series[d]), "z_score": round(float(z_scores[d]), 2)}
                for d in anomalies.index
            ]
            _make_anomaly_chart(series, anomalies, chart_dir, ds_id, chart_data)
    except Exception:
        pass

    return result


def _make_rolling_chart(df, date_col, value_col, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    series = df.set_index(date_col)[value_col].dropna()
    roll = series.rolling(7, min_periods=1)
    roll_mean = roll.mean()
    roll_std = roll.std()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines", name=str(value_col)[:20],
                             line=dict(color="#589df6", width=1), opacity=0.4))
    fig.add_trace(go.Scatter(x=roll_mean.index, y=roll_mean.values, mode="lines", name="7天滚动均值",
                             line=dict(color="#f5a623", width=2)))
    fig.add_trace(go.Scatter(
        x=list(roll_mean.index) + list(roll_mean.index[::-1]),
        y=list((roll_mean + roll_std).values) + list((roll_mean - roll_std).values[::-1]),
        fill="toself", fillcolor="rgba(245,166,35,0.15)", line=dict(width=0),
        name="±1σ",
    ))
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=40),
                      legend=dict(orientation="h", yanchor="top", y=-0.15),
                      template="plotly_white")
    _make_chart(fig, "rolling", chart_dir, ds_id, chart_data)


def _make_decomposition_chart(series, stl, chart_dir, ds_id, chart_data):
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        subplot_titles=["趋势", "季节", "残差"],
                        vertical_spacing=0.08)

    idx = series.index

    def _add(trace, row):
        fig.add_trace(trace, row=row, col=1)

    _add(go.Scatter(x=idx, y=stl.trend, mode="lines", line=dict(color="#589df6", width=1.5), name="趋势"), 1)
    _add(go.Scatter(x=idx, y=stl.seasonal, mode="lines", line=dict(color="#66bb6a", width=1.5), name="季节"), 2)
    _add(go.Scatter(x=idx, y=stl.resid, mode="lines", line=dict(color="#ef5350", width=1), name="残差"), 3)

    fig.update_layout(height=450, showlegend=False, margin=dict(l=20, r=20, t=50, b=20),
                      template="plotly_white")
    _make_chart(fig, "decomposition", chart_dir, ds_id, chart_data)


def _make_anomaly_chart(series, anomalies, chart_dir, ds_id, chart_data):
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines", name="数值",
                             line=dict(color="#589df6", width=1)))

    anomaly_dates = list(anomalies.index)
    anomaly_vals = [float(series[d]) for d in anomaly_dates]
    fig.add_trace(go.Scatter(x=anomaly_dates, y=anomaly_vals, mode="markers", name="异常点",
                             marker=dict(color="#ef5350", size=8, symbol="x"),
                             hovertemplate="%{x}<br>值: %{y:.2f}<extra></extra>"))

    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=40),
                      legend=dict(orientation="h", yanchor="top", y=-0.15),
                      template="plotly_white")
    _make_chart(fig, "anomalies", chart_dir, ds_id, chart_data)


def _is_dark_friendly() -> bool:
    """Use plotly_white template since charts are embedded on light backgrounds."""
    return False
