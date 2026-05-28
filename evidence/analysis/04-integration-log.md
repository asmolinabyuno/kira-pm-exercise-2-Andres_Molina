# Integration Log — Phase 2 Difficulty Telemetry

**Status:** IN PROGRESS — 18/30 endpoints probed (count distinct canonical endpoints across all batches; `GET /v1/recipients` appears in both Batch A and Batch C and is counted once)
**Drift events captured:** 53
**Last merge:** 2026-05-27 (DEC-006 closeout, 5 parallel batch logs consolidated)

Per-endpoint difficulty KPIs captured during Phase 2 empirical integration.

**Methodology** (per DEC-002):
- Iteration count starts at **1** on the first attempt. Increment on each non-2xx response. Stop at first 2xx or after 3 failures.
- Doc sufficiency: **YES** (docs alone got us to 2xx on attempt 1) · **PARTIAL** (docs got us close; we had to guess something) · **NO** (insufficient; required out-of-band escalation/knowledge).
- Drift event = any runtime fact that contradicts the documentation. One DRIFT-N entry per contradiction with an evidence path.
- Latency: single-call elapsed for now. p50/p95/p99 are captured separately in `evidence/work/latency/<endpoint>.json` once N≥10 baselines are collected for each endpoint.

## Per-endpoint table (master)

| # | Method | Path | Family | Iter to 2xx | Doc sufficiency | Drift events | Latency median (ms) | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | POST | `/auth` | Auth | 2 | PARTIAL | DRIFT-1, 2 | 953 | Pre-batch. DRIFT-1 base URL global. |
| 2 | POST | `/v1/users` (create business) | Users | 1 | PARTIAL (request shape) | DRIFT-3, 4, 5 | 299 (n=4) | Pre-batch. DRIFT-3 root cause resolved in DRIFT-19 (Batch B B6). |
| 3 | GET | `/v1/countries` | RefData | 1 | PARTIAL | DRIFT-6 (=A1), 11 (=A6) | 366 | Batch A. No reference example (GAP-30 confirmed). Alpha-3 codes echoed. |
| 4 | GET | `/v1/banks` | RefData | 2 | NO | DRIFT-6, 7, 8, 9, 12 | 268 | Batch A. `country_code=CO` only — Colombia-only at runtime. |
| 5 | GET | `/v1/users` (list) | Users | 1 | PARTIAL | DRIFT-6, 10, 11 | 247 | Batch A. `?limit=100000` → 500. List echoes both `US` and `USA`. |
| 6 | GET | `/v1/virtual-accounts` (list) | VA | 1 | PARTIAL | DRIFT-6, 10 | 261 | Batch A. Empty `data[]`; same 500 on `limit=100000`. |
| 7 | GET | `/v1/recipients` (list) | Recipients | n/a (400 by design) | PARTIAL | DRIFT-6, 13 | 281 (validation path) | Batch A — needs `user_id`. Batch C confirmed envelope `{recipients, total}`. |
| 8 | GET | `/v1/users/{userId}` | Users | 1 | PARTIAL | DRIFT-14 | 339.8 (n=10), p95 642 | Batch B. `verification_triggered` field missing on GET. |
| 9 | PUT | `/v1/users/{userId}` | Users | 3 | NO | DRIFT-15, 19, 20 | 351.2 (n=10), p95 498 | Batch B. Empty body → 200 (not 400). Metadata must be strings. |
| 10 | POST | `/v1/users/{userId}/verifications` | Verification | 1 | PARTIAL | DRIFT-16, 17 | 440.0 (n=10), p95 532 | Batch B. Idempotency NOT enforced; does not move state machine. |
| 11 | POST | `/verification/send` | Verification | 2 | NO | DRIFT-21 | 251 (n=1) | Batch B. GAP-23 resolved — path is root, not `/v1/`. Keyed on email. |
| 12 | POST | `/v1/users` (mass-assignment probe) | Users | 1 | NO | DRIFT-22 | 200 | Batch B. `status` enum input `active\|inactive\|suspended` — third enum. |
| 13 | POST | `/v1/users` (zero-missing trigger) | Users | 2 | NO | (resolves DRIFT-3) | 201 | Batch B. Adds occupation → `verification_triggered: TRUE`. |
| 14 | POST | `/v1/recipients` (SPEI MX) | Recipients | 1 | YES (SPEI only) | DRIFT-31, 32 | 370.0 | Batch C. |
| 15 | POST | `/v1/recipients` (ACH USD) | Recipients | 2 | NO | DRIFT-27, 28 | 276.0 | Batch C. `doc_type:"ssn"` rejected — enum is `id\|dni\|passport\|ein`. |
| 16 | POST | `/v1/recipients` (USDT TRON) | Recipients | 2 | PARTIAL | DRIFT-29 | 247.0 | Batch C. base58check validated. |
| 17 | POST | `/v1/recipients` (SWIFT EUR) | Recipients | 2 | NO | DRIFT-27, 30, 33 | 277.9 | Batch C. SWIFT also requires recipient-level address; POST loses state/postal_code. |
| 18 | GET | `/v1/recipients?user_id=…` | Recipients | 1 | PARTIAL | DRIFT-34 | 279.8 | Batch C. Envelope `{recipients, total}` — third list-envelope shape. |
| 19 | GET | `/v1/recipients/{id}` (4 variants) | Recipients | 1 | PARTIAL | DRIFT-31, 33 | 251.6 | Batch C. Unmasked; SWIFT detail correct (POST/GET divergence). |
| 20 | POST | `/v1/recipients` (idem-replay/conflict/omit) | Recipients | 1 | NO | DRIFT-35, 36, 37 | 249.1 | Batch C. 201 not 202 on replay; empty 409 details; two envelopes on same endpoint. |
| 21 | POST | `/v1/recipients` (mutation probes) | Recipients | 1 | (probe) | DRIFT-38, 39 | 284.6 | Batch C. Extra fields silently stripped; country silently overridden. |
| 22 | DELETE | `/v1/recipients/{id}` | Recipients | n/a | (probe) | DRIFT-40 | 250.8 | Batch C. 403 with AWS SigV4 leak; recipient still exists after. |
| 23 | POST | `/v1/quotations` (Guides shape) | Quotations | ∞ (unreachable) | NO | DRIFT-41, 45 | n/a (4xx only) | Batch E. Guides body silently dropped — GAP-31 confirmed. |
| 24 | POST | `/v1/quotations` (Reference shape) | Quotations | 0/22 (blocked at fee layer) | PARTIAL | DRIFT-42, 43, 44, 46, 47 | n/a (4xx only) | Batch E. Schema passes; sandbox fee profiles ≥100% block all. |
| 25 | POST | `/webhooks/register` | Webhooks | 1 (docs body) / 2 (brief path) | NO | DRIFT-47..53 | 400 (n=16) | Batch G. Path has no `/v1/`. SSRF surface, no idempotency, opaque response. |
| 26 | POST | `/v1/webhooks/register` | Webhooks | n/a | n/a | DRIFT-52 | n/a | Batch G. 403 — route does not exist. |
| 27 | GET | `/webhooks` / `/v1/webhooks` / `/webhooks/{id}` | Webhooks | n/a | n/a | (GAP-21 confirmed) | n/a | Batch G. All 403 — no list, no get, no delete. |
| 28 | DELETE | `/webhooks/{id}` | Webhooks | n/a | n/a | (GAP-21 confirmed) | n/a | Batch G. Untestable — no id from register. |

