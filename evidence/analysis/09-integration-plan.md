# Phase 2 — Master Integration Plan

**Created:** 2026-05-27 (DEC-006)
**Status:** ACTIVE — guides remaining 28 endpoint probes + webhook decision
**Author:** data-architect

## 0. TL;DR

- **Endpoints remaining:** 28 of 30 (auth + POST /v1/users probed). 30th endpoint (`POST /v1/users/{id}/wallets`) is the GAP-37 Wallets-probe — separately tracked.
- **Batches:** 7 (A → G), ordered by dependency. Each unlocks a specific resource state for the next.
- **Webhook receiver decision:** **NO** for Phase 2 happy-path. Polling covers every async resource within sandbox latency tolerance; GAP-11 (delivery semantics absent) makes webhooks a Phase-3 adversarial target, not a Phase-2 dependency. Spin up the FastAPI receiver in Phase 3 only.
- **Estimated drift:** 28 endpoints × DRIFT-rate of 2.5/endpoint (running mean from auth + users) ≈ **~70 drift events expected** across Phase 2. Concentrated in Batches B (KYB), E (Quotations — GAP-31), and F (Payouts — GAP-19/23).
- **Phase 3 readiness:** Batches A + B + C should be Phase-3 ready by mid-Phase 2; Batch F is the gating dependency for adversarial money-movement.

---

## 1. Endpoint Inventory & Status

Status legend: ✅ probed | ⏳ pending | 🚫 blocked | ❓ doc-clarification dependent

| # | Method | Path | Family | Status | Dependencies | Sync/Async |
|---|---|---|---|---|---|---|
| 1 | POST | `/auth` | Auth | ✅ | — | sync |
| 2 | POST | `/v1/users` | Users | ✅ | auth | sync (returns CREATED; verification async) |
| 3 | GET | `/v1/countries` | RefData | ⏳ | auth | sync |
| 4 | GET | `/banks?country_code=XX` | RefData | ⏳ | auth | sync (unversioned — GAP-32) |
| 5 | GET | `/v1/users` | Users | ⏳ | auth | sync (offset pagination) |
| 6 | GET | `/v1/users/{userId}` | Users | ⏳ | user_id | sync |
| 7 | PUT | `/v1/users/{userId}` | Users | ⏳ | user_id | sync (may re-trigger verification) |
| 8 | POST | `/v1/users/{userId}/verifications` | Users (legacy) | ⏳ | user_id (CREATED state) | async (returns verification_url) |
| 9 | POST | `/v1/users/{userId}/wallets` | Wallets | ❓ | user_id | unknown — GAP-37 probe |
| 10 | POST | `/v1/recipients` | Recipients | ⏳ | user_id (any state?) | sync |
| 11 | GET | `/v1/recipients?user_id={uuid}` | Recipients | ⏳ | user_id | sync (no pagination — GAP-15) |
| 12 | GET | `/v1/recipients/{recipientId}` | Recipients | ⏳ | recipient_id | sync |
| 13 | POST | `/v1/virtual-accounts` | VirtualAccounts | ❓ | user VERIFIED | async (pending → active) |
| 14 | GET | `/v1/virtual-accounts` | VirtualAccounts | ⏳ | auth | sync (offset pagination) |
| 15 | GET | `/v1/virtual-accounts/{id}` | VirtualAccounts | ⏳ | va_id | sync |
| 16 | GET | `/v1/users/{userId}/virtual-accounts` | VirtualAccounts | ⏳ | user_id | sync |
| 17 | GET | `/v1/virtual-accounts/{id}/balance` | Balance | ⏳ | va_id (fiat mode + active) | sync |
| 18 | GET | `/v1/virtual-accounts/{id}/deposits` | Deposits | ⏳ | va_id (active) | sync (limit only — GAP-09) |
| 19 | GET | `/v1/virtual-accounts/{id}/deposits/{depositId}` | Deposits | ⏳ | deposit_id | sync |
| 20 | GET | `/v1/virtual-accounts/deposits` | Deposits | ⏳ | auth | sync (client-wide) |
| 21 | POST | `/v1/quotations` | Quotations | 🚫❓ | auth | sync (10-min TTL) — **GAP-31** blocker (two schemas) |
| 22 | POST | `/v1/payins/fees` | PayIns | ⏳ | auth | sync (10-min TTL fee_quote_id) |
| 23 | POST | `/v1/payins` | PayIns | ⏳ | user (KYC?? — GAP-24) | async |
| 24 | GET | `/v1/payins/{payinId}` | PayIns | ⏳ | payin_id | sync |
| 25 | POST | `/v1/virtual-accounts/{id}/payout/preview` | Payouts | ⏳ | va_id + quote_id | sync (dry-run) |
| 26 | POST | `/v1/virtual-accounts/{id}/payout` | Payouts | ⏳ | va_id + recipient_id + quote_id | async (CREATED → COMPLETED) |
| 27 | GET | `/v1/payouts?user_id={uuid}` | Payouts | ⏳ | user_id (required — GAP-18) | sync (page-based — GAP-09) |
| 28 | GET | `/v1/payouts/{payoutId}` | Payouts | ⏳ | payout_id | sync |
| 29 | POST | `/v1/payment-link` | PayLink | ⏳ | user_id | sync |
| 30 | POST | `/v1/virtual-accounts/{id}/liquidation-address` | LiqAddr | ⏳ | va_id (active) + user VERIFIED | sync (then long-running sweeps) |
| 31 | GET | `/v1/virtual-accounts/{id}/liquidation-address` | LiqAddr | ⏳ | liq created | sync |
| 32 | POST | `/webhooks/register` | Webhooks | ⏳ | x-api-key only (no JWT) | sync |

Note: catalog row count is **32** (we treat sub-resources and listing variants as separate endpoint-probes). The "30 endpoints" figure in the brief collapses some; this plan keeps them split for probe-granularity.

---

## 2. Dependency Map

```mermaid
graph TD
  AUTH[POST /auth] --> RefData[Batch A: countries, banks, lists]
  AUTH --> Users[Batch B: /v1/users family]
  Users -->|user_id| Verif[Batch B: verifications submit + poll GET /v1/users/{id}]
  Verif -->|status=VERIFIED| VA[Batch D: VA create + activation poll]
  Users -->|user_id| Recip[Batch C: recipients]
  AUTH --> Quote[Batch E: /v1/quotations — GAP-31 BLOCKER]
  VA -->|active + balance| Payout[Batch F: payout preview + initiate]
  Recip --> Payout
  Quote --> Payout
  Users --> PayIn[Batch F: /v1/payins family]
  Quote --> PayInFees[Batch E: payins/fees]
  VA --> LiqAddr[Batch F: liquidation-address]
  Recip --> LiqAddr
  Users --> PayLink[Batch F: payment-link]
  AUTH --> Webhooks[Batch G: webhooks/register — Phase 3 only]
  VA -.->|depends external| Deposit[external: deposit simulation — GAP-22]
```

