"""Kira sandbox integration runner. Phase 2 — start with /auth.

Run: ``python3 evidence/work/run_flow.py``

Reads credentials from ``.env`` at the project root. Captures every HTTP call
under ``evidence/work/{step}/{NN}-{outcome}.json`` with secrets redacted via
``_redact.py``.

Hard rules (do not violate):
- Never write raw secrets to disk; everything goes through ``redact_*``.
- Token returned by :func:`auth` lives in memory only; it is **never** persisted.
- All inputs come from ``.env``; no hardcoded credentials.
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

# Make _redact importable regardless of cwd.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _redact import redact_body, redact_headers  # noqa: E402

ROOT = HERE.parents[1]  # project root: .../Exercise 2 - API Integration
load_dotenv(ROOT / ".env")

BASE_URL = os.environ["KIRA_API_BASE_URL"].rstrip("/")
CLIENT_ID = os.environ["KIRA_CLIENT_ID"]
PASSWORD = os.environ["KIRA_COGNITO_SECRET"]  # docs call this field "password"
API_KEY = os.environ["KIRA_API_KEY"]

EVIDENCE_DIR = HERE  # evidence/work


def capture(
    step: str,
    attempt_id: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    elapsed_ms: float,
    outcome: str,
    filename: Optional[str] = None,
) -> Path:
    """Write a single request/response evidence file.

    Filename pattern: ``{NN}-{outcome}.json`` inside ``evidence/work/{step}/``.

    If *filename* is provided (without ``.json`` extension), it overrides the
    auto-generated ``{NN}-{outcome}`` stem. Used for fixed-name probe files
    (e.g., ``00-drift-probe-A``).
    """
    out_dir = EVIDENCE_DIR / step
    out_dir.mkdir(parents=True, exist_ok=True)
    if filename is not None:
        out = out_dir / f"{filename}.json"
    else:
        existing = sorted(out_dir.glob("*.json"))
        nn = f"{len(existing) + 1:02d}"
        out = out_dir / f"{nn}-{outcome}.json"

    req_body = request.get("body")
    resp_body = response.get("body")

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": attempt_id,
        "elapsed_ms": round(elapsed_ms, 2),
        "outcome": outcome,
        "request": {
            "method": request["method"],
            "url": request["url"],
            "headers": redact_headers(request.get("headers", {}) or {}),
            "body": redact_body(req_body) if req_body is not None else None,
        },
        "response": {
            "status": response["status"],
            "headers": redact_headers(response.get("headers", {}) or {}),
            "body": redact_body(resp_body),
        },
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def auth() -> Optional[str]:
    """Call ``POST /auth``. Returns the bearer token (in-memory only)."""
    attempt_id = str(uuid.uuid4())
    url = f"{BASE_URL}/auth"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }
    body = {"client_id": CLIENT_ID, "password": PASSWORD}

    t0 = time.perf_counter_ns()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    outcome = "success" if 200 <= resp.status_code < 300 else f"fail-{resp.status_code}"
    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    capture(
        "auth",
        attempt_id,
        request={"method": "POST", "url": url, "headers": headers, "body": body},
        response={
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp_body,
        },
        elapsed_ms=elapsed_ms,
        outcome=outcome,
    )

    if outcome.startswith("success") and isinstance(resp_body, dict):
        # Try documented shape first, then plausible alternates. Never log the value.
        data = resp_body.get("data") if isinstance(resp_body.get("data"), dict) else {}
        token = (
            data.get("access_token")
            or resp_body.get("access_token")
            or resp_body.get("token")
        )
        return token
    return None


def create_user(
    token: str,
    body: Dict[str, Any],
    *,
    base_override: Optional[str] = None,
    filename: Optional[str] = None,
) -> Tuple[int, Union[Dict[str, Any], str], Path]:
    """Call ``POST /v1/users``.

    Per ``evidence/work/flow-design.md`` § 3.2.1 the docs declare the request
    body schema and that ``idempotency-key`` is a required header.

    Parameters
    ----------
    token:
        Bearer JWT from :func:`auth`. Passed in (never re-fetched here) so
        callers can chain multiple ``create_user`` calls without burning new
        ``/auth`` requests.
    body:
        Request body — the caller is responsible for the shape. Driver
        ``main()`` below iterates on this when error responses point at fixes.
    base_override:
        If provided, replaces ``BASE_URL`` (loaded from ``.env``). Used by the
        DRIFT-2 probe to test the legacy ``/sandbox`` prefix without editing
        ``.env``.
    filename:
        Optional fixed filename stem for the evidence file (no ``.json``).
        When omitted, ``capture()`` auto-numbers ``{NN}-{outcome}``.

    Returns
    -------
    (status, response_body, evidence_path)
        ``status`` is the HTTP status code. ``response_body`` is the parsed
        JSON (dict) or raw text (str). ``evidence_path`` is where the
        request+response capture was written. **The returned body has not
        been redacted** — callers should not write it to disk directly; the
        capture file already contains the redacted form.
    """
    attempt_id = str(uuid.uuid4())
    base = (base_override or BASE_URL).rstrip("/")
    url = f"{base}/v1/users"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }

    t0 = time.perf_counter_ns()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6

    try:
        resp_body: Any = resp.json()
    except Exception:
        resp_body = resp.text

    if 200 <= resp.status_code < 300:
        outcome = "success"
    elif resp.status_code == 400:
        outcome = "fail-400-validation"
    else:
        outcome = f"fail-{resp.status_code}"

    path = capture(
        "users",
        attempt_id,
        request={"method": "POST", "url": url, "headers": headers, "body": body},
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


# ---------------------------------------------------------------------------
# Fake-payload helpers — sandbox-only test data.
#
# Hard rules:
# - NEVER use real PII (real names, real SSNs/CURPs/RFCs, real document images).
# - All identifiers are random UUIDs or obviously fake constants.
# - Document files are a 1×1 transparent PNG, base64-encoded — not a real ID.
# ---------------------------------------------------------------------------

# 1×1 transparent PNG, base64. ~70 bytes — useful as a "this is a file" placeholder
# without resembling any real document.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
TINY_PNG_DATA_URI = f"data:image/png;base64,{_TINY_PNG_B64}"


def fake_individual_payload(*, country_alpha3: str = "USA") -> Dict[str, Any]:
    """Build a minimal USA-individual payload per flow-design.md § 3.2.1.

    The auto-verify schema is the most documented flavor. We use it as the
    first iteration because the docs explicitly publish its required fields.
    """
    epoch = int(time.time())
    return {
        "type": "individual",
        "first_name": "Test",
        "last_name": "User",
        "email": f"test+phase2-{epoch}-{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+12025550100",
        "birth_date": "1990-01-15",
        "nationality": country_alpha3,
        "address_street": "123 Main St",
        "address_city": "San Francisco",
        "address_state": "CA",
        "address_zip_code": "94105",
        "address_country": country_alpha3,
        "identifying_information": [
            {
                "type": "ssn",
                "issuing_country": country_alpha3,
                "number": "000-00-0000",  # obviously fake SSN
            },
            {
                "type": "drivers_license",
                "issuing_country": country_alpha3,
                "number": "FAKE-DL-000000",
                "documents": [
                    {"type": "front", "file": TINY_PNG_DATA_URI},
                    {"type": "back", "file": TINY_PNG_DATA_URI},
                ],
            },
        ],
    }


def fake_business_payload(*, country_alpha3: str = "USA") -> Dict[str, Any]:
    """Build a minimal USA-business ACT-product payload per flow-design.md § 3.2.1.

    Lighter onboarding shape (no photo IDs at creation) — `ein` + `associated_persons`.
    """
    epoch = int(time.time())
    return {
        "type": "business",
        "business_legal_name": f"Test Corp {epoch}",
        "email": f"ops+phase2-{epoch}-{uuid.uuid4().hex[:6]}@example.com",
        "business_type": "corporation",
        "formation_date": "2018-03-15",
        "formation_state": "DE",
        "address_country": country_alpha3,
        "ein": "00-0000000",  # obviously fake EIN
        "associated_persons": [
            {
                "first_name": "Test",
                "last_name": "Signer",
                "ssn": "000-00-0000",
                "birth_date": "1975-08-22",
                "nationality": country_alpha3,
                "is_signer": True,
                "has_ownership": True,
                "ownership_percentage": 100,
            }
        ],
    }


if __name__ == "__main__":
    token = auth()
    print(f"AUTH: {'OK' if token else 'FAILED'} — evidence in evidence/work/auth/")