**Endpoints touched (distinct canonical):** 18 (POST `/auth`, POST `/v1/users` (create), GET `/v1/users/{id}`, PUT `/v1/users/{id}`, GET `/v1/countries`, GET `/v1/banks`, GET `/v1/users` (list), GET `/v1/virtual-accounts`, GET `/v1/recipients` (list — counted once), POST `/v1/recipients` (4 variants = 1 endpoint), GET `/v1/recipients/{id}`, DELETE `/v1/recipients/{id}`, POST `/v1/quotations`, POST `/v1/users/{id}/verifications`, POST `/verification/send`, POST `/webhooks/register`, GET `/webhooks` (attempted), DELETE `/webhooks/{id}` (attempted)).

---

## Drift events detail (master, renumbered)

### DRIFT-1 — Documented `/sandbox` stage prefix returns 403 for `/auth` (base URL global lie)
- **Doc claim:** `CLAUDE.md` § "Integration Target" and `flow-design.md` § 2.1 state sandbox base URL is `https://api.balampay.com/sandbox`. `.env` also set `KIRA_API_BASE_URL=https://api.balampay.com/sandbox`.
- **Runtime fact:** `POST https://api.balampay.com/sandbox/auth` returns **403 ForbiddenException** for every key combination. `POST https://api.balampay.com/auth` returns **200**.
- **Evidence:** `evidence/work/auth/01-fail-403.json`, `evidence/work/auth/02-success.json`.
- **Workaround:** `.env` `KIRA_API_BASE_URL` updated to `https://api.balampay.com`.

