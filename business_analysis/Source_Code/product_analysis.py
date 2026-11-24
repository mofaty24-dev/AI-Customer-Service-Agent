from __future__ import annotations

from typing import Any

import pandas as pd

CANCELLED_STATUSES = {"cancelled", "canceled", "refunded"}


def analyze_products(df: pd.DataFrame) -> dict[str, Any]:
    """Analyze product sales volume, revenue contribution, and top/bottom performers."""
    if df.empty:
        return {
            "best_selling_product": None,
            "lowest_selling_product": None,
            "highest_revenue_product": None,
            "products": [],
        }

    completed_df = df[~df["status"].astype(str).str.lower().isin(CANCELLED_STATUSES)]
    target_df = completed_df if not completed_df.empty else df

    total_revenue = float(target_df["revenue"].sum())

    grouped = (
        target_df.groupby("product", as_index=False)
        .agg(
            category=("category", "first"),
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
            orders_count=("order_id", "nunique"),
            avg_unit_price=("unit_price", "mean"),
        )
    )

    grouped["units_sold"] = grouped["units_sold"].astype(int)
    grouped["orders_count"] = grouped["orders_count"].astype(int)
    grouped["revenue"] = grouped["revenue"].round(2)
    grouped["avg_unit_price"] = grouped["avg_unit_price"].round(2)
    grouped["revenue_share_pct"] = (
        (grouped["revenue"] / total_revenue * 100.0).round(2) if total_revenue > 0 else 0.0
    )

    by_revenue = grouped.sort_values(by=["revenue", "units_sold"], ascending=[False, False]).reset_index(drop=True)
    by_units = grouped.sort_values(by=["units_sold", "revenue"], ascending=[False, False]).reset_index(drop=True)

    best_selling_row = by_units.iloc[0]
    lowest_selling_row = by_units.iloc[-1]
    highest_revenue_row = by_revenue.iloc[0]

    products_list: list[dict[str, Any]] = []
    for _, row in by_revenue.iterrows():
        share = float(row["revenue_share_pct"])
        if share >= 25.0:
            tier = "Core Revenue Driver"
        elif share >= 12.0:
            tier = "Steady Contributor"
        else:
            tier = "Long-Tail / Growth Opportunity"

        products_list.append(
            {
                "product": str(row["product"]),
                "category": str(row["category"]),
                "units_sold": int(row["units_sold"]),
                "orders_count": int(row["orders_count"]),
                "avg_unit_price": float(row["avg_unit_price"]),
                "revenue": float(row["revenue"]),
                "revenue_share_pct": share,
                "performance_tier": tier,
            }
        )

    return {
        "best_selling_product": {
            "product": str(best_selling_row["product"]),
            "units_sold": int(best_selling_row["units_sold"]),
            "revenue": float(best_selling_row["revenue"]),
        },
        "lowest_selling_product": {
            "product": str(lowest_selling_row["product"]),
            "units_sold": int(lowest_selling_row["units_sold"]),
            "revenue": float(lowest_selling_row["revenue"]),
        },
        "highest_revenue_product": {
            "product": str(highest_revenue_row["product"]),
            "revenue": float(highest_revenue_row["revenue"]),
            "revenue_share_pct": float(highest_revenue_row["revenue_share_pct"]),
        },
        "products": products_list,
    }
