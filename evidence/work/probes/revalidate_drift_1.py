"""Revalidate DRIFT-1 (the `/sandbox` URL prefix question) against the partner-
distributed Sandbox Integration Guide (received 2026-05-28).

Guide claims (contradicting our 2026-05-27 empirical DRIFT-1 finding):
- Sandbox base URL = `https://api.balampay.com/sandbox`
- One-time pin: POST https://api.balampay.com/sandbox/v1/versioning/upgrade
  body {"target_version":"2026-04-14"}
- After pinning, `X-Api-Version` becomes optional and (implied) `/sandbox`
  prefix should "just work" for everything.

Hard rules:
- httpx, timeout=30, no SDKs.
- Never log raw secrets — every capture file goes through _redact.
- 5–6 calls max, ≤3 attempts per probe.
- Standalone probe script — imports `auth`, `BASE_URL`, `API_KEY`, `capture`
  from run_flow but does NOT modify it.

Output:
- Each probe writes one evidence file under
  evidence/work/versioning/{NN}-{outcome}.json (created if missing).
- Probe 6 (simulate-deposit existence) also writes under versioning/.

Run: ``python3 evidence/work/probes/revalidate_drift_1.py``
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# Make parent (evidence/work) importable so we can reuse run_flow + _redact.
HERE = Path(__file__).resolve().parent
WORK = HERE.parent  # evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import API_KEY, auth, capture  # noqa: E402  — reuse, do not modify

# The guide's claimed bases — we test BOTH explicitly regardless of .env.
NO_PREFIX_BASE = "https://api.balampay.com"
SANDBOX_BASE = "https://api.balampay.com/sandbox"

TIMEOUT = 30.0
FAKE_VA_UUID = "00000000-0000-0000-0000-000000000000"


def _do(
    method: str,
    url: str,
    *,
    token: Optional[str],
    body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> tuple[int, Any, Dict[str, str], float]:
    """Execute one HTTP call, return (status, parsed_body, response_headers, elapsed_ms)."""
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)

    t0 = time.perf_counter_ns()
    if method == "GET":
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT)
    elif method == "POST":
        resp = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT)
    else:
        raise ValueError(f"Unsupported method: {method}")
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        parsed: Any = resp.json()
    except Exception:
        parsed = resp.text
    return resp.status_code, parsed, dict(resp.headers), elapsed_ms


def _outcome(status: int) -> str:
    if 200 <= status < 300:
        return "success"
    return f"fail-{status}"


def _save(
    nn: int,
    label: str,
    *,
    method: str,
    url: str,
    request_headers: Dict[str, str],
    request_body: Optional[Dict[str, Any]],
    status: int,
    response_headers: Dict[str, str],
    response_body: Any,
    elapsed_ms: float,
) -> Path:
    outcome = _outcome(status)
    filename = f"{nn:02d}-{label}-{outcome}"
    return capture(
        "versioning",
        attempt_id=str(uuid.uuid4()),
        request={
            "method": method,
            "url": url,
            "headers": request_headers,
            "body": request_body,
        },
        response={
            "status": status,
            "headers": response_headers,
            "body": response_body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )


def main() -> int:
    # -- Probe 1: baseline auth at the no-prefix base.
    print("Probe 1: baseline /auth at no-prefix base ...")
    token = auth()
    print(f"  Probe 1: auth {'OK' if token else 'FAILED'}")
    if not token:
        print("Cannot proceed without a bearer token. Abort.")
        return 2

    # Common request headers we will record (redacted in capture).
    base_req_headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    pin_body = {"target_version": "2026-04-14"}

    # -- Probe 2: pin attempt at no-prefix base (`/v1/versioning/upgrade`).
    print("Probe 2: POST /v1/versioning/upgrade at no-prefix base ...")
    url2 = f"{NO_PREFIX_BASE}/v1/versioning/upgrade"
    s2, b2, h2, e2 = _do("POST", url2, token=token, body=pin_body)
    p2 = _save(
        1, "pin-no-prefix",
        method="POST", url=url2,
        request_headers=base_req_headers, request_body=pin_body,
        status=s2, response_headers=h2, response_body=b2, elapsed_ms=e2,
    )
    print(f"  Probe 2: HTTP {s2} -> {p2.name}")

    # -- Probe 3: pin attempt at /sandbox base (`/sandbox/v1/versioning/upgrade`).
    print("Probe 3: POST /sandbox/v1/versioning/upgrade ...")
    url3 = f"{SANDBOX_BASE}/v1/versioning/upgrade"
    s3, b3, h3, e3 = _do("POST", url3, token=token, body=pin_body)
    p3 = _save(
        2, "pin-sandbox-prefix",
        method="POST", url=url3,
        request_headers=base_req_headers, request_body=pin_body,
        status=s3, response_headers=h3, response_body=b3, elapsed_ms=e3,
    )
    print(f"  Probe 3: HTTP {s3} -> {p3.name}")

    pin_succeeded = (200 <= s2 < 300) or (200 <= s3 < 300)
    pinned_base = None
    if 200 <= s2 < 300:
        pinned_base = NO_PREFIX_BASE
    elif 200 <= s3 < 300:
        pinned_base = SANDBOX_BASE

    # -- Probe 4: retry /sandbox/auth after pin attempt.
    print("Probe 4: retry POST /sandbox/auth (no bearer — same shape as /auth) ...")
    url4 = f"{SANDBOX_BASE}/auth"
    # auth() body is client_id+password — but we don't want to expose .env values
    # from here. The simpler diagnostic is: does the route exist at all post-pin?
    # We POST an empty body — pre-pin this returns 403 (gateway). Post-pin we
    # expect either 200 (if route now wired) or 400 (validation = route exists)
    # vs 403 (route still gated). Three signals, all diagnostic.
    s4, b4, h4, e4 = _do(
        "POST",
        url4,
        token=None,  # /auth must not carry a bearer
        body={},
        extra_headers={"X-Api-Version": "2026-04-14"},  # belt-and-suspenders
    )
    # capture request_headers must match what we actually sent (no Authorization)
    sent_h4 = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "X-Api-Version": "2026-04-14",
    }
    p4 = _save(
        3, "sandbox-auth-after-pin",
        method="POST", url=url4,
        request_headers=sent_h4, request_body={},
        status=s4, response_headers=h4, response_body=b4, elapsed_ms=e4,
    )
    print(f"  Probe 4: HTTP {s4} -> {p4.name}")

    # -- Probe 5: retry GET /sandbox/v1/users?limit=1 with bearer.
    print("Probe 5: retry GET /sandbox/v1/users?limit=1 with bearer ...")
    url5 = f"{SANDBOX_BASE}/v1/users?limit=1"
    sent_h5 = dict(base_req_headers)
    sent_h5["X-Api-Version"] = "2026-04-14"
    s5, b5, h5, e5 = _do(
        "GET", url5,
        token=token,
        extra_headers={"X-Api-Version": "2026-04-14"},
    )
    p5 = _save(
        4, "sandbox-users-after-pin",
        method="GET", url=url5,
        request_headers=sent_h5, request_body=None,
        status=s5, response_headers=h5, response_body=b5, elapsed_ms=e5,
    )
    print(f"  Probe 5: HTTP {s5} -> {p5.name}")

    # -- Probe 6: simulate-deposit endpoint existence — try both bases.
    print("Probe 6a: POST /v1/virtual-accounts/<fake>/simulate-deposit (no-prefix) ...")
    url6a = f"{NO_PREFIX_BASE}/v1/virtual-accounts/{FAKE_VA_UUID}/simulate-deposit"
    s6a, b6a, h6a, e6a = _do(
        "POST", url6a, token=token,
        body={"amount": 1000, "currency": "USD"},
    )
    p6a = _save(
        5, "simulate-deposit-no-prefix",
        method="POST", url=url6a,
        request_headers=base_req_headers,
        request_body={"amount": 1000, "currency": "USD"},
        status=s6a, response_headers=h6a, response_body=b6a, elapsed_ms=e6a,
    )
    print(f"  Probe 6a: HTTP {s6a} -> {p6a.name}")

    print("Probe 6b: POST /sandbox/v1/virtual-accounts/<fake>/simulate-deposit ...")
    url6b = f"{SANDBOX_BASE}/v1/virtual-accounts/{FAKE_VA_UUID}/simulate-deposit"
    s6b, b6b, h6b, e6b = _do(
        "POST", url6b, token=token,
        body={"amount": 1000, "currency": "USD"},
    )
    p6b = _save(
        6, "simulate-deposit-sandbox-prefix",
        method="POST", url=url6b,
        request_headers=base_req_headers,
        request_body={"amount": 1000, "currency": "USD"},
        status=s6b, response_headers=h6b, response_body=b6b, elapsed_ms=e6b,
    )
    print(f"  Probe 6b: HTTP {s6b} -> {p6b.name}")

    # -- Tiny summary line for the runner's stdout.
    summary = {
        "probe2_pin_no_prefix": s2,
        "probe3_pin_sandbox_prefix": s3,
        "probe4_sandbox_auth_after_pin": s4,
        "probe5_sandbox_users_after_pin": s5,
        "probe6a_simulate_deposit_no_prefix": s6a,
        "probe6b_simulate_deposit_sandbox": s6b,
        "pin_succeeded": pin_succeeded,
        "pinned_base": pinned_base,
    }
    print("\nSUMMARY:")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
