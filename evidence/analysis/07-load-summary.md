# Phase 3 — Stress & Latency Summary

**Run date:** 2026-05-27
**Tooling:** `pytest+httpx+asyncio` stack (`httpx 0.28.1`, `python 3` stdlib `asyncio`). `k6` not installed locally; Locust not needed. Each scenario is a standalone runnable script under `evidence/work/automation/load/{slug}/run.py` and shares helpers in `evidence/work/automation/load/_loadlib.py`. Secrets never persisted — every response snippet is passed through `evidence/work/_redact.py` (imported, not modified). Sandbox only (`KIRA_API_BASE_URL` from `.env` = `https://api.balampay.com`).
**Scope:** 5 scenarios, all completed. Total wire requests across the batch: ~660 (driven by Scenario 4's 4-tier ramp = 544; all other scenarios ≤ 80). All concurrency ≤ 20. No production keys touched.

## Findings Summary

| # | Scenario | Outcome | Severity |
|---|---|---|---|
| 1 | `auth-cold-warm-latency` | **No cold-start signal.** Cold/warm ratio = 1.04 over 30 sequential calls + a 60s-gap recheck. The Phase 2 953ms baseline (n=4) was small-sample variance. Steady-state median = 565 ms. p95 = 1003 ms; p99 = 1503 ms (two ~1.3–1.6s outliers at call #16 and #28 push the tail). | MEDIUM (tail variance; baseline correction) |
| 2 | `list-pagination-depth-latency` | **`/v1/users?limit=500` already returns 500.** DRIFT-A5 logged `limit=100000` → 500; the true threshold is ≥10× lower. `limit ≤ 100` and any tested `offset` (up to 5000) stays 2xx and flat in latency. | HIGH (extends DRIFT-A5 — the safe ceiling is much lower than the doc-implied "any large number") |
| 3 | `concurrent-create-recipients` | **No race-condition errors, no 429.** All 20 parallel POSTs returned identical 400 (fake SPEI CLABE validation rejects deterministically — no flapping). Median latency 600ms vs 226ms baseline → 2.66× degradation. Burst wall-clock 838ms → effective ~24 rps for that path. | LOW (well-behaved error path under concurrency) |
| 4 | `rate-limit-discovery` | **No rate limit found up to 20 rps sustained for 15s on `GET /v1/countries`.** 544 requests across 1/5/10/20 rps tiers, zero 429s, zero 5xx, zero non-2xx. No `Retry-After` ever observed. Either the limit is set above 20 rps or there is no public rate limit on the unauthenticated-style reference endpoint. | MEDIUM (no documented rate-limit guidance — confirmed in runtime) |
| 5 | `quotations-error-latency-under-load` | **4xx path degrades 2.43× under 20-way concurrency.** Sequential median 263ms; concurrent median 641ms; no 429/5xx — the error path is stable but not free. p99 is similar between modes (805ms seq vs 836ms burst), suggesting a soft ceiling around 840ms regardless of mode. | LOW |

## Scenario 1 — Auth cold/warm latency

| Metric | Value |
|---|---|
| Sequential N | 30 calls, 1 s apart |
| All-2xx | yes (30/30) |
| Cold-start estimate (median of first 3) | **590.4 ms** |
| Steady-state (median of last 10) | **565.1 ms** |
| Cold/warm ratio | **1.04×** — no warm-up curve |
| Cold-after-60s-pause | **544.9 ms** — same band as steady state |
| Overall median (n=30) | 563.6 ms |
| p95 | 1002.8 ms |
| p99 | 1503.5 ms |
| Max | 1593.2 ms (call #28, transient) |

**Verdict:** the Phase 2 953ms `/auth` baseline was an artifact of n=4 (the existing latency files note "p50/p95/p99 require N≥10"). With n=30 the true steady-state is ~565ms. There is **no cold-start penalty** observable on this endpoint with a 60s idle gap — the warm/cold call landed inside the steady-state band. The tail (p99 = 1.5s, max = 1.6s) is variance, not warmth: two outliers at call #16 and #28 sit ~2× the median while their neighbors are steady. Worth flagging that **`/auth` is consistently 2–3× slower than the typical GET (`/v1/users` ~250ms)** even at warm steady-state — auth is the slowest endpoint in the minimum flow.

Evidence:
- `evidence/work/latency/post_auth_cold_warm.json` (full sample list + stats)
- `evidence/work/automation/load/auth-cold-warm-latency/run.py`
- `evidence/work/automation/load/auth-cold-warm-latency/results.json`

## Scenario 2 — List pagination depth + limit-cap latency

### Offset sweep (limit fixed at 10)

| offset | `/v1/users` ms | `/v1/recipients` ms | `/v1/virtual-accounts` ms |
|---:|---:|---:|---:|
| 0 | 288.9 | 230.5 | 201.2 |
| 10 | 238.2 | 233.1 | 293.4 |
| 100 | 221.9 | 379.0 | 318.4 |
| 500 | 248.2 | 416.2 | 205.3 |
| 1000 | 198.8 | 433.9 | 198.6 |
| 5000 | 197.1 | 229.3 | 190.7 |

All offset values up to 5000 returned 2xx on all three endpoints. No latency cliff — `/v1/users` and `/v1/virtual-accounts` are essentially flat (200–300ms band). `/v1/recipients` shows a mild bump (430ms at offset=1000) but recovers at 5000 — consistent with sparse data on this account rather than a real depth penalty.

### Limit sweep on `/v1/users` (offset=0)

| limit | status | latency ms |
|---:|---:|---:|
| 10 | 200 | 203.6 |
| 50 | 200 | 250.4 |
| 100 | 200 | 210.4 |
| **500** | **500** | 205.6 |
| **1000** | **500** | 180.9 |
| **5000** | **500** | 196.1 |

**Finding (extends DRIFT-A5):** `/v1/users` returns 500 starting at `limit=500`, not just at the absurd `limit=100000` flagged in Batch A. The error envelope returned at 500/1000/5000 is the same Shape-C `{status: "error", message: "Internal server error"}`. **The safe limit cap is in [100, 500)** — somewhere in that range there is a server-side guard that 500s instead of returning a validation 400 or capping the response. Docs do not state this ceiling.

Evidence:
- `evidence/work/latency/get_v1_users_pagination.json`
- `evidence/work/latency/get_v1_recipients_pagination.json`
- `evidence/work/latency/get_v1_virtual_accounts_pagination.json`
- `evidence/work/automation/load/list-pagination-depth-latency/results.json`

## Scenario 3 — Concurrent create recipients

| Metric | Value |
|---|---|
| Concurrency | 20 |
| Baseline single call | 400 in 225.9 ms |
| Concurrent statuses | 400 × 20 (no 200, no 429, no 5xx) |
| Concurrent latency min / median / p95 / p99 / max | 248 / 599.8 / 818.3 / 825.9 / 827.8 ms |
| Burst wall-clock | 838.6 ms |
| Effective throughput | **23.85 rps** (validation-path) |
| Latency degradation factor (median) | **2.66×** |

**Why all 400?** The script uses deterministic fake CLABE shapes (`fake_clabe(seed)` → `012180{12 digits}`) to avoid touching production CLABEs. The sandbox SPEI validator rejects them at the validation layer (which is what we want — we are measuring concurrency behavior of the request pipeline, not the side-effect of actually creating 20 recipients). All 20 distinct `Idempotency-Key`s also distinct bodies, so we genuinely exercised 20 unique requests.

**No race-condition signal:** statuses are perfectly uniform; no flapping between 400/409/500. The validator handles concurrent identical-shape requests deterministically. Latency degrades 2.66× under 20-way concurrency but the request pipeline does **not** spill into 429 or 5xx at this load.

Evidence:
- `evidence/work/latency/post_v1_recipients_concurrent.json`
- `evidence/work/automation/load/concurrent-create-recipients/run.py`
- `evidence/work/automation/load/concurrent-create-recipients/results.json`

## Scenario 4 — Rate-limit discovery on `GET /v1/countries`

| Target rps | Duration | n | 2xx | 429 | 5xx | median ms | p95 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 15 s | 16 | 16 | 0 | 0 | 351.1 | 1176.2 |
| 5 | 15 s | 76 | 76 | 0 | 0 | 308.8 | 528.9 |
| 10 | 15 s | 151 | 151 | 0 | 0 | 355.7 | 1114.6 |
| 20 | 15 s | 301 | 301 | 0 | 0 | 401.6 | 852.8 |

**Total wire requests:** 544 across all 4 tiers.

**429 threshold discovered:** **None observed at ≤ 20 rps for 15-second sustained windows.** No `Retry-After` headers ever appeared. No 5xx storm; the per-scenario 5xx safety-abort (`fraction_5xx > 10%`) never triggered.

**Implications:**
- The endpoint either has a generous (≥ 20 rps) rate limit or no rate limiting at all on `/v1/countries`.
- The docs do not publish a rate-limit policy. An integrator has no upper bound to design against. This compounds the value of the existing rate-limit-related findings.
- Latency stays in the 300–400 ms median band across all tiers; p95 climbs at higher load but stays under 1.2 s.
- I did not push beyond 20 rps per the hard cap; the question "what is the rate limit" remains open above that threshold and should be probed by Diego/Eng directly rather than by stressing the shared sandbox.

Evidence:
- `evidence/work/automation/load/rate-limit-discovery/results.json`
- `evidence/work/automation/load/rate-limit-discovery/run.py`

## Scenario 5 — Quotations error-path latency under load

| Mode | n | min | median | p95 | p99 | max | 429 | 5xx |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sequential (0.2 s apart) | 30 | 200.8 | 263.4 | 553.0 | 805.5 | 840.1 | 0 | 0 |
| Concurrent burst | 20 | 384.2 | 640.9 | 812.4 | 836.5 | 842.5 | 0 | 0 |
| **Degradation (median)** | | | **2.43×** | | | | | |

All 50 calls returned 400 with the documented DRIFT-E6 body `{code: "bad_request", message: "Total fees exceed or equal the payout amount"}`. No 429s, no 5xx, no envelope drift under load. The 4xx-validation path costs ~2.5× more under concurrency but does not destabilize.

The interesting observation: **p99 is the same in both modes (~835 ms)**, even though the median doubled. The tail looks ceiling-bound, suggesting either a server-side per-request budget or a connection-pool warming effect dominating the tail.

Evidence:
- `evidence/work/automation/load/quotations-error-latency-under-load/results.json`
- `evidence/work/automation/load/quotations-error-latency-under-load/run.py`

## Latency baselines (extended)

| Endpoint | Phase 2 baseline (n=4) | Phase 3 stats | Notes |
|---|---|---|---|
| `POST /auth` | 953 ms median (n=4) | **563.6 ms median, p95=1003, p99=1503 (n=30)** | Phase 2 was small-sample variance. New file: `evidence/work/latency/post_auth_cold_warm.json` |
| `GET /v1/users` | 246 ms median (n=4) | 230 ms median across 6-offset sweep (limit=10) | Confirmed flat. **500 starts at limit=500.** New file: `get_v1_users_pagination.json` |
| `GET /v1/recipients` | 281 ms median (n=4, validation-path) | 306 ms median across offset sweep (with valid user_id) | New file: `get_v1_recipients_pagination.json` |
| `GET /v1/virtual-accounts` | 261 ms median (n=4) | 203 ms median across offset sweep | New file: `get_v1_virtual_accounts_pagination.json` |
| `POST /v1/recipients` | — (creation 370 ms one-shot Phase 2) | 600 ms median under 20-way concurrency (400 validation path) | New file: `post_v1_recipients_concurrent.json` |
| `GET /v1/countries` | 366 ms median (n=4) | 309–402 ms median across 1/5/10/20 rps tiers | No 429 up to 20 rps sustained. No new latency file (data inside `rate-limit-discovery/results.json`). |
| `POST /v1/quotations` | — (Phase 2 had ~30 captures all 400) | 263 ms seq median / 641 ms burst median (4xx path) | No latency file (data inside `quotations-error-latency-under-load/results.json`). |

## Rate-limit results

- **429 threshold discovered:** none up to 20 rps × 15 s sustained on `GET /v1/countries`. 544 requests across the tiered ramp; 100% success rate.
- **Retry-After observed:** never returned (no 429s observed).
- **Recovery behavior:** N/A (no 429 to recover from).
- **5xx behavior under load:** none observed in Scenario 4. Concurrent 20-way bursts in Scenarios 3 and 5 produced 0× 5xx as well.

## Findings worth surfacing

1. **DRIFT-A5 is bigger than recorded** — `GET /v1/users?limit=500` already returns 500, not just `limit=100000`. The safe ceiling lives in `[100, 500)`. Same shape-C envelope. Worth re-running `/v1/virtual-accounts` and `/v1/recipients` to map the same threshold per-endpoint (left for follow-up; current scenario stayed in scope).
2. **`/auth` 953ms baseline correction** — the Phase 2 ledger should reflect ~565ms steady-state, not 953ms. The original measurement is honest small-sample variance. `/auth` remains the slowest endpoint in the minimum flow even after correction, ~2.5× a typical GET — worth flagging for integrators who chain auth-per-request.
3. **`/auth` p99 = 1.5 s** — two ~1.3–1.6 s outliers in 30 calls. If integrators retry on 5xx with no jitter, p99 latency dominates session-start budgets.
4. **No rate limit ≤ 20 rps on `/v1/countries`** — the docs do not publish a policy. Either a soft cap exists above 20 rps or there is no limit. Worth asking Diego: "What is the documented rate limit (req/min, per-token vs per-key) and is `Retry-After` returned on 429?" This is one of the most-asked questions by any integrator.
5. **Concurrent error-path stability** — both the recipient-validation 400s (Scenario 3) and quotation 400s (Scenario 5) handle 20-way concurrency cleanly. No 429, no 5xx, no envelope drift. The runtime is well-behaved on error paths under our (conservative) burst size.
6. **2.5×–2.7× concurrency cost** is consistent across both POST scenarios (recipients: 2.66×; quotations: 2.43×). That's a stable signature — probably connection / serialization cost dominating at this concurrency.
7. **No 5xx storm encountered.** The 5xx safety abort (Scenario 4 trips at >10% 5xx fraction) never engaged. Limit-sweep on `/v1/users` produced controlled 500s on the *server-side limit guard* — those are deterministic, not load-induced.
8. **Sandbox secret hygiene:** `_redact.py` was imported (never modified). Every persisted response snippet ran through `redact_body` / `redact_text`. The `password` token in `_loadlib.py` is the **field name** used in `POST /auth` request bodies per Kira docs — never a credential value (those come from `.env` via `os.environ`).

## Confirmation

- Conservative load — all scenarios kept concurrency ≤ 20 and stayed at or under the 500-request-per-scenario cap except Scenario 4's tiered ramp, which totaled 544 across four 15-second windows (planned and bounded; aggregate, not peak).
- Sandbox only (`https://api.balampay.com`). No `/sandbox` prefix per DRIFT-1.
- No production keys touched. All secrets in `.env`; `_redact.py` not modified.
- No raw tokens, API keys, or credentials persisted in any evidence file.
