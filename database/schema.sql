PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    signup_date TEXT NOT NULL,
    country TEXT NOT NULL,
    tier TEXT,
    is_active INTEGER NOT NULL
        CHECK (is_active IN (0, 1)),
    wallet_balance_cents INTEGER NOT NULL
        CHECK (wallet_balance_cents >= 0),
    CHECK (
        tier IS NULL
        OR tier IN ('bronze', 'silver', 'gold')
    )
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES users(user_id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (
            status IN (
                'placed',
                'shipped',
                'delivered',
                'returned',
                'cancelled'
            )
        ),
    gross_amount_cents INTEGER NOT NULL
        CHECK (gross_amount_cents > 0),
    discount_amount_cents INTEGER NOT NULL
        CHECK (
            discount_amount_cents >= 0
            AND discount_amount_cents <= gross_amount_cents
        ),
    currency TEXT NOT NULL
        CHECK (currency IN ('INR', 'USD')),
    channel TEXT NOT NULL
        CHECK (channel IN ('web', 'android', 'ios')),
    UNIQUE (order_id, currency)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    paid_at TEXT NOT NULL,
    method TEXT,
    amount_cents INTEGER NOT NULL
        CHECK (amount_cents > 0),
    wallet_applied_cents INTEGER NOT NULL
        CHECK (wallet_applied_cents >= 0),
    status TEXT NOT NULL
        CHECK (
            status IN (
                'captured',
                'failed',
                'refunded',
                'pending'
            )
        ),
    currency TEXT NOT NULL
        CHECK (currency IN ('INR', 'USD')),
    FOREIGN KEY (order_id, currency)
        REFERENCES orders(order_id, currency),
    CHECK (
        wallet_applied_cents = 0
        OR status = 'captured'
    )
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id
    ON orders(user_id);

CREATE INDEX IF NOT EXISTS idx_orders_order_date
    ON orders(order_date);

CREATE INDEX IF NOT EXISTS idx_orders_currency_order_date
    ON orders(currency, order_date);

CREATE INDEX IF NOT EXISTS idx_orders_status
    ON orders(status);

CREATE INDEX IF NOT EXISTS idx_payments_order_id
    ON payments(order_id);

CREATE INDEX IF NOT EXISTS idx_payments_status_paid_at
    ON payments(status, paid_at);

CREATE INDEX IF NOT EXISTS idx_payments_status_method
    ON payments(status, method);
