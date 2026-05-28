# Abuse Scenarios — Phase 3 Partial (Functional Track)

**Run date:** 2026-05-27 (UTC ~02:21 – 02:27 the next morning per `captured_at`)
**Scope:** 18 endpoints validated in Phase 2 (`integration-log.md` master)
**Tester agent:** `api-functional-tester`
**Persona file:** `.claude/agents/api-functional-tester.md`
**Coordination:** parallel with `api-security-auditor` (OWASP) and `qa-engineer` (stress).
`run_flow.py` and `_redact.py` not modified — abuse harnesses import only.

---

## Summary

| # | Scenario | Severity | Category | Status |
|---|---|---|---|---|
| 1 | `delete-recipient-pollution` | **HIGH** | tenant-abuse / state-machine | Reproduced — DRIFT-C15 firing 20/20 |
| 2 | `idempotency-replay-race` | LOW (positive) | concurrency | Idempotency is RACE-SAFE on `/v1/recipients` (good — contrast with DRIFT-G4 on webhooks) |
| 3 | `bola-cross-tenant-stub` | LOW | tenant-abuse | No leak — random UUID enumeration returns 404 consistently |
| 4 | `silent-country-override-exploit` | **HIGH** | currency-exploit / compliance | DRIFT-C14 reproduced + **NEW: ACH USD route accepts `address.country=MX` with US routing number** |
| 5 | `webhook-spoof-no-event-filter` | **CRITICAL** | tenant-abuse / webhook-spoof | **3/3 bogus `client_uuid` values accepted** — cross-tenant webhook hijack vector |
| 6 | `verification-skip-attempt` | **HIGH** | state-machine / dependency-skip | Verification check works for MX_SPEI (great!) but **4th error envelope shape discovered**, and **layer ordering inconsistent** (schema-first for US_BANK, verification-first for MX_SPEI) |

**6 of 6 scenarios attempted. 1 CRITICAL, 3 HIGH, 1 LOW, 1 LOW-positive.**

---

## Scenario 1 — delete-recipient-pollution

**Category:** tenant-abuse / state-machine
**Impact:** Trust hit + operational ($) — attacker pollutes recipient list and operator must escalate to Kira support for manual cleanup.

**Setup:** Use existing tenant API key + bearer; target user `65ba0e06-…` (CREATED state, already had 6 recipients from Batch C).

**Attempt:**
1. POST 20 distinct SPEI recipients via `POST /v1/recipients`.
2. Immediately DELETE each created recipient via `DELETE /v1/recipients/{id}`.
3. List `GET /v1/recipients?user_id=…` and inspect.
4. Probe pagination boundary: `?limit=100`, `?limit=1000`, `?limit=100000`, `?offset=9999`, `?limit=-1`, `?limit=0`.

**Expected:** DELETE returns 405 with `Allow:` header OR 200 + cleanup; pagination params either honored or rejected with 400.

**Observed:**
- 20/20 POST → 201 (creates succeeded — no rate limit, no quota).
- 20/20 DELETE → **403 with AWS SigV4 leaked error** (DRIFT-C15 firing every single time — `"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '<REDACTED>='."`). No `Allow` header. **The recipient list grew to 26 total (the 6 prior + 20 new), and no DELETE removed any of them.**
- GET list → 200 with all 26 recipients returned in a single response. `{recipients:[…], total:26}` envelope (DRIFT-C9 holds).
- **NEW FINDING — pagination params are SILENTLY IGNORED on `/v1/recipients` list:**
  - `?limit=100` → 26 records (the entire list)
  - `?limit=1000` → 26 records
  - `?limit=100000` → **200 with 26 records** (NOT 500 like `/v1/users` and `/v1/virtual-accounts` per DRIFT-10 — `/v1/recipients` doesn't blow up but also doesn't respect the param at all)
  - `?limit=-1` → 200, 26 records
  - `?limit=0` → 200, 26 records
  - `?offset=9999` → 200, 26 records

  **This is a divergence between two list endpoints on the same API:**
  - `/v1/users?limit=100000` → 500 server error (DRIFT-10)
  - `/v1/recipients?limit=100000` → 200, param ignored
  - Two list endpoints, two different handling of out-of-range pagination on the same API.

