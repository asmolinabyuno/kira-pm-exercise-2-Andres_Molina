"""Scenario 3 — bola-cross-tenant-stub.

Without a second tenant we can't truly test BOLA, but we probe whether the API
leaks any unexpected 200s on resources we DIDN'T create. The hunt is for:
  - Sequential ID guessability (mutate one nibble of our own user ID)
  - Random UUID-v4 GETs that come back 200 (not 404)
  - Cross-resource references that BYPASS ownership checks (e.g., POST /v1/payouts
    referencing a recipient_id we don't own — does the API enforce ownership?)
  - POST /v1/virtual-accounts referencing a user_id we don't own — same check?

Run: python3 evidence/work/abuse/bola-cross-tenant-stub/run.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _abuse_common import (  # noqa: E402
    BASE_URL,
    USER_CREATED,
    base_headers,
    call,
    write_summary,
)

SLUG = "bola-cross-tenant-stub"

# Our own resources to use as anchors.
OUR_USER = USER_CREATED


def _mutate_uuid(u: str, position: int = -1) -> str:
    """Return UUID with one hex char flipped at the given position (mod 32)."""
    raw = u.replace("-", "")
    pos = position % len(raw)
    cur = raw[pos]
    new = "0" if cur != "0" else "1"
    new_raw = raw[:pos] + new + raw[pos + 1:]
    return f"{new_raw[0:8]}-{new_raw[8:12]}-{new_raw[12:16]}-{new_raw[16:20]}-{new_raw[20:32]}"


def main() -> None:
    results = []

    # ---- Probe 1: enumerate users by mutating one byte of our user_id -----
    for pos in (-1, -2, -3, -7, 0, 4, 8):
        mutated = _mutate_uuid(OUR_USER, position=pos)
        s, body, _, _ = call(
            method="GET",
            url=f"{BASE_URL}/v1/users/{mutated}",
            headers=base_headers(),
            body=None,
            scenario_slug=SLUG,
            outcome_hint=f"mutated-user-pos{pos}",
            filename=f"01-mutated-user-pos{pos:+d}",
        )
        results.append({"probe": "mutate-user", "pos": pos, "target": mutated, "status": s,
                        "response_kind": "data" if (isinstance(body, dict) and "id" in body) else
                                         ("error" if isinstance(body, dict) else "text")})

    # ---- Probe 2: random UUID-v4 GET on /v1/recipients/{id} ---------------
    for i in range(5):
        rand_id = str(uuid.uuid4())
        s, body, _, _ = call(
            method="GET",
            url=f"{BASE_URL}/v1/recipients/{rand_id}",
            headers=base_headers(),
            body=None,
            scenario_slug=SLUG,
            outcome_hint=f"random-recipient-{i}",
            filename=f"02-random-recipient-{i:02d}",
        )
        results.append({"probe": "random-recipient", "target": rand_id, "status": s,
                        "body_kind": type(body).__name__})

    # ---- Probe 3: random UUID-v4 GET on /v1/users/{id} ---------------
    for i in range(5):
        rand_id = str(uuid.uuid4())
        s, body, _, _ = call(
            method="GET",
            url=f"{BASE_URL}/v1/users/{rand_id}",
            headers=base_headers(),
            body=None,
            scenario_slug=SLUG,
            outcome_hint=f"random-user-{i}",
            filename=f"03-random-user-{i:02d}",
        )
        results.append({"probe": "random-user", "target": rand_id, "status": s,
                        "body_kind": type(body).__name__})

    # ---- Probe 4: random UUID-v4 GET on /v1/virtual-accounts/{id} ---------------
    for i in range(3):
        rand_id = str(uuid.uuid4())
        s, body, _, _ = call(
            method="GET",
            url=f"{BASE_URL}/v1/virtual-accounts/{rand_id}",
            headers=base_headers(),
            body=None,
            scenario_slug=SLUG,
            outcome_hint=f"random-va-{i}",
            filename=f"04-random-va-{i:02d}",
        )
        results.append({"probe": "random-va", "target": rand_id, "status": s})

    # ---- Probe 5: POST /v1/payouts referencing a random recipient_id ------
    # We don't know the payout body shape (Batch F blocked by DRIFT-23), so the
    # call will likely 400. But the SHAPE of the error tells us a lot:
    #   - 400 "recipient not found" → ownership/existence check at the right layer
    #   - 400 "field X required" → schema layer rejects before ownership check
    #   - 403 → method/IAM problem
    fake_recipient = str(uuid.uuid4())
    payout_body_minimal = {
        "user_id": OUR_USER,
        "recipient_id": fake_recipient,
        "amount": 1.00,
        "currency": "USD",
    }
    s, body, _, _ = call(
        method="POST",
        url=f"{BASE_URL}/v1/payouts",
        headers={**base_headers(), "idempotency-key": str(uuid.uuid4())},
        body=payout_body_minimal,
        scenario_slug=SLUG,
        outcome_hint="payout-fake-recipient",
        filename="05-payout-fake-recipient",
    )
    results.append({"probe": "payout-fake-recipient", "target": fake_recipient, "status": s,
                    "body_kind": type(body).__name__})

    # ---- Probe 6: POST /v1/virtual-accounts referencing random user_id ----
    fake_user = str(uuid.uuid4())
    va_body_minimal = {
        "user_id": fake_user,
        "product": "usa-virtual-accounts",
    }
    s, body, _, _ = call(
        method="POST",
        url=f"{BASE_URL}/v1/virtual-accounts",
        headers={**base_headers(), "idempotency-key": str(uuid.uuid4())},
        body=va_body_minimal,
        scenario_slug=SLUG,
        outcome_hint="va-fake-user",
        filename="06-va-fake-user",
    )
    results.append({"probe": "va-fake-user", "target": fake_user, "status": s,
                    "body_kind": type(body).__name__})

    # ---- Probe 7: GET unknown listed resources (sanity) -------------------
    # Confirm "we own our own user" sanity check
    s, body, _, _ = call(
        method="GET",
        url=f"{BASE_URL}/v1/users/{OUR_USER}",
        headers=base_headers(),
        body=None,
        scenario_slug=SLUG,
        outcome_hint="sanity-own-user",
        filename="07-sanity-own-user",
    )
    results.append({"probe": "sanity-own-user", "target": OUR_USER, "status": s})

    summary = {
        "scenario": SLUG,
        "results": results,
        "leak_count": sum(1 for r in results
                          if r["status"] == 200 and r["probe"] != "sanity-own-user"),
    }
    write_summary(SLUG, summary)
    from collections import Counter
    by_probe = {}
    for r in results:
        by_probe.setdefault(r["probe"], Counter())[r["status"]] += 1
    print(f"[{SLUG}] leak_count={summary['leak_count']} "
          f"per-probe-status-counts={ {k: dict(v) for k,v in by_probe.items()} }")


if __name__ == "__main__":
    main()
