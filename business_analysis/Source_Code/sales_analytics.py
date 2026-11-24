from __future__ import annotations

from typing import Any

import pandas as pd

CANCELLED_STATUSES = {"cancelled", "canceled", "refunded"}


def analyze_sales(df: pd.DataFrame) -> dict[str, Any]:
    """Calculate core sales KPIs and order status performance metrics."""
    if df.empty:
        return {
            "total_revenue": 0.0,
            "cancelled_revenue_impact": 0.0,
            "total_orders": 0,
            "completed_orders": 0,
            "cancelled_orders": 0,
            "cancellation_rate_pct": 0.0,
            "total_units_sold": 0,
            "average_order_value": 0.0,
            "sales_performance": "No Data",
            "by_status": {},
        }

    status_series = df["status"].astype(str).str.lower()
    is_cancelled = status_series.isin(CANCELLED_STATUSES)
    is_completed = ~is_cancelled

    completed_df = df[is_completed]
    cancelled_df = df[is_cancelled]

    total_revenue = round(float(completed_df["revenue"].sum()), 2)
    cancelled_revenue_impact = round(float(cancelled_df["revenue"].sum()), 2)

    total_orders = int(df["order_id"].nunique()) if "order_id" in df.columns else int(len(df))
    completed_orders = int(completed_df["order_id"].nunique()) if "order_id" in df.columns else int(len(completed_df))
    cancelled_orders = int(cancelled_df["order_id"].nunique()) if "order_id" in df.columns else int(len(cancelled_df))

    cancellation_rate_pct = round((cancelled_orders / total_orders * 100.0), 2) if total_orders > 0 else 0.0
    total_units_sold = int(completed_df["quantity"].sum())
    average_order_value = round((total_revenue / completed_orders), 2) if completed_orders > 0 else 0.0

    completion_rate = (completed_orders / total_orders) if total_orders > 0 else 0.0
    if completion_rate >= 0.90 and average_order_value >= 250.0:
        sales_performance = "Strong"
    elif completion_rate >= 0.75 and total_revenue > 0:
        sales_performance = "Healthy"
    elif total_revenue > 0:
        sales_performance = "Moderate (Watch Cancellations)"
    else:
        sales_performance = "Needs Attention"

    by_status: dict[str, dict[str, Any]] = {}
    for status_val, group in df.groupby(status_series):
        by_status[str(status_val)] = {
            "orders": int(group["order_id"].nunique()) if "order_id" in group.columns else int(len(group)),
            "units": int(group["quantity"].sum()),
            "revenue": round(float(group["revenue"].sum()), 2),
        }

    return {
        "total_revenue": total_revenue,
        "cancelled_revenue_impact": cancelled_revenue_impact,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "cancellation_rate_pct": cancellation_rate_pct,
        "total_units_sold": total_units_sold,
        "average_order_value": average_order_value,
        "sales_performance": sales_performance,
        "by_status": by_status,
    }
