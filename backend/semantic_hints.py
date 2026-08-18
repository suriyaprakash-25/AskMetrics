SEMANTIC_HINTS = """
BUSINESS SEMANTIC HINTS — use these meanings, not guesses from raw names:

1. Currency:
   The dataset contains INR and USD and has no exchange-rate data.
   Never add INR and USD together. For monetary analytics, retain currency
   as a grouping dimension or refuse a cross-currency comparison/ranking.

2. orders.discount_amount_cents:
   This is an order discount. The raw CSV called this field "credit".
   It is NOT customer wallet/store credit.

3. payments.wallet_applied_cents:
   Store/customer wallet value actually applied toward a captured payment.
   Historical wallet spending should use this field, not users.wallet_balance_cents.

4. users.wallet_balance_cents:
   Current customer wallet balance. It is not historical spending.

5. Revenue for this application:
   captured payment amount + captured wallet applied - refunded payment amount,
   grouped separately by currency.

6. Customer amount spent:
   For the assessment metric, use net order value:
   orders.gross_amount_cents - orders.discount_amount_cents,
   grouped by customer and currency.

7. Average order value:
   For the assessment metric, use AVG(orders.gross_amount_cents),
   grouped by customer tier and currency. Missing tiers are unknown.

8. "Fails most often":
   Interpret as the largest count of failed payment attempts.
   The current data also has the same winner by failure rate.

9. Missing values:
   Do not invent missing payment methods or customer tiers.

10. Unsupported dimensions:
    The data has country, not region. Do not treat country as region.
""".strip()
