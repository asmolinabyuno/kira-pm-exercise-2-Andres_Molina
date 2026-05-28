"""Batch E followup #2 — try to break past "Total fees exceed payout amount".

Hypotheses tested:
- A: amount is in cents (try "100" = $1, "1000000" = $10000)
- B: account_type ACH/WIRE requires recipient_id OR additional context (currency).
- C: Maybe the Reference's `inverse_calculation: true` flips fee handling
- D: Try `base_currency`/`quote_currency` ADDED to the Reference shape (hybrid that's a real combination)
- E: Try `payment_instructions` / `client_markup` fields from the Reference schema
- F: Try `recipient_id: null` explicit and very large amount
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body  # noqa: E402
import run_flow  # noqa: E402

BASE_URL = run_flow.BASE_URL
API_KEY = run_flow.API_KEY
QUOTE_URL = f"{BASE_URL}/v1/quotations"
STEP = "quotations"


def _send(body, token, *, label, method="POST", url=None):
    attempt_id = str(uuid.uuid4())
    target = url or QUOTE_URL
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    t0 = time.perf_counter_ns()
    if method == "POST":
        resp = httpx.post(target, headers=headers, json=body, timeout=30.0)
    else:
        resp = httpx.get(target, headers=headers, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        resp_body = resp.json()
    except Exception:
        resp_body = resp.text
    outcome = (
        f"{label}-success" if 200 <= resp.status_code < 300
        else f"{label}-fail-{resp.status_code}"
    )
    path = run_flow.capture(
        STEP, attempt_id,
        request={"method": method, "url": target, "headers": headers, "body": body},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms, outcome=outcome,
    )
    return resp.status_code, resp_body, elapsed_ms, path


def main():
    print("=" * 72)
    print("Batch E followup #2 — push past fee gate")
    print("=" * 72)
    token = run_flow.auth()
    if not token:
        return 1

    trials = [
        # Hypothesis A: amount is in cents (try 100 → $1; 1000000 → $10k)
        ("ACH-amt-100", {"amount": "100", "account_type": "ACH"}),
        ("ACH-amt-1000000", {"amount": "1000000", "account_type": "ACH"}),
        ("ACH-amt-100M", {"amount": "100000000", "account_type": "ACH"}),
        # Hypothesis C: inverse_calculation
        ("ACH-inverse-big", {"amount": "1000000", "account_type": "ACH", "inverse_calculation": True}),
        ("ACH-inverse-small", {"amount": "100", "account_type": "ACH", "inverse_calculation": True}),
        # Hybrid: Reference + base/quote currency
        ("hybrid-ACH-USD-MXN", {
            "amount": "1000000", "account_type": "ACH",
            "base_currency": "USD", "quote_currency": "MXN",
        }),
        # client_markup / payment_instructions
        ("ACH-with-markup", {
            "amount": "1000000", "account_type": "ACH",
            "client_markup": "0",
        }),
        # Recipient_id null + account_type
        ("ACH-recip-null", {
            "amount": "1000000", "account_type": "ACH",
            "recipient_id": None,
        }),
        # currency on the body
        ("ACH-currency-USD", {
            "amount": "1000000", "account_type": "ACH",
            "currency": "USD",
        }),
        # Add base_currency only
        ("ACH-base-USD", {
            "amount": "1000000", "account_type": "ACH",
            "base_currency": "USD",
        }),
    ]
    summary = {}
    winner = None
    winner_body = None
    winner_resp = None
    for label, body in trials:
        s, b, ms, p = _send(body, token, label=f"fu2-{label}")
        rb = b if isinstance(b, dict) else str(b)[:200]
        msg = b.get("message") if isinstance(b, dict) else None
        summary[label] = {"status": s, "ms": round(ms, 2), "evidence": p.name, "message": msg}
        print(f"  {label:<30} → {s} {msg or ''} → {p.name}")
        if 200 <= s < 300 and winner is None:
            winner = label
            winner_body = body
            winner_resp = b

    if winner:
        print(f"\nWINNER: {winner}")
        summary["WINNER_BODY"] = winner_body
        summary["WINNER_RESPONSE_REDACTED"] = redact_body(winner_resp)

    out = WORK / "probes" / "batch_E_followup2_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary: {out.relative_to(WORK)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
