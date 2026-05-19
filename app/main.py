from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager
import shutil
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.jobs import JobStore, run_join_job
from app.logging_config import configure_logging
from app.models import (
    ExecutionMode,
    JobRecord,
    TriggerJoinRequest,
    TriggerJoinResponse,
    UploadResponse,
)
from app.settings import DATA_DIR, IS_VERCEL, STATIC_DIR, ensure_runtime_dirs


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


@app.post("/upload-csv", response_model=UploadResponse)
def upload_csv(
    dataset: str = Form(...),
    file: UploadFile = File(...),
) -> UploadResponse:
    if dataset not in {"users", "transactions"}:
        raise HTTPException(status_code=400, detail="dataset must be users or transactions")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    upload_dir = DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name.replace(" ", "_")
    saved_path = upload_dir / f"{dataset}_{safe_name}"

    with saved_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    return UploadResponse(
        filename=file.filename,
        saved_path=str(saved_path),
        message=f"Uploaded {dataset} CSV",
    )


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
