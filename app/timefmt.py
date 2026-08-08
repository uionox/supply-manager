"""Claim timestamps are stored in UTC; people read them in camp time."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STORED_FORMAT = "%Y-%m-%d %H:%M:%S"
DISPLAY_FORMAT = "%d %b %Y, %H:%M"


def get_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def to_local(stored, zone):
    """Parse a `datetime('now')` value and move it into `zone`.

    Returns None for anything that doesn't parse, so a bad row shows the raw
    value rather than breaking the page.
    """
    if not stored:
        return None
    try:
        naive = datetime.strptime(str(stored), STORED_FORMAT)
    except ValueError:
        return None
    return naive.replace(tzinfo=timezone.utc).astimezone(zone)


def init_app(app):
    zone = get_zone(app.config["DISPLAY_TIMEZONE"])

    @app.template_filter("localtime")
    def _localtime(stored):
        moment = to_local(stored, zone)
        return moment.strftime(DISPLAY_FORMAT) if moment else stored

    app.extensions["display_zone"] = zone
