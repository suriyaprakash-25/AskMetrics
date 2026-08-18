# Data & Ingestion Decisions

## Scope

This document records the decisions made while turning the three raw CSV exports into a relational SQLite database.

The raw exports are intentionally inconsistent. We normalize formatting at ingestion, preserve missing business information where it cannot be safely inferred, and reject rows that cannot satisfy the relational model.

## Database

SQLite was chosen because the supplied dataset is small (434 users, 2,123 orders, 2,805 payment attempts) and a self-contained database makes the assessment reproducible on a clean machine.

If this workload were roughly 1,000x larger or required many concurrent analytical users, PostgreSQL would be the next choice.

## Schema decisions

### users

- `user_id`: `TEXT PRIMARY KEY`. The source IDs are unique and stable (`U0001` ... `U0434`).
- `full_name`: `TEXT NOT NULL`. Names are not unique, so no uniqueness constraint.
- `email`: `TEXT NOT NULL`. Leading/trailing whitespace is removed. Email is not unique because normalized duplicate addresses occur across different user IDs in the source.
- `signup_date`: normalized to ISO `YYYY-MM-DD`. The source contains three date representations. The source time component in ISO-formatted rows is not retained because the field is semantically a signup *date* and most rows contain no time.
- `country`: `TEXT NOT NULL`.
- `tier`: nullable `TEXT`. Case variants are normalized to `bronze`, `silver`, or `gold`. Missing tiers remain NULL rather than being invented.
- `is_active`: `INTEGER` restricted to 0/1.
- `wallet_balance_cents`: integer minor units, non-negative.

### orders

- `order_id`: `TEXT PRIMARY KEY`.
- `user_id`: foreign key to `users(user_id)`.
- `order_date`: normalized to ISO `YYYY-MM-DD`.
- `status`: restricted to the five observed statuses.
- `gross_amount_cents`: integer cents; positive.
- `discount_amount_cents`: renamed from the source column `credit`. Cross-table accounting shows that `credit` behaves as an order discount, not customer wallet credit.
- `currency`: restricted to INR/USD. INR and USD are never combined into a single monetary total because the dataset contains no FX information.
- `channel`: restricted to web/android/ios.

### payments

- `payment_id`: `TEXT PRIMARY KEY`.
- `order_id`: foreign key to `orders`; multiple payment attempts per order are allowed.
- `paid_at`: normalized timestamp text. Explicit source timezones are preserved; timezone-less source timestamps remain timezone-less rather than being assigned an invented timezone.
- `method`: nullable. The 102 missing methods cannot be safely reconstructed.
- `amount_cents`: integer cents. The 46 missing captured amounts are deterministically reconstructed from the validated relationship `gross - discount - wallet_applied`.
- `wallet_applied_cents`: non-negative integer cents. Non-zero wallet application occurs only on captured payments in the source.
- `status`: restricted to captured/failed/refunded/pending.
- `currency`: restricted to INR/USD and checked against the parent order's currency.

## Rejections

The loader rejects structurally invalid rows rather than silently dropping them.

The source contains 23 orders whose `user_id` does not exist. Those orders are rejected.

Payments are loaded only if their referenced order was successfully loaded. Therefore 17 payments with nonexistent order IDs plus 27 payments belonging to rejected orders are rejected: 44 payment rows in total.

Missing payment methods are not rejected because NULL is a valid representation of incomplete source information.

## Idempotency

The loader performs a full refresh inside a database transaction. Re-running it replaces the current loaded dataset rather than inserting duplicate rows or silently preserving stale rows.

## Important semantic distinction

The following fields are deliberately kept separate:

- `discount_amount_cents`: discount applied to an order; source field was named `credit`.
- `wallet_applied_cents`: store/customer wallet value used toward a captured payment.
- `wallet_balance_cents`: current wallet balance on the customer account.

These are not interchangeable.

## Currency

There is no exchange-rate data in the supplied exports. Monetary analytics therefore retain currency as a grouping dimension. The application must not add INR and USD together or invent an exchange rate.

## Known source inconsistencies

- User tier has casing variants and 24 missing values.
- Four user emails contain surrounding whitespace.
- Fourteen normalized duplicate email pairs exist; user IDs remain the account identity.
- User signup dates use three formats.
- Payment timestamps use ISO timestamps with explicit timezones and timezone-less `DD-MM-YYYY HH:MM` values.
- 23 orders reference nonexistent users.
- 17 payment rows reference nonexistent orders.
- 27 additional payments reference orders rejected because their users do not exist.
- 46 captured payment amounts are missing but can be deterministically derived from the validated order/payment accounting relationship.
- 102 payment methods are missing and are retained as NULL.

## Still a business-definition decision

The raw data does not contain a field literally named "revenue". The application will define business metrics explicitly rather than allowing the LLM to invent their meaning. The proposed revenue definition and evaluation numbers will be finalized after the loaded database is used to validate the payment/refund relationships.


## Finalized Level 5 metric definitions

The metric contract is recorded in `METRICS.md` and the independently verified answers are recorded in `EVALS.md`.

For this assessment:

- Customer amount spent = net order value (`gross - discount`), grouped by customer and currency.
- Discounts = recorded order discount, grouped by currency. Cancelled orders are not excluded because the export contains no separate reversal field for discounts.
- Store credit spent = `payments.wallet_applied_cents`.
- Revenue = captured payment amount + captured wallet applied - refunded payment amount, grouped by currency.
- AOV = average gross order value, grouped by tier and currency.
- Payment method "fails most often" = highest failed-attempt count.

These are explicit application-level business definitions. They are not columns supplied by the source system.
