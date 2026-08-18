# Business Metric Contract

This document defines the meanings used by the evaluation suite. These definitions are deliberate choices based on the raw data and cross-table checks; they are not claims that the source system had an explicit revenue specification.

## 1. Currency rule

The dataset contains INR and USD and provides no exchange-rate data.

Therefore:

- INR and USD are always reported separately.
- The system must not add INR and USD into one total.
- A cross-currency ranking is not considered answerable without an exchange rate.

## 2. Order value

**Gross order value** = `orders.gross_amount_cents`.

**Net order value** = `orders.gross_amount_cents - orders.discount_amount_cents`.

The source column `orders.credit` is treated as an order discount because the captured-payment accounting relationship is:

`payment amount + wallet applied = gross amount - discount`

for captured payments.

## 3. Customer amount spent

For the supplied "top customers by total amount spent" evaluation, amount spent means:

`SUM(net order value)` grouped by customer and currency over the accepted relational dataset.

This deliberately does not invent an FX conversion. INR and USD rankings are separate.

## 4. Discounts

For "how much have we given away in discounts", the evaluation uses the recorded order discount:

`SUM(orders.discount_amount_cents)` grouped by currency.

We do not exclude cancelled orders because the source records a discount on the order and does not contain a separate field saying that the discount was reversed. A status-based alternative is a business assumption, not a fact in the export.

## 5. Store credit spent

Store credit actually spent is:

`SUM(payments.wallet_applied_cents)`

grouped by currency.

`users.wallet_balance_cents` is the current account balance and is not historical spending.

## 6. Revenue

The source has no field literally named `revenue`. For this assessment we define revenue as payment-event net value:

`SUM(captured amount + captured wallet applied) - SUM(refunded amount)`

reported separately by currency.

Why:

- `gross_amount` is before discount.
- captured payments represent successful payment events.
- wallet application is value used toward captured orders.
- refunded payment records explicitly remove value.
- failed and pending attempts do not contribute revenue.

The 46 missing captured payment amounts are reconstructed deterministically during ingestion from:

`gross - discount - wallet_applied`.

## 7. Average order value

For "average order value by customer tier", AOV means:

`AVG(orders.gross_amount_cents)`

grouped by normalized customer tier and currency.

The question says "order value", not "net order value", so discounts are not subtracted for this metric.

Missing customer tiers are reported as `unknown`; they are not discarded.

## 8. Payment failure

"Which payment method fails most often?" is interpreted as the largest **count of failed payment attempts**, not merely the highest percentage.

The current dataset produces the same winner under both count and failure-rate interpretations: `netbanking`.

## 9. Time

Order dates are normalized to `YYYY-MM-DD`.

Payment timestamps preserve explicit source timezone information. Timezone-less source timestamps are not assigned an invented timezone.

For month-based payment metrics in the evaluation, the normalized source calendar month is used.

## 10. Relational validity

The evaluation runs against the accepted relational dataset:

- 434 users
- 2,100 orders
- 2,761 payments

23 orders with nonexistent users are rejected. 44 payments are rejected because their orders are absent from the accepted order set.
