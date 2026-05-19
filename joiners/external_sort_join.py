import csv
import heapq
import itertools
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path


def _key_value(row: dict[str, str], key: str) -> tuple[int, str]:
    value = row[key]
    try:
        return (0, f"{int(value):020d}")
    except ValueError:
        return (1, value)


def _write_chunk(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    key: str,
    chunk_path: Path,
) -> None:
    rows.sort(key=lambda row: _key_value(row, key))
    with chunk_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sort_csv_chunks(
    input_path: Path,
    key: str,
    temp_dir: Path,
    chunk_size: int,
    prefix: str,
) -> tuple[list[Path], list[str]]:
    chunk_paths: list[Path] = []
    with input_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {input_path}")
        if key not in reader.fieldnames:
            raise ValueError(f"CSV {input_path} is missing key column: {key}")

        fieldnames = list(reader.fieldnames)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append(row)
            if len(rows) >= chunk_size:
                chunk_path = temp_dir / f"{prefix}_{len(chunk_paths):04d}.csv"
                _write_chunk(rows, fieldnames, key, chunk_path)
                chunk_paths.append(chunk_path)
                rows = []

        if rows:
            chunk_path = temp_dir / f"{prefix}_{len(chunk_paths):04d}.csv"
            _write_chunk(rows, fieldnames, key, chunk_path)
            chunk_paths.append(chunk_path)

    return chunk_paths, fieldnames


def _merged_rows(chunk_paths: list[Path], key: str) -> Iterator[dict[str, str]]:
    handles = [path.open("r", newline="", encoding="utf-8") for path in chunk_paths]
    try:
        readers = [csv.DictReader(handle) for handle in handles]
        heap: list[tuple[tuple[int, str], int, dict[str, str], int]] = []
        counter = itertools.count()

        for index, reader in enumerate(readers):
            try:
                row = next(reader)
            except StopIteration:
                continue
            heapq.heappush(heap, (_key_value(row, key), next(counter), row, index))

        while heap:
            _, _, row, index = heapq.heappop(heap)
            yield row
            try:
                next_row = next(readers[index])
            except StopIteration:
                continue
            heapq.heappush(
                heap,
                (_key_value(next_row, key), next(counter), next_row, index),
            )
    finally:
        for handle in handles:
            handle.close()


def _grouped_by_key(
    rows: Iterator[dict[str, str]],
    key: str,
) -> Iterator[tuple[tuple[int, str], list[dict[str, str]]]]:
    current_key: tuple[int, str] | None = None
    group: list[dict[str, str]] = []

    for row in rows:
        row_key = _key_value(row, key)
        if current_key is None:
            current_key = row_key
        if row_key != current_key:
            yield current_key, group
            current_key = row_key
            group = []
        group.append(row)

    if current_key is not None:
        yield current_key, group


def _numeric_sort_value(row: dict[str, str], key: str) -> tuple[int, str]:
    value = row.get(key, "")
    try:
        return (0, f"{int(value):020d}")
    except ValueError:
        return (1, value)


def external_sort_join(
    users_path: str | Path,
    transactions_path: str | Path,
    output_path: str | Path,
    temp_dir: str | Path | None = None,
    chunk_size: int = 100_000,
) -> int:
    users = Path(users_path)
    transactions = Path(transactions_path)
    output = Path(output_path)

    if not users.exists():
        raise FileNotFoundError(f"Users file not found: {users}")
    if not transactions.exists():
        raise FileNotFoundError(f"Transactions file not found: {transactions}")

    output.parent.mkdir(parents=True, exist_ok=True)
    root_temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="csv_join_"))
    work_dir = root_temp_dir / "external_sort"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        user_chunks, _ = _sort_csv_chunks(users, "user_id", work_dir, chunk_size, "users")
        transaction_chunks, _ = _sort_csv_chunks(
            transactions,
            "user_id",
            work_dir,
            chunk_size,
            "transactions",
        )

        user_groups = _grouped_by_key(_merged_rows(user_chunks, "user_id"), "user_id")
        transaction_groups = _grouped_by_key(
            _merged_rows(transaction_chunks, "user_id"),
            "user_id",
        )

        output_fields = [
            "user_id",
            "name",
            "signup_date",
            "transaction_id",
            "amount",
        ]
        rows_written = 0

        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=output_fields)
            writer.writeheader()

            try:
                user_key, users_for_key = next(user_groups)
                transaction_key, transactions_for_key = next(transaction_groups)
            except StopIteration:
                return 0

            while True:
                if user_key == transaction_key:
                    ordered_users = sorted(
                        users_for_key,
                        key=lambda row: _numeric_sort_value(row, "user_id"),
                    )
                    ordered_transactions = sorted(
                        transactions_for_key,
                        key=lambda row: _numeric_sort_value(row, "transaction_id"),
                    )
                    for user in ordered_users:
                        for transaction in ordered_transactions:
                            writer.writerow(
                                {
                                    "user_id": user["user_id"],
                                    "name": user.get("name", ""),
                                    "signup_date": user.get("signup_date", ""),
                                    "transaction_id": transaction.get("transaction_id", ""),
                                    "amount": transaction.get("amount", ""),
                                }
                            )
                            rows_written += 1
                    try:
                        user_key, users_for_key = next(user_groups)
                        transaction_key, transactions_for_key = next(transaction_groups)
                    except StopIteration:
                        break
                elif user_key < transaction_key:
                    try:
                        user_key, users_for_key = next(user_groups)
                    except StopIteration:
                        break
                else:
                    try:
                        transaction_key, transactions_for_key = next(transaction_groups)
                    except StopIteration:
                        break

        return rows_written
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if temp_dir is None:
            shutil.rmtree(root_temp_dir, ignore_errors=True)
