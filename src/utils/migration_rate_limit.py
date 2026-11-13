"""In-process guard for legacy-password migration attempts.

Only SHA-256 digests of normalized emails and source IPs are retained. A
multi-worker deployment should additionally enforce a perimeter/WAF limit.
"""
from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic


class LegacyMigrationRateLimiter:
    def __init__(self, limit=5, window_seconds=15 * 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts = defaultdict(deque)
        self._lock = Lock()

    def allow(self, remote_addr: str | None, email: str | None) -> bool:
        digest = sha256((email or "").encode("utf-8")).hexdigest()
        keys = ("ip:" + (remote_addr or "unknown"), "email:" + digest)
        now = monotonic()
        with self._lock:
            for key in keys:
                bucket = self._attempts[key]
                while bucket and bucket[0] <= now - self.window_seconds:
                    bucket.popleft()
                if len(bucket) >= self.limit:
                    return False
            for key in keys:
                self._attempts[key].append(now)
        return True


legacy_migration_limiter = LegacyMigrationRateLimiter()
