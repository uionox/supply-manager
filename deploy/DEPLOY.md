# Deploying the Camp Supply Tracker

Written for a small Debian/Ubuntu VPS (0.5 GB RAM is enough). Everything
here assumes the app lives at `/srv/supply-manager`.

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

Generate the two secrets and paste them into `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

```bash
sudo -u supply /srv/supply-manager/.venv/bin/flask --app wsgi hash-password "your-admin-password"
```

> Run the `hash-password` command from `/srv/supply-manager`. The output is
> the `ADMIN_PASSWORD_HASH` value — the plain password is never stored.

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

## Shutting the site down for good

```bash
sudo systemctl disable --now supply-manager
sudo cp /srv/supply-manager/instance/supply.db ~/supply-final-export.db
```

Take a final Excel export from the admin page first if you want the data in
a readable form.
