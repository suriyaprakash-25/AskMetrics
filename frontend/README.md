# AskMetrics frontend

React + TypeScript + Vite frontend for the AskMetrics FastAPI backend.

## Run

From the repository root, start the backend first:

```bash
uvicorn backend.main:app --reload
```

Then:

```bash
cd frontend
npm install
npm run build
npm run dev
```

The frontend calls `POST /ask` on `http://localhost:8000` by default. To change the API URL, copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL`.

## Currency & Monetary Presentation

Monetary values returned by the database/backend are stored in integer cents (e.g. `150000`). The presentation layer automatically detects monetary columns and formats them:

- `150000` $\rightarrow$ `$1,500.00` (or `₹1,500.00` when currency is INR)
- `-150000` $\rightarrow$ `-$1,500.00`
- `0` $\rightarrow$ `$0.00`

Formatting rules:
- **Tables & KPIs**: Monetary columns (`_cents`, `aov`, `revenue`, `discounts`, etc.) are rendered with currency symbols and two decimal places.
- **Charts**: Underlying data remains strictly numeric in cents for precise chart geometry; Y-axis ticks (`formatChartAxisCurrency`) and tooltips (`formatCurrencyFromCents`) display formatted currency.
- **Non-monetary metrics**: Identifiers, counts, and quantities (`user_id`, `COUNT(*)`, `active_users`, `quantity`) remain plain numeric values without currency symbols.

## Result rendering rule

The chart type is selected locally and deterministically from the result shape; the LLM never chooses the visualization.

- One numeric value and no dimensions: KPI scalar card + table.
- One dimension + numeric metric(s): line chart for time-like dimensions, otherwise bar chart, followed by the result table.
- Two dimensions + one numeric metric: deterministic grouped chart, followed by the result table.
- More complex shapes: result table only, because collapsing dimensions would be misleading.

Refusal, error, and empty-result states are rendered separately from successful query results.
