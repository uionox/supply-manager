# Deploying the Camp Supply Tracker

Written for a Debian/Ubuntu VPS. The app itself is light — Flask, stdlib
SQLite, no build step — so it runs comfortably on a 0.5 GB box, but these
steps target the current deployment target: **8 GB RAM, 4 vCPU**, which
is why the systemd unit below runs 4 Gunicorn workers instead of 2.
Everything here assumes the app lives at `/srv/supply-manager`.

## 1. System packages

```bash
sudo apt update && sudo apt install -y python3-venv git
```

Install Caddy from the official repo (see https://caddyserver.com/docs/install).

## 2. A user and the code

```bash
sudo useradd --system --home /srv/supply-manager --shell /usr/sbin/nologin supply
sudo git clone https://github.com/uionox/supply-manager.git /srv/supply-manager
sudo chown -R supply:supply /srv/supply-manager
```

## 3. Virtualenv

```bash
sudo -u supply python3 -m venv /srv/supply-manager/.venv
sudo -u supply /srv/supply-manager/.venv/bin/pip install -r /srv/supply-manager/requirements.txt
```

## 4. Configuration

```bash
sudo -u supply cp /srv/supply-manager/.env.example /srv/supply-manager/.env
sudo chmod 600 /srv/supply-manager/.env
```

The only required value is the admin password hash:

```bash
cd /srv/supply-manager && sudo -u supply .venv/bin/flask --app wsgi hash-password "your-admin-password"
```

Paste the output as `ADMIN_PASSWORD_HASH`. The plain password is never stored.

Check the rest of `.env` before moving on:

| Setting | Why it matters |
| --- | --- |
| `SESSION_COOKIE_SECURE=1` | Keeps the admin cookie off plain HTTP. Only ever set to `0` for local development. |
| `TRUST_PROXY=1` | Caddy is in front, so the real visitor IP is used for login throttling instead of `127.0.0.1`. Leave at `0` if nothing proxies the app, or the header can be forged. |
| `DISPLAY_TIMEZONE` | Timezone claim times are shown in. Storage is always UTC. |
| `SECRET_KEY` | Optional. Left unset, a random key is generated once into `instance/secret_key`. Setting it to an obvious placeholder makes the app refuse to start, on purpose. |

## 5. Create the database

```bash
cd /srv/supply-manager && sudo -u supply .venv/bin/flask --app wsgi init-db
```

This creates `instance/supply.db`. That directory is gitignored, so
`git pull` never touches live data.

## 6. Run it under systemd

```bash
sudo cp /srv/supply-manager/deploy/supply-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now supply-manager
sudo systemctl status supply-manager
```

The unit runs 4 Gunicorn workers, one per vCPU. Gunicorn's own rule of
thumb is `(2 × cores) + 1`, but this app's actual traffic — dozens of
visitors, one admin — never gets close to stressing even 2, and SQLite
serializes every write regardless of worker count (see
`write_transaction()` in [app/db.py](../app/db.py)). More workers mainly
buys headroom for concurrent page reads during a burst, not raw
throughput, so there's no need to chase the full formula here. Edit
`--workers` in the `.service` file and `systemctl daemon-reload` +
`restart` if you ever want to change it.

## 7. Put Caddy in front

Edit `deploy/Caddyfile` to use the real domain, then:

```bash
sudo cp /srv/supply-manager/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy obtains and renews the TLS certificate on its own — nothing else to do.

## 8. Backups

The whole database is one file. A nightly copy is enough:

```bash
sudo crontab -e
```

```
0 3 * * * sqlite3 /srv/supply-manager/instance/supply.db ".backup '/var/backups/supply-$(date +\%F).db'"
```

`.backup` is safe to run while the app is live; a plain `cp` can catch a
half-written page. Install `sqlite3` (`sudo apt install sqlite3`) for this.

## Updating after a code change

```bash
cd /srv/supply-manager && sudo -u supply git pull && sudo systemctl restart supply-manager
```

Schema changes apply themselves on the next start, so no migration step.

## Checking it worked

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://supplies.example.org/
```

```bash
sudo journalctl -u supply-manager -n 30 --no-pager
```

Then sign in at `/admin`, add a category and an item, and claim it from a
phone.

## Shutting the site down for good

```bash
sudo systemctl disable --now supply-manager
sudo cp /srv/supply-manager/instance/supply.db ~/supply-final-export.db
```

Take a final Excel export from the admin page first if you want the data in
a readable form.
