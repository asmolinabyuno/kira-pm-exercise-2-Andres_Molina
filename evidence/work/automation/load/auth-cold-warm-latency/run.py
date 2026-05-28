"""Scenario 1 — Auth cold/warm latency probe.

Hypothesis: DRIFT-2-adjacent. Phase 2 measured /auth at 953 ms median (n=4).
Is that cold-start or steady-state? Validate with:
  (a) 30 sequential calls, 1s apart -> warm-up curve.
  (b) 1 call + 60s pause + 1 call -> does the second call's latency match cold-start?

Sandbox-only. No secrets persisted (loadlib redacts).
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _loadlib import (  # noqa: E402
    cfg,
    percentile,
    summarize_latency,
    timed_request,
    write_latency_json,
    write_scenario_log,
)

SCENARIO = "auth-cold-warm-latency"
N_SEQUENTIAL = 30
SLEEP_BETWEEN = 1.0  # seconds
COLD_GAP_S = 60.0  # gap for cold-restart probe


def main() -> int:
    c = cfg()
    url = f"{c.base_url}/auth"
    body = {"client_id": c.client_id, "password": c.password}
    headers = {"Content-Type": "application/json", "x-api-key": c.api_key}

    print(f"[{SCENARIO}] Sequential warm-up: {N_SEQUENTIAL} calls, {SLEEP_BETWEEN}s apart")
    samples = []
    statuses = []
    with httpx.Client() as client:
        for i in range(N_SEQUENTIAL):
            r = timed_request(client, "POST", url, headers=headers, json_body=body)
            samples.append(r["elapsed_ms"])
            statuses.append(r["status"])
            print(f"  [{i+1:02d}/{N_SEQUENTIAL}] status={r['status']} t={r['elapsed_ms']:.1f} ms")
            if i < N_SEQUENTIAL - 1:
                time.sleep(SLEEP_BETWEEN)

    # Cold-restart probe
    print(f"[{SCENARIO}] Cold-restart probe: pause {COLD_GAP_S}s then 1 call")
    time.sleep(COLD_GAP_S)
    with httpx.Client() as client:
        cold = timed_request(client, "POST", url, headers=headers, json_body=body)
    print(f"  cold call: status={cold['status']} t={cold['elapsed_ms']:.1f} ms")

    # Stats
    first_3 = samples[:3]
    last_10 = samples[-10:]
    cold_est = statistics.median(first_3)
    warm_med = statistics.median(last_10)
    ratio = round(cold_est / warm_med, 2) if warm_med else None

    extra = {
        "scenario": SCENARIO,
        "sequential_n": N_SEQUENTIAL,
        "sleep_between_s": SLEEP_BETWEEN,
        "cold_gap_s": COLD_GAP_S,
        "all_2xx": all(200 <= s < 300 for s in statuses + [cold["status"]]),
        "cold_start_estimate_ms": round(cold_est, 2),
        "steady_state_median_ms": round(warm_med, 2),
        "cold_vs_warm_ratio": ratio,
        "cold_after_60s_pause_ms": cold["elapsed_ms"],
        "cold_after_60s_status": cold["status"],
        "first_3_ms": [round(x, 2) for x in first_3],
        "last_10_ms": [round(x, 2) for x in last_10],
        "p95_ms": round(percentile(samples, 95), 2),
        "p99_ms": round(percentile(samples, 99), 2),
        "notes": "30 sequential POST /auth, 1s apart; then 60s pause + 1 call. Sandbox shared, conservative load.",
    }
    payload = summarize_latency(samples, endpoint="POST /auth", scenario=SCENARIO, extra=extra)

    lat_path = write_latency_json(payload, "post_auth_cold_warm.json")
    log_path = write_scenario_log(SCENARIO, payload)
    print(f"[{SCENARIO}] -> latency: {lat_path}")
    print(f"[{SCENARIO}] -> scenario:  {log_path}")
    print(
        f"[{SCENARIO}] cold(first3)={cold_est:.1f}ms  warm(last10)={warm_med:.1f}ms  "
        f"ratio={ratio}  cold@60s={cold['elapsed_ms']:.1f}ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
