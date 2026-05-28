"""Scenario 3 — Concurrent POST /v1/recipients.

20 parallel httpx requests with distinct fake CLABEs. Measure:
- Per-request latency under concurrency.
- 429 / rate-limit behavior (Retry-After).
- Successful concurrent throughput.
- Any race-condition errors.

Conservative: 20 parallel, 1 burst. Then 1 sequential baseline call for comparison.
"""
from __future__ import annotations

import asyncio
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _loadlib import (  # noqa: E402
    atimed_request,
    auth_headers,
    auth_once,
    cfg,
    fake_recipient_body,
    percentile,
    summarize_latency,
    timed_request,
    write_latency_json,
    write_scenario_log,
)

SCENARIO = "concurrent-create-recipients"
CONCURRENCY = 20


async def fire_concurrent(client: httpx.AsyncClient, url: str, headers_base: dict, n: int):
    """Send n parallel POSTs with distinct idempotency keys + fake CLABEs."""
    async def one(seed: int) -> dict:
        hdr = {**headers_base, "Idempotency-Key": str(uuid.uuid4())}
        body = fake_recipient_body(seed)
        r = await atimed_request(client, "POST", url, headers=hdr, json_body=body)
        # Strip snippet body but keep error-relevant fields, redact already applied.
        r["seed"] = seed
        return r

    seeds = [int(time.time()) * 1000 + i for i in range(n)]
    return await asyncio.gather(*[one(s) for s in seeds])


def main() -> int:
    c = cfg()
    token = auth_once()
    headers = auth_headers(token)
    url = f"{c.base_url}/v1/recipients"

    # Baseline single sequential call
    print(f"[{SCENARIO}] baseline single POST /v1/recipients")
    with httpx.Client() as client:
        hdr = {**headers, "Idempotency-Key": str(uuid.uuid4())}
        baseline = timed_request(
            client, "POST", url, headers=hdr,
            json_body=fake_recipient_body(seed=int(time.time())),
        )
    print(f"  baseline status={baseline['status']} t={baseline['elapsed_ms']:.1f}ms")

    # Concurrent burst
    print(f"[{SCENARIO}] concurrent burst — {CONCURRENCY} parallel POSTs")
    async def runner():
        async with httpx.AsyncClient(timeout=30.0) as ac:
            return await fire_concurrent(ac, url, headers, CONCURRENCY)

    burst_start = time.perf_counter_ns()
    results = asyncio.run(runner())
    burst_total_ms = (time.perf_counter_ns() - burst_start) / 1e6

    statuses = [r["status"] for r in results]
    ms = [r["elapsed_ms"] for r in results]
    ok_count = sum(1 for s in statuses if 200 <= s < 300)
    err_429 = sum(1 for s in statuses if s == 429)
    err_4xx = sum(1 for s in statuses if 400 <= s < 500 and s != 429)
    err_5xx = sum(1 for s in statuses if 500 <= s < 600)
    retry_afters = [r["retry_after"] for r in results if r["retry_after"]]

    print(f"  ok={ok_count}/{CONCURRENCY}  429={err_429}  other-4xx={err_4xx}  5xx={err_5xx}")
    print(f"  total burst wall-clock: {burst_total_ms:.1f}ms")
    print(f"  per-request median={statistics.median(ms):.1f}ms p95={percentile(ms, 95):.1f}ms max={max(ms):.1f}ms")

    extra = {
        "scenario": SCENARIO,
        "concurrency": CONCURRENCY,
        "baseline_single_ms": baseline["elapsed_ms"],
        "baseline_status": baseline["status"],
        "burst_wall_clock_ms": round(burst_total_ms, 2),
        "ok_count": ok_count,
        "err_429": err_429,
        "err_other_4xx": err_4xx,
        "err_5xx": err_5xx,
        "retry_after_values": retry_afters,
        "status_codes": statuses,
        "throughput_rps_under_burst": round(CONCURRENCY / (burst_total_ms / 1000.0), 2)
        if burst_total_ms > 0 else None,
        "latency_degradation_factor": round(statistics.median(ms) / baseline["elapsed_ms"], 2)
        if baseline["elapsed_ms"] > 0 else None,
        "runs": [{k: v for k, v in r.items() if k != "snippet"} for r in results],
        "notes": "20 parallel POSTs with distinct fake CLABEs + distinct Idempotency-Keys. Sandbox-only fake data.",
    }
    payload = summarize_latency(ms, endpoint="POST /v1/recipients", scenario=SCENARIO, extra=extra)
    write_latency_json(payload, "post_v1_recipients_concurrent.json")
    write_scenario_log(SCENARIO, payload)
    print(f"[{SCENARIO}] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
