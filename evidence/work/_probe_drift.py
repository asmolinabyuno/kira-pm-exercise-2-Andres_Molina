"""DRIFT-1 follow-up probe for POST /v1/users.

Probes both candidate bases:
  A) https://api.balampay.com/v1/users          (no /sandbox prefix)
  B) https://api.balampay.com/sandbox/v1/users  (with /sandbox prefix)

Sends a minimal-but-likely-invalid body ({}) with a fresh bearer token.
Whichever URL returns a *validation* error (structured 4xx) is the working base.
A 403 ForbiddenException at the AWS API Gateway layer means the URL itself is wrong.

Captures both probes to evidence/work/users/00-drift-probe-{A,B}.json via _redact.
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import httpx  # noqa: E402

from run_flow import auth, capture, API_KEY  # noqa: E402


def probe(label: str, full_url: str, token: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    body: dict = {}

    attempt_id = str(uuid.uuid4())
    t0 = time.perf_counter_ns()
    try:
        resp = httpx.post(full_url, headers=headers, json=body, timeout=30.0)
    except Exception as e:
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        print(f"[{label}] {full_url} → EXCEPTION {type(e).__name__}: {e}")
        return
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body = resp.json()
    except Exception:
        resp_body = resp.text

    outcome = (
        f"drift-probe-{label}-validation" if 400 <= resp.status_code < 500 and resp.status_code != 403
        else f"drift-probe-{label}-forbidden" if resp.status_code == 403
        else f"drift-probe-{label}-{resp.status_code}"
    )

    path = capture(
        "users",
        attempt_id,
        request={"method": "POST", "url": full_url, "headers": headers, "body": body},
        response={
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=f"00-drift-probe-{label}",
    )
    # Print a one-line summary (status, content-type, headline error) — no secrets.
    err_type = resp.headers.get("x-amzn-errortype", "-")
    snippet = ""
    if isinstance(resp_body, dict):
        snippet = str({k: resp_body[k] for k in list(resp_body)[:3]})[:240]
    elif isinstance(resp_body, str):
        snippet = resp_body[:240]
    print(f"[{label}] {full_url}")
    print(f"    status={resp.status_code} elapsed_ms={elapsed_ms:.1f} x-amzn-errortype={err_type}")
    print(f"    body_snippet={snippet}")
    print(f"    saved={path.relative_to(HERE.parent.parent)}")


def main() -> None:
    token = auth()
    if not token:
        print("AUTH failed — cannot probe /v1/users")
        sys.exit(1)
    print("AUTH OK")

    probe("A", "https://api.balampay.com/v1/users", token)
    probe("B", "https://api.balampay.com/sandbox/v1/users", token)


if __name__ == "__main__":
    main()
