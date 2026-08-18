# AI Usage

This project was developed with AI assistance. The important rule for this assessment was that every submitted design and function must remain explainable by the candidate.

## Tools used

### ChatGPT

Used for:
- interpreting the assessment brief
- forensic analysis of the supplied CSVs
- checking cross-table business semantics
- reviewing the database/loader design
- reviewing the backend safety architecture
- reviewing the final project for integration and submission issues

### Antigravity

Used for:
- generating the initial React/Vite/TypeScript frontend implementation
- creating the initial chart-rendering component and UI layout

## Important AI-assisted decisions

The most important design decisions were not accepted blindly from an AI output. The raw CSVs were inspected and cross-checked before deciding the schema and business semantics.

Examples:

- The source column `orders.credit` was renamed to `discount_amount_cents` because payment arithmetic consistently supported it as an order discount.
- `payments.wallet_applied` was kept distinct from `users.wallet_balance` because one represents historical wallet value applied to payments while the other is a current balance.
- INR and USD are kept separate because the supplied dataset contains no exchange-rate information.
- SQL generation is treated as untrusted output and is protected by validation plus a read-only SQLite connection/authorizer.

## AI suggestion/error caught during review

The initial AI-assisted frontend expected an API property named `results`, while the FastAPI backend actually returns query rows in the `rows` property.

The mismatch was caught by inspecting the API response contract and testing the backend endpoint. Without the correction, a successful backend query would have reached the frontend with `undefined` result data.

The frontend was changed to use the backend's actual `status`, `sql`, `rows`, `explanation`, and `error` fields, and refusal/error states were handled explicitly.

A separate backend review also found a duplicated `MockProvider.repair()` definition. The second definition incorrectly attempted to call a network helper that the mock provider did not have. It was removed so the mock provider now has one deterministic repair method.

A third error was found during the first real Gemini request after the provider was wired up. The backend responded with HTTP 500 and the traceback identified:

```
KeyError: '"sql"'
```

at `SYSTEM_PROMPT.format(schema=schema, hints=SEMANTIC_HINTS)` in `backend/llm.py`.

The initial test suite used the deterministic mock provider, so a formatting bug in the Gemini prompt was not exercised. During the first real Gemini request, the provider failed with `KeyError: '"sql"'`. Inspection showed that literal JSON braces in a Python `.format()` template had not been escaped. The prompt contained:

```
- Return JSON only: {"sql":"...", "explanation":"..."}.
```

Python's `str.format()` interpreted the `{` as the start of a placeholder and tried to resolve `"sql"` as a keyword argument. The fix was to escape the literal braces by doubling them:

```
- Return JSON only: {{"sql":"...", "explanation":"..."}}.
```

The `{schema}` and `{hints}` placeholders were left as single braces — they are the intended substitution points. The corrected prompt was then tested independently with a direct `.format()` call before restarting the server.


## What was written/implemented with AI assistance

The frontend structure, React components, initial styling, and chart implementation were substantially AI-assisted.

The backend was also developed with AI assistance, but the database schema, data-forensics decisions, metric definitions, SQL safety boundaries, loader behavior, and evaluation strategy were reviewed against the actual data and tests.

## What the candidate must be able to explain

AI assistance does not replace understanding. The candidate should be able to explain:

- the three-table relational model
- why `credit` means discount in this dataset
- why money is stored as integer cents
- why INR and USD are not combined
- why invalid foreign-key rows are rejected
- how missing captured payment amounts are reconstructed
- where read-only SQL enforcement occurs
- how single-statement and row-limit checks work
- how query timeouts work
- how the live schema is supplied to the model
- how the frontend chooses chart types deterministically
