from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.jobs import JobStore, run_join_job
from app.logging_config import configure_logging
from app.models import (
    ExecutionMode,
    JobRecord,
    TriggerJoinRequest,
    TriggerJoinResponse,
)
from app.settings import IS_VERCEL, STATIC_DIR, ensure_runtime_dirs


configure_logging()
ensure_runtime_dirs()

store = JobStore()
store.init_db()
executor = None if IS_VERCEL else ProcessPoolExecutor(max_workers=1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        yield
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=False)


app = FastAPI(
    title="Scalable Data Processing API",
    description="Non-blocking API for memory-safe CSV joins.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict[str, str]:
    if IS_VERCEL:
        return {
            "users_path": "sample_data/users.csv",
            "transactions_path": "sample_data/transactions.csv",
            "output_path": "/tmp/result.csv",
            "execution_mode": "background_task",
        }
    return {
        "users_path": "data/users.csv",
        "transactions_path": "data/transactions.csv",
        "output_path": "data/result.csv",
        "execution_mode": "process_pool",
    }


@app.post("/trigger-join", response_model=TriggerJoinResponse)
def trigger_join(
    request: TriggerJoinRequest,
    background_tasks: BackgroundTasks,
) -> TriggerJoinResponse:
    job = store.create_job(request)
    options = {
        "users_path": job.users_path,
        "transactions_path": job.transactions_path,
        "output_path": job.output_path,
        "join_mode": job.join_mode.value,
        "execution_mode": job.execution_mode.value,
        "duckdb_memory_limit": request.duckdb_memory_limit,
        "chunk_size": request.chunk_size,
    }

    if request.execution_mode == ExecutionMode.background_task or executor is None:
        background_tasks.add_task(run_join_job, job.job_id, options)
    else:
        executor.submit(run_join_job, job.job_id, options)

    return TriggerJoinResponse(
        job_id=job.job_id,
        status=job.status,
        message="Join job queued. Use the job_id to check status.",
    )


@app.get("/jobs", response_model=list[JobRecord])
def list_jobs() -> list[JobRecord]:
    return store.list_jobs()


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}/events")
def get_job_events(job_id: str) -> dict[str, object]:
    if store.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "events": store.list_events(job_id)}
