"""Shared helpers for Phase 3 abuse scenarios.

Imports ``auth`` and ``capture`` from ``run_flow.py`` (read-only — never patched).
Provides:
  - SESSION_TOKEN — single shared bearer for the run
  - call(method, url, headers, body, step, outcome, filename) → records evidence
  - parallel_call(...) — thread-pooled concurrent HTTP probe

All evidence is redacted via ``_redact.py``.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent  # evidence/work/abuse
WORK = HERE.parent  # evidence/work
ROOT = WORK.parents[1]
for p in (str(WORK), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import auth  # noqa: E402 — read-only import

load_dotenv(ROOT / ".env")

BASE_URL = os.environ["KIRA_API_BASE_URL"].rstrip("/")
API_KEY = os.environ["KIRA_API_KEY"]
CLIENT_ID = os.environ["KIRA_CLIENT_ID"]

# Known user IDs from prior batches (in-memory references only; no PII):
USER_CREATED = "65ba0e06-9f52-4c43-b093-5d30a632ce3d"  # Batch A/C user — CREATED
USER_REVIEW_INDIV = "02e4e953-f423-4a7a-8828-f9c2a2ecb1c7"  # Batch B — individual REVIEW
USER_REVIEW_BIZ = "0ba8a87a-a49e-423b-86fb-c6a025ba27f9"  # Batch B — business REVIEW

_TOKEN_LOCK = threading.Lock()
_TOKEN: Optional[str] = None


def get_token() -> str:
    """Return the cached bearer, fetching on first use. Thread-safe."""
    global _TOKEN
    with _TOKEN_LOCK:
        if _TOKEN is None:
            t = auth()
            if not t:
                raise RuntimeError("auth() returned no token — cannot run abuse probes")
            _TOKEN = t
        return _TOKEN


def base_headers(*, with_bearer: bool = True, with_apikey: bool = True) -> Dict[str, str]:
    h: Dict[str, str] = {"Content-Type": "application/json"}
    if with_apikey:
        h["x-api-key"] = API_KEY
    if with_bearer:
        h["Authorization"] = f"Bearer {get_token()}"
    return h


def write_evidence(
    scenario_slug: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    elapsed_ms: float,
    outcome: str,
    filename: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write a redacted evidence file under abuse/<slug>/<filename>.json."""
    out_dir = HERE / scenario_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{filename}.json"
    payload: Dict[str, Any] = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": round(elapsed_ms, 2),
        "outcome": outcome,
        "request": {
            "method": request["method"],
            "url": request["url"],
            "headers": redact_headers(request.get("headers", {}) or {}),
            "body": redact_body(request.get("body")) if request.get("body") is not None else None,
        },
        "response": {
            "status": response["status"],
            "headers": redact_headers(response.get("headers", {}) or {}),
            "body": redact_body(response.get("body")),
        },
    }
    if extra:
        payload["extra"] = extra
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def call(
    *,
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    scenario_slug: str,
    outcome_hint: str,
    filename: str,
    timeout: float = 30.0,
) -> Tuple[int, Any, Path, float]:
    """Send one HTTP request and write evidence. Returns (status, parsed_body, path, elapsed_ms)."""
    t0 = time.perf_counter_ns()
    try:
        resp = httpx.request(method, url, headers=headers, json=body, timeout=timeout)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        try:
            parsed: Any = resp.json()
        except Exception:
            parsed = resp.text
        outcome = f"{'success' if 200 <= resp.status_code < 300 else 'fail'}-{resp.status_code}-{outcome_hint}"
        p = write_evidence(
            scenario_slug,
            request={"method": method, "url": url, "headers": headers, "body": body},
            response={"status": resp.status_code, "headers": dict(resp.headers), "body": parsed},
            elapsed_ms=elapsed_ms,
            outcome=outcome,
            filename=filename,
        )
        return resp.status_code, parsed, p, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        p = write_evidence(
            scenario_slug,
            request={"method": method, "url": url, "headers": headers, "body": body},
            response={"status": -1, "headers": {}, "body": f"EXCEPTION: {type(e).__name__}: {e}"},
            elapsed_ms=elapsed_ms,
            outcome=f"exception-{outcome_hint}",
            filename=filename,
        )
        return -1, None, p, elapsed_ms


