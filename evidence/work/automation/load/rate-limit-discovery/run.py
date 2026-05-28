"""Scenario 4 — Rate-limit discovery on GET /v1/countries.

Probe tiers: 1, 5, 10, 20 req/sec. Each tier runs ~15s (conservative).
At each tier capture: 2xx count, 429 count, 5xx count, latency stats, Retry-After.

STOP IMMEDIATELY on a 5xx storm — we are NOT trying to DOS the shared sandbox.
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
    percentile,
    summarize_latency,
    write_scenario_log,
)

SCENARIO = "rate-limit-discovery"
ENDPOINT = "/v1/countries"

# (target_rps, duration_seconds)
TIERS = [(1, 15), (5, 15), (10, 15), (20, 15)]

# Safety: if 5xx fraction in a tier exceeds this, abort the rest.
ABORT_5XX_FRACTION = 0.10

# Inter-tier cool-down so we don't bleed bucket between tiers.
COOLDOWN_S = 5.0


async def run_tier(rps: int, duration_s: int, url: str, headers: dict):
    interval = 1.0 / rps
    results = []
    end = time.perf_counter() + duration_s

    async with httpx.AsyncClient(timeout=15.0) as client:
        next_fire = time.perf_counter()
        # Cap absolute requests per tier as belt-and-suspenders. 20 rps * 15 s = 300.
        cap = rps * duration_s + 5
        tasks: list[asyncio.Task] = []
        while time.perf_counter() < end and len(tasks) < cap:
            now = time.perf_counter()
            if now < next_fire:
                await asyncio.sleep(next_fire - now)
            tasks.append(asyncio.create_task(
                atimed_request(client, "GET", url, headers=headers)
            ))
            next_fire += interval
        for t in tasks:
            results.append(await t)
    return results


def tier_stats(rps: int, results: list[dict]) -> dict:
    statuses = [r["status"] for r in results]
    ms = [r["elapsed_ms"] for r in results]
    ok = sum(1 for s in statuses if 200 <= s < 300)
    err_429 = sum(1 for s in statuses if s == 429)
    err_5xx = sum(1 for s in statuses if 500 <= s < 600)
    err_4xx_other = sum(1 for s in statuses if 400 <= s < 500 and s != 429)
    ra = [r["retry_after"] for r in results if r["retry_after"]]
    n = len(results)
    return {
        "target_rps": rps,
        "n": n,
        "ok": ok,
        "err_429": err_429,
        "err_5xx": err_5xx,
        "err_other_4xx": err_4xx_other,
        "retry_after_values": ra,
        "min_ms": round(min(ms), 2) if ms else None,
        "median_ms": round(statistics.median(ms), 2) if ms else None,
        "p95_ms": round(percentile(ms, 95), 2) if ms else None,
        "p99_ms": round(percentile(ms, 99), 2) if ms else None,
        "max_ms": round(max(ms), 2) if ms else None,
        "fraction_5xx": round(err_5xx / n, 3) if n else None,
        "fraction_429": round(err_429 / n, 3) if n else None,
        "status_codes_seen": sorted(set(statuses)),
    }


def main() -> int:
    c = cfg()
    token = auth_once()
    headers = auth_headers(token)
    url = f"{c.base_url}{ENDPOINT}"

    print(f"[{SCENARIO}] target={ENDPOINT}  tiers={TIERS}")
    tier_results = []
    aborted = False
    abort_reason = None

    for rps, dur in TIERS:
        print(f"[{SCENARIO}] Tier rps={rps} dur={dur}s")
        results = asyncio.run(run_tier(rps, dur, url, headers))
        stats = tier_stats(rps, results)
        tier_results.append({**stats, "runs": [
            {k: v for k, v in r.items() if k != "snippet"} for r in results
        ]})
        print(
            f"  n={stats['n']} ok={stats['ok']} 429={stats['err_429']} 5xx={stats['err_5xx']} "
            f"4xx-other={stats['err_other_4xx']} median={stats['median_ms']}ms p95={stats['p95_ms']}ms"
        )
        if stats["fraction_5xx"] and stats["fraction_5xx"] > ABORT_5XX_FRACTION:
            aborted = True
            abort_reason = f"Aborted at rps={rps}: 5xx fraction {stats['fraction_5xx']} > {ABORT_5XX_FRACTION}"
            print(f"[{SCENARIO}] {abort_reason}")
            break
        if rps != TIERS[-1][0]:
            print(f"[{SCENARIO}] cooling down {COOLDOWN_S}s")
            time.sleep(COOLDOWN_S)

    # Threshold heuristic: first tier with any 429.
    threshold_rps = None
    sample_retry_after = None
    for t in tier_results:
        if t["err_429"] > 0:
            threshold_rps = t["target_rps"]
            sample_retry_after = t["retry_after_values"][:5] if t["retry_after_values"] else None
            break

    summary = {
        "scenario": SCENARIO,
        "endpoint": f"GET {ENDPOINT}",
        "tiers": tier_results,
        "aborted_early": aborted,
        "abort_reason": abort_reason,
        "rate_limit_threshold_rps_discovered": threshold_rps,
        "retry_after_sample": sample_retry_after,
        "notes": (
            "Tiered ramp 1->5->10->20 rps for 15s each. STOP-on-5xx>=10% safety guard. "
            "If threshold_rps is None, no 429s were observed in the tested range."
        ),
    }
    write_scenario_log(SCENARIO, summary)
    print(f"[{SCENARIO}] threshold_rps={threshold_rps}  aborted={aborted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
