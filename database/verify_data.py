"""Run structural and forensic checks against the loaded AskMetrics database."""

from pathlib import Path
from decimal import Decimal
import csv
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "askmetrics.db"
REJECTS_PATH = ROOT / "rejects" / "rejects.csv"

EXPECTED = {
    "users": 434,
    "orders": 2100,
    "payments": 2761,
    "rejected_users": 0,
    "rejected_orders": 23,
    "rejected_payments": 44,
    "active_users": 350,
    "june_2026_orders": 308,
    "discount_inr_cents": 9631065,
    "discount_usd_cents": 66779,
}


def scalar(conn, query):
    return conn.execute(query).fetchone()[0]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    for table in ("users", "orders", "payments"):
        actual = scalar(conn, f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {actual}")
        assert actual == EXPECTED[table]

    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"foreign_key_violations: {len(fk_violations)}")
    assert not fk_violations

    checks = {
        "duplicate_users": """
            SELECT COUNT(*) FROM (
                SELECT user_id FROM users GROUP BY user_id HAVING COUNT(*) > 1
            )
        """,
        "duplicate_orders": """
            SELECT COUNT(*) FROM (
                SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1
            )
        """,
        "duplicate_payments": """
            SELECT COUNT(*) FROM (
                SELECT payment_id FROM payments GROUP BY payment_id HAVING COUNT(*) > 1
            )
        """,
        "negative_user_wallet": """
            SELECT COUNT(*) FROM users WHERE wallet_balance_cents < 0
        """,
        "invalid_tier": """
            SELECT COUNT(*) FROM users
            WHERE tier IS NOT NULL
              AND tier NOT IN ('bronze', 'silver', 'gold')
        """,
        "invalid_order_status": """
            SELECT COUNT(*) FROM orders
            WHERE status NOT IN ('placed','shipped','delivered','returned','cancelled')
        """,
        "invalid_payment_status": """
            SELECT COUNT(*) FROM payments
            WHERE status NOT IN ('captured','failed','refunded','pending')
        """,
        "payment_currency_mismatch": """
            SELECT COUNT(*)
            FROM payments p
            JOIN orders o ON o.order_id = p.order_id
            WHERE p.currency <> o.currency
        """,
        "negative_money": """
            SELECT
                (SELECT COUNT(*) FROM users WHERE wallet_balance_cents < 0) +
                (SELECT COUNT(*) FROM orders
                 WHERE gross_amount_cents < 0 OR discount_amount_cents < 0) +
                (SELECT COUNT(*) FROM payments
                 WHERE amount_cents < 0 OR wallet_applied_cents < 0)
        """,
    }

    for name, query in checks.items():
        value = scalar(conn, query)
        print(f"{name}: {value}")
        assert value == 0

    active_users = scalar(conn, "SELECT COUNT(*) FROM users WHERE is_active = 1")
    print(f"active_users: {active_users}")
    assert active_users == EXPECTED["active_users"]

    june_orders = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM orders
        WHERE order_date >= '2026-06-01'
          AND order_date < '2026-07-01'
        """,
    )
    print(f"june_2026_orders: {june_orders}")
    assert june_orders == EXPECTED["june_2026_orders"]

    discount_inr = scalar(
        conn,
        "SELECT COALESCE(SUM(discount_amount_cents), 0) FROM orders WHERE currency='INR'",
    )
    discount_usd = scalar(
        conn,
        "SELECT COALESCE(SUM(discount_amount_cents), 0) FROM orders WHERE currency='USD'",
    )
    print(f"discount_inr_cents: {discount_inr}")
    print(f"discount_usd_cents: {discount_usd}")
    assert discount_inr == EXPECTED["discount_inr_cents"]
    assert discount_usd == EXPECTED["discount_usd_cents"]

    # The key forensic accounting identity:
    # captured amount + wallet applied = gross amount - discount.
    # The 46 source-missing captured amounts were derived from this identity.
    identity_failures = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM payments p
        JOIN orders o ON o.order_id = p.order_id
        WHERE p.status = 'captured'
          AND p.amount_cents + p.wallet_applied_cents
              <> o.gross_amount_cents - o.discount_amount_cents
        """,
    )
    print(f"captured_payment_identity_failures: {identity_failures}")
    assert identity_failures == 0

    # Count payments where amount was derived is tracked by the rejects/raw
    # comparison in the loader; no database column is added merely for provenance.
    print("captured payment accounting identity: PASS")

    with REJECTS_PATH.open("r", encoding="utf-8", newline="") as handle:
        reject_rows = list(csv.DictReader(handle))

    reject_counts = {}
    for row in reject_rows:
        reject_counts[row["source_file"]] = reject_counts.get(row["source_file"], 0) + 1

    print(f"reject_counts: {reject_counts}")
    assert reject_counts.get("users.csv", 0) == EXPECTED["rejected_users"]
    assert reject_counts.get("orders.csv", 0) == EXPECTED["rejected_orders"]
    assert reject_counts.get("payments.csv", 0) == EXPECTED["rejected_payments"]

    conn.close()
    print("All Level 4 checks passed.")


if __name__ == "__main__":
    main()
