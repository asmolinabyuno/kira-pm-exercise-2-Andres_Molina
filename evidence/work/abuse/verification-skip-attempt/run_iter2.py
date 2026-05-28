"""Scenario 6 iter2 — push past the schema layer for the VA + payout endpoints
so we can actually probe whether the verification check fires.

VA: type enum is `US_BANK | MX_SPEI`. Build a US_BANK request for each user.
Payout: needs `network`, `txHash`, `quote_id`. quote_id comes from /v1/quotations.
We can't get a quote_id without a recipient_id; for a stub, send a fake one.

Goal: get past schema → land on whichever layer enforces verification state.
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


def main() -> None:
    findings = []
    for state_label, user_id in USER_STATES:
        # ---- iter2 P1: VA with type=US_BANK ----
        va_body = {
            "user_id": user_id,
            "product": "usa-virtual-accounts",
            "type": "US_BANK",
        }
        s, body, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/virtual-accounts",
            headers=make_idem_headers(),
            body=va_body,
            scenario_slug=SLUG,
            outcome_hint=f"iter2-P1-va-US_BANK-{state_label}",
            filename=f"11-iter2-P1-va-US_BANK-{state_label}",
        )
        findings.append({"probe": "iter2-P1-va-US_BANK", "user_state": state_label,
                         "status": s, "body": _excerpt(body)})

        # ---- iter2 P1b: VA with type=MX_SPEI ----
        va_body2 = {
            "user_id": user_id,
            "product": "mexico-virtual-accounts",
            "type": "MX_SPEI",
        }
        s, body, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/virtual-accounts",
            headers=make_idem_headers(),
            body=va_body2,
            scenario_slug=SLUG,
            outcome_hint=f"iter2-P1b-va-MX_SPEI-{state_label}",
            filename=f"12-iter2-P1b-va-MX_SPEI-{state_label}",
        )
        findings.append({"probe": "iter2-P1b-va-MX_SPEI", "user_state": state_label,
                         "status": s, "body": _excerpt(body)})

    summary = {
        "scenario": SLUG,
        "iter2_findings": findings,
        "any_bypass": any(200 <= f["status"] < 300 for f in findings),
    }
    # Merge with existing summary
    import json
    out = HERE / "_summary.json"
    existing = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text())
        except Exception:
            existing = {}
    existing.update(summary)
    out.write_text(json.dumps(existing, indent=2, ensure_ascii=False, default=str))
    print(f"[{SLUG} iter2] any_bypass={summary['any_bypass']}")
    for f in findings:
        print(f"  {f['probe']} / {f['user_state']} -> {f['status']}")
        print(f"     {f['body']}")


def _excerpt(body, max_len: int = 350):
    if body is None:
        return None
    import json
    try:
        return json.dumps(body, ensure_ascii=False)[:max_len]
    except Exception:
        return str(body)[:max_len]


if __name__ == "__main__":
    main()
