"""Batch A — Foundations & Reference Data probes.

Endpoints probed (all GET, all auth-only — no state mutation):
  1. GET /v1/countries
  2. GET /v1/banks  (with /v1/ vs no-prefix; ISO-3166 variants)
  3. GET /v1/users  (list)
  4. GET /v1/virtual-accounts  (list)
  5. GET /v1/recipients  (list)

Cross-cutting mutations applied per endpoint:
  - Omit x-api-key            (extends GAP-05 / GAP-04 envelope study)
  - Omit Authorization Bearer (GAP-04 — does x-api-key alone work?)
  - X-Api-Version: 2025-01-01 vs omit (GAP-01)
  - Pagination: default vs limit=100000 vs offset=99999 (list endpoints)
  - /v1/banks only: drop /v1/ prefix entirely (GAP-32)

Hard rules (do not violate):
  - Never write raw secrets — uses `_redact` from sibling module.
  - Does not modify `run_flow.py`; imports `auth`, `capture`, `BASE_URL`, `API_KEY`.
  - Per-call evidence files written to:
      evidence/work/countries/    (Family: countries)
      evidence/work/banks/        (Family: banks)
      evidence/work/users-list/   (Family: users-list — separate from users/ batch B)
      evidence/work/va-list/      (Family: va-list)
      evidence/work/recipients/   (Family: recipients)
  - Latency files:
      evidence/work/latency/get_v1_countries.json
      evidence/work/latency/get_v1_banks.json
      evidence/work/latency/get_v1_users.json
      evidence/work/latency/get_v1_virtual_accounts.json
      evidence/work/latency/get_v1_recipients.json

Run: ``python3 evidence/work/probes/batch_A.py``
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Make parent (evidence/work) and `_redact`+`run_flow` importable.
HERE = Path(__file__).resolve().parent
WORK = HERE.parent  # evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import (  # noqa: E402  — reuse helpers, do not modify
    API_KEY,
    BASE_URL,
    auth,
)

EVIDENCE_DIR = WORK


# ---------------------------------------------------------------------------
# Local capture (writes to evidence/work/{family}/...) — copy of run_flow.capture
# kept here so we don't mutate the shared module. Same redaction rules.
# ---------------------------------------------------------------------------


def capture(
    family: str,
    attempt_id: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    elapsed_ms: float,
    outcome: str,
    filename: Optional[str] = None,
) -> Path:
    """Write a single request/response evidence file under ``evidence/work/{family}/``."""
    out_dir = EVIDENCE_DIR / family
    out_dir.mkdir(parents=True, exist_ok=True)
    if filename is not None:
        out = out_dir / f"{filename}.json"
    else:
        existing = sorted(out_dir.glob("*.json"))
        nn = f"{len(existing) + 1:02d}"
        out = out_dir / f"{nn}-{outcome}.json"

    req_body = request.get("body")
    resp_body = response.get("body")

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "elapsed_ms": round(elapsed_ms, 2),
        "outcome": outcome,
        "request": {
            "method": request["method"],
            "url": request["url"],
            "headers": redact_headers(request.get("headers", {}) or {}),
            "body": redact_body(req_body) if req_body is not None else None,
        },
        "response": {
            "status": response["status"],
            "headers": redact_headers(response.get("headers", {}) or {}),
            "body": redact_body(resp_body),
        },
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _do_get(
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    *,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, str], Any, float]:
    """Run a GET and return (status, response_headers, parsed_body, elapsed_ms).

    Body is parsed JSON if possible, else raw text. Returned headers are raw —
    redaction happens in :func:`capture`.
    """
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, params=params, timeout=timeout)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    return resp.status_code, dict(resp.headers), body, elapsed_ms


def _outcome(status: int, label: str) -> str:
    if 200 <= status < 300:
        return f"success-{label}" if label else "success"
    return f"fail-{status}-{label}" if label else f"fail-{status}"


def _shape_summary(body: Any) -> Dict[str, Any]:
    """Lightweight envelope-shape descriptor for the log.

    Returns a small dict the caller can dump in narrative — keys present at
    top level, whether it's an array or object, length if array.
    """
    if isinstance(body, list):
        return {"top_type": "array", "length": len(body), "first_keys": sorted((body[0].keys() if isinstance(body[0], dict) else [])) if body else []}
    if isinstance(body, dict):
        return {"top_type": "object", "keys": sorted(body.keys())}
    return {"top_type": type(body).__name__, "value": str(body)[:120]}


def _write_latency(family: str, samples_ms: List[float], notes: str) -> Path:
    out_dir = EVIDENCE_DIR / "latency"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"get_v1_{family}.json"
    payload: Dict[str, Any] = {
        "endpoint": f"GET /v1/{family.replace('_', '-')}",
        "n": len(samples_ms),
        "samples_ms": [round(s, 2) for s in samples_ms],
    }
    if samples_ms:
        payload["min_ms"] = round(min(samples_ms), 2)
        payload["max_ms"] = round(max(samples_ms), 2)
        payload["median_ms"] = round(statistics.median(samples_ms), 2)
    payload["notes"] = notes
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


# ---------------------------------------------------------------------------
# Per-endpoint probe sets.
# Each probe function returns a list of "iteration records" for the log:
#   { iter, label, status, outcome, elapsed_ms, shape, evidence_path }
# ---------------------------------------------------------------------------


def _std_headers(token: str, *, with_key: bool = True, with_bearer: bool = True, version: Optional[str] = "OMIT") -> Dict[str, str]:
    """Build standard request headers with toggles.

    - ``with_key``: include ``x-api-key``.
    - ``with_bearer``: include ``Authorization: Bearer <token>``.
    - ``version``: ``"OMIT"`` (no X-Api-Version), or a string value to send.
    """
    h: Dict[str, str] = {"Accept": "application/json"}
    if with_key:
        h["x-api-key"] = API_KEY
    if with_bearer:
        h["Authorization"] = f"Bearer {token}"
    if version != "OMIT" and version is not None:
        h["X-Api-Version"] = version
    return h


def probe_countries(token: str) -> Dict[str, Any]:
    family = "countries"
    url = f"{BASE_URL.rstrip('/')}/v1/countries"
    iterations: List[Dict[str, Any]] = []

    def _run(label: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, headers, params)
        outcome = _outcome(status, label)
        path = capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url, "headers": headers, "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        return {
            "iter": len(iterations) + 1,
            "label": label,
            "status": status,
            "outcome": outcome,
            "elapsed_ms": round(elapsed, 2),
            "shape": _shape_summary(body),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
            "x_api_version_resp": rh.get("x-api-version"),
        }

    # 1. Happy path — full headers, no version header
    iterations.append(_run("happy", _std_headers(token)))
    # 2. Omit x-api-key
    iterations.append(_run("no-apikey", _std_headers(token, with_key=False)))
    # 3. Omit Authorization (Bearer) — does x-api-key alone work? (GAP-04)
    iterations.append(_run("no-bearer", _std_headers(token, with_bearer=False)))
    # 4. Send X-Api-Version: 2025-01-01
    iterations.append(_run("xver-2025-01-01", _std_headers(token, version="2025-01-01")))
    # 5. Send X-Api-Version: 2026-04-14 (the documented version)
    iterations.append(_run("xver-2026-04-14", _std_headers(token, version="2026-04-14")))

    # 6. Pagination probe (rough): countries may not paginate, but try limit
    iterations.append(_run("limit-100000", _std_headers(token), params={"limit": 100000}))
    iterations.append(_run("offset-99999", _std_headers(token), params={"offset": 99999}))

    # Latency sampling — 3 successful calls if happy succeeded
    samples: List[float] = []
    if iterations[0]["status"] == 200:
        samples.append(iterations[0]["elapsed_ms"])
        for i in range(3):
            attempt_id = str(uuid.uuid4())
            status, rh, body, elapsed = _do_get(url, _std_headers(token))
            outcome = _outcome(status, f"latency-{i+1}")
            capture(
                family,
                attempt_id,
                request={"method": "GET", "url": url, "headers": _std_headers(token), "body": None},
                response={"status": status, "headers": rh, "body": body},
                elapsed_ms=elapsed,
                outcome=outcome,
            )
            if status == 200:
                samples.append(elapsed)
    if samples:
        _write_latency(
            "countries",
            samples,
            notes=f"Preliminary baseline (n={len(samples)}). p50/p95/p99 require N>=10. Includes CF edge + AWS API GW + Lambda.",
        )

    return {"family": family, "url": url, "iterations": iterations, "latency_samples_ms": samples}


def probe_banks(token: str) -> Dict[str, Any]:
    family = "banks"
    url_v1 = f"{BASE_URL.rstrip('/')}/v1/banks"
    url_nov1 = f"{BASE_URL.rstrip('/')}/banks"
    iterations: List[Dict[str, Any]] = []

    def _run(label: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, headers, params)
        outcome = _outcome(status, label)
        path = capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""), "headers": headers, "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        return {
            "iter": len(iterations) + 1,
            "label": label,
            "url": url,
            "params": params or {},
            "status": status,
            "outcome": outcome,
            "elapsed_ms": round(elapsed, 2),
            "shape": _shape_summary(body),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        }

    # === GAP-32 disambiguation: /v1/banks vs /banks ===
    # 1. /v1/banks?country=MX
    iterations.append(_run("v1-country-MX", url_v1, _std_headers(token), params={"country": "MX"}))
    # 2. /banks?country=MX (no /v1/ prefix — what the Reference page actually documents)
    iterations.append(_run("nov1-country-MX", url_nov1, _std_headers(token), params={"country": "MX"}))

    # === ISO-3166 normalization probes (only run if at least one URL form responds) ===
    # 3. alpha-3: MEX
    iterations.append(_run("v1-country-MEX-alpha3", url_v1, _std_headers(token), params={"country": "MEX"}))
    # 4. lowercase: mx
    iterations.append(_run("v1-country-mx-lower", url_v1, _std_headers(token), params={"country": "mx"}))
    # 5. English name: Mexico
    iterations.append(_run("v1-country-Mexico-name", url_v1, _std_headers(token), params={"country": "Mexico"}))
    # 6. omitted country
    iterations.append(_run("v1-no-country", url_v1, _std_headers(token)))

    # === Cross-cutting mutations on whichever form returned 2xx ===
    # Determine the "working" URL form for the country=MX case.
    working_url = url_v1 if iterations[0]["status"] == 200 else url_nov1 if iterations[1]["status"] == 200 else None

    if working_url is not None:
        # 7. Omit x-api-key
        iterations.append(_run("no-apikey", working_url, _std_headers(token, with_key=False), params={"country": "MX"}))
        # 8. Omit Bearer (GAP-04)
        iterations.append(_run("no-bearer", working_url, _std_headers(token, with_bearer=False), params={"country": "MX"}))
        # 9. X-Api-Version: 2025-01-01
        iterations.append(_run("xver-2025-01-01", working_url, _std_headers(token, version="2025-01-01"), params={"country": "MX"}))
        # 10. X-Api-Version: 2026-04-14
        iterations.append(_run("xver-2026-04-14", working_url, _std_headers(token, version="2026-04-14"), params={"country": "MX"}))

    # Latency sampling on working URL
    samples: List[float] = []
    if working_url is not None:
        # First sample is from the happy iteration
        first = iterations[0] if iterations[0]["status"] == 200 else iterations[1]
        samples.append(first["elapsed_ms"])
        for i in range(3):
            attempt_id = str(uuid.uuid4())
            status, rh, body, elapsed = _do_get(working_url, _std_headers(token), params={"country": "MX"})
            outcome = _outcome(status, f"latency-{i+1}")
            capture(
                family,
                attempt_id,
                request={"method": "GET", "url": working_url + "?country=MX", "headers": _std_headers(token), "body": None},
                response={"status": status, "headers": rh, "body": body},
                elapsed_ms=elapsed,
                outcome=outcome,
            )
            if status == 200:
                samples.append(elapsed)

    if samples:
        _write_latency(
            "banks",
            samples,
            notes=f"Preliminary baseline on {'working URL form' if working_url else 'NONE'} (n={len(samples)}). p50/p95/p99 require N>=10.",
        )

    return {"family": family, "iterations": iterations, "working_url": working_url, "latency_samples_ms": samples}


def probe_users_list(token: str) -> Dict[str, Any]:
    family = "users-list"
    url = f"{BASE_URL.rstrip('/')}/v1/users"
    iterations: List[Dict[str, Any]] = []

    def _run(label: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, headers, params)
        outcome = _outcome(status, label)
        path = capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""), "headers": headers, "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        return {
            "iter": len(iterations) + 1,
            "label": label,
            "status": status,
            "outcome": outcome,
            "elapsed_ms": round(elapsed, 2),
            "shape": _shape_summary(body),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        }

    iterations.append(_run("happy", _std_headers(token)))
    iterations.append(_run("no-apikey", _std_headers(token, with_key=False)))
    iterations.append(_run("no-bearer", _std_headers(token, with_bearer=False)))
    iterations.append(_run("xver-2025-01-01", _std_headers(token, version="2025-01-01")))
    iterations.append(_run("xver-2026-04-14", _std_headers(token, version="2026-04-14")))
    iterations.append(_run("limit-100000", _std_headers(token), params={"limit": 100000}))
    iterations.append(_run("offset-99999", _std_headers(token), params={"offset": 99999}))

    samples: List[float] = []
    if iterations[0]["status"] == 200:
        samples.append(iterations[0]["elapsed_ms"])
        for i in range(3):
            attempt_id = str(uuid.uuid4())
            status, rh, body, elapsed = _do_get(url, _std_headers(token))
            outcome = _outcome(status, f"latency-{i+1}")
            capture(
                family,
                attempt_id,
                request={"method": "GET", "url": url, "headers": _std_headers(token), "body": None},
                response={"status": status, "headers": rh, "body": body},
                elapsed_ms=elapsed,
                outcome=outcome,
            )
            if status == 200:
                samples.append(elapsed)
    if samples:
        _write_latency(
            "users",
            samples,
            notes=f"Preliminary baseline GET /v1/users (n={len(samples)}). p50/p95/p99 require N>=10.",
        )

    return {"family": family, "url": url, "iterations": iterations, "latency_samples_ms": samples}


def probe_virtual_accounts_list(token: str) -> Dict[str, Any]:
    family = "va-list"
    url = f"{BASE_URL.rstrip('/')}/v1/virtual-accounts"
    iterations: List[Dict[str, Any]] = []

    def _run(label: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, headers, params)
        outcome = _outcome(status, label)
        path = capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""), "headers": headers, "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        return {
            "iter": len(iterations) + 1,
            "label": label,
            "status": status,
            "outcome": outcome,
            "elapsed_ms": round(elapsed, 2),
            "shape": _shape_summary(body),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        }

    iterations.append(_run("happy", _std_headers(token)))
    iterations.append(_run("no-apikey", _std_headers(token, with_key=False)))
    iterations.append(_run("no-bearer", _std_headers(token, with_bearer=False)))
    iterations.append(_run("xver-2025-01-01", _std_headers(token, version="2025-01-01")))
    iterations.append(_run("xver-2026-04-14", _std_headers(token, version="2026-04-14")))
    iterations.append(_run("limit-100000", _std_headers(token), params={"limit": 100000}))
    iterations.append(_run("offset-99999", _std_headers(token), params={"offset": 99999}))

    samples: List[float] = []
    if iterations[0]["status"] == 200:
        samples.append(iterations[0]["elapsed_ms"])
        for i in range(3):
            attempt_id = str(uuid.uuid4())
            status, rh, body, elapsed = _do_get(url, _std_headers(token))
            outcome = _outcome(status, f"latency-{i+1}")
            capture(
                family,
                attempt_id,
                request={"method": "GET", "url": url, "headers": _std_headers(token), "body": None},
                response={"status": status, "headers": rh, "body": body},
                elapsed_ms=elapsed,
                outcome=outcome,
            )
            if status == 200:
                samples.append(elapsed)
    if samples:
        _write_latency(
            "virtual_accounts",
            samples,
            notes=f"Preliminary baseline GET /v1/virtual-accounts (n={len(samples)}). p50/p95/p99 require N>=10.",
        )

    return {"family": family, "url": url, "iterations": iterations, "latency_samples_ms": samples}


def probe_recipients_list(token: str) -> Dict[str, Any]:
    family = "recipients"
    url = f"{BASE_URL.rstrip('/')}/v1/recipients"
    iterations: List[Dict[str, Any]] = []

    def _run(label: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, headers, params)
        outcome = _outcome(status, label)
        path = capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""), "headers": headers, "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        return {
            "iter": len(iterations) + 1,
            "label": label,
            "status": status,
            "outcome": outcome,
            "elapsed_ms": round(elapsed, 2),
            "shape": _shape_summary(body),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        }

    # Recipients list is documented as requiring user_id. Probe without first (default) — capture the error shape.
    iterations.append(_run("happy-no-user-id", _std_headers(token)))
    iterations.append(_run("no-apikey", _std_headers(token, with_key=False)))
    iterations.append(_run("no-bearer", _std_headers(token, with_bearer=False)))
    iterations.append(_run("xver-2025-01-01", _std_headers(token, version="2025-01-01")))
    iterations.append(_run("xver-2026-04-14", _std_headers(token, version="2026-04-14")))
    iterations.append(_run("limit-100000", _std_headers(token), params={"limit": 100000}))
    iterations.append(_run("offset-99999", _std_headers(token), params={"offset": 99999}))
    # Junk user_id
    iterations.append(_run("junk-user-id", _std_headers(token), params={"user_id": "00000000-0000-0000-0000-000000000000"}))

    samples: List[float] = []
    # Latency samples on whatever the "default" call returned (could be 2xx or 4xx — but we measure base path).
    samples.append(iterations[0]["elapsed_ms"])
    for i in range(3):
        attempt_id = str(uuid.uuid4())
        status, rh, body, elapsed = _do_get(url, _std_headers(token))
        outcome = _outcome(status, f"latency-{i+1}")
        capture(
            family,
            attempt_id,
            request={"method": "GET", "url": url, "headers": _std_headers(token), "body": None},
            response={"status": status, "headers": rh, "body": body},
            elapsed_ms=elapsed,
            outcome=outcome,
        )
        samples.append(elapsed)
    _write_latency(
        "recipients",
        samples,
        notes=f"Preliminary baseline GET /v1/recipients (n={len(samples)}). Measures handler reach time even when returning 4xx (validation path). p50/p95/p99 require N>=10.",
    )

    return {"family": family, "url": url, "iterations": iterations, "latency_samples_ms": samples}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    print("[Batch A] Authenticating...")
    token = auth()
    if not token:
        print("[Batch A] AUTH FAILED — aborting.")
        return 2
    print("[Batch A] AUTH OK. Token cached in memory.")

    results: Dict[str, Any] = {}

    print("[Batch A] Probing GET /v1/countries ...")
    results["countries"] = probe_countries(token)
    print(f"  iters={len(results['countries']['iterations'])} latency_n={len(results['countries']['latency_samples_ms'])}")

    print("[Batch A] Probing GET /v1/banks vs /banks ...")
    results["banks"] = probe_banks(token)
    print(f"  iters={len(results['banks']['iterations'])} working_url={results['banks']['working_url']}")

    print("[Batch A] Probing GET /v1/users (list) ...")
    results["users_list"] = probe_users_list(token)
    print(f"  iters={len(results['users_list']['iterations'])} latency_n={len(results['users_list']['latency_samples_ms'])}")

    print("[Batch A] Probing GET /v1/virtual-accounts (list) ...")
    results["va_list"] = probe_virtual_accounts_list(token)
    print(f"  iters={len(results['va_list']['iterations'])}")

    print("[Batch A] Probing GET /v1/recipients (list) ...")
    results["recipients"] = probe_recipients_list(token)
    print(f"  iters={len(results['recipients']['iterations'])}")

    # Write a single batch-results JSON for the log generator to consume.
    summary_path = EVIDENCE_DIR / "probes" / "batch_A_results.json"
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[Batch A] Summary written to {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
