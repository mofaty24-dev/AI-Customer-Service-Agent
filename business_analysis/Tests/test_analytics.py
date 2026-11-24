import pandas as pd
import pytest

from Source_Code.anomaly_detector import detect_anomalies
from Source_Code.main import run_analysis_from_records
from Source_Code.product_analysis import analyze_products
from Source_Code.recommendations import generate_recommendations
from Source_Code.sales_analytics import analyze_sales
from Source_Code.trends_analysis import analyze_trends
from Source_Code.validators import DataValidationError, validate_and_clean_sales_data


def _sample_records() -> list[dict]:
    return [
        {"order_id": "O1", "date": "2026-10-01", "product": "Mouse", "category": "Acc", "quantity": 10, "unit_price": 20.0, "status": "completed"},
        {"order_id": "O2", "date": "2026-10-02", "product": "Keyboard", "category": "Acc", "quantity": 5, "unit_price": 80.0, "status": "completed"},
        {"order_id": "O3", "date": "2026-10-03", "product": "Mouse", "category": "Acc", "quantity": 50, "unit_price": 20.0, "status": "completed"},
        {"order_id": "O4", "date": "2026-10-04", "product": "Stand", "category": "Office", "quantity": 2, "unit_price": 50.0, "status": "cancelled"},
        {"order_id": "O5", "date": "2026-10-05", "product": "Keyboard", "category": "Acc", "quantity": 8, "unit_price": 80.0, "status": "completed"},
        {"order_id": "O6", "date": "2026-10-06", "product": "Mouse", "category": "Acc", "quantity": 12, "unit_price": 20.0, "status": "completed"},
    ]


def test_validation_catches_bad_quantity_and_missing_columns() -> None:
    bad_qty_df = pd.DataFrame(
        [{"order_id": "O1", "date": "2026-10-01", "product": "Mouse", "quantity": -3, "unit_price": 15.0}]
    )
    with pytest.raises(DataValidationError):
        validate_and_clean_sales_data(bad_qty_df)

    missing_col_df = pd.DataFrame([{"order_id": "O1", "date": "2026-10-01", "product": "Mouse"}])
    with pytest.raises(DataValidationError):
        validate_and_clean_sales_data(missing_col_df)


def test_validation_handles_duplicates_and_invalid_dates() -> None:
    dup_df = pd.DataFrame(
        [
            {"order_id": "O1", "date": "2026-10-01", "product": "Mouse", "quantity": 2, "unit_price": 10.0, "status": "completed"},
            {"order_id": "O1", "date": "2026-10-01", "product": "Mouse", "quantity": 2, "unit_price": 10.0, "status": "completed"},
        ]
    )
    res = validate_and_clean_sales_data(dup_df)
    assert res.deduplicated_rows == 1
    assert len(res.cleaned_df) == 1

    bad_date_df = pd.DataFrame(
        [{"order_id": "O1", "date": "not-a-date", "product": "Mouse", "quantity": 2, "unit_price": 10.0}]
    )
    with pytest.raises(DataValidationError):
        validate_and_clean_sales_data(bad_date_df)


def test_analytics_modules_and_recommendations() -> None:
    cleaned = validate_and_clean_sales_data(pd.DataFrame(_sample_records())).cleaned_df

    sales = analyze_sales(cleaned)
    assert sales["completed_orders"] == 5
    assert sales["cancelled_orders"] == 1
    assert sales["total_revenue"] == 2480.0

    products = analyze_products(cleaned)
    assert products["best_selling_product"]["product"] == "Mouse"
    assert products["lowest_selling_product"]["product"] == "Keyboard"

    anomalies = detect_anomalies(cleaned)
    assert anomalies["anomaly_count"] >= 1

    trends = analyze_trends(cleaned)
    assert trends["granularity"] == "daily"
    assert len(trends["time_series"]) == 5

    recs = generate_recommendations(sales, products, anomalies, trends)
    assert len(recs) >= 2
    assert all("evidence" in r and len(r["evidence"]) > 0 for r in recs)

    full = run_analysis_from_records(_sample_records())
    assert full["report"]["evaluation"]["passed"] is True
