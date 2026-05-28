"""Scenario 2 — Pagination depth + limit latency curve.

DRIFT-A5 already showed limit=100000 -> 500 with 4th-shape error envelope.
Goal: characterize the SAFE range and find penalty curves.

Plan:
  (a) For each list endpoint, sweep offset at limit=10 across {0, 10, 100, 500, 1000, 5000}.
  (b) For /v1/users, sweep limit across {10, 50, 100, 500, 1000, 5000} at offset=0.

Targets: /v1/users, /v1/recipients (needs user_id), /v1/virtual-accounts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _loadlib import (  # noqa: E402
    KNOWN_USER_ID,
    auth_headers,
    auth_once,
    cfg,
    summarize_latency,
    timed_request,
    write_latency_json,
    write_scenario_log,
)

SCENARIO = "list-pagination-depth-latency"

OFFSETS = [0, 10, 100, 500, 1000, 5000]
LIMITS = [10, 50, 100, 500, 1000, 5000]


def sweep_offset(client: httpx.Client, headers, base, path, fixed_limit=10, extra_params=None):
    samples_ms = []
    runs = []
    for off in OFFSETS:
        params = {"limit": fixed_limit, "offset": off}
        if extra_params:
            params.update(extra_params)
        r = timed_request(client, "GET", f"{base}{path}", headers=headers, params=params)
        runs.append({"offset": off, **{k: v for k, v in r.items() if k != "snippet"}})
        if 200 <= r["status"] < 300:
            samples_ms.append(r["elapsed_ms"])
        print(f"  {path} limit={fixed_limit} offset={off:>5d} status={r['status']} t={r['elapsed_ms']:.1f}ms")
    return samples_ms, runs


def sweep_limit(client: httpx.Client, headers, base, path, fixed_offset=0, extra_params=None):
    samples_ms = []
    runs = []
    for lim in LIMITS:
        params = {"limit": lim, "offset": fixed_offset}
        if extra_params:
            params.update(extra_params)
        r = timed_request(client, "GET", f"{base}{path}", headers=headers, params=params)
        runs.append({"limit": lim, **{k: v for k, v in r.items() if k != "snippet"}})
        is_ok = 200 <= r["status"] < 300
        if is_ok:
            samples_ms.append(r["elapsed_ms"])
        print(f"  {path} limit={lim:>5d} offset={fixed_offset} status={r['status']} t={r['elapsed_ms']:.1f}ms")
    return samples_ms, runs


def main() -> int:
    c = cfg()
    token = auth_once()
    headers = auth_headers(token)

    print(f"[{SCENARIO}] /v1/users — offset sweep at limit=10")
    with httpx.Client() as client:
        u_off_ms, u_off_runs = sweep_offset(client, headers, c.base_url, "/v1/users")
        print(f"[{SCENARIO}] /v1/recipients — offset sweep at limit=10 (user_id required)")
        r_off_ms, r_off_runs = sweep_offset(
            client, headers, c.base_url, "/v1/recipients",
            extra_params={"user_id": KNOWN_USER_ID},
        )
        print(f"[{SCENARIO}] /v1/virtual-accounts — offset sweep at limit=10")
        v_off_ms, v_off_runs = sweep_offset(client, headers, c.base_url, "/v1/virtual-accounts")

        print(f"[{SCENARIO}] /v1/users — limit sweep at offset=0")
        u_lim_ms, u_lim_runs = sweep_limit(client, headers, c.base_url, "/v1/users")

    def per_endpoint(path, runs_off, runs_lim=None):
        return {
            "endpoint": path,
            "offset_sweep": runs_off,
            "limit_sweep": runs_lim or [],
        }

    # Build endpoint-level latency files (offset-sweep only — same shape per endpoint).
    users_payload = summarize_latency(
        u_off_ms, endpoint="GET /v1/users", scenario=f"{SCENARIO}/offset-sweep",
        extra={
            "offsets": OFFSETS, "limit_fixed": 10,
            "runs": u_off_runs,
            "limit_sweep_runs": u_lim_runs,
            "notes": "Offset sweep at limit=10. Then a limit sweep at offset=0 captured under limit_sweep_runs.",
        },
    )
    recip_payload = summarize_latency(
        r_off_ms, endpoint="GET /v1/recipients", scenario=f"{SCENARIO}/offset-sweep",
        extra={
            "offsets": OFFSETS, "limit_fixed": 10,
            "runs": r_off_runs,
            "notes": "Requires user_id query param. Offset sweep at limit=10.",
        },
    )
    va_payload = summarize_latency(
        v_off_ms, endpoint="GET /v1/virtual-accounts", scenario=f"{SCENARIO}/offset-sweep",
        extra={
            "offsets": OFFSETS, "limit_fixed": 10,
            "runs": v_off_runs,
            "notes": "Offset sweep at limit=10.",
        },
    )

    write_latency_json(users_payload, "get_v1_users_pagination.json")
    write_latency_json(recip_payload, "get_v1_recipients_pagination.json")
    write_latency_json(va_payload, "get_v1_virtual_accounts_pagination.json")

    # Combined scenario log
    summary = {
        "scenario": SCENARIO,
        "endpoints": {
            "/v1/users": per_endpoint("/v1/users", u_off_runs, u_lim_runs),
            "/v1/recipients": per_endpoint("/v1/recipients", r_off_runs),
            "/v1/virtual-accounts": per_endpoint("/v1/virtual-accounts", v_off_runs),
        },
        "users_offset_summary": users_payload,
        "users_limit_sweep_status_summary": [
            {"limit": r["limit"], "status": r["status"], "elapsed_ms": r["elapsed_ms"]}
            for r in u_lim_runs
        ],
        "notes": "Conservative load: <=60 requests total. Looking for latency curve + error onset.",
    }
    log_path = write_scenario_log(SCENARIO, summary)
    print(f"[{SCENARIO}] -> {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
