"""Scenario 2 — idempotency-replay-race.

DRIFT-G4 already confirmed `/webhooks/register` ignores Idempotency-Key. Cross-
check on `POST /v1/recipients` (where DRIFT-C10 / C11 / C12 partially probed it
serially). The race-condition angle:

Probe A: N=10 PARALLEL identical POST /v1/recipients (same key, same body).
        Expect: all 10 return the SAME recipient_id (Stripe-pattern idempotency).
Probe B: N=10 PARALLEL identical POST with DIFFERENT keys + same body.
        Expect: 10 distinct recipient_ids — body is not the discriminator.
Probe C: N=10 PARALLEL same key + mutated body per worker.
        Expect: one wins (201), others get 409 idempotency_conflict OR all 409.
Probe D: 2-parallel race at wall-clock T0 with same key + same body to look for
        races where the second sees a stale or partial response.

Run: python3 evidence/work/abuse/idempotency-replay-race/run.py
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
    parallel_call,
    random_clabe,
    spei_payload,
    write_summary,
)

SLUG = "idempotency-replay-race"

# Cap concurrency low — abuse tooling, sandbox only.
N_PARALLEL = 10


def main() -> None:
    # =========================================================================
    # Probe A — N parallel identical (same key + same body)
    # =========================================================================
    shared_key_A = str(uuid.uuid4())
    body_A = spei_payload(user_id=USER_CREATED, clabe=random_clabe(900),
                          last_name="ReplayA")

    def headers_A(_idx: int):
        h = base_headers()
        h["idempotency-key"] = shared_key_A
        return h

    def body_A_factory(_idx: int):
        return body_A

    res_A = parallel_call(
        method="POST",
        url=f"{BASE_URL}/v1/recipients",
        body_factory=body_A_factory,
        headers_factory=headers_A,
        n=N_PARALLEL,
        scenario_slug=SLUG,
        filename_prefix="A-same-key-same-body",
        outcome_hint="replay-A",
    )

    # =========================================================================
    # Probe B — N parallel DIFFERENT keys + same body → expect N distinct creates
    # =========================================================================
    body_B = spei_payload(user_id=USER_CREATED, clabe=random_clabe(901),
                          last_name="ReplayB")

    def headers_B(_idx: int):
        h = base_headers()
        h["idempotency-key"] = str(uuid.uuid4())
        return h

    def body_B_factory(_idx: int):
        return body_B

    res_B = parallel_call(
        method="POST",
        url=f"{BASE_URL}/v1/recipients",
        body_factory=body_B_factory,
        headers_factory=headers_B,
        n=N_PARALLEL,
        scenario_slug=SLUG,
        filename_prefix="B-diff-keys-same-body",
        outcome_hint="diff-keys",
    )

    # =========================================================================
    # Probe C — N parallel same key + mutated body (per worker) → expect 1 win + 9 conflicts
    # =========================================================================
    shared_key_C = str(uuid.uuid4())

    # Each worker mutates `last_name` (must remain valid-letter chars).
    # last_name "MutA", "MutB", ...
    def headers_C(_idx: int):
        h = base_headers()
        h["idempotency-key"] = shared_key_C
        return h

    suffixes = "ABCDEFGHIJ"

    def body_C_factory(idx: int):
        return spei_payload(user_id=USER_CREATED, clabe=random_clabe(902),
                            last_name=f"Mut{suffixes[idx]}")

    res_C = parallel_call(
        method="POST",
        url=f"{BASE_URL}/v1/recipients",
        body_factory=body_C_factory,
        headers_factory=headers_C,
        n=N_PARALLEL,
        scenario_slug=SLUG,
        filename_prefix="C-same-key-mut-body",
        outcome_hint="race-mut",
    )

    # =========================================================================
    # Probe D — 2 parallel same key + same body (tight race)
    # =========================================================================
    shared_key_D = str(uuid.uuid4())
    body_D = spei_payload(user_id=USER_CREATED, clabe=random_clabe(903),
                          last_name="RaceD")

    def headers_D(_idx: int):
        h = base_headers()
        h["idempotency-key"] = shared_key_D
        return h

    def body_D_factory(_idx: int):
        return body_D

    res_D = parallel_call(
        method="POST",
        url=f"{BASE_URL}/v1/recipients",
        body_factory=body_D_factory,
        headers_factory=headers_D,
        n=2,
        scenario_slug=SLUG,
        filename_prefix="D-pair-race",
        outcome_hint="pair-race",
    )

    # ---- Summary ---------------------------------------------------------
    def _ids(results):
        out = []
        for status, body, _p, _e, idx in results:
            rid = None
            if isinstance(body, dict):
                rid = body.get("recipient_id") or body.get("id")
            out.append({"worker": idx, "status": status, "recipient_id": rid})
        return out

    def _status_counts(results):
        from collections import Counter
        return dict(Counter([r[0] for r in results]))

    summary = {
        "scenario": SLUG,
        "n_parallel": N_PARALLEL,
        "probe_A_same_key_same_body": {
            "status_counts": _status_counts(res_A),
            "ids": _ids(res_A),
            "unique_ids": len({r["recipient_id"] for r in _ids(res_A) if r["recipient_id"]}),
        },
        "probe_B_diff_keys_same_body": {
            "status_counts": _status_counts(res_B),
            "ids": _ids(res_B),
            "unique_ids": len({r["recipient_id"] for r in _ids(res_B) if r["recipient_id"]}),
        },
        "probe_C_same_key_mut_body": {
            "status_counts": _status_counts(res_C),
            "ids": _ids(res_C),
        },
        "probe_D_pair_race": {
            "status_counts": _status_counts(res_D),
            "ids": _ids(res_D),
        },
    }
    write_summary(SLUG, summary)
    print(f"[{SLUG}] A unique_ids={summary['probe_A_same_key_same_body']['unique_ids']} "
          f"B unique_ids={summary['probe_B_diff_keys_same_body']['unique_ids']} "
          f"C status_counts={summary['probe_C_same_key_mut_body']['status_counts']} "
          f"D status_counts={summary['probe_D_pair_race']['status_counts']}")


if __name__ == "__main__":
    main()
