"""Probe 3 — BOLA / IDOR enumeration (OWASP API1:2023).

Tests whether GET /v1/users/{id}, GET /v1/recipients/{id}, GET /v1/virtual-accounts/{id}
return cross-tenant data when called with a UUID we did NOT create.

For each endpoint we send a small mix:
  a) 5 random uuid4 — generic enumeration
  b) 1 sequential uuid (own_id with last byte +1) — neighbor enumeration
  c) 1 known-invalid UUID — control (should 404)
  d) 1 well-formed but never-issued UUID variant — confirms 404 vs 403 vs 200

Expected SAFE behavior: 404 (not found) or 403 (forbidden — preferable, doesn't
distinguish "missing" from "yours-vs-mine") for every attempt.

ANY 200 with a body that contains a `client_uuid` or `created_at` distinct from
our own is a CRITICAL cross-tenant leak finding.

We pre-load `OUR_USER_ID` and `OUR_RECIPIENT_ID` from existing evidence files to
avoid creating new records.

Run: python3 evidence/work/security/bola-id-enumeration/probe_bola.py
"""
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
from run_flow import API_KEY, BASE_URL, auth  # noqa: E402


def load_ids_from_evidence() -> Dict[str, str]:
    """Pull one user_id and one recipient_id from existing evidence."""
    out: Dict[str, str] = {}
    # User: users/03-success.json
    try:
        d = json.load(open(WORK / "users" / "03-success.json"))
        body = d.get("response", {}).get("body", {})
        if isinstance(body, dict) and body.get("id"):
            out["our_user_id"] = body["id"]
    except Exception:
        pass
    # Recipient: recipients/01-success-201-spei.json
    try:
        d = json.load(open(WORK / "recipients" / "01-success-201-spei.json"))
        body = d.get("response", {}).get("body", {})
        if isinstance(body, dict) and body.get("recipient_id"):
            out["our_recipient_id"] = body["recipient_id"]
    except Exception:
        pass
    return out


def sequential_uuid(base: str) -> str:
    """Bump the last byte of a uuid by 1 (wrap on overflow)."""
    u = uuid.UUID(base)
    hi = u.int & ~0xFF
    lo = ((u.int & 0xFF) + 1) % 0x100
    return str(uuid.UUID(int=hi | lo))


def attempt(label: str, token: str, url: str) -> Dict[str, Any]:
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, timeout=15.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        body = resp.json()
    except Exception:
        body = resp.text[:300]
    return {
        "label": label,
        "url": url,
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "response_headers": {k.lower(): v for k, v in resp.headers.items() if k.lower() in ("x-amzn-errortype", "content-type", "x-amzn-requestid")},
        "request_headers": redact_headers(headers),
        "body": redact_body(body) if isinstance(body, dict) else body,
        "looks_like_leak": (
            200 <= resp.status_code < 300
            and isinstance(body, dict)
        ),
    }


def main() -> None:
    token = auth()
    if not token:
        sys.exit(1)

    ids = load_ids_from_evidence()
    our_user_id = ids.get("our_user_id")
    our_recipient_id = ids.get("our_recipient_id")
    print("Our user_id:", our_user_id)
    print("Our recipient_id:", our_recipient_id)

    families = []

    # Family: /v1/users/{id}
    if our_user_id:
        targets = [
            ("users-control-own", our_user_id),
            ("users-random-1", str(uuid.uuid4())),
            ("users-random-2", str(uuid.uuid4())),
            ("users-random-3", str(uuid.uuid4())),
            ("users-sequential-+1", sequential_uuid(our_user_id)),
            ("users-zeros-uuid", "00000000-0000-4000-8000-000000000000"),
            ("users-malformed", "not-a-uuid"),
        ]
    else:
        targets = [("users-random-1", str(uuid.uuid4()))]
    family_results: List[Dict[str, Any]] = []
    for label, uid in targets:
        family_results.append(attempt(label, token, f"{BASE_URL}/v1/users/{uid}"))
    families.append({"family": "/v1/users/{id}", "attempts": family_results})

    # Family: /v1/recipients/{id}
    if our_recipient_id:
        targets = [
            ("recipients-control-own", our_recipient_id),
            ("recipients-random-1", str(uuid.uuid4())),
            ("recipients-random-2", str(uuid.uuid4())),
            ("recipients-random-3", str(uuid.uuid4())),
            ("recipients-sequential-+1", sequential_uuid(our_recipient_id)),
            ("recipients-zeros-uuid", "00000000-0000-4000-8000-000000000000"),
        ]
    else:
        targets = [("recipients-random-1", str(uuid.uuid4()))]
    family_results = []
    for label, rid in targets:
        family_results.append(attempt(label, token, f"{BASE_URL}/v1/recipients/{rid}"))
    families.append({"family": "/v1/recipients/{id}", "attempts": family_results})

    # Family: /v1/virtual-accounts/{id} — we don't own one, so all attempts are
    # pure enumeration. Status codes from these tell us whether the endpoint
    # exists and how it errors on unknown IDs.
    family_results = []
    for label, vid in [
        ("va-random-1", str(uuid.uuid4())),
        ("va-random-2", str(uuid.uuid4())),
        ("va-zeros-uuid", "00000000-0000-4000-8000-000000000000"),
    ]:
        family_results.append(attempt(label, token, f"{BASE_URL}/v1/virtual-accounts/{vid}"))
    families.append({"family": "/v1/virtual-accounts/{id}", "attempts": family_results})

    # Summarize: any 200 outside control rows?
    leaks: List[Dict[str, Any]] = []
    for f in families:
        for a in f["attempts"]:
            if a.get("looks_like_leak") and not a.get("label", "").endswith("-control-own"):
                leaks.append({"family": f["family"], "label": a["label"], "status": a["status"]})

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "our_user_id_known": bool(our_user_id),
        "our_recipient_id_known": bool(our_recipient_id),
        "families": families,
        "leaks_found": leaks,
        "verdict": "LEAK" if leaks else "no-leak (404/403 as expected)",
    }
    out = HERE / "01-bola-results.json"
    out.write_text(json.dumps(summary, indent=2))
    print("Probe 3 output:", out)
    print("Verdict:", summary["verdict"])
    for f in families:
        for a in f["attempts"]:
            print(f"  [{f['family']}] {a.get('label')}: status={a.get('status')}")


if __name__ == "__main__":
    main()
