from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
TMP_DIR = BASE_DIR / "tmp"
DB_PATH = DATA_DIR / "jobs.sqlite3"


def ensure_runtime_dirs() -> None:
    for path in (DATA_DIR, LOG_DIR, STATIC_DIR, TMP_DIR):
        path.mkdir(parents=True, exist_ok=True)
