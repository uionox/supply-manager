# Camp Supply Tracker

A small web app for a Red Cross camp. An admin lists what the camp needs;
anyone can open the site, see what's still missing, and claim a quantity
they'll bring — name, phone number, optional note. No accounts, no signup.

Built to run on a 0.5 GB VPS: Flask + SQLite (stdlib `sqlite3`, no ORM),
server-rendered Jinja2, vanilla CSS/JS. No Node, no build step, no Docker.

## Running locally

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -r requirements.txt
```

(on Linux/macOS use `.venv/bin/pip`)

Create a `.env` from the example and set an admin password hash:

```bash
.venv/Scripts/flask --app wsgi hash-password "letmein"
```

Then run it:

```bash
.venv/Scripts/flask --app wsgi run --debug
```

The database is created automatically at `instance/supply.db` on first boot.
To load a few sample categories and items:

```bash
.venv/Scripts/flask --app wsgi seed-demo
```

## Layout

| Path | What it holds |
| --- | --- |
| `app/public.py` | The public browse-and-claim page |
| `app/admin.py` | Dashboard, category/item CRUD, claim moderation, Excel export |
| `app/auth.py` | Single-password admin login |
| `app/db.py` | SQLite connection and the write-transaction helper |
| `schema.sql` | Table definitions, re-runnable |
| `deploy/` | systemd unit, Caddyfile, and step-by-step server setup |

## Notes

- **Claims can't oversubscribe an item.** Each submission re-reads the
  remaining quantity inside a `BEGIN IMMEDIATE` transaction, so two people
  racing for the last units can't both win.
- **The database file is gitignored** (`instance/`), so deploying with
  `git pull` never touches live data.
- **Every page works without JavaScript.** The claim form is a `<details>`
  disclosure; JS only clamps the quantity field and prevents double-submits.

See [deploy/DEPLOY.md](deploy/DEPLOY.md) for the server setup.
