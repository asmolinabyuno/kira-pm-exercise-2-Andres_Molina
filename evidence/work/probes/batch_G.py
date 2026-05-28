"""Batch G — Webhooks (functional) + light SSRF probe.

Two goals in one batch:
  1) Functional characterization of `POST /v1/webhooks/register`:
     - happy-path registration against a public capture URL (webhook.site)
     - GAP-04 resolution: does `x-api-key` alone suffice, or is Bearer enforced
       at runtime despite the docs?
     - idempotency (replay vs conflict)
     - read endpoints (`GET /v1/webhooks`, `GET /v1/webhooks/{id}`)
     - cleanup (`DELETE /v1/webhooks/{id}`)
     - edge cases (empty events, NONEXISTENT_EVENT, missing url)

  2) Light Phase-3 preview SSRF probe (OWASP API7:2023, GAP-21, GAP-11):
     does Kira validate the `url` field against private / link-local /
     non-HTTP destinations? One request per probe URL, no retries, immediate
     cleanup on any accepted registration.

Hard rules (do not violate):
  - Never write raw secrets — uses `_redact` from sibling module.
  - Does not modify `run_flow.py`; imports `auth`, `BASE_URL`, `API_KEY`.
  - Per-call evidence files written to `evidence/work/webhooks/{NN}-{outcome}.json`.
  - One webhook.site UUID for the entire batch — easy cleanup.
  - SSRF-flavored registrations are immediately DELETEd if accepted.
  - Does NOT probe internal infrastructure — only asks Kira to register URLs
    so we can document Kira's acceptance/rejection behavior.

Run: ``python3 evidence/work/probes/batch_G.py``
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Make parent (evidence/work) and `_redact`+`run_flow` importable.
HERE = Path(__file__).resolve().parent
WORK = HERE.parent  # evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import (  # noqa: E402  — reuse helpers, do not modify
    API_KEY,
    BASE_URL,
    CLIENT_ID,
    auth,
)

EVIDENCE_DIR = WORK
FAMILY = "webhooks"

# Single capture URL for the entire batch — easy cleanup, single inbox to inspect.
# Generated at module import; same UUID reused for all functional + control probes.
CAPTURE_UUID = str(uuid.uuid4())
CAPTURE_URL = f"https://webhook.site/{CAPTURE_UUID}"


# ---------------------------------------------------------------------------
# Local capture — copy of run_flow.capture kept here so we don't mutate the
# shared module. Same redaction rules.
# ---------------------------------------------------------------------------


def capture(
    family: str,
    attempt_id: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    elapsed_ms: float,
    outcome: str,
    filename: Optional[str] = None,
) -> Path:
    out_dir = EVIDENCE_DIR / family
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


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _do(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]] = None,
    *,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, str], Any, float]:
    """Run an arbitrary HTTP request. Returns (status, headers, parsed_body, ms)."""
    t0 = time.perf_counter_ns()
    if body is None:
        resp = httpx.request(method, url, headers=headers, timeout=timeout)
    else:
        resp = httpx.request(method, url, headers=headers, json=body, timeout=timeout)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        parsed: Any = resp.json()
    except Exception:
        parsed = resp.text
    return resp.status_code, dict(resp.headers), parsed, elapsed_ms


def _outcome(status: int, label: str) -> str:
    if 200 <= status < 300:
        return f"success-{label}" if label else "success"
    return f"fail-{status}-{label}" if label else f"fail-{status}"


def _shape_summary(body: Any) -> Dict[str, Any]:
    if isinstance(body, list):
        return {
            "top_type": "array",
            "length": len(body),
            "first_keys": sorted((body[0].keys() if isinstance(body[0], dict) else [])) if body else [],
        }
    if isinstance(body, dict):
        return {"top_type": "object", "keys": sorted(body.keys())}
    return {"top_type": type(body).__name__, "value": str(body)[:120]}


def _redacted_id(webhook_id: Any) -> str:
    """Display webhook IDs in logs without echoing the full opaque value."""
    if not isinstance(webhook_id, str):
        return f"<non-string:{type(webhook_id).__name__}>"
    if len(webhook_id) <= 8:
        return webhook_id
    return f"{webhook_id[:8]}…(len={len(webhook_id)})"


def _try_extract_id(body: Any) -> Optional[str]:
    """Try common shapes for an id field on the registration response.

    Per flow-design § 2.7 / § 3.11 the docs do not pin the response shape down.
    We try several plausible locations.
    """
    if not isinstance(body, dict):
        return None
    # Documented envelope: { data: { ... } }
    data = body.get("data") if isinstance(body.get("data"), dict) else None
    candidates = [
        body.get("id"),
        body.get("webhook_id"),
        body.get("webhookId"),
        body.get("registration_id"),
        data.get("id") if data else None,
        data.get("webhook_id") if data else None,
        data.get("webhookId") if data else None,
    ]
    for c in candidates:
        if isinstance(c, str) and c:
            return c
    return None


def _try_extract_secret_present(body: Any) -> bool:
    """Detect whether the API returned a `secret` in the registration response.

    Used for the secret-leak observation. We only record presence — never the
    value. The capture file already redacts via `_redact`.
    """
    if not isinstance(body, dict):
        return False
    if "secret" in body:
        return True
    data = body.get("data") if isinstance(body.get("data"), dict) else None
    if data and "secret" in data:
        return True
    return False


# ---------------------------------------------------------------------------
# Probe headers
# ---------------------------------------------------------------------------


def _hdr_x_api_key_only(*, idem_key: Optional[str] = None) -> Dict[str, str]:
    """`x-api-key` only — the documented requirement per GAP-04."""
    h = {"Content-Type": "application/json", "x-api-key": API_KEY, "Accept": "application/json"}
    if idem_key:
        h["Idempotency-Key"] = idem_key
    return h


def _hdr_bearer_only(token: str, *, idem_key: Optional[str] = None) -> Dict[str, str]:
    """Bearer only — does the API accept without x-api-key on /webhooks/register?"""
    h = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if idem_key:
        h["Idempotency-Key"] = idem_key
    return h


def _hdr_both(token: str, *, idem_key: Optional[str] = None) -> Dict[str, str]:
    """Both x-api-key + Bearer — defensive integrator default."""
    h = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if idem_key:
        h["Idempotency-Key"] = idem_key
    return h


# ---------------------------------------------------------------------------
# Single-call wrapper that captures + returns a structured iteration record
# ---------------------------------------------------------------------------


def _run(
    iterations: List[Dict[str, Any]],
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    label: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attempt_id = str(uuid.uuid4())
    status, rh, parsed, elapsed = _do(method, url, headers, body)
    outcome = _outcome(status, label)
    path = capture(
        FAMILY,
        attempt_id,
        request={"method": method, "url": url, "headers": headers, "body": body},
        response={"status": status, "headers": rh, "body": parsed},
        elapsed_ms=elapsed,
        outcome=outcome,
    )
    rec = {
        "iter": len(iterations) + 1,
        "label": label,
        "method": method,
        "url": url,
        "status": status,
        "outcome": outcome,
        "elapsed_ms": round(elapsed, 2),
        "shape": _shape_summary(parsed),
        "evidence": str(path.relative_to(EVIDENCE_DIR.parents[1])),
        "secret_present_in_response": _try_extract_secret_present(parsed),
        "id_extracted": _redacted_id(_try_extract_id(parsed)) if _try_extract_id(parsed) else None,
        "_id_raw": _try_extract_id(parsed),  # private — used by deletes; never log/serialize
    }
    if extra:
        rec.update(extra)
    iterations.append(rec)
    return rec


# ---------------------------------------------------------------------------
# Probe sequence
# ---------------------------------------------------------------------------


def probe_webhooks(token: str) -> Dict[str, Any]:
    # Path disambiguation: the docs (flow-design § 3.11, § 4.6) document
    # `POST /webhooks/register` (no /v1/ prefix) but the brief uses
    # `POST /v1/webhooks/register`. Probe both first to decide which one is
    # the runtime canonical, then proceed against the working path.
    iterations: List[Dict[str, Any]] = []
    created_ids: List[Tuple[str, str]] = []  # [(label, id)]
    # Use the docs-canonical body shape: {webhook_url, secret, client_uuid}
    # per flow-design § 2.7 / § 3.11 / § 4.6. The brief mentioned {url, events}
    # but that contradicts the docs — preserve docs-canonical for disambig.
    # Note: we set `secret` to a fake high-entropy hex value (never echoed in
    # this code — the capture file will redact it via the SECRET_FIELD_NAMES
    # rule in `_redact.py`).
    FAKE_SECRET = "00000000000000000000000000000000"  # 32 chars per docs §3.11
    body_disambig = {
        "webhook_url": CAPTURE_URL,
        "secret": FAKE_SECRET,
        "client_uuid": CLIENT_ID,
    }

    rec_with_v1 = _run(
        iterations,
        "POST",
        f"{BASE_URL.rstrip('/')}/v1/webhooks/register",
        _hdr_both(token, idem_key=str(uuid.uuid4())),
        body_disambig,
        "G0.1-path-v1-webhooks-register",
    )
    rec_no_v1 = _run(
        iterations,
        "POST",
        f"{BASE_URL.rstrip('/')}/webhooks/register",
        _hdr_both(token, idem_key=str(uuid.uuid4())),
        body_disambig,
        "G0.2-path-webhooks-register-no-v1",
    )
    # Track for cleanup if either produced an id
    if rec_with_v1["status"] < 300 and rec_with_v1["_id_raw"]:
        created_ids.append((rec_with_v1["label"], rec_with_v1["_id_raw"]))
    if rec_no_v1["status"] < 300 and rec_no_v1["_id_raw"]:
        created_ids.append((rec_no_v1["label"], rec_no_v1["_id_raw"]))

    # Decide which base path to use for the remaining probes — prefer 2xx.
    # Fall back to non-403 if both are non-2xx. Otherwise default to docs path.
    def _picks(rec_a, rec_b, a_url, b_url):
        if 200 <= rec_a["status"] < 300:
            return a_url
        if 200 <= rec_b["status"] < 300:
            return b_url
        # Prefer the non-403 one — 403 MissingAuthenticationToken from API
        # Gateway means "no such route" so the OTHER path is more interesting.
        if rec_a["status"] != 403 and rec_b["status"] == 403:
            return a_url
        if rec_b["status"] != 403 and rec_a["status"] == 403:
            return b_url
        return a_url  # default — both failed identically

    register_url = _picks(
        rec_with_v1,
        rec_no_v1,
        f"{BASE_URL.rstrip('/')}/v1/webhooks/register",
        f"{BASE_URL.rstrip('/')}/webhooks/register",
    )
    # Derive list URL by stripping `/register`
    list_url = register_url[: -len("/register")]

    # Also try the bare list endpoint families to find an alive read surface.
    for label, url in (
        ("G0.3-list-v1-webhooks", f"{BASE_URL.rstrip('/')}/v1/webhooks"),
        ("G0.4-list-webhooks-no-v1", f"{BASE_URL.rstrip('/')}/webhooks"),
    ):
        _run(iterations, "GET", url, _hdr_both(token), None, label)

    # ----- G2.1 — GAP-04 resolution: docs claim x-api-key alone is enough -----
    # Send only x-api-key. If 2xx → docs are right for this endpoint.
    # Body shape per docs (§ 3.11): {webhook_url, secret, client_uuid}
    body_basic = {
        "webhook_url": CAPTURE_URL,
        "secret": FAKE_SECRET,
        "client_uuid": CLIENT_ID,
    }
    rec = _run(
        iterations,
        "POST",
        register_url,
        _hdr_x_api_key_only(idem_key=str(uuid.uuid4())),
        body_basic,
        "G2.1-xapikey-only",
    )
    if rec["status"] < 300 and rec["_id_raw"]:
        created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G2.2 — Bearer-only — does the API accept without x-api-key? -----
    rec = _run(
        iterations,
        "POST",
        register_url,
        _hdr_bearer_only(token, idem_key=str(uuid.uuid4())),
        body_basic,
        "G2.2-bearer-only",
    )
    if rec["status"] < 300 and rec["_id_raw"]:
        created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G2.3 — Both headers (defensive integrator default) -----
    rec = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=str(uuid.uuid4())),
        body_basic,
        "G2.3-both-headers",
    )
    if rec["status"] < 300 and rec["_id_raw"]:
        created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G2.4 — Cross-check: does the API also accept `{url, events}` ?  -----
    # The exercise brief suggested this shape; docs don't show it. Probe to
    # confirm whether the API supports event-filtering or only the bulk
    # registration shape.
    rec = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=str(uuid.uuid4())),
        {"url": CAPTURE_URL, "events": ["user.created"]},
        "G2.4-alt-shape-url-events",
    )
    if rec["status"] < 300 and rec["_id_raw"]:
        created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G4 — Idempotency: replay same body + same key -----
    idem_replay = str(uuid.uuid4())
    body_idem = body_basic  # same canonical shape
    rec_first = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=idem_replay),
        body_idem,
        "G4.1-idem-first",
    )
    if rec_first["status"] < 300 and rec_first["_id_raw"]:
        created_ids.append((rec_first["label"], rec_first["_id_raw"]))
    # Replay: same idem-key + same body → expect 2xx replay (same id ideally)
    rec_replay = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=idem_replay),
        body_idem,
        "G4.2-idem-replay-same-body",
    )
    if rec_replay["status"] < 300 and rec_replay["_id_raw"] and (
        not rec_first["_id_raw"] or rec_replay["_id_raw"] != rec_first["_id_raw"]
    ):
        created_ids.append((rec_replay["label"], rec_replay["_id_raw"]))
    # Conflict: same idem-key + DIFFERENT body → expect 409
    rec_conflict = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=idem_replay),
        {
            "webhook_url": f"https://webhook.site/{CAPTURE_UUID}?conflict=1",
            "secret": FAKE_SECRET,
            "client_uuid": CLIENT_ID,
        },
        "G4.3-idem-conflict-diff-body",
    )
    if rec_conflict["status"] < 300 and rec_conflict["_id_raw"]:
        created_ids.append((rec_conflict["label"], rec_conflict["_id_raw"]))

    # ----- G3 — SSRF probe matrix (LIGHT — one request per URL) -----
    # Per scope: do NOT retry or escalate. Each accepted reg gets immediate DELETE.
    ssrf_urls = [
        ("ssrf-localhost-80", "http://localhost:80/"),
        ("ssrf-127-0-0-1", "http://127.0.0.1/"),
        ("ssrf-aws-imds", "http://169.254.169.254/latest/meta-data/"),
        ("ssrf-rfc1918-10", "http://10.0.0.1/"),
        ("ssrf-ipv6-loopback", "http://[::1]/"),
        ("ssrf-fragment", f"https://webhook.site/{CAPTURE_UUID}#evil"),
        ("ssrf-ftp-scheme", "ftp://webhook.site/test"),
        ("ssrf-dup-query", f"https://webhook.site/{CAPTURE_UUID}?a=1&a=2"),
    ]
    ssrf_results: List[Dict[str, Any]] = []
    for label, ssrf_url in ssrf_urls:
        rec = _run(
            iterations,
            "POST",
            register_url,
            _hdr_both(token, idem_key=str(uuid.uuid4())),
            {
                "webhook_url": ssrf_url,
                "secret": FAKE_SECRET,
                "client_uuid": CLIENT_ID,
            },
            label,
            extra={"probed_url": ssrf_url},
        )
        accepted = rec["status"] < 300
        ssrf_results.append(
            {
                "label": label,
                "url": ssrf_url,
                "status": rec["status"],
                "accepted": accepted,
                "evidence": rec["evidence"],
            }
        )
        if accepted and rec["_id_raw"]:
            # CRITICAL: do not leave SSRF-flavored regs alive. Delete immediately.
            del_label = f"ssrf-cleanup-{label}"
            del_url = f"{list_url}/{rec['_id_raw']}"
            del_rec = _run(
                iterations,
                "DELETE",
                del_url,
                _hdr_both(token),
                None,
                del_label,
            )
            ssrf_results[-1]["delete_status"] = del_rec["status"]
            ssrf_results[-1]["delete_evidence"] = del_rec["evidence"]
            if del_rec["status"] >= 300:
                created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G6 — Edge probes (against docs-canonical body shape) -----
    edge_probes: List[Tuple[str, Optional[Dict[str, Any]]]] = [
        ("G6.1-missing-webhook_url", {"secret": FAKE_SECRET, "client_uuid": CLIENT_ID}),
        ("G6.2-missing-client_uuid", {"webhook_url": CAPTURE_URL, "secret": FAKE_SECRET}),
        # Secret variants — per integration-plan §Batch G checklist
        ("G6.3-secret-empty", {"webhook_url": CAPTURE_URL, "secret": "", "client_uuid": CLIENT_ID}),
        ("G6.4-secret-null", {"webhook_url": CAPTURE_URL, "secret": None, "client_uuid": CLIENT_ID}),
        ("G6.5-secret-omit", {"webhook_url": CAPTURE_URL, "client_uuid": CLIENT_ID}),
        # http (not https) — docs imply HTTPS-only
        ("G6.6-http-not-https", {"webhook_url": CAPTURE_URL.replace("https://", "http://"), "secret": FAKE_SECRET, "client_uuid": CLIENT_ID}),
    ]
    for label, body in edge_probes:
        rec = _run(
            iterations,
            "POST",
            register_url,
            _hdr_both(token, idem_key=str(uuid.uuid4())),
            body,
            label,
        )
        if rec["status"] < 300 and rec["_id_raw"]:
            created_ids.append((rec["label"], rec["_id_raw"]))

    # ----- G5 — Read endpoints -----
    rec_list = _run(
        iterations,
        "GET",
        list_url,
        _hdr_both(token),
        None,
        "G5.1-list",
    )
    # GET detail (if we have at least one id)
    if created_ids:
        first_id = created_ids[0][1]
        _run(
            iterations,
            "GET",
            f"{list_url}/{first_id}",
            _hdr_both(token),
            None,
            "G5.2-detail",
        )

    # Variant: list with no Bearer (only x-api-key) — does GET respect GAP-04 too?
    _run(
        iterations,
        "GET",
        list_url,
        _hdr_x_api_key_only(),
        None,
        "G5.3-list-xapikey-only",
    )

    # ----- Cleanup — best-effort -----
    # Empirically the API returns ONLY {"message": "..."} on registration —
    # no `id`, no `webhook_id`. There is no GET /webhooks list and no
    # DELETE /webhooks/{id} endpoint (both returned 403 MissingAuthToken =
    # API GW "no such route"). Cleanup strategy: overwrite by registering
    # one final clean URL for our client_uuid (the registration appears to
    # be keyed by client_uuid — last-write-wins).
    cleanup_results: List[Dict[str, Any]] = []
    # First, try DELETE on any IDs we did manage to capture (defensive).
    seen_ids = set()
    for label, wid in created_ids:
        if wid in seen_ids:
            continue
        seen_ids.add(wid)
        del_rec = _run(
            iterations,
            "DELETE",
            f"{list_url}/{wid}",
            _hdr_both(token),
            None,
            f"cleanup-by-id-{label}",
        )
        cleanup_results.append(
            {"strategy": "DELETE-by-id", "label": label, "id": _redacted_id(wid), "delete_status": del_rec["status"]}
        )

    # Last-write-wins overwrite: register a final clean URL for our
    # client_uuid so any SSRF-flavored registration is no longer pointed at.
    final_overwrite = _run(
        iterations,
        "POST",
        register_url,
        _hdr_both(token, idem_key=str(uuid.uuid4())),
        {
            "webhook_url": CAPTURE_URL,  # back to clean webhook.site
            "secret": FAKE_SECRET,
            "client_uuid": CLIENT_ID,
        },
        "cleanup-overwrite-final",
    )
    cleanup_results.append(
        {
            "strategy": "POST-overwrite",
            "label": "final-clean-overwrite",
            "status": final_overwrite["status"],
            "evidence": final_overwrite["evidence"],
        }
    )

    # ----- Latency stats from happy-path-shaped calls (POST register, 2xx) -----
    successful_register_ms = [
        it["elapsed_ms"] for it in iterations if it["method"] == "POST"
        and it["url"].endswith("/webhooks/register")
        and 200 <= it["status"] < 300
    ]
    latency_stats: Dict[str, Any] = {"n": len(successful_register_ms)}
    if successful_register_ms:
        latency_stats["min_ms"] = round(min(successful_register_ms), 2)
        latency_stats["max_ms"] = round(max(successful_register_ms), 2)
        latency_stats["median_ms"] = round(statistics.median(successful_register_ms), 2)

    return {
        "capture_url": CAPTURE_URL,
        "capture_uuid": CAPTURE_UUID,
        "register_url": register_url,
        "list_url": list_url,
        "iterations": iterations,
        "ssrf_results": ssrf_results,
        "cleanup_results": cleanup_results,
        "latency_stats": latency_stats,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print(f"Batch G — capture URL = {CAPTURE_URL}")
    token = auth()
    if not token:
        print("AUTH FAILED — aborting Batch G.")
        return 2
    print("AUTH ok — running webhook probes…")

    result = probe_webhooks(token)

    # Write a summary JSON the markdown log can reference.
    summary_path = EVIDENCE_DIR / FAMILY / "_batch_G_summary.json"
    # Strip _id_raw before persisting (we never serialize raw IDs to evidence).
    safe_iters: List[Dict[str, Any]] = []
    for it in result["iterations"]:
        copy_it = {k: v for k, v in it.items() if not k.startswith("_")}
        safe_iters.append(copy_it)
    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "capture_url": result["capture_url"],
        "capture_uuid": result["capture_uuid"],
        "register_url": result["register_url"],
        "list_url": result["list_url"],
        "iterations": safe_iters,
        "ssrf_results": result["ssrf_results"],
        "cleanup_results": result["cleanup_results"],
        "latency_stats": result["latency_stats"],
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Summary written to {summary_path.relative_to(EVIDENCE_DIR.parents[1])}")
    print(f"Iterations: {len(safe_iters)}")
    print(f"SSRF probes: {len(result['ssrf_results'])}")
    accepted_ssrf = [r for r in result["ssrf_results"] if r["accepted"]]
    print(f"SSRF accepted (CRITICAL if >0): {len(accepted_ssrf)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
