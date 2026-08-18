from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass

class SQLValidationError(ValueError):
    pass

@dataclass(frozen=True)
class ValidatedQuery:
    sql: str

_FORBIDDEN_WORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "truncate", "attach", "detach", "vacuum", "reindex",
}
_QUERY_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

def _strip_trailing_semicolon(sql: str) -> str:
    return sql.strip().rstrip(";").strip()

def _remove_literals_and_comments(sql: str) -> str:
    # Enough for policy scanning; SQLite remains the final parser.
    out = []
    i = 0
    while i < len(sql):
        if sql[i:i+2] == "--":
            j = sql.find("\n", i+2)
            i = len(sql) if j == -1 else j
            out.append(" ")
        elif sql[i:i+2] == "/*":
            j = sql.find("*/", i+2)
            if j == -1:
                raise SQLValidationError("Unterminated SQL comment.")
            i = j + 2
            out.append(" ")
        elif sql[i] in ("'", '"'):
            quote = sql[i]
            i += 1
            while i < len(sql):
                if sql[i] == quote:
                    if i + 1 < len(sql) and sql[i+1] == quote:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(" ")
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)

def validate_sql(conn: sqlite3.Connection, sql: str, max_rows: int) -> ValidatedQuery:
    if not isinstance(sql, str):
        raise SQLValidationError("LLM did not return SQL text.")
    sql = _strip_trailing_semicolon(sql)
    if not sql:
        raise SQLValidationError("Empty SQL.")
    if not _QUERY_START.match(sql):
        raise SQLValidationError("Only SELECT/WITH read-only queries are allowed.")

    cleaned = _remove_literals_and_comments(sql)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned.lower())
    forbidden = _FORBIDDEN_WORDS.intersection(tokens)
    if forbidden:
        raise SQLValidationError(
            f"Forbidden SQL operation: {sorted(forbidden)[0]}"
        )

    # SQLite's parser gives us a reliable single-statement check without executing.
    try:
        statements = list(conn.execute(f"EXPLAIN QUERY PLAN {sql}"))
    except sqlite3.Error as exc:
        raise SQLValidationError(f"SQL parse/validation failed: {exc}") from exc
    if not statements:
        raise SQLValidationError("SQL could not be validated.")

    # Wrap the complete query so the application, not the model, enforces the output cap.
    limited = f"SELECT * FROM ({sql}) AS _askmetrics_result LIMIT {int(max_rows)}"
    try:
        conn.execute(f"EXPLAIN QUERY PLAN {limited}").fetchall()
    except sqlite3.Error as exc:
        raise SQLValidationError(f"Result-limit wrapper is invalid: {exc}") from exc

    return ValidatedQuery(limited)
