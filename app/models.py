from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JoinMode(str, Enum):
    duckdb = "duckdb"
    external_sort = "external_sort"


class ExecutionMode(str, Enum):
    background_task = "background_task"
    process_pool = "process_pool"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TriggerJoinRequest(BaseModel):
    users_path: str = Field(default="data/users.csv")
    transactions_path: str = Field(default="data/transactions.csv")
    output_path: str = Field(default="data/result.csv")
    join_mode: JoinMode = JoinMode.duckdb
    execution_mode: ExecutionMode = ExecutionMode.process_pool
    duckdb_memory_limit: str = "200MB"
    chunk_size: int = Field(default=100_000, ge=1_000, le=1_000_000)


class TriggerJoinResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    users_path: str
    transactions_path: str
    output_path: str
    join_mode: JoinMode
    execution_mode: ExecutionMode
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
