import sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.sql_validator import validate_sql, SQLValidationError
from backend.db import connect_readonly

DB = Path(__file__).resolve().parents[1] / "askmetrics.db"

def conn():
    return connect_readonly(DB)

def test_select_is_allowed():
    c = conn()
    try:
        q = validate_sql(c, "SELECT COUNT(*) AS n FROM users", 100)
        assert "LIMIT 100" in q.sql
    finally:
        c.close()

def test_delete_rejected():
    c = conn()
    try:
        try:
            validate_sql(c, "DELETE FROM users", 100)
            assert False
        except SQLValidationError:
            pass
    finally:
        c.close()

def test_multiple_statements_rejected():
    c = conn()
    try:
        try:
            validate_sql(c, "SELECT * FROM users; SELECT * FROM orders", 100)
            assert False
        except SQLValidationError:
            pass
    finally:
        c.close()

def test_output_is_bounded():
    c = conn()
    try:
        q = validate_sql(c, "SELECT user_id FROM users", 10)
        rows = c.execute(q.sql).fetchall()
        assert len(rows) == 10
    finally:
        c.close()

def test_readonly_connection_blocks_write():
    c = conn()
    try:
        try:
            c.execute("DELETE FROM users")
            assert False
        except sqlite3.DatabaseError:
            pass
    finally:
        c.close()


def test_query_timeout_interrupts_runaway_query():
    from backend.db import execute_with_timeout, QueryTimeout
    c = conn()
    try:
        sql = """SELECT x FROM (
            WITH RECURSIVE c(x) AS (
                SELECT 1
                UNION ALL
                SELECT x + 1 FROM c
            )
            SELECT x FROM c
        )"""
        try:
            execute_with_timeout(c, sql, 10)
            assert False, "Expected timeout"
        except QueryTimeout:
            pass
    finally:
        c.close()
