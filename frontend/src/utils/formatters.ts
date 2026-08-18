/**
 * Presentation-layer currency and value formatters for AskMetrics.
 * Formats cents-based monetary values without modifying underlying data or SQL.
 */

/**
 * Determines whether a given column name or aggregation represents monetary cents.
 */
export const isMonetaryColumn = (columnName: string): boolean => {
  if (!columnName) return false;
  const clean = columnName.toLowerCase().trim();

  // Explicit non-monetary columns/patterns
  if (
    clean === 'user_id' ||
    clean === 'order_id' ||
    clean === 'payment_id' ||
    clean === 'id' ||
    clean === 'quantity' ||
    clean === 'qty' ||
    clean === 'is_active' ||
    clean === 'tier' ||
    clean === 'status' ||
    clean === 'method' ||
    clean === 'channel' ||
    clean === 'currency' ||
    clean === 'country' ||
    clean === 'order_date' ||
    clean === 'paid_at' ||
    clean === 'signup_date' ||
    clean === 'email' ||
    clean === 'full_name' ||
    clean.startsWith('count(') ||
    clean === 'count(*)' ||
    clean.includes('active_users') ||
    clean.includes('failed_count') ||
    clean.includes('order_count') ||
    clean.includes('returned_orders')
  ) {
    return false;
  }

  // 1. Columns ending with _cents or containing _cents
  if (clean.includes('_cents') || clean.endsWith('cents')) {
    return true;
  }

  // 2. Aggregation over cents (e.g. SUM(gross_amount_cents), AVG(orders.gross_amount_cents))
  if (/\b(sum|avg|total|min|max)\s*\(.*cents.*\)/i.test(clean)) {
    return true;
  }

  // 3. Known business-semantic monetary metric aliases
  const monetaryAliases = [
    'aov',
    'average_order_value',
    'avg_order_value',
    'net_order_value',
    'gross_order_value',
    'revenue',
    'total_revenue',
    'net_revenue',
    'revenue_cents',
    'total_spent',
    'amount_spent',
    'spent_cents',
    'discounts',
    'total_discounts',
    'discount_amount',
    'refund_amount',
    'refund_cents',
    'total_refunded',
    'store_credit_spent',
    'wallet_applied',
    'wallet_balance',
    'gross_amount',
    'net_amount',
  ];

  return monetaryAliases.includes(clean);
};

/**
 * Formats a monetary integer in cents to currency string with 2 decimal places.
 * Example: 150000 -> "$1,500.00", -150000 -> "-$1,500.00", 0 -> "$0.00"
 */
export const formatCurrencyFromCents = (
  cents: number | unknown,
  currency?: string
): string => {
  if (typeof cents !== 'number' || !Number.isFinite(cents)) {
    return cents === null || cents === undefined ? '—' : String(cents);
  }

  const curr = String(currency || '').trim().toUpperCase();
  const symbol = curr === 'INR' ? '₹' : '$';
  const isNegative = cents < 0;
  const absDollars = Math.abs(cents) / 100;

  const formattedNumber = absDollars.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return isNegative ? `-${symbol}${formattedNumber}` : `${symbol}${formattedNumber}`;
};

/**
 * Formats a monetary value for compact chart Y-axis ticks.
 * Example: 150000 -> "$1,500", 1500000 -> "$15k", 150000000 -> "$1.5M"
 */
export const formatChartAxisCurrency = (
  cents: number | unknown,
  currency?: string
): string => {
  if (typeof cents !== 'number' || !Number.isFinite(cents)) {
    return String(cents ?? '');
  }

  const curr = String(currency || '').trim().toUpperCase();
  const symbol = curr === 'INR' ? '₹' : '$';
  const isNegative = cents < 0;
  const absDollars = Math.abs(cents) / 100;

  if (absDollars >= 1_000_000) {
    const val = (absDollars / 1_000_000).toFixed(1).replace(/\.0$/, '');
    return `${isNegative ? '-' : ''}${symbol}${val}M`;
  }
  if (absDollars >= 10_000) {
    const val = (absDollars / 1_000).toFixed(0);
    return `${isNegative ? '-' : ''}${symbol}${val}k`;
  }

  return `${isNegative ? '-' : ''}${symbol}${absDollars.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
};
