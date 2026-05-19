# Scalable Data Processing API

Assignment-ready implementation for joining large CSV datasets without loading them fully into memory, then triggering the join through a non-blocking FastAPI API.

## Direction

The primary join engine is DuckDB because it can scan CSV files lazily, enforce a memory limit, and spill intermediate work to disk. A pure Python external sort-merge join is also included to demonstrate the out-of-core algorithm explicitly.

The API exposes two non-blocking execution approaches:

- `background_task`: FastAPI `BackgroundTasks`, simplest for demos.
- `process_pool`: `ProcessPoolExecutor`, better isolation for CPU-heavy joins.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Generate sample data

```powershell
python scripts\generate_data.py --users 10000 --transactions 25000
```

For full assignment-sized files, run:

```powershell
python scripts\generate_data.py --users 5000000 --transactions 10000000
```

## Run the API

```powershell
uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000
```

## Trigger a job

```powershell
curl -X POST http://127.0.0.1:8000/trigger-join `
  -H "Content-Type: application/json" `
  -d "{\"users_path\":\"data/users.csv\",\"transactions_path\":\"data/transactions.csv\",\"output_path\":\"data/result.csv\",\"join_mode\":\"duckdb\",\"execution_mode\":\"process_pool\"}"
```

Then check:

```powershell
curl http://127.0.0.1:8000/jobs
```

## Run tests

```powershell
pytest
```
