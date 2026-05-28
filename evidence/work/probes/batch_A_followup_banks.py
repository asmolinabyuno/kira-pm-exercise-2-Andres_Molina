"""Batch A follow-up — /v1/banks deep dive.

Main run revealed:
  - /v1/banks?country=MX → 400 "Only CO (Colombia) is supported" (real param is `country_code`)
  - /banks?country=MX → 200 but body "error code: 522" (Cloudflare 522 — backend unreachable)
  - /banks no-bearer → 200 "Blocked" (Cloudflare blocked)

Follow-up probes:
  - /v1/banks?country_code=CO (the only supported value)
  - /v1/banks?country_code=co (lowercase)
  - /v1/banks?country_code=COL (alpha-3)
  - /v1/banks?country_code=MX (still 400?)
  - /banks?country_code=CO (no /v1/ prefix — does it also work or is it dead?)
  - /v1/banks no params

Run: python3 evidence/work/probes/batch_A_followup_banks.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth  # noqa: E402

EVIDENCE_DIR = WORK


def capture(family: str, attempt_id: str, request, response, elapsed_ms, outcome, filename=None):
    out_dir = EVIDENCE_DIR / family
    out_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        out = out_dir / f"{filename}.json"
    else:
        existing = sorted(out_dir.glob("*.json"))
        out = out_dir / f"{len(existing) + 1:02d}-{outcome}.json"
    payload = {
        "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
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


def main() -> int:
    print("[Batch A FU] Authenticating...")
    token = auth()
    if not token:
        print("[Batch A FU] AUTH FAILED — aborting.")
        return 2

    headers = {
        "Accept": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }

    probes = [
        ("v1-cc-CO",                f"{BASE_URL.rstrip('/')}/v1/banks", {"country_code": "CO"}),
        ("v1-cc-co-lower",          f"{BASE_URL.rstrip('/')}/v1/banks", {"country_code": "co"}),
        ("v1-cc-COL-alpha3",        f"{BASE_URL.rstrip('/')}/v1/banks", {"country_code": "COL"}),
        ("v1-cc-MX",                f"{BASE_URL.rstrip('/')}/v1/banks", {"country_code": "MX"}),
        ("v1-cc-Colombia-name",     f"{BASE_URL.rstrip('/')}/v1/banks", {"country_code": "Colombia"}),
        ("v1-no-params",            f"{BASE_URL.rstrip('/')}/v1/banks", None),
        ("nov1-cc-CO",              f"{BASE_URL.rstrip('/')}/banks", {"country_code": "CO"}),
    ]

    results = []
    for label, url, params in probes:
        attempt_id = str(uuid.uuid4())
        t0 = time.perf_counter_ns()
        resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        outcome = f"success-{label}" if 200 <= resp.status_code < 300 else f"fail-{resp.status_code}-{label}"
        path = capture(
            "banks",
            attempt_id,
            request={
                "method": "GET",
                "url": url + (("?" + "&".join(f"{k}={v}" for k, v in params.items())) if params else ""),
                "headers": headers,
                "body": None,
            },
            response={
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": body,
            },
            elapsed_ms=elapsed_ms,
            outcome=outcome,
        )
        # Summary line — count items in body.data if present
        items = None
        if isinstance(body, dict):
            if isinstance(body.get("data"), list):
                items = len(body["data"])
            elif isinstance(body.get("count"), int):
                items = body["count"]
        elif isinstance(body, list):
            items = len(body)
        results.append({
            "label": label,
            "url": url,
            "params": params,
            "status": resp.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "items": items,
            "body_top": list(body.keys()) if isinstance(body, dict) else (type(body).__name__),
            "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        })
        print(f"  [{label}] {resp.status_code} in {round(elapsed_ms, 0)}ms → items={items}")

    out_summary = EVIDENCE_DIR / "probes" / "batch_A_banks_followup.json"
    out_summary.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[Batch A FU] Summary at {out_summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