- **Cumulative finding:** an attacker with API-key access who creates N recipients permanently pollutes the tenant's recipient inventory. Cleanup requires manual Kira-support intervention because:
  1. No DELETE endpoint at runtime (DRIFT-C15 = 403 every time).
  2. No PATCH or "archive" endpoint observed.
  3. No way to hide / mark-deleted from the tenant side.
  4. List endpoint returns ALL recipients including the polluted ones, with no pagination control.

**Severity:** HIGH (operational + DX + integrator trust). The "20 polluted recipients" is a finding-by-itself; the real risk is **an attacker who creates 10,000 recipients makes the tenant's UI un-renderable** until manual cleanup ships.

**Repeatable:** 20/20 DELETE returned 403. 20/20 POST succeeded. List confirmed all 26 visible.

**Evidence:** `evidence/work/abuse/delete-recipient-pollution/`
- `01-create-00..19.json` (20 successful creates)
- `02-delete-00..19.json` (20 failed deletes — all 403, all with AWS SigV4 leak)
- `03-list-default.json` (final state: 26 recipients visible)
- `04-list-limit-*.json` (pagination param probes)
- `_summary.json` (machine-readable)

**Cleanup state:** Sandbox left with 26 recipients on `65ba0e06-…`. **Cleanup is empirically impossible** — proving the finding.

---

## Scenario 2 — idempotency-replay-race

**Category:** concurrency
**Impact:** Trust hit (if duplicates are billable) — but happily, the API is well-behaved here.

**Setup:** Single token, single user, four probes on `POST /v1/recipients`.

**Attempt:**
- **Probe A:** 10 PARALLEL POST with SAME `idempotency-key` + SAME body — expected: 1 unique recipient_id.
- **Probe B:** 10 PARALLEL POST with DIFFERENT keys + SAME body — expected: 10 distinct recipient_ids.
- **Probe C:** 10 PARALLEL POST with SAME key + MUTATED body (each worker uses a unique `last_name`) — expected: 1 winner (201), 9 conflicts (409 IDEMPOTENCY_CONFLICT).
- **Probe D:** 2 PARALLEL POST with same key + same body, at synchronized wall-clock T0 — expected: same `recipient_id` both calls.

**Expected:** Stripe-pattern idempotency: cached response on same key+body; conflict 409 on same key+different body; no race window where two creates slip through.

**Observed:**
- Probe A → **1 unique recipient_id** across all 10 workers. All 10 returned 201. Idempotency holds under N=10 parallelism. ✓
- Probe B → **10 distinct recipient_ids** across all 10 workers. All 10 returned 201. Body is correctly NOT a fallback discriminator. ✓
- Probe C → **1 worker won (201), 9 workers got 409 IDEMPOTENCY_CONFLICT**. The first request-to-arrive owns the key; the others see a conflict. No "split brain" — exactly 1 creation. ✓
- Probe D → **2 workers, same recipient_id, both 201.** Clean. ✓

**Severity:** **LOW-POSITIVE** — this is a control that came back clean. Combined with DRIFT-G4 (webhooks DOES ignore Idempotency-Key), it sharpens the finding: **idempotency works on `/v1/recipients` but is broken on `/webhooks/register`** — the API is inconsistent in which endpoints respect the contract.

**Repeatable:** 10/10 on each of probes A/B/C/D.

**Evidence:** `evidence/work/abuse/idempotency-replay-race/`
- `A-same-key-same-body-w00..09.json` (10 workers)
- `B-diff-keys-same-body-w00..09.json` (10)
- `C-same-key-mut-body-w00..09.json` (10)
- `D-pair-race-w00..01.json` (2)
- `_summary.json` (status_counts + unique_ids per probe)

