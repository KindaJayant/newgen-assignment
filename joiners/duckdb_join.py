from pathlib import Path

import duckdb


def join_csv_with_duckdb(
    users_path: str | Path,
    transactions_path: str | Path,
    output_path: str | Path,
    memory_limit: str = "200MB",
    temp_dir: str | Path | None = None,
) -> int:
    users = Path(users_path)
    transactions = Path(transactions_path)
    output = Path(output_path)

    if not users.exists():
        raise FileNotFoundError(f"Users file not found: {users}")
    if not transactions.exists():
        raise FileNotFoundError(f"Transactions file not found: {transactions}")

    output.parent.mkdir(parents=True, exist_ok=True)
    if temp_dir is not None:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

    with duckdb.connect(database=":memory:") as connection:
        connection.execute("SET memory_limit = ?", [memory_limit])
        if temp_dir is not None:
            connection.execute("SET temp_directory = ?", [str(temp_dir)])

        connection.execute(
            """
            COPY (
                SELECT
                    u.user_id,
                    u.name,
                    u.signup_date,
                    t.transaction_id,
                    t.amount
                FROM read_csv_auto(?, header = true) AS u
                INNER JOIN read_csv_auto(?, header = true) AS t
                    ON u.user_id = t.user_id
                ORDER BY u.user_id, t.transaction_id
            )
            TO ?
            WITH (HEADER, DELIMITER ',')
            """,
            [str(users), str(transactions), str(output)],
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM read_csv_auto(?, header = true)",
            [str(output)],
        ).fetchone()[0]

    return int(count)
