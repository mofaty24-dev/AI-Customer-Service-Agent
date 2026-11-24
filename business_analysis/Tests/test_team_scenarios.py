import pytest

from Source_Code.main import run_analysis_from_records
from Source_Code.validators import DataValidationError


def test_column_aliases_and_default_optional_fields() -> None:
    records = [
        {
            "order_id": "A-1",
            "order_date": "2026-11-01",
            "item": "USB Cable",
            "qty": 4,
            "price": 15.0,
        },
        {
            "order_id": "A-2",
            "order_date": "2026-11-02",
            "item": "Webcam",
            "qty": 2,
            "price": 75.0,
        },
    ]

    result = run_analysis_from_records(records)
    assert result["status"] == "success"
    assert result["validation"]["valid_rows"] == 2
    assert result["sales_analytics"]["total_revenue"] == 210.0
    assert result["report"]["evaluation"]["passed"] is True


def test_empty_records_raises_validation_error() -> None:
    with pytest.raises(DataValidationError):
        run_analysis_from_records([])
