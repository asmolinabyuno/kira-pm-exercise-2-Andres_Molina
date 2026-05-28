"""Collect latency baselines for Batch B endpoints (N>=10).

Endpoints baselined:
  GET  /v1/users/{userId}                 — read the DRIFT-3 user 10x
  POST /v1/users/{userId}/verifications   — fire 10x against the DRIFT-3 user
                                            (each gets a fresh idempotency-key
                                             so we measure non-cached latency)
  PUT  /v1/users/{userId}                 — 10x metadata-only updates

Outputs (one file per endpoint) under ``evidence/work/latency/``:
  get_v1_users_id.json
  post_v1_users_id_verifications.json
  put_v1_users_id.json
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

import httpx  # noqa: E402

from run_flow import API_KEY, BASE_URL, auth  # noqa: E402


USER_ID = "ae80515c-2d59-4e02-9678-0bcfd6e9a188"
N = 10


def _headers(token: str, idem: str | None = None) -> dict:
    h = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
    }
    if idem:
        h["Idempotency-Key"] = idem
    return h


def write_baseline(name: str, samples: List[float], notes: str) -> Path:
    out_dir = WORK / "latency"
    out_dir.mkdir(parents=True, exist_ok=True)
    s_sorted = sorted(samples)

    def percentile(p: float) -> float:
        if not s_sorted:
            return 0.0
        idx = max(0, min(len(s_sorted) - 1, int(round((p / 100.0) * (len(s_sorted) - 1)))))
        return round(s_sorted[idx], 2)

    payload = {
        "endpoint": name,
        "n": len(samples),
        "samples_ms": [round(s, 2) for s in samples],
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "median_ms": round(statistics.median(samples), 2),
        "p50_ms": percentile(50),
        "p95_ms": percentile(95),
        "p99_ms": percentile(99),
        "mean_ms": round(statistics.mean(samples), 2),
        "stdev_ms": round(statistics.stdev(samples), 2) if len(samples) > 1 else 0.0,
        "notes": notes,
    }
    slug = name.lower().replace("/", "_").replace(" ", "_").replace("{", "").replace("}", "")
    out = out_dir / f"{slug}.json"
    out.write_text(json.dumps(payload, indent=2))
    return out


def main() -> int:
    print(f"Latency probe — N={N} per endpoint")
    token = auth()
    if not token:
        print("AUTH FAILED", file=sys.stderr)
        return 1
    print("AUTH OK")

    # 1) GET /v1/users/{id}
    samples_get: List[float] = []
    url = f"{BASE_URL}/v1/users/{USER_ID}"
    for i in range(N):
        t0 = time.perf_counter_ns()
        resp = httpx.get(url, headers=_headers(token), timeout=30.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        samples_get.append(elapsed_ms)
        print(f"  GET #{i+1}: {elapsed_ms:.2f}ms status={resp.status_code}")
    p = write_baseline(
        "GET /v1/users/id",
        samples_get,
        f"N={N} sequential GETs against DRIFT-3 user. No idempotency on GET. Sandbox warm path.",
    )
    print(f"  saved: {p.relative_to(WORK.parent)}")

    # 2) POST /v1/users/{id}/verifications — fresh idem each time
    samples_post: List[float] = []
    url = f"{BASE_URL}/v1/users/{USER_ID}/verifications"
    for i in range(N):
        idem = str(uuid.uuid4())
        body = {"type": "embedded-link", "redirect_uri": f"https://example.com/lat-{i}"}
        t0 = time.perf_counter_ns()
        resp = httpx.post(url, headers=_headers(token, idem), json=body, timeout=30.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        samples_post.append(elapsed_ms)
        print(f"  POST /verifications #{i+1}: {elapsed_ms:.2f}ms status={resp.status_code}")
    p = write_baseline(
        "POST /v1/users/id/verifications",
        samples_post,
        f"N={N} fresh idempotency keys (no cached replays) — each provisions a new AiPrise session. "
        "Includes the partner-side session-create roundtrip; higher latency than vanilla CRUD.",
    )
    print(f"  saved: {p.relative_to(WORK.parent)}")

    # 3) PUT /v1/users/{id} — metadata-only
    samples_put: List[float] = []
    url = f"{BASE_URL}/v1/users/{USER_ID}"
    for i in range(N):
        # NOTE: metadata values must be STRINGS — DRIFT-B7 finding.
        body = {"metadata": {"latency_probe": "true", "i": str(i), "ts": str(int(time.time()))}}
        t0 = time.perf_counter_ns()
        resp = httpx.put(url, headers=_headers(token), json=body, timeout=30.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        samples_put.append(elapsed_ms)
        print(f"  PUT #{i+1}: {elapsed_ms:.2f}ms status={resp.status_code}")
    p = write_baseline(
        "PUT /v1/users/id",
        samples_put,
        f"N={N} metadata-only updates (non-sensitive — should not trigger reverification). "
        "PUT has no Idempotency-Key — implicitly idempotent.",
    )
    print(f"  saved: {p.relative_to(WORK.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
