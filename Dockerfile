# The app has no compiled dependencies (Flask, Gunicorn, and openpyxl are
# all pure Python), so a single stage is enough — no build tools to strip
# out afterward.
FROM python:3.12-slim-bookworm

# - PYTHONDONTWRITEBYTECODE: skip .pyc files, pointless in a container that
#   gets rebuilt from source every deploy.
# - PYTHONUNBUFFERED: flush stdout/stderr immediately so `docker logs` shows
#   Gunicorn's output as it happens instead of on a buffering delay.
# - PIP_NO_CACHE_DIR: pip's download cache would just be dead weight in the
#   final image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Installed before the rest of the source is copied in, so `docker build`
# reuses this (slow) layer whenever only application code changed.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# instance/ holds the SQLite database and the generated session secret —
# neither should ever be baked into an image. Mount a volume over this
# directory at runtime (see docker-compose.yml) so data survives a rebuild.
RUN useradd --system --create-home --home-dir /home/supply --shell /usr/sbin/nologin supply \
    && mkdir -p instance \
    && chown -R supply:supply /app
USER supply

ENV DATABASE_PATH=/app/instance/supply.db

EXPOSE 8000
VOLUME ["/app/instance"]

# No curl in the slim image, so the healthcheck speaks HTTP directly with
# stdlib urllib rather than pulling in another package just for this.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/', timeout=2)" || exit 1

# Worker count matches deploy/supply-manager.service (4, one per vCPU on the
# current VPS) — see deploy/DEPLOY.md for why that's plenty for this app's
# traffic rather than Gunicorn's usual (2 x cores) + 1 rule of thumb.
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
