"""Schema migrations against databases from earlier versions."""

import sqlite3

from app import create_app
from app.timefmt import to_local, get_zone

# The very first released shape: no general_note, and a phone number.
ORIGINAL_SCHEMA = """
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT, sort_order INTEGER);
CREATE TABLE items (id INTEGER PRIMARY KEY, category_id INTEGER, name TEXT,
    description TEXT, quantity_needed INTEGER, unit TEXT, sort_order INTEGER);
CREATE TABLE claims (id INTEGER PRIMARY KEY, item_id INTEGER, claimant_name TEXT,
    phone_number TEXT, quantity INTEGER, note TEXT, created_at TEXT);
INSERT INTO categories (id, name, sort_order) VALUES (1, 'Bedding', 0);
INSERT INTO items (id, category_id, name, description, quantity_needed, unit, sort_order)
    VALUES (1, 1, 'Blankets', '', 10, 'pcs', 0);
INSERT INTO claims (item_id, claimant_name, phone_number, quantity, note, created_at)
    VALUES (1, 'Old Claim', '+961 70 111 222', 2, 'still here', '2026-01-01 09:00:00');
"""


def migrate(tmp_path):
    path = tmp_path / "legacy.db"
    old = sqlite3.connect(path)
    old.executescript(ORIGINAL_SCHEMA)
    old.commit()
    old.close()

    application = create_app({"DATABASE": str(path), "SECRET_KEY": "k" * 40})
    with application.app_context():
        from app.db import get_db

        database = get_db()
        return {
            "columns": {r["name"] for r in database.execute("PRAGMA table_info(claims)")},
            "indexes": {r["name"] for r in database.execute("PRAGMA index_list(claims)")},
            "claim": database.execute(
                "SELECT * FROM claims WHERE claimant_name = 'Old Claim'").fetchone(),
            "app": application,
        }


def test_general_note_column_is_added(tmp_path):
    assert "general_note" in migrate(tmp_path)["columns"]


def test_phone_number_column_is_removed(tmp_path):
    assert "phone_number" not in migrate(tmp_path)["columns"]


def test_existing_claims_survive_the_rebuild(tmp_path):
    claim = migrate(tmp_path)["claim"]
    assert claim["claimant_name"] == "Old Claim"
    assert claim["quantity"] == 2
    assert claim["note"] == "still here"
    assert claim["general_note"] is None


def test_index_survives_the_rebuild(tmp_path):
    assert "idx_claims_item" in migrate(tmp_path)["indexes"]


def test_migrating_twice_is_harmless(tmp_path):
    result = migrate(tmp_path)
    path = result["app"].config["DATABASE"]
    again = create_app({"DATABASE": path, "SECRET_KEY": "k" * 40})
    with again.app_context():
        from app.db import get_db

        assert get_db().execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1


def test_the_migrated_database_still_serves_pages(tmp_path):
    application = migrate(tmp_path)["app"]
    assert application.test_client().get("/").status_code == 200


# ── timestamps ───────────────────────────────────────────────────────────

def test_stored_utc_is_shown_in_camp_time():
    moment = to_local("2026-08-08 07:42:15", get_zone("Asia/Beirut"))
    assert moment.hour == 10 and moment.minute == 42


def test_unparseable_timestamp_is_left_alone():
    assert to_local("not a date", get_zone("Asia/Beirut")) is None


def test_unknown_timezone_falls_back_to_utc():
    moment = to_local("2026-08-08 07:42:15", get_zone("Not/AZone"))
    assert moment.hour == 7


def test_claims_page_shows_local_time(admin, client, board):
    client.post(f"/list/{board['blankets']}", data={"quantity": "1"})
    client.post("/confirm", data={"claimant_name": "Sara", "general_note": ""})
    page = admin.get(f"/admin/items/{board['blankets']}/claims").data
    # Formatted, not the raw "2026-08-08 07:42:15" that SQLite stores.
    assert b"Sara" in page
    assert page.count(b"-08-") == 0 or b"," in page
