"""Batch E — Quotations schema disambiguation (GAP-31).

Sends POST /v1/quotations with the Guides schema, then the Reference schema,
then a union body, then an empty body, then mutations on the canonical winner,
then a latency burst, then a GET /v1/quotations/{id} read-back if a quote_id
was returned.

Hard rules:
- Do not modify run_flow.py (we only import auth/capture/_redact from it).
- httpx with timeout=30.
- Evidence per call goes to evidence/work/quotations/{NN}-{outcome}.json.
- Never log secrets — all bodies/headers go through _redact.
- Iteration counted manually; max 3 attempts per shape.
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

# Re-use redaction + auth from the shared module without modifying it.
from _redact import redact_body, redact_headers  # noqa: E402
import run_flow  # noqa: E402  — we use BASE_URL, API_KEY, capture(), auth()

BASE_URL = run_flow.BASE_URL
API_KEY = run_flow.API_KEY

QUOTE_URL = f"{BASE_URL}/v1/quotations"
STEP = "quotations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send(
    body: Dict[str, Any] | None,
    token: str,
    *,
    label: str,
    method: str = "POST",
    url: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Any, float, Path]:
    """Send a single request, capture evidence, return (status, body, ms, path)."""
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
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    if 200 <= resp.status_code < 300:
        outcome = f"{label}-success"
    elif resp.status_code in (400, 422):
        outcome = f"{label}-validation-{resp.status_code}"
    elif resp.status_code in (401, 403):
        outcome = f"{label}-authz-{resp.status_code}"
    elif resp.status_code in (404,):
        outcome = f"{label}-notfound-{resp.status_code}"
    elif resp.status_code in (409,):
        outcome = f"{label}-conflict-{resp.status_code}"
    else:
        outcome = f"{label}-fail-{resp.status_code}"

    path = run_flow.capture(
        STEP,
        attempt_id,
        request={"method": method, "url": target, "headers": headers, "body": body},
        response={
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
    )
    return resp.status_code, resp_body, elapsed_ms, path


def _extract_quote_id(body: Any) -> Optional[str]:
    """Best-effort dig for a quote_id-shaped string in the response."""
    if not isinstance(body, dict):
        return None
    candidates = [
        body.get("quote_id"),
        body.get("id"),
        body.get("quotation_id"),
    ]
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    candidates += [data.get("quote_id"), data.get("id"), data.get("quotation_id")]
    for c in candidates:
        if isinstance(c, str) and len(c) >= 8:
            return c
    return None


def _summary(status: int, body: Any, ms: float, path: Path) -> Dict[str, Any]:
    return {
        "status": status,
        "elapsed_ms": round(ms, 2),
        "evidence": str(path.relative_to(WORK)),
        "body_keys": (
            list(body.keys())
            if isinstance(body, dict)
            else (f"<{type(body).__name__}:len={len(body) if hasattr(body, '__len__') else '?'}>")
        ),
    }


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


def probe_e1_guides(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E1 — Guides schema: base_currency / quote_currency / amount."""
    body = {
        "base_currency": "USD",
        "quote_currency": "MXN",
        "amount": 1000,
    }
    return _send(body, token, label="e1-guides")