---

## Scenario 3 — bola-cross-tenant-stub

**Category:** tenant-abuse (BOLA preview)
**Impact:** would be CRITICAL if any cross-tenant data leaked; we found none in the stub probe.

**Setup:** Take known UUIDs (our user, random UUID-v4) and try various GET / POST mutations that should fail at the ownership/existence layer.

**Attempt:**
- **Probe 1:** mutate one hex char of our user UUID at 7 positions; `GET /v1/users/<mutated>` × 7.
- **Probe 2:** generate 5 random UUID-v4 strings; `GET /v1/recipients/<random>` × 5.
- **Probe 3:** generate 5 random UUID-v4 strings; `GET /v1/users/<random>` × 5.
- **Probe 4:** generate 3 random UUID-v4 strings; `GET /v1/virtual-accounts/<random>` × 3.
- **Probe 5:** `POST /v1/payouts` with our `user_id` and a random `recipient_id`. Expected: 400 "recipient not found" OR schema error.
- **Probe 6:** `POST /v1/virtual-accounts` with random `user_id`. Same.

**Expected:** All GETs → 404. POSTs → 400 or 403. No leakage of other tenants' data.

**Observed:**
- All 7 mutated-user-id GETs → 404.
- All 5 random recipient GETs → 404.
- All 5 random user GETs → 404.
- All 3 random VA GETs → 404.
- Probe 5 (`POST /v1/payouts`) → 400 at the SCHEMA layer: missing `network`, `txHash`, `quote_id`. **Ownership check is gated by schema** — an attacker can't reach the "does recipient belong to user?" check without supplying a full valid payout request. (Not a leak.)
- Probe 6 (`POST /v1/virtual-accounts` with random user_id) → 400 at schema layer: `type is Required`. Same gating.
- Sanity: `GET /v1/users/<our-user>` → 200. ✓

**Severity:** **LOW** (negative result) — no BOLA leak observed via random ID guessing in this stub. **But this is NOT a clean bill of health** — a full BOLA test requires a second tenant API key, which we don't have. The schema layer gating Probe 5/6 means we can't tell whether ownership-of-recipient or ownership-of-user is actually enforced once the request is valid. Recommend **Phase-3 deeper probe with a second tenant** before declaring BOLA absent.

**Repeatable:** 23/23 GETs returned 404; 2/2 POSTs returned 400 at schema layer.

**Evidence:** `evidence/work/abuse/bola-cross-tenant-stub/`
- `01-mutated-user-pos*.json` (7 mutated-byte UUID probes)
- `02-random-recipient-*.json`, `03-random-user-*.json`, `04-random-va-*.json` (random UUID GETs)
- `05-payout-fake-recipient.json`, `06-va-fake-user.json` (cross-resource POSTs)
- `07-sanity-own-user.json`
- `_summary.json`

---

## Scenario 4 — silent-country-override-exploit

**Category:** currency-exploit / compliance / state-machine
**Impact:** Compliance / regulatory — silent data correction means integrator reconciliation reports diverge from Kira's. AML/KYC implications.

**Setup:** Create recipients with deliberately mismatched country/account info across SPEI / ACH / WALLET variants.

**Attempt:**
- **P1:** SPEI body + `account.country: "USA"` + valid MX CLABE → does country override to MX?
- **P2 (control):** SPEI body + `account.country: "MX"` + valid MX CLABE → confirm baseline.
- **P3:** SPEI body + `account.country: "COL"` + valid MX CLABE → what wins?
- **P4:** ACH USD body + valid US routing number `011000015` + address `{country: "MX"}` + `account.doc_country_code: "MX"` + `account.country: "MX"` — does the API enforce address-vs-routing-number consistency?
- **P5:** WALLET (TRON) body + `account.country: "USA"` — does wallet preserve the requested country?

**Expected:** P1 should be rejected as "country mismatch with CLABE bank prefix" OR explicitly normalized with a warning. P4 should reject because US ABA routing implies US address. P5 should either accept country or strip it consistently.

