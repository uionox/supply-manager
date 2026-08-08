"""Building a list and confirming it — the part visitors actually touch."""

import threading


def add(client, item_id, quantity, note=""):
    return client.post(
        f"/list/{item_id}", data={"quantity": str(quantity), "note": note},
        follow_redirects=True,
    )


def confirm(client, name="Sara", general_note="", **kwargs):
    return client.post(
        "/confirm",
        data={"claimant_name": name, "general_note": general_note},
        **kwargs,
    )


def test_items_show_publicly(client, board):
    page = client.get("/").data
    assert b"Blankets" in page and b"Pillows" in page


def test_building_a_list_writes_nothing(client, board, scalar):
    response = add(client, board["blankets"], 4, "all size L")
    assert b"added to your list" in response.data
    assert b"all size L" in response.data
    assert scalar("SELECT COUNT(*) FROM claims") == 0


def test_confirm_bar_appears_once_something_is_listed(client, board):
    assert b"pendbar" not in client.get("/").data
    assert b"pendbar" in add(client, board["blankets"], 1).data


def test_one_confirm_records_every_item(client, board, scalar):
    add(client, board["blankets"], 4, "all size L")
    add(client, board["pillows"], 3)
    confirm(client, "Sara", "Friday morning", follow_redirects=True)

    assert scalar("SELECT COUNT(*) FROM claims") == 2
    assert scalar("SELECT COUNT(*) FROM claims WHERE claimant_name = 'Sara'") == 2


def test_note_levels_are_kept_apart(client, board, scalar):
    add(client, board["blankets"], 4, "all size L")
    add(client, board["pillows"], 3)  # deliberately no per-item note
    confirm(client, "Sara", "Friday morning", follow_redirects=True)

    assert scalar("SELECT COUNT(*) FROM claims WHERE general_note = 'Friday morning'") == 2
    assert scalar("SELECT note FROM claims WHERE item_id = ?", (board["blankets"],)) == "all size L"
    # An item with no note of its own must not inherit the drop-off note.
    assert scalar("SELECT note FROM claims WHERE item_id = ?", (board["pillows"],)) is None


def test_public_page_falls_back_to_the_dropoff_note(client, board):
    add(client, board["pillows"], 3)
    page = confirm(client, "Sara", "Friday morning", follow_redirects=True).data
    assert b"Friday morning" in page


def test_quantity_and_note_can_be_edited_without_reordering(client, board):
    add(client, board["blankets"], 4, "all size L")
    add(client, board["pillows"], 2)
    page = client.post(
        f"/list/{board['blankets']}",
        data={"quantity": "6", "note": "all size L", "from": "confirm"},
        follow_redirects=True,
    ).data
    assert b'value="6"' in page and b"all size L" in page
    assert page.index(b"Blankets") < page.index(b"Pillows")


def test_item_can_be_removed(client, board):
    add(client, board["blankets"], 2)
    add(client, board["pillows"], 2)
    page = client.post(
        f"/list/{board['pillows']}", data={"remove": "1", "from": "confirm"},
        follow_redirects=True,
    ).data
    # The flash names the item, so look for its row instead.
    assert f'id="q-{board["pillows"]}"'.encode() not in page


def test_over_claiming_is_refused_when_adding(client, board):
    assert b"still needed" in add(client, board["blankets"], 99).data


def test_quantity_must_be_a_positive_whole_number(client, board):
    assert b"whole number" in add(client, board["blankets"], -2).data


def test_name_is_required(client, board, scalar):
    add(client, board["blankets"], 1)
    response = confirm(client, "")
    assert response.status_code == 400
    assert b"enter your name" in response.data
    assert scalar("SELECT COUNT(*) FROM claims") == 0


def test_over_long_dropoff_note_is_refused(client, board):
    add(client, board["blankets"], 1)
    response = confirm(client, "Sara", "x" * 400)
    assert response.status_code == 400
    assert b"under 300 characters" in response.data


def test_empty_list_bounces_back(client, board):
    page = client.get("/confirm", follow_redirects=True).data
    assert b"Your list is empty" in page


def test_name_is_remembered_and_suggested(client, board):
    add(client, board["blankets"], 1)
    confirm(client, "Rami Haddad", follow_redirects=True)

    add(client, board["pillows"], 1)
    page = client.get("/confirm").data
    assert b'list="known-names"' in page
    assert b'value="Rami Haddad"' in page


def test_no_phone_is_collected(client, board):
    add(client, board["blankets"], 1)
    assert b'name="phone_number"' not in client.get("/confirm").data


def test_deleted_item_falls_off_the_list(client, admin, board):
    add(client, board["pillows"], 1)
    admin.post(f"/admin/items/{board['pillows']}/delete")
    response = client.get("/confirm", follow_redirects=True)
    assert response.status_code == 200
    assert b"empty" in response.data


# ── the race everything else depends on ──────────────────────────────────

def test_simultaneous_confirms_cannot_oversubscribe(app, board, scalar):
    """Ten people confirm the last four units at the same instant."""
    blankets = board["blankets"]
    with app.app_context():
        from app.db import get_db

        get_db().execute(
            "INSERT INTO claims (item_id, claimant_name, quantity) VALUES (?, ?, ?)",
            (blankets, "Earlier", 6),
        )
    assert scalar("SELECT COALESCE(SUM(quantity), 0) FROM claims WHERE item_id = ?",
                  (blankets,)) == 6  # 4 left

    racers = 10
    gate = threading.Barrier(racers)

    def race(n):
        session = app.test_client()
        session.post(f"/list/{blankets}", data={"quantity": "1"})
        gate.wait()
        session.post("/confirm", data={"claimant_name": f"Racer{n}", "general_note": ""})

    threads = [threading.Thread(target=race, args=(n,)) for n in range(racers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert scalar("SELECT COUNT(*) FROM claims WHERE claimant_name LIKE 'Racer%'") == 4
    assert scalar("SELECT COALESCE(SUM(quantity), 0) FROM claims WHERE item_id = ?",
                  (blankets,)) == 10


def test_shortfall_is_explained_and_stays_on_the_list(app, board, scalar):
    """Someone lists all 8 pillows, another takes 5 first."""
    pillows = board["pillows"]
    slow = app.test_client()
    slow.post(f"/list/{pillows}", data={"quantity": "8"})

    quick = app.test_client()
    quick.post(f"/list/{pillows}", data={"quantity": "5"})
    quick.post("/confirm", data={"claimant_name": "Quick", "general_note": ""})

    page = slow.post(
        "/confirm", data={"claimant_name": "Slow", "general_note": ""},
        follow_redirects=True,
    ).data

    assert b"only 3 pcs" in page
    assert b"couldn&#39;t be recorded" in page
    assert f'id="q-{pillows}"'.encode() in page          # still adjustable
    assert scalar("SELECT COUNT(*) FROM claims WHERE claimant_name = 'Slow'") == 0
    assert scalar("SELECT COUNT(*) FROM claims WHERE claimant_name = 'Quick'") == 1
