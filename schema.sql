-- Camp Supply Tracker schema. Safe to re-run: everything is IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL DEFAULT '',
    quantity_needed INTEGER NOT NULL CHECK (quantity_needed > 0),
    unit            TEXT    NOT NULL DEFAULT 'pcs',
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS claims (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    claimant_name TEXT    NOT NULL,
    phone_number  TEXT    NOT NULL,
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    -- note: about this item specifically. general_note: about the whole
    -- drop-off, repeated on every claim confirmed together.
    note          TEXT,
    general_note  TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_items_category ON items (category_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_claims_item    ON claims (item_id);
