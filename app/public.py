"""Public browse-and-claim pages. No login.

Claiming is two steps: a visitor builds up a list of what they can bring
(kept in their signed session cookie, nothing written to the database), then
confirms the whole list once with their name and phone number. That way
someone bringing eight things types their details once instead of eight
times.
"""

import re

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .db import get_db, write_transaction

bp = Blueprint("public", __name__)

PHONE_ALLOWED = re.compile(r"^[0-9+()\-\s]{7,25}$")
MAX_NAME_LEN = 80
MAX_NOTE_LEN = 300
MAX_LIST_ITEMS = 40

PENDING_KEY = "pending"
CONTACT_KEY = "contact"

REMAINING_SQL = """
    SELECT i.quantity_needed - COALESCE(SUM(c.quantity), 0) AS remaining,
           i.name, i.unit
    FROM items i
    LEFT JOIN claims c ON c.item_id = i.id
    WHERE i.id = ?
    GROUP BY i.id
"""


# --------------------------------------------------------------------------
# The visitor's list (session-backed, no database writes)
# --------------------------------------------------------------------------


def get_pending():
    """[(item_id, quantity)] from the session, ignoring anything malformed."""
    pairs = []
    for entry in session.get(PENDING_KEY) or []:
        try:
            item_id, quantity = int(entry[0]), int(entry[1])
        except (TypeError, ValueError, IndexError):
            continue
        if quantity > 0:
            pairs.append((item_id, quantity))
    return pairs


def save_pending(pairs):
    if pairs:
        session[PENDING_KEY] = [[item_id, qty] for item_id, qty in pairs]
    else:
        session.pop(PENDING_KEY, None)


def pending_details():
    """The list joined against live item data.

    Items an admin deleted in the meantime are dropped from the session here,
    so the confirm page never shows a row that can't be claimed.
    """
    pairs = get_pending()
    if not pairs:
        return []

    placeholders = ",".join("?" * len(pairs))
    rows = {
        row["id"]: row
        for row in get_db().execute(
            f"""
            SELECT i.id, i.name, i.unit, i.quantity_needed, c.name AS category_name,
                   COALESCE(SUM(cl.quantity), 0) AS claimed
            FROM items i
            JOIN categories c ON c.id = i.category_id
            LEFT JOIN claims cl ON cl.item_id = i.id
            WHERE i.id IN ({placeholders})
            GROUP BY i.id
            """,
            [item_id for item_id, _ in pairs],
        ).fetchall()
    }

    details, kept = [], []
    for item_id, quantity in pairs:
        row = rows.get(item_id)
        if row is None:
            continue
        kept.append((item_id, quantity))
        details.append(
            {
                "id": item_id,
                "name": row["name"],
                "unit": row["unit"],
                "category_name": row["category_name"],
                "quantity": quantity,
                "remaining": row["quantity_needed"] - row["claimed"],
            }
        )

    if kept != pairs:
        save_pending(kept)
    return details


@bp.context_processor
def inject_pending():
    """Every public template can show the 'ready to confirm' bar."""
    return {"pending_count": len(get_pending())}


# --------------------------------------------------------------------------
# Browsing
# --------------------------------------------------------------------------


def load_board():
    """Categories with their items, claim totals and public claimant list."""
    db = get_db()
    categories = db.execute(
        "SELECT id, name FROM categories ORDER BY sort_order, id"
    ).fetchall()
    items = db.execute(
        """
        SELECT i.id, i.category_id, i.name, i.description, i.quantity_needed, i.unit,
               COALESCE(SUM(c.quantity), 0) AS claimed
        FROM items i
        LEFT JOIN claims c ON c.item_id = i.id
        GROUP BY i.id
        ORDER BY i.sort_order, i.id
        """
    ).fetchall()
    claims = db.execute(
        """SELECT item_id, claimant_name, quantity, note
           FROM claims ORDER BY created_at, id"""
    ).fetchall()

    claims_by_item = {}
    for claim in claims:
        claims_by_item.setdefault(claim["item_id"], []).append(claim)

    board = []
    for category in categories:
        rows = [
            {
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "unit": item["unit"],
                "quantity_needed": item["quantity_needed"],
                "claimed": item["claimed"],
                "remaining": item["quantity_needed"] - item["claimed"],
                "claims": claims_by_item.get(item["id"], []),
            }
            for item in items
            if item["category_id"] == category["id"]
        ]
        if rows:
            # Key is "entries", not "items": Jinja would resolve `.items` to
            # the dict method instead of this list.
            board.append({"name": category["name"], "entries": rows})
    return board


def board_summary(board):
    """Headline numbers for the strip at the top of the public page."""
    entries = [entry for category in board for entry in category["entries"]]
    needed = sum(e["quantity_needed"] for e in entries)
    covered = sum(min(e["claimed"], e["quantity_needed"]) for e in entries)
    return {
        "total_items": len(entries),
        "open_items": sum(1 for e in entries if e["remaining"] > 0),
        "percent": round(covered / needed * 100) if needed else 0,
    }


@bp.get("/")
def index():
    board = load_board()
    return render_template(
        "index.html",
        board=board,
        summary=board_summary(board),
        pending_map=dict(get_pending()),
    )


# --------------------------------------------------------------------------
# Building the list
# --------------------------------------------------------------------------


