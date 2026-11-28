DEPI Business / Sales Analysis
Run the API
Open a terminal in the business_analysis directory.
If your virtual environment is not active, activate it from this directory using PowerShell:
..\.venv\Scripts\Activate.ps1

Install the required packages:
pip install -r requirements.txt

Start the API:
uvicorn api:app --reload

API documentation: http://127.0.0.1:8000/docs
Test the API

Health check: GET http://127.0.0.1:8000/health
Analyze the default CSV file: POST http://127.0.0.1:8000/analyze with an empty JSON body {}.
Analyze custom records: send this JSON body to POST /analyze:

{
  "records": [
    {
      "order_id": "A1",
      "date": "2026-01-01",
      "product": "Item",
      "quantity": 2,
      "unit_price": 10,
      "status": "completed"
    }
  ]
}

n8n Automation
Import the workflow file business_analyst.json into n8n.
In the Call Analytics API node, replace the placeholder API URL with your currently active public API URL:
https://REPLACE_WITH_YOUR_PUBLIC_API_URL/analyze
For n8n Cloud, a local address such as localhost will not reach your computer. You must expose the API through a secure tunnel or deploy it to a public server.
If you use a temporary Cloudflare Tunnel URL, remember that it may change when the tunnel restarts.
Configure the OpenAI credentials for the AI Business Analyst node before running the workflow.
The workflow currently uses a Manual Trigger, so you need to execute it manually in n8n.
Security note: The API does not currently include authentication. Use temporary access for project demonstrations only; add authentication before production deployment.
