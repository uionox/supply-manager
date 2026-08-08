"""Public browse-and-claim pages. No login.

Claiming is two steps: a visitor builds up a list of what they can bring
(kept in their signed session cookie, nothing written to the database), then
confirms the whole list once with their name and phone number. That way
someone bringing eight things types their details once instead of eight
times.
"""

import json

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
from .i18n import set_language, translate as t

bp = Blueprint("public", __name__)

MAX_NAME_LEN = 80
MAX_ITEM_NOTE_LEN = 140
MAX_GENERAL_NOTE_LEN = 300
MAX_LIST_ITEMS = 30

# The list lives in the signed session cookie, and browsers drop cookies over
# ~4KB. Per-item notes make the payload variable, so measure it rather than
# trusting the item count alone.
SESSION_LIST_BUDGET = 2800

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
    """The list from the session, ignoring anything malformed."""
    entries = []
    for raw in session.get(PENDING_KEY) or []:
        try:
            item_id, quantity = int(raw[0]), int(raw[1])
        except (TypeError, ValueError, IndexError):
            continue
        note = raw[2] if len(raw) > 2 and isinstance(raw[2], str) else ""
        if quantity > 0:
            entries.append({"id": item_id, "quantity": quantity, "note": note})
    return entries


def _packed(entries):
    return [[e["id"], e["quantity"], e["note"]] for e in entries]


def save_pending(entries):
    if entries:
        session[PENDING_KEY] = _packed(entries)
    else:
        session.pop(PENDING_KEY, None)


def fits_in_session(entries):
    packed = json.dumps(_packed(entries), separators=(",", ":"))
    return len(packed.encode("utf-8")) <= SESSION_LIST_BUDGET


def pending_details():
    """The list joined against live item data.

    Items an admin deleted in the meantime are dropped from the session here,
    so the confirm page never shows a row that can't be claimed.
    """
    entries = get_pending()
    if not entries:
        return []

    placeholders = ",".join("?" * len(entries))
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
            [entry["id"] for entry in entries],
        ).fetchall()
    }

    details, kept = [], []
    for entry in entries:
        row = rows.get(entry["id"])
        if row is None:
            continue
        kept.append(entry)
        details.append(
            {
                **entry,
                "name": row["name"],
                "unit": row["unit"],
                "category_name": row["category_name"],
                "remaining": row["quantity_needed"] - row["claimed"],
            }
        )

    if kept != entries:
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
        """SELECT item_id, claimant_name, quantity, note, general_note
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
        pending_map={entry["id"]: entry for entry in get_pending()},
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
    """Add an item to the visitor's list, change it, or drop it."""
    item = get_db().execute(REMAINING_SQL, (item_id,)).fetchone()
    entries = get_pending()

    if item is None:
        flash(t("That item is no longer listed."), "error")
        save_pending([e for e in entries if e["id"] != item_id])
        return redirect(url_for("public.index"))

    raw = request.form.get("quantity", "").strip()
    note = request.form.get("note", "").strip()[:MAX_ITEM_NOTE_LEN]

    if request.form.get("remove") or raw in ("", "0"):
        save_pending([e for e in entries if e["id"] != item_id])
        flash(t("Removed {name} from your list.", name=item["name"]), "success")
        return _back()

    if not raw.isdigit() or int(raw) < 1:
        flash(t("Quantity must be a whole number of at least 1."), "error")
        return _back(item_id)

    quantity = int(raw)
    if item["remaining"] <= 0:
        flash(t("{name} has just been fully claimed.", name=item["name"]), "error")
        save_pending([e for e in entries if e["id"] != item_id])
        return _back()
    if quantity > item["remaining"]:
        flash(
            t(
                "Only {n} {unit} of {name} are still needed.",
                n=item["remaining"],
                unit=item["unit"],
                name=item["name"],
            ),
            "error",
        )
        return _back(item_id)

    existing = next((e for e in entries if e["id"] == item_id), None)
    if existing:
        # Update in place so editing a note doesn't reshuffle the list.
        existing["quantity"] = quantity
        existing["note"] = note
        message = t("{name} updated.", name=item["name"])
    else:
        if len(entries) >= MAX_LIST_ITEMS:
            flash(t("Your list is full — please confirm what's on it first."), "error")
            return _back(item_id)
        entries.append({"id": item_id, "quantity": quantity, "note": note})
        message = t("{name} added to your list.", name=item["name"])

    if not fits_in_session(entries):
        flash(
            t(
                "That's more than your list can hold — please confirm what's on "
                "it first, or shorten a note."
            ),
            "error",
        )
        return _back(item_id)

    save_pending(entries)
    flash(message, "success")
    return _back(item_id)


