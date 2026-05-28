"""Iterate ``POST /v1/users`` to first 2xx with empirical telemetry.

Strategy:
- Attempt 1: docs-only USA business (ACT) payload per flow-design.md § 3.2.1.
  This is the most-documented happy path.
- Each subsequent attempt: read the 4xx ``details[]`` (Shape "A") and adjust
  the body. Log what was changed, what the error said, and whether the doc
  alone would have told the integrator what to fix (doc-sufficiency signal).
- Stop on first 2xx or after 5 attempts.

The iteration log is printed to stdout in a structured form so it can be
copied into ``integration-log.md``.
"""
from __future__ import annotations

import copy
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_flow import (  # noqa: E402
    auth,
    create_user,
    fake_business_payload,
    fake_individual_payload,
)


def details_summary(resp_body: Any) -> str:
    """Render a one-line summary of a Kira validation error body.

    Handles the observed Shape: ``{error, details: [{path, message, code}]}``.
    Falls back to a truncated str() for anything else.
    """
    if isinstance(resp_body, dict):
        details = resp_body.get("details")
        if isinstance(details, list):
            return "; ".join(
                f"{d.get('path', '?')}: {d.get('code', '?')} — {d.get('message', '?')}"
                for d in details
            )
        return json.dumps(resp_body)[:400]
    return str(resp_body)[:400]


def main() -> None:
    token = auth()
    if not token:
        print("AUTH failed", file=sys.stderr)
        sys.exit(1)
    print("AUTH OK")

    iteration_log: List[Dict[str, Any]] = []
    body = fake_business_payload(country_alpha3="USA")
    last_change = "initial docs-only USA business (ACT) payload per flow-design.md § 3.2.1"

    MAX_ATTEMPTS = 5
    success = False
    success_response: Dict[str, Any] | None = None
    success_path: Path | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        status, resp_body, path = create_user(token, body)
        summary = details_summary(resp_body)
        rel = path.relative_to(HERE.parent.parent)
        print(f"\n--- attempt {attempt} ---")
        print(f"  status={status}  evidence={rel}")
        print(f"  changed: {last_change}")
        print(f"  error_summary: {summary}")

        iteration_log.append(
            {
                "attempt": attempt,
                "changed": last_change,
                "status": status,
                "error_summary": summary,
                "evidence": str(rel),
            }
        )

        if 200 <= status < 300:
            success = True
            success_response = resp_body if isinstance(resp_body, dict) else None
            success_path = path
            break

        # Decide next change based on the error shape.
        next_body = copy.deepcopy(body)
        next_change = "no further changes to attempt"

        if isinstance(resp_body, dict) and isinstance(resp_body.get("details"), list):
            details = resp_body["details"]
            # Strategy: address each top-level field path with a targeted fix.
            paths = [d.get("path") for d in details if isinstance(d, dict)]
            codes = [d.get("code") for d in details if isinstance(d, dict)]

            fixes: List[str] = []

            # Switch user type discriminator if error complains about it.
            if any(p == "type" for p in paths):
                if next_body.get("type") != "business":
                    next_body["type"] = "business"
                    fixes.append("set type=business")
                else:
                    next_body["type"] = "individual"
                    next_body = fake_individual_payload(country_alpha3="USA")
                    fixes.append("flipped discriminator to type=individual + rebuild as individual")

            # If a field is required but missing, log what.
            missing = [d for d in details if isinstance(d, dict) and "required" in (d.get("code") or "").lower()]
            if missing:
                fixes.append(f"docs gap — server demanded: {[d.get('path') for d in missing]}")

            # If country-code style errors (alpha-3 invalid), try alpha-2 and vice versa.
            if any("country" in (p or "") for p in paths):
                cur_country = next_body.get("address_country") or next_body.get("nationality")
                if cur_country == "USA":
                    next_body["address_country"] = "US"
                    if "nationality" in next_body:
                        next_body["nationality"] = "US"
                    fixes.append("retry with alpha-2 country (US instead of USA)")
                elif cur_country == "US":
                    next_body["address_country"] = "USA"
                    if "nationality" in next_body:
                        next_body["nationality"] = "USA"
                    fixes.append("retry with alpha-3 country (USA instead of US)")

            if not fixes:
                # Fallback: add a fresh email to dodge unique-key collisions, and try MX.
                next_body = fake_business_payload(country_alpha3="USA")
                fixes.append("fresh business payload — no targeted fix derivable from error")

            next_change = "; ".join(fixes)
        elif status >= 500:
            next_change = "server error — abort iteration"
            iteration_log[-1]["note"] = "5xx encountered; flagging as drift"
            break
        else:
            next_change = "no structured details — abort iteration"
            iteration_log[-1]["note"] = "non-structured error body; flagging as drift"
            break

        body = next_body
        last_change = next_change

    print("\n========== ITERATION SUMMARY ==========")
    print(json.dumps(iteration_log, indent=2))
    print("=======================================")

    if success and success_response is not None:
        # Pull out fields useful for the chaining step (NOT secrets — IDs only).
        print("\nSUCCESS — top-level fields observed:")
        for key in success_response.keys():
            value = success_response[key]
            if isinstance(value, (str, int, bool, float)):
                print(f"  {key}: {value!r}")
            elif isinstance(value, list):
                print(f"  {key}: list[len={len(value)}]")
            elif isinstance(value, dict):
                print(f"  {key}: dict[keys={list(value.keys())}]")
            else:
                print(f"  {key}: {type(value).__name__}")
        print(f"\nevidence: {success_path.relative_to(HERE.parent.parent)}")
    elif success:
        print("\nSUCCESS but no JSON dict body — see evidence.")
    else:
        print("\nFAIL — no 2xx within max attempts.")
        sys.exit(2)


if __name__ == "__main__":
    main()
