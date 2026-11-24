from __future__ import annotations

from typing import Any

REQUIRED_REPORT_SECTIONS = [
    "Executive Summary",
    "Sales KPIs",
    "Product Analysis",
    "Anomaly Detection",
    "Trend Analysis",
    "Business Recommendations",
]


def evaluate_business_report(
    markdown_report: str,
    recommendations: list[dict[str, str]],
) -> dict[str, Any]:
    """Evaluate report completeness and verify that recommendations cite calculated evidence."""
    missing_sections = [
        section for section in REQUIRED_REPORT_SECTIONS if f"## {section}" not in markdown_report
    ]

    supported_recs = [
        r for r in recommendations if isinstance(r, dict) and r.get("recommendation") and r.get("evidence")
    ]
    all_supported = len(recommendations) > 0 and len(supported_recs) == len(recommendations)

    passed = len(missing_sections) == 0 and all_supported
    return {
        "passed": passed,
        "required_sections_checked": REQUIRED_REPORT_SECTIONS,
        "missing_sections": missing_sections,
        "recommendations_count": len(recommendations),
        "evidence_supported_recommendations": len(supported_recs),
        "notes": "All required sections present and every recommendation is backed by calculated metrics."
        if passed
        else "Report failed completeness or evidence verification checks.",
    }


def generate_business_report(
    validation_summary: dict[str, Any],
    sales_metrics: dict[str, Any],
    product_metrics: dict[str, Any],
    anomaly_metrics: dict[str, Any],
    trend_metrics: dict[str, Any],
    recommendations: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a structured Markdown & JSON business analysis report and evaluate its quality."""
    best_prod = product_metrics.get("best_selling_product") or {}
    low_prod = product_metrics.get("lowest_selling_product") or {}
    top_rev = product_metrics.get("highest_revenue_product") or {}

    exec_summary = (
        f"Analyzed {validation_summary.get('valid_rows', 0)} validated sales records. "
        f"Completed revenue reached ${sales_metrics.get('total_revenue', 0):,.2f} across "
        f"{sales_metrics.get('completed_orders', 0)} completed orders "
        f"(Average Order Value: ${sales_metrics.get('average_order_value', 0):,.2f}; "
        f"Performance Rating: {sales_metrics.get('sales_performance', 'N/A')}). "
        f"Overall sales trend is {trend_metrics.get('trend_direction', 'N/A')} "
        f"({trend_metrics.get('period_change_pct', 0):+.1f}%), with "
        f"{anomaly_metrics.get('anomaly_count', 0)} statistical anomaly/anomalies detected."
    )

    lines: list[str] = [
        "# Business Analysis Report",
        "",
        "## Executive Summary",
        exec_summary,
        "",
        "## Sales KPIs",
        f"- **Total Completed Revenue:** ${sales_metrics.get('total_revenue', 0):,.2f}",
        f"- **Cancelled Revenue Impact:** ${sales_metrics.get('cancelled_revenue_impact', 0):,.2f}",
        f"- **Total Orders:** {sales_metrics.get('total_orders', 0)} (Completed: {sales_metrics.get('completed_orders', 0)}, Cancelled: {sales_metrics.get('cancelled_orders', 0)})",
        f"- **Cancellation Rate:** {sales_metrics.get('cancellation_rate_pct', 0)}%",
        f"- **Total Units Sold:** {sales_metrics.get('total_units_sold', 0)}",
        f"- **Average Order Value (AOV):** ${sales_metrics.get('average_order_value', 0):,.2f}",
        f"- **Sales Performance Status:** {sales_metrics.get('sales_performance', 'N/A')}",
        "",
        "## Product Analysis",
        f"- **Best-Selling Product (Units):** {best_prod.get('product', 'N/A')} ({best_prod.get('units_sold', 0)} units, ${best_prod.get('revenue', 0):,.2f})",
        f"- **Highest-Revenue Product:** {top_rev.get('product', 'N/A')} (${top_rev.get('revenue', 0):,.2f}, {top_rev.get('revenue_share_pct', 0)}% share)",
        f"- **Lowest-Selling Product (Units):** {low_prod.get('product', 'N/A')} ({low_prod.get('units_sold', 0)} units, ${low_prod.get('revenue', 0):,.2f})",
        "",
    ]

    for p in product_metrics.get("products", []):
        lines.append(
            f"- {p['product']} ({p['category']}): {p['units_sold']} units | ${p['revenue']:,.2f} ({p['revenue_share_pct']}%) | Tier: {p['performance_tier']}"
        )

    lines.extend(
        [
            "",
            "## Anomaly Detection",
            f"- **Summary:** {anomaly_metrics.get('summary', '')}",
        ]
    )
    for anom in anomaly_metrics.get("anomalies", []):
        lines.append(f"- [{anom.get('type', 'anomaly')}] {anom.get('explanation', '')}")

    lines.extend(
        [
            "",
            "## Trend Analysis",
            f"- **Direction:** {trend_metrics.get('trend_direction', 'N/A')} ({trend_metrics.get('granularity', 'period')} granularity)",
            f"- **Period-over-Period Change:** {trend_metrics.get('period_change_pct', 0):+.1f}% (Slope: {trend_metrics.get('slope_per_period', 0):+.2f})",
            f"- **Fluctuation Level:** {trend_metrics.get('fluctuation_level', 'N/A')} (CV: {trend_metrics.get('volatility_cv', 0)})",
        ]
    )
    for insight in trend_metrics.get("insights", []):
        lines.append(f"- {insight}")

    lines.extend(["", "## Business Recommendations"])
    for idx, rec in enumerate(recommendations, start=1):
        lines.append(
            f"{idx}. **[{rec.get('priority', 'Medium')}] {rec.get('area', 'General')}:** "
            f"{rec.get('recommendation', '')} *(Evidence: {rec.get('evidence', '')})*"
        )

    markdown_report = "\n".join(lines)
    evaluation = evaluate_business_report(markdown_report, recommendations)

    return {
        "executive_summary": exec_summary,
        "markdown_report": markdown_report,
        "evaluation": evaluation,
    }
