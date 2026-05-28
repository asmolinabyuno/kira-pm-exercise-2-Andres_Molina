"""Probe 2-extension — Confirm `status` and `verification_mode` enum-validated
inputs are real mass-assignment surface."""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth, fake_business_payload  # noqa: E402


def post_user(token: str, body: Dict[str, Any], label: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/v1/users"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    t0 = time.perf_counter_ns()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        rb = resp.json()
    except Exception:
        rb = resp.text[:500]
    return {
        "label": label,
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "request_body_overlay_keys": [k for k in body if k in ("status", "verification_mode")],
        "request_body_overlay_values": {k: body[k] for k in body if k in ("status", "verification_mode")},
        "response_body_status_field": rb.get("status") if isinstance(rb, dict) else None,
        "response_body_verification_mode": rb.get("verification_mode") if isinstance(rb, dict) else None,
        "response_body_verification_status": rb.get("verification_status") if isinstance(rb, dict) else None,
        "response_body": redact_body(rb) if isinstance(rb, dict) else rb,
    }


def main() -> None:
    token = auth()
    if not token:
        sys.exit(1)

    overlays = [
        ("E1-status-active-lowercase", {"status": "active"}),
        ("E2-status-suspended", {"status": "suspended"}),
        ("E3-status-inactive", {"status": "inactive"}),
        ("E4-verification_mode-verification_link", {"verification_mode": "verification_link"}),
        ("E5-both", {"status": "suspended", "verification_mode": "verification_link"}),
    ]
    results: List[Dict[str, Any]] = []
    for label, overlay in overlays:
        body = fake_business_payload()
        body["email"] = f"sec+enum-{label.lower()}-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
        body.update(overlay)
        r = post_user(token, body, label)
        results.append(r)
        print(f"  {label}: status={r['status']} response.status={r['response_body_status_field']} "
              f"response.verification_mode={r['response_body_verification_mode']} "
              f"response.verification_status={r['response_body_verification_status']}")

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    out = HERE / "02-enum-input-results.json"
    out.write_text(json.dumps(summary, indent=2))
    print("Probe 2-ext output:", out)


if __name__ == "__main__":
    main()
