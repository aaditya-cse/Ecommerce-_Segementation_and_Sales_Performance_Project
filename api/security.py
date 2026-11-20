"""Security utilities for request rate limiting, CSV sanitization, and HTTP headers."""

import csv
import io
import os
import re
import base64
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple
from flask import Response


def generate_nonce() -> str:
    """Return a 16-byte URL-safe base64-encoded nonce for CSP use."""
    return base64.urlsafe_b64encode(os.urandom(16)).decode("ascii")


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


# Binary magic-byte signatures that indicate non-CSV content
_BINARY_SIGNATURES = (
    b"PK",           # ZIP
    b"%PDF",         # PDF
    b"\xff\xd8\xff", # JPEG
    b"\x89PNG",      # PNG
    b"GIF8",         # GIF
    b"BM",           # BMP
)

# SQL injection patterns in column names
_SQL_INJECTION_RE = re.compile(r"\b(DROP|INSERT|DELETE|SELECT|UNION)\b", re.IGNORECASE)

_MAX_ROW_ESTIMATE = 100_000


def validate_csv_bytes(raw_bytes: bytes, max_bytes: int = 5 * 1024 * 1024) -> str:
    """Validate uploaded CSV payload size, UTF-8 encoding, and tabular structure."""
    if not raw_bytes:
        raise ValueError("Uploaded CSV file is empty.")
    if len(raw_bytes) > max_bytes:
        raise ValueError("Uploaded CSV exceeds the 5 MB size limit.")

    # Binary MIME-sniffing check
    for sig in _BINARY_SIGNATURES:
        if raw_bytes.startswith(sig):
            raise ValueError("Binary file detected")

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

    # SQL injection check on header column names
    for col in rows[0]:
        if _SQL_INJECTION_RE.search(col):
            raise ValueError("Suspicious column names detected")

    # Row count estimate: guard against huge files
    file_size = len(raw_bytes)
    # Sample average row size from first two data rows
    sample_lines = decoded.splitlines()
    sample_rows = [l for l in sample_lines[1:3] if l.strip()]
    if sample_rows:
        avg_row_size = max(1, sum(len(r) for r in sample_rows) // len(sample_rows))
        estimated_rows = file_size // avg_row_size
        if estimated_rows > _MAX_ROW_ESTIMATE:
            raise ValueError(
                f"CSV appears to exceed the 100,000 row limit (estimated {estimated_rows:,} rows)."
            )

    return decoded


def sanitize_csv_cell(value: str) -> str:
    """Neutralize spreadsheet formula injection characters (=, +, -, @, tab, CR, |, `)."""
    if not value:
        return value
    # Leading formula injection triggers (including pipe and backtick)
    if value[0] in ("=", "+", "-", "@", "\t", "\r", "|", "`"):
        return "'" + value
    # DDE attack: tab embedded after non-tab chars
    if "\t" in value[1:]:
        return "'" + value
    return value


def apply_hardened_headers(response: Response) -> Response:
    """Attach hardened OWASP security headers including CSP and HSTS."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline'; "
        "script-src-attr 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-DNS-Prefetch-Control"] = "off"
    response.headers.pop("Server", None)
    return response
