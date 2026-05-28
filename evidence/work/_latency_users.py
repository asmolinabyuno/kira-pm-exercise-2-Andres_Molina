"""Latency baseline for POST /v1/users — 4-sample first cut.

Reuses the 3 existing successful captures and adds 1 more fresh successful
call so the JSON summary lives in ``evidence/work/latency/post_v1_users.json``.

Statistical caveat: 4 samples is below the threshold for p50/p95/p99 (which
needs N≥10). This file is honest about that — it reports min, max, median
only, plus the raw samples, and is intended as a first cut.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_flow import auth, create_user, fake_business_payload  # noqa: E402


def existing_successes() -> List[float]:
    """Read elapsed_ms from every existing 2xx capture under users/."""
    users_dir = HERE / "users"
    out: List[float] = []
    for f in sorted(users_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        status = data.get("response", {}).get("status")
        if isinstance(status, int) and 200 <= status < 300:
            ms = data.get("elapsed_ms")
            if isinstance(ms, (int, float)):
                out.append(float(ms))
    return out


def main() -> None:
    token = auth()
    if not token:
        print("AUTH failed", file=sys.stderr)
        sys.exit(1)

    samples = existing_successes()
    print(f"existing successful samples: {samples}")
    needed = max(0, 4 - len(samples))
    print(f"adding {needed} fresh calls to reach n=4")

    for i in range(needed):
        body = fake_business_payload(country_alpha3="USA")
        status, _, path = create_user(token, body)
        rel = path.relative_to(HERE.parent.parent)
        data = json.loads(path.read_text())
        ms = data["elapsed_ms"]
        print(f"  +call status={status} elapsed_ms={ms} evidence={rel}")
        if 200 <= status < 300:
            samples.append(float(ms))

    samples = sorted(samples)
    if not samples:
        print("no samples collected", file=sys.stderr)
        sys.exit(2)

    summary = {
        "endpoint": "POST /v1/users",
        "n": len(samples),
        "samples_ms": samples,
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "notes": (
            "4-sample first cut. p50/p95/p99 require N>=10 per data-engineer "
            "persona; this is the initial baseline. Latency includes Cloudflare "
            "edge + AWS API Gateway + Lambda hops. All calls used distinct "
            "fake business payloads (different emails) so no idempotency cache "
            "hits."
        ),
    }

    out_dir = HERE / "latency"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "post_v1_users.json"
    out.write_text(json.dumps(summary, indent=2))
    print("\nLatency summary:")
    print(json.dumps(summary, indent=2))
    print(f"written: {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
