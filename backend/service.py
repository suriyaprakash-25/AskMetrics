from __future__ import annotations
import sqlite3
from .config import settings
from .db import connect_readonly, execute_with_timeout, QueryTimeout
from .schema_inspector import get_schema_context
from .sql_validator import validate_sql, SQLValidationError
from .llm import get_provider, LLMError
from .policy import preflight_question, Refusal

class AskService:
    def __init__(self):
        self.provider = get_provider(settings.provider)

    def ask(self, question: str) -> dict:
        try:
            preflight_question(question)
        except Refusal as exc:
            return {
                "status": "refusal",
                "question": question,
                "sql": None,
                "answer": None,
                "rows": [],
                "row_count": 0,
                "explanation": str(exc),
                "attempts": 0,
            }

        conn = connect_readonly(settings.database_path)
        try:
            schema = get_schema_context(conn)
            last_error = None

            generated = self.provider.generate(question, schema)
            for attempt in range(settings.retry_count + 1):
                try:
                    if generated.sql.strip() == "":
                        explanation = generated.explanation or "The question cannot be answered from the available data."
                        return {
                            "status": "refusal",
                            "question": question,
                            "sql": None,
                            "answer": None,
                            "rows": [],
                            "row_count": 0,
                            "explanation": explanation,
                            "attempts": attempt + 1,
                        }

                    validated = validate_sql(
                        conn,
                        generated.sql,
                        settings.max_result_rows,
                    )
                    rows = execute_with_timeout(
                        conn,
                        validated.sql,
                        settings.timeout_ms,
                    )
                    return {
                        "status": "success",
                        "question": question,
                        "sql": generated.sql,
                        "answer": rows,
                        "rows": rows,
                        "row_count": len(rows),
                        "explanation": generated.explanation,
                        "attempts": attempt + 1,
                    }

                except (SQLValidationError, sqlite3.Error, QueryTimeout) as exc:
                    last_error = str(exc)
                    if attempt >= settings.retry_count:
                        break
                    generated = self.provider.repair(
                        question, schema, generated.sql, last_error
                    )
                    continue

            return {
                "status": "error",
                "question": question,
                "sql": None,
                "answer": None,
                "rows": [],
                "row_count": 0,
                "explanation": "The generated query could not be safely executed.",
                "error": last_error,
                "attempts": settings.retry_count + 1,
            }
        except LLMError as exc:
            return {
                "status": "error",
                "question": question,
                "sql": None,
                "answer": None,
                "rows": [],
                "row_count": 0,
                "explanation": "The language model is unavailable.",
                "error": str(exc),
                "attempts": 0,
            }
        finally:
            conn.close()