**Observed:**
- **P1: DRIFT-C14 reproduced exactly.** SPEI POST with `country: "USA"` → 201, response `account_details.doc_country_code: "MX"`. GET-detail of the same recipient → also `"MX"`. Persisted state is MX. The integrator's submitted `"USA"` is silently dropped. **Reproducible.**
- **P2 (control):** As expected → `"MX"`.
- **P3:** SPEI POST with `country: "COL"` → 201, response `doc_country_code: "MX"`. **CLABE prefix wins universally** — Colombia silently downgraded too. Pattern confirmed: any country sent with a SPEI body is silently overridden to MX.
- **P4: NEW HIGH-SEVERITY FINDING.** ACH USD body with US routing `011000015` (a well-known publicly-documented test ABA) was accepted **with `address.country = "MX"`** echoed back unchanged in the response. **No validation that ACH routing-number country matches address country.** A Mexico-addressed recipient with a US bank routing number is now stored as-is — this looks like a real compliance/AML hole:
  - Treasury OFAC reporting expects the beneficiary address to be coherent with the rail.
  - An attacker (or careless integrator) can register MX-addressed recipients with US ACH routings and route money out of a US virtual account "to Mexico" while the underlying bank is US.
- **P5:** WALLET TRON body with `country: "USA"` → 201, response strips country entirely (no `account_details.country` field in response). Silent strip — third behaviour pattern (override on SPEI, accept on ACH, strip on WALLET).

**Summary of country-handling inconsistency across recipient variants:**

| Variant | Request `account.country` | Response `account_details.country` | Behavior |
|---|---|---|---|
| SPEI | `USA`/`MX`/`COL` (any) | always `"MX"` | **Silent override** (derived from CLABE) |
| ACH USD | `MX` (mismatched vs routing-number country) | absent | Stored in `address.country` only, no cross-check against routing-number country |
| WALLET TRON | `USA` | absent | **Silent strip** (no country preserved) |

**Severity:** **HIGH** — three different country-handling behaviours on the same endpoint, all undocumented. The ACH compliance angle is the most concerning (real AML implications).

**Repeatable:** 5/5 probes returned the expected anomalous outcome.

**Evidence:** `evidence/work/abuse/silent-country-override-exploit/`
- `01-P1-spei-country-USA-create.json` + `…-get.json`
- `02-P2-spei-country-MX.json` (control)
- `03-P3-spei-country-COL.json`
- `04-P4-ach-country-MX.json` (the new HIGH finding — US ABA + MX address accepted)
- `05-P5-wallet-country-USA.json` (silent strip)
- `_summary.json`

---

## Scenario 5 — webhook-spoof-no-event-filter

**Category:** tenant-abuse / webhook-spoof
**Impact:** **CRITICAL** — full cross-tenant webhook hijack (data exfiltration, fraud-trigger vector).

**Setup:** Call `POST /webhooks/register` with various `client_uuid` values: our own, random UUIDs (not our tenant), and absent.

