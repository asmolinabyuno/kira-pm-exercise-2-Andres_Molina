"""Batch E followup — push past the fee/business-validation layer to get a 2xx.

Key insight from initial run:
- Reference schema {account_type, ...} is canonical — it gets past schema validation.
- Guides schema is silently ignored (server requires recipient_id OR account_type).
- amount must be a STRING (per regex error), not a number.
- ACH with amount=1000 (cents? dollars?) returned "Total fees exceed or equal the payout amount".
- WALLET returned "No fee profile configured for product usa-va-fiat-to-crypto-payout".

This script:
1. Retries with amount as STRING "10000.00" on ACH (large amount to dwarf any fee)
2. Tries WIRE, SWIFT, INSTANT_PAY with same large amount
3. Tries amount as integer string "10000" (no decimals)
4. Tries inverse_calculation true/false
5. Once a 2xx is achieved, captures full response shape, then runs GET /v1/quotations/{id}
6. Runs the actual mutations on the canonical body
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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


def _send(body, token, *, label, method="POST", url=None, extra_headers=None):
    attempt_id = str(uuid.uuid4())
    target = url or QUOTE_URL
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    if extra_headers:
        headers.update(extra_headers)
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

    if 200 <= resp.status_code < 300:
        outcome = f"{label}-success"
    elif resp.status_code == 400:
        outcome = f"{label}-fail-400"
    else:
        outcome = f"{label}-fail-{resp.status_code}"

    path = run_flow.capture(
        STEP,
        attempt_id,
        request={"method": method, "url": target, "headers": headers, "body": body},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms,
        outcome=outcome,
    )
    return resp.status_code, resp_body, elapsed_ms, path


def _extract_quote_id(body):
    if not isinstance(body, dict):
        return None
    for k in ("quote_id", "id", "quotation_id"):
        v = body.get(k)
        if isinstance(v, str) and len(v) >= 8:
            return v
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    for k in ("quote_id", "id", "quotation_id"):
        v = data.get(k)
        if isinstance(v, str) and len(v) >= 8:
            return v
    return None


def _short(body):
    if isinstance(body, dict):
        return {k: (v if not isinstance(v, (dict, list)) else f"<{type(v).__name__}>")
                for k, v in list(body.items())[:20]}
    return body


def main():
    print("=" * 72)
    print("Batch E followup — push to 2xx, capture canonical response shape")
    print("=" * 72)
    token = run_flow.auth()
    if not token:
        print("FATAL auth")
        return 1
    print(f"AUTH OK (token len={len(token)})")

    summary = {}

    # Try different account_type + amount combos. amount as STRING per regex hint.
    trials = [
        ("ACH-10000", {"amount": "10000.00", "account_type": "ACH"}),
        ("ACH-100000", {"amount": "100000.00", "account_type": "ACH"}),
        ("WIRE-10000", {"amount": "10000.00", "account_type": "WIRE"}),
        ("SWIFT-10000", {"amount": "10000.00", "account_type": "SWIFT"}),
        ("INSTANT_PAY-10000", {"amount": "10000.00", "account_type": "INSTANT_PAY"}),
        ("WALLET-poly-USDC-10000", {
            "amount": "10000.00", "account_type": "WALLET",
            "wallet_network": "polygon", "wallet_token": "USDC",
        }),
        ("WALLET-tron-USDT-10000", {
            "amount": "10000.00", "account_type": "WALLET",
            "wallet_network": "tron", "wallet_token": "USDT",
        }),
        ("WALLET-solana-USDC-10000", {
            "amount": "10000.00", "account_type": "WALLET",
            "wallet_network": "solana", "wallet_token": "USDC",
        }),
        # Inverse
        ("ACH-inverse-true", {"amount": "10000.00", "account_type": "ACH", "inverse_calculation": True}),
        # int-string amount (no decimals)
        ("ACH-intstr-10000", {"amount": "10000", "account_type": "ACH"}),
    ]

    canonical_body = None
    canonical_resp = None
    quote_id = None
    canonical_label = None

    for label, body in trials:
        status, resp_body, ms, path = _send(body, token, label=f"fu-{label}")
        rb_short = _short(resp_body) if isinstance(resp_body, dict) else str(resp_body)[:300]
        summary[label] = {
            "status": status,
            "elapsed_ms": round(ms, 2),
            "evidence": path.name,
            "response_excerpt": rb_short,
        }
        print(f"  {label:<32} → {status} in {ms:6.1f}ms → {path.name}")
        if 200 <= status < 300 and canonical_body is None:
            canonical_body = dict(body)
            canonical_resp = resp_body
            canonical_label = label
            qid = _extract_quote_id(resp_body)
            if qid:
                quote_id = qid

    # If we have a quote_id, GET it
    if quote_id:
        print(f"\nQUOTE_ID surfaced: {quote_id[:8]}...")
        s, b, ms, p = _send(None, token, label="fu-get-quote", method="GET",
                            url=f"{BASE_URL}/v1/quotations/{quote_id}")
        summary["GET_quote_by_id"] = {"status": s, "elapsed_ms": round(ms, 2), "evidence": p.name}
        print(f"  GET /v1/quotations/{{id}} → {s} in {ms:.1f}ms → {p.name}")

    # Mutations on the canonical winner — re-issue with realistic mutations
    if canonical_body is not None:
        print(f"\nRunning mutations on canonical winner: {canonical_label}")
        # Wrong wallet_network enum (only meaningful if WALLET shape worked)
        if "wallet_network" in canonical_body:
            mut = dict(canonical_body)
            mut["wallet_network"] = "bitcoin"
            s, b, ms, p = _send(mut, token, label="mut-bad-network")
            summary["mut_wrong_wallet_network"] = {"status": s, "elapsed_ms": round(ms, 2),
                                                   "evidence": p.name, "body": _short(b)}
            print(f"  wrong wallet_network=bitcoin → {s} → {p.name}")

            # impossible combo: USDT on solana
            mut = dict(canonical_body)
            mut["wallet_token"] = "USDT"
            mut["wallet_network"] = "solana"
            s, b, ms, p = _send(mut, token, label="mut-impossible-combo")
            summary["mut_impossible_combo"] = {"status": s, "elapsed_ms": round(ms, 2),
                                              "evidence": p.name, "body": _short(b)}
            print(f"  impossible USDT+solana → {s} → {p.name}")

        # Negative amount on the canonical shape
        mut = dict(canonical_body)
        mut["amount"] = "-10000.00"
        s, b, ms, p = _send(mut, token, label="mut-neg-amount")
        summary["mut_negative_amount"] = {"status": s, "elapsed_ms": round(ms, 2),
                                          "evidence": p.name, "body": _short(b)}
        print(f"  negative amount → {s} → {p.name}")

        # Wrong account_type enum
        mut = dict(canonical_body)
        mut["account_type"] = "SPEI"  # not in WIRE/SWIFT/WALLET/ACH/INSTANT_PAY per error msg
        s, b, ms, p = _send(mut, token, label="mut-spei")
        summary["mut_account_type_SPEI"] = {"status": s, "elapsed_ms": round(ms, 2),
                                            "evidence": p.name, "body": _short(b)}
        print(f"  account_type=SPEI (LATAM) → {s} → {p.name}")

        # Latency burst on the canonical 2xx call
        if 200 <= summary[canonical_label.replace("fu-", "")]["status"] if False else True:
            print(f"\nLatency burst (n=5) on {canonical_label}")
            samples = []
            last_status = None
            for i in range(5):
                s, b, ms, p = _send(canonical_body, token, label=f"lat-{i+1}")
                samples.append(ms)
                last_status = s
                time.sleep(0.2)
            if samples:
                stats = {
                    "n": len(samples),
                    "min_ms": round(min(samples), 2),
                    "median_ms": round(statistics.median(samples), 2),
                    "max_ms": round(max(samples), 2),
                    "samples_ms": [round(x, 2) for x in samples],
                    "last_status": last_status,
                    "canonical_label": canonical_label,
                }
                summary["latency_burst"] = stats
                out_lat = WORK / "latency" / "post_v1_quotations.json"
                out_lat.write_text(json.dumps(stats, indent=2))
                print(f"  median={stats['median_ms']}ms n={stats['n']} status={last_status}")

    # Capture the canonical response shape verbatim (redacted)
    if canonical_resp is not None:
        summary["CANONICAL_RESPONSE_SHAPE_REDACTED"] = redact_body(canonical_resp)
        summary["CANONICAL_LABEL"] = canonical_label

    out = WORK / "probes" / "batch_E_followup_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary written to {out.relative_to(WORK)}")
    print(f"CANONICAL WINNER: {canonical_label or 'NONE (all 4xx)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
