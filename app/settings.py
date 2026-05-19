import os
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
IS_VERCEL = os.getenv("VERCEL") == "1"

DATA_DIR = BASE_DIR / "data"
RUNTIME_DIR = Path(tempfile.gettempdir()) / "newgen_assignment" if IS_VERCEL else BASE_DIR
LOG_DIR = RUNTIME_DIR / "logs"
TMP_DIR = RUNTIME_DIR / "tmp"
DB_PATH = DATA_DIR / "jobs.sqlite3"
if IS_VERCEL:
    DB_PATH = TMP_DIR / "jobs.sqlite3"


def ensure_runtime_dirs() -> None:
    paths = [LOG_DIR, STATIC_DIR, TMP_DIR]
    if not IS_VERCEL:
        paths.append(DATA_DIR)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
