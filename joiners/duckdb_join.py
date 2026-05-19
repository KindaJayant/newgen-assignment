from pathlib import Path

import duckdb


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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
        connection.execute(f"SET memory_limit = {_sql_literal(memory_limit)}")
        if temp_dir is not None:
            connection.execute(f"SET temp_directory = {_sql_literal(temp_dir)}")

        connection.execute(
            f"""
            COPY (
                SELECT
                    u.user_id,
                    u.name,
                    u.signup_date,
                    t.transaction_id,
                    t.amount
                FROM read_csv_auto({_sql_literal(users)}, header = true) AS u
                INNER JOIN read_csv_auto({_sql_literal(transactions)}, header = true) AS t
                    ON u.user_id = t.user_id
                ORDER BY u.user_id, t.transaction_id
            )
            TO {_sql_literal(output)}
            WITH (HEADER, DELIMITER ',')
            """
        )

        count = connection.execute(
            f"SELECT COUNT(*) FROM read_csv_auto({_sql_literal(output)}, header = true)",
        ).fetchone()[0]

    return int(count)