- **Revalidation 2026-05-28 — CONFIRMED, doc still wrong.** Triggered by the partner-distributed `kira-sandbox-integration-guide.docx` (received 2026-05-28; extracted to `/tmp/kira-sandbox-guide.txt`). The guide explicitly states sandbox base = `https://api.balampay.com/sandbox` AND defines a one-time "pin your account" call (`POST /sandbox/v1/versioning/upgrade` body `{"target_version":"2026-04-14"}`) which the guide claims unlocks subsequent requests and makes `X-Api-Version` optional. We ran a 6-probe revalidation (`evidence/work/probes/revalidate_drift_1.py`) to settle this empirically:
  - **Probe 2** `POST https://api.balampay.com/v1/versioning/upgrade` (no prefix) → **200** with body `{"previous_version":"2026-04-14","current_version":"2026-04-14"}` exactly as the guide claims. `evidence/work/versioning/01-pin-no-prefix-success.json`.
  - **Probe 3** `POST https://api.balampay.com/sandbox/v1/versioning/upgrade` (guide's URL verbatim) → **401 UnauthorizedException** `{message:"Unauthorized"}`. `evidence/work/versioning/02-pin-sandbox-prefix-fail-401.json`.
  - **Probe 4** `POST https://api.balampay.com/sandbox/auth` after the successful pin → still **403 ForbiddenException** (identical to original DRIFT-1 capture). `evidence/work/versioning/03-sandbox-auth-after-pin-fail-403.json`.
  - **Probe 5** `GET https://api.balampay.com/sandbox/v1/users?limit=1` with bearer + `X-Api-Version: 2026-04-14` after the successful pin → still **401 UnauthorizedException** (identical to original DRIFT-2 capture). `evidence/work/versioning/04-sandbox-users-after-pin-fail-401.json`.
- **Verdict:** DRIFT-1 stands. The version-pin endpoint exists, but it lives at the **no-prefix** base (`/v1/versioning/upgrade`), NOT at the `/sandbox` prefix the guide documents. Pinning does **not** unlock the `/sandbox` stage — `/sandbox/*` continues to return the same gateway-level 403/401 envelopes as before. The partner guide is wrong about base URL on BOTH the versioning endpoint AND on every subsequent endpoint it lists. Net effect: an integrator who copy-pastes any URL from the guide hits gateway errors on call #1.
- **New sub-finding (`DRIFT-1b`):** The version-pin endpoint itself was never publicly documented (not in Guides, not in API Reference) — only the partner guide mentions it. Even though it returned 200, the response is a no-op for our account (`previous_version == current_version == "2026-04-14"`). The guide's claim that this call makes `X-Api-Version` optional cannot be falsified without a "before/after" header probe, but it is moot because every call we run already omits the header anyway and is succeeding — so the pin was never doing real work for this account.

### DRIFT-2 — `/sandbox` prefix is wrong for `/v1/users` too (DRIFT-1 escalation, scope-widening)
- **Doc claim:** After DRIFT-1, open question: maybe `/sandbox` required for non-auth endpoints.
- **Runtime fact:** `https://api.balampay.com/v1/users` → 400 validation; `https://api.balampay.com/sandbox/v1/users` → 401 UnauthorizedException. Base URL is consistent — both at root.
- **Sub-observation:** `/sandbox/auth` → 403 ForbiddenException, `/sandbox/v1/users` → 401 UnauthorizedException. Same gateway, two error types.
- **Evidence:** `evidence/work/users/00-drift-probe-A.json`, `evidence/work/users/00-drift-probe-B.json`.

### DRIFT-3 — `verification_triggered: false` despite docs claiming auto-trigger
- **Doc claim:** `flow-design.md` § 3.2 — minimal payload auto-triggers KYB.
- **Runtime fact:** Minimal § 3.2.1 payload returned 201 with `verification_triggered: false` and 21 missing fields. **RESOLVED in DRIFT-19 (Batch B B6)** — trigger gate is `missing_fields: {}` for at least one product; published "minimal" omits `account_purpose`, `source_of_funds`, `employment_status`, `current_employer`, `occupation`.
- **Evidence:** `evidence/work/users/03-success.json`.

### DRIFT-4 — Undocumented response fields on `UserResponse`
- **Doc claim:** `flow-design.md` § 3.2 advertised `id`, `status`, `eligible_products[]`, `missing_fields{}`.
- **Runtime fact:** Server returns 15 top-level keys. Undocumented: `verification_mode: "automatic"`, `registered_address` (synthesized nested object with renamed fields — `subdivision` vs `address_state`, `street_line_1` vs `address_street`), `verification_status` (legacy lowercase vs modern uppercase), `associated_persons[]` echo.
- **Evidence:** `evidence/work/users/03-success.json`.

### DRIFT-5 — GAP-20 worse than predicted: alpha-2 and alpha-3 both accepted, neither normalized
- **Doc claim:** GAP-20 predicted alpha-2/alpha-3 mix would 404 or trigger silent revalidation.
- **Runtime fact:** Both `"USA"` and `"US"` accepted with 201. Server echoed back exactly as submitted. **No normalization.** Latent data-quality bomb.
- **Evidence:** `evidence/work/users/04-success-iso-probe-alpha3.json`, `evidence/work/users/05-success-iso-probe-alpha2.json`.

### DRIFT-6 — Three-shape (later four-shape) error envelope variance in 401/403/400/500 responses
- **Family:** Cross-cutting (Batch A)
- **Original ID:** DRIFT-A1
- **Doc claim:** GAP-03 / GAP-05 flag envelope inconsistency as predicted.
- **Runtime fact:** Four distinct error envelope shapes in one set of probes:
  - **Shape G (gateway):** `{message: "Forbidden"|"Unauthorized"}` + `x-amzn-errortype` header.
  - **Shape A (Zod):** `{error: "Invalid request data", details: [{path, message, code}]}`.
  - **Shape B (typed):** `{error: {code: "VALIDATION_ERROR", message, details: {}}}`.
  - **Shape C (internal):** `{status: "error", message: "Internal server error"}` (500).
- **Evidence:** `evidence/work/countries/02-fail-403-no-apikey.json`, `evidence/work/users-list/03-fail-401-no-bearer.json`, `evidence/work/banks/01-fail-400-v1-country-MX.json`, `evidence/work/recipients/15-fail-400-happy-no-user-id.json`, `evidence/work/users-list/06-fail-500-limit-100000.json`, `evidence/work/va-list/06-fail-500-limit-100000.json`.

### DRIFT-7 — `/banks` (no `/v1/` prefix) is documented but broken at runtime (GAP-32 resolved, worse than predicted)
- **Family:** Reference data (Batch A)
- **Original ID:** DRIFT-A2
- **Doc claim:** Reference page uses `GET /banks` (no `/v1/`).
- **Runtime fact:**
  - `GET /banks?country=MX` → HTTP 200 with Cloudflare 522 string body after ~20s.
  - `GET /banks?country=MX` with `x-api-key` only → HTTP 200 with body `"Blocked"` (CF WAF, 200 status).
  - `GET /v1/banks?country_code=CO` → HTTP 200 with valid `{banks:[...28...], total, country_code}`.
- **Severity:** Silent-success bug — copy-pasting docs path gets HTTP 200 with non-JSON body.
- **Evidence:** `evidence/work/banks/02-success-nov1-country-MX.json`, `evidence/work/banks/08-success-no-bearer.json`, `evidence/work/banks/14-success-v1-cc-CO.json`, `evidence/work/banks/20-success-nov1-cc-CO.json`.

### DRIFT-8 — `/v1/banks` accepts ONLY `country_code=CO` — Colombia-only at runtime
- **Family:** Reference data (Batch A)
- **Original ID:** DRIFT-A3
- **Doc claim:** GAP-20 implies multi-country `/banks` with alpha-2 ISO-3166.
- **Runtime fact:** `CO` → 200. `co`, `COL`, `MX`, `Colombia`, omitted → 400 `Only CO (Colombia) is supported at this time`. **Strict uppercase alpha-2 only.**
- **Implication:** SPEI/PSE/CLP/ARS payout flows cannot construct recipients via bank_code lookup at runtime.
- **Evidence:** `evidence/work/banks/14-success-v1-cc-CO.json`, `evidence/work/banks/15-fail-400-v1-cc-co-lower.json`, `evidence/work/banks/16-fail-400-v1-cc-COL-alpha3.json`, `evidence/work/banks/17-fail-400-v1-cc-MX.json`.

### DRIFT-9 — Query param name `country_code` not `country` on `/v1/banks`
- **Family:** Reference data (Batch A)
- **Original ID:** DRIFT-A4
- **Doc claim:** Some doc pages imply `country`.
- **Runtime fact:** `GET /v1/banks?country=MX` returns 400 with `details[0].path: "country_code"` — server rejects on missing `country_code` while ignoring the supplied `country`.
- **Evidence:** `evidence/work/banks/01-fail-400-v1-country-MX.json`.

### DRIFT-10 — `?limit=100000` returns HTTP 500 on `/v1/users` and `/v1/virtual-accounts`
- **Family:** Pagination (Batch A)
- **Original ID:** DRIFT-A5
- **Doc claim:** Pagination is `{limit, offset, total, has_more}`. No documented upper bound.
- **Runtime fact:** `limit=100000` triggers 500 Internal Server Error with body `{status:"error", message:"Internal server error"}` in ~241ms (validation-fast). `?offset=99999` returns gracefully as empty page. Server-side error has no `details`/`code` — integrator can only file support ticket via `x-amzn-requestid`.
- **Evidence:** `evidence/work/users-list/06-fail-500-limit-100000.json`, `evidence/work/va-list/06-fail-500-limit-100000.json`, contrast `evidence/work/users-list/07-success-offset-99999.json`.

### DRIFT-11 — `X-Api-Version: 2025-01-01` request header is silently echoed back, identical response body (GAP-01 extension)
- **Family:** Versioning (Batch A)
- **Original ID:** DRIFT-A6
- **Doc claim:** GAP-01 — no documented request-side version header.
- **Runtime fact:** Server accepts the header, echoes it back in response header `x-api-version`, body unchanged. Integrator pinning to an older version has false confidence — getting today's contract with a vanity header.
- **Evidence:** `evidence/work/countries/04-success-xver-2025-01-01.json`, `evidence/work/countries/05-success-xver-2026-04-14.json`, `evidence/work/users-list/04-success-xver-2025-01-01.json`, `evidence/work/users-list/05-success-xver-2026-04-14.json`.

### DRIFT-12 — `x-api-key` alone does not suffice for any Batch-A list endpoint (GAP-04 extension)
- **Family:** Auth (Batch A)
- **Original ID:** DRIFT-A7
- **Doc claim:** GAP-04 — some endpoints documented as Bearer-OR-API-key.
- **Runtime fact:** Across all 5 Batch-A endpoints, omitting `Authorization: Bearer` (with valid `x-api-key`) returns 401 UnauthorizedException. Only `POST /webhooks/register` was previously thought to be API-key-only — see DRIFT-49 for the inversion there.

### DRIFT-13 — `/v1/recipients` returns Shape B error envelope, different from `/v1/users` Shape A
- **Family:** Error envelopes (Batch A)
- **Original ID:** DRIFT-A8
- **Doc claim:** GAP-03 — envelope variance predicted.
- **Runtime fact:** Same 400 status, two different shapes. Users uses flat `details: []`; recipients uses nested `details: {}` with `code` field only in Shape B.
- **Evidence:** `evidence/work/recipients/15-fail-400-happy-no-user-id.json`, `evidence/work/recipients/22-fail-404-junk-user-id.json`, `evidence/work/banks/01-fail-400-v1-country-MX.json`.

### DRIFT-14 — `verification_triggered` field disappears on `GET /v1/users/{id}`
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B1
- **Doc claim:** `flow-design.md` § 3.2 documents `verification_triggered` as part of `UserResponse`. Returned by POST.
- **Runtime fact:** GET against same user omits the key. Integrator must store client-side or re-issue PUT.
- **Evidence:** `evidence/work/users/12-batchB-get-initial.json` vs `evidence/work/users/03-success.json`.

### DRIFT-15 — `PUT /v1/users/{id}` with empty body returns 200 (not 400)
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B2
- **Doc claim:** § 3.2 PUT returns 200 with `updated_fields[]`.
- **Runtime fact:** `PUT {}` returns 200 with `updated_fields: []`, `requires_reverification: false`. No error.
- **Evidence:** `evidence/work/users/15-batchB-put-empty.json`.

### DRIFT-16 — Idempotency NOT enforced on `POST /v1/users/{id}/verifications`
- **Family:** Verification (Batch B)
- **Original ID:** DRIFT-B3
- **Doc claim:** § 2.4 lists endpoint as requiring `idempotency-key`. Same-key + diff body should 409.
- **Runtime fact:** Same key + two different `redirect_uri` → both 201 with different verification IDs (`fdb4…`, `4f7d…`). No 409. Same key + same body returns cached replay.
- **Severity:** HIGH. Billable if AiPrise charges per session.
- **Evidence:** `evidence/work/verification/01-post-verifications-idem-diff-1.json`, `02-idem-diff-2.json`.

### DRIFT-17 — `POST /v1/users/{id}/verifications` does NOT move the user state machine
- **Family:** Verification (Batch B)
- **Original ID:** DRIFT-B4
- **Doc claim:** § 3.2 implies it activates the verification flow; § 5.2 shows no state change.
- **Runtime fact:** Fired 3+ times against the DRIFT-3 user; status stayed `CREATED`/`unverified` for 2 minutes. Endpoint provisions an AiPrise hosted-link URL but doesn't advance state.
- **Evidence:** `evidence/work/verification/01-post-verifications-happy.json`, `evidence/work/verification/poll-drift3-*-success.json`.

### DRIFT-18 — `account_purpose` enum differs by user `type` (individual vs business)
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B5
- **Doc claim:** Field listed but values not enumerated.
- **Runtime fact:** Business → 400 with 18-value enum; individual → 400 with 14-value enum. Enums overlap but differ. Business-only: `operating_business_payments`, `receive_payments_for_goods_and_services`, `internal_treasury`, `third_party_money_transmission`, `receive_payment_for_freelancing`, `operating_a_company`. Individual-only: `manage_personal_funds`.
- **Evidence:** `evidence/work/users/13-batchB-put-complete-act.json`, `evidence/work/users/21-batchB-maximal-individual.json`.

### DRIFT-19 — `business_industry` is a NAICS-coded ARRAY enum (90+ values)
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B6
- **Doc claim:** Mentioned only in `missing_fields`. Not enumerated.
- **Runtime fact:** `"technology"` (string) → 400 `Expected array`. `["technology"]` → 400 with 90+ NAICS-coded values (`crop_production`, `data_processing_hosting_related_services`, etc.). US Census NAICS list, snake_cased, zero docs.
- **Evidence:** `evidence/work/users/22-batchB-maximal-business-act.json`, `evidence/work/users/24-batchB-zero-missing-business.json`.

### DRIFT-20 — `metadata` values must be strings (silent type constraint)
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B7
- **Doc claim:** `metadata` is opaque key-value.
- **Runtime fact:** PUT with `metadata: { "latency_probe": true }` → 400 `Expected string, received boolean`. Forces stringification.
- **Evidence:** `evidence/work/probes/batch_B_latency.py` first run output.

### DRIFT-21 — GAP-23 RESOLVED: OTP endpoint exists at `POST /verification/send` (root, not `/v1/`)
- **Family:** Verification (Batch B)
- **Original ID:** DRIFT-B8
- **Doc claim:** § 3.7 / GAP-23 named the endpoint without a reference page.
- **Runtime fact:** Path is `POST /verification/send` (no `/v1/`, like `/auth`). Body `{ "email": "<registered>" }` → 200 `{ success: true, message, expiresAt }`. `{ "client_uuid": "<user_id>" }` → 400 `Client not found` — `client_uuid` means TENANT, not user. Keyed on email, not user.
- **Side discovery:** Three other guessed paths returned 403 `IncompleteSignatureException` — exist at AWS gateway but require SigV4 (likely admin-only).
- **Evidence:** `evidence/work/verification/10-otp-send-probe-02-verification_send.json`, `evidence/work/verification/12-otp-send-email.json`.

### DRIFT-22 — Mass-assignment: `status` accepts LEGACY enum on input (different from output)
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B9
- **Doc claim:** Output enum documented as `CREATED|VERIFYING|VERIFIED|REJECTED|REVIEW`.
- **Runtime fact:** `status: "VERIFIED"` on POST → 400 with input enum: `'active'|'inactive'|'suspended'`. **Three enums for the same concept:** input (modern: active/inactive/suspended), output (modern: 5-value), output (legacy: 6-value lowercase).
- **Phase 3 follow-up:** does `status: "active"` bypass KYC?
- **Evidence:** `evidence/work/users/20-batchB-mass-assignment-probe.json`.

### DRIFT-23 — Sandbox does NOT auto-approve verification; stuck in `REVIEW` indefinitely
- **Family:** Verification (Batch B)
- **Original ID:** DRIFT-B10
- **Doc claim:** § 5.2: `CREATED --> VERIFIED: sandbox auto-approves`. Recipe F shows `user.verification.accepted` async event.
- **Runtime fact:** After triggering verification, user goes `CREATED → VERIFYING → REVIEW` in ~10s, then stays in REVIEW the full 2-minute window. `eligible_products[*].eligible` remains `false`.
- **Severity:** **CRITICAL.** Blocks Batches D and F end-to-end validation in sandbox.
- **Evidence:** `evidence/work/verification/poll-individual-*-success.json`, `evidence/work/verification/poll-business-*-success.json`.

### DRIFT-24 — S3 presigned URLs leak `production` bucket name + tenant `client_id`
- **Family:** Users (Batch B)
- **Original ID:** DRIFT-B11
- **Doc claim:** None — file upload mechanism undocumented.
- **Runtime fact:** Response replaces `documents[*].file` (base64) with 10-min presigned URL pointing to `kirafin-user-files-production.s3.us-west-2.amazonaws.com/clients/<tenant_uuid>/users/<user_uuid>/...`. Sandbox + prod share bucket; tenant UUID in URL path.
- **Severity:** MEDIUM-HIGH (cross-bucket); LOW (path leak).
- **Evidence:** `evidence/work/users/21-batchB-maximal-individual.json`.

### DRIFT-25 — Undocumented verification type `api` (in addition to `embedded-link`)
- **Family:** Verification (Batch B)
- **Original ID:** DRIFT-B12
- **Doc claim:** § 3.2 documents only `type: "embedded-link"`.
- **Runtime fact:** Empty body / invalid type reveals discriminator enum: `'embedded-link' | 'api'`. The `api` value is undocumented (presumably headless KYC).
- **Evidence:** `evidence/work/verification/01-post-verifications-missing-required.json` line 56, `01-post-verifications-bad-enum.json` line 59.

### DRIFT-26 — (reserved — C1 unused; sequential mapping per merge rule)
- *Original ID DRIFT-C1 reserved/unused in Batch C; this entry is a placeholder so DRIFT-C2..C15 align to DRIFT-26..39.*

> NOTE: Per the merge rule "map sequentially regardless of skipped C1", Batch C drifts DRIFT-C2..C15 (14 entries) map to DRIFT-26..DRIFT-39. The mapping below follows that rule.

### DRIFT-26 — Recipient country fields require alpha-2, contradicting `/v1/users` (alpha-3)
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C2
- **Doc claim:** § 3.5 + § 2.6 + GAP-20 — users alpha-3; banks alpha-2; recipients ambiguous.
- **Runtime fact:** Recipient `address.country`, `account.bank_address.country`, `account.doc_country_code`, `account.country` **all require alpha-2** (`US`, `MX`, `ES`). Alpha-3 returns 400 `"Country must be a 2-character ISO code"`. **Two endpoints, two formats simultaneously enforced.**
- **Severity:** HIGH. Integrator using alpha-3 (docs-recommended for users) blocked on every recipient.
- **Evidence:** `evidence/work/recipients/02-fail-400-ach.json`, `evidence/work/recipients/04-fail-400-swift.json`.

### DRIFT-27 — Documented `doc_type: "ssn"` for ACH is rejected at runtime
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C3
- **Doc claim:** § 3.5 ACH row implies SSN/EIN; `run_flow.py` uses `doc_type: "ssn"`.
- **Runtime fact:** Runtime enum is `id|dni|passport|ein`. `ssn` returns 400 `Invalid enum value`.
- **Severity:** HIGH. US-bank ACH is the API's bread-and-butter.
- **Evidence:** `evidence/work/recipients/02-fail-400-ach.json` line 84-87.

### DRIFT-28 — WALLET TRON address validated against base58check (good, but undocumented as hard validation)
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C4
- **Doc claim:** § 3.5 says TRON addresses start with `T` and are 34 chars (length-only validation implied).
- **Runtime fact:** Performs base58check decoding. Pure-fake `T...` strings fail. Can't generate fake-but-format-valid TRON address without a publicly known burn address.
- **Evidence:** `evidence/work/recipients/03-fail-400-usdt.json`.

### DRIFT-29 — SWIFT recipients require recipient-level `address` object (flow-design listed this as ACH-only)
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C5
- **Doc claim:** ACH row mentions recipient-level address; SWIFT row does not.
- **Runtime fact:** SWIFT returns 400 `"address is required for SWIFT accounts (structured object with street_name, city, state, postal_code, country)"`.
- **Evidence:** `evidence/work/recipients/04-fail-400-swift.json` line 87-91.

### DRIFT-30 — `account_details` returned UNMASKED, contradicting docs claim of `****7890` masking
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C6
- **Doc claim:** § 3.5: `account_number: "****7890"` masking implied.
- **Runtime fact:** Full `clabe`, `account_number`, `routing_number`, `swift_code`, wallet `address`, `doc_number` returned plaintext on both POST and GET, across all 4 variants. CLABE includes destination bank code + account number plaintext — bank-secrecy-sensitive in MX.
- **Severity:** HIGH — security-adjacent. Escalate to api-security-auditor for Phase 3.
- **Evidence:** `evidence/work/recipients/26-31-*.json`, `01-success-201-spei.json`, `06-success-200-detail-spei.json`.

### DRIFT-31 — Timestamp format is non-ISO: `"2026-05-28 00:52:49.879228+00"` (space separator + `+00`)
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C7
- **Doc claim:** No format specified; implicit ISO 8601.
- **Runtime fact:** PostgreSQL-default formatting — space separator, 6-digit microseconds, `+00` (not `+00:00`), no `Z`. Go `time.Parse(time.RFC3339, …)` **fails**. Python 3.10+ `datetime.fromisoformat` accepts.
- **Evidence:** Every success response — e.g. `01-success-201-spei.json` line 79.

### DRIFT-32 — SWIFT POST-create loses `bank_address.state` and `bank_address.postal_code` (empty strings); GET-detail returns them
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C8
- **Doc claim:** Both fields should round-trip per § 3.5 SWIFT row.
- **Runtime fact:** POST request had `state:"Madrid"`, `postal_code:"28001"`; POST-response has both as `""`. Subsequent GET-detail returns them correctly. POST and GET built from different projections.
- **Severity:** HIGH. Integrators echoing POST-response to UI store/display empty values. Idempotent-replay hash-comparisons fail.
- **Evidence:** `evidence/work/recipients/30-success-201-swift-iter2.json` line 95-99 vs `31-success-200-detail-swift-iter2.json` line 64-69.

### DRIFT-33 — `GET /v1/recipients` envelope is `{recipients:[...], total:N}` — third distinct list-envelope on the API
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C9
- **Doc claim:** § 3.5 says flat array; api-reference-coverage suspected `{data:[...]}`.
- **Runtime fact:** Wrapped object `{recipients:[...], total:1}`. Cross-endpoint: `/v1/users` → `{data, pagination}`, `/v1/recipients` → `{recipients, total}`. No consistent total field name, no consistent pagination model.
- **Severity:** HIGH. List-envelope-uniformity finding.
- **Evidence:** `evidence/work/recipients/05-success-200-list-by-user.json`.

### DRIFT-34 — Idempotent-replay returns 201 not 202; flow-design § 3.5 "unusual 202-on-replay" is FALSE
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C10
- **Doc claim:** § 3.5: "202 on idempotent reuse for existing recipient (unusual)".
- **Runtime fact:** Same key + same body → 201 with original `recipient_id`. The flagged "generic-SDK-killer" quirk doesn't exist.
- **Evidence:** `evidence/work/recipients/07-success-201-idem-replay-same-spei.json`.

### DRIFT-35 — Idempotency-conflict 409 returns `details: {}` (empty) — no field-level diff
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C11
- **Doc claim:** § 2.4 / GAP-08 implied details carries diff info.
- **Runtime fact:** Shape B envelope `{error:{code:"IDEMPOTENCY_CONFLICT", message, details:{}}}` — empty details. No indication of which field changed.
- **Severity:** HIGH-for-DX. Integrator can't debug conflict from response.
- **Evidence:** `evidence/work/recipients/08-fail-409-idem-conflict-spei.json`.

### DRIFT-36 — `/v1/recipients` returns TWO error-envelope shapes on the same endpoint
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C12
- **Doc claim:** § 2.3 noted two shapes coexist across the API.
- **Runtime fact:** 409 idem conflict → Shape B. 400 validation (ACH/SWIFT/USDT/idem-omit) → Shape A. Single endpoint, two envelopes, two different `details` types.
- **Severity:** HIGH. Per-endpoint version of GAP-05. Type-safe codegen breaks.
- **Evidence:** `evidence/work/recipients/02, 03, 04, 08, 09`.

### DRIFT-37 — Cross-pollution: SPEI body + WALLET fields → 201 silent strip
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C13
- **Doc claim:** Undefined behavior.
- **Runtime fact:** SPEI body with injected `wallet_address`/`network`/`token` → 201 success; extra fields silently stripped. No 400, no `unknown_fields` echo.
- **Severity:** MEDIUM (mass-assignment-adjacent).
- **Evidence:** `evidence/work/recipients/10-success-201-m1-spei-with-wallet-fields.json`.

### DRIFT-38 — SPEI with `country: "USA"` → 201 silent OVERRIDE to `country: "MX"` (derived from CLABE)
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C14
- **Doc claim:** Undefined.
- **Runtime fact:** Submit `account.country: "USA"`; response has `account_details.doc_country_code: "MX"`. Integrator UI may show "USA" while DB stores "MX".
- **Severity:** HIGH. Silent data correction; persists divergent state.
- **Evidence:** `evidence/work/recipients/11-success-201-m2-spei-country-mismatch.json`.

### DRIFT-39 — `DELETE /v1/recipients/{id}` returns 403 with AWS-IAM SigV4 error leaking through
- **Family:** Recipients (Batch C)
- **Original ID:** DRIFT-C15
- **Doc claim:** No DELETE documented for recipients.
- **Runtime fact:** DELETE returns 403 with body `{"message":"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '…'."}`. Same gateway-layer error class as DRIFT-1. No `Allow` header. GET-after-DELETE confirms recipient still exists.
- **Severity:** MEDIUM (DX + info-leak).
- **Evidence:** `evidence/work/recipients/12-fail-403-delete-spei.json`.

### DRIFT-40 — Guides Quotations schema is non-existent at runtime
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E1
- **Doc claim:** Guides describe `{base_currency, quote_currency, amount, amount_in_destination}`.
- **Runtime fact:** Server's validator does not recognize any of those four field names. Silently dropped. The 400 mentions `recipient_id` / `account_type` (which Guides never mention).
- **Severity:** CRITICAL. GAP-31 STAYS CRITICAL with sharper framing — Guides is dead documentation.
- **Evidence:** `evidence/work/quotations/01-e1-guides-validation-400.json`, `02-e1b-guides-amt-in-dest-validation-400.json`.

### DRIFT-41 — `amount` MUST BE A STRING, not a number (TS-SDK killer)
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E2
- **Doc claim:** Reference Body Param widget inconsistent; snippets show `1000` numeric.
- **Runtime fact:** Empty-body 400 explicitly states `"expected":"string","received":"undefined"`. Negative-amount probe reveals regex `^[0-9]+(\.[0-9]{1,2})?$`. **String, positive, ≤2 decimals.**
- **Severity:** HIGH. TS SDKs typed as `amount: number` break.
- **Evidence:** `evidence/work/quotations/06-e4-empty-validation-400.json`, `08-e5b-negative-amount-validation-400.json`.

### DRIFT-42 — `client_markup` is an OBJECT, not a string
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E3
- **Doc claim:** Type not clearly rendered (per GAP-30).
- **Runtime fact:** `client_markup: "0"` → 400 `Expected object, received string`. Inner schema still unknown — field is unusable.
- **Evidence:** `evidence/work/quotations/29-fu2-ACH-with-markup-fail-400.json`.

### DRIFT-43 — `recipient_id` field present but null is rejected (null ≠ omission)
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E4
- **Doc claim:** Either `recipient_id` OR `account_type` required.
- **Runtime fact:** `{recipient_id: null, account_type: "ACH", amount: "1000000"}` → 400 `expected:"string", received:"null"`. Null treated as type violation, not absence.
- **Evidence:** `evidence/work/quotations/30-fu2-ACH-recip-null-fail-400.json`.

### DRIFT-44 — Empty-body 400 returns ONLY `amount` as missing, masking the conditional gate
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E5
- **Doc claim:** N/A — UX issue.
- **Runtime fact:** Empty body 400 emits ONLY `amount` Required. Conditional `recipient_id OR account_type` gate fires only as a SECOND 400.
- **Evidence:** `evidence/work/quotations/06-e4-empty-validation-400.json` vs `01-…`/`02-…`.

### DRIFT-45 — Sandbox fee profiles configured with rates ≥100% — every Reference-shape happy path blocked
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E6
- **Doc claim:** N/A — sandbox config issue not warned.
- **Runtime fact:** Every account_type (`WIRE/SWIFT/ACH/INSTANT_PAY`) returns `"Total fees exceed or equal the payout amount"` for every amount $1 → $100M. `inverse_calculation: true` returns `"Fee rates exceed 100%, inverse calculation is not possible"`. `WALLET` returns `"No fee profile configured for product usa-va-fiat-to-crypto-payout"`. **Canonical 2xx unreachable in sandbox.**
- **Severity:** HIGH. Blocks Batch F (payouts) end-to-end.
- **Evidence:** `evidence/work/quotations/04-e2b-ref-ach-validation-400.json`, `15-fu-WIRE-10000-fail-400.json`, `16-fu-SWIFT-10000-fail-400.json`, `17-fu-INSTANT_PAY-10000-fail-400.json`, `18-fu-WALLET-poly-USDC-10000-fail-400.json`, `21-fu-ACH-inverse-true-fail-400.json`, `24-fu2-ACH-amt-1000000-fail-400.json`, `25-fu2-ACH-amt-100M-fail-400.json`.

### DRIFT-46 — Server names a product family `usa-va-fiat-to-crypto-payout` that is undocumented
- **Family:** Quotations (Batch E)
- **Original ID:** DRIFT-E7
- **Doc claim:** No "product" abstraction mentioned in Quotations docs or recipients/account-types reference.
- **Runtime fact:** WALLET error message exposes internal taxonomy: `"No fee profile configured for product usa-va-fiat-to-crypto-payout with account type WALLET"`. Implies sibling products (`usa-va-fiat-to-bank-payout`, `usa-va-crypto-to-bank-payout`, etc.) each with own fee profile.
- **Severity:** HIGH (info-leak via error + docs gap).
- **Evidence:** `evidence/work/quotations/03-e2-ref-wallet-validation-400.json`.

### DRIFT-47 — `POST /webhooks/register` accepts SSRF-flavored URLs without validation
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G1
- **Doc claim:** Reference page documents `webhook_url: uri` with no validation rules; flow-design § 2.7 implies HTTPS. Implicit assumption: private IPs / loopback / link-local / RFC1918 rejected.
- **Runtime fact:** `http://localhost`, `http://127.0.0.1`, `http://169.254.169.254/latest/meta-data/` (AWS IMDS), `http://10.0.0.1` (RFC1918), `http://[::1]` (IPv6 loopback) — all returned 200 `"Webhook registered successfully"`. Only `ftp://` rejected (Pydantic `HttpUrl` scheme check).
- **OWASP mapping:** API7:2023 — SSRF. Pre-exploit posture confirmed. Phase-3 work to confirm outbound delivery (out of scope this batch).
- **Severity:** CRITICAL (security).
- **Evidence:** `evidence/work/webhooks/12-success-ssrf-localhost-80.json` through `19-success-ssrf-dup-query.json` (skipping `18-fail-400-ssrf-ftp-scheme.json`).

### DRIFT-48 — `secret` is effectively optional; only empty string is rejected
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G2
- **Doc claim:** Reference marks `secret` as optional; flow-design § 2.7 implicit-required for HMAC-SHA256.
- **Runtime fact:** `secret: <32 chars>` → 200. `secret: ""` → 400 (string_too_short, min 5). `secret: null` → 200. Omitted → 200. **Unsigned webhook deliveries possible.**
- **Severity:** HIGH (security).
- **Evidence:** `evidence/work/webhooks/22-fail-400-G6.3-secret-empty.json`, `23-success-G6.4-secret-null.json`, `24-success-G6.5-secret-omit.json`.

### DRIFT-49 — GAP-04 INVERTED: `x-api-key` alone is NOT enough; both headers required on `/webhooks/register`
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G3
- **Doc claim:** § 2.7, § 3.11 and GAP-04 all state this endpoint does not require Bearer.
- **Runtime fact:** `x-api-key` only → 401. Bearer only → 403 (gateway). Both → 400/200. **Endpoint behaves like every other endpoint.** GAP-04 reclassified to "Bearer is required everywhere; docs are misleading".
- **Severity:** HIGH (contract/docs).
- **Evidence:** `evidence/work/webhooks/05-fail-401-G2.1-xapikey-only.json`, `06-fail-403-G2.2-bearer-only.json`, `07-success-G2.3-both-headers.json`.

### DRIFT-50 — `Idempotency-Key` is silently ignored on `/webhooks/register`
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G4
- **Doc claim:** docs/idempotency-key.md lists POST endpoints supporting idempotency; webhooks-register not explicitly excluded.
- **Runtime fact:** Same key + same body → 200. Same key + different body → 200 (no 409). Header is accepted but ignored. Second call re-registers (overwrite).
- **Severity:** HIGH. Integrators retrying with altered bodies silently overwrite their own webhook.
- **Evidence:** `evidence/work/webhooks/09-success-G4.1-idem-first.json`, `10-success-G4.2-idem-replay-same-body.json`, `11-success-G4.3-idem-conflict-diff-body.json`.

### DRIFT-51 — Registration response is opaque: no id, no echo, no inventory
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G5
- **Doc claim:** Reference documents 200 with no body schema; § 4.6 example shows `{ message: "Webhook registered successfully" }`.
- **Runtime fact:** Response is literally `{"message":"Webhook registered successfully"}` — nothing else. Combined with no `GET /webhooks` and no `DELETE /webhooks/{id}` (both 403, route does not exist — GAP-21 confirmed), integrator has **zero observable state**. No audit/list/rotate/delete; recovery from misconfigured secret requires emailing Kira support.
- **Severity:** HIGH (contract).
- **Evidence:** `evidence/work/webhooks/02-success-G0.2-path-webhooks-register-no-v1.json`, `26-fail-403-G5.1-list.json`.

### DRIFT-52 — Path is `/webhooks/register` (no `/v1/` prefix) — inconsistent with rest of API
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G6
- **Doc claim:** § 3.11 documents the no-`/v1/` path; brief assumed `/v1/webhooks/register`.
- **Runtime fact:** `/webhooks/register` → 200. `/v1/webhooks/register` → 403 `MissingAuthenticationTokenException`. Webhooks is the only family without `/v1/`. OpenAPI-codegen trap.
- **Severity:** MEDIUM (contract).
- **Evidence:** `evidence/work/webhooks/01-fail-403-G0.1-path-v1-webhooks-register.json` vs `02-success-G0.2-path-webhooks-register-no-v1.json`.

### DRIFT-53 — HTTP (not just HTTPS) accepted as `webhook_url` scheme
- **Family:** Webhooks (Batch G)
- **Original ID:** DRIFT-G7
- **Doc claim:** § 3.11 documents `webhook_url (HTTPS)`; Guides imply HTTPS-only.
- **Runtime fact:** `http://webhook.site/<uuid>` accepted with 200. Only non-`http(s)` rejected. Combined with DRIFT-48 (secret optional), deliveries can fly cleartext-and-unsigned.
- **Severity:** MEDIUM (security/contract).
- **Evidence:** `evidence/work/webhooks/25-success-G6.6-http-not-https.json`.

---

## Per-endpoint narrative (master, by family)

### Auth — `POST /auth`
Documented response contract honored byte-for-byte. Friction at URL layer: docs base URL rejected by AWS API Gateway with identity-style 403, regardless of `x-api-key` correctness. Failure mode is actively misleading. Single-call 953 ms (cold-ish). Undocumented `set-cookie` (308 bytes, redacted), `x-api-version: 2026-04-14` echoed in response header.

### Users — `POST /v1/users` (create)
Easy on the wire — docs-only ACT-business payload returned 201 first attempt. "First 2xx" is a deceptive success metric: response reveals "minimal" body isn't enough to *trigger KYB* — 21 missing fields. Combined with DRIFT-1 escalation (`/sandbox` is dead for `/v1/*` too), country-code probe (alpha-2/alpha-3 both silently accepted) is the worst latent data-quality bomb. Warm latency (n=4) min 252 / median 299 / max 370 ms. Response surface ~3.2 KB, 15 top-level keys, 4 undocumented.

### Users — `GET /v1/users/{id}`, `PUT /v1/users/{id}`, list
GET drops `verification_triggered` field (DRIFT-14). PUT-empty-body returns 200 (DRIFT-15). PUT metadata must be strings (DRIFT-20). List envelope `{data, pagination}` matches docs but shows persistent `US`/`USA` mix (DRIFT-5 persistent). `limit=100000` → 500 (DRIFT-10). Mass-assignment probe surfaced three enums for the same concept (DRIFT-22).

### Verification — `POST /v1/users/{id}/verifications`, `POST /verification/send`, polling
The `/verifications` endpoint mints AiPrise hosted-link URLs but doesn't move state machine (DRIFT-17). Idempotency NOT enforced (DRIFT-16). OTP endpoint exists at `/verification/send` (root path, DRIFT-21) keyed on email not user. **Sandbox does not auto-approve** (DRIFT-23, CRITICAL) — users stuck in REVIEW indefinitely. Empirically observed: `CREATED → VERIFYING → REVIEW` in ~10s, stays REVIEW for full 2-minute poll window. Blocks Batches D and F. Undocumented `type: "api"` discriminator surfaced (DRIFT-25). S3 presigned URLs leak `production` bucket + tenant `client_id` (DRIFT-24).

### Reference data — `GET /v1/countries`, `GET /v1/banks`
Countries: 250 entries, alpha-3 codes (`USA`, `MEX`), with `subdivisions[]`. Reference page has no example (GAP-30 confirmed). Banks: the most painful endpoint of Batch A — two doc errors stacked (path `/banks` vs `/v1/banks`, param `country` vs `country_code`), plus runtime feature gap (`country_code=CO` only). `/banks` Reference path returns HTTP 200 with non-JSON body (Cloudflare WAF/origin error) — actively misleading. Mexico/Argentina/Chile/Peru/Brazil bank lookups unavailable.

### Recipients — `POST /v1/recipients`, list, detail, DELETE
Polymorphic schema matrix empirically captured (SPEI/ACH/USDT/SWIFT). Recipient creation **does not require user to be VERIFIED** (UNDOCUMENTED, useful). Five highest-impact findings: (a) alpha-2-only (DRIFT-26 — opposite of `/v1/users` alpha-3); (b) doc_type:"ssn" rejected (DRIFT-27); (c) account_details unmasked despite docs (DRIFT-30); (d) SWIFT POST/GET divergence on state/postal_code (DRIFT-32); (e) silent country override from CLABE (DRIFT-38). Two error-envelope shapes on the same endpoint (DRIFT-36). Idempotency 202-on-replay claim is FALSE (DRIFT-34). DELETE returns 403 with AWS-IAM SigV4 leak (DRIFT-39).

### Virtual accounts — `GET /v1/virtual-accounts` (list)
Empty `data[]` (no VAs — gated on Batch D). Same envelope as `/v1/users`. Same `limit=100000` → 500 bug (DRIFT-10). Warm n=4 median 261 ms.

### Quotations — `POST /v1/quotations`
GAP-31 RESOLVED. **Canonical schema: REFERENCE (with extensions).** Guides body shape is non-functional (DRIFT-40, CRITICAL) — silently ignored at runtime; error message mentions only Reference fields. `amount` is STRING with regex (DRIFT-41, TS-SDK killer). `client_markup` is OBJECT (DRIFT-42). `recipient_id` null rejected (DRIFT-43). Empty-body 400 masks conditional gate (DRIFT-44). **Sandbox fee profiles ≥100% block every Reference-shape happy path** (DRIFT-45, HIGH) — canonical 2xx unreachable. Server leaks internal product taxonomy via error messages (DRIFT-46).

### Webhooks — `POST /webhooks/register`, list/get/delete attempts
**No SSRF validation at registration** (DRIFT-47, CRITICAL) — accepts localhost, 127.0.0.1, AWS IMDS, RFC1918, IPv6 loopback. Secret effectively optional (DRIFT-48). Both headers required — docs were wrong (DRIFT-49). Idempotency silently ignored (DRIFT-50). Opaque response — no id, no echo, no list/get/delete (DRIFT-51, GAP-21 confirmed). Path is `/webhooks/register` (no `/v1/`, DRIFT-52). HTTP accepted in addition to HTTPS (DRIFT-53). No `events` field — no per-event subscription model.

---

## Phase 2 → Phase 3 handoff (updated)

For each endpoint family, status:

- **`POST /auth`** — Pre-cleared for adversarial testing: YES. Critical findings already captured: DRIFT-1, DRIFT-2.
- **`POST /v1/users` (create)** — Pre-cleared: YES. Critical findings: DRIFT-3, DRIFT-4, DRIFT-5, DRIFT-22 (mass-assignment requires Phase 3 follow-up), DRIFT-24 (S3 prod bucket — Phase 3 BOLA/SSRF surface).
- **`GET /v1/users/{id}` / PUT / list** — Pre-cleared: YES. Critical findings: DRIFT-14, DRIFT-15, DRIFT-20.
- **`POST /v1/users/{id}/verifications` / `POST /verification/send`** — Pre-cleared: YES (with caveat — DRIFT-23 blocks downstream). Critical findings: DRIFT-16, DRIFT-17, DRIFT-21, DRIFT-23, DRIFT-25.
- **`GET /v1/countries`, `GET /v1/banks`** — Pre-cleared: YES. Critical findings: DRIFT-7, DRIFT-8, DRIFT-9, DRIFT-11.
- **`GET /v1/users` (list), `GET /v1/virtual-accounts` (list)** — Pre-cleared: YES. Critical findings: DRIFT-10.
- **`POST /v1/recipients` (4 variants), GET list/detail, DELETE** — Pre-cleared: YES. Critical findings: DRIFT-26 through DRIFT-39 (Phase 3 escalations: DRIFT-30 unmasked PII; DRIFT-37 mass-assignment; DRIFT-39 gateway leak).
- **`POST /v1/quotations`** — **BLOCKED-BY-DRIFT-45.** Canonical 2xx unreachable in sandbox until fee profiles are seeded. Critical findings: DRIFT-40, DRIFT-41, DRIFT-42, DRIFT-45.
- **`POST /webhooks/register`** — Pre-cleared: YES (with Phase-3-immediate flag). Critical findings: DRIFT-47, DRIFT-48, DRIFT-49, DRIFT-50, DRIFT-51. **Phase 3 escalation: SSRF exploit confirmation (force Kira to fetch IMDS); signature-on-unsigned-secret; cross-tenant `client_uuid` spoof.**
- **Batches D (Virtual Accounts: POST/GET single/simulate-deposit), F (Payouts), H (Webhook receiver e2e)** — **BLOCKED-BY-DRIFT-23 (sandbox no auto-approve)** and **BLOCKED-BY-DRIFT-45 (no canonical quote_id).** Cannot exercise canonical happy path without escalation to `@Diego`.

---

## Drift renumber map (audit trail)

| Original | Canonical | Origin batch |
|---|---|---|
| DRIFT-1 | DRIFT-1 | Pre-batch |
| DRIFT-2 | DRIFT-2 | Pre-batch |
| DRIFT-3 | DRIFT-3 | Pre-batch |
| DRIFT-4 | DRIFT-4 | Pre-batch |
| DRIFT-5 | DRIFT-5 | Pre-batch |
| DRIFT-A1 | DRIFT-6 | A |
| DRIFT-A2 | DRIFT-7 | A |
| DRIFT-A3 | DRIFT-8 | A |
| DRIFT-A4 | DRIFT-9 | A |
| DRIFT-A5 | DRIFT-10 | A |
| DRIFT-A6 | DRIFT-11 | A |
| DRIFT-A7 | DRIFT-12 | A |
| DRIFT-A8 | DRIFT-13 | A |
| DRIFT-B1 | DRIFT-14 | B |
| DRIFT-B2 | DRIFT-15 | B |
| DRIFT-B3 | DRIFT-16 | B |
| DRIFT-B4 | DRIFT-17 | B |
| DRIFT-B5 | DRIFT-18 | B |
| DRIFT-B6 | DRIFT-19 | B |
| DRIFT-B7 | DRIFT-20 | B |
| DRIFT-B8 | DRIFT-21 | B |
| DRIFT-B9 | DRIFT-22 | B |
| DRIFT-B10 | DRIFT-23 | B |
| DRIFT-B11 | DRIFT-24 | B |
| DRIFT-B12 | DRIFT-25 | B |
| (DRIFT-C1 reserved/unused) | DRIFT-26 (placeholder slot — see note below) | C |
| DRIFT-C2 | DRIFT-26 | C |
| DRIFT-C3 | DRIFT-27 | C |
| DRIFT-C4 | DRIFT-28 | C |
| DRIFT-C5 | DRIFT-29 | C |
| DRIFT-C6 | DRIFT-30 | C |
| DRIFT-C7 | DRIFT-31 | C |
| DRIFT-C8 | DRIFT-32 | C |
| DRIFT-C9 | DRIFT-33 | C |
| DRIFT-C10 | DRIFT-34 | C |
| DRIFT-C11 | DRIFT-35 | C |
| DRIFT-C12 | DRIFT-36 | C |
| DRIFT-C13 | DRIFT-37 | C |
| DRIFT-C14 | DRIFT-38 | C |
| DRIFT-C15 | DRIFT-39 | C |
| DRIFT-E1 | DRIFT-40 | E |
| DRIFT-E2 | DRIFT-41 | E |
| DRIFT-E3 | DRIFT-42 | E |
| DRIFT-E4 | DRIFT-43 | E |
| DRIFT-E5 | DRIFT-44 | E |
| DRIFT-E6 | DRIFT-45 | E |
| DRIFT-E7 | DRIFT-46 | E |
| DRIFT-G1 | DRIFT-47 | G |
| DRIFT-G2 | DRIFT-48 | G |
| DRIFT-G3 | DRIFT-49 | G |
| DRIFT-G4 | DRIFT-50 | G |
| DRIFT-G5 | DRIFT-51 | G |
| DRIFT-G6 | DRIFT-52 | G |
| DRIFT-G7 | DRIFT-53 | G |

> **Note on Batch C numbering:** Batch C used the IDs DRIFT-C2..C15 (skipping C1 — reserved/unused). Per the merge rule, the 14 Batch C entries map sequentially to DRIFT-26..DRIFT-39 regardless of the C1 gap. The "DRIFT-26 placeholder" row above is informational only; canonical DRIFT-26 is the renumbered DRIFT-C2.

---

## Per-batch headline summaries

### Pre-batch (auth + POST /v1/users)
Two endpoints; 5 drift events. Established that the docs lie about the base URL across the entire API (`/sandbox` is dead). Surface-level "201 on first call" obscured a deeper finding: the published "minimal" payload doesn't actually trigger KYB — 21 missing fields. Both alpha-2 and alpha-3 country codes silently accepted on `/v1/users` with no normalization (latent data-quality bomb).

### Batch A — Foundations & Reference
5 read endpoints; 8 drift events. Resolved GAP-32 worse than predicted (`/banks` returns HTTP 200 with non-JSON Cloudflare error body — silent-success bug). `/v1/banks` is **Colombia-only at runtime** despite multi-country positioning. `?limit=100000` triggers 500 across list endpoints. `X-Api-Version` is a pure echo (no semantic effect). Four distinct error-envelope shapes catalogued. Reference data for non-Colombian banks unavailable in sandbox.

### Batch B — User lifecycle & verification
6 endpoints; 12 drift events. **CRITICAL: sandbox does NOT auto-approve verification** — users stuck in REVIEW indefinitely, blocking Batches D and F. DRIFT-3 root cause resolved (trigger gate = `missing_fields: {}` for one product; docs omit 5+ required fields). Idempotency NOT enforced on `/v1/users/{id}/verifications` (HIGH severity; billable if AiPrise charges per session). Mass-assignment surface: `status` accepts a third enum (`active|inactive|suspended`) at create time. OTP endpoint located at root `/verification/send` keyed on email. S3 presigned URLs leak `production` bucket + tenant `client_id`. `business_industry` is an undocumented 90+ NAICS-coded ARRAY.

### Batch C — Recipients polymorphic
1 endpoint family, 4 variants + list + detail + DELETE; 14 drift events. Polymorphic schema matrix empirically captured. **Recipients require alpha-2 country codes — opposite of `/v1/users` (alpha-3)**, two endpoints two formats simultaneously enforced. `account_details` returned UNMASKED despite docs claiming `****7890` masking — security-adjacent finding. SWIFT POST-create response **loses** `state` and `postal_code` (returns `""`); GET-detail returns them correctly — POST/GET divergence. Silent country override from CLABE prefix (declared "USA" persisted as "MX"). Documented `doc_type: "ssn"` is rejected — enum is `id|dni|passport|ein`. Third distinct list-envelope shape on the API (`{recipients, total}`). Two error envelopes on the same endpoint.

### Batch E — Quotations
1 endpoint; 7 drift events. **GAP-31 RESOLVED — Guides Quotations page is dead documentation**. Reference shape is canonical; Guides body is silently dropped at runtime. `amount` is a STRING with regex `^[0-9]+(\.[0-9]{1,2})?$` — TypeScript SDK killer. `client_markup` is OBJECT, not string; `recipient_id` null rejected. **Sandbox fee profiles configured at ≥100% — canonical 2xx happy path is unreachable for every account_type**; blocks Batch F. Server leaks internal product taxonomy (`usa-va-fiat-to-crypto-payout`) via error messages.

### Batch G — Webhooks + SSRF preview
1 endpoint working + 5 attempted; 7 drift events. **CRITICAL: zero SSRF validation on `webhook_url`** — Kira accepts localhost, 127.0.0.1, AWS IMDS, RFC1918, IPv6 loopback with 200 success. OWASP API7:2023 pre-exploit posture confirmed. Secret is effectively optional (`null` and omitted both accepted). GAP-04 INVERTED — both `x-api-key` AND Bearer required, contradicting all three doc layers. `Idempotency-Key` silently ignored. Response is opaque `{"message":"Webhook registered successfully"}` — no id, no echo. No list/get/delete endpoints (all 403 — route does not exist). Path is `/webhooks/register` (no `/v1/`), the only family without the prefix. HTTP accepted in addition to HTTPS.
