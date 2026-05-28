"""Scenario 1 — delete-recipient-pollution.

Hypothesis: DRIFT-C15 shows DELETE recipients is a 403 no-op. If an attacker with
API-key access can create N recipients but cannot remove them, can they pollute
the tenant's recipient list to the point of breaking pagination / list reads?

Plan:
  1. Create up to N=20 SPEI recipients (capped low to avoid sandbox spam).
  2. After each create, try DELETE — confirm DRIFT-C15 reproduces every time.
  3. List GET /v1/recipients?user_id=<our-user> — observe envelope, total, max
     page size.
  4. Probe deep-paging: limit=100, limit=1000, limit=100000 (and offset huge).
  5. Document: cleanup IS impossible (the point).

Run:  python3 evidence/work/abuse/delete-recipient-pollution/run.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _abuse_common import (  # noqa: E402
    BASE_URL,
    USER_CREATED,
    base_headers,
    call,
    random_clabe,
    spei_payload,
    write_summary,
)

SLUG = "delete-recipient-pollution"

# Cap at a modest number. The point is to *prove the door is open*, not flood
# the sandbox. 20 is enough to (a) confirm DELETE is consistently broken,
# (b) see if listing returns all of them, (c) compute a max-page-size.
N_CREATE = 20


def main() -> None:
    created_ids: list[str] = []
    delete_results: list[tuple[str, int]] = []

    # ---- Step 1+2: create + delete loop -----------------------------------
    for i in range(N_CREATE):
        # `last_name` validation rejects digits. Use spelled-out tens/units.
        suffix_map = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
                      "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"]
        body = spei_payload(user_id=USER_CREATED, clabe=random_clabe(i),
                            last_name=f"Pollute{suffix_map[i % len(suffix_map)]}")
        hdrs = base_headers()
        hdrs["idempotency-key"] = str(uuid.uuid4())
        status, parsed, _, _ = call(
            method="POST",
            url=f"{BASE_URL}/v1/recipients",
            headers=hdrs,
            body=body,
            scenario_slug=SLUG,
            outcome_hint=f"create-{i:02d}",
            filename=f"01-create-{i:02d}",
        )
        rid = None
        if isinstance(parsed, dict):
            rid = parsed.get("recipient_id") or parsed.get("id")
        if status == 201 and rid:
            created_ids.append(rid)
            # Immediately try DELETE
            d_status, _, _, _ = call(
                method="DELETE",
                url=f"{BASE_URL}/v1/recipients/{rid}",
                headers=base_headers(),
                body=None,
                scenario_slug=SLUG,
                outcome_hint=f"delete-{i:02d}",
                filename=f"02-delete-{i:02d}",
            )
            delete_results.append((rid, d_status))

    # ---- Step 3: list ----------------------------------------------------
    # Default list
    status_list, list_body, _, _ = call(
        method="GET",
        url=f"{BASE_URL}/v1/recipients?user_id={USER_CREATED}",
        headers=base_headers(),
        body=None,
        scenario_slug=SLUG,
        outcome_hint="list-default",
        filename="03-list-default",
    )

    # ---- Step 4: pagination boundary probes ------------------------------
    # We know from DRIFT-10 that ?limit=100000 returned 500 on /v1/users.
    # Re-test on recipients.
    paging_probes = [
        ("limit-100", "limit=100"),
        ("limit-1000", "limit=1000"),
        ("limit-100000", "limit=100000"),
        ("offset-9999", "offset=9999"),
        ("limit-neg1", "limit=-1"),
        ("limit-0", "limit=0"),
    ]
    paging_results = []
    for label, qs in paging_probes:
        s, body, _, _ = call(
            method="GET",
            url=f"{BASE_URL}/v1/recipients?user_id={USER_CREATED}&{qs}",
            headers=base_headers(),
            body=None,
            scenario_slug=SLUG,
            outcome_hint=f"list-{label}",
            filename=f"04-list-{label}",
        )
        # Tally recipient count if listable
        listed = None
        if isinstance(body, dict):
            recipients = body.get("recipients")
            if isinstance(recipients, list):
                listed = len(recipients)
        paging_results.append({"label": label, "status": s, "listed_count": listed})

    total_observed = None
    listed_now = None
    if isinstance(list_body, dict):
        total_observed = list_body.get("total")
        recipients_list = list_body.get("recipients")
        if isinstance(recipients_list, list):
            listed_now = len(recipients_list)

    summary = {
        "scenario": SLUG,
        "n_create_attempts": N_CREATE,
        "n_created_ok": len(created_ids),
        "delete_status_counts": {
            str(s): sum(1 for _r, ss in delete_results if ss == s)
            for s in sorted({ss for _r, ss in delete_results})
        },
        "delete_success_count": sum(1 for _r, ss in delete_results if 200 <= ss < 300),
        "list_total_field": total_observed,
        "list_count_observed": listed_now,
        "paging_probes": paging_results,
        "evidence_dir": str(HERE.relative_to(HERE.parents[3])),
    }
    write_summary(SLUG, summary)
    print(f"[{SLUG}] created={len(created_ids)} deleted_ok={summary['delete_success_count']} "
          f"total_in_list={total_observed} listed_now={listed_now}")


if __name__ == "__main__":
    main()
