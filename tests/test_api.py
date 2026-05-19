import csv
from pathlib import Path

from fastapi.testclient import TestClient


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_trigger_join_returns_job_id_and_completes(tmp_path: Path) -> None:
    from app.main import app

    users = tmp_path / "users.csv"
    transactions = tmp_path / "transactions.csv"
    output = tmp_path / "result.csv"

    write_csv(
        users,
        ["user_id", "name", "signup_date"],
        [{"user_id": 1, "name": "Ada", "signup_date": "2020-01-01"}],
    )
    write_csv(
        transactions,
        ["transaction_id", "user_id", "amount"],
        [{"transaction_id": 1, "user_id": 1, "amount": 10.0}],
    )

    client = TestClient(app)
    response = client.post(
        "/trigger-join",
        json={
            "users_path": str(users),
            "transactions_path": str(transactions),
            "output_path": str(output),
            "join_mode": "external_sort",
            "execution_mode": "background_task",
            "chunk_size": 1000,
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    events = client.get(f"/jobs/{job_id}/events").json()["events"]

    assert job["status"] == "completed"
    assert output.exists()
    assert any("Join started" in event["message"] for event in events)
    assert any("Join completed" in event["message"] for event in events)