def parallel_call(
    *,
    method: str,
    url: str,
    body_factory,
    headers_factory,
    n: int,
    scenario_slug: str,
    filename_prefix: str,
    outcome_hint: str,
) -> List[Tuple[int, Any, Path, float, int]]:
    """Fire `n` concurrent HTTP requests via thread pool.

    body_factory(i)->dict|None and headers_factory(i)->dict are called per worker
    so callers can vary inputs per request. Returns list of (status, body, path,
    elapsed_ms, worker_index) — preserves order via worker_index.
    """
    results: List[Tuple[int, Any, Path, float, int]] = []
    barrier = threading.Barrier(n)

    def worker(idx: int):
        h = headers_factory(idx)
        b = body_factory(idx)
        barrier.wait(timeout=10)  # synchronize start
        t0 = time.perf_counter_ns()
        try:
            resp = httpx.request(method, url, headers=h, json=b, timeout=30.0)
            elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
            try:
                parsed: Any = resp.json()
            except Exception:
                parsed = resp.text
            outcome = f"{'success' if 200 <= resp.status_code < 300 else 'fail'}-{resp.status_code}-{outcome_hint}"
            p = write_evidence(
                scenario_slug,
                request={"method": method, "url": url, "headers": h, "body": b},
                response={"status": resp.status_code, "headers": dict(resp.headers), "body": parsed},
                elapsed_ms=elapsed_ms,
                outcome=outcome,
                filename=f"{filename_prefix}-w{idx:02d}",
                extra={"worker_index": idx, "t0_perf_ns": t0},
            )
            return (resp.status_code, parsed, p, elapsed_ms, idx)
        except Exception as e:
            elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
            p = write_evidence(
                scenario_slug,
                request={"method": method, "url": url, "headers": h, "body": b},
                response={"status": -1, "headers": {}, "body": f"EXCEPTION: {type(e).__name__}: {e}"},
                elapsed_ms=elapsed_ms,
                outcome=f"exception-{outcome_hint}",
                filename=f"{filename_prefix}-w{idx:02d}",
                extra={"worker_index": idx, "t0_perf_ns": t0},
            )
            return (-1, None, p, elapsed_ms, idx)

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(worker, i) for i in range(n)]
        for f in as_completed(futures):
            results.append(f.result())
    results.sort(key=lambda r: r[4])
    return results


def write_summary(scenario_slug: str, summary: Dict[str, Any]) -> Path:
    out_dir = HERE / scenario_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "_summary.json"
    p.write_text(json.dumps(summary, indent=2, default=str, ensure_ascii=False))
    return p


# ---------------------------------------------------------------------------
# Payload builders (sandbox-only fake data)
# ---------------------------------------------------------------------------

def spei_payload(*, user_id: str = USER_CREATED, clabe: Optional[str] = None,
                 last_name: str = "Beneficiary", country: str = "MX") -> Dict[str, Any]:
    """Build a SPEI recipient body. CLABE format: 3-digit bank + 15 numeric chars."""
    if clabe is None:
        # 012 prefix (BBVA shape) + 15 deterministic digits — caller can override
        clabe = "012180001234567890"
    return {
        "user_id": user_id,
        "first_name": "Test",
        "last_name": last_name,
        "email": f"test+abuse-{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+525512345678",
        "account": {
            "account_type": "SPEI",
            "clabe": clabe,
            "doc_type": "rfc",
            "doc_number": "TFAK900101AAA",
            "bank_name": "Test SPEI Bank",
            "currency": "MXN",
            "country": country,
        },
    }


def random_clabe(seed_idx: int) -> str:
    """Generate a format-valid-shape (18-digit) CLABE.

    Sandbox accepts our existing CLABE format; just rotate the trailing digits.
    """
    base = "012180001234567"  # 15 digits (3-digit bank + 12 acct)
    suffix = f"{seed_idx % 1000:03d}"
    return base + suffix
