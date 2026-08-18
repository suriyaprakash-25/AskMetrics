SEMANTIC_HINTS = """
BUSINESS SEMANTIC HINTS — use these meanings, not guesses from raw names:

1. Currency & Multi-Currency Rules:
   The dataset contains INR and USD without exchange-rate data.
   Never add INR and USD together. When returning monetary aggregates across orders or payments
   without a specific currency filter, always retain `currency` as a SELECT and GROUP BY column
   (e.g., SELECT currency, SUM(...) ... GROUP BY currency).

2. Direct Column Preference & Avoid Metric Inversion:
   When the database schema contains a column that directly represents the requested metric,
   always use that column directly rather than calculating an arithmetic expression.
   - Gross, Discount, and Net are distinct concepts:
     * Gross order value = `orders.gross_amount_cents`
     * Order discount = `orders.discount_amount_cents`
     * Net order value (after discount) = `orders.gross_amount_cents - orders.discount_amount_cents`
   - NEVER calculate `gross - discount` when the user asks for discounts!
     `gross_amount_cents - discount_amount_cents` is NET value after discount, NOT discount.

3. Discounts ("how much have we given away in discounts", "total discounts", "discount amount"):
   - Total discounts given / discount value:
     SELECT currency, SUM(discount_amount_cents) AS total_discounts FROM orders GROUP BY currency
   - Number of discounted orders: COUNT(*) FROM orders WHERE discount_amount_cents > 0
   - Average discount on discounted orders: AVG(discount_amount_cents) FROM orders WHERE discount_amount_cents > 0

4. Customer Amount Spent:
   - For "top customers by total amount spent", use net order value:
     SUM(orders.gross_amount_cents - orders.discount_amount_cents) AS spent_cents,
     grouped by user_id, full_name, filtered by currency (e.g., WHERE o.currency = 'INR').

5. Store Credit & Wallet Spending:
   - `payments.wallet_applied_cents`: Store credit / customer wallet actually spent toward captured payments.
     For "how much store credit have customers spent":
     SELECT currency, SUM(wallet_applied_cents) FROM payments GROUP BY currency
   - `users.wallet_balance_cents`: Current account balance (NOT historical spending).

6. Revenue (Payment-Event Net Value):
   - Total revenue = captured payment amount + captured wallet applied - refunded payment amount:
     SELECT currency,
            SUM(CASE WHEN status = 'captured' THEN amount_cents + wallet_applied_cents ELSE 0 END) -
            SUM(CASE WHEN status = 'refunded' THEN amount_cents ELSE 0 END) AS revenue_cents
     FROM payments
     GROUP BY currency

7. Average Order Value:
   - For "average order value by customer tier":
     SELECT users.tier, orders.currency, AVG(orders.gross_amount_cents) AS average_order_value
     FROM orders JOIN users ON orders.user_id = users.user_id
     GROUP BY users.tier, orders.currency

8. Payment Failures:
   - "Which payment method fails most often": largest COUNT(*) of failed payments (WHERE status = 'failed').

9. Unsupported Dimensions:
   - The data has country, not region. If a query asks for region, refuse the query.
""".strip()
