from pathlib import Path

from Source_Code.main import PROJECT_ROOT, run_analysis_from_csv


def test_project_structure_exists() -> None:
    expected_files = [
        "Source_Code/main.py",
        "Source_Code/sales_analytics.py",
        "Source_Code/product_analysis.py",
        "Source_Code/anomaly_detector.py",
        "Source_Code/trends_analysis.py",
        "Source_Code/recommendations.py",
        "Source_Code/validators.py",
        "Source_Code/report_generator.py",
        "Data/sales_data.csv",
        "requirements.txt",
    ]
    for rel_path in expected_files:
        assert (PROJECT_ROOT / rel_path).exists(), f"Missing expected file: {rel_path}"


def test_end_to_end_sample_dataset_pipeline() -> None:
    sample_csv = PROJECT_ROOT / "Data" / "sales_data.csv"
    assert Path(sample_csv).exists()

    result = run_analysis_from_csv(sample_csv)
    assert result["status"] == "success"
    assert result["validation"]["valid_rows"] > 10
    assert result["sales_analytics"]["total_revenue"] > 0
    assert len(result["recommendations"]) > 0
    assert result["report"]["evaluation"]["passed"] is True
