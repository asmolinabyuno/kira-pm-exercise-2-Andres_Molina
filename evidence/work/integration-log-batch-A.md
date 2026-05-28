> **MERGED INTO MASTER `integration-log.md` on 2026-05-27.** Canonical drift IDs renumbered: DRIFT-A1..A8 → DRIFT-6..DRIFT-13. See `evidence/analysis/04-integration-log.md` for the consolidated audit trail.

# Batch A — Foundations & Reference Data (parallel probe run)

**Worker:** parallel Phase 2 probe — Batch A. Sibling agents on B / C / E-A / G.
**Persona:** `data-engineer`. Run timestamp: 2026-05-28T00:51–00:55 UTC.
**Script:** `evidence/work/probes/batch_A.py` (+ follow-up `evidence/work/probes/batch_A_followup_banks.py`).
**Endpoints in scope:** `GET /v1/countries`, `GET /v1/banks`, `GET /v1/users` (list), `GET /v1/virtual-accounts` (list), `GET /v1/recipients` (list).
**Mutation set per endpoint:** omit `x-api-key`, omit `Authorization: Bearer`, `X-Api-Version: 2025-01-01` vs `2026-04-14` vs omitted, `?limit=100000`, `?offset=99999`, plus `/v1/`-vs-no-prefix on `/banks` and ISO-3166 variants on `/banks`.

## Endpoint table (extends main integration-log.md)

| # | Endpoint | Iter to 2xx | Doc sufficiency | Drift events | Lat median (ms, n=4) | Notes |
|---|---|---|---|---|---|---|
| 3 | `GET /v1/countries` | 1 | PARTIAL | A1, A6 | 366 | Returns `{count: 250, data:[...]}` (alpha-3 codes). `X-Api-Version: 2025-01-01` echoed back unchanged with **identical 250-row body**. No reference example in docs (GAP-30 confirmed). |
| 4 | `GET /v1/banks` | 2 | **NO** | A1, A2, A3, A4, A7 | 268 (preliminary, on `/v1/banks?country_code=CO`) | Docs claim `/banks` + `country=XX`. Runtime: **`/v1/banks` + `country_code=CO`** is the only working shape; everything else 400 or Cloudflare-WAF-blocked. Resolves GAP-32 conclusively (see A2). |
| 5 | `GET /v1/users` | 1 | PARTIAL | A1, A5, A6 | 247 | Envelope `{data, pagination:{total, limit, offset, has_more}}` matches docs. `limit=100000` → **500 Internal Server Error**. `offset=99999` → empty `data[]` (graceful). DRIFT-5 echo: list shows both `"US"` and `"USA"` for `registered_address.country`. |
| 14 | `GET /v1/virtual-accounts` | 1 | PARTIAL | A1, A5 | 261 | Same envelope as `/v1/users`. Empty `data[]` (no VAs yet). `limit=100000` → **500 Internal Server Error** (same Shape-C envelope as users). `offset=99999` accepted gracefully. |
| 11 | `GET /v1/recipients` | n/a (400 by design) | PARTIAL | A1, A8 | 281 (validation-path) | Hardcoded 400 unless `user_id` query param present. **New error envelope: `{error: {code, message, details}}`** — distinct from users' `{error, details[]}`. Confirms GAP-15 (no pagination) and re-confirms GAP-03 envelope variance. |

Where "Iter to 2xx" is **n/a (400 by design)** — the endpoint reaches its handler, validates input, and returns the documented 400. Doc sufficiency tracks whether you could *form a successful call* from the docs alone; for `/v1/recipients` you'd need a `user_id` first (cross-batch dependency on B/C).

## Drift events (Batch A namespace — renumber on merge)

### DRIFT-A1 — Three-shape error envelope variance in 401/403/400/500 responses (extends GAP-03 / GAP-05)

