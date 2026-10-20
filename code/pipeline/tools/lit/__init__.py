"""Literature tooling (L0). HTTP helpers live here so sources.py stays under 200 lines."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from tools.lit.schema import OA, Provenance, Record, Screening

TIMEOUT = 20
_LAST: dict[str, float] = {}

__all__ = ["OA", "Provenance", "Record", "Screening", "SourceUnavailable"]


@dataclass(frozen=True)
class SourceUnavailable:
    source: str
    reason: str


def _ua() -> dict[str, str]:
    return {"User-Agent": f"research-mvp-lit/0.1 (mailto:{os.environ.get('LIT_MAILTO', 'unset')})"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get(
    url: str, source: str, *, throttle: bool, retries: int = 2
) -> tuple[bytes, Provenance] | SourceUnavailable:
    if throttle:
        wait = 1.0 - (time.monotonic() - _LAST.get(source, 0.0))
        if wait > 0:
            time.sleep(wait)
        _LAST[source] = time.monotonic()
    last = "no attempt"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=_ua())
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read(), Provenance(source=source, url=url, retrieved_utc=_now())
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                return SourceUnavailable(source, last)
        except (urllib.error.URLError, TimeoutError) as exc:
            last = str(getattr(exc, "reason", exc) or type(exc).__name__)
            if attempt >= retries:
                return SourceUnavailable(source, last)
        time.sleep(float(attempt + 1))
    return SourceUnavailable(source, last)


def _json(
    url: str, source: str, *, throttle: bool, retries: int = 2
) -> tuple[Any, Provenance] | SourceUnavailable:
    got = _get(url, source, throttle=throttle, retries=retries)
    if isinstance(got, SourceUnavailable):
        return got
    try:
        return json.loads(got[0].decode("utf-8")), got[1]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return SourceUnavailable(source, f"json: {exc}")
