"""Scenario 6 — verification-skip-attempt.

DRIFT-23 (DRIFT-B10): sandbox does NOT auto-approve verification — users stuck
in REVIEW. Can users in non-VERIFIED states still create downstream resources
(VAs, payouts)?

Three states to probe:
  - CREATED (no verification triggered): USER_CREATED = 65ba0e06...
  - REVIEW (individual): USER_REVIEW_INDIV = 02e4e953...
  - REVIEW (business): USER_REVIEW_BIZ = 0ba8a87a...

Probes:
  P1. POST /v1/virtual-accounts for each of the 3 users.
      Expected: 400 (or 403) "user not verified" envelope.
      Watch for: bypass (201), inconsistent error envelopes, info-disclosure.
  P2. POST /v1/payouts for each of the 3 users (with a fake recipient_id).
      We expect 400 either at schema layer (network/quote_id/txHash) or at
      ownership/recipient-existence layer.
  P3. POST /v1/quotations for each — same drill.

Compare error envelopes — are they consistent across states, across endpoints?
DRIFT-12 already showed two envelope shapes coexist; here we look at the
DEPENDENCY-CHECK error specifically.

Run: python3 evidence/work/abuse/verification-skip-attempt/run.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _abuse_common import (  # noqa: E402
    BASE_URL,
    USER_CREATED,
    USER_REVIEW_BIZ,
    USER_REVIEW_INDIV,
    base_headers,
    call,
    write_summary,
)

SLUG = "verification-skip-attempt"

USER_STATES = [
    ("CREATED", USER_CREATED),
    ("REVIEW-individual", USER_REVIEW_INDIV),
    ("REVIEW-business", USER_REVIEW_BIZ),
]


def make_idem_headers():
    h = base_headers()
    h["idempotency-key"] = str(uuid.uuid4())
    return h


def _err_envelope_kind(body) -> str:
    """Classify error envelope by top-level shape."""
    if not isinstance(body, dict):
        return "non-dict"
    keys = set(body.keys())
    if "error" in keys and isinstance(body.get("error"), str):
        return "shape-A-flat"  # {error:str, details:[...]}
    if "error" in keys and isinstance(body.get("error"), dict):
        return "shape-B-nested"  # {error: {code, message, details}}
    if "code" in keys and "error" in keys:
        return "shape-C-code+error"  # {code, error, details}
    if "message" in keys and "code" not in keys:
        return "shape-D-message-only"
    return f"unknown-{sorted(list(keys))[:5]}"


def main() -> None:
    findings = []

    for state_label, user_id in USER_STATES:
        # ---- P1: POST /v1/virtual-accounts -------------------------------
        va_body = {
            "user_id": user_id,
            "product": "usa-virtual-accounts",
            "type": "individual",  # discriminator hinted by Batch B mass-asssgn probe
        }
        s, body, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/virtual-accounts",
            headers=make_idem_headers(),
            body=va_body,
            scenario_slug=SLUG,
            outcome_hint=f"P1-va-create-{state_label}",
            filename=f"01-P1-va-create-{state_label}",
        )
        findings.append({
            "probe": "P1-va-create",
            "user_state": state_label,
            "status": s,
            "envelope": _err_envelope_kind(body),
            "body_excerpt": _excerpt(body),
        })

        # ---- P2: POST /v1/payouts ----------------------------------------
        # Use a fake recipient_id; we don't expect this to ever succeed.
        payout_body = {
            "user_id": user_id,
            "recipient_id": str(uuid.uuid4()),
            "amount": 1.00,
            "currency": "USD",
        }
        s, body, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/payouts",
            headers=make_idem_headers(),
            body=payout_body,
            scenario_slug=SLUG,
            outcome_hint=f"P2-payout-{state_label}",
            filename=f"02-P2-payout-{state_label}",
        )
        findings.append({
            "probe": "P2-payout",
            "user_state": state_label,
            "status": s,
            "envelope": _err_envelope_kind(body),
            "body_excerpt": _excerpt(body),
        })

        # ---- P3: POST /v1/quotations -------------------------------------
        # Per Batch E findings, Reference shape body for quotations:
        quote_body = {
            "user_id": user_id,
            "source_currency": "USD",
            "destination_currency": "MXN",
            "amount": 100.00,
            "amount_type": "source",
        }
        s, body, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/quotations",
            headers=make_idem_headers(),
            body=quote_body,
            scenario_slug=SLUG,
            outcome_hint=f"P3-quote-{state_label}",
            filename=f"03-P3-quote-{state_label}",
        )
        findings.append({
            "probe": "P3-quotation",
            "user_state": state_label,
            "status": s,
            "envelope": _err_envelope_kind(body),
            "body_excerpt": _excerpt(body),
        })

    # Summary
    by_probe = {}
    for f in findings:
        by_probe.setdefault(f["probe"], []).append(
            {"state": f["user_state"], "status": f["status"], "envelope": f["envelope"]})

    summary = {
        "scenario": SLUG,
        "findings": findings,
        "per_probe_status_matrix": by_probe,
        "any_bypass": any(200 <= f["status"] < 300 for f in findings),
    }
    write_summary(SLUG, summary)
    print(f"[{SLUG}] any_bypass={summary['any_bypass']}")
    for probe, rows in by_probe.items():
        print(f"  {probe}: " + ", ".join(f"{r['state']}->{r['status']}/{r['envelope']}" for r in rows))


def _excerpt(body, max_len: int = 250) -> Optional[str]:
    if body is None:
        return None
    import json as _json
    try:
        s = _json.dumps(body, ensure_ascii=False)
    except Exception:
        s = str(body)
    return s[:max_len]


if __name__ == "__main__":
    main()
