"""Public browse-and-claim page. No login."""

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .db import get_db, write_transaction

bp = Blueprint("public", __name__)

PHONE_ALLOWED = re.compile(r"^[0-9+()\-\s]{7,25}$")
MAX_NAME_LEN = 80
MAX_NOTE_LEN = 300


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


def _validate(form):
    """Return an error message, or None if the submission looks usable."""
    if not form["claimant_name"]:
        return "Please enter your name."
    if len(form["claimant_name"]) > MAX_NAME_LEN:
        return "That name is too long."
    digits = sum(ch.isdigit() for ch in form["phone_number"])
    if not PHONE_ALLOWED.match(form["phone_number"]) or digits < 7:
        return "Please enter a phone number we can reach you on."
    if not form["quantity"].isdigit() or int(form["quantity"]) < 1:
        return "Quantity must be a whole number of at least 1."
    if len(form["note"]) > MAX_NOTE_LEN:
        return f"Please keep the note under {MAX_NOTE_LEN} characters."
    return None


@bp.get("/")
def index():
    return render_template(
        "index.html", board=load_board(), open_item_id=None, claim_error=None, form={}
    )


@bp.post("/items/<int:item_id>/claim")
def claim(item_id):
    form = {
        "claimant_name": request.form.get("claimant_name", "").strip(),
        "phone_number": request.form.get("phone_number", "").strip(),
        "quantity": request.form.get("quantity", "").strip(),
        "note": request.form.get("note", "").strip(),
    }
    error = _validate(form)

    if error is None:
        with write_transaction() as db:
            # Re-read inside the write lock: the number shown on the page may
            # already be out of date by the time this form comes back.
            row = db.execute(
                """SELECT i.quantity_needed - COALESCE(SUM(c.quantity), 0) AS remaining
                   FROM items i
                   LEFT JOIN claims c ON c.item_id = i.id
                   WHERE i.id = ?
                   GROUP BY i.id""",
                (item_id,),
            ).fetchone()

            if row is None:
                error = "That item is no longer listed."
            elif row["remaining"] <= 0:
                error = "This item has just been fully claimed by someone else."
            elif int(form["quantity"]) > row["remaining"]:
                error = (
                    f"Only {row['remaining']} left — someone claimed the rest "
                    "while you were filling this in."
                )
            else:
                db.execute(
                    """INSERT INTO claims
                       (item_id, claimant_name, phone_number, quantity, note)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        item_id,
                        form["claimant_name"],
                        form["phone_number"],
                        int(form["quantity"]),
                        form["note"] or None,
                    ),
                )

    if error is None:
        flash(f"Thank you, {form['claimant_name']}! Your claim is recorded.", "success")
        return redirect(url_for("public.index") + f"#item-{item_id}")

    return (
        render_template(
            "index.html",
            board=load_board(),
            open_item_id=item_id,
            claim_error=error,
            form=form,
        ),
        400,
    )
