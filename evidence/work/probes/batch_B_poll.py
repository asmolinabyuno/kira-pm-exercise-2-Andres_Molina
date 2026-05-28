"""Batch B follow-up: poll users for verification state transitions.

After ``batch_B.py`` we identified two users that triggered verification:
  - 02e4e953-f423-4a7a-8828-f9c2a2ecb1c7  (individual, zero-missing)
  - 0ba8a87a-a49e-423b-86fb-c6a025ba27f9  (business, zero-missing on ACT)

This script polls ``GET /v1/users/{id}`` every 10 seconds for up to 2 minutes
and captures every snapshot under ``evidence/work/verification/poll-{NN}-*.json``.

We're looking for:
  - ``status`` transition: CREATED → VERIFYING → VERIFIED|REJECTED|REVIEW
  - ``verification_status`` transition: unverified → started → verified|rejected|needs_action
  - ``eligible_products[*].eligible`` flipping to true

This validates the sandbox auto-approve claim from flow-design.md § 4.1 / § 5.2.
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

import httpx  # noqa: E402

from run_flow import API_KEY, BASE_URL, auth, capture  # noqa: E402


USERS_TO_POLL = [
    ("individual", "02e4e953-f423-4a7a-8828-f9c2a2ecb1c7"),
    ("business", "0ba8a87a-a49e-423b-86fb-c6a025ba27f9"),
    # Also re-poll the DRIFT-3 user that had POST /verifications fired against it
    ("drift3", "ae80515c-2d59-4e02-9678-0bcfd6e9a188"),
]
POLL_INTERVAL_S = 10
MAX_POLLS = 12  # 2 minutes total


def get_user(token: str, user_id: str, label: str, n: int) -> Tuple[int, Optional[Dict[str, Any]], Path]:
    url = f"{BASE_URL}/v1/users/{user_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    attempt_id = str(uuid.uuid4())
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    outcome = "success" if 200 <= resp.status_code < 300 else f"fail-{resp.status_code}"
    path = capture(
        "verification",
        attempt_id,
        request={"method": "GET", "url": url, "headers": headers, "body": None},
        response={
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=f"poll-{label}-{n:02d}-{outcome}",
    )
    return resp.status_code, body if isinstance(body, dict) else None, path


def summarize(body: Optional[Dict[str, Any]]) -> str:
    if not body:
        return "<no body>"
    st = body.get("status")
    vs = body.get("verification_status")
    vt = body.get("verification_triggered")
    mf = body.get("missing_fields") or {}
    mf_count = sum(len(v) for v in mf.values() if isinstance(v, list))
    eligible = [p.get("product_code") for p in (body.get("eligible_products") or []) if p.get("eligible")]
    return (
        f"status={st!r} verification_status={vs!r} "
        f"verification_triggered={vt!r} missing={mf_count} "
        f"eligible_products={eligible or '[]'}"
    )


def main() -> int:
    print("Batch B poll — verification state transitions")
    token = auth()
    if not token:
        print("AUTH FAILED", file=sys.stderr)
        return 1
    print("AUTH OK")

    transitions: Dict[str, list] = {label: [] for label, _ in USERS_TO_POLL}

    for n in range(1, MAX_POLLS + 1):
        print(f"\n--- poll #{n} ({n * POLL_INTERVAL_S}s wall) ---")
        for label, uid in USERS_TO_POLL:
            status, body, path = get_user(token, uid, label, n)
            sig = summarize(body)
            transitions[label].append(sig)
            print(f"  [{label} {uid[:8]}…] http={status} {sig}")
            print(f"    evidence={path.relative_to(WORK.parent)}")
        if n < MAX_POLLS:
            time.sleep(POLL_INTERVAL_S)

    print("\n========== TRANSITION SUMMARY ==========")
    for label, sigs in transitions.items():
        first, last = sigs[0], sigs[-1]
        moved = first != last
        print(f"{label}: moved={moved}")
        if moved:
            for i, s in enumerate(sigs):
                if i == 0 or s != sigs[i - 1]:
                    print(f"  poll #{i + 1}: {s}")
        else:
            print(f"  (no transition): {first}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