- **Doc claim:** `flow-design.md` §6 GAP-03 / GAP-05 flag envelope inconsistency as a *predicted* gap.
- **Runtime fact:** Batch A surfaced **four distinct error envelope shapes** in one set of probes, each tied to a different layer:
  - **Shape G (gateway):** `{message: "Forbidden" | "Unauthorized"}` + header `x-amzn-errortype: ForbiddenException | UnauthorizedException`. Returned by API Gateway when `x-api-key` or `Authorization` are absent (`countries/02-fail-403-no-apikey.json`, `countries/03-fail-401-no-bearer.json`, identical on `va-list`, `users-list`, `recipients`).
  - **Shape A (Zod-style validation):** `{error: "Invalid request data", details: [{path, message, code}]}` — Returned by users/banks request-body or query-string validation (`banks/01-fail-400-v1-country-MX.json`, `banks/15-fail-400-v1-cc-co-lower.json`).
  - **Shape B (typed error object):** `{error: {code: "VALIDATION_ERROR", message, details: {}}}` — Returned by `/v1/recipients` when `user_id` missing (`recipients/15-fail-400-happy-no-user-id.json`). **Same HTTP status (400), totally different body.**
  - **Shape C (internal):** `{status: "error", message: "Internal server error"}` — Returned by `/v1/users` and `/v1/virtual-accounts` on `?limit=100000` (500). No `code`, no `details`, no correlation back to the parameter (`users-list/06-fail-500-limit-100000.json`, `va-list/06-fail-500-limit-100000.json`).
- **Why this is a finding:** An integrator writing a single `parseError(response)` helper has to pattern-match on at least **four** independent envelope shapes within Batch A alone. Generic error handlers will mis-classify (`response.error` is truthy in both A and B but means different things; in B you must dereference `.error.code`).
- **Evidence:**
  - Shape G: `evidence/work/countries/02-fail-403-no-apikey.json`, `evidence/work/users-list/03-fail-401-no-bearer.json`
  - Shape A: `evidence/work/banks/01-fail-400-v1-country-MX.json`, `evidence/work/banks/04-fail-400-v1-country-mx-lower.json`
  - Shape B: `evidence/work/recipients/15-fail-400-happy-no-user-id.json`
  - Shape C: `evidence/work/users-list/06-fail-500-limit-100000.json`, `evidence/work/va-list/06-fail-500-limit-100000.json`

### DRIFT-A2 — `/banks` (no `/v1/` prefix) is documented but **broken at runtime** — GAP-32 resolved (and worse than predicted)

- **Doc claim:** `flow-design.md` §3.11 + GAP-32 noted that the Reference page for banks uses `GET /banks` (no `/v1/` prefix), inconsistent with the rest of the API.
- **Runtime fact:**
  - `GET https://api.balampay.com/banks?country=MX` → **HTTP 200** but body is the **Cloudflare 522 string** `"error code: 522"` after ~20s (`banks/02-success-nov1-country-MX.json`). The upstream origin is unreachable from CF for this path.
  - `GET https://api.balampay.com/banks?country=MX` with `x-api-key` only (no Bearer) → **HTTP 200** with body `"Blocked"` — Cloudflare WAF dropping the request but **with a 200 status code** (`banks/08-success-no-bearer.json`). Misleading the integrator into thinking it succeeded.
  - `GET https://api.balampay.com/v1/banks?country_code=CO` → **HTTP 200** with `{banks: [...28 entries...], total, country_code}` (`banks/14-success-v1-cc-CO.json`) — this is the **only** path that actually returns bank data.
  - `GET https://api.balampay.com/banks?country_code=CO` → **HTTP 200** but body `"Blocked"` (`banks/20-success-nov1-cc-CO.json`) — same Cloudflare WAF block.
- **Why this is worse than GAP-32 predicted:** Originally GAP-32 was a documentation-inconsistency finding. Empirically it's now a **silent-success bug** — the Reference-page URL returns HTTP 200 with no real data, no error code, and no JSON envelope. An integrator copy-pasting the docs path will:
  1. Get HTTP 200 (think it worked)
  2. Parse the response as JSON (fail — body is plain text `"Blocked"` or `"error code: 522"`)
  3. Either crash on parse or silently treat as empty (depending on parser)
- **The correct shape:** `GET /v1/banks?country_code=<alpha-2>` — the path needs `/v1/` AND the query param name is `country_code`, not `country`. **The docs are wrong on both axes.**
- **Open question (Eng / @Diego):** Should `/banks` be removed from the API surface entirely, or backfilled to proxy to `/v1/banks`? Returning 200 with a Cloudflare error string is the worst-case for integrators.

### DRIFT-A3 — `/v1/banks` accepts ONLY `country_code=CO` — Colombia-only at runtime (contradicts docs)

