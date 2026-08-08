"""SQLite access helpers. Stdlib sqlite3 only — no ORM."""

import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, g

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql"
)


def get_db():
    """Connection for the current request, opened lazily."""
    if "db" not in g:
        conn = sqlite3.connect(
            current_app.config["DATABASE"],
            # Autocommit mode: transactions are started explicitly by
            # write_transaction() so we control exactly when the write lock
            # is taken.
            isolation_level=None,
            timeout=15,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def write_transaction():
    """Serialised read-then-write block.

    BEGIN IMMEDIATE takes SQLite's write lock up front, so a value read
    inside the block cannot change before the matching write commits. This
    is what stops two simultaneous claims from oversubscribing an item.
    """
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# Columns added after the first release. CREATE TABLE IF NOT EXISTS won't
# touch a table that already exists, so they're added here instead.
ADDED_COLUMNS = [
    ("claims", "general_note", "ALTER TABLE claims ADD COLUMN general_note TEXT"),
]


def _drop_phone_number(db):
    """Phone numbers are no longer collected, so remove the column.

    SQLite only gained ALTER TABLE ... DROP COLUMN in 3.35, so rebuild the
    table instead — that works whatever version the server ships.
    """
    columns = {row["name"] for row in db.execute("PRAGMA table_info(claims)")}
    if "phone_number" not in columns:
        return

    db.executescript(
        """
        PRAGMA foreign_keys = off;
        BEGIN;
        CREATE TABLE claims_rebuilt (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            claimant_name TEXT    NOT NULL,
            quantity      INTEGER NOT NULL CHECK (quantity > 0),
            note          TEXT,
            general_note  TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO claims_rebuilt
            (id, item_id, claimant_name, quantity, note, general_note, created_at)
            SELECT id, item_id, claimant_name, quantity, note, general_note, created_at
            FROM claims;
        DROP TABLE claims;
        ALTER TABLE claims_rebuilt RENAME TO claims;
        CREATE INDEX IF NOT EXISTS idx_claims_item ON claims (item_id);
        COMMIT;
        PRAGMA foreign_keys = on;
        """
    )


def ensure_schema():
    """Create missing tables and columns. Safe to call on every boot."""
    db = get_db()
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        db.executescript(fh.read())

    for table, column, statement in ADDED_COLUMNS:
        existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            db.execute(statement)

    # Runs after the column additions above, so the rebuild can copy
    # general_note across on a database old enough to lack both.
    _drop_phone_number(db)


def init_app(app):
    app.teardown_appcontext(close_db)
