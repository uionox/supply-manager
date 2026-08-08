"""Session-key handling and login throttling."""

import os
import secrets
import threading
import time

# The value this app used to fall back to. It is published in the repository,
# so anyone could forge an admin session cookie with it — never accept it.
COMPROMISED_KEYS = {"dev-key-not-for-production", "change-me", "dev", "secret"}


def resolve_secret_key(instance_path):
    """The key that signs session cookies.

    SECRET_KEY from the environment wins. Otherwise a random key is generated
    once and kept in the instance directory — that survives restarts, is
    shared by every Gunicorn worker, and is never committed. The point is
    that there is no shared default to fall back to.
    """
    from_env = os.environ.get("SECRET_KEY", "").strip()
    if from_env and from_env not in COMPROMISED_KEYS:
        return from_env
    if from_env:
        raise RuntimeError(
            "SECRET_KEY is set to a placeholder that is public in this "
            "repository, so admin sessions could be forged. Generate a real "
            'one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )

    key_path = os.path.join(instance_path, "secret_key")
    if not os.path.exists(key_path):
        # Two workers can boot at once, so write to a private temporary file
        # and swap it in. Whoever loses the race just reads the winner's key.
        temporary = f"{key_path}.{os.getpid()}"
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(handle, secrets.token_hex(32).encode("ascii"))
        finally:
            os.close(handle)
        try:
            os.replace(temporary, key_path)
        except OSError:  # pragma: no cover - another worker got there first
            os.unlink(temporary)

    with open(key_path, encoding="ascii") as fh:
        return fh.read().strip()


class LoginThrottle:
    """Slows down password guessing against the single admin password.

    Held in memory, so each Gunicorn worker counts separately and a restart
    forgets everything. That is fine for the threat here — it turns an
    unlimited guessing loop into a handful of tries per window, which is all
    a short-lived camp site needs.
    """

    def __init__(self, limit=8, window=900, lockout=900):
        self.limit = limit
        self.window = window
        self.lockout = lockout
        self._failures = {}
        self._lock = threading.Lock()

    def _prune(self, key, now):
        recent = [at for at in self._failures.get(key, []) if now - at < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def seconds_blocked(self, key):
        """How long this caller must wait, or 0 if they may try now."""
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, now)
            if len(recent) < self.limit:
                return 0
            return max(0, int(self.lockout - (now - recent[-1])) + 1)

    def record_failure(self, key):
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._failures.setdefault(key, []).append(now)

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)
