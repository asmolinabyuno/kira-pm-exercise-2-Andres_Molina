"""Batch B — User Lifecycle & Verification probe.

This is the CRITICAL PATH unblocker. DRIFT-3 said ``verification_triggered: false``
despite docs claiming auto-trigger on full required fields. Until we know what
actually triggers KYB, Batches D (Virtual Accounts) and F (Payouts) are blocked.

Endpoints probed (in dependency order):
  B1  GET  /v1/users/{userId}                 — read current state, missing_fields
  B2  PUT  /v1/users/{userId}                 — submit missing fields (DRIFT-3 follow-up)
  B3  POST /v1/users/{userId}/verifications   — legacy explicit-trigger
  B4  POST /v1/verification/send              — OTP endpoint (GAP-23) — undocumented path
  B5  Mass-assignment probe — POST /v1/users with verification_status: VERIFIED
  B6  Maximal payload create — does *every documented field* auto-trigger?

Rules:
- httpx, timeout=30, redact-on-write via _redact.
- NEVER write secrets to disk — `capture` is the only file-writing path.
- Fake data only (UUIDs, tiny PNG, fake SSN/EIN).
- Max 5 iterations per endpoint.
- Per-call evidence under evidence/work/{users|verification}/{NN}-{outcome}.json.

Run: ``python3 evidence/work/probes/batch_B.py``
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

HERE = Path(__file__).resolve().parent
WORK = HERE.parent  # evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

import httpx  # noqa: E402

# Re-use the shared helpers (do NOT modify run_flow.py — shared with other agents).
from run_flow import (  # noqa: E402
    API_KEY,
    BASE_URL,
    auth,
    capture,
    fake_business_payload,
    fake_individual_payload,
    TINY_PNG_DATA_URI,
)

# ---------------------------------------------------------------------------
# Generic HTTP wrappers — write evidence via the shared `capture()` helper so
# the redaction rules stay consistent with other batches.
# ---------------------------------------------------------------------------


def _do_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    step: str,
    outcome_prefix: str = "",
    filename: Optional[str] = None,
) -> Tuple[int, Any, Path]:
    """Send a single HTTP call and persist the redacted capture.

    Returns ``(status_code, response_body, evidence_path)``. The response body
    is the parsed JSON (dict / list) or raw text — caller must not write it to
    disk directly (use ``capture()`` only).
    """
    attempt_id = str(uuid.uuid4())
    t0 = time.perf_counter_ns()
    try:
        resp = httpx.request(method, url, headers=headers, json=body, timeout=30.0)
    except Exception as exc:
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        path = capture(
            step,
            attempt_id,
            request={"method": method, "url": url, "headers": headers, "body": body},
            response={"status": -1, "headers": {}, "body": f"EXCEPTION: {type(exc).__name__}: {exc}"},
            elapsed_ms=elapsed_ms,
            outcome=f"{outcome_prefix}exception",
            filename=filename,
        )
        return -1, None, path
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    if 200 <= resp.status_code < 300:
        outcome = f"{outcome_prefix}success"
    elif resp.status_code == 400:
        outcome = f"{outcome_prefix}fail-400-validation"
    elif resp.status_code == 404:
        outcome = f"{outcome_prefix}fail-404-notfound"
    elif resp.status_code == 409:
        outcome = f"{outcome_prefix}fail-409-conflict"
    else:
        outcome = f"{outcome_prefix}fail-{resp.status_code}"

    path = capture(
        step,
        attempt_id,
        request={"method": method, "url": url, "headers": headers, "body": body},
        response={
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        filename=filename,
    )
    return resp.status_code, resp_body, path


def _base_headers(token: str, idem: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _short(body: Any, limit: int = 320) -> str:
    """One-line summary for stdout — never includes secrets (capture redacts on disk)."""
    if isinstance(body, dict):
        return json.dumps({k: ("…" if isinstance(v, (dict, list)) else v) for k, v in list(body.items())[:6]})[:limit]
    return str(body)[:limit]


# ---------------------------------------------------------------------------
# B0 — Pre-flight: find or create the test user we'll drive through verification.
# ---------------------------------------------------------------------------

EXISTING_USER_FROM_DRIFT3 = "ae80515c-2d59-4e02-9678-0bcfd6e9a188"


def b0_pick_user(token: str) -> Optional[str]:
    """Probe GET /v1/users/{id} against the user from DRIFT-3.

    If that user still exists, reuse it. If the API returns 404 (sandbox flushed)
    or anything else, create a fresh one via the shared ``fake_business_payload``.

    Returns the user_id we will drive through verification.
    """
    url = f"{BASE_URL}/v1/users/{EXISTING_USER_FROM_DRIFT3}"
    status, body, path = _do_request(
        "GET", url, _base_headers(token), None, step="users", filename="10-batchB-get-existing"
    )
    print(f"[B0] GET existing user → status={status} evidence={path.relative_to(WORK.parent)}")
    if status == 200 and isinstance(body, dict):
        return EXISTING_USER_FROM_DRIFT3

    # Fallback: create a fresh user.
    print("[B0] existing user not reachable — creating fresh business user")
    idem = str(uuid.uuid4())
    create_url = f"{BASE_URL}/v1/users"
    create_body = fake_business_payload(country_alpha3="USA")
    status, body, path = _do_request(
        "POST",
        create_url,
        _base_headers(token, idem),
        create_body,
        step="users",
        filename="11-batchB-create-fallback",
    )
    if status == 201 and isinstance(body, dict):
        return body.get("id")
    return None


# ---------------------------------------------------------------------------
# B1 — GET /v1/users/{userId} — observe current verification_status + missing_fields.
# ---------------------------------------------------------------------------


def b1_get_user(token: str, user_id: str, label: str) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/v1/users/{user_id}"
    status, body, path = _do_request(
        "GET",
        url,
        _base_headers(token),
        None,
        step="users",
        filename=f"12-batchB-get-{label}",
    )
    if isinstance(body, dict):
        vt = body.get("verification_triggered")
        vs = body.get("verification_status")
        st = body.get("status")
        mf = body.get("missing_fields") or {}
        mf_count = sum(len(v) for v in mf.values() if isinstance(v, list))
        print(
            f"[B1:{label}] status={status} | "
            f"http_status={st!r} verification_status={vs!r} verification_triggered={vt!r} "
            f"missing_fields_total={mf_count} evidence={path.relative_to(WORK.parent)}"
        )
        return body
    print(f"[B1:{label}] status={status} body_type={type(body).__name__} evidence={path.relative_to(WORK.parent)}")
    return None


# ---------------------------------------------------------------------------
# B2 — PUT /v1/users/{userId} — submit the missing_fields per DRIFT-3.
# ---------------------------------------------------------------------------


# Per DRIFT-3, the ACT-product `missing_fields` list was:
#   formation_country, address_street, address_city, address_state,
#   address_zip_code, associated_persons:email, associated_persons:document_number,
#   account_purpose
# We fill them with fake-but-shape-correct values.
def b2_put_user_complete_act_missing(token: str, user_id: str) -> Tuple[int, Any, Path]:
    url = f"{BASE_URL}/v1/users/{user_id}"
    body: Dict[str, Any] = {
        "formation_country": "USA",
        "address_street": "123 Fake Ave",
        "address_city": "Wilmington",
        "address_state": "DE",
        "address_zip_code": "19801",
        # Business-only canonical enum value (the original guess
        # `operating_business_payments` is not accepted — DRIFT-B5)
        "account_purpose": "ecommerce_retail_payments",
        "associated_persons": [
            {
                # The DRIFT-3 user had a single associated person — patch their
                # email + document_number, leave existing keys alone.
                "first_name": "Test",
                "last_name": "Signer",
                "email": f"signer+batchB-{int(time.time())}@example.com",
                "document_number": "FAKE-DOC-00000001",
                "ssn": "000-00-0000",
                "birth_date": "1975-08-22",
                "nationality": "USA",
                "is_signer": True,
                "has_ownership": True,
                "ownership_percentage": 100,
            }
        ],
    }
    return _do_request(
        "PUT",
        url,
        _base_headers(token),
        body,
        step="users",
        filename="13-batchB-put-complete-act",
    )


def b2_put_user_metadata_only(token: str, user_id: str) -> Tuple[int, Any, Path]:
    """Non-sensitive update — `metadata` only. Expect requires_reverification: false."""
    url = f"{BASE_URL}/v1/users/{user_id}"
    body = {"metadata": {"batch": "B", "probe": "non-sensitive-update", "ts": str(int(time.time()))}}
    return _do_request(
        "PUT",
        url,
        _base_headers(token),
        body,
        step="users",
        filename="14-batchB-put-metadata-only",
    )


def b2_put_user_empty(token: str, user_id: str) -> Tuple[int, Any, Path]:
    """Empty body — expect 400 with structured details."""
    url = f"{BASE_URL}/v1/users/{user_id}"
    return _do_request(
        "PUT",
        url,
        _base_headers(token),
        {},
        step="users",
        filename="15-batchB-put-empty",
    )


# ---------------------------------------------------------------------------
# B3 — POST /v1/users/{userId}/verifications — legacy explicit trigger.
# ---------------------------------------------------------------------------


def b3_post_verification(
    token: str,
    user_id: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    idem: Optional[str] = None,
    label: str = "happy",
) -> Tuple[int, Any, Path]:
    url = f"{BASE_URL}/v1/users/{user_id}/verifications"
    if body is None:
        body = {
            "type": "embedded-link",
            "redirect_uri": "https://example.com/done",
        }
    return _do_request(
        "POST",
        url,
        _base_headers(token, idem or str(uuid.uuid4())),
        body,
        step="verification",
        filename=f"01-post-verifications-{label}",
    )


# ---------------------------------------------------------------------------
# B4 — POST /v1/verification/send — OTP endpoint (GAP-23, undocumented path).
# ---------------------------------------------------------------------------


def b4_otp_send_probes(token: str, user_id: str) -> List[Tuple[str, int, Path]]:
    """Try several plausible OTP-send paths and bodies. GAP-23 — no reference page exists."""
    paths_to_try = [
        ("/v1/verification/send", {"user_id": user_id}),
        ("/verification/send", {"user_id": user_id}),
        ("/v1/users/{id}/verification/send", {"user_id": user_id}),
        ("/v1/users/{id}/verifications/send", {}),
    ]
    out: List[Tuple[str, int, Path]] = []
    for i, (raw_path, raw_body) in enumerate(paths_to_try, start=1):
        url = f"{BASE_URL}{raw_path.replace('{id}', user_id)}"
        status, body, path = _do_request(
            "POST",
            url,
            _base_headers(token, str(uuid.uuid4())),
            raw_body,
            step="verification",
            filename=f"10-otp-send-probe-{i:02d}-{raw_path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
        )
        print(f"[B4] {raw_path} → status={status} body={_short(body)} evidence={path.relative_to(WORK.parent)}")
        out.append((raw_path, status, path))
    return out


# ---------------------------------------------------------------------------
# B5 — Mass-assignment probe on POST /v1/users.
# Can an integrator inject `verification_status: "VERIFIED"` at create time?
# ---------------------------------------------------------------------------


def b5_mass_assignment_create(token: str) -> Tuple[int, Any, Path]:
    body = fake_business_payload(country_alpha3="USA")
    # Inject fields the user should NOT be able to set themselves.
    body["verification_status"] = "verified"
    body["status"] = "VERIFIED"
    body["verification_triggered"] = True
    body["eligible_products"] = []
    body["requires_reverification"] = False
    idem = str(uuid.uuid4())
    return _do_request(
        "POST",
        f"{BASE_URL}/v1/users",
        _base_headers(token, idem),
        body,
        step="users",
        filename="20-batchB-mass-assignment-probe",
    )


# ---------------------------------------------------------------------------
# B6 — Maximal-payload create — does *everything documented* trigger?
# Uses an `individual` body with full identifying_information per § 3.2.1.
# ---------------------------------------------------------------------------


def b6_maximal_individual_create(token: str) -> Tuple[int, Any, Path]:
    body = fake_individual_payload(country_alpha3="USA")
    # Add several "documented but not in fake_individual_payload" fields per
    # the API Reference page enumeration we have in api-reference-coverage.md.
    # Individual `account_purpose` enum (per DRIFT-B5, 14 values) — use canonical:
    body["account_purpose"] = "personal_or_living_expenses"
    body["source_of_funds"] = "salary"
    body["employment_status"] = "employed"
    body["current_employer"] = "Test Corp"
    body["gender"] = "other"
    body["middle_name"] = "Q"
    idem = str(uuid.uuid4())
    return _do_request(
        "POST",
        f"{BASE_URL}/v1/users",
        _base_headers(token, idem),
        body,
        step="users",
        filename="21-batchB-maximal-individual",
    )


def b6b_maximal_business_create(token: str) -> Tuple[int, Any, Path]:
    """Maximal business payload — every ACT-missing field per DRIFT-3 + extras."""
    body = fake_business_payload(country_alpha3="USA")
    body["formation_country"] = "USA"
    body["address_street"] = "123 Fake Ave"
    body["address_city"] = "Wilmington"
    body["address_state"] = "DE"
    body["address_zip_code"] = "19801"
    body["doing_business_as"] = f"Test DBA {int(time.time())}"
    body["business_industry"] = "technology"
    body["phone"] = "+12025550100"
    # Business `account_purpose` enum (per DRIFT-B5, 18 values incl. business-only):
    body["account_purpose"] = "ecommerce_retail_payments"
    body["document_number"] = "FAKE-DOC-00000002"
    # Patch the associated person with email + document_number.
    body["associated_persons"][0]["email"] = f"signer+max-{int(time.time())}@example.com"
    body["associated_persons"][0]["document_number"] = "FAKE-DOC-00000003"
    idem = str(uuid.uuid4())
    return _do_request(
        "POST",
        f"{BASE_URL}/v1/users",
        _base_headers(token, idem),
        body,
        step="users",
        filename="22-batchB-maximal-business-act",
    )


def b8_zero_missing_individual(token: str) -> Tuple[int, Any, Path]:
    """Maximal individual + `occupation` — the last missing field per B6.a.

    DRIFT-3 follow-up: does ``verification_triggered`` flip to ``true`` when
    ``missing_fields`` is empty?
    """
    body = fake_individual_payload(country_alpha3="USA")
    body["account_purpose"] = "personal_or_living_expenses"
    body["source_of_funds"] = "salary"
    body["employment_status"] = "employed"
    body["current_employer"] = "Test Corp"
    body["occupation"] = "software_engineer"
    body["gender"] = "other"
    body["middle_name"] = "Q"
    idem = str(uuid.uuid4())
    return _do_request(
        "POST",
        f"{BASE_URL}/v1/users",
        _base_headers(token, idem),
        body,
        step="users",
        filename="23-batchB-zero-missing-individual",
    )


def b8b_zero_missing_business(token: str) -> Tuple[int, Any, Path]:
    """Maximal business with ``business_industry`` as an ARRAY (per B6.b 400).

    Goal: empty ``missing_fields`` + ``verification_triggered: true`` on a business.
    """
    body = fake_business_payload(country_alpha3="USA")
    body["formation_country"] = "USA"
    body["address_street"] = "123 Fake Ave"
    body["address_city"] = "Wilmington"
    body["address_state"] = "DE"
    body["address_zip_code"] = "19801"
    body["doing_business_as"] = f"Test DBA {int(time.time())}"
    # NAICS-coded enum (per B8.b 400 reveal — 90+ values); use IT
    body["business_industry"] = ["data_processing_hosting_related_services"]
    body["phone"] = "+12025550100"
    body["account_purpose"] = "ecommerce_retail_payments"
    body["document_number"] = "FAKE-DOC-00000004"
    body["associated_persons"][0]["email"] = f"signer+zm-{int(time.time())}@example.com"
    body["associated_persons"][0]["document_number"] = "FAKE-DOC-00000005"
    idem = str(uuid.uuid4())
    return _do_request(
        "POST",
        f"{BASE_URL}/v1/users",
        _base_headers(token, idem),
        body,
        step="users",
        filename="24-batchB-zero-missing-business",
    )


def b7_otp_send_with_correct_body(token: str, user_id: str, user_email: Optional[str]) -> List[Tuple[str, int, Path]]:
    """Re-probe POST /verification/send with the body shape the 400 revealed.

    The earlier 400 said: "is Either client_uuid or email must be provided".
    Probe both shapes; capture the success/error envelope.
    """
    results: List[Tuple[str, int, Path]] = []

    # Try client_uuid = our user_id
    body1 = {"client_uuid": user_id}
    status1, b1, p1 = _do_request(
        "POST",
        f"{BASE_URL}/verification/send",
        _base_headers(token, str(uuid.uuid4())),
        body1,
        step="verification",
        filename="11-otp-send-client_uuid",
    )
    print(f"[B7] /verification/send client_uuid → status={status1} body={_short(b1)} evidence={p1.relative_to(WORK.parent)}")
    results.append(("/verification/send (client_uuid)", status1, p1))

    # Try email (if known)
    if user_email:
        body2 = {"email": user_email}
        status2, b2, p2 = _do_request(
            "POST",
            f"{BASE_URL}/verification/send",
            _base_headers(token, str(uuid.uuid4())),
            body2,
            step="verification",
            filename="12-otp-send-email",
        )
        print(f"[B7] /verification/send email → status={status2} body={_short(b2)} evidence={p2.relative_to(WORK.parent)}")
        results.append(("/verification/send (email)", status2, p2))

    return results


# ---------------------------------------------------------------------------
# Mutation probes — idempotency / enum / missing field on B3 (verifications).
# ---------------------------------------------------------------------------


def m1_idempotency_replay_same(token: str, user_id: str) -> Tuple[Path, Path]:
    """Same idem key + same body twice → expect 2xx both times (cached replay)."""
    idem = str(uuid.uuid4())
    body = {"type": "embedded-link", "redirect_uri": "https://example.com/done-idem"}
    _, _, p1 = b3_post_verification(token, user_id, body=body, idem=idem, label=f"idem-replay-same-1")
    _, _, p2 = b3_post_verification(token, user_id, body=body, idem=idem, label=f"idem-replay-same-2")
    return p1, p2


def m2_idempotency_replay_diff(token: str, user_id: str) -> Tuple[Path, Path]:
    """Same idem key + different body → expect 409 idempotency_conflict (Shape A or B)."""
    idem = str(uuid.uuid4())
    body1 = {"type": "embedded-link", "redirect_uri": "https://example.com/A"}
    body2 = {"type": "embedded-link", "redirect_uri": "https://example.com/B-different"}
    _, _, p1 = b3_post_verification(token, user_id, body=body1, idem=idem, label=f"idem-diff-1")
    _, _, p2 = b3_post_verification(token, user_id, body=body2, idem=idem, label=f"idem-diff-2")
    return p1, p2


def m3_missing_required(token: str, user_id: str) -> Path:
    """Empty body → does the error envelope tell you which field is missing?"""
    _, _, p = b3_post_verification(token, user_id, body={}, idem=str(uuid.uuid4()), label="missing-required")
    return p


def m4_bad_enum(token: str, user_id: str) -> Path:
    """Unknown `type` enum value → does the response surface allowed_values?"""
    body = {"type": "NONEXISTENT", "redirect_uri": "https://example.com/done"}
    _, _, p = b3_post_verification(token, user_id, body=body, idem=str(uuid.uuid4()), label="bad-enum")
    return p


def m5_omit_idempotency_key(token: str, user_id: str) -> Path:
    """Omit Idempotency-Key entirely → expect 400 (idempotency.md says required)."""
    url = f"{BASE_URL}/v1/users/{user_id}/verifications"
    headers = _base_headers(token)  # no idem
    body = {"type": "embedded-link", "redirect_uri": "https://example.com/done"}
    _, _, p = _do_request(
        "POST",
        url,
        headers,
        body,
        step="verification",
        filename="02-post-verifications-omit-idem",
    )
    return p


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def main() -> int:
    print("Batch B — User Lifecycle & Verification")
    print(f"  BASE_URL={BASE_URL}")
    print("  Authing…")
    token = auth()
    if not token:
        print("AUTH FAILED — aborting", file=sys.stderr)
        return 2
    print("  AUTH OK")

    summary: Dict[str, Any] = {"steps": []}

    # B0
    user_id = b0_pick_user(token)
    if not user_id:
        print("FATAL — could not obtain test user_id")
        return 3
    print(f"  test user_id={user_id}")

    # B1.a — baseline read
    initial = b1_get_user(token, user_id, label="initial")
    initial_status = initial.get("status") if isinstance(initial, dict) else None
    initial_vt = initial.get("verification_triggered") if isinstance(initial, dict) else None
    summary["steps"].append(
        {"step": "B1.a-get-initial", "status": initial_status, "verification_triggered": initial_vt}
    )

    # B2.a — non-sensitive update (metadata)
    status, body, path = b2_put_user_metadata_only(token, user_id)
    print(f"[B2.a] PUT metadata-only → status={status} body={_short(body)} evidence={path.relative_to(WORK.parent)}")
    summary["steps"].append({"step": "B2.a-put-metadata", "status": status})

    # B2.b — submit missing ACT fields per DRIFT-3
    status, body, path = b2_put_user_complete_act_missing(token, user_id)
    print(f"[B2.b] PUT complete-ACT → status={status} body={_short(body)} evidence={path.relative_to(WORK.parent)}")
    summary["steps"].append({"step": "B2.b-put-complete-act", "status": status})

    # B1.b — read again to see if verification_triggered flipped
    after = b1_get_user(token, user_id, label="after-put-complete")
    after_vt = after.get("verification_triggered") if isinstance(after, dict) else None
    after_status = after.get("status") if isinstance(after, dict) else None
    summary["steps"].append(
        {"step": "B1.b-get-after-put", "status": after_status, "verification_triggered": after_vt}
    )

    # B2.c — empty body PUT (validation probe)
    status, body, path = b2_put_user_empty(token, user_id)
    print(f"[B2.c] PUT empty → status={status} body={_short(body)} evidence={path.relative_to(WORK.parent)}")
    summary["steps"].append({"step": "B2.c-put-empty", "status": status})

    # B3 — legacy verifications endpoint
    status, body, path = b3_post_verification(token, user_id)
    print(f"[B3] POST verifications → status={status} body={_short(body)} evidence={path.relative_to(WORK.parent)}")
    summary["steps"].append({"step": "B3-post-verifications", "status": status})

    # B3 mutations — idempotency, enum, missing-required, omit-idem
    m5_omit_idempotency_key(token, user_id)
    m3_missing_required(token, user_id)
    m4_bad_enum(token, user_id)
    m1_idempotency_replay_same(token, user_id)
    m2_idempotency_replay_diff(token, user_id)

    # B1.c — final state read
    final = b1_get_user(token, user_id, label="final")
    final_vt = final.get("verification_triggered") if isinstance(final, dict) else None
    final_status = final.get("status") if isinstance(final, dict) else None
    summary["steps"].append(
        {"step": "B1.c-get-final", "status": final_status, "verification_triggered": final_vt}
    )

    # B4 — OTP-send endpoint guessing (GAP-23)
    b4_otp_send_probes(token, user_id)

    # B7 — Re-probe OTP send with correct body discovered from B4's 400 reveal
    user_email_for_otp = initial.get("email") if isinstance(initial, dict) else None
    b7_otp_send_with_correct_body(token, user_id, user_email_for_otp)

    # B5 — mass-assignment probe (fresh user)
    status, body, path = b5_mass_assignment_create(token)
    if isinstance(body, dict):
        ma_vt = body.get("verification_triggered")
        ma_vs = body.get("verification_status")
        ma_st = body.get("status")
        print(
            f"[B5] mass-assignment → status={status} "
            f"status={ma_st!r} verification_status={ma_vs!r} verification_triggered={ma_vt!r} "
            f"evidence={path.relative_to(WORK.parent)}"
        )
        summary["steps"].append(
            {
                "step": "B5-mass-assignment",
                "http_status": status,
                "user_status": ma_st,
                "user_verification_status": ma_vs,
                "verification_triggered": ma_vt,
            }
        )
    else:
        print(f"[B5] mass-assignment → status={status} body_type={type(body).__name__}")

    # B6 — maximal individual + business creates
    status_i, body_i, path_i = b6_maximal_individual_create(token)
    if isinstance(body_i, dict):
        ind_vt = body_i.get("verification_triggered")
        ind_mf = body_i.get("missing_fields") or {}
        ind_mf_count = sum(len(v) for v in ind_mf.values() if isinstance(v, list))
        print(
            f"[B6.a] maximal individual → status={status_i} verification_triggered={ind_vt!r} "
            f"missing_fields_total={ind_mf_count} evidence={path_i.relative_to(WORK.parent)}"
        )
        summary["steps"].append(
            {
                "step": "B6.a-maximal-individual",
                "http_status": status_i,
                "verification_triggered": ind_vt,
                "missing_fields_total": ind_mf_count,
            }
        )

    status_b, body_b, path_b = b6b_maximal_business_create(token)
    if isinstance(body_b, dict):
        biz_vt = body_b.get("verification_triggered")
        biz_mf = body_b.get("missing_fields") or {}
        biz_mf_count = sum(len(v) for v in biz_mf.values() if isinstance(v, list))
        print(
            f"[B6.b] maximal business → status={status_b} verification_triggered={biz_vt!r} "
            f"missing_fields_total={biz_mf_count} evidence={path_b.relative_to(WORK.parent)}"
        )
        summary["steps"].append(
            {
                "step": "B6.b-maximal-business",
                "http_status": status_b,
                "verification_triggered": biz_vt,
                "missing_fields_total": biz_mf_count,
            }
        )

    # B8 — Zero-missing iteration. Goal: prove the trigger gate.
    status_zi, body_zi, path_zi = b8_zero_missing_individual(token)
    if isinstance(body_zi, dict):
        zi_vt = body_zi.get("verification_triggered")
        zi_status = body_zi.get("status")
        zi_vs = body_zi.get("verification_status")
        zi_mf = body_zi.get("missing_fields") or {}
        zi_mf_count = sum(len(v) for v in zi_mf.values() if isinstance(v, list))
        print(
            f"[B8.a] zero-missing individual → status={status_zi} "
            f"http_status={zi_status!r} verification_status={zi_vs!r} "
            f"verification_triggered={zi_vt!r} missing_fields_total={zi_mf_count} "
            f"evidence={path_zi.relative_to(WORK.parent)}"
        )
        summary["steps"].append(
            {
                "step": "B8.a-zero-missing-individual",
                "http_status": status_zi,
                "user_status": zi_status,
                "user_verification_status": zi_vs,
                "verification_triggered": zi_vt,
                "missing_fields_total": zi_mf_count,
            }
        )

    status_zb, body_zb, path_zb = b8b_zero_missing_business(token)
    if isinstance(body_zb, dict):
        zb_vt = body_zb.get("verification_triggered")
        zb_status = body_zb.get("status")
        zb_vs = body_zb.get("verification_status")
        zb_mf = body_zb.get("missing_fields") or {}
        zb_mf_count = sum(len(v) for v in zb_mf.values() if isinstance(v, list))
        print(
            f"[B8.b] zero-missing business → status={status_zb} "
            f"http_status={zb_status!r} verification_status={zb_vs!r} "
            f"verification_triggered={zb_vt!r} missing_fields_total={zb_mf_count} "
            f"evidence={path_zb.relative_to(WORK.parent)}"
        )
        summary["steps"].append(
            {
                "step": "B8.b-zero-missing-business",
                "http_status": status_zb,
                "user_status": zb_status,
                "user_verification_status": zb_vs,
                "verification_triggered": zb_vt,
                "missing_fields_total": zb_mf_count,
            }
        )

    print("\n========== BATCH B SUMMARY ==========")
    print(json.dumps(summary, indent=2))
    print("=====================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