- **Doc claim:** `flow-design.md` §3.11 + GAP-20 imply `/banks` supports multiple countries (Mexico, Colombia, US, etc.) with alpha-2 ISO-3166. Bullet says "**Uses ISO 3166-1 alpha-2** (`CO`, `MX`, `US`)".
- **Runtime fact:** Probing `country_code` with all of `CO`, `co`, `COL`, `MX`, `Colombia`, omitted:
  - `CO` (uppercase alpha-2) → **200 OK**, returns 28 Colombian banks.
  - `co` (lowercase) → **400** `Only CO (Colombia) is supported at this time`
  - `COL` (alpha-3) → **400** same error
  - `MX` (alpha-2 Mexico) → **400** `Only CO (Colombia) is supported at this time`
  - `Colombia` (English name) → **400** same error
  - omitted → **400** validation error
- **Why this is a finding:** Two implications:
  1. **The platform's whole LATAM positioning depends on this endpoint** (every payout recipient builder needs a bank_code). At runtime, **Mexico/Argentina/Chile/Peru/Brazil bank lookups are not available**, which means SPEI/PSE/CLP/ARS payout flows cannot construct recipients via bank_code lookup — they'd have to be hardcoded or sourced elsewhere.
  2. **The error is *not* a doc gap but a runtime feature gap** — the API itself prints `"Only CO (Colombia) is supported at this time"`, acknowledging the limitation in-band. Docs should reflect this until parity ships.
- **No alpha-2/alpha-3 normalization:** `CO` works, `COL` fails. The endpoint is **strict alpha-2 only**. This means GAP-20's "alpha-2 vs alpha-3 mismatch with `/v1/users` (alpha-3)" is **runtime-confirmed**: an integrator who reads `address_country = "USA"` from a created user and tries `/v1/banks?country_code=USA` will get 400. They'd have to mentally maintain a 2↔3 alpha mapping.
- **Evidence:**
  - `evidence/work/banks/14-success-v1-cc-CO.json` (200, 28 banks)
  - `evidence/work/banks/15-fail-400-v1-cc-co-lower.json` (400, `details[].code: "invalid_literal"`)
  - `evidence/work/banks/16-fail-400-v1-cc-COL-alpha3.json` (400)
  - `evidence/work/banks/17-fail-400-v1-cc-MX.json` (400)

### DRIFT-A4 — Query param name `country_code` not `country` on `/v1/banks`

- **Doc claim:** `flow-design.md` §3.11 example: `GET /banks?country_code=XX`. Hidden trap: depending on which doc page you read, you may infer `country` (the example block in the integration-plan §3 Batch A row says "country_code=MX/MEX/mx/Mexico variants" but the Reference page is inconsistent).
- **Runtime fact:** `GET /v1/banks?country=MX` returns **400** with `details[0].path: "country_code"` — the server rejects on the missing `country_code` param while ignoring the supplied `country`. Confirmed param name is `country_code`.
- **Why it matters:** A common typo / mental-model mismatch. The error message is fortunately informative (it names the required param), but the doc Reference page should be auditable in one pass; this is the second documented field-name drift in Batch A (also `country_code=CO` only — DRIFT-A3).
- **Evidence:** `evidence/work/banks/01-fail-400-v1-country-MX.json`

### DRIFT-A5 — `?limit=100000` returns **HTTP 500 Internal Server Error** on `/v1/users` AND `/v1/virtual-accounts`

- **Doc claim:** Pagination is documented as `{limit, offset, total, has_more}` (`flow-design.md` §3.2). No documented upper bound on `limit`.
- **Runtime fact:** A `limit=100000` query parameter consistently triggers a **500 Internal Server Error** on both `/v1/users` and `/v1/virtual-accounts`, with response body `{status: "error", message: "Internal server error"}`. The 500 returns in ~241ms (validation-fast, not a timeout) — implying the server *does* validate the limit but does so by **throwing an unhandled exception** rather than returning a structured 400 `validation_error`.
- **Why this is a finding:**
  1. An integrator probing for "what's the max page size?" will see a 500 and reasonably conclude the service is broken (vs. "I overshot the limit"). The correct shape would be `400 limit_too_large` with `details: {max_allowed: 100}`.
  2. The 500 envelope (`{status, message}`) is a **fourth distinct error shape** — see DRIFT-A1.
  3. Server-side errors with no `details` or `code` give the integrator nothing actionable; they'd have to file a support ticket using the `x-amzn-requestid` header.
