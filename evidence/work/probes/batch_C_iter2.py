"""Batch C — iteration 2. Re-runs only the variants that failed in iter1 with
schemas corrected for the empirical drifts learned from iter1:

  DRIFT-C2  country fields are ALPHA-2 (docs say alpha-3)
  DRIFT-C3  ACH doc_type enum is {id, dni, passport, ein} (docs say ssn)
  DRIFT-C4  WALLET address validation is real base58check (use format-valid test addr)
  DRIFT-C5  SWIFT also requires recipient-level `address` object (docs only listed for ACH)

Also re-tests:
  - DETAIL on the actually-newly-created (ACH or SWIFT) recipient — to capture
    `account_details` masking behavior across variants beyond SPEI.

This re-uses ach/usdt/swift builders from batch_C.py (now corrected).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from batch_C import (  # noqa: E402
    ach_usd_payload,
    auth,
    get_recipient_detail,
    post_recipient,
    swift_eur_payload,
    usdt_tron_payload,
)


def run() -> None:
    print("=== Batch C — Iter2 (corrected schemas) ===")
    token = auth()
    if not token:
        print("AUTH FAILED — aborting")
        sys.exit(1)
    print("AUTH OK")

    for variant_name, builder in (
        ("ach-iter2",   ach_usd_payload),
        ("usdt-iter2",  usdt_tron_payload),
        ("swift-iter2", swift_eur_payload),
    ):
        idem = str(uuid.uuid4())
        body = builder()
        status, resp, path, ms = post_recipient(
            token, body,
            idem_key=idem,
            outcome_hint=variant_name,
        )
        print(f"  {variant_name:>11}  HTTP {status}  {ms:6.1f}ms  -> {path.name}")
        if 200 <= status < 300 and isinstance(resp, dict):
            rec_id = (
                resp.get("recipient_id")
                or resp.get("id")
                or (resp.get("data") or {}).get("id")
                or (resp.get("data") or {}).get("recipient_id")
            )
            if rec_id:
                s2, _, p2, ms2 = get_recipient_detail(
                    token,
                    recipient_id=rec_id,
                    outcome_hint=f"detail-{variant_name}",
                )
                print(f"    DETAIL HTTP {s2}  {ms2:6.1f}ms  -> {p2.name}")


if __name__ == "__main__":
    run()
