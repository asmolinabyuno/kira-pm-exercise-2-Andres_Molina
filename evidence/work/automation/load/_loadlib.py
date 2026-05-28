"""Shared helpers for Phase 3 Stress & Latency probes.

Hard rules:
- Sandbox-only target loaded from ``KIRA_API_BASE_URL``.
- Secrets never persisted — every evidence write goes through ``_redact``.
- Conservative: callers enforce concurrency/total caps.
- This module imports ``evidence/work/_redact.py`` only — never modifies it.

Public API:
    cfg()                    -> Config (base url, headers helpers)
    auth_once()              -> bearer JWT (in-memory)
    auth_headers(token)      -> dict with x-api-key + bearer
    timed_request(...)       -> dict with status, elapsed_ms, body summary
    summarize_latency(samples_ms, endpoint, scenario, extra) -> latency JSON dict
    write_latency_json(...)  -> path
    percentile(samples, p)   -> float
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent  # evidence/work/automation/load
WORK = HERE.parents[1]                  # evidence/work
ROOT = WORK.parents[1]                  # project root

# Make _redact importable from evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers, redact_text  # noqa: E402

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Config:
    base_url: str
    client_id: str
    password: str
    api_key: str


def cfg() -> Config:
    return Config(
        base_url=os.environ["KIRA_API_BASE_URL"].rstrip("/"),
        client_id=os.environ["KIRA_CLIENT_ID"],
        password=os.environ["KIRA_COGNITO_SECRET"],
        api_key=os.environ["KIRA_API_KEY"],
    )


def auth_once(timeout: float = 30.0) -> str:
    """One-shot auth, returns JWT (in-memory only)."""
    c = cfg()
    resp = httpx.post(
        f"{c.base_url}/auth",
        headers={"Content-Type": "application/json", "x-api-key": c.api_key},
        json={"client_id": c.client_id, "password": c.password},
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data") or {}
    token = data.get("access_token") or body.get("access_token")
    if not token:
        raise RuntimeError("No access_token in auth response (shape changed?)")
    return token


def auth_headers(token: str) -> Dict[str, str]:
    c = cfg()
    return {
        "Content-Type": "application/json",
        "x-api-key": c.api_key,
        "Authorization": f"Bearer {token}",
    }


def timed_request(
    client: httpx.Client | httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Sync wrapper. Returns {status, elapsed_ms, retry_after, snippet}."""
    t0 = time.perf_counter_ns()
    resp = client.request(
        method,
        url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    snippet: Any
    try:
        snippet = resp.json()
    except Exception:
        snippet = resp.text[:500]
    return {
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "retry_after": resp.headers.get("retry-after") or resp.headers.get("Retry-After"),
        "x_api_version": resp.headers.get("x-api-version"),
        "x_amzn_errortype": resp.headers.get("x-amzn-errortype"),
        "snippet": _redact_snippet(snippet),
    }


async def atimed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    t0 = time.perf_counter_ns()
    resp = await client.request(
        method,
        url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    snippet: Any
    try:
        snippet = resp.json()
    except Exception:
        snippet = resp.text[:500]
    return {
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "retry_after": resp.headers.get("retry-after") or resp.headers.get("Retry-After"),
        "x_api_version": resp.headers.get("x-api-version"),
        "x_amzn_errortype": resp.headers.get("x-amzn-errortype"),
        "snippet": _redact_snippet(snippet),
    }


def _redact_snippet(value: Any) -> Any:
    """Best-effort redaction on response snippets before we persist them."""
    if isinstance(value, dict) or isinstance(value, list):
        return redact_body(value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def percentile(samples: List[float], p: float) -> float:
    """Linear-interpolation percentile. p in [0, 100]."""
    if not samples:
        return float("nan")
    s = sorted(samples)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    d0 = s[f] * (c - k)
    d1 = s[c] * (k - f)
    return d0 + d1


def summarize_latency(
    samples_ms: List[float],
    *,
    endpoint: str,
    scenario: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not samples_ms:
        return {
            "endpoint": endpoint,
            "scenario": scenario,
            "n": 0,
            "notes": "No samples collected.",
            **(extra or {}),
        }
    out = {
        "endpoint": endpoint,
        "scenario": scenario,
        "n": len(samples_ms),
        "min_ms": round(min(samples_ms), 2),
        "median_ms": round(percentile(samples_ms, 50), 2),
        "p95_ms": round(percentile(samples_ms, 95), 2),
        "p99_ms": round(percentile(samples_ms, 99), 2),
        "max_ms": round(max(samples_ms), 2),
        "samples_ms": [round(x, 2) for x in samples_ms],
    }
    if extra:
        out.update(extra)
    return out


def write_latency_json(payload: Dict[str, Any], filename: str) -> Path:
    out_dir = WORK / "latency"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / filename
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def write_scenario_log(slug: str, payload: Dict[str, Any], filename: str = "results.json") -> Path:
    out_dir = HERE / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / filename
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


# Known sandbox user_id from Phase 2 (created in evidence/work/users/).
# Used for endpoints that need a `user_id` query param (e.g., /v1/recipients).
KNOWN_USER_ID = "65ba0e06-9f52-4c43-b093-5d30a632ce3d"


def fake_clabe(seed: int) -> str:
    """Deterministic 18-digit CLABE-shaped string. Sandbox-only fake data."""
    # SPEI CLABE is 18 digits. Prefix 012180 keeps it shaped like Bancomer.
    suffix = f"{seed:012d}"
    return f"012180{suffix}"


def fake_recipient_body(seed: int) -> Dict[str, Any]:
    return {
        "user_id": KNOWN_USER_ID,
        "first_name": "Load",
        "last_name": f"Test{seed:04d}",
        "email": f"loadtest+{seed}-{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+525512345678",
        "account": {
            "account_type": "SPEI",
            "clabe": fake_clabe(seed),
            "doc_type": "rfc",
            "doc_number": "TFAK900101AAA",
            "bank_name": "Test SPEI Bank",
            "currency": "MXN",
            "country": "MX",
        },
    }


def fake_quotation_body() -> Dict[str, Any]:
    """Valid-shape body that hits sandbox fee-config 400 per DRIFT-E6."""
    return {"amount": "10000.00", "account_type": "ACH"}