@bp.post("/list/clear")
def list_clear():
    save_pending([])
    flash(t("Your list has been emptied."), "success")
    return redirect(url_for("public.index"))


@bp.post("/lang/<code>")
def switch_language(code):
    set_language(code)
    target = request.form.get("next", "")
    safe = target.startswith("/") and not target.startswith("//")
    return redirect(target if safe else url_for("public.index"))


# --------------------------------------------------------------------------
# Confirming
# --------------------------------------------------------------------------


def known_names():
    """Names already used, to suggest in the name box.

    Keeps spelling consistent between visits without needing accounts — the
    field stays free text, this only offers what's been typed before.
    """
    return [
        row["claimant_name"]
        for row in get_db().execute(
            """SELECT claimant_name, MAX(created_at) AS latest
               FROM claims
               GROUP BY claimant_name COLLATE NOCASE
               ORDER BY latest DESC
               LIMIT 200"""
        ).fetchall()
    ]


def _validate_contact(form):
    """Return an error message, or None if the details look usable."""
    if not form["claimant_name"]:
        return t("Please enter your name.")
    if len(form["claimant_name"]) > MAX_NAME_LEN:
        return t("That name is too long.")
    if len(form["general_note"]) > MAX_GENERAL_NOTE_LEN:
        return t("Please keep the note under {n} characters.", n=MAX_GENERAL_NOTE_LEN)
    return None


@bp.get("/confirm")
def confirm():
    details = pending_details()
    if not details:
        flash(t("Your list is empty — pick something you can bring."), "error")
        return redirect(url_for("public.index"))

    remembered = session.get(CONTACT_KEY) or {}
    return render_template(
        "confirm.html",
        details=details,
        names=known_names(),
        form={
            "claimant_name": remembered.get("name", ""),
            "general_note": "",
        },
        error=None,
    )


@bp.post("/confirm")
def submit_confirm():
    details = pending_details()
    if not details:
        flash(t("Your list is empty — pick something you can bring."), "error")
        return redirect(url_for("public.index"))

    form = {
        "claimant_name": request.form.get("claimant_name", "").strip(),
        "general_note": request.form.get("general_note", "").strip(),
    }

    error = _validate_contact(form)
    if error:
        return (
            render_template(
                "confirm.html",
                details=details,
                names=known_names(),
                form=form,
                error=error,
            ),
            400,
        )

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
                   (item_id, claimant_name, quantity, note, general_note)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    entry["id"],
                    form["claimant_name"],
                    entry["quantity"],
                    entry["note"] or None,
                    form["general_note"] or None,
                ),
            )
            placed.append(entry)

    # Remember the name so a return visit doesn't retype it.
    session[CONTACT_KEY] = {"name": form["claimant_name"]}
    # Anything that no longer fits stays on the list so it can be adjusted —
    # unless nothing is left at all, in which case keeping it is pointless.
    save_pending(
        [
            {"id": e["id"], "quantity": e["quantity"], "note": e["note"]}
            for e in short
            if e["remaining"] > 0
        ]
    )

    if placed:
        flash(
            t("Thank you, {name}! 1 item confirmed.", name=form["claimant_name"])
            if len(placed) == 1
            else t(
                "Thank you, {name}! {n} items confirmed.",
                name=form["claimant_name"],
                n=len(placed),
            ),
            "success",
        )
    if short:
        for entry in short:
            if entry["remaining"] > 0:
                flash(
                    t(
                        "{name}: only {n} {unit} left, so your {q} couldn't be "
                        "recorded. Adjust it below.",
                        name=entry["name"],
                        n=entry["remaining"],
                        unit=entry["unit"],
                        q=entry["quantity"],
                    ),
                    "error",
                )
            else:
                flash(
                    t(
                        "{name} was fully claimed by someone else before you "
                        "confirmed.",
                        name=entry["name"],
                    ),
                    "error",
                )
        return redirect(url_for("public.confirm"))

    return redirect(url_for("public.index"))