- **Bonus:** `?offset=99999` is handled gracefully (returns `{data: [], pagination: {offset: 99999, has_more: false}}`) — only the high `limit` hits the 500 path. So the bug is specifically a too-large `limit`, not an unsafe input class.
- **Evidence:**
  - `evidence/work/users-list/06-fail-500-limit-100000.json`
  - `evidence/work/va-list/06-fail-500-limit-100000.json`
  - Compare: `evidence/work/users-list/07-success-offset-99999.json` (200, graceful empty page)

### DRIFT-A6 — `X-Api-Version: 2025-01-01` request header is silently echoed back, identical response body (extends GAP-01)

- **Doc claim:** GAP-01 — no documented request-side version header; the URL path carries `v2026-04-14`.
- **Runtime fact:** Sent `X-Api-Version: 2025-01-01` to `/v1/countries` → **HTTP 200**, response header `x-api-version: 2025-01-01` echoed back (not the server's `2026-04-14`). Body shape identical to the no-header probe (same 250 countries, same keys). Sent `X-Api-Version: 2026-04-14` → server returns the same body but echoes `x-api-version: 2026-04-14`. **The header value influences only the response *header*, not the response *body*.**
- **Why this is a finding:**
  - The server *accepts* the header (no error) but doesn't *use* it to vary the contract. An integrator pinning to "an older version" would have false confidence — they think they're stabilizing against an old contract; in reality they're getting today's contract with a vanity header.
  - GAP-01 was about "no enforcement on the request side, but the server tags the response anyway." This refines it: **the request header is a pure echo with no semantic effect.** That's actively *worse* than ignoring it (an integrator might pin to a version that doesn't exist, get a 200, and silently get newer-schema data).
- **Evidence:**
  - `evidence/work/countries/04-success-xver-2025-01-01.json` (response header `x-api-version: 2025-01-01`, body identical to default)
  - `evidence/work/countries/05-success-xver-2026-04-14.json` (response header `x-api-version: 2026-04-14`, body identical)
  - `evidence/work/users-list/04-success-xver-2025-01-01.json`, `evidence/work/users-list/05-success-xver-2026-04-14.json` — same behavior on the user-list endpoint

### DRIFT-A7 — `x-api-key` alone (no Bearer) does **not** suffice for ANY Batch-A list endpoint (resolves GAP-04 — extension)

- **Doc claim:** GAP-04 — some endpoints documented as "Bearer-OR-API-key" (e.g. webhooks register uses `x-api-key` only).
- **Runtime fact:** Across all 5 Batch-A endpoints, omitting `Authorization: Bearer` while sending a valid `x-api-key` returns **401 UnauthorizedException** with body `{"message": "Unauthorized"}`. No Batch-A list endpoint accepts API-key-only auth.
  - `/v1/countries` → 401
  - `/v1/banks` (working `?country_code=CO`) — would also need testing here; the initial probe on `/banks` no-bearer returned 200 "Blocked" (Cloudflare WAF, not a successful API auth). On `/v1/banks` no-bearer was not directly probed in the follow-up; safer to consolidate as "401 expected" per the gateway pattern.
  - `/v1/users` (list) → 401
  - `/v1/virtual-accounts` (list) → 401
  - `/v1/recipients` (list) → 401
- **Why it matters:** GAP-04's resolution: **for read-style auth-only endpoints, Bearer is mandatory.** The only known "API-key alone" surface remains `POST /webhooks/register` per the docs. This is empirical confirmation; the platform's bifurcation of "Bearer-required" vs "key-only" applies cleanly to webhook registration and nowhere else in the read surface tested so far.

### DRIFT-A8 — `/v1/recipients` returns Shape B error envelope (`{error: {code, message, details}}`) — different from `/v1/users` Shape A (`{error, details[]}`)