Critical paths:
- **Money-movement chain (longest):** auth → users → verifications → poll VERIFIED → VA create → poll active → quotation → recipient → payout. ~7 dependent calls + 2 async waits.
- **Quote chain (blocked):** Batch E (quotations) is the GAP-31 critical-path blocker. Until we resolve which schema (Guides vs Reference) is canonical, Batch F (payouts) cannot execute correctly. **First Batch E task: schema-disambiguation probe.**

---

## 3. Execution Batches

### Batch A — Foundations & Reference Data (cheap reads, broad coverage)
- **Goal:** confirm auth-only endpoints work, build country/bank lookups for downstream payloads, measure list-endpoint shape inconsistency (GAP-03), capture ISO-3166 acceptance matrix (Finding #11).
- **Endpoints:** #3 `GET /v1/countries`, #4 `GET /banks` (with country_code=MX/MEX/mx/Mexico variants), #5 `GET /v1/users`, #11 `GET /v1/recipients?user_id=`, #14 `GET /v1/virtual-accounts`, #20 `GET /v1/virtual-accounts/deposits`, #27 `GET /v1/payouts?user_id=`.
- **Prerequisites:** auth (Batch 0, done).
- **Drift candidates:** GAP-32 (`/banks` unversioned), GAP-20 (alpha-2/alpha-3), GAP-09 (mixed pagination shapes), GAP-03 (envelope variance — `{data, pagination}` vs `{payouts, total, page}` vs flat).
- **Complexity:** S × 7. All reads, no state mutation.

### Batch B — User lifecycle & verification
- **Goal:** drive a user from CREATED → VERIFIED (or capture why we can't), confirm DRIFT-3 (verification not auto-triggered) is reproducible, populate the legacy verifications endpoint.
- **Endpoints:** #6 `GET /v1/users/{userId}`, #7 `PUT /v1/users/{userId}` (with sensitive fields → expect re-verification), #8 `POST /v1/users/{id}/verifications`, #9 `POST /v1/users/{id}/wallets` (GAP-37 probe).
- **Prerequisites:** Batch A done (countries/banks lookup ready); existing user_id from Phase 2 probe-1.
- **Drift candidates:** GAP-14 (dual enum), GAP-37 (Wallets missing — confirm or undercut Finding #5), DRIFT-3 follow-up (what payload DOES auto-trigger?), GAP-23 (OTP endpoint hidden? — defer to Batch F).
- **Complexity:** M × 4. PUT may cascade re-verification; wallets probe is exploratory.

### Batch C — Recipients (polymorphic)
- **Goal:** exercise the 22-variant recipient polymorphism, validate GAP-33 (Reference page doesn't render variants), build a SPEI recipient for Batch F payouts.
- **Endpoints:** #10 `POST /v1/recipients` (ACH, WIRE, SPEI, PSE, SWIFT, BRL, WALLET — 7 variants minimum), #11 list, #12 get.
- **Prerequisites:** user_id from Batch B (Recipient doesn't strictly require VERIFIED — UNDOCUMENTED, probe this).
- **Drift candidates:** GAP-16 (bank_address string-vs-object), GAP-17 (Spanish enum strings on CLP), GAP-19 (currency casing), idempotency 202-on-replay quirk, GAP-15 (no pagination on list).
- **Complexity:** L × 1 collective (one polymorphic endpoint, many variants).

### Batch D — Virtual Accounts (async)
- **Goal:** create a VA, drive to active, fetch balance + deposits. This is the gating dependency for Batch F money-movement.
- **Endpoints:** #13 `POST /v1/virtual-accounts`, #15 `GET /v1/virtual-accounts/{id}` (poll for active), #16 user VA list, #17 balance, #18 deposits list, #19 single deposit (if any).
- **Prerequisites:** Batch B user VERIFIED. **Strong dependency** — VA create returns 400 if user not verified.
- **Drift candidates:** GAP-22 (sandbox deposit simulation undocumented — Batch D might fail at deposit step if sandbox doesn't auto-credit), GAP-34 (Reference stale: `provider`, `mode`, `destination`, `markup` fields), Finding #8.
- **Complexity:** M × 5 + 1 async-poll. The "is sandbox verification real?" question (DRIFT-3) cascades here.

### Batch E — Quotations & PayIn-fees (read-style writes, no state mutation)
- **Goal:** **Resolve GAP-31 (Quotations Reference vs Guides schema drift) — this is the single most important Phase 2 disambiguation.** Then create PayIn fee quotes.
- **Endpoints:** #21 `POST /v1/quotations` (3 probes: Guides schema, Reference schema, hybrid), #22 `POST /v1/payins/fees`.
- **Prerequisites:** auth + Batch A (bank_code lookup).
- **Drift candidates:** GAP-31 (the headline), GAP-29 (Quotations Reference hidden), GAP-34 (stablecoin base_currency from Apr-14 changelog), GAP-05 (Shape B error envelopes here).
- **Complexity:** M × 2. Batch E is **first-mover-after-foundations** because quotations gates Batch F.

### Batch F — Money movement (write, with-side-effects)
- **Goal:** execute one full Recipe B (USD → MXN fiat payout) and Recipe C (MXN → USDT PayIn), capture state machines empirically, complete the minimum-viable integration flow.
- **Endpoints:** #25 payout/preview, #26 payout initiate, #28 GET payout, #29 payment-link, #30 liquidation-address create, #31 liquidation-address get, #23 payins create, #24 GET payin.
- **Prerequisites:** Batches B, C, D, E all green. Active VA + balance + recipient_id + quote_id.
- **Drift candidates:** GAP-19 (payout casing), GAP-23 (OTP endpoint hidden), GAP-25 (PayIn SLA folklore), GAP-26 (recipient inline vs by-id on liquidation), GAP-28 (no cancel-payout endpoint).
- **Complexity:** L × 8. This is the Phase-3 prerequisite — once Batch F is green, adversarial harnesses can run.

### Batch G — Webhooks (deferred decision; see § 5)
- **Goal:** register a webhook URL, observe whether deliveries arrive without a receiver, capture the registration response shape, document GAP-11/GAP-21 empirically.
- **Endpoints:** #32 `POST /webhooks/register` only.
- **Prerequisites:** auth + ngrok URL (or webhook.site URL for passive capture).
- **Drift candidates:** GAP-11 (delivery semantics), GAP-21 (no PUT/DELETE), Finding #4 (`secret: ""` / null / omitted), Phase-1 noted ZERO error codes on Reference page.
- **Complexity:** S × 1 (registration). Receiving is **Phase 3** per webhook decision.

---

## 4. Per-Endpoint Plan

> Format kept compact — each entry ~10 lines. Probe checklist is the union of mutations that apply per the matrix in § 6.

### Batch A

#### GET /v1/countries
- **Batch:** A
- **Prerequisites:** auth
- **Sync/Async:** sync
- **Documented schema:** `[ { code (alpha-3?), name, subdivisions[], postal_code_format } ]` — flow-design §3.11. Total ~250 entries.
- **Expected drift:** GAP-30 (no Reference response example), GAP-03 (envelope shape unclear — flat array or `{data: []}`?), GAP-20 (alpha-2 vs alpha-3 — likely alpha-3 here).
- **Probe checklist:**
  - [ ] Happy-path GET
  - [ ] Omit `x-api-key` → expect 401/403
  - [ ] Omit Authorization → does API key alone suffice (GAP-04)?
  - [ ] Send `X-Api-Version: 2025-01-01` vs omitted vs `2026-04-14` → diff response
  - [ ] Capture envelope shape; cross-reference response header `x-api-version`
- **Doc-sufficiency prediction:** PARTIAL (no Reference response example — GAP-30 will bite).
- **Sample notes:** Used downstream to validate `user.address_country` enum. If returns alpha-3 here but `/banks` expects alpha-2, GAP-20 confirmed empirically.

#### GET /banks?country_code=XX
- **Batch:** A
- **Prerequisites:** auth
- **Sync/Async:** sync
- **Documented schema:** `[ { bank_code, bank_name, ... } ]` — flow-design §3.11. **No `/v1/` prefix** (GAP-32).
- **Expected drift:** GAP-32 (unversioned), GAP-20 (alpha-2 required while users take alpha-3), GAP-30 (no response example), Finding #6 + Finding #11.
- **Probe checklist:**
  - [ ] Happy-path with `country_code=MX`
  - [ ] alpha-3 (`MEX`) — does it 404 or 200?
  - [ ] lowercase (`mx`)
  - [ ] English name (`Mexico`)
  - [ ] Omitted country_code → does it return all banks or 400?
  - [ ] **GAP-32 probe:** hit `/v1/banks?country_code=MX` — does the unversioned shadow surface exist? If both 200, structural inventory finding (API9).
  - [ ] Omit `x-api-key` → expect 4xx
- **Doc-sufficiency:** NO — page doesn't state alpha-2 vs alpha-3.
- **Sample notes:** Bootstrap dependency for every LATAM payout recipient (PSE/CLP/ARS).

#### GET /v1/users (list)
- **Batch:** A
- **Prerequisites:** auth
- **Sync/Async:** sync (offset pagination)
- **Documented schema:** `{ data: [...], pagination: { total, limit, offset, has_more } }` — flow-design §3.2.
- **Expected drift:** GAP-09 (pagination shape — already at users; will diverge from /v1/payouts), GAP-14 (status filter enum overlap), GAP-03 (envelope).
- **Probe checklist:**
  - [ ] Happy-path no filters
  - [ ] `limit=1` then `offset=1` → verify pagination math
  - [ ] `limit=101` → 4xx with allowed_values?
  - [ ] `status=CREATED` (modern) and `status=ACTIVE` (legacy) — both accepted?
  - [ ] `verification_status=verified` (legacy lowercase)
  - [ ] `created_after=invalid` → error shape
  - [ ] Concurrent dupes (low value here; skip unless free)
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Confirms our user from probe #2 is listed.

#### GET /v1/recipients?user_id={uuid}
- **Batch:** A
- **Prerequisites:** auth + user_id
- **Sync/Async:** sync
- **Documented schema:** flat array — **no pagination** (GAP-15).
- **Expected drift:** GAP-15 (no pagination — empty result OK for now, but document the unbounded behavior), GAP-03 (envelope).
- **Probe checklist:**
  - [ ] Happy-path with our user_id (empty array initially)
  - [ ] Omit `user_id` → 400 expected
  - [ ] Junk user_id → 400 or empty?
  - [ ] Cross-tenant user_id (another client's) → 403/404 (security-adjacent — capture, defer exploit to Phase 3)
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Becomes more useful after Batch C populates it.

#### GET /v1/virtual-accounts (list)
- **Batch:** A
- **Prerequisites:** auth
- **Sync/Async:** sync (offset pagination)
- **Documented schema:** `{ data: [...], pagination }` — flow-design §3.4.
- **Expected drift:** GAP-04 (Bearer-or-key — Reference says `x-api-key` alone may work), GAP-09 (pagination consistency check).
- **Probe checklist:**
  - [ ] Happy-path
  - [ ] Bearer-only (no x-api-key) — does API key alone suffice?
  - [ ] x-api-key only (no Bearer)
  - [ ] Filter `status=pending` / `mode=fiat` / `user_id={our}` / `search=<email>`
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Empty list expected until Batch D.

#### GET /v1/virtual-accounts/deposits (client-wide)
- **Batch:** A
- **Prerequisites:** auth
- **Sync/Async:** sync
- **Documented schema:** flow-design §3.4 — same page as the per-VA variant. Path collision risk.
- **Expected drift:** GAP-09, GAP-03, potential path-ambiguity in OpenAPI codegen.
- **Probe checklist:**
  - [ ] Happy-path no filters
  - [ ] Filter by `status`, `account_id`, date range
  - [ ] Diff envelope shape vs the per-VA endpoint
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Useful for audit-style queries; probably empty initially.

#### GET /v1/payouts?user_id={uuid}
- **Batch:** A
- **Prerequisites:** auth + user_id
- **Sync/Async:** sync (**page-based** — GAP-09)
- **Documented schema:** `{ payouts: [...], total, page, limit, total_pages }` — flow-design §3.7.
- **Expected drift:** GAP-09 (different shape from /v1/users list), GAP-18 (user_id required — confirm 400 if omitted), GAP-19 (status casing).
- **Probe checklist:**
  - [ ] Omit `user_id` → confirm 400 (GAP-18)
  - [ ] Happy-path with our user_id (empty)
  - [ ] `page=0` (illegal? — docs say ≥1)
  - [ ] `status=completed` (lowercase, per guide) vs `COMPLETED` (uppercase, per schema)
  - [ ] `status=returned` — accepted? (GAP-19)
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Empty until Batch F; but the pagination-shape diff is captured now.

### Batch B

#### GET /v1/users/{userId}
- **Batch:** B
- **Prerequisites:** user_id from earlier probe
- **Sync/Async:** sync
- **Documented schema:** full `UserResponse` — flow-design §3.2.
- **Expected drift:** DRIFT-4 echo (15 keys vs documented 4), GAP-14 (dual enums emitted), `missing_fields` block — verify the 21-field count from DRIFT-3.
- **Probe checklist:**
  - [ ] Happy-path with our user_id
  - [ ] Junk UUID → 400 `invalid_user_id`
  - [ ] Well-formed but nonexistent UUID → 404 `not_found`
  - [ ] Cross-tenant UUID (Phase 3 BOLA — defer)
  - [ ] Omit Authorization
- **Doc-sufficiency:** PARTIAL (response shape grossly under-documented; DRIFT-4 already proven).
- **Sample notes:** Confirms `verification_triggered` value persists in subsequent reads.

#### PUT /v1/users/{userId}
- **Batch:** B
- **Prerequisites:** user_id, CREATED state
- **Sync/Async:** sync (but may trigger async verification)
- **Documented schema:** flow-design §3.2 — sensitive-field update sets `requires_reverification: true`.
- **Expected drift:** GAP-19 (status casing in `requires_reverification` response), DRIFT-3 follow-up (will THIS update finally trigger verification?), GAP-05 (409 on email-in-use envelope).
- **Probe checklist:**
  - [ ] Update non-sensitive field (`metadata` or similar) → `requires_reverification: false`
  - [ ] Update sensitive field (`first_name`, `address_city`) → expect `requires_reverification: true` + `verification_triggered: true`
  - [ ] Update with empty body → 400
  - [ ] Submit `missing_fields` completion (add the 13 ACT-missing fields per DRIFT-3) → confirm verification finally triggers
  - [ ] Idempotency: PUT same body twice — server-side semantics? (PUT is implicitly idempotent; no header)
  - [ ] Concurrent PUTs with conflicting fields
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** **This endpoint resolves DRIFT-3 — if completing `missing_fields` triggers verification, the docs need a "minimum-to-verify" example.**

#### POST /v1/users/{userId}/verifications
- **Batch:** B
- **Prerequisites:** user_id (CREATED state), idempotency-key
- **Sync/Async:** sync response, async verification flow
- **Documented schema:** `{ type: "embedded-link", redirect_uri }` → `{ verification_url }` — flow-design §3.2.
- **Expected drift:** GAP-08 (idempotency required confirmation), shape of `verification_url`, whether embedded-link works in sandbox at all.
- **Probe checklist:**
  - [ ] Happy-path with `type: "embedded-link"`, valid redirect_uri
  - [ ] Omit idempotency-key → 400 expected
  - [ ] Replay same key + same body → 200 cached
  - [ ] Replay same key + DIFFERENT redirect_uri → 409 `IDEMPOTENCY_CONFLICT` (Shape A or B?)
  - [ ] Submit on an ALREADY-VERIFIED user → 409 / 403?
  - [ ] Unknown `type` enum value → 4xx with allowed_values?
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Legacy endpoint per §3.2 — competes with auto-trigger. Whether sandbox honors verification_url is unknown.

#### POST /v1/users/{userId}/wallets (GAP-37 probe)
- **Batch:** B
- **Prerequisites:** user_id
- **Sync/Async:** unknown
- **Documented schema:** **None visible.** Listed in idempotency.md only.
- **Expected drift:** GAP-37 (the Wallets-missing finding). Outcome dictates whether Finding #5 stays HIGH (genuinely missing) or escalates to "undocumented surface" CRITICAL.
- **Probe checklist:**
  - [ ] POST with empty body — capture 4xx
  - [ ] POST with `{}` → 400 / 404?
  - [ ] POST with a guessed body `{currency: "USDC", network: "polygon"}`
  - [ ] **Also probe siblings:** `GET /v1/users/{id}/wallets`, `GET /v1/wallets`, `GET /v1/wallets/{id}` — does the surface exist?
  - [ ] Idempotency-key required per the idempotency guide — confirm
- **Doc-sufficiency:** NO (definitionally — that's the whole finding).
- **Sample notes:** If any 2xx returns here, escalate Finding #5 and add a new GAP for review.

### Batch C

#### POST /v1/recipients (polymorphic — many variants)
- **Batch:** C
- **Prerequisites:** user_id (verification state TBD — UNDOCUMENTED, probe), idempotency-key
- **Sync/Async:** sync
- **Documented schema:** §3.5 — 22 account_type variants. Reference page does **not** render variants (GAP-33).
- **Expected drift:** GAP-16 (bank_address string vs object across ACH/WIRE), GAP-17 (Spanish CLP enum strings), GAP-19 (status casing), idempotency 202-on-replay, GAP-20 (country fields), GAP-33 (Reference incomplete).
- **Probe checklist (run for SPEI as the canonical case; subset for the other variants):**
  - [ ] **SPEI** (MXN) happy-path — CLABE 18 digits, doc_type=rfc → 201
  - [ ] **ACH** (USD domestic) — `bank_address` as **string**
  - [ ] **WIRE** (USD domestic) — `bank_address` as **object** (GAP-16 confirmation)
  - [ ] **PSE** (COP) — requires `bank_code` from /banks (cross-test GAP-20: alpha-2 vs alpha-3 in `doc_country_code`)
  - [ ] **BRL** (PIX) — `pix_key_type` enum
  - [ ] **SWIFT** — `swift_code` length 8 or 11, `bank_address` object
  - [ ] **CLP** — Spanish-string enum `"Cuenta corriente"` (GAP-17)
  - [ ] **WALLET** — USDT on `solana` (should reject per Apr-14 changelog — USDT only tron/polygon)
  - [ ] Idempotency replay same body → 202 (unusual — flow-design §3.5 quirk)
  - [ ] Idempotency replay different body → 409 — capture Shape A or Shape B
  - [ ] Omit idempotency-key → 400
  - [ ] Concurrent identical SPEI creates → both 201? or one 409? race semantics
- **Doc-sufficiency:** PARTIAL (Reference page hides variants — GAP-33 mandates cross-reference to Guides).
- **Sample notes:** SPEI recipient created here is the dependency for Batch F payout. The 202-on-replay behavior is a generic-SDK-killer — capture verbatim.

#### GET /v1/recipients/{recipientId}
- **Batch:** C
- **Prerequisites:** recipient_id
- **Sync/Async:** sync
- **Documented schema:** §3.5 — `account_details` masked.
- **Expected drift:** masking format (`****7890` — is leading length preserved?), GAP-03 envelope.
- **Probe checklist:**
  - [ ] Happy-path
  - [ ] Junk UUID → 400 / 404
  - [ ] Cross-tenant UUID (Phase 3 BOLA, defer)
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Quick read. Use to verify our SPEI recipient persisted.

### Batch D

#### POST /v1/virtual-accounts
- **Batch:** D
- **Prerequisites:** user VERIFIED, idempotency-key
- **Sync/Async:** async (pending → activating → active)
- **Documented schema:** §3.4 — `user_id`, `type`, `bank` or `provider`, optional `destination`, `mode`, `markup`, `description`. Apr-14 changelog added `provider`, `mode`, `destination`, `markup` (GAP-34: Reference page stale).
- **Expected drift:** GAP-22 (sandbox deposit simulation — does VA ever reach active?), GAP-34 (Reference omits fields — empirically confirm which work), Finding #8.
- **Probe checklist:**
  - [ ] Happy-path: minimum payload `{user_id, type: "US_BANK", bank: "portage"}` → 201 status `pending`
  - [ ] **Full Apr-14 body:** include `provider: "portage"`, `mode: "CRYPTO"`, `destination`, `markup` — which fields survive? Which are silently dropped (DRIFT-class)?
  - [ ] Both `bank: "portage"` AND `provider: "act"` — does conflict 400 or does one win silently?
  - [ ] Without user VERIFIED → expect 400 `validation_error` (confirms verification gate)
  - [ ] Idempotency replay same body → cached 201
  - [ ] Idempotency replay different body → 409
  - [ ] Omit idempotency-key → 400
- **Doc-sufficiency:** PARTIAL (Reference page is stale — Guides + changelog needed).
- **Sample notes:** **Likely fails because user is not VERIFIED in sandbox** (DRIFT-3 cascade). If so, Batch D blocks — flag as **🚫 blocked** and escalate to @Nicolle / @Diego.

#### GET /v1/virtual-accounts/{id}
- **Batch:** D
- **Prerequisites:** va_id
- **Sync/Async:** sync (polled for state)
- **Documented schema:** §3.4 — VA object; `source_deposit_instructions` populated when `active`.
- **Expected drift:** state transition timing (how long pending → active in sandbox?), GAP-30 (no response example), case sensitivity (`pending` lowercase vs the modern uppercase elsewhere).
- **Probe checklist:**
  - [ ] Happy-path immediately after create
  - [ ] Poll every 5s for ≤2min — capture state transitions
  - [ ] After active: confirm `source_deposit_instructions` shape (ABA routing, account number, beneficiary name)
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Polling alternative to webhook — confirms polling-only strategy works in sandbox.

#### GET /v1/users/{userId}/virtual-accounts
- **Batch:** D
- **Prerequisites:** user_id with at least one VA
- **Sync/Async:** sync
- **Documented schema:** array of VAs.
- **Expected drift:** GAP-03 (envelope: array or `{data:[]}`?).
- **Probe checklist:** happy-path, junk user_id, cross-tenant.
- **Doc-sufficiency:** PARTIAL.
- **Sample notes:** Trivial.

#### GET /v1/virtual-accounts/{id}/balance
- **Batch:** D
- **Prerequisites:** va_id, mode=fiat, status=active
- **Sync/Async:** sync
- **Documented schema:** `{ virtual_account_id, available_balance, currency: "USD", updated_at }`.
- **Expected drift:** GAP-22 (deposit simulation needed to make balance > 0), `invalid_operation` error if crypto-mode (Shape A).
- **Probe checklist:**
  - [ ] Happy-path (likely 0.00)
  - [ ] Against a crypto-mode VA (if Batch D probe with `mode: CRYPTO` succeeded) → expect 400 `invalid_operation`
- **Doc-sufficiency:** PARTIAL.

#### GET /v1/virtual-accounts/{id}/deposits (list)
- **Batch:** D
- **Prerequisites:** va_id
- **Sync/Async:** sync
- **Documented schema:** `{ deposits: [] }` — GAP-09: **limit only, no offset**.
- **Expected drift:** GAP-09 (unique pagination shape), empty array shape.
- **Probe checklist:**
  - [ ] Happy-path (empty)
  - [ ] `limit=101` → 4xx?
  - [ ] `offset=10` — silently ignored or 4xx?
- **Doc-sufficiency:** PARTIAL.

#### GET /v1/virtual-accounts/{id}/deposits/{depositId}
- **Batch:** D
- **Prerequisites:** deposit_id (likely none in sandbox without deposit simulation — **🚫 blocked**)
- **Sync/Async:** sync
- **Documented schema:** `EnrichedDeposit` with `sender`, `payment_rail`, `settlement_tx_hash`.
- **Expected drift:** unreachable without GAP-22 resolution.
- **Probe checklist:** N/A unless we acquire a deposit_id (escalate).
- **Doc-sufficiency:** Cannot evaluate empirically — depends on GAP-22.

### Batch E

#### POST /v1/quotations (GAP-31 — schema disambiguation)
- **Batch:** E
- **Prerequisites:** auth
- **Sync/Async:** sync (10-min TTL on quote)
- **Documented schema:** **TWO COEXISTING.** Guides: `{base_currency, quote_currency, amount, amount_in_destination}`. Reference: `{amount, recipient_id, account_type, wallet_network, wallet_token, inverse_calculation, payment_instructions, client_markup}`.
- **Expected drift:** GAP-31 (the headline), GAP-29 (Reference URL hidden), GAP-34 (stablecoin base currencies from changelog), GAP-05 (Shape B error envelope).
- **Probe checklist:**
  - [ ] **Probe A — Guides schema:** `{base_currency: "USD", quote_currency: "MXN", amount: 1000}` → capture status + body
  - [ ] **Probe B — Reference schema:** `{amount: 1000, account_type: "SPEI", recipient_id: <our SPEI recipient_id>}` → capture status + body
  - [ ] **Probe C — Union:** all fields from both → 400 / 200 / silently accepted with one schema's interpretation?
  - [ ] **Stablecoin base (changelog):** `{base_currency: "USDC", quote_currency: "USD", amount: 1000}` — Reference doesn't list this, changelog does. Honored?
  - [ ] Junk `account_type` → 4xx with allowed_values?
  - [ ] Quote TTL: capture and verify 10-min via probe-and-replay-after-11-min
- **Doc-sufficiency:** NO (the entire finding).
- **Sample notes:** **Most critical Phase-2 probe — its outcome rewrites Recipe B and possibly README #1.** Sequence Probe A first; if 200, the Guides are canonical and Finding #1 promotes to a runtime drift.

#### POST /v1/payins/fees
- **Batch:** E
- **Prerequisites:** auth
- **Sync/Async:** sync (10-min TTL fee_quote_id)
- **Documented schema:** body `{amount, base_currency, quote_currency, collection_method: SPEI|PSE, settlement_network}` → `{fee_quote_id, expires_at, breakdown}`.
- **Expected drift:** GAP-05 (Shape B envelope), settlement_network enum.
- **Probe checklist:**
  - [ ] Happy-path SPEI MXN→USDT TRON
  - [ ] PSE COP→USDC POLYGON
  - [ ] Unknown `collection_method` → 4xx
  - [ ] Stablecoin base (USDC→MXN) — does the payins/fees endpoint mirror the quotations stablecoin support?
- **Doc-sufficiency:** PARTIAL.

### Batch F

#### POST /v1/virtual-accounts/{id}/payout/preview (dry-run)
- **Batch:** F
- **Prerequisites:** va_id (active, fiat mode), recipient_id, optional quote_id
- **Sync/Async:** sync
- **Documented schema:** flow-design §3.7 — returns fee breakdown; `create_quote: true` reserves a 15-min quote.
- **Expected drift:** GAP-31 cascade (which quote_id from Batch E?), GAP-25 (settlement timing).
- **Probe checklist:**
  - [ ] Happy-path with quote_id from Batch E winning schema
  - [ ] Happy-path with `create_quote: true` (skip explicit quote)
  - [ ] Preview with insufficient balance — does preview 400 or silently return a payout that would 400 on commit?
  - [ ] All three modes: fiat→bank, crypto→bank, fiat→crypto
- **Doc-sufficiency:** PARTIAL.

#### POST /v1/virtual-accounts/{id}/payout (initiate)
- **Batch:** F
- **Prerequisites:** preview successful, idempotency-key, optional x-validation-header (OTP)
- **Sync/Async:** async (CREATED → PENDING → PROCESSING → COMPLETED)
- **Documented schema:** §3.7 — body `{amount, recipient_id, quote_id}`.
- **Expected drift:** GAP-19 (status casing), GAP-23 (OTP endpoint), GAP-28 (no cancel), GAP-05 (Shape B errors).
- **Probe checklist:**
  - [ ] Happy-path no OTP, idempotency-key fresh
  - [ ] With expired quote_id → 409 / 400?
  - [ ] With `x-validation-header: 000000` (junk OTP) → 401 with `attemptsRemaining`/`isBlocked`? (probes GAP-23)
  - [ ] Idempotency replay same body → cached response
  - [ ] Idempotency replay different amount → 409
  - [ ] Concurrent identical payout requests (race) — both succeed, one wins?
  - [ ] Insufficient balance → 400 or 422?
- **Doc-sufficiency:** PARTIAL (and GAP-23 unfixable from docs alone).

#### GET /v1/payouts/{payoutId}
- **Batch:** F
- **Prerequisites:** payout_id
- **Sync/Async:** sync (poll for state)
- **Documented schema:** §3.7 + `events[]` log.
- **Expected drift:** GAP-19 (case in status), `events[].provider_details` shape (undocumented schema), GAP-30 (no response example).
- **Probe checklist:** poll every 10s until COMPLETED or 5min timeout; capture every state transition.
- **Doc-sufficiency:** PARTIAL.

#### POST /v1/payins
- **Batch:** F
- **Prerequisites:** fee_quote_id from Batch E (or omit?), user_id
- **Sync/Async:** async (CREATED → COMPLETED via external payment)
- **Documented schema:** §3.8 — `type: PSE|SPEI`, `settlement.account.{address, network, token}`, fee_quote_id, idempotency-key.
- **Expected drift:** GAP-13 (state machine partial), GAP-24 (KYC required? probe with unverified user), GAP-25 (SLA), settlement[] array structure (SPEI reusable vs PSE single).
- **Probe checklist:**
  - [ ] Happy-path SPEI MXN → USDT TRON
  - [ ] Happy-path PSE COP → USDC POLYGON
  - [ ] With unverified user → 4xx (probes GAP-24)
  - [ ] Omit fee_quote_id — required or computed?
  - [ ] Idempotency replay
  - [ ] Stablecoin → fiat? (likely 4xx — "no fiat-to-fiat")
- **Doc-sufficiency:** PARTIAL.

#### GET /v1/payins/{payinId}
- **Batch:** F
- **Prerequisites:** payin_id
- **Sync/Async:** sync (poll)
- **Documented schema:** §3.8 — `settlement` array (multi for SPEI, single for PSE).
- **Expected drift:** GAP-19 case, status enum (CREATED/PENDING/PROCESSING/COMPLETED/FAILED/REFUNDED — confirm).
- **Probe checklist:** poll; capture transitions; verify settlement[] structure.
- **Doc-sufficiency:** PARTIAL.

#### POST /v1/payment-link
- **Batch:** F
- **Prerequisites:** user_id (verified? — UNDOCUMENTED)
- **Sync/Async:** sync
- **Documented schema:** §3.9 — recipient details, `acct_info`, optional `link_type: "top-up"`.
- **Expected drift:** redirect_url query string handling, two webhook events (`card_payment`, `barcode_generated`) emitted but no doc on link expiry, hosted-page CSP/iframe behavior (fullstack-integrations concern).
- **Probe checklist:**
  - [ ] Happy-path remittance flow
  - [ ] `link_type: "top-up"` variant
  - [ ] redirect_url with query string already → does Kira's `?status=success` collide?
  - [ ] omit `acct_info` → 4xx?
- **Doc-sufficiency:** PARTIAL.

#### POST /v1/virtual-accounts/{id}/liquidation-address
- **Batch:** F
- **Prerequisites:** va_id (active, US_BANK), user VERIFIED, idempotency-key
- **Sync/Async:** sync (then long-running sweeps)
- **Documented schema:** §3.10 — `network`, `token`, inline recipient block (NOT recipient_id — GAP-26).
- **Expected drift:** GAP-26 (recipient shape divergence — TS-interface killer), GAP-08 (idempotency added in Apr-14 changelog).
- **Probe checklist:**
  - [ ] Happy-path USDC on solana → ACH recipient inline
  - [ ] Try `recipient_id` reference instead of inline — 4xx?
  - [ ] USDT on solana (should reject per Apr-14 changelog — USDT only tron/polygon)
  - [ ] Idempotency replay variants
- **Doc-sufficiency:** PARTIAL.

#### GET /v1/virtual-accounts/{id}/liquidation-address
- **Batch:** F
- **Prerequisites:** liq created
- **Sync/Async:** sync
- **Documented schema:** §3.10 — cumulative stats.
- **Expected drift:** stats accuracy in sandbox.
- **Probe checklist:** happy-path read; verify `total_deposits=0` initially.
- **Doc-sufficiency:** PARTIAL.

### Batch G

#### POST /webhooks/register
- **Batch:** G
- **Prerequisites:** auth (x-api-key only — NO Bearer required per §3.11)
- **Sync/Async:** sync
- **Documented schema:** §3.11 — `{webhook_url, secret, client_uuid}`. Reference page has ZERO error codes (Finding #4).
- **Expected drift:** GAP-11 (delivery semantics absent), GAP-21 (no PUT/DELETE), Finding #4 (secret optional?), GAP-04 (auth mode confirmation — Bearer not required).
- **Probe checklist:**
  - [ ] Happy-path with valid HTTPS URL + 32-char secret + our client_uuid → 200
  - [ ] `secret: ""` → does it accept?
  - [ ] `secret: null` → does it accept?
  - [ ] Omit `secret` → does it accept?
  - [ ] Different `client_uuid` (cross-tenant probe) — defer the exploit to Phase 3
  - [ ] With Bearer header included anyway — accepted or 4xx?
  - [ ] Re-register same webhook_url → does it duplicate or upsert?
  - [ ] Use webhook.site URL for **passive capture** only (do not stand up receiver)
- **Doc-sufficiency:** NO (the entire Finding #4).
- **Sample notes:** Register a webhook.site URL toward end of Phase 2. Capture deliveries as raw evidence (`evidence/work/webhooks/*.json`) for Phase 3 forensics. **Do not build the receiver.**

---

## 5. Webhook Architecture Decision

### 5.1 Webhook event catalogue (from Kira docs)

Confirmed via flow-design §2.7 (canonical inventory). Docs **do** list events, but are silent on delivery semantics — confirming GAP-11.

| Event | Resource | Trigger | Polling alternative | Required or complementary? |
|---|---|---|---|---|
| `user.created` | User | POST /v1/users 201 | Caller already has it from create response | Complementary (redundant) |
| `user.verification.accepted` | User | KYC/KYB approved | `GET /v1/users/{id}` → status=VERIFIED | Complementary (poll viable) |
| `user.verification.failed` | User | KYC/KYB rejected | `GET /v1/users/{id}` → status=REJECTED | Complementary |
| `virtual_account.created` | VA | Row inserted (status=activating) | Caller already has it from create | Complementary |
| `virtual_account.activated` | VA | active + deposit instructions populated | `GET /v1/virtual-accounts/{id}` → status=active | Complementary |
| `virtual_account.deposit_funds_received` | Deposit | Inbound rail received | `GET /v1/virtual-accounts/{id}/deposits` | Complementary (poll cost: 1 call per N seconds × #VAs) |
| `virtual_account.deposit_funds_in_transit` | Deposit (crypto) | Stablecoin send initiated | `GET /v1/virtual-accounts/{id}/deposits/{depositId}` | Complementary |
| `virtual_account.deposit_funds_in_destination` | Deposit (crypto) | Stablecoin delivered | same | Complementary |
| `payout.created` / `.pending` / `.processing` / `.completed` / `.failed` / `.returned` | Payout | State transitions | `GET /v1/payouts/{id}` per state | Complementary (poll viable, ≤5 transitions per payout) |
| `payout.deposit_received` | Payout (crypto-mode) | Stablecoin received in escrow | `GET /v1/payouts/{id}` (custom field) | Complementary |
| `payin.created` / `.pending` / `.processing` / `.completed` / `.failed` / `.refunded` | PayIn | State transitions | `GET /v1/payins/{id}` | Complementary |
| `card_payment` | Payment Link | Card success | none (terminal state on link itself? — UNDOCUMENTED) | Possibly **required** |
| `barcode_generated` | Payment Link (cashPay) | Barcode emitted | none documented | Possibly **required** |
| `transaction_update` | Payout (legacy) | Generic | n/a | Legacy noise |

**Key empirical finding from this catalogue:** **No event is webhook-only** for the resources Phase 2 touches (users, VAs, deposits, payouts, payins). Every async state is queryable via a GET. The Payment Link `card_payment` event has no documented poll alternative, but Payment Link is in Batch F and likely not on the Phase-2 critical path for Recipe B/C.

→ The docs **do contain a webhook event catalogue** (contradicts a naive "docs are silent" read), but they do **not** contain delivery semantics (retry, signature encoding, replay, timestamps) — that's the GAP-11 surface.

### 5.2 Polling alternatives per async resource

| Async resource | Poll endpoint | Acceptable cost in sandbox? |
|---|---|---|
| User verification | `GET /v1/users/{id}` every 10s for ≤5min | Yes — sandbox auto-approves per docs (DRIFT-3 caveat) |
| VA activation | `GET /v1/virtual-accounts/{id}` every 5s for ≤2min | Yes |
| Deposit receipt | `GET /v1/virtual-accounts/{id}/deposits` every 10s | Yes (but GAP-22: deposit simulation undocumented) |
| Payout completion | `GET /v1/payouts/{id}` every 10s for ≤5min | Yes — settlement timelines docs §3.7 |
| PayIn completion | `GET /v1/payins/{id}` every 10s | Yes |

Rate-limit headroom: 10 rps allowance, our polling pattern peaks at ~0.2 rps. Well under budget.

### 5.3 Decision matrix

| Async resource | Webhook required? | Polling viable? | Decision |
|---|---|---|---|
| User verification | No | Yes (auto-approves in sandbox) | **Poll** |
| VA activation | No | Yes | **Poll** |
| Deposit | No | Yes (if GAP-22 resolves) | **Poll** |
| Payout settlement | No | Yes | **Poll** |
| PayIn settlement | No | Yes | **Poll** |
| Payment Link card_payment | Possibly | Unknown poll-equivalent | **Defer to Batch F probe** — capture passively via webhook.site if needed |

### 5.4 BINARY DECISION

**Should we stand up the FastAPI webhook receiver in Phase 2?** **NO.**

Rationale:
- Every Phase-2 async resource has a working polling alternative within rate-limit budget; no event is webhook-only on our critical path.
- GAP-11 (signature encoding, retry, replay protection all unspecified) means building a receiver in Phase 2 would force us to **guess** the verification contract — that work belongs in **Phase 3 as an adversarial probe**, not in Phase 2 as plumbing.
- Sandbox webhook delivery reliability is itself untested. Standing up a receiver and not getting deliveries would block Batches D/F unnecessarily; polling can't be silently broken the same way.
- Finding #4 (CRITICAL) gets stronger empirical support by treating the receiver as an *adversarial harness* — register variants of `secret`, capture what arrives via passive `webhook.site`, then in Phase 3 stand up FastAPI with explicit experiments (signature decode hex vs base64, timestamp probes, replay).

**Phase 2 webhook plan (without a receiver):**
1. In Batch G, register **one** webhook against a `webhook.site` URL with a known secret.
2. Trigger the Recipe-B happy path in Batch F. Capture every delivery raw to `evidence/work/webhooks/{NN}-{event}.raw`.
3. Pass the raw captures to Phase 3 for signature reverse-engineering and the `secret: ""/null/omit` experiments.

**Phase 3 webhook plan (with FastAPI receiver):**
- ngrok-exposed FastAPI app, signature verification toggle (try hex, try base64, try `sha256=` prefix), idempotent processing via `event_id`, structured evidence logging. Hardens Finding #4 from "docs gap" to "exploitable spoofability" if `secret: ""` accepts.

---

## 6. Probe-Mutation Matrix

Symbols: ✓ apply | — N/A | ? doc unclear (resolve empirically)

| Mutation | Auth | Users | Recipients | VAs | Quotations | PayIns | Payouts | PayLink | LiqAddr | Webhooks | RefData |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Omit `x-api-key` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Junk `x-api-key` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Omit Authorization Bearer | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (allowed) | ? (GAP-04) |
| Stale Bearer (>1hr) | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Bearer-only (no x-api-key) | — | ? | ? | ? (GAP-04) | ? | ? | ? | ? | ? | — | ? (GAP-04) |
| `X-Api-Version` omit | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `X-Api-Version: 2025-01-01` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `X-Api-Version: garbage` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Idempotency replay (same body) | — | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | ? | — |
| Idempotency replay (diff body) | — | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | ? | — |
| Idempotency omit | — | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | — | — |
| ISO 3166 alpha-2 / alpha-3 swap | — | ✓ (DRIFT-5 done) | ✓ | ✓ | ? | — | ? | ? | — | — | ✓ (GAP-32 dimension) |
| Concurrent dupes (race) | — | ? | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | ? | — |
| Unknown enum value | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Cross-tenant resource ID | — | ✓ (defer P3) | ✓ (defer P3) | ✓ (defer P3) | — | ✓ (defer P3) | ✓ (defer P3) | — | — | ✓ (defer P3) | — |
| Illegal state transition | — | ✓ (PUT verified) | — | ? (close VA) | ✓ (expired quote) | — | ? (cancel) | — | — | — | — |
| `secret: ""` / null / omit | — | — | — | — | — | — | — | — | — | ✓ (Finding #4) | — |

---

## 7. Phase 2 → Phase 3 Handoff

| Endpoint | Functional abuse cleared? | Security audit cleared? | Stress/load cleared? | Blockers |
|---|---|---|---|---|
| POST /auth | yes | yes (Phase 3 JWT/replay still pending) | yes | — |
| POST /v1/users | yes | partial (BOLA pending) | partial (KYB doc upload sizing) | KYB doc base64 → payload sizing for stress |
| GET /v1/users | yes | partial | yes | — |
| GET /v1/users/{id} | yes | **BOLA priority** | yes | — |
| PUT /v1/users/{id} | yes | partial (mass-assignment priority) | yes | — |
| POST /v1/users/{id}/verifications | partial (legacy path probes) | yes | n/a | sandbox auto-approve verify caveat |
| POST /v1/users/{id}/wallets | depends on GAP-37 outcome | depends | depends | GAP-37 resolution |
| POST /v1/recipients | yes | yes (BOLA priority) | yes | — |
| GET /v1/recipients/{id} | yes | BOLA priority | yes | — |
| POST /v1/virtual-accounts | yes | yes (mass-assignment on markup) | partial | GAP-22 sandbox deposit |
| GET /v1/virtual-accounts/{id} | yes | BOLA priority | yes | — |
| GET /v1/virtual-accounts/{id}/balance | yes | BOLA | yes | — |
| GET /v1/virtual-accounts/{id}/deposits | yes | BOLA | yes | — |
| POST /v1/quotations | **BLOCKED on GAP-31 disambiguation** | partial | partial | GAP-31 |
| POST /v1/payins/fees | yes | yes | yes | — |
| POST /v1/payins | yes | yes | yes | GAP-24 KYC requirement |
| GET /v1/payins/{id} | yes | BOLA | yes | — |
| POST /v1/virtual-accounts/{id}/payout/preview | yes | yes | yes | — |
| POST /v1/virtual-accounts/{id}/payout | yes (abuse priority: race, refund-after) | yes (OTP bypass priority) | yes | GAP-23 (OTP endpoint hidden) |
| GET /v1/payouts | yes | partial | yes | — |
| GET /v1/payouts/{id} | yes | BOLA | yes | — |
| POST /v1/payment-link | partial | yes (open-redirect priority) | yes | hosted-page probes (fullstack-integrations owns) |
| POST /v1/virtual-accounts/{id}/liquidation-address | yes | yes (recipient swap) | yes | — |
| POST /webhooks/register | yes (spoof priority) | **TOP PRIORITY** (Finding #4) | yes | GAP-11 |

---

## 8. Open Architectural Questions (for @Nicolle / @Diego)

1. **DRIFT-3 escalation — what payload actually triggers KYB?** The §3.2.1 minimal business body returns 201 with `verification_triggered: false`. The published `missing_fields` block lists 13 + 8 fields across the two USA-VA products. Is there a documented "minimum-to-trigger-verification" payload, or is "submit everything in `missing_fields` then PUT" the intended flow? (Cascades into Batch D blocking risk.)
2. **GAP-22 — sandbox deposit simulation endpoint.** Without an endpoint to credit a sandbox VA, Batches D/E/F partially block on the money-movement chain. Is there an undocumented `POST /sandbox/simulate-deposit` or equivalent? If not, how do we evaluate the deposit/payout chain in PM-exercise scope?
3. **GAP-31 — Quotations canonical schema.** Reference and Guides describe disjoint bodies. Which is the runtime contract? (Batch E first probe will answer empirically; recording the question for the upstream fix.)
4. **GAP-37 — Wallets surface.** Does `POST /v1/users/{id}/wallets` exist at runtime, and if so, what's its body schema? Are there sibling endpoints (`GET /v1/wallets`, etc.) we should be testing?
5. **GAP-23 — OTP endpoint.** `POST /verification/send` is named in the payouts guide but has no Reference page. Path, body, rate-limit?
6. **Undocumented `x-client-id` request header.** Surfaced on the gateway-rejected `/sandbox/v1/users` `Access-Control-Allow-Headers`. Any endpoint actually consume this? (Possible cross-tenant scoping primitive — high security relevance.)
7. **GAP-24 — KYC required for PayIns?** Can a SPEI PayIn (collection only) be created without a verified user? Affects PayIn flow ordering in Batch F.

---

**End of plan.** Next `/proc_comment "execute next Phase 2 batch"` should dispatch agents starting with **Batch A** (foundations & reference data). Batch E first-probe (Quotations GAP-31 disambiguation) is the **highest-priority single call** in Phase 2 once a recipient_id is available from Batch C — consider hoisting Batch E ahead of Batch C if a recipient_id can be synthesized or skipped (Probe A in Batch E uses the Guides schema with NO recipient_id).
