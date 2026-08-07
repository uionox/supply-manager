"""Small `flask` commands for setup on the server."""

import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .db import ensure_schema, get_db


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create the database file and tables if they don't exist yet."""
    ensure_schema()
    click.echo(f"Database ready at {current_app.config['DATABASE']}")


@click.command("hash-password")
@click.argument("password")
def hash_password_command(password):
    """Print an ADMIN_PASSWORD_HASH value for the given password."""
    click.echo(generate_password_hash(password))


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    """Insert a little sample data. Refuses to run if anything exists."""
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]:
        raise click.ClickException("Database already has data; not seeding.")

    data = {
        "Food & Water": [
            ("Bottled water", "1.5L bottles, sealed.", 200, "bottles"),
            ("Canned food", "Long shelf life, no pork.", 120, "cans"),
        ],
        "Bedding": [
            ("Blankets", "Clean, warm, any size.", 60, "pcs"),
            ("Sleeping mats", "Foam or inflatable.", 40, "pcs"),
        ],
        "Hygiene": [
            ("Soap bars", "Unscented preferred.", 150, "bars"),
            ("Toothbrushes", "Individually wrapped.", 100, "pcs"),
        ],
    }
    for cat_order, (cat_name, items) in enumerate(data.items()):
        cur = db.execute(
            "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
            (cat_name, cat_order),
        )
        cat_id = cur.lastrowid
        for order, (name, desc, qty, unit) in enumerate(items):
            db.execute(
                """INSERT INTO items
                   (category_id, name, description, quantity_needed, unit, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cat_id, name, desc, qty, unit, order),
            )
    click.echo("Sample categories and items inserted.")


def init_app(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(hash_password_command)
    app.cli.add_command(seed_demo_command)
