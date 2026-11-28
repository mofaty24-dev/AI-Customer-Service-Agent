# DEPI Business Analysis - n8n Automation Bridge

## Run API (from project root, activated venv)
```powershell
pip install -r requirements.txt
uvicorn api:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Test
- GET http://127.0.0.1:8000/health
- POST http://127.0.0.1:8000/analyze with JSON body `{}` to analyze default Data/sales_data.csv
- POST same endpoint with body `{"records":[{"order_id":"A1","date":"2026-01-01","product":"Item","quantity":2,"unit_price":10,"status":"completed"}]}` to analyze supplied records.

## n8n
Import `n8n_workflow.json`. If n8n runs in Docker on the same machine, `host.docker.internal` may work.
If n8n Cloud, localhost/host.docker.internal will not reach your computer: expose the API using a secure tunnel or deploy it publicly with authentication.
Configure the Email node credentials and replace REPLACE_WITH_EMAIL.
