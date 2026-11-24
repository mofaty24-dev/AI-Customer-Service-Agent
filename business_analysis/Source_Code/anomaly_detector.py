from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

CANCELLED_STATUSES = {"cancelled", "canceled", "refunded"}


def detect_anomalies(df: pd.DataFrame, z_threshold: float = 1.50) -> dict[str, Any]:
    """Detect statistical anomalies in daily sales revenue and individual order volumes."""
    if df.empty:
        return {
            "anomaly_count": 0,
            "anomalies": [],
            "summary": "No sales records available for anomaly detection.",
        }

    completed_df = df[~df["status"].astype(str).str.lower().isin(CANCELLED_STATUSES)].copy()
    target_df = completed_df if not completed_df.empty else df.copy()

    anomalies: list[dict[str, Any]] = []

    # 1. Daily revenue spike / drop detection via Z-score
    target_df["date_str"] = target_df["date"].dt.strftime("%Y-%m-%d")
    daily = (
        target_df.groupby("date_str", as_index=False)
        .agg(daily_revenue=("revenue", "sum"), daily_units=("quantity", "sum"), orders=("order_id", "nunique"))
        .sort_values("date_str")
    )

    if len(daily) >= 3:
        mean_rev = float(daily["daily_revenue"].mean())
        std_rev = float(daily["daily_revenue"].std(ddof=1))
        if std_rev > 0:
            for _, row in daily.iterrows():
                rev = float(row["daily_revenue"])
                z_score = (rev - mean_rev) / std_rev
                if abs(z_score) >= z_threshold:
                    direction = "spike" if z_score > 0 else "drop"
                    pct_diff = ((rev - mean_rev) / mean_rev * 100.0) if mean_rev > 0 else 0.0
                    anomalies.append(
                        {
                            "type": f"daily_revenue_{direction}",
                            "date": str(row["date_str"]),
                            "observed_value": round(rev, 2),
                            "baseline_mean": round(mean_rev, 2),
                            "z_score": round(float(z_score), 2),
                            "explanation": (
                                f"Daily revenue on {row['date_str']} was ${rev:,.2f} "
                                f"({pct_diff:+.1f}% vs daily average of ${mean_rev:,.2f}, z={z_score:+.2f}), "
                                f"indicating an unusual sales {direction}."
                            ),
                        }
                    )

    # 2. Order-level quantity / revenue outlier detection via IQR
    if len(target_df) >= 4:
        q1 = float(np.percentile(target_df["revenue"], 25))
        q3 = float(np.percentile(target_df["revenue"], 75))
        iqr = q3 - q1
        upper_bound = q3 + 1.5 * iqr
        median_rev = float(target_df["revenue"].median())

        if iqr > 0:
            outliers = target_df[target_df["revenue"] > upper_bound]
            for _, row in outliers.iterrows():
                rev = float(row["revenue"])
                anomalies.append(
                    {
                        "type": "high_value_order_outlier",
                        "order_id": str(row["order_id"]),
                        "date": str(row["date_str"]),
                        "product": str(row["product"]),
                        "quantity": int(row["quantity"]),
                        "observed_value": round(rev, 2),
                        "baseline_median": round(median_rev, 2),
                        "explanation": (
                            f"Order {row['order_id']} ({row['product']}, qty={int(row['quantity'])}) "
                            f"generated ${rev:,.2f}, exceeding the upper IQR threshold (${upper_bound:,.2f}) "
                            f"and median order revenue (${median_rev:,.2f})."
                        ),
                    }
                )

    summary = (
        f"Detected {len(anomalies)} statistical anomaly/anomalies across daily revenue and order volume."
        if anomalies
        else "No statistically significant anomalies detected within configured thresholds."
    )

    return {
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "summary": summary,
    }
