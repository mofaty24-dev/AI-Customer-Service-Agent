from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"order_id", "date", "product", "quantity", "unit_price"}

COLUMN_ALIASES = {
    "order_date": "date",
    "transaction_date": "date",
    "product_name": "product",
    "item": "product",
    "item_name": "product",
    "qty": "quantity",
    "price": "unit_price",
    "order_status": "status",
}


class DataValidationError(Exception):
    """Raised when incoming sales data fails critical schema or quality validation."""

    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or [message]


@dataclass
class ValidationResult:
    cleaned_df: pd.DataFrame
    initial_rows: int
    valid_rows: int
    deduplicated_rows: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": True,
            "initial_rows": self.initial_rows,
            "valid_rows": self.valid_rows,
            "deduplicated_rows": self.deduplicated_rows,
            "warnings": self.warnings,
        }


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        clean_col = str(col).strip().lower()
        renamed[col] = COLUMN_ALIASES.get(clean_col, clean_col)
    return df.rename(columns=renamed)


def load_csv_file(csv_path: str | Path) -> pd.DataFrame:
    """Safely load a CSV file into a pandas DataFrame."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Sales data file not found: {path}")
    if path.stat().st_size == 0:
        raise DataValidationError(f"Sales data file is empty: {path}")
    return pd.read_csv(path)


def validate_and_clean_sales_data(df: pd.DataFrame) -> ValidationResult:
    """Validate schema, dates, quantities, prices, missing values, and duplicates."""
    if df is None or not isinstance(df, pd.DataFrame):
        raise DataValidationError("Input must be a valid tabular dataset.")

    if df.empty:
        raise DataValidationError("Sales dataset contains zero rows.")

    working_df = _normalize_columns(df.copy())
    initial_rows = len(working_df)
    warnings: list[str] = []
    issues: list[str] = []

    missing_cols = sorted(REQUIRED_COLUMNS - set(working_df.columns))
    if missing_cols:
        raise DataValidationError(
            f"Missing required columns: {', '.join(missing_cols)}",
            issues=[f"Missing required column: {col}" for col in missing_cols],
        )

    # Check missing values in required columns
    for col in sorted(REQUIRED_COLUMNS):
        null_mask = working_df[col].isna() | (working_df[col].astype(str).str.strip() == "")
        if null_mask.any():
            bad_rows = [int(i) + 1 for i in working_df.index[null_mask].tolist()]
            issues.append(f"Column '{col}' has missing values at row(s): {bad_rows}")

    if issues:
        raise DataValidationError("Dataset contains missing required values.", issues=issues)

    # Clean string fields
    working_df["order_id"] = working_df["order_id"].astype(str).str.strip()
    working_df["product"] = working_df["product"].astype(str).str.strip()

    if "category" not in working_df.columns:
        working_df["category"] = "General"
        warnings.append("Column 'category' was absent; defaulted to 'General'.")
    else:
        working_df["category"] = working_df["category"].fillna("General").astype(str).str.strip()
        working_df.loc[working_df["category"] == "", "category"] = "General"

    if "status" not in working_df.columns:
        working_df["status"] = "completed"
        warnings.append("Column 'status' was absent; defaulted to 'completed'.")
    else:
        working_df["status"] = working_df["status"].fillna("completed").astype(str).str.strip().str.lower()
        working_df.loc[working_df["status"] == "", "status"] = "completed"

    if "region" not in working_df.columns:
        working_df["region"] = "Unknown"
    else:
        working_df["region"] = working_df["region"].fillna("Unknown").astype(str).str.strip()
        working_df.loc[working_df["region"] == "", "region"] = "Unknown"

    # Validate dates
    parsed_dates = pd.to_datetime(working_df["date"], errors="coerce")
    invalid_date_mask = parsed_dates.isna()
    if invalid_date_mask.any():
        bad_rows = [int(i) + 1 for i in working_df.index[invalid_date_mask].tolist()]
        issues.append(f"Invalid date format detected at row(s): {bad_rows}")
    else:
        working_df["date"] = parsed_dates

    # Validate quantity and unit_price
    qty_num = pd.to_numeric(working_df["quantity"], errors="coerce")
    invalid_qty_mask = qty_num.isna() | (qty_num <= 0)
    if invalid_qty_mask.any():
        bad_rows = [int(i) + 1 for i in working_df.index[invalid_qty_mask].tolist()]
        issues.append(f"Quantity must be a positive number (> 0); invalid at row(s): {bad_rows}")

    price_num = pd.to_numeric(working_df["unit_price"], errors="coerce")
    invalid_price_mask = price_num.isna() | (price_num <= 0)
    if invalid_price_mask.any():
        bad_rows = [int(i) + 1 for i in working_df.index[invalid_price_mask].tolist()]
        issues.append(f"Unit price must be a positive number (> 0); invalid at row(s): {bad_rows}")

    if issues:
        raise DataValidationError("Data validation failed due to invalid field values.", issues=issues)

    working_df["quantity"] = qty_num.astype(float)
    working_df["unit_price"] = price_num.astype(float)

    # Deduplicate exact duplicate records
    dedup_subset = ["order_id", "date", "product", "quantity", "unit_price", "status"]
    if "order_line_id" in working_df.columns:
        dedup_subset.append("order_line_id")

    before_dedup = len(working_df)
    working_df = working_df.drop_duplicates(subset=dedup_subset, keep="first").reset_index(drop=True)
    deduplicated_rows = before_dedup - len(working_df)
    if deduplicated_rows > 0:
        warnings.append(f"Removed {deduplicated_rows} duplicate record(s).")

    # Compute line revenue
    working_df["revenue"] = (working_df["quantity"] * working_df["unit_price"]).round(2)

    return ValidationResult(
        cleaned_df=working_df,
        initial_rows=initial_rows,
        valid_rows=len(working_df),
        deduplicated_rows=deduplicated_rows,
        warnings=warnings,
    )
