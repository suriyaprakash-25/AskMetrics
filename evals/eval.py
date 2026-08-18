"""Run the 15 hand-verified Level 5 evaluation queries.

This is a data/evaluation baseline, not the LLM evaluation yet.
The queries are intentionally explicit so that expected answers are independently
verifiable before the natural-language layer is introduced.
"""

from pathlib import Path
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "askmetrics.db"


def money(cents):
    return f"{cents / 100:.2f}"


def fetch(conn, sql):
    return conn.execute(sql).fetchall()


TESTS = [
    {
        "id": 1,
        "question": "How many active users do we have?",
        "sql": "SELECT COUNT(*) FROM users WHERE is_active = 1",
        "expected": [(350,)],
    },
    {
        "id": 2,
        "question": "How many valid orders did we receive in June 2026?",
        "sql": """
            SELECT COUNT(*)
            FROM orders
            WHERE order_date >= '2026-06-01'
              AND order_date < '2026-07-01'
        """,
        "expected": [(308,)],
    },
    {
        "id": 3,
        "question": "How were the June 2026 orders distributed by status?",
        "sql": """
            SELECT status, COUNT(*)
            FROM orders
            WHERE order_date >= '2026-06-01'
              AND order_date < '2026-07-01'
            GROUP BY status
            ORDER BY status
        """,
        "expected": [
            ("cancelled", 37),
            ("delivered", 141),
            ("placed", 38),
            ("returned", 49),
            ("shipped", 43),
        ],
    },
    {
        "id": 4,
        "question": "How much have we given away in discounts?",
        "sql": """
            SELECT currency, SUM(discount_amount_cents)
            FROM orders
            GROUP BY currency
            ORDER BY currency
        """,
        "expected": [
            ("INR", 9631065),
            ("USD", 66779),
        ],
    },
    {
        "id": 5,
        "question": "How much store credit have customers actually spent?",
        "sql": """
            SELECT currency, SUM(wallet_applied_cents)
            FROM payments
            GROUP BY currency
            ORDER BY currency
        """,
        "expected": [
            ("INR", 1583896),
            ("USD", 1008),
        ],
    },
    {
        "id": 6,
        "question": "What is our total revenue?",
        "sql": """
            SELECT currency,
                   SUM(
                       CASE WHEN status = 'captured'
                            THEN amount_cents + wallet_applied_cents
                            ELSE 0 END
                   )
                   -
                   SUM(
                       CASE WHEN status = 'refunded'
                            THEN amount_cents
                            ELSE 0 END
                   ) AS revenue_cents
            FROM payments
            GROUP BY currency
            ORDER BY currency
        """,
        "expected": [
            ("INR", 163100282),
            ("USD", 1099205),
        ],
    },
    {
        "id": 7,
        "question": "Show me revenue month by month for 2026.",
        "sql": """
            SELECT substr(paid_at, 1, 7) AS month,
                   currency,
                   SUM(
                       CASE WHEN status = 'captured'
                            THEN amount_cents + wallet_applied_cents
                            ELSE 0 END
                   )
                   -
                   SUM(
                       CASE WHEN status = 'refunded'
                            THEN amount_cents
                            ELSE 0 END
                   ) AS revenue_cents
            FROM payments
            WHERE substr(paid_at, 1, 4) = '2026'
            GROUP BY month, currency
            ORDER BY month, currency
        """,
        "expected": [
            ("2026-01", "INR", 11079060),
            ("2026-01", "USD", 61938),
            ("2026-02", "INR", 13596643),
            ("2026-02", "USD", 75045),
            ("2026-03", "INR", 11629255),
            ("2026-03", "USD", 90042),
            ("2026-04", "INR", 14391143),
            ("2026-04", "USD", 124629),
            ("2026-05", "INR", 21738429),
            ("2026-05", "USD", 137530),
            ("2026-06", "INR", 22483341),
            ("2026-06", "USD", 151862),
            ("2026-07", "INR", 19080122),
            ("2026-07", "USD", 125993),
            ("2026-08", "INR", -467638),
            ("2026-08", "USD", -5407),
        ],
    },
    {
        "id": 8,
        "question": "Who are the top 10 customers by total amount spent in INR?",
        "sql": """
            SELECT u.user_id, u.full_name,
                   SUM(o.gross_amount_cents - o.discount_amount_cents) AS spent_cents
            FROM users u
            JOIN orders o ON o.user_id = u.user_id
            WHERE o.currency = 'INR'
            GROUP BY u.user_id, u.full_name
            ORDER BY spent_cents DESC, u.user_id
            LIMIT 10
        """,
        "expected": [
            ("U0251", "Fatima Smith", 2264844),
            ("U0042", "Sofia Al-Farsi", 2258994),
            ("U0017", "Rahul Chen", 2241251),
            ("U0168", "Michael Smith", 1912813),
            ("U0386", "Michael Brown", 1892452),
            ("U0178", "Arjun Rao", 1875478),
            ("U0376", "Nikhil Chandra", 1793611),
            ("U0232", "Kavya Chandra", 1770601),
            ("U0140", "Vikram Bose", 1746473),
            ("U0307", "Mei Singh", 1683695),
        ],
    },
    {
        "id": 9,
        "question": "Who are the top 10 customers by total amount spent in USD?",
        "sql": """
            SELECT u.user_id, u.full_name,
                   SUM(o.gross_amount_cents - o.discount_amount_cents) AS spent_cents
            FROM users u
            JOIN orders o ON o.user_id = u.user_id
            WHERE o.currency = 'USD'
            GROUP BY u.user_id, u.full_name
            ORDER BY spent_cents DESC, u.user_id
            LIMIT 10
        """,
        "expected": [
            ("U0067", "Neha Rossi", 21350),
            ("U0281", "Vikram Brown", 19906),
            ("U0120", "Shruti Tanaka", 19265),
            ("U0283", "Neha Chandra", 18824),
            ("U0021", "Wei Wilson", 18231),
            ("U0221", "Emily Garcia", 17753),
            ("U0248", "Shruti Al-Farsi", 17348),
            ("U0306", "Sofia Menon", 17193),
            ("U0056", "Meera Chandra", 17017),
            ("U0418", "Emily Menon", 16493),
        ],
    },
    {
        "id": 10,
        "question": "What is the average order value by customer tier?",
        "sql": """
            SELECT COALESCE(u.tier, 'unknown') AS tier,
                   o.currency,
                   ROUND(AVG(o.gross_amount_cents) / 100.0, 2) AS aov
            FROM orders o
            JOIN users u ON u.user_id = o.user_id
            GROUP BY u.tier, o.currency
            ORDER BY tier, o.currency
        """,
        "expected": [
            ("bronze", "INR", 1796.95),
            ("bronze", "USD", 23.06),
            ("gold", "INR", 1667.15),
            ("gold", "USD", 21.33),
            ("silver", "INR", 1784.23),
            ("silver", "USD", 19.30),
            ("unknown", "INR", 2060.33),
            ("unknown", "USD", 18.36),
        ],
    },
    {
        "id": 11,
        "question": "Which payment method fails most often?",
        "sql": """
            SELECT method, COUNT(*) AS failed_count
            FROM payments
            WHERE status = 'failed'
              AND method IS NOT NULL
            GROUP BY method
            ORDER BY failed_count DESC, method
            LIMIT 1
        """,
        "expected": [("netbanking", 113)],
    },
    {
        "id": 12,
        "question": "How many payment attempts were captured, failed, pending and refunded?",
        "sql": """
            SELECT status, COUNT(*)
            FROM payments
            GROUP BY status
            ORDER BY status
        """,
        "expected": [
            ("captured", 1837),
            ("failed", 501),
            ("pending", 66),
            ("refunded", 357),
        ],
    },
    {
        "id": 13,
        "question": "How many users have never placed an order?",
        "sql": """
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN orders o ON o.user_id = u.user_id
            WHERE o.order_id IS NULL
        """,
        "expected": [(4,)],
    },
    {
        "id": 14,
        "question": "How many orders came through each channel in 2026?",
        "sql": """
            SELECT channel, COUNT(*)
            FROM orders
            WHERE order_date >= '2026-01-01'
              AND order_date < '2027-01-01'
            GROUP BY channel
            ORDER BY channel
        """,
        "expected": [
            ("android", 392),
            ("ios", 369),
            ("web", 759),
        ],
    },
    {
        "id": 15,
        "question": "How much was refunded on returned orders, by currency?",
        "sql": """
            SELECT p.currency,
                   COUNT(DISTINCT o.order_id) AS returned_orders_refunded,
                   SUM(p.amount_cents) AS refund_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'returned'
              AND p.status = 'refunded'
            GROUP BY p.currency
            ORDER BY p.currency
        """,
        "expected": [
            ("INR", 169, 31332688),
            ("USD", 147, 272038),
        ],
    },
]


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run database/load_data.py first.")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    passed = 0

    for test in TESTS:
        actual = fetch(conn, test["sql"])
        expected = test["expected"]
        ok = actual == expected

        if ok:
            passed += 1
            print(f"PASS {test['id']:02d}: {test['question']}")
        else:
            print(f"FAIL {test['id']:02d}: {test['question']}")
            print(f"  expected: {expected}")
            print(f"  actual:   {actual}")

    total = len(TESTS)
    print()
    print(f"Pass rate: {passed}/{total} ({passed / total * 100:.1f}%)")

    conn.close()

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