- **Doc claim:** GAP-03 — envelope variance predicted across list endpoints.
- **Runtime fact:** Same 400 status, two different shapes. `/v1/users?limit=100000` and `/v1/banks` 400's use **Shape A** with flat `details: []`. `/v1/recipients` 400 uses **Shape B** with nested `details: {}`. The `code` field exists only in Shape B (`code: "VALIDATION_ERROR"`).
- **Why it matters:** An integrator parsing errors needs `response.error.code` for recipients but `response.details[0].code` for users — same field name, different paths.
- **Evidence:**
  - Shape A: `evidence/work/users-list/06-fail-500-limit-100000.json` (well, that's Shape C — better example below), `evidence/work/banks/01-fail-400-v1-country-MX.json`
  - Shape B: `evidence/work/recipients/15-fail-400-happy-no-user-id.json`, `evidence/work/recipients/22-fail-404-junk-user-id.json`

## Per-endpoint narrative (2–4 lines each)

### `GET /v1/countries`
First 2xx on iteration 1 with default headers. Envelope `{count: 250, data: [...]}` — 250 entries, alpha-3 country codes (`AFG`, `USA`, `MEX`), with `name`, `postal_code_format` (regex), and full `subdivisions[]` for each country. Cold-call latency 1009 ms; warm latency settled to 307/360/373 ms (n=4 samples). `X-Api-Version` request header is a no-op echo (DRIFT-A6). Reference page has no response example (GAP-30 confirmed via empirical inference). Doc sufficiency: PARTIAL — the docs would let you call it, but you'd be guessing the response shape until first contact.

### `GET /v1/banks`
The most painful endpoint of the batch. **Two doc errors stacked:** (1) the Reference page documents path `/banks` but the working path is `/v1/banks` (DRIFT-A2/GAP-32 confirmed); (2) the doc-implied param name `country` is rejected — the real param is `country_code` (DRIFT-A4); (3) **only `CO` works** — `MX`, `MEX`, `co`, `Colombia` all 400 (DRIFT-A3). The `/banks` Reference path returns HTTP 200 with body strings `"Blocked"` (CF WAF) or `"error code: 522"` (CF origin-unreachable) — actively misleading. Reference data for non-Colombian banks is **unavailable** at runtime as of this probe — a platform-level claim worth raising to PD. Doc sufficiency: **NO**.

### `GET /v1/users` (list)
First 2xx on iteration 1, envelope `{data: [...], pagination: {total, limit, offset, has_more}}` exactly matches docs. Cold latency 252 ms; warm n=4 samples 226–295 ms (median 247 ms). **Two surprises:** `?limit=100000` triggers a **500 Internal Server Error** (DRIFT-A5), and the existing user records in the response surface **both `"US"` and `"USA"`** in `registered_address.country` — confirming DRIFT-5 (no normalization) is now a *persistent* data-quality issue, not a one-call accident. The list view shows **identical 15-key user objects** to the create response (DRIFT-4 echoed) — `verification_mode`, `verification_status`, `associated_persons` all present.

### `GET /v1/virtual-accounts` (list)
Empty `data[]` (no VAs created yet — gated on Batch D). Envelope identical to `/v1/users` (`{data, pagination}`) — pagination consistency holds across both endpoints. Same `?limit=100000` → **500** bug (DRIFT-A5) — server-side input handling shares code between these endpoints. Cold latency 278 ms; warm n=4 median 261 ms. Doc sufficiency: PARTIAL (docs predict the empty-list shape; the 500 on big-limit is unflagged).

### `GET /v1/recipients` (list)
**Never reached a 2xx** — by design, the endpoint hardcodes a 400 unless `user_id` is supplied. Docs (`flow-design.md` §3.5) note this. Returns a **distinct error envelope** (`{error: {code, message, details}}`) — DRIFT-A8 — making it the third Batch-A endpoint emitting an incompatible error shape. Empty-`user_id` returns 400; junk UUID returns 404 (`{error: {code: "USER_NOT_FOUND" or similar}}`). Latency to validation 220–308 ms (n=4 median 284 ms). Doc sufficiency: PARTIAL — docs predict the requirement but not the envelope.

## Cross-cutting findings (Batch A)

- **GAP-32 resolved (DRIFT-A2):** The Reference page documents `/banks` (no `/v1/`). At runtime, `/banks` returns **HTTP 200 with non-JSON body** (`"Blocked"` from Cloudflare WAF when bearer omitted, `"error code: 522"` from CF when bearer present). The **working path is `/v1/banks`**. **The docs are wrong** — and worse, they return HTTP 200, so naive `if resp.status == 200: parse_json(resp.body)` will crash on parse rather than catch the failure gracefully.
- **GAP-04 partial-auth pattern:** None of the 5 Batch-A endpoints accept `x-api-key`-alone. Bearer is mandatory across `/v1/countries`, `/v1/users`, `/v1/virtual-accounts`, `/v1/recipients`, and `/v1/banks`. The known "API-key alone" surface remains limited to `POST /webhooks/register` per the docs. (DRIFT-A7)
- **ISO-3166 normalization pattern (`/v1/banks`):** **No normalization.** Strict uppercase alpha-2 only. `co` (lowercase) → 400, `COL` (alpha-3) → 400, `MX` → 400 ("Only CO supported"), `Colombia` → 400. Combined with the `/v1/users` finding (DRIFT-5: both `"US"` and `"USA"` accepted and persisted), the platform now empirically uses **two incompatible country-code conventions** in two adjacent endpoints, **with no validation on the user side and no normalization on either** — a guaranteed data-quality bomb at any join time. (DRIFT-A3)
- **GAP-01 (X-Api-Version):** Request header `X-Api-Version: 2025-01-01` is **silently echoed back in the response header**, response body unchanged. The server effectively ignores the request header for contract-versioning purposes — it's only output, not input. (DRIFT-A6)
- **Pagination behavior summary:**
  - **Shape consistency:** `/v1/users` and `/v1/virtual-accounts` share envelope `{data, pagination:{total, limit, offset, has_more}}` — consistent across the two probed.
  - **Default limit:** 10 (observed in `pagination.limit` on default calls).
  - **High limit (`100000`):** **500 Internal Server Error** on `/v1/users` and `/v1/virtual-accounts` (DRIFT-A5). Validation-fast (~241–251 ms) — the server inspects the value but throws rather than returns a structured 400.
  - **Deep offset (`99999`):** Graceful. Returns `{data: [], pagination: {offset: 99999, has_more: false}}` with no latency penalty (~254 ms vs 252 ms default — within noise).
  - **`/v1/recipients`** has no pagination at all (GAP-15 confirmed — it never reached the data-fetch path due to user_id-required gate).
- **Error envelope inventory (Batch A — DRIFT-A1):** Four distinct shapes observed in 22 captured failures:
  1. **G — Gateway:** `{message}` + `x-amzn-errortype` header (401/403, missing creds).
  2. **A — Zod validation:** `{error: <string>, details: [{path, message, code}]}` (400 query/body validation).
  3. **B — Typed error:** `{error: {code, message, details: {}}}` (400 on `/v1/recipients`).
  4. **C — Internal:** `{status: "error", message}` (500 on big `limit`).
  → No common field across all four — `code` lives in `details[]` in A but at `error.code` in B; `message` lives at root in G/C but at `error.message` in B. A generic `errorMessage(resp)` helper for an SDK has to pattern-match four ways.
- **Latency cluster (preliminary, n=4 per endpoint):**
  - `/v1/countries`: median 366 ms — heaviest payload (250 country objects with subdivisions, ~2 MB ungzipped).
  - `/v1/banks?country_code=CO`: median 268 ms — small payload (~28 banks).
  - `/v1/users` (list): median 247 ms — lightest pagination metadata + small `data[]`.
  - `/v1/virtual-accounts` (list): median 261 ms — empty data, same pagination.
  - `/v1/recipients` (validation path): median 281 ms — fails fast, no DB read.
  - All comparable to `POST /v1/users` warm baseline (median 299 ms) — Batch A endpoints land slightly faster, consistent with read-only no-validation-heavy paths.

## Coordination notes
- **No modifications to `evidence/work/run_flow.py`.** `batch_A.py` imports `auth`, `BASE_URL`, `API_KEY` from it; defines its own local `capture()` to keep state isolated.
- **No collisions with sibling batches:** evidence written to `evidence/work/{countries,banks,users-list,va-list,recipients}/`. The path `evidence/work/users/` is left untouched (owned by Batch B).
- **No raw secrets in any evidence file.** All `x-api-key`, `Authorization`, `set-cookie` headers redacted via `_redact.py`. Confirmed by sampling: `countries/01-success-happy.json` line 11–12 show `REDACTED(40)` and `REDACTED(872)`.
- **Drift IDs are Batch-A-namespaced** (`DRIFT-A1`..`DRIFT-A8`). Architect to resequence at merge time per DEC-005 — these are likely DRIFT-6..DRIFT-13 in the canonical sequence.
- **Probes per endpoint:** countries 7, banks 10 (+7 follow-up = 17 total), users-list 7, va-list 7, recipients 8. **Total: 46 evidence files** under `evidence/work/{countries,banks,users-list,va-list,recipients}/` + 5 latency files under `evidence/work/latency/`.
