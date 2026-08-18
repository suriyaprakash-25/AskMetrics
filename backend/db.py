from __future__ import annotations
import sqlite3
import time
from pathlib import Path
from typing import Any

class QueryTimeout(RuntimeError):
    pass

def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA foreign_keys = ON")

    def authorizer(action, arg1, arg2, dbname, source):
        # SQLite authorizer is a second, independent safety boundary.
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
        }
        if action == sqlite3.SQLITE_PRAGMA:
            pragma_name = (arg1 or "").lower()
            if pragma_name in {"table_info", "foreign_key_list"}:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            function_name = (arg2 or arg1 or "").lower()
            if function_name in {"load_extension", "writefile", "readfile"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE}:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(authorizer)
    return conn

def execute_with_timeout(conn: sqlite3.Connection, sql: str, timeout_ms: int) -> list[dict[str, Any]]:
    start = time.monotonic()
    deadline = start + timeout_ms / 1000.0

    def progress_handler() -> int:
        return 1 if time.monotonic() >= deadline else 0

    conn.set_progress_handler(progress_handler, 1000)
    try:
        cur = conn.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        return rows
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryTimeout(f"Query exceeded {timeout_ms} ms.") from exc
        raise
    finally:
        conn.set_progress_handler(None, 0)
