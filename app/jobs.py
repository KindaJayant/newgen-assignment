import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import ExecutionMode, JobRecord, JobStatus, JoinMode, TriggerJoinRequest
from app.settings import BASE_DIR, DB_PATH, TMP_DIR, ensure_runtime_dirs
from joiners.duckdb_join import join_csv_with_duckdb
from joiners.external_sort_join import external_sort_join


logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate


class JobStore:
    def __init__(self, db_path: Path = DB_PATH):
        ensure_runtime_dirs()
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    users_path TEXT NOT NULL,
                    transactions_path TEXT NOT NULL,
                    output_path TEXT NOT NULL,
                    join_mode TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_seconds REAL,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )

    def create_job(self, request: TriggerJoinRequest) -> JobRecord:
        job = JobRecord(
            job_id=uuid.uuid4().hex,
            status=JobStatus.queued,
            users_path=str(resolve_path(request.users_path)),
            transactions_path=str(resolve_path(request.transactions_path)),
            output_path=str(resolve_path(request.output_path)),
            join_mode=request.join_mode,
            execution_mode=request.execution_mode,
            created_at=utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id, status, users_path, transactions_path, output_path,
                    join_mode, execution_mode, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.status.value,
                    job.users_path,
                    job.transactions_path,
                    job.output_path,
                    job.join_mode.value,
                    job.execution_mode.value,
                    job.created_at,
                ),
            )
        self.add_event(job.job_id, "INFO", "Job queued")
        return job

    def add_event(self, job_id: str, level: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (job_id, created_at, level, message)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, utc_now(), level, message),
            )

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
        duration_seconds: float | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    started_at = COALESCE(?, started_at),
                    finished_at = COALESCE(?, finished_at),
                    duration_seconds = COALESCE(?, duration_seconds),
                    error = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    started_at,
                    finished_at,
                    duration_seconds,
                    error,
                    job_id,
                ),
            )

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(self) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT created_at, level, message
                FROM job_events
                WHERE job_id = ?
                ORDER BY id ASC
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            status=JobStatus(row["status"]),
            users_path=row["users_path"],
            transactions_path=row["transactions_path"],
            output_path=row["output_path"],
            join_mode=JoinMode(row["join_mode"]),
            execution_mode=ExecutionMode(row["execution_mode"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_seconds=row["duration_seconds"],
            error=row["error"],
        )


def run_join_job(job_id: str, options: dict[str, Any]) -> None:
    store = JobStore()
    store.init_db()

    started_at = utc_now()
    start = time.perf_counter()
    store.update_status(job_id, JobStatus.running, started_at=started_at, error=None)
    store.add_event(job_id, "INFO", "Join started")
    logger.info("Job %s started", job_id)

    try:
        join_mode = JoinMode(options["join_mode"])
        users_path = Path(options["users_path"])
        transactions_path = Path(options["transactions_path"])
        output_path = Path(options["output_path"])

        if join_mode == JoinMode.duckdb:
            rows_written = join_csv_with_duckdb(
                users_path,
                transactions_path,
                output_path,
                memory_limit=options.get("duckdb_memory_limit", "200MB"),
                temp_dir=TMP_DIR / job_id,
            )
        else:
            rows_written = external_sort_join(
                users_path,
                transactions_path,
                output_path,
                temp_dir=TMP_DIR / job_id,
                chunk_size=int(options.get("chunk_size", 100_000)),
            )

        duration = round(time.perf_counter() - start, 3)
        store.update_status(
            job_id,
            JobStatus.completed,
            finished_at=utc_now(),
            duration_seconds=duration,
            error=None,
        )
        message = f"Join completed; wrote {rows_written} rows to {output_path}"
        store.add_event(job_id, "INFO", message)
        logger.info("Job %s completed in %.3fs; rows=%s", job_id, duration, rows_written)
    except Exception as exc:
        duration = round(time.perf_counter() - start, 3)
        store.update_status(
            job_id,
            JobStatus.failed,
            finished_at=utc_now(),
            duration_seconds=duration,
            error=str(exc),
        )
        store.add_event(job_id, "ERROR", f"Join failed: {exc}")
        logger.exception("Job %s failed", job_id)
