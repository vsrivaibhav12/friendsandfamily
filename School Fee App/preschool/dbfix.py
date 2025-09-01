# preschool/dbfix.py
"""
Idempotent schema fixer for SQLite.
Adds/updates columns needed by recent features.
Safe to run at every startup.
"""
from sqlalchemy import text

def ensure_schema(db):
    engine = db.engine
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        def table_exists(name: str) -> bool:
            row = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {'n': name}).fetchone()
            return bool(row)

        def has_col(table: str, col: str) -> bool:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return any((r[1] == col) for r in rows)

        def add_col(table: str, decl: str):
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {decl}"))

        # --- bank_credit: legacy table for statement imports (optional)
        if table_exists("bank_credit"):
            if not has_col("bank_credit", "amount_net"):
                add_col("bank_credit", "amount_net NUMERIC DEFAULT 0")
            if not has_col("bank_credit", "utr"):
                add_col("bank_credit", "utr VARCHAR(64)")
            if not has_col("bank_credit", "created_at"):
                add_col("bank_credit", "created_at DATETIME")

        # --- settlement_batch: ensure expected new fields exist
        if table_exists("settlement_batch"):
            needed = {
                "charges":        "NUMERIC DEFAULT 0",
                "expected_net":   "NUMERIC DEFAULT 0",
                "bank_net":       "NUMERIC DEFAULT 0",
                "variance":       "NUMERIC DEFAULT 0",
                "days_grouping":  "INTEGER DEFAULT 2",
                "provider":       "VARCHAR(50) DEFAULT 'UPI'",
                "rule_id":        "INTEGER",
            }
            for col, decl in needed.items():
                if not has_col("settlement_batch", col):
                    add_col("settlement_batch", f"{col} {decl}")

        # --- cash_count: ensure expected & variance exist
        if table_exists("cash_count"):
            if not has_col("cash_count", "expected"):
                add_col("cash_count", "expected NUMERIC DEFAULT 0")
            if not has_col("cash_count", "variance"):
                add_col("cash_count", "variance NUMERIC DEFAULT 0")
