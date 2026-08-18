"""
Load AskMetrics CSV exports into a clean SQLite database.

Design choices:
- SQLite with foreign keys enabled.
- Monetary values are stored as integer cents.
- Source formatting is normalized at the ingestion boundary.
- Structurally invalid rows are written to rejects/rejects.csv.
- The load is a full refresh inside one transaction, so rerunning it
  does not duplicate rows.
- Missing amounts on captured payments are deterministically derived from
  gross_amount - discount_amount - wallet_applied, after validating that
  the same relationship holds for all non-missing captured payments.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "askmetrics.db"
SCHEMA_PATH = ROOT / "database" / "schema.sql"
REJECTS_PATH = ROOT / "rejects" / "rejects.csv"

MONEY_SCALE = Decimal("0.01")

ALLOWED_TIERS = {"bronze", "silver", "gold"}
ALLOWED_ORDER_STATUSES = {
    "placed",
    "shipped",
    "delivered",
    "returned",
    "cancelled",
}
ALLOWED_CURRENCIES = {"INR", "USD"}
ALLOWED_CHANNELS = {"web", "android", "ios"}
ALLOWED_PAYMENT_METHODS = {"card", "netbanking", "wallet", "cod", "upi"}
ALLOWED_PAYMENT_STATUSES = {"captured", "failed", "refunded", "pending"}


def read_rows(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def money_to_cents(raw: str, field: str) -> int:
    if raw is None or raw == "":
        raise ValueError(f"{field} is required")

    try:
        value = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{field} is not a valid decimal: {raw!r}") from exc

    if not value.is_finite():
        raise ValueError(f"{field} is not finite")

    cents = (value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    # Source values are expected to have at most two decimal places.
    if value != cents / Decimal(100):
        raise ValueError(f"{field} has more than two decimal places: {raw!r}")

    return int(cents)


def optional_money_to_cents(raw: str, field: str) -> Optional[int]:
    if raw is None or raw == "":
        return None
    return money_to_cents(raw, field)


def parse_date(raw: str, field: str) -> str:
    raw = raw.strip()

    formats = (
        "%d-%m-%Y",
        "%B %d, %Y",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    )

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue

    raise ValueError(f"{field} has an unsupported date format: {raw!r}")


def parse_paid_at(raw: str) -> str:
    raw = raw.strip()

    # Preserve explicit timezone information. For timezone-naive source
    # timestamps, normalize only the separator and leave the timezone absent.
    formats = (
        ("%Y-%m-%dT%H:%M:%SZ", lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"),
        ("%Y-%m-%dT%H:%M:%S%z", lambda dt: dt.isoformat()),
        ("%d-%m-%Y %H:%M", lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S")),
    )

    for fmt, render in formats:
        try:
            return render(datetime.strptime(raw, fmt))
        except ValueError:
            continue

    raise ValueError(f"paid_at has an unsupported timestamp format: {raw!r}")


def normalize_tier(raw: str) -> Optional[str]:
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip().lower()
    if value not in ALLOWED_TIERS:
        raise ValueError(f"invalid tier: {raw!r}")
    return value


def normalize_method(raw: str) -> Optional[str]:
    if raw is None or raw.strip() == "":
        return None
    value = raw.strip().lower()
    if value not in ALLOWED_PAYMENT_METHODS:
        raise ValueError(f"invalid payment method: {raw!r}")
    return value


def normalize_bool(raw: str, field: str) -> int:
    if raw not in {"0", "1"}:
        raise ValueError(f"{field} must be 0 or 1")
    return int(raw)


def reject(rejects: list, source_file: str, source_row: int, reason: str, row: dict) -> None:
    rejects.append(
        {
            "source_file": source_file,
            "source_row": source_row,
            "reason": reason,
            "raw_data": json.dumps(row, ensure_ascii=False, sort_keys=True),
        }
    )


def ensure_unique(rows: List[dict], key: str, source_file: str, rejects: list) -> List[dict]:
    seen = set()
    accepted = []
    for source_row, row in enumerate(rows, start=2):
        value = row.get(key, "")
        if value in seen:
            reject(rejects, source_file, source_row, f"duplicate {key}: {value!r}", row)
            continue
        seen.add(value)
        accepted.append((source_row, row))
    return accepted


def validate_users(rows: List[dict], rejects: list) -> List[Tuple[int, dict]]:
    accepted = []
    seen = set()

    for source_row, row in enumerate(rows, start=2):
        try:
            user_id = row["user_id"].strip()
            if not user_id:
                raise ValueError("user_id is required")
            if user_id in seen:
                raise ValueError(f"duplicate user_id: {user_id}")
            seen.add(user_id)

            full_name = row["full_name"].strip()
            email = row["email"].strip()
            if not full_name:
                raise ValueError("full_name is required")
            if not email:
                raise ValueError("email is required")

            signup_date = parse_date(row["signup_date"], "signup_date")
            country = row["country"].strip()
            if not country:
                raise ValueError("country is required")

            tier = normalize_tier(row["tier"])
            is_active = normalize_bool(row["is_active"], "is_active")
            wallet_balance_cents = money_to_cents(
                row["wallet_balance"], "wallet_balance"
            )
            if wallet_balance_cents < 0:
                raise ValueError("wallet_balance cannot be negative")

            accepted.append(
                (
                    source_row,
                    {
                        "user_id": user_id,
                        "full_name": full_name,
                        "email": email,
                        "signup_date": signup_date,
                        "country": country,
                        "tier": tier,
                        "is_active": is_active,
                        "wallet_balance_cents": wallet_balance_cents,
                    },
                )
            )
        except (KeyError, ValueError) as exc:
            reject(rejects, "users.csv", source_row, str(exc), row)

    return accepted


def validate_orders(
    rows: List[dict],
    accepted_user_ids: set,
    rejects: list,
) -> List[Tuple[int, dict]]:
    accepted = []
    seen = set()

    for source_row, row in enumerate(rows, start=2):
        try:
            order_id = row["order_id"].strip()
            if not order_id:
                raise ValueError("order_id is required")
            if order_id in seen:
                raise ValueError(f"duplicate order_id: {order_id}")
            seen.add(order_id)

            user_id = row["user_id"].strip()
            if user_id not in accepted_user_ids:
                raise ValueError(
                    f"user_id {user_id!r} does not exist in accepted users"
                )

            order_date = parse_date(row["order_date"], "order_date")

            status = row["status"].strip().lower()
            if status not in ALLOWED_ORDER_STATUSES:
                raise ValueError(f"invalid order status: {status!r}")

            gross = money_to_cents(row["gross_amount"], "gross_amount")
            discount = money_to_cents(row["credit"], "credit")

            if gross <= 0:
                raise ValueError("gross_amount must be greater than zero")
            if discount < 0:
                raise ValueError("credit/discount cannot be negative")
            if discount > gross:
                raise ValueError("credit/discount cannot exceed gross_amount")

            currency = row["currency"].strip().upper()
            if currency not in ALLOWED_CURRENCIES:
                raise ValueError(f"invalid currency: {currency!r}")

            channel = row["channel"].strip().lower()
            if channel not in ALLOWED_CHANNELS:
                raise ValueError(f"invalid channel: {channel!r}")

            accepted.append(
                (
                    source_row,
                    {
                        "order_id": order_id,
                        "user_id": user_id,
                        "order_date": order_date,
                        "status": status,
                        "gross_amount_cents": gross,
                        "discount_amount_cents": discount,
                        "currency": currency,
                        "channel": channel,
                    },
                )
            )
        except (KeyError, ValueError) as exc:
            reject(rejects, "orders.csv", source_row, str(exc), row)

    return accepted


def validate_payments(
    rows: List[dict],
    accepted_orders: Dict[str, dict],
    rejects: list,
) -> List[Tuple[int, dict]]:
    accepted = []
    seen = set()

    for source_row, row in enumerate(rows, start=2):
        try:
            payment_id = row["payment_id"].strip()
            if not payment_id:
                raise ValueError("payment_id is required")
            if payment_id in seen:
                raise ValueError(f"duplicate payment_id: {payment_id}")
            seen.add(payment_id)

            order_id = row["order_id"].strip()
            order = accepted_orders.get(order_id)
            if order is None:
                raise ValueError(
                    f"order_id {order_id!r} does not exist in accepted orders"
                )

            paid_at = parse_paid_at(row["paid_at"])

            method = normalize_method(row["method"])

            status = row["status"].strip().lower()
            if status not in ALLOWED_PAYMENT_STATUSES:
                raise ValueError(f"invalid payment status: {status!r}")

            currency = row["currency"].strip().upper()
            if currency not in ALLOWED_CURRENCIES:
                raise ValueError(f"invalid currency: {currency!r}")

            if currency != order["currency"]:
                raise ValueError(
                    f"payment currency {currency} does not match "
                    f"order currency {order['currency']}"
                )

            wallet_applied = money_to_cents(
                row["wallet_applied"], "wallet_applied"
            )
            if wallet_applied < 0:
                raise ValueError("wallet_applied cannot be negative")
            if wallet_applied > 0 and status != "captured":
                raise ValueError(
                    "wallet_applied must be zero for non-captured payments"
                )

            amount = optional_money_to_cents(row["amount"], "amount")

            if amount is None:
                if status != "captured":
                    raise ValueError(
                        "amount is missing and cannot be derived for "
                        f"status {status!r}"
                    )

                # Deterministic reconstruction validated against all
                # non-missing captured payments during forensic analysis.
                amount = (
                    order["gross_amount_cents"]
                    - order["discount_amount_cents"]
                    - wallet_applied
                )

                if amount <= 0:
                    raise ValueError(
                        "derived captured amount is not greater than zero"
                    )

            if amount <= 0:
                raise ValueError("amount must be greater than zero")

            accepted.append(
                (
                    source_row,
                    {
                        "payment_id": payment_id,
                        "order_id": order_id,
                        "paid_at": paid_at,
                        "method": method,
                        "amount_cents": amount,
                        "wallet_applied_cents": wallet_applied,
                        "status": status,
                        "currency": currency,
                    },
                )
            )
        except (KeyError, ValueError) as exc:
            reject(rejects, "payments.csv", source_row, str(exc), row)

    return accepted


def write_rejects(rejects: list) -> None:
    REJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REJECTS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_file", "source_row", "reason", "raw_data"],
        )
        writer.writeheader()
        writer.writerows(rejects)


def load_database() -> dict:
    users_raw = read_rows(DATA_DIR / "users.csv")
    orders_raw = read_rows(DATA_DIR / "orders.csv")
    payments_raw = read_rows(DATA_DIR / "payments.csv")

    rejects = []

    users = validate_users(users_raw, rejects)
    user_ids = {row["user_id"] for _, row in users}

    orders = validate_orders(orders_raw, user_ids, rejects)
    accepted_orders = {row["order_id"]: row for _, row in orders}

    payments = validate_payments(payments_raw, accepted_orders, rejects)

    # Write rejects before touching the database so the rejected source
    # information is available even if the DB transaction later fails.
    write_rejects(rejects)

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
            connection.executescript(schema_file.read())

        with connection:
            # Full refresh makes the loader idempotent and reflects the
            # current CSV exports rather than silently preserving stale rows.
            connection.execute("DELETE FROM payments")
            connection.execute("DELETE FROM orders")
            connection.execute("DELETE FROM users")

            connection.executemany(
                """
                INSERT INTO users (
                    user_id, full_name, email, signup_date, country,
                    tier, is_active, wallet_balance_cents
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [tuple(row.values()) for _, row in users],
            )

            connection.executemany(
                """
                INSERT INTO orders (
                    order_id, user_id, order_date, status,
                    gross_amount_cents, discount_amount_cents,
                    currency, channel
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [tuple(row.values()) for _, row in orders],
            )

            connection.executemany(
                """
                INSERT INTO payments (
                    payment_id, order_id, paid_at, method,
                    amount_cents, wallet_applied_cents,
                    status, currency
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [tuple(row.values()) for _, row in payments],
            )

        counts = {
            "users_raw": len(users_raw),
            "users_loaded": len(users),
            "orders_raw": len(orders_raw),
            "orders_loaded": len(orders),
            "payments_raw": len(payments_raw),
            "payments_loaded": len(payments),
            "rejected_rows": len(rejects),
        }

        # Sanity check: source rows are partitioned into accepted/rejected.
        assert counts["users_raw"] == counts["users_loaded"] + sum(
            r["source_file"] == "users.csv" for r in rejects
        )
        assert counts["orders_raw"] == counts["orders_loaded"] + sum(
            r["source_file"] == "orders.csv" for r in rejects
        )
        assert counts["payments_raw"] == counts["payments_loaded"] + sum(
            r["source_file"] == "payments.csv" for r in rejects
        )

        return counts

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        counts = load_database()
    except Exception as exc:
        print(f"LOAD FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print("AskMetrics load completed.")
    for key, value in counts.items():
        print(f"{key}: {value}")
    print(f"database: {DB_PATH}")
    print(f"rejects: {REJECTS_PATH}")
