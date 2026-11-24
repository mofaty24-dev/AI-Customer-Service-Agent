from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

CANCELLED_STATUSES = {"cancelled", "canceled", "refunded"}


def analyze_trends(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze sales trends over time, growth rates, volatility, and weekday patterns."""
    if df.empty:
        return {
            "granularity": "none",
            "trend_direction": "No Data",
            "slope_per_period": 0.0,
            "period_change_pct": 0.0,
            "volatility_cv": 0.0,
            "fluctuation_level": "None",
            "time_series": [],
            "day_of_week_summary": [],
            "insights": ["No records available to compute time trends."],
        }

    completed_df = df[~df["status"].astype(str).str.lower().isin(CANCELLED_STATUSES)].copy()
    if completed_df.empty:
        completed_df = df.copy()

    date_span_days = int((completed_df["date"].max() - completed_df["date"].min()).days)
    if date_span_days >= 14:
        completed_df["period"] = completed_df["date"].dt.to_period("W-MON").apply(lambda p: str(p.start_time.date()))
        granularity = "weekly"
    else:
        completed_df["period"] = completed_df["date"].dt.strftime("%Y-%m-%d")
        granularity = "daily"

    series_df = (
        completed_df.groupby("period", as_index=False)
        .agg(
            revenue=("revenue", "sum"),
            units=("quantity", "sum"),
            orders=("order_id", "nunique"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )

    revenues = series_df["revenue"].astype(float).to_numpy()
    n = len(revenues)

    if n >= 2:
        x = np.arange(n, dtype=float)
        slope, _ = np.polyfit(x, revenues, 1)
        first_val = revenues[0]
        last_val = revenues[-1]
        period_change_pct = ((last_val - first_val) / first_val * 100.0) if first_val > 0 else 0.0

        mean_val = float(np.mean(revenues))
        std_val = float(np.std(revenues, ddof=1))
        volatility_cv = (std_val / mean_val) if mean_val > 0 else 0.0

        if slope > 0.01 * max(mean_val, 1.0):
            trend_direction = "Increasing"
        elif slope < -0.01 * max(mean_val, 1.0):
            trend_direction = "Decreasing"
        else:
            trend_direction = "Stable / Flat"

        if volatility_cv >= 0.45:
            fluctuation_level = "High Fluctuation"
        elif volatility_cv >= 0.20:
            fluctuation_level = "Moderate Fluctuation"
        else:
            fluctuation_level = "Low Fluctuation"
    else:
        slope = 0.0
        period_change_pct = 0.0
        volatility_cv = 0.0
        trend_direction = "Insufficient Data Points"
        fluctuation_level = "Low Fluctuation"

    completed_df["day_of_week"] = completed_df["date"].dt.day_name()
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_grouped = (
        completed_df.groupby("day_of_week", as_index=False)
        .agg(avg_revenue=("revenue", "mean"), total_revenue=("revenue", "sum"), units=("quantity", "sum"))
    )
    dow_grouped["rank_order"] = dow_grouped["day_of_week"].apply(lambda d: dow_order.index(d) if d in dow_order else 99)
    dow_grouped = dow_grouped.sort_values("rank_order")

    day_of_week_summary = [
        {
            "day_of_week": str(r["day_of_week"]),
            "total_revenue": round(float(r["total_revenue"]), 2),
            "avg_transaction_revenue": round(float(r["avg_revenue"]), 2),
            "units": int(r["units"]),
        }
        for _, r in dow_grouped.iterrows()
    ]

    best_dow = max(day_of_week_summary, key=lambda item: item["total_revenue"]) if day_of_week_summary else None

    insights: list[str] = [
        f"Overall {granularity} revenue trend is '{trend_direction}' ({period_change_pct:+.1f}% from first to last period, slope={slope:+.2f}).",
        f"Sales variability shows '{fluctuation_level}' (coefficient of variation={volatility_cv:.2f}).",
    ]
    if best_dow:
        insights.append(
            f"Peak revenue day of the week is {best_dow['day_of_week']} with ${best_dow['total_revenue']:,.2f} total completed revenue."
        )

    time_series = [
        {
            "period": str(r["period"]),
            "revenue": round(float(r["revenue"]), 2),
            "units": int(r["units"]),
            "orders": int(r["orders"]),
        }
        for _, r in series_df.iterrows()
    ]

    return {
        "granularity": granularity,
        "trend_direction": trend_direction,
        "slope_per_period": round(float(slope), 2),
        "period_change_pct": round(float(period_change_pct), 2),
        "volatility_cv": round(float(volatility_cv), 2),
        "fluctuation_level": fluctuation_level,
        "time_series": time_series,
        "day_of_week_summary": day_of_week_summary,
        "insights": insights,
    }
