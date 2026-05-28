"""Probe 6 — Information disclosure sweep (OWASP API3:2023 property-level
authorization + API8:2023 misconfiguration).

Confirms DRIFT-30 (account_details unmasked on recipients) at GET-detail time
AND on list view. Also surveys:
  - GET /v1/users/{id} — does it return SSN / EIN / document numbers unmasked?
  - GET /v1/users (list) — does the list view expose PII fields?
  - Error responses for stack traces / framework versions / file paths.
  - Server / X-Powered-By / X-Amzn-Errortype framework disclosure.

Read-only — does not create any resources.

Run: python3 evidence/work/security/info-disclosure-account-details/probe_disclosure.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers, redact_text  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth  # noqa: E402

# Fields that are sensitive if returned plaintext (not masked) on any read.
SENSITIVE_KEYS = {
    "ssn", "ein", "tax_id", "document_number", "doc_number",
    "account_number", "clabe", "routing_number", "swift_code",
    "wallet_address", "address", "bank_account_number",
    "card_number", "iban",
    "secret", "api_key", "password", "private_key", "mnemonic",
}

# Suggested masking patterns ("****1234", "XXXX1234", "..1234").
MASK_RE = re.compile(r"^\*+|^X+|^\.+|\*{4,}|X{4,}|\.{4,}|^\*\*\*\*")


def is_masked(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    if v == "" or len(v) <= 4:
        return True
    return bool(MASK_RE.search(v))


def find_sensitive(node: Any, path: str = "$") -> List[Dict[str, Any]]:
    """Walk a JSON tree, flag any key whose name is in SENSITIVE_KEYS with a
    plaintext-looking value."""
    out: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        for k, v in node.items():
            sub_path = f"{path}.{k}"
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                if isinstance(v, (dict, list)):
                    # Nested sensitive — recurse but still flag
                    out.append({
                        "path": sub_path,
                        "key": k,
                        "value_repr": json.dumps(v)[:120],
                        "looks_masked": False,
                        "is_nested": True,
                    })
                    out.extend(find_sensitive(v, sub_path))
                else:
                    out.append({
                        "path": sub_path,
                        "key": k,
                        "value_repr": str(v)[:80],
                        "looks_masked": is_masked(v),
                        "is_nested": False,
                    })
            else:
                out.extend(find_sensitive(v, sub_path))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(find_sensitive(item, f"{path}[{i}]"))
    return out


def fetch(token: str, label: str, path: str, params: Dict[str, str] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, params=params or {}, timeout=15.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return {
        "label": label,
        "url": str(resp.request.url),
        "method": "GET",
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "response_headers": {k.lower(): v for k, v in resp.headers.items()},
        "body": redact_body(body) if isinstance(body, dict) else (redact_text(body) if isinstance(body, str) else body),
        "raw_body": body,  # for analysis (not written to disk)
    }


def load_known_ids() -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        d = json.load(open(WORK / "users" / "03-success.json"))
        body = d["response"]["body"]
        if isinstance(body, dict) and body.get("id"):
            out["user_id"] = body["id"]
    except Exception:
        pass
    try:
        d = json.load(open(WORK / "recipients" / "01-success-201-spei.json"))
        body = d["response"]["body"]
        if isinstance(body, dict) and body.get("recipient_id"):
            out["recipient_id_spei"] = body["recipient_id"]
    except Exception:
        pass
    # ACH / SWIFT / USDT for fuller coverage
    for fname, label in [
        ("recipients/26-success-201-ach-iter2.json", "recipient_id_ach"),
        ("recipients/28-success-201-usdt-iter2.json", "recipient_id_usdt"),
        ("recipients/30-success-201-swift-iter2.json", "recipient_id_swift"),
    ]:
        try:
            d = json.load(open(WORK / fname))
            rid = d["response"]["body"].get("recipient_id")
            if rid:
                out[label] = rid
        except Exception:
            pass
    return out


def main() -> None:
    token = auth()
    if not token:
        sys.exit(1)

    ids = load_known_ids()
    print("Known IDs:", ids)

    probes: List[Dict[str, Any]] = []

    # A) GET /v1/users (list view) — does it expose SSN/EIN in list?
    probes.append(fetch(token, "users-list", "/v1/users", {"limit": "5"}))

    # B) GET /v1/users/{id}
    if "user_id" in ids:
        probes.append(fetch(token, "user-detail", f"/v1/users/{ids['user_id']}"))

    # C) GET /v1/recipients?user_id=... (list view)
    if "user_id" in ids:
        probes.append(fetch(token, "recipients-list", "/v1/recipients", {"user_id": ids["user_id"]}))

    # D) GET /v1/recipients/{id} for each variant
    for k, rid in ids.items():
        if k.startswith("recipient_id"):
            probes.append(fetch(token, f"{k}-detail", f"/v1/recipients/{rid}"))

    # E) Trigger several error responses for stack-trace probing
    err_probes = [
        ("err-bad-uuid-user", "GET", "/v1/users/not-a-uuid", None),
        ("err-bad-uuid-recipient", "GET", "/v1/recipients/not-a-uuid", None),
        ("err-massive-limit-users", "GET", "/v1/users", {"limit": "100000"}),
        ("err-bogus-query-banks", "GET", "/v1/banks", {"country_code": "ZZZ"}),
        ("err-unknown-path", "GET", "/v1/this-endpoint-does-not-exist", None),
    ]
    for label, method, path, params in err_probes:
        probes.append(fetch(token, label, path, params))

    # Analyze
    analysis = []
    for p in probes:
        body = p.pop("raw_body", None)  # don't write the raw plaintext sensitive values to disk
        sensitive = []
        if isinstance(body, (dict, list)):
            sensitive = find_sensitive(body)
            # Annotate masked vs plaintext
            unmasked_count = sum(1 for s in sensitive if not s["looks_masked"] and not s["is_nested"])
        else:
            unmasked_count = 0
        # Disclosure clues in headers and body
        body_text_excerpt = ""
        if isinstance(body, str):
            body_text_excerpt = body[:500]
        elif isinstance(body, dict):
            body_text_excerpt = json.dumps(body)[:500]
        disclosure_clues = {
            "framework_hints": [
                k for k in ("server", "x-powered-by", "x-amzn-errortype", "x-amz-apigw-id")
                if k in p.get("response_headers", {})
            ],
            "stack_trace_in_body": any(s in body_text_excerpt for s in ("Traceback", "    at ", "File \"/", ".py\", line", ".js:", "node_modules")),
            "framework_versions": any(s in body_text_excerpt for s in ("Express", "FastAPI", "Django", "Flask", "Lambda", "Pydantic", "ZodError")),
        }
        analysis.append({
            "label": p["label"],
            "url": p["url"],
            "status": p["status"],
            "sensitive_fields_found": sensitive,
            "unmasked_sensitive_field_count": unmasked_count,
            "disclosure_clues": disclosure_clues,
            "response_headers_subset": {k: v for k, v in p["response_headers"].items() if k in ("server", "x-powered-by", "x-amzn-errortype", "x-amzn-requestid", "x-amz-apigw-id", "x-api-version", "content-type")},
        })

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "ids_used": ids,
        "probes": probes,  # redacted body
        "analysis": analysis,
    }
    out = HERE / "01-disclosure-sweep.json"
    out.write_text(json.dumps(summary, indent=2))
    print("Probe 6 output:", out)
    # Compact summary print
    for a in analysis:
        print(f"  {a['label']}: status={a['status']} unmasked_sensitive={a['unmasked_sensitive_field_count']} clues={a['disclosure_clues']['framework_hints']}")


if __name__ == "__main__":
    main()
