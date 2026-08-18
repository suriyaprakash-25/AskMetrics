from __future__ import annotations
import sqlite3
from typing import Any

def get_schema_context(conn: sqlite3.Connection) -> str:
    """Read live SQLite schema metadata; never relies on a hardcoded table list."""
    tables = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    lines: list[str] = []
    for (table_name,) in tables:
        columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        lines.append(f"TABLE {table_name}")
        for col in columns:
            # cid, name, type, notnull, default_value, pk
            _, name, col_type, notnull, default, pk = col
            flags = []
            if pk:
                flags.append("PRIMARY KEY")
            if notnull:
                flags.append("NOT NULL")
            suffix = f" [{' '.join(flags)}]" if flags else ""
            lines.append(f"  - {name}: {col_type}{suffix}")

        fks = conn.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
        for fk in fks:
            # id, seq, table, from, to, on_update, on_delete, match
            _, _, parent, child_col, parent_col, *_ = fk
            lines.append(f"  FK: {child_col} -> {parent}({parent_col})")
        lines.append("")

    return "\n".join(lines).strip()
