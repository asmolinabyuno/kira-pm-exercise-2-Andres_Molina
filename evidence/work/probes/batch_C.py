"""Batch C — POST /v1/recipients polymorphic probe.

Goals (per integration-plan.md §3 Batch C and §4 POST /v1/recipients):
  - Create 4 polymorphic variants: SPEI MX, USD ACH bank, USDT crypto (TRC20), SWIFT EUR
  - Capture per-variant schema (required / optional / response shape)
  - Stress idempotency: replay same body, replay different body (GAP-08 confirmation)
  - Cross-pollution probes: mix variant fields, mismatched country
  - List + Detail reads
  - DELETE recipient (probe semantics — not documented as supported in flow-design)

Hard rules (re-iterating Batch C instructions):
  - Use ONLY fake data; format-valid but obviously test (CLABE `01218...`,
    IBAN GB-style fake, BIC `TESTUS33`, TRON `T...`).
  - NEVER log raw secrets; all writes use _redact through run_flow.capture.
  - Do NOT modify run_flow.py — import auth + capture only.
  - Per-call evidence path: evidence/work/recipients/{NN}-{outcome}.json
  - httpx, timeout=30.

Outputs:
  - evidence/work/recipients/*.json (one per HTTP call)
  - evidence/work/integration-log-batch-C.md (the batch ledger; appended by hand)

Run:  python3 evidence/work/probes/batch_C.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import httpx
from dotenv import load_dotenv

# Make sibling modules importable regardless of cwd.
HERE = Path(__file__).resolve().parent              # evidence/work/probes
WORK = HERE.parent                                  # evidence/work
ROOT = WORK.parents[1]                              # project root
for p in (str(WORK), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _redact import redact_body, redact_headers     # noqa: E402
from run_flow import auth                           # noqa: E402  – reuse auth(), do NOT modify it

load_dotenv(ROOT / ".env")

BASE_URL = os.environ["KIRA_API_BASE_URL"].rstrip("/")
API_KEY = os.environ["KIRA_API_KEY"]

STEP_DIR = WORK / "recipients"
STEP_DIR.mkdir(parents=True, exist_ok=True)

# Pre-existing user from prior Batch A/B work (per evidence/work/users/06-success.json).
# This user is in status CREATED (verification_triggered: false) — Batch C will discover
# whether recipient creation requires VERIFIED (per integration-plan §3 prereq UNDOCUMENTED).
EXISTING_USER_ID = "65ba0e06-9f52-4c43-b093-5d30a632ce3d"

# Optional override via env. Falls back to the file-known UUID.
USER_ID = os.environ.get("KIRA_BATCH_C_USER_ID", EXISTING_USER_ID)


# ---------------------------------------------------------------------------
# Capture helper (mirrors run_flow.capture but writes into evidence/work/recipients).
# We re-implement here only so this script never touches run_flow.py.
# ---------------------------------------------------------------------------
def _next_seq() -> int:
    return len(sorted(STEP_DIR.glob("*.json"))) + 1


def capture_call(
    attempt_id: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    elapsed_ms: float,
    outcome: str,
    filename: Optional[str] = None,
) -> Path:
    """Write a request/response evidence file under evidence/work/recipients/."""
    if filename is not None:
        out = STEP_DIR / f"{filename}.json"
    else:
        nn = f"{_next_seq():02d}"
        out = STEP_DIR / f"{nn}-{outcome}.json"

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "elapsed_ms": round(elapsed_ms, 2),
        "outcome": outcome,
        "request": {
            "method": request["method"],
            "url": request["url"],
            "headers": redact_headers(request.get("headers", {}) or {}),
            "body": redact_body(request.get("body")) if request.get("body") is not None else None,
        },
        "response": {
            "status": response["status"],
            "headers": redact_headers(response.get("headers", {}) or {}),
            "body": redact_body(response.get("body")),
        },
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


# ---------------------------------------------------------------------------
# Low-level HTTP helpers.
# ---------------------------------------------------------------------------
def _headers(token: str, idem_key: Optional[str] = None) -> Dict[str, str]:
    h: Dict[str, str] = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    if idem_key is not None:
        # Per flow-design §2.4, docs use lowercase `idempotency-key`. Send both
        # forms-equivalent — httpx normalises header names but the wire format
        # follows what we send. Send lowercase to match docs.
        h["idempotency-key"] = idem_key
    return h


def post_recipient(
    token: str,
    body: Dict[str, Any],
    *,
    idem_key: Optional[str],
    outcome_hint: str,
    filename: Optional[str] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Path, float]:
    url = f"{BASE_URL}/v1/recipients"
    headers = _headers(token, idem_key=idem_key)
    attempt_id = str(uuid.uuid4())

    t0 = time.perf_counter_ns()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    if 200 <= resp.status_code < 300:
        outcome = f"success-{resp.status_code}-{outcome_hint}"
    else:
        outcome = f"fail-{resp.status_code}-{outcome_hint}"

    path = capture_call(
        attempt_id,
        request={"method": "POST", "url": url, "headers": headers, "body": body},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )
    return resp.status_code, resp_body, path, elapsed_ms


def get_recipients_list(
    token: str,
    *,
    user_id: str,
    outcome_hint: str = "list",
    filename: Optional[str] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Path, float]:
    url = f"{BASE_URL}/v1/recipients"
    params = {"user_id": user_id}
    headers = _headers(token)
    attempt_id = str(uuid.uuid4())

    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    outcome = f"{'success' if 200 <= resp.status_code < 300 else 'fail'}-{resp.status_code}-{outcome_hint}"
    full_url = f"{url}?user_id={user_id}"
    path = capture_call(
        attempt_id,
        request={"method": "GET", "url": full_url, "headers": headers, "body": None},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )
    return resp.status_code, resp_body, path, elapsed_ms


def get_recipient_detail(
    token: str,
    *,
    recipient_id: str,
    outcome_hint: str = "detail",
    filename: Optional[str] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Path, float]:
    url = f"{BASE_URL}/v1/recipients/{recipient_id}"
    headers = _headers(token)
    attempt_id = str(uuid.uuid4())

    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    outcome = f"{'success' if 200 <= resp.status_code < 300 else 'fail'}-{resp.status_code}-{outcome_hint}"
    path = capture_call(
        attempt_id,
        request={"method": "GET", "url": url, "headers": headers, "body": None},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )
    return resp.status_code, resp_body, path, elapsed_ms


def delete_recipient(
    token: str,
    *,
    recipient_id: str,
    outcome_hint: str = "delete",
    filename: Optional[str] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Path, float]:
    url = f"{BASE_URL}/v1/recipients/{recipient_id}"
    headers = _headers(token)
    attempt_id = str(uuid.uuid4())

    t0 = time.perf_counter_ns()
    resp = httpx.delete(url, headers=headers, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    outcome = f"{'success' if 200 <= resp.status_code < 300 else 'fail'}-{resp.status_code}-{outcome_hint}"
    path = capture_call(
        attempt_id,
        request={"method": "DELETE", "url": url, "headers": headers, "body": None},
        response={"status": resp.status_code, "headers": dict(resp.headers), "body": resp_body},
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )
    return resp.status_code, resp_body, path, elapsed_ms


# ---------------------------------------------------------------------------
# Fake-payload builders per recipient variant.
#
# All numbers are *format-valid but obviously fake* — leading `0...` patterns,
# `FAKE` document numbers, and `TEST` BIC codes ensure no real account is
# referenced.
# ---------------------------------------------------------------------------
def spei_mx_payload() -> Dict[str, Any]:
    """SPEI MX variant — flow-design §3.5 row SPEI.

    Required per flow-design: clabe (18 digits), doc_type (rfc|curp), doc_number.
    """
    return {
        "user_id": USER_ID,
        "first_name": "Test",
        "last_name": "Beneficiary",
        "email": "test+spei@example.com",
        "phone": "+525512345678",
        "account": {
            "account_type": "SPEI",
            "clabe": "012180001234567890",  # fake 18-digit CLABE (BBVA prefix-shape)
            "doc_type": "rfc",
            "doc_number": "TFAK900101AAA",   # fake RFC pattern
            "bank_name": "Test SPEI Bank",
            "currency": "MXN",
            "country": "MX",
        },
    }


def ach_usd_payload() -> Dict[str, Any]:
    """ACH USD variant — flow-design §3.5 row ACH.

    Required: routing_number (9 digits ABA), account_number (>=4), type
    (checking|savings), bank_name, bank_address (STRING for ACH — GAP-16),
    doc_type, doc_number, + recipient-level address object.

    EMPIRICAL CORRECTIONS (DRIFT-C2, DRIFT-C3):
      - country fields are ALPHA-2 not ALPHA-3 (docs say alpha-3) — flipped USA→US
      - doc_type enum runtime is {id, dni, passport, ein} — `ssn` is NOT accepted
        (flow-design §3.5 listed `ssn` as a doc_type which is wrong)
    """
    return {
        "user_id": USER_ID,
        "first_name": "Test",
        "last_name": "Recipient",
        "email": "test+ach@example.com",
        "phone": "+15555550100",
        "address": {
            "street_name": "100 Test St",
            "city": "San Francisco",
            "state": "CA",
            "postal_code": "94105",
            "country": "US",   # alpha-2 per DRIFT-C2
        },
        "account": {
            "account_type": "ACH",
            "routing_number": "021000089",
            "account_number": "000123456789",
            "type": "checking",
            "bank_name": "Test US Bank N.A.",
            "bank_address": "1 Bank Plaza, New York, NY 10001, USA",  # STRING — ACH form
            "doc_type": "id",     # runtime enum per DRIFT-C3
            "doc_number": "FAKE000000",
            "currency": "USD",
            "country": "US",
        },
    }


def usdt_tron_payload() -> Dict[str, Any]:
    """USDT crypto (TRON / TRC20) — flow-design §3.5 row WALLET.

    Per Apr-14 changelog: USDT supports tron/polygon (NOT solana). TRON addresses
    are base58 and start with `T`. The API enforces base58check, so we use a
    real-shaped test address — TRON's "burn address" (TLsV52sRDL79HXGGm9yzwKibb6BeruhUzy)
    is publicly known and not attacker-controlled (still no privkey).

    EMPIRICAL CORRECTION (DRIFT-C4): runtime rejects pure-fake addresses (good
    — it actually validates base58check), so we must use a format-VALID test
    address. The chosen value is documented publicly as TRON's zero-address.
    """
    return {
        "user_id": USER_ID,
        "first_name": "Test",
        "last_name": "WalletHolder",
        "email": "test+usdt@example.com",
        "account": {
            "account_type": "WALLET",
            "token": "USDT",
            "network": "tron",
            # Format-valid 34-char TRON address (base58check valid; publicly known test addr).
            "address": "TLsV52sRDL79HXGGm9yzwKibb6BeruhUzy",
            "currency": "USDT",
        },
    }


def swift_eur_payload() -> Dict[str, Any]:
    """SWIFT EUR variant — flow-design §3.5 row SWIFT.

    Required: account_number (or IBAN, >=4), swift_code (8 or 11),
    bank_name, bank_address (OBJECT for SWIFT — GAP-16), doc_type, doc_number.

    EMPIRICAL CORRECTIONS (DRIFT-C2, DRIFT-C5):
      - bank_address.country MUST be alpha-2 (runtime: "exactly 2 characters")
      - doc_country_code MUST be alpha-2 (runtime: "exactly 2 characters")
      - RECIPIENT-LEVEL `address` object is REQUIRED for SWIFT — flow-design §3.5
        listed it as required only for ACH (DRIFT-C5: extends Address-required-set)
    """
    return {
        "user_id": USER_ID,
        "first_name": "Test",
        "last_name": "EuroBeneficiary",
        "email": "test+swift@example.com",
        "phone": "+34900000000",
        # SWIFT also requires recipient-level address per runtime — DRIFT-C5
        "address": {
            "street_name": "1 Recipient St",
            "city": "Madrid",
            "state": "Madrid",
            "postal_code": "28001",
            "country": "ES",
        },
        "account": {
            "account_type": "SWIFT",
            "account_number": "ES7100000000000000000000",   # fake IBAN-shape (ES + 22 digits)
            "swift_code": "TESTESM0XXX",                    # fake 11-char BIC
            "bank_name": "Test European Bank S.A.",
            "bank_address": {                                # OBJECT for SWIFT
                "street_name": "1 Bank Avenue",
                "city": "Madrid",
                "state": "Madrid",
                "postal_code": "28001",
                "country": "ES",       # alpha-2 per DRIFT-C2
            },
            "doc_type": "passport",
            "doc_number": "FAKE000000",
            "doc_country_code": "ES",  # alpha-2 per DRIFT-C2
            "currency": "EUR",
            "country": "ES",
        },
    }


# ---------------------------------------------------------------------------
# Driver — runs all phases and prints a compact summary.
# ---------------------------------------------------------------------------
def run() -> None:
    print("=== Batch C — Recipients (polymorphic) probe ===")
    print(f"user_id: {USER_ID}")

    token = auth()
    if not token:
        print("AUTH FAILED — aborting Batch C")
        sys.exit(1)
    print("AUTH OK")

    summary: Dict[str, Any] = {"created": [], "phases": {}}

    # ----- Phase C1: 4 polymorphic variants -----
    print("\n--- Phase C1: 4 polymorphic variants ---")
    for variant_name, builder in (
        ("spei",  spei_mx_payload),
        ("ach",   ach_usd_payload),
        ("usdt",  usdt_tron_payload),
        ("swift", swift_eur_payload),
    ):
        idem = str(uuid.uuid4())
        body = builder()
        status, resp, path, ms = post_recipient(
            token, body,
            idem_key=idem,
            outcome_hint=variant_name,
        )
        print(f"  {variant_name:>5}  HTTP {status}  {ms:6.1f}ms  -> {path.name}")
        rec_id = None
        if isinstance(resp, dict):
            # Probe multiple plausible response shapes.
            rec_id = (
                resp.get("id")
                or resp.get("recipient_id")
                or (resp.get("data") or {}).get("id")
                or (resp.get("data") or {}).get("recipient_id")
            )
        summary["created"].append({
            "variant": variant_name,
            "status": status,
            "recipient_id": rec_id,
            "idem_key": idem,
            "body": body,
            "evidence": str(path),
        })

    # Identify the SPEI created recipient for the idempotency phase (it's the
    # canonical Recipe-B dependency per integration-plan §3 Batch C).
    spei_record = next((r for r in summary["created"] if r["variant"] == "spei"), None)
    ach_record  = next((r for r in summary["created"] if r["variant"] == "ach"),  None)

    # ----- Phase C2: list + detail reads -----
    print("\n--- Phase C2: list + detail ---")
    status, list_body, path, ms = get_recipients_list(
        token, user_id=USER_ID, outcome_hint="list-by-user",
    )
    print(f"  LIST   HTTP {status}  {ms:6.1f}ms  -> {path.name}")
    summary["phases"]["list"] = {"status": status, "evidence": str(path)}

    detail_target = None
    for rec in summary["created"]:
        if rec["recipient_id"]:
            detail_target = rec
            break
    if detail_target:
        status, body, path, ms = get_recipient_detail(
            token,
            recipient_id=detail_target["recipient_id"],
            outcome_hint=f"detail-{detail_target['variant']}",
        )
        print(f"  DETAIL HTTP {status}  {ms:6.1f}ms  -> {path.name}  ({detail_target['variant']})")
        summary["phases"]["detail"] = {
            "status": status,
            "recipient_id": detail_target["recipient_id"],
            "variant": detail_target["variant"],
            "evidence": str(path),
        }
    else:
        print("  DETAIL skipped — no recipient_id captured from C1")
        summary["phases"]["detail"] = {"skipped": True}

    # ----- Phase C3: idempotency probes (the highest-leverage section) -----
    print("\n--- Phase C3: idempotency probes ---")

    # 3a. Replay SAME body + SAME key (expected: cached 201, or 202-on-replay per §3.5 quirk)
    #    Choose the SPEI variant: a successful create gives us the cleanest replay signal.
    #    If SPEI failed, fall back to ACH or any successful create.
    replay_record = None
    for r in summary["created"]:
        if 200 <= r["status"] < 300:
            replay_record = r
            break
    if replay_record is None:
        # As fallback, use the SPEI record even on failure to still observe behavior.
        replay_record = spei_record

    if replay_record is not None:
        print(f"  IDEM-REPLAY (same body, same key, variant={replay_record['variant']})")
        status, resp, path, ms = post_recipient(
            token, replay_record["body"],
            idem_key=replay_record["idem_key"],
            outcome_hint=f"idem-replay-same-{replay_record['variant']}",
        )
        replayed_id = None
        if isinstance(resp, dict):
            replayed_id = (
                resp.get("id")
                or resp.get("recipient_id")
                or (resp.get("data") or {}).get("id")
                or (resp.get("data") or {}).get("recipient_id")
            )
        same_id = (replayed_id == replay_record["recipient_id"]) if replayed_id else None
        print(f"           HTTP {status}  {ms:6.1f}ms  same_id={same_id}  -> {path.name}")
        summary["phases"]["idem_replay_same"] = {
            "status": status,
            "original_id": replay_record["recipient_id"],
            "replayed_id": replayed_id,
            "ids_match": same_id,
            "evidence": str(path),
        }

        # 3b. SAME key + MUTATED body — expect 409 idempotency_conflict / IDEMPOTENCY_CONFLICT.
        mutated = json.loads(json.dumps(replay_record["body"]))  # deep copy
        # Mutate a non-secret, identity-bearing field:
        mutated["last_name"] = "MutatedSurname"
        if "account" in mutated and "doc_number" in mutated["account"]:
            mutated["account"]["doc_number"] = "MUTATED00000"
        print(f"  IDEM-CONFLICT (same key, mutated body, variant={replay_record['variant']})")
        status, resp, path, ms = post_recipient(
            token, mutated,
            idem_key=replay_record["idem_key"],
            outcome_hint=f"idem-conflict-{replay_record['variant']}",
        )
        print(f"            HTTP {status}  {ms:6.1f}ms  -> {path.name}")
        summary["phases"]["idem_conflict_mutated"] = {
            "status": status,
            "evidence": str(path),
        }
    else:
        print("  IDEM probes skipped — no created recipient available")

    # 3c. Omit idempotency-key entirely — expected 400 per flow-design §2.4.
    print("  IDEM-OMIT (no idempotency-key header)")
    status, resp, path, ms = post_recipient(
        token, spei_mx_payload(),
        idem_key=None,
        outcome_hint="idem-omit",
    )
    print(f"            HTTP {status}  {ms:6.1f}ms  -> {path.name}")
    summary["phases"]["idem_omit"] = {"status": status, "evidence": str(path)}

    # ----- Mutations: cross-pollution + country mismatch -----
    print("\n--- Mutations: cross-pollution + country mismatch ---")

    # M1. SPEI body with WALLET fields injected — does API reject or silently ignore?
    polluted = spei_mx_payload()
    polluted["account"]["wallet_address"] = "TInjectedWalletAddrXXXXXXXXXXXXXXXX"
    polluted["account"]["network"] = "tron"
    polluted["account"]["token"] = "USDT"
    print("  M1: SPEI body + WALLET fields injected")
    status, resp, path, ms = post_recipient(
        token, polluted,
        idem_key=str(uuid.uuid4()),
        outcome_hint="m1-spei-with-wallet-fields",
    )
    print(f"      HTTP {status}  {ms:6.1f}ms  -> {path.name}")
    summary["phases"]["m1_cross_pollution"] = {"status": status, "evidence": str(path)}

    # M2. SPEI body with country=USA instead of MX — country mismatch (GAP-20 cross-test).
    mismatched = spei_mx_payload()
    mismatched["account"]["country"] = "USA"  # WRONG: SPEI is MXN-only
    print("  M2: SPEI body + country=USA (should be MX)")
    status, resp, path, ms = post_recipient(
        token, mismatched,
        idem_key=str(uuid.uuid4()),
        outcome_hint="m2-spei-country-mismatch",
    )
    print(f"      HTTP {status}  {ms:6.1f}ms  -> {path.name}")
    summary["phases"]["m2_country_mismatch"] = {"status": status, "evidence": str(path)}

    # ----- Phase C4: DELETE recipient -----
    # flow-design §3.5 does NOT document DELETE; this is a probe of unsupported-method behavior.
    print("\n--- Phase C4: DELETE recipient ---")
    delete_target = None
    for r in summary["created"]:
        if r["recipient_id"]:
            delete_target = r
            break
    # Prefer USDT or ACH for deletion to keep the SPEI recipient alive for Batch F.
    for r in summary["created"]:
        if r["recipient_id"] and r["variant"] in ("usdt", "ach"):
            delete_target = r
            break
    if delete_target:
        status, body, path, ms = delete_recipient(
            token,
            recipient_id=delete_target["recipient_id"],
            outcome_hint=f"delete-{delete_target['variant']}",
        )
        print(f"  DELETE HTTP {status}  {ms:6.1f}ms  ({delete_target['variant']})  -> {path.name}")
        summary["phases"]["delete"] = {
            "status": status,
            "recipient_id": delete_target["recipient_id"],
            "variant": delete_target["variant"],
            "evidence": str(path),
        }
        # Follow up: GET the deleted recipient — does it 404, or return tombstoned record?
        status_after, body_after, path_after, ms_after = get_recipient_detail(
            token,
            recipient_id=delete_target["recipient_id"],
            outcome_hint=f"detail-after-delete-{delete_target['variant']}",
        )
        print(f"  GET-AFTER-DELETE HTTP {status_after}  {ms_after:6.1f}ms  -> {path_after.name}")
        summary["phases"]["delete_followup_get"] = {
            "status": status_after,
            "evidence": str(path_after),
        }
    else:
        print("  DELETE skipped — no recipient_id captured for deletion")
        summary["phases"]["delete"] = {"skipped": True}

    # Persist summary (with redaction since it includes request bodies).
    summary_path = STEP_DIR / "_batch_C_summary.json"
    redacted_summary = {
        "created": [
            {
                "variant": r["variant"],
                "status": r["status"],
                "recipient_id": r["recipient_id"],
                "idem_key": r["idem_key"],
                "evidence": r["evidence"],
            }
            for r in summary["created"]
        ],
        "phases": summary["phases"],
    }
    summary_path.write_text(json.dumps(redacted_summary, indent=2, ensure_ascii=False))
    print(f"\nSummary -> {summary_path}")


if __name__ == "__main__":
    run()
