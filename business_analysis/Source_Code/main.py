from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

from Source_Code.anomaly_detector import detect_anomalies
from Source_Code.product_analysis import analyze_products
from Source_Code.recommendations import generate_recommendations
from Source_Code.report_generator import generate_business_report
from Source_Code.sales_analytics import analyze_sales
from Source_Code.trends_analysis import analyze_trends
from Source_Code.validators import DataValidationError, load_csv_file, validate_and_clean_sales_data

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def run_analysis_on_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Run the complete business analysis pipeline on a raw pandas DataFrame."""
    validation_res = validate_and_clean_sales_data(df)
    cleaned_df = validation_res.cleaned_df

    sales_metrics = analyze_sales(cleaned_df)
    product_metrics = analyze_products(cleaned_df)
    anomaly_metrics = detect_anomalies(cleaned_df)
    trend_metrics = analyze_trends(cleaned_df)
    recommendations = generate_recommendations(
        sales_metrics=sales_metrics,
        product_metrics=product_metrics,
        anomaly_metrics=anomaly_metrics,
        trend_metrics=trend_metrics,
    )
    report = generate_business_report(
        validation_summary=validation_res.to_dict(),
        sales_metrics=sales_metrics,
        product_metrics=product_metrics,
        anomaly_metrics=anomaly_metrics,
        trend_metrics=trend_metrics,
        recommendations=recommendations,
    )

    return {
        "status": "success",
        "validation": validation_res.to_dict(),
        "sales_analytics": sales_metrics,
        "product_analysis": product_metrics,
        "anomaly_detection": anomaly_metrics,
        "trends_analysis": trend_metrics,
        "recommendations": recommendations,
        "report": report,
    }


def run_analysis_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the complete analysis pipeline from a list of sales record dictionaries."""
    if not isinstance(records, list) or len(records) == 0:
        raise DataValidationError("Expected a non-empty list of sales record objects.")
    df = pd.DataFrame(records)
    return run_analysis_on_dataframe(df)


def run_analysis_from_csv(csv_path: str | Path | None = None) -> dict[str, Any]:
    """Load a CSV file (defaulting to Data/sales_data.csv) and run the analysis pipeline."""
    default_rel = os.getenv("DEFAULT_SALES_DATA_PATH", "Data/sales_data.csv")
    resolved_path = Path(csv_path) if csv_path is not None else (PROJECT_ROOT / default_rel)
    if not resolved_path.is_absolute():
        resolved_path = PROJECT_ROOT / resolved_path

    raw_df = load_csv_file(resolved_path)
    return run_analysis_on_dataframe(raw_df)


def main() -> None:
    """CLI entry point for running local business analysis and printing a summary report."""
    try:
        result = run_analysis_from_csv()
    except (FileNotFoundError, DataValidationError) as exc:
        print(f"Analysis Error: {exc}")
        raise SystemExit(1) from exc

    print(result["report"]["markdown_report"])
    print("\n--- Evaluation ---")
    print(json.dumps(result["report"]["evaluation"], indent=2))


if __name__ == "__main__":
    main()
