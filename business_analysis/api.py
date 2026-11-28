from __future__ import annotations

from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from Source_Code.main import run_analysis_from_csv, run_analysis_from_records
from Source_Code.validators import DataValidationError

app = FastAPI(
    title="DEPI Business / Sales Analysis API",
    description="API wrapper for the existing Python business analysis engine.",
    version="1.0.0",
)

class AnalyzeRequest(BaseModel):
    records: list[dict[str, Any]] | None = Field(default=None, description="Sales records as JSON objects")

@app.get("/")
def home():
    return {"status": "online", "service": "DEPI Business Analysis API"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        if request.records is not None:
            result = run_analysis_from_records(request.records)
        else:
            result = run_analysis_from_csv()
        return result
    except (DataValidationError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Analysis failed unexpectedly.") from exc
