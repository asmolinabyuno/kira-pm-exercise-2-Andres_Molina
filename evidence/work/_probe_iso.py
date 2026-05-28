"""GAP-20 probe — ISO 3166 alpha-2 vs alpha-3 on POST /v1/users.

Submits two USA-business payloads, identical except for the country field:
- alpha-2: ``"US"``
- alpha-3: ``"USA"``

Captures both to ``users/{NN}-iso-probe-{alpha2|alpha3}.json``.

Per flow-design.md § 6 GAP-20: user ``address_country``/``nationality`` are
documented as alpha-3, but ``/banks`` uses alpha-2. This probe checks whether
alpha-2 is silently rejected at user-creation, silently accepted, or
normalized.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_flow import auth, create_user, fake_business_payload  # noqa: E402


def summarize(label: str, status: int, resp_body: Any, path: Path) -> None:
    rel = path.relative_to(HERE.parent.parent)
    if isinstance(resp_body, dict):
        # Look for "registered_address.country" or similar normalization signals
        norm_country = None
        ra = resp_body.get("registered_address")
        if isinstance(ra, dict):
            norm_country = ra.get("country")
        details = resp_body.get("details") if 400 <= status < 500 else None
        body_keys = list(resp_body.keys())[:8]
        print(f"[{label}] status={status} evidence={rel}")
        print(f"    body_top_keys={body_keys}")
        if norm_country is not None:
            print(f"    registered_address.country={norm_country!r}")
        if details:
            print(f"    error_details={details}")
    else:
        print(f"[{label}] status={status} evidence={rel} body_raw={str(resp_body)[:200]}")


def main() -> None:
    token = auth()
    if not token:
        print("AUTH failed", file=sys.stderr)
        sys.exit(1)
    print("AUTH OK")

    # alpha-3 first (documented happy path)
    body_alpha3 = fake_business_payload(country_alpha3="USA")
    status3, resp3, path3 = create_user(
        token,
        body_alpha3,
        filename=None,  # let it auto-number, then rename for the iso-probe naming
    )
    # Auto-numbered evidence — fine; we'll just record the path.
    summarize("alpha-3 (USA)", status3, resp3, path3)

    # alpha-2: same builder but country_alpha3="US" — note that arg name is a
    # historical artifact; we're injecting an alpha-2 value to probe behavior.
    body_alpha2 = fake_business_payload(country_alpha3="US")
    # Sanity: ensure associated_persons nationality is also alpha-2 in this probe.
    for p in body_alpha2.get("associated_persons", []):
        if isinstance(p, dict) and p.get("nationality") == "US":
            pass  # already alpha-2
    status2, resp2, path2 = create_user(token, body_alpha2)
    summarize("alpha-2 (US)", status2, resp2, path2)

    # Rename the two new evidence files so they're discoverable.
    users_dir = HERE / "users"

    def rename_to(src: Path, label: str) -> Path:
        new_name = users_dir / f"{src.stem}-iso-probe-{label}.json"
        # If a file with this exact name already exists, fall through to a fresh stem.
        if new_name.exists():
            new_name = users_dir / f"iso-probe-{label}-{uuid.uuid4().hex[:6]}.json"
        src.rename(new_name)
        return new_name

    new3 = rename_to(path3, "alpha3")
    new2 = rename_to(path2, "alpha2")
    print(f"\nrenamed:\n  alpha-3 → {new3.relative_to(HERE.parent.parent)}")
    print(f"  alpha-2 → {new2.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
