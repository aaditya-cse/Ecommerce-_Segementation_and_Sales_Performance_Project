"""Security utilities for request rate limiting, CSV sanitization, and HTTP headers."""

import csv
import io
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
from flask import Response


class SlidingWindowRateLimiter:
    """In-memory per-IP sliding-window rate limiter to prevent endpoint abuse."""

    def __init__(self, max_requests: int = 25, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds) for the given client identifier."""
        now = time.monotonic()
        bucket = self._hits[client_id]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0


def validate_csv_bytes(raw_bytes: bytes, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Validate uploaded CSV payload size, UTF-8 encoding, and tabular structure."""
    if not raw_bytes:
        raise ValueError("Uploaded CSV file is empty.")
    if len(raw_bytes) > max_bytes:
        raise ValueError("Uploaded CSV exceeds the 5 MB size limit.")
    if b"\x00" in raw_bytes[:4096]:
        raise ValueError("Binary content detected. Please upload a valid text CSV file.")
    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV file must be UTF-8 encoded.") from exc

    reader = csv.reader(io.StringIO(decoded))
    rows = [row for _, row in zip(range(5), reader) if any(cell.strip() for cell in row)]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ValueError("CSV must contain a header row and at least one data row with 2+ columns.")
    return decoded


def sanitize_csv_cell(value: str) -> str:
    """Neutralize spreadsheet formula injection characters (=, +, -, @, tab, CR)."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def apply_hardened_headers(response):
    """Attach hardened OWASP security headers including CSP and HSTS."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

