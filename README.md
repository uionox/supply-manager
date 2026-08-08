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
| `app/static/style.css` | The whole design system — tokens, components, responsive rules |
| `app/templates/partials/_icons.html` | Inline SVG icon macro |
| `schema.sql` | Table definitions, re-runnable |
| `deploy/` | systemd unit, Caddyfile, and step-by-step server setup |

## Design

Light-only, Inter for text and JetBrains Mono for quantities, matching the
IMS/warehouse admin look: `#f1f3f5` page, white cards on a 1px `#e2e5e9`
border at 8px radius, and a `#2563eb` accent. Colour carries meaning —
green for covered, amber for partly covered, red for destructive actions —
so the accent stays blue rather than competing with the danger red.

The public page is a single centred column built for phones. The admin side
is the familiar sidebar shell, which collapses to a drawer plus a bottom
nav bar under 768px.

## Languages

The public pages ship in English and Arabic, toggled from the header and
remembered in the session. Translations live in
[app/i18n.py](app/i18n.py) as a plain dict keyed on the English string —
no Flask-Babel, no `.mo` compilation step on the server. Arabic switches
the page to `dir="rtl"` and to the Noto Sans Arabic face.

Only the site's own wording is translated. Category names, item names,
descriptions and units are content the organisers type in, so they appear
exactly as entered in both languages. **The admin area is English-only**
and stays left-to-right whatever the visitor picked.

To add a string: wrap it in `t("…")` in the template or view, then add the
same English text as a key under `TRANSLATIONS["ar"]`. Anything missing a
translation falls back to English rather than breaking.

## How claiming works

Claiming is two steps, so somebody bringing eight things types their details
once rather than eight times:

1. **Build a list.** Each item takes a quantity and an optional note about
   that item ("all size L"). The list is held in the visitor's signed session
   cookie — nothing is written to the database yet, and no name or phone
   number is asked for.
2. **Review & confirm.** One screen shows the whole list with editable
   amounts and notes, then asks for name, phone, and an optional note about
   the whole drop-off ("dropping everything off Friday"). Every claim is
   written in a single transaction.

So there are two note levels: `claims.note` belongs to one item, and
`claims.general_note` describes the drop-off and is repeated across the
claims confirmed together. The public page shows the item note, falling back
to the drop-off note when an item has none, so a claim always shows something
useful. Admins see both, and the Excel export gives them separate columns.

No phone number is collected — the camp knows everyone taking part. The name
box suggests names already used on the site (a plain `<datalist>`, still free
text) so the same person doesn't end up recorded three different ways, and
the name is remembered in the session so a return visit arrives pre-filled.

The list lives in a cookie, so its size is checked on every change
(`SESSION_LIST_BUDGET` in [app/public.py](app/public.py)) — browsers drop
cookies over about 4KB, and per-item notes make the payload variable.

## Notes

- **Claims can't oversubscribe an item.** Every amount is re-read inside a
  `BEGIN IMMEDIATE` transaction at confirm time, so two people racing for the
  last units can't both win. Because a list can sit unconfirmed for a while,
  the confirm step reports per item: what was recorded, and what no longer
  fits (with the real number left, so it can be adjusted and retried).
- **The database file is gitignored** (`instance/`), so deploying with
  `git pull` never touches live data.
- **Every page works without JavaScript.** The claim form is a `<details>`
  disclosure; JS only clamps the quantity field and prevents double-submits.

See [deploy/DEPLOY.md](deploy/DEPLOY.md) for the server setup.
