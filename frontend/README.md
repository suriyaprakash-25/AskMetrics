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

## Result rendering rule

The chart type is selected locally and deterministically from the result shape; the LLM never chooses the visualization.

- One numeric value and no dimensions: KPI + table.
- One dimension + numeric metric(s): line chart for time-like dimensions, otherwise bar chart, followed by the result table.
- Two dimensions + one numeric metric: deterministic grouped chart, followed by the result table.
- More complex shapes: result table only, because collapsing dimensions would be misleading.

Refusal, error, and empty-result states are rendered separately from successful query results.