**Attempt:**
- **P1 (baseline):** register with our `client_uuid` (from `.env`). Expected: 200.
- **P2:** register with 3 random UUIDs (NOT our tenant's `client_uuid`). Expected: 400 / 403 with "client_uuid does not match auth context" or similar.
- **P3:** register WITHOUT `client_uuid` field. Expected: 400 / fallback to auth context.
- **P4:** register with our `client_uuid` but different `webhook_url` twice. Expected: 200 + last-write-wins (or 200 + accumulate — both possible).
- **P5:** register with an `events: [...]` filter field — the doc-published catalogue. Expected: 200 (silent strip) OR 400 (unknown field).
- **Cleanup:** register our benign URL again to restore the baseline.

**Expected:** Bogus `client_uuid` should be rejected (401 / 403 cross-tenant). Or at minimum, the request should be confined to our tenant.

**Observed:**
- P1 → 200. ✓
- **P2 → 3/3 BOGUS `client_uuid` ACCEPTED WITH 200** (`{"message":"Webhook registered successfully"}`). **No validation that `client_uuid` matches the authenticated tenant.** Each bogus UUID we sent (random UUIDs, NOT belonging to any known tenant) returned 200. ❌
- P3 → 400 `{loc: client_uuid, msg: Field required}`. The field is required, but the value is never cross-checked against the auth context.
- P4 → both 200. Per DRIFT-G5, no id is returned, so we can't tell if it's last-write or accumulate. (Confirmed open question from Batch G.)
- P5 → 200 with `events` field silently stripped (DRIFT-G* extension; no `events` filter exists at runtime).
- Cleanup → 200.

**The CRITICAL implication:** If `client_uuid` is the partition key for fan-out (per Kira's hypothesis in DRIFT-G), then **an attacker who knows or guesses another tenant's `client_uuid` can register a webhook URL of their choosing to receive that tenant's events.** Even if the OWN tenant's events also still fire, the attacker now siphons the victim tenant's events as a copy.

**To be 100% confirmed** in Phase 3: trigger an event from a separate-tenant account (out-of-scope today) and check whether the attacker-registered webhook fires. The registration-time acceptance is already a CRITICAL pre-exploit posture finding.

**Severity:** **CRITICAL.** This combines with the SSRF finding (DRIFT-G1 — `webhook_url` accepts internal/loopback URLs) and the secret-optional finding (DRIFT-G2) to make the webhook subsystem a triple-vector:
1. Send Kira to internal IPs (SSRF).
2. Pull another tenant's events to attacker URL (cross-tenant spoof, NEW).
3. Drop signature verification (secret optional).

**Repeatable:** 3/3 bogus client_uuid POSTs returned 200. The cleanup overwrite restored the baseline URL for our own tenant.

**Evidence:** `evidence/work/abuse/webhook-spoof-no-event-filter/`
- `01-P1-baseline-own-client_uuid.json` (200)
- `02-P2-bogus-client_uuid-{00,01,02}.json` (3 × 200 — the CRITICAL finding)
- `03-P3-omit-client_uuid.json` (400)
- `04-P4-overwrite-1.json`, `05-P4-overwrite-2.json` (both 200)
- `06-P5-with-events-field.json` (200, events stripped)
- `07-cleanup-restore-baseline.json` (200)
- `_summary.json`

**Coordination with `api-security-auditor`:** this is OWASP API3:2023 (Broken Object Property Level Authorization / BOPLA) and a cross-tenant data-leak vector. Recommend pairing on the writeup.

---

## Scenario 6 — verification-skip-attempt

**Category:** state-machine / dependency-skip
**Impact:** State-machine integrity. If REVIEW users could create VAs / payouts, that's CRITICAL. We confirmed they cannot — but found 3 collateral findings.

**Setup:** 3 users in distinct states (CREATED, REVIEW-individual, REVIEW-business). Try to create VAs, payouts, and quotations as each.

**Attempt iter1:** Minimal POST bodies for each endpoint to see error shapes. Schema layer blocked all 9 attempts before reaching the verification check.

**Attempt iter2:** Build complete-enough bodies to push past the schema layer.
- VA `type: "US_BANK"` → schema layer needs `bank` field → 400 (still schema-gated)
- VA `type: "MX_SPEI"` → **schema passes, hits verification layer → 400 with EXPLICIT message** ✓

**Expected:** 400 with a clear "user not verified" envelope; consistent envelope across endpoints; no bypass.

**Observed:**
- **No bypass.** All probes returned 4xx; no resource created.
- **CRITICAL POSITIVE: verification check WORKS** for MX_SPEI VAs.
  Sample: `{"statusCode":400,"error":"Bad Request","message":"User must be in VERIFIED status to create a virtual account. Current status: REVIEW","timestamp":"2026-05-28T02:27:13Z"}`
- **NEW FINDING: 4th distinct error-envelope shape on the API.** This `{statusCode, error, message, timestamp}` is **not** any of:
  - Shape A: `{error:"<str>", details:[…]}` (e.g., `/v1/recipients` 400)
  - Shape B: `{error:{code, message, details}}` (e.g., `/v1/recipients` 409)
  - Shape C: `{code, error:"<str>", details:[…]}` (e.g., `/v1/virtual-accounts` schema-layer error)
  - Shape D (NEW): `{statusCode, error:"<str>", message, timestamp}` — Nest-style "filter" envelope, distinct from all three others.

  → **4 distinct error envelopes on the same API.** GAP-05 / DRIFT-12 escalated.

- **NEW FINDING: layer-ordering inconsistency.** For `POST /v1/virtual-accounts`:
  - `type: "US_BANK"` → schema layer fires first (`"bank is required"`)
  - `type: "MX_SPEI"` → verification layer fires first (`"User must be in VERIFIED status"`)

  The order of validation checks **depends on the `type` discriminator value**. This means:
  - An attacker probing whether their user is verified can use the MX_SPEI discriminator to get an info-disclosure of the user's status.
  - An attacker probing schema requirements first can use US_BANK to reverse-engineer required fields without leaking state.

- **State info-disclosure.** The error message echoes the user's current `status` field (`"Current status: REVIEW"` and `"Current status: CREATED"`). An attacker with API-key access can use this to enumerate the verification state of any user they know the UUID of — without GET access. Useful reconnaissance.

**Severity:** **HIGH** — state-machine integrity holds (positive), but the API leaks state via the error message, has an inconsistent ordering of validation layers, and introduces a 4th error envelope shape.

**Repeatable:** 3/3 MX_SPEI VA creates returned the explicit verification-failed envelope. 3/3 US_BANK returned the schema-layer envelope. 3/3 payouts returned the payouts-schema envelope.

**Evidence:** `evidence/work/abuse/verification-skip-attempt/`
- `01-P1-va-create-{CREATED,REVIEW-individual,REVIEW-business}.json` (3 × schema-layer 400)
- `02-P2-payout-*.json` (3 × payouts-schema 400)
- `03-P3-quote-*.json` (3 × quotations-schema 400)
- `11-iter2-P1-va-US_BANK-*.json` (3 × US_BANK schema 400)
- `12-iter2-P1b-va-MX_SPEI-*.json` (**3 × verification-layer 400 — the key finding**)
- `run.py`, `run_iter2.py`
- `_summary.json` (per_probe_status_matrix + iter2_findings)

---

## Scenarios that came back negative (controls)

- **BOLA via random UUID enumeration** (Scenario 3): 23/23 random UUID GETs returned 404. Cross-resource POSTs (referencing another tenant's recipient/user) blocked at schema layer — couldn't probe the ownership check directly without a complete request. **Not declared clean** because schema gating obscures the check; recommend Phase-3 dual-tenant probe.
- **Idempotency replay race on `/v1/recipients`** (Scenario 2): Stripe-pattern idempotency works correctly even at N=10 parallel. Bonus finding: the API is GOOD on this endpoint, in contrast with DRIFT-G4 (webhooks ignores Idempotency-Key entirely).
- **Verification bypass attempt** (Scenario 6): the verification check fires on the canonical MX_SPEI VA-create path. State-machine integrity confirmed for that branch.

---

## New abuse findings (separate from already-documented DRIFTs)

These were **discovered for the first time** in this Phase-3 partial run and are not in `integration-log.md`:

1. **ABUSE-1 (HIGH):** `/v1/recipients` pagination params are silently ignored — `?limit=100000`, `?limit=-1`, `?limit=0`, `?offset=9999` all return the full list. Inconsistent with `/v1/users` and `/v1/virtual-accounts` where `?limit=100000` returns 500 (DRIFT-10). Scenario 1.

2. **ABUSE-2 (HIGH — compliance):** ACH USD recipient creation accepts `address.country = "MX"` together with a US Federal Reserve routing number. No cross-check between routing-number-implied-country and recipient address country. AML/OFAC implications. Scenario 4 / P4.

3. **ABUSE-3 (different from DRIFT-C14):** WALLET (TRON) recipients silently STRIP the requested `account.country` (vs SPEI which silently OVERRIDES, vs ACH which silently ACCEPTS even when mismatched). Three different country-handling behaviours on the same endpoint. Scenario 4 / P5.

4. **ABUSE-4 (CRITICAL):** `POST /webhooks/register` accepts arbitrary `client_uuid` values, including random UUIDs that don't belong to the authenticated tenant. **3/3 bogus values returned 200 "Webhook registered successfully".** Cross-tenant webhook hijack vector. (This is the cross-tenant escalation of DRIFT-G1/DRIFT-G5.) Scenario 5.

5. **ABUSE-5 (HIGH):** 4th distinct error-envelope shape on the API: `{statusCode, error, message, timestamp}` — Nest-style — emitted by `POST /v1/virtual-accounts` when the verification-state check fires. Not any of the three envelopes already catalogued in GAP-05 / DRIFT-12 / DRIFT-6. Scenario 6.

6. **ABUSE-6 (MEDIUM):** Validation-layer ordering on `POST /v1/virtual-accounts` depends on `type` discriminator. `US_BANK` → schema layer first; `MX_SPEI` → verification layer first. An attacker can choose which check to probe by manipulating the discriminator. Scenario 6.

7. **ABUSE-7 (MEDIUM — info-disclosure):** Verification-layer error message echoes the user's current status (`"Current status: REVIEW"` / `"Current status: CREATED"`). Attacker with API-key access enumerates user verification states without GET access. Scenario 6.

8. **ABUSE-8 (LOW-POSITIVE — control):** Idempotency works correctly on `POST /v1/recipients` under N=10 parallel — contrast with DRIFT-G4 which showed it ignored on `/webhooks/register`. The API is inconsistent on this contract across endpoints. Scenario 2.

---

## Cross-tenant probe outcome (Scenario 3)

**No data leak observed from sequential / random UUID enumeration.** 23/23 GET probes on mutated user UUIDs, random recipient UUIDs, random user UUIDs, and random VA UUIDs returned 404. Cross-resource POSTs (referencing fake recipient_id or fake user_id) were blocked at the schema layer before reaching the ownership check — so the ownership check itself was NOT empirically tested. **Not declared clean.** Recommend Phase-3 dual-tenant probe.

## Webhook spoof outcome (Scenario 5)

**CONFIRMED: cross-tenant webhook registration succeeds.** Kira accepts `client_uuid` values that do not belong to the authenticated tenant. 3/3 bogus UUIDs returned 200. This is a CRITICAL pre-exploit posture finding. Full exploit confirmation requires triggering an event under the victim's tenant and observing whether the attacker-registered URL fires — Phase-3 work, out of scope today.

## State-machine bypass outcome (Scenario 6)

**No bypass.** REVIEW and CREATED users cannot create virtual accounts. Confirmed for the MX_SPEI path with the explicit error envelope `"User must be in VERIFIED status to create a virtual account. Current status: REVIEW"`. The US_BANK path was schema-gated before reaching the verification check. Payouts and quotations were also schema-gated and didn't reveal the verification check directly. The state machine is enforced — but the layer ordering is inconsistent (Scenario 6 / ABUSE-6) and a new error envelope shape was discovered (ABUSE-5).

---

## Recommended for Phase 3 deeper probe (out-of-scope today)

1. **Full BOLA with a second tenant** — register a second tenant API key and attempt cross-tenant reads. Without this, Scenario 3 is a stub.
2. **Cross-tenant webhook spoof — full exploit confirmation.** Trigger an event under a second-tenant API key and observe whether the bogus-`client_uuid` registration we made fires. If yes → confirmed cross-tenant data exfil.
3. **SSRF outbound confirmation.** Per Batch G recommendation; depends on a webhook receiver and a registration pointing at internal IPs.
4. **Pollute the recipient list to 1,000+ entries** and confirm whether any limit or paging behaviour breaks at scale (out-of-scope today; capped at 20 per persona instructions).
5. **Idempotency window TTL** — DRIFT-C deferred. Test whether expired keys allow re-use, and whether the TTL is documented.
6. **Concurrent verification trigger race** — two parallel `POST /v1/users/{id}/verifications` with same key. Does AiPrise get double-charged?
7. **Negative-amount and zero-amount payouts** — couldn't reach this layer today because of schema gating on `network`/`quote_id`. With a real quote_id, probe boundary amounts.
8. **CLABE-prefix-vs-bank-code collision** — submit SPEI with a CLABE that doesn't match any documented MX bank prefix; does the API accept or reject? (Related to ABUSE-2.)

---

## Files created

```
evidence/work/abuse/_abuse_common.py                                     ← shared HTTP plumbing
evidence/work/abuse/delete-recipient-pollution/run.py                    ← scenario 1
evidence/work/abuse/delete-recipient-pollution/{01..04,_summary}.json    ← 45 evidence files
evidence/work/abuse/idempotency-replay-race/run.py                       ← scenario 2
evidence/work/abuse/idempotency-replay-race/{A,B,C,D}-*.json             ← 32 evidence files
evidence/work/abuse/idempotency-replay-race/_summary.json
evidence/work/abuse/bola-cross-tenant-stub/run.py                        ← scenario 3
evidence/work/abuse/bola-cross-tenant-stub/{01..07}-*.json + summary     ← 22 evidence files
evidence/work/abuse/silent-country-override-exploit/run.py               ← scenario 4
evidence/work/abuse/silent-country-override-exploit/{01..05}-*.json      ← 6 evidence files
evidence/work/abuse/silent-country-override-exploit/_summary.json
evidence/work/abuse/webhook-spoof-no-event-filter/run.py                 ← scenario 5
evidence/work/abuse/webhook-spoof-no-event-filter/{01..07}-*.json        ← 9 evidence files
evidence/work/abuse/webhook-spoof-no-event-filter/_summary.json
evidence/work/abuse/verification-skip-attempt/run.py + run_iter2.py      ← scenario 6
evidence/work/abuse/verification-skip-attempt/{01..03,11..12}-*.json     ← 15 evidence files
evidence/work/abuse/verification-skip-attempt/_summary.json
evidence/analysis/06-abuse-scenarios.md                                          ← THIS file
```

`run_flow.py` and `_redact.py` not modified — only imported.

---

## Confirmations

- **Sandbox only.** All HTTP calls hit `https://api.balampay.com`. No production credentials touched.
- **No real PII.** All names (`Test`, `Beneficiary`, `PolluteA…T`, `ExploitUSA`, `ControlMX`, `MutA…J`, `RaceD`, `AchExploit`, `WalletExploit`), emails (`test+…@example.com`), SSN-style doc numbers (`TFAK900101AAA`, `FAKE000000`), and bank routing/CLABE values were synthetic. The TRON address `TLsV52sRDL79HXGGm9yzwKibb6BeruhUzy` was reused from Batch C as a publicly-known test address.
- **No raw secrets in evidence.** Every evidence file went through `_redact.redact_headers` + `_redact.redact_body`. Spot-check: `x-api-key: REDACTED(40)`, `Authorization: REDACTED(872)`, `secret: REDACTED(32)`.
- **`run_flow.py` and `_redact.py` not modified.** Only imported via `_abuse_common.py`.
- **Rate-limit safe.** No probe hit a 429. Concurrency was capped at N=10 per scenario.
- **Phase 3 functional track only.** No OWASP / no stress / no load testing. Those are the other two agents' work.
- **No out-of-scope endpoints touched.** All probes against documented or already-discovered paths on `api.balampay.com`.
