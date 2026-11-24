from __future__ import annotations

from typing import Any


def generate_recommendations(
    sales_metrics: dict[str, Any],
    product_metrics: dict[str, Any],
    anomaly_metrics: dict[str, Any],
    trend_metrics: dict[str, Any],
) -> list[dict[str, str]]:
    """Generate practical, metric-backed business recommendations."""
    recommendations: list[dict[str, str]] = []

    top_rev = product_metrics.get("highest_revenue_product")
    best_unit = product_metrics.get("best_selling_product")
    low_unit = product_metrics.get("lowest_selling_product")

    if top_rev:
        recommendations.append(
            {
                "priority": "High",
                "area": "Inventory & Core Revenue Protection",
                "recommendation": (
                    f"Prioritize safety stock and prominent merchandising for '{top_rev['product']}', "
                    f"which generates ${top_rev['revenue']:,.2f} ({top_rev['revenue_share_pct']}% of completed revenue)."
                ),
                "evidence": f"highest_revenue_product={top_rev['product']}, revenue=${top_rev['revenue']:,.2f}, share={top_rev['revenue_share_pct']}%",
            }
        )

    if best_unit and top_rev and best_unit["product"] != top_rev["product"]:
        recommendations.append(
            {
                "priority": "Medium",
                "area": "Cross-Selling & Bundle Pricing",
                "recommendation": (
                    f"Bundle high-volume '{best_unit['product']}' ({best_unit['units_sold']} units sold) "
                    f"with top-revenue '{top_rev['product']}' to lift Average Order Value (${sales_metrics.get('average_order_value', 0):,.2f})."
                ),
                "evidence": f"best_selling_product={best_unit['product']} ({best_unit['units_sold']} units), AOV=${sales_metrics.get('average_order_value', 0):,.2f}",
            }
        )

    if low_unit and best_unit and low_unit["product"] != best_unit["product"]:
        recommendations.append(
            {
                "priority": "Medium",
                "area": "Catalog Optimization & Targeted Promotions",
                "recommendation": (
                    f"Run targeted promotions or review pricing/positioning for '{low_unit['product']}', "
                    f"currently the lowest-selling item ({low_unit['units_sold']} units, ${low_unit['revenue']:,.2f})."
                ),
                "evidence": f"lowest_selling_product={low_unit['product']}, units_sold={low_unit['units_sold']}, revenue=${low_unit['revenue']:,.2f}",
            }
        )

    cancel_rate = float(sales_metrics.get("cancellation_rate_pct", 0.0))
    cancelled_orders = int(sales_metrics.get("cancelled_orders", 0))
    if cancelled_orders > 0:
        priority = "High" if cancel_rate >= 10.0 else "Medium"
        recommendations.append(
            {
                "priority": priority,
                "area": "Order Fulfillment & Cancellation Reduction",
                "recommendation": (
                    f"Audit checkout and fulfillment bottlenecks for the {cancelled_orders} cancelled order(s) "
                    f"({cancel_rate}% cancellation rate, ${sales_metrics.get('cancelled_revenue_impact', 0):,.2f} lost revenue)."
                ),
                "evidence": f"cancelled_orders={cancelled_orders}, cancellation_rate_pct={cancel_rate}%, cancelled_revenue_impact=${sales_metrics.get('cancelled_revenue_impact', 0):,.2f}",
            }
        )

    anomaly_count = int(anomaly_metrics.get("anomaly_count", 0))
    if anomaly_count > 0:
        first_anom = anomaly_metrics["anomalies"][0]
        recommendations.append(
            {
                "priority": "High",
                "area": "Demand Spike & Outlier Readiness",
                "recommendation": (
                    f"Investigate detected sales anomaly on {first_anom.get('date', 'N/A')} "
                    f"({first_anom.get('type', 'outlier')}) and establish bulk-order replenishment triggers."
                ),
                "evidence": f"anomaly_count={anomaly_count}; {first_anom.get('explanation', '')}",
            }
        )

    trend_dir = trend_metrics.get("trend_direction", "Unknown")
    pct_change = float(trend_metrics.get("period_change_pct", 0.0))
    if trend_dir == "Increasing":
        recommendations.append(
            {
                "priority": "Medium",
                "area": "Growth Scaling",
                "recommendation": (
                    f"Maintain current acquisition campaigns while scaling inventory capacity to support "
                    f"the upward {trend_metrics.get('granularity', 'period')} revenue trend ({pct_change:+.1f}%)."
                ),
                "evidence": f"trend_direction={trend_dir}, period_change_pct={pct_change:+.1f}%, volatility_cv={trend_metrics.get('volatility_cv', 0)}",
            }
        )
    elif trend_dir == "Decreasing":
        recommendations.append(
            {
                "priority": "High",
                "area": "Revenue Recovery",
                "recommendation": (
                    f"Launch retention outreach and promotional campaigns immediately to reverse the downward "
                    f"{trend_metrics.get('granularity', 'period')} revenue trend ({pct_change:+.1f}%)."
                ),
                "evidence": f"trend_direction={trend_dir}, period_change_pct={pct_change:+.1f}%",
            }
        )

    return recommendations
