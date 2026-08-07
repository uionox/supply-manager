# Camp Supply Tracker — Design

Date: 2026-08-08
Status: Approved for planning

## Purpose

A temporary, one-time-use web app for a Red Cross camp. An admin lists items
needed (grouped into categories, each with description and quantity needed).
Visitors see what's still needed and claim a quantity they'll bring, with
name, phone number, and an optional note. Runs for a few weeks around the
event, then is shut down for good.

## Constraints

- Target server: 0.5GB RAM, slow CPU (small VPS). No Docker, no Node build
  step, no heavy frameworks/ORMs.
- Stack: Python + Flask + SQLite (stdlib `sqlite3`), Jinja2 server-rendered
  templates, vanilla JS/CSS.
- Served by Gunicorn (1–2 workers) behind Caddy for automatic HTTPS.
- Content is English only.
- Low traffic (dozens of users), so SQLite is sufficient — no need for a
  separate DB server.

## Architecture

Single Flask app using the application-factory pattern, split into two
blueprints (`public`, `admin`) plus small `db.py`/`auth.py` helpers. No ORM —
raw SQL via stdlib `sqlite3`, using `sqlite3.Row` for dict-like row access.

```
supply-manager/
  app/
    __init__.py          # app factory, config from env vars
    db.py                 # get_db(), schema init, transaction helper
    auth.py                # admin login/logout, session, @login_required decorator
    public.py              # blueprint: index (browse+claim), submit claim
    admin.py               # blueprint: dashboard, category/item CRUD, claims mgmt, xlsx export
    templates/
      base.html
      index.html            # public browse/claim page
      admin/
        login.html
        dashboard.html
        categories.html
        items.html
        item_form.html
        item_claims.html      # claims for one item, with delete action
    static/
      style.css
      claim.js               # claim modal open/close, client-side qty cap (UX only)
  schema.sql               # CREATE TABLE statements, run once at startup if DB absent
  wsgi.py                  # entrypoint for gunicorn
  requirements.txt          # Flask, gunicorn, openpyxl
  .env.example
  .gitignore                # instance/, .env, __pycache__/
  instance/                 # gitignored; holds supply.db at runtime
  deploy/
    supply-manager.service    # systemd unit template
    Caddyfile                  # reverse proxy + auto-HTTPS template
    DEPLOY.md                   # step-by-step VPS setup instructions
```

## Data model

```sql
categories(id, name, sort_order)
items(id, category_id FK, name, description, quantity_needed, unit, sort_order)
claims(id, item_id FK, claimant_name, phone_number, quantity, note NULL, created_at)
```

- `quantity_remaining = quantity_needed - SUM(claims.quantity WHERE item_id = ?)`,
  computed on read (no stored column, no cache — trivial query volume).
- `CHECK(quantity_needed > 0)`, `CHECK(quantity > 0)` at the schema level as a
  backstop; app logic is the primary guard (see Validation below).
- Deleting a category or item that still has claims is **blocked** in the UI
  (admin must remove claims first, or the delete action explicitly warns and
  requires confirming it will also remove N claims). No silent cascade.

## Public page

- `/` — items grouped by category (ordered by `sort_order`), each showing
  name, description, unit, progress ("12 / 20 boxes claimed"), and the
  existing claims list (name, quantity, note — public, so people can
  coordinate without duplicating).
- "Claim this" opens an inline form (name, phone, quantity, optional note).
  Quantity input is capped client-side to the remaining amount for UX, but
  the server is the source of truth.
- Fully-claimed items show a "Fully claimed" badge and the claim control is
  disabled.
- Mobile-first single-column layout; no JS framework — one small script for
  modal open/close and the client-side quantity cap.

## Admin

- Password-protected: single admin password from `ADMIN_PASSWORD_HASH` env
  var (generated with `werkzeug.security.generate_password_hash`), Flask
  session-based login, no roles/users table.
- **Dashboard** (`/admin/`): total items, overall % fulfilled, table of items
  sorted by remaining quantity (most-needed first).
- **Categories**: create/edit/delete, reorder via up/down buttons (swaps
  `sort_order` with the adjacent row, small POST, no drag-and-drop library).
- **Items**: create/edit/delete (same reorder pattern), scoped to a category.
- **Claims**: from an item's detail view, list all claims including phone
  numbers (for follow-up), with a delete/cancel action per claim.
- **Export**: `/admin/export.xlsx` — one workbook, one sheet, one row per
  claim (category, item, unit, quantity needed, quantity remaining,
  claimant name, phone, quantity claimed, note, timestamp), built with
  `openpyxl` (pure Python, no pandas — keeps RAM footprint low).

## Concurrency

Claim submission runs inside a single SQLite transaction (`BEGIN IMMEDIATE`):
re-read `SUM(quantity)` for the item, verify `requested <= quantity_needed -
already_claimed`, insert if it fits, commit. SQLite's write lock serializes
concurrent writers, so two simultaneous claims can never push the total over
`quantity_needed` — the second request re-checks against the up-to-date sum
and is rejected (with a friendly "someone just claimed the rest, N left"
message) if it no longer fits.

## Validation

- Quantity: must be a positive integer, ≤ current remaining — enforced
  server-side inside the same transaction as the check above.
- Phone number: lenient regex (digits, spaces, `+`, `-`, `()`, 7–15 digits
  total) — no country-specific validation library, to stay lightweight.
- Name: required, non-empty after trimming.

## Deployment

- `deploy/supply-manager.service`: systemd unit running
  `gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app` from the project venv.
- `deploy/Caddyfile`: reverse proxy to `127.0.0.1:8000` with automatic HTTPS
  for the camp's domain.
- `deploy/DEPLOY.md`: step-by-step — clone repo, create venv, install
  requirements, set `.env` (admin password hash, secret key), initialize
  `instance/supply.db` from `schema.sql`, enable systemd service, point
  Caddy at the domain, notes on backing up `instance/supply.db` via periodic
  file copy.
- `instance/` (holding the live `.db` file) is gitignored, so `git pull` on
  the server never touches live data.

## Testing approach

- Manual verification via the dev server in a browser (public claim flow,
  admin CRUD, claim deletion, export) since this is a small, short-lived app
  without an existing test suite to extend.
- A lightweight `pytest` smoke-test module is optional and not required for
  v1, given the app's scope and lifespan — can be added later if useful.

## Out of scope

- User accounts / self-service claim editing (admin edits claims on behalf
  of users if needed).
- Multi-language / i18n framework (English only, per user decision).
- Anything beyond a single admin password (no roles, no multi-admin).
- Automated test suite (manual verification only, per app's short lifespan).