def probe_e1b_guides_amount_in_destination(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E1b — Guides schema variant with amount_in_destination flag."""
    body = {
        "base_currency": "USD",
        "quote_currency": "MXN",
        "amount": 1000,
        "amount_in_destination": True,
    }
    return _send(body, token, label="e1b-guides-amt-in-dest")


def probe_e2_reference(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E2 — Reference schema: account_type / wallet_network / wallet_token.

    The Reference page only documents WIRE/SWIFT/WALLET/ACH/INSTANT_PAY as
    account_type values. We send WALLET with USDC on polygon — the most
    Reference-canonical combination.
    """
    body = {
        "amount": 1000,
        "account_type": "WALLET",
        "wallet_network": "polygon",
        "wallet_token": "USDC",
        "inverse_calculation": False,
    }
    return _send(body, token, label="e2-ref-wallet")


def probe_e2b_reference_ach(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E2b — Reference schema with ACH account_type (no wallet_* fields)."""
    body = {
        "amount": 1000,
        "account_type": "ACH",
        "inverse_calculation": False,
    }
    return _send(body, token, label="e2b-ref-ach")


def probe_e3_union(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E3 — both shapes mixed in one body."""
    body = {
        # Guides fields
        "base_currency": "USD",
        "quote_currency": "MXN",
        "amount": 1000,
        "amount_in_destination": False,
        # Reference fields
        "account_type": "WALLET",
        "wallet_network": "polygon",
        "wallet_token": "USDC",
        "inverse_calculation": False,
    }
    return _send(body, token, label="e3-union")


def probe_e4_empty(token: str) -> Tuple[int, Any, float, Path]:
    """Probe E4 — empty body. Reveals which fields the server requires."""
    return _send({}, token, label="e4-empty")


def probe_e5_mutations(token: str, canonical_template: Dict[str, Any]) -> Dict[str, Any]:
    """Probe E5 — mutations on the canonical winner.

    Runs three error probes:
    - Wrong enum for wallet_network (or quote_currency)
    - Negative amount
    - Cross-currency impossibility (USDC token on bitcoin-shaped network)
    """
    results: Dict[str, Any] = {}

    # 5a — wrong enum
    body = dict(canonical_template)
    if "wallet_network" in body:
        body["wallet_network"] = "bitcoin"  # not in {solana, polygon, tron}
        results["wrong_wallet_network"] = _send(body, token, label="e5a-bad-network")
    elif "quote_currency" in body:
        body["quote_currency"] = "XYZ"  # nonsense ISO code
        results["wrong_quote_currency"] = _send(body, token, label="e5a-bad-currency")

    # 5b — negative amount
    body = dict(canonical_template)
    body["amount"] = -1000
    results["negative_amount"] = _send(body, token, label="e5b-negative-amount")

    # 5c — cross-currency impossibility
    body = dict(canonical_template)
    if "wallet_network" in body and "wallet_token" in body:
        # USDT on solana — per Apr-14 changelog USDT is only tron/polygon
        body["wallet_token"] = "USDT"
        body["wallet_network"] = "solana"
        results["impossible_token_network"] = _send(body, token, label="e5c-impossible-combo")
    elif "base_currency" in body and "quote_currency" in body:
        # Fiat-to-fiat — Kira does NOT do this per CLAUDE.md
        body["base_currency"] = "USD"
        body["quote_currency"] = "EUR"
        results["fiat_to_fiat"] = _send(body, token, label="e5c-fiat-to-fiat")
    return results


def probe_e6_latency(token: str, body: Dict[str, Any], n: int = 5) -> Dict[str, Any]:
    """Probe E6 — n samples of canonical successful call. Latency only."""
    samples: list[float] = []
    last_status = None
    for i in range(n):
        status, _, ms, _ = _send(body, token, label=f"e6-lat-{i+1}")
        samples.append(ms)
        last_status = status
        time.sleep(0.2)
    if samples:
        stats = {
            "n": len(samples),
            "min_ms": round(min(samples), 2),
            "median_ms": round(statistics.median(samples), 2),
            "max_ms": round(max(samples), 2),
            "p95_ms": round(
                statistics.quantiles(samples, n=20)[18] if len(samples) >= 5 else max(samples), 2
            ),
            "samples_ms": [round(s, 2) for s in samples],
            "last_status": last_status,
        }
    else:
        stats = {"n": 0}
    return stats


def probe_e7_get_quote(token: str, quote_id: str) -> Tuple[int, Any, float, Path]:
    """Probe E7 — GET /v1/quotations/{id}."""
    return _send(
        None,
        token,
        label="e7-get",
        method="GET",
        url=f"{BASE_URL}/v1/quotations/{quote_id}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 72)
    print("Batch E — Quotations disambiguation (GAP-31)")
    print("=" * 72)

    token = run_flow.auth()
    if not token:
        print("FATAL: /auth failed — cannot run Batch E.")
        return 1
    print(f"AUTH OK — token in memory, length={len(token)}")

    log: Dict[str, Any] = {"probes": {}}

    # --- E1 — Guides schema ----------------------------------------------
    s, b, ms, p = probe_e1_guides(token)
    log["probes"]["E1_guides"] = _summary(s, b, ms, p)
    print(f"E1 (Guides simple)  → {s} in {ms:.1f}ms → {p.name}")

    s_b, b_b, ms_b, p_b = probe_e1b_guides_amount_in_destination(token)
    log["probes"]["E1b_guides_amount_in_destination"] = _summary(s_b, b_b, ms_b, p_b)
    print(f"E1b (Guides amt_in_dest) → {s_b} in {ms_b:.1f}ms → {p_b.name}")

    # --- E2 — Reference schema -------------------------------------------
    s2, b2, ms2, p2 = probe_e2_reference(token)
    log["probes"]["E2_reference_wallet"] = _summary(s2, b2, ms2, p2)
    print(f"E2 (Reference WALLET) → {s2} in {ms2:.1f}ms → {p2.name}")

    s2b, b2b, ms2b, p2b = probe_e2b_reference_ach(token)
    log["probes"]["E2b_reference_ach"] = _summary(s2b, b2b, ms2b, p2b)
    print(f"E2b (Reference ACH) → {s2b} in {ms2b:.1f}ms → {p2b.name}")

    # --- E3 — union ------------------------------------------------------
    s3, b3, ms3, p3 = probe_e3_union(token)
    log["probes"]["E3_union"] = _summary(s3, b3, ms3, p3)
    print(f"E3 (Union)          → {s3} in {ms3:.1f}ms → {p3.name}")

    # --- E4 — empty body -------------------------------------------------
    s4, b4, ms4, p4 = probe_e4_empty(token)
    log["probes"]["E4_empty"] = _summary(s4, b4, ms4, p4)
    print(f"E4 (Empty body)     → {s4} in {ms4:.1f}ms → {p4.name}")
    log["probes"]["E4_empty"]["response_body_redacted"] = redact_body(b4)

    # --- Determine canonical schema --------------------------------------
    def _is_2xx(status: int) -> bool:
        return 200 <= status < 300

    canonical: Optional[str] = None
    canonical_body: Optional[Dict[str, Any]] = None

    if _is_2xx(s):
        canonical = "guides"
        canonical_body = {"base_currency": "USD", "quote_currency": "MXN", "amount": 1000}
    elif _is_2xx(s_b):
        canonical = "guides"
        canonical_body = {
            "base_currency": "USD",
            "quote_currency": "MXN",
            "amount": 1000,
            "amount_in_destination": True,
        }
    elif _is_2xx(s2):
        canonical = "reference"
        canonical_body = {
            "amount": 1000,
            "account_type": "WALLET",
            "wallet_network": "polygon",
            "wallet_token": "USDC",
            "inverse_calculation": False,
        }
    elif _is_2xx(s2b):
        canonical = "reference"
        canonical_body = {
            "amount": 1000,
            "account_type": "ACH",
            "inverse_calculation": False,
        }
    elif _is_2xx(s3):
        canonical = "union-accepted"
        canonical_body = {
            "base_currency": "USD",
            "quote_currency": "MXN",
            "amount": 1000,
            "account_type": "WALLET",
            "wallet_network": "polygon",
            "wallet_token": "USDC",
        }

    log["canonical_schema"] = canonical
    print(f"\n>>> CANONICAL SCHEMA DETECTED: {canonical or 'NEITHER (no 2xx yet)'}")

    # If neither shape succeeded, inspect the 4xx error bodies to extract a hint
    if canonical is None:
        log["error_bodies"] = {
            "E1": redact_body(b),
            "E1b": redact_body(b_b),
            "E2": redact_body(b2),
            "E2b": redact_body(b2b),
            "E3": redact_body(b3),
            "E4": redact_body(b4),
        }

    # --- E5 — mutations on the winning schema (or best-effort otherwise) -
    if canonical_body is not None:
        e5 = probe_e5_mutations(token, canonical_body)
        log["probes"]["E5_mutations"] = {
            k: _summary(*v) for k, v in e5.items()
        }
        for name, (st, _, mss, pp) in e5.items():
            print(f"E5 ({name})  → {st} in {mss:.1f}ms → {pp.name}")
    else:
        # No canonical yet — still try mutations against both shapes for forensics
        print("E5 SKIPPED — no canonical 2xx; running mutations on Guides shape anyway")
        e5 = probe_e5_mutations(
            token, {"base_currency": "USD", "quote_currency": "MXN", "amount": 1000}
        )
        log["probes"]["E5_mutations_guides_fallback"] = {
            k: _summary(*v) for k, v in e5.items()
        }

    # --- E6 — latency on the canonical successful call -------------------
    if canonical_body is not None and canonical is not None:
        lat = probe_e6_latency(token, canonical_body, n=5)
        log["probes"]["E6_latency"] = lat
        out_lat = WORK / "latency" / "post_v1_quotations.json"
        out_lat.parent.mkdir(parents=True, exist_ok=True)
        out_lat.write_text(json.dumps({"canonical_schema": canonical, **lat}, indent=2))
        print(f"E6 latency stats  → n={lat.get('n')} median={lat.get('median_ms')}ms")
    else:
        # Still measure 4xx latency on the Guides shape so we have *something*.
        lat = probe_e6_latency(
            token, {"base_currency": "USD", "quote_currency": "MXN", "amount": 1000}, n=3
        )
        log["probes"]["E6_latency_4xx_fallback"] = lat
        out_lat = WORK / "latency" / "post_v1_quotations.json"
        out_lat.parent.mkdir(parents=True, exist_ok=True)
        out_lat.write_text(
            json.dumps({"canonical_schema": None, "note": "4xx-only timings", **lat}, indent=2)
        )
        print(f"E6 (4xx latency)  → n={lat.get('n')} median={lat.get('median_ms')}ms")

    # --- E7 — GET on returned quote --------------------------------------
    quote_id: Optional[str] = None
    for canonical_resp in [b, b_b, b2, b2b, b3]:
        qid = _extract_quote_id(canonical_resp)
        if qid:
            quote_id = qid
            break

    if quote_id:
        s7, b7, ms7, p7 = probe_e7_get_quote(token, quote_id)
        log["probes"]["E7_get_quote"] = _summary(s7, b7, ms7, p7)
        print(f"E7 (GET quote)     → {s7} in {ms7:.1f}ms → {p7.name}")
        # Also try a junk UUID for shape diff
        s7b, b7b, ms7b, p7b = probe_e7_get_quote(token, "00000000-0000-4000-8000-000000000000")
        log["probes"]["E7b_get_quote_junk"] = _summary(s7b, b7b, ms7b, p7b)
        print(f"E7b (GET junk uuid) → {s7b} in {ms7b:.1f}ms → {p7b.name}")
    else:
        print("E7 SKIPPED — no quote_id surfaced in any 2xx response.")
        log["probes"]["E7_get_quote"] = "skipped: no quote_id"

    # --- summary out -----------------------------------------------------
    out = WORK / "probes" / "batch_E_summary.json"
    out.write_text(json.dumps(log, indent=2, default=str))
    print(f"\nSummary written to {out.relative_to(WORK)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
