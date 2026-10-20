"""HTTP fetch. PubChem calls pin IPv4 because IPv6 TLS is reset on this machine.

## [EXPLORATORY]
"""

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime

from core.errors import PipelineError

# PubChem returns HTTP 503 / empty bodies when calls are issued back to back.
_PAUSE_S = 1.2
_TIMEOUT_S = 90
_ATTEMPTS = 5
_USER_AGENT = "ProjectS-gpr68-audit/0.1 (local research pipeline)"


@contextmanager
def force_ipv4():
    """Resolve names as IPv4 only for the duration of the block."""
    original = socket.getaddrinfo

    def ipv4_only(
        host: str,
        port: int | str,
        family: int = 0,
        socktype: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list:
        return original(host, port, socket.AF_INET, socktype, proto, flags)

    socket.getaddrinfo = ipv4_only
    try:
        yield
    finally:
        socket.getaddrinfo = original


def fetch_bytes(url: str, *, ipv4: bool) -> tuple[bytes, str]:
    """GET ``url``. Returns ``(body, retrieved_utc)``. Raises ``PipelineError`` on failure."""
    retrieved = datetime.now(UTC).isoformat()
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    last_error: Exception | None = None
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            body = _open(request, ipv4=ipv4)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == _ATTEMPTS or not _retryable(exc):
                break
            time.sleep(_PAUSE_S * attempt)
            continue
        time.sleep(_PAUSE_S)
        return body, retrieved
    raise PipelineError(f"fetch failed for {url}: {last_error}")


def _open(request: urllib.request.Request, *, ipv4: bool) -> bytes:
    return _read(request, pinned=ipv4)


def _read(request: urllib.request.Request, *, pinned: bool) -> bytes:
    if pinned:
        with force_ipv4():
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                return _body(response, request.full_url)
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        return _body(response, request.full_url)


def _body(response: object, url: str) -> bytes:
    status = getattr(response, "status", None)
    if status != 200:
        raise PipelineError(f"HTTP {status} for {url}")
    payload = response.read()
    if not isinstance(payload, bytes) or payload == b"":
        raise PipelineError(f"empty body for {url}")
    return payload


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {429, 500, 502, 503, 504}
    return True
