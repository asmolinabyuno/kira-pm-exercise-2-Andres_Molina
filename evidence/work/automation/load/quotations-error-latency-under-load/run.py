"""Scenario 5 — Quotations 4xx latency under load.

DRIFT-E6: all 22 Phase 2 quotation attempts returned 4xx (sandbox fee config
blocks the happy path; body says "Total fees exceed or equal the payout amount").
Question: does the 4xx (validation/business-rule) path degrade under concurrency?

Plan:
  (a) 30 sequential POST /v1/quotations -> baseline.
  (b) 20 concurrent POST /v1/quotations -> stress.
  Compare median, p95, p99. Compute degradation factor.
"""
from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _loadlib import (  # noqa: E402
    atimed_request,
    auth_headers,
    auth_once,
    cfg,
    fake_quotation_body,
    percentile,
    summarize_latency,
    timed_request,
    write_scenario_log,
)

SCENARIO = "quotations-error-latency-under-load"
N_SEQUENTIAL = 30
CONCURRENCY = 20


def main() -> int:
    c = cfg()
    token = auth_once()
    headers = auth_headers(token)
    url = f"{c.base_url}/v1/quotations"
    body = fake_quotation_body()

    # Sequential baseline
    print(f"[{SCENARIO}] sequential baseline n={N_SEQUENTIAL}")
    seq_ms = []
    seq_statuses = []
    with httpx.Client() as client:
        for i in range(N_SEQUENTIAL):
            r = timed_request(client, "POST", url, headers=headers, json_body=body)
            seq_ms.append(r["elapsed_ms"])
            seq_statuses.append(r["status"])
            print(f"  [{i+1:02d}/{N_SEQUENTIAL}] status={r['status']} t={r['elapsed_ms']:.1f}ms")
            time.sleep(0.2)

    # Concurrent burst
    print(f"[{SCENARIO}] concurrent burst concurrency={CONCURRENCY}")
    async def runner():
        async with httpx.AsyncClient(timeout=30.0) as ac:
            return await asyncio.gather(*[
                atimed_request(ac, "POST", url, headers=headers, json_body=body)
                for _ in range(CONCURRENCY)
            ])
    t0 = time.perf_counter_ns()
    burst = asyncio.run(runner())
    burst_wall_ms = (time.perf_counter_ns() - t0) / 1e6
    burst_ms = [r["elapsed_ms"] for r in burst]
    burst_statuses = [r["status"] for r in burst]
    burst_429 = sum(1 for s in burst_statuses if s == 429)
    burst_5xx = sum(1 for s in burst_statuses if 500 <= s < 600)
    print(f"  burst wall_clock={burst_wall_ms:.1f}ms 429={burst_429} 5xx={burst_5xx}")

    seq_med = statistics.median(seq_ms)
    burst_med = statistics.median(burst_ms)
    degrade = round(burst_med / seq_med, 2) if seq_med else None

    summary = {
        "scenario": SCENARIO,
        "endpoint": "POST /v1/quotations",
        "sequential": summarize_latency(
            seq_ms, endpoint="POST /v1/quotations",
            scenario=f"{SCENARIO}/sequential",
            extra={
                "status_codes_seen": sorted(set(seq_statuses)),
                "all_4xx": all(400 <= s < 500 for s in seq_statuses),
                "notes": "DRIFT-E6: sandbox fee config blocks happy path; all responses 400.",
            },
        ),
        "concurrent": summarize_latency(
            burst_ms, endpoint="POST /v1/quotations",
            scenario=f"{SCENARIO}/concurrent",
            extra={
                "concurrency": CONCURRENCY,
                "burst_wall_clock_ms": round(burst_wall_ms, 2),
                "status_codes_seen": sorted(set(burst_statuses)),
                "err_429": burst_429,
                "err_5xx": burst_5xx,
            },
        ),
        "degradation_factor_median": degrade,
        "notes": "Sandbox happy path blocked by fee config (DRIFT-E6). Measuring 4xx path latency only.",
    }
    write_scenario_log(SCENARIO, summary)
    print(f"[{SCENARIO}] seq_median={seq_med:.1f}ms burst_median={burst_med:.1f}ms degrade_x={degrade}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