def _back(item_id=None):
    """Return to wherever the form was submitted from."""
    if request.form.get("from") == "confirm":
        return redirect(url_for("public.confirm"))
    return redirect(url_for("public.index") + (f"#item-{item_id}" if item_id else ""))


@bp.post("/list/<int:item_id>")
def list_set(item_id):
    """Add an item to the visitor's list, change the amount, or drop it."""
    item = get_db().execute(REMAINING_SQL, (item_id,)).fetchone()
    if item is None:
        flash("That item is no longer listed.", "error")
        save_pending([(i, q) for i, q in get_pending() if i != item_id])
        return redirect(url_for("public.index"))

    others = [(i, q) for i, q in get_pending() if i != item_id]
    raw = request.form.get("quantity", "").strip()

    if request.form.get("remove") or raw in ("", "0"):
        save_pending(others)
        flash(f"Removed {item['name']} from your list.", "success")
        return _back()

    if not raw.isdigit() or int(raw) < 1:
        flash("Quantity must be a whole number of at least 1.", "error")
        return _back(item_id)

    quantity = int(raw)
    if item["remaining"] <= 0:
        flash(f"{item['name']} has just been fully claimed.", "error")
        save_pending(others)
        return _back()
    if quantity > item["remaining"]:
        flash(
            f"Only {item['remaining']} {item['unit']} of {item['name']} are "
            f"still needed.",
            "error",
        )
        return _back(item_id)
    if len(others) >= MAX_LIST_ITEMS:
        flash("Your list is full — please confirm what's on it first.", "error")
        return _back(item_id)

    save_pending(others + [(item_id, quantity)])
    flash(f"{item['name']} added to your list.", "success")
    return _back(item_id)


@bp.post("/list/clear")
def list_clear():
    save_pending([])
    flash("Your list has been emptied.", "success")
    return redirect(url_for("public.index"))


# --------------------------------------------------------------------------
# Confirming
# --------------------------------------------------------------------------


def _validate_contact(form):
    """Return an error message, or None if the details look usable."""
    if not form["claimant_name"]:
        return "Please enter your name."
    if len(form["claimant_name"]) > MAX_NAME_LEN:
        return "That name is too long."
    digits = sum(ch.isdigit() for ch in form["phone_number"])
    if not PHONE_ALLOWED.match(form["phone_number"]) or digits < 7:
        return "Please enter a phone number we can reach you on."
    if len(form["note"]) > MAX_NOTE_LEN:
        return f"Please keep the note under {MAX_NOTE_LEN} characters."
    return None


@bp.get("/confirm")
def confirm():
    details = pending_details()
    if not details:
        flash("Your list is empty — pick something you can bring.", "error")
        return redirect(url_for("public.index"))

    remembered = session.get(CONTACT_KEY) or {}
    return render_template(
        "confirm.html",
        details=details,
        form={
            "claimant_name": remembered.get("name", ""),
            "phone_number": remembered.get("phone", ""),
            "note": "",
        },
        error=None,
    )


@bp.post("/confirm")
def submit_confirm():
    details = pending_details()
    if not details:
        flash("Your list is empty — pick something you can bring.", "error")
        return redirect(url_for("public.index"))

    form = {
        "claimant_name": request.form.get("claimant_name", "").strip(),
        "phone_number": request.form.get("phone_number", "").strip(),
        "note": request.form.get("note", "").strip(),
    }

    error = _validate_contact(form)
    if error:
        return render_template("confirm.html", details=details, form=form, error=error), 400

    placed, short = [], []
    with write_transaction() as db:
        # Re-read every amount inside the write lock. Someone else may have
        # claimed the last units while this list was being built.
        for entry in details:
            row = db.execute(REMAINING_SQL, (entry["id"],)).fetchone()
            if row is None:
                continue
            if entry["quantity"] > row["remaining"]:
                short.append({**entry, "remaining": row["remaining"]})
                continue
            db.execute(
                """INSERT INTO claims
                   (item_id, claimant_name, phone_number, quantity, note)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    entry["id"],
                    form["claimant_name"],
                    form["phone_number"],
                    entry["quantity"],
                    form["note"] or None,
                ),
            )
            placed.append(entry)

    # Remember the details so a return visit doesn't retype them.
    session[CONTACT_KEY] = {
        "name": form["claimant_name"],
        "phone": form["phone_number"],
    }
    # Anything that no longer fits stays on the list so it can be adjusted —
    # unless nothing is left at all, in which case keeping it is pointless.
    save_pending([(e["id"], e["quantity"]) for e in short if e["remaining"] > 0])

    if placed:
        flash(
            f"Thank you, {form['claimant_name']}! "
            f"{len(placed)} item{'s' if len(placed) != 1 else ''} confirmed.",
            "success",
        )
    if short:
        for entry in short:
            if entry["remaining"] > 0:
                flash(
                    f"{entry['name']}: only {entry['remaining']} {entry['unit']} "
                    f"left, so your {entry['quantity']} couldn't be recorded. "
                    f"Adjust it below.",
                    "error",
                )
            else:
                flash(
                    f"{entry['name']} was fully claimed by someone else before "
                    f"you confirmed.",
                    "error",
                )
        return redirect(url_for("public.confirm"))

    return redirect(url_for("public.index"))
