import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_data(users: int, transactions: int, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    users_path = output_dir / "users.csv"
    transactions_path = output_dir / "transactions.csv"

    start = datetime(2020, 1, 1)
    with users_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "name", "signup_date"])
        for user_id in range(1, users + 1):
            signup_date = start + timedelta(minutes=user_id - 1)
            writer.writerow([user_id, f"User_{user_id}", signup_date.isoformat()])

    with transactions_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["transaction_id", "user_id", "amount"])
        for transaction_id in range(1, transactions + 1):
            writer.writerow(
                [
                    transaction_id,
                    random.randint(1, users),
                    round(random.uniform(5.0, 500.0), 2),
                ]
            )

    print(f"Wrote {users_path}")
    print(f"Wrote {transactions_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=10_000)
    parser.add_argument("--transactions", type=int, default=25_000)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    generate_data(args.users, args.transactions, args.output_dir)


if __name__ == "__main__":
    main()
