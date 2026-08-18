# AskMetrics

Natural-language analytics over a relational commerce database.

AskMetrics accepts a plain-English analytics question, supplies live database schema and business-semantic hints to an LLM, validates the generated SQL, executes it against a read-only SQLite connection, and displays the SQL and result in a small React frontend.

## Project structure

```text
AskMetrics/
├── backend/              # FastAPI API, LLM providers, SQL safety
├── database/             # schema, loader, verification
├── data/                 # supplied CSV exports
├── evals/                # deterministic baseline evaluation
├── frontend/             # React + TypeScript + Vite UI
├── rejects/              # rejected source rows and reasons
├── DECISIONS.md
├── METRICS.md
├── AI_USAGE.md
└── EVALS.md
```

## Requirements

- Python 3.11+
- Node.js 20+
- npm

The default LLM provider is `mock`, so the application can be run and tested without an API key.

## 1. Create the database

From the repository root:

```bash
python database/load_data.py
python database/verify_data.py
```

The loader performs a transactional full refresh. It normalizes known formatting issues, derives the 46 missing captured payment amounts from the validated accounting identity, enforces relational integrity, and records rejected rows in `rejects/rejects.csv`.

Expected validated row counts:

```text
users:    434
orders:  2100
payments:2761
```

## 2. Install backend dependencies

```bash
python -m pip install -r backend/requirements.txt
```

## 3. Start the backend

From the repository root:

```bash
uvicorn backend.main:app --reload
```

The API runs at `http://localhost:8000`.

Useful endpoints:

```text
GET  /health
GET  /schema
POST /ask
```

Example:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many active users do we have?"}'
```

## 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

The frontend defaults to `http://localhost:8000` for the API. To change it, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`.

## 5. LLM providers

The backend defaults to a deterministic mock provider for reproducible local tests.

### Ollama (Local Qwen3 8B)

```bash
export ASKMETRICS_LLM_PROVIDER=ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen3:8b
uvicorn backend.main:app --reload
```

### Gemini (Optional)

```bash
export ASKMETRICS_LLM_PROVIDER=gemini
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-2.5-flash"
uvicorn backend.main:app --reload
```

## Safety design

```text
question
  -> preflight policy
  -> live schema inspection
  -> semantic hints
  -> LLM
  -> SQL validator
  -> read-only SQLite + authorizer
  -> application result-row limit
  -> query timeout
  -> result
```

The LLM is treated as an untrusted SQL generator. It cannot execute writes. Multiple statements are rejected, result rows are bounded by the application, and long-running queries are interrupted. A failed query may be repaired at most once by default.

## Data model

```text
users 1 ───< orders 1 ───< payments
```

The raw `orders.credit` field is represented as `discount_amount_cents` because cross-table payment arithmetic supports the interpretation that it is an order discount, not customer wallet credit.

Money is stored as integer cents. INR and USD are never combined because the supplied data contains no FX information.

## Evaluation

The deterministic baseline contains at least 15 hand-verified questions. Run it with:

```bash
python evals/eval.py
```

The baseline verifies the metric definitions independently of the LLM. Real LLM evaluation results must be recorded separately and failures reported honestly.

## Tests

Run backend tests with:

```bash
pytest -q
```

## AI usage

See `AI_USAGE.md` for the actual AI-assisted development record, including an integration error caught during review.
