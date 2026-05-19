import csv
from pathlib import Path

from joiners.duckdb_join import join_csv_with_duckdb
from joiners.external_sort_join import external_sort_join


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sample_files(tmp_path: Path) -> tuple[Path, Path]:
    users = tmp_path / "users.csv"
    transactions = tmp_path / "transactions.csv"
    write_csv(
        users,
        ["user_id", "name", "signup_date"],
        [
            {"user_id": 1, "name": "Ada", "signup_date": "2020-01-01"},
            {"user_id": 2, "name": "Linus", "signup_date": "2020-01-02"},
            {"user_id": 3, "name": "Grace", "signup_date": "2020-01-03"},
        ],
    )
    write_csv(
        transactions,
        ["transaction_id", "user_id", "amount"],
        [
            {"transaction_id": 10, "user_id": 2, "amount": 25.5},
            {"transaction_id": 11, "user_id": 1, "amount": 12.0},
            {"transaction_id": 12, "user_id": 2, "amount": 8.25},
            {"transaction_id": 13, "user_id": 99, "amount": 100.0},
        ],
    )
    return users, transactions


def test_duckdb_join_writes_inner_join_result(tmp_path: Path) -> None:
    users, transactions = sample_files(tmp_path)
    output = tmp_path / "duckdb_result.csv"

    rows_written = join_csv_with_duckdb(
        users,
        transactions,
        output,
        memory_limit="128MB",
        temp_dir=tmp_path / "duckdb_tmp",
    )

    rows = read_rows(output)
    assert rows_written == 3
    assert [row["user_id"] for row in rows] == ["1", "2", "2"]
    assert [row["transaction_id"] for row in rows] == ["11", "10", "12"]


def test_external_sort_join_writes_inner_join_result(tmp_path: Path) -> None:
    users, transactions = sample_files(tmp_path)
    output = tmp_path / "external_sort_result.csv"

    rows_written = external_sort_join(
        users,
        transactions,
        output,
        temp_dir=tmp_path / "external_tmp",
        chunk_size=2,
    )

    rows = read_rows(output)
    assert rows_written == 3
    assert [row["user_id"] for row in rows] == ["1", "2", "2"]
    assert [row["transaction_id"] for row in rows] == ["11", "10", "12"]
