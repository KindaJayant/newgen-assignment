# NewGenesis Assessment Submission

## Repository

GitHub: https://github.com/KindaJayant/newgen-assignment

## Live Demo

Vercel: https://newgenassignment.vercel.app

The Vercel deployment is a lightweight hosted demo using committed sample CSV files and serverless-safe background tasks.

## Local Demo

For the full assignment behavior, including `process_pool`, run locally:

```powershell
pip install -r requirements.txt
python scripts\generate_data.py --users 1000 --transactions 5000 --output-dir data
uvicorn app.main:app --reload
```

Open:

```txt
http://127.0.0.1:8000
```

## What Is Implemented

- Assignment 1: memory-safe CSV inner join on `user_id`.
- Join approach 1: DuckDB with memory limit and disk spill support.
- Join approach 2: pure Python external sort-merge join.
- Assignment 2: non-blocking FastAPI API.
- API approach 1: FastAPI `BackgroundTasks`.
- API approach 2: `ProcessPoolExecutor`.
- SQLite job tracking.
- Job event logs.
- Dashboard frontend.
- Tests for joiners and API.

## Verification

```powershell
pytest
```

Expected:

```txt
3 passed
```
