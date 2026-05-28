> **MERGED INTO MASTER `integration-log.md` on 2026-05-27.** Canonical drift IDs renumbered: DRIFT-C2..C15 → DRIFT-26..DRIFT-39 (C1 was reserved/unused; mapping is sequential regardless of the gap). See `evidence/analysis/04-integration-log.md` for the consolidated audit trail.

# Batch C — Recipients Polymorphic (parallel probe run)

**Owner:** `data-engineer` (Batch C parallel worker)
**Run date:** 2026-05-28
**User used:** `65ba0e06-9f52-4c43-b093-5d30a632ce3d` (status `CREATED`, `verification_triggered: false` — from prior Batch A/B `users/06-success.json`)
**Note:** Recipient creation **does not require user to be `VERIFIED`** — empirically confirmed below (UNDOCUMENTED — answer to `integration-plan.md` § 3 Batch C open question).
**Evidence dir:** `evidence/work/recipients/` (19 calls captured)
**Scripts:** `evidence/work/probes/batch_C.py` + `evidence/work/probes/batch_C_iter2.py`

---

## 1. Polymorphic schema matrix — empirical (CRITICAL DELIVERABLE)

> Builds on `flow-design.md` § 3.5. **Bold** = empirical correction to flow-design / Reference docs (DRIFT-C).

| Variant | Documented in | Required (runtime) | Optional / silently dropped | Response shape diff vs request |
|---|---|---|---|---|
| **SPEI MX** | flow-design § 3.5 row SPEI | `user_id`, `first_name`, `last_name`, `email`, `phone`, `account.{account_type, clabe(18d), doc_type(rfc\|curp), doc_number}` | request-level `bank_name`, `currency`, `country` **silently dropped from response** (not in `account_details`); `phone` echoed | Response wraps as `{recipient_id, type, first_name, last_name, phone, email, account_type, account_details:{clabe, doc_type, doc_number, doc_country_code(derived alpha-2)}, created_ts, updated_ts, metadata}`. **`doc_country_code` is auto-derived (not sent by integrator) — from CLABE.** |
| **ACH USD** | flow-design § 3.5 row ACH | `user_id`, `first_name`, `last_name`, `email`, `phone`, **`address` object (recipient-level)**, `account.{account_type, routing_number(9d), account_number, type(checking\|savings), bank_name, bank_address(STRING), doc_type, doc_number}` | request-level `account.currency` + `account.country` dropped from response | Same envelope as SPEI but with `address` echoed at recipient level, and `account_details` carries full `bank_address` STRING (GAP-16 confirmed). |
| **USDT (TRON)** | flow-design § 3.5 row WALLET | `user_id`, `first_name`, `last_name`, `email`, `account.{account_type:"WALLET", token:"USDT", network:"tron", address(base58check-valid)}` | `currency`, `phone` optional (omitted in our payload, accepted) | `account_details: {token, address, network}` — fields **reordered** vs request; `currency` field not echoed. **`phone` field is OMITTED from response entirely** when not sent (other variants always echo phone). |
| **SWIFT EUR** | flow-design § 3.5 row SWIFT | `user_id`, `first_name`, `last_name`, `email`, `phone`, **`address` object (recipient-level)** (DRIFT-C5 — flow-design listed this as ACH-only), `account.{account_type:"SWIFT", account_number(IBAN-shape), swift_code(8 or 11), bank_name, bank_address(OBJECT), doc_type, doc_number, doc_country_code}` | request-level `account.currency`, `account.country` dropped from response | Response includes recipient-level `address` AND `account_details.bank_address` (object). **CRITICAL: in POST-create response, `bank_address.state` and `bank_address.postal_code` come back as empty strings `""` despite being present in request. On GET-detail of the same recipient, they're populated correctly. POST-response vs GET-detail divergence — DRIFT-C8.** |

### Cross-variant invariants (from empirical observation):
- All variants use the SAME top-level envelope keys: `{recipient_id, type, first_name, last_name, phone (where sent), email, account_type, account_details, created_ts, updated_ts, metadata}` — no `id`, no `data` wrapper, no `pagination`.
- `recipient_id` is `id`-shaped UUID (lowercase) — **not `id` as Reference page suggests**.
- `created_ts`/`updated_ts` use **PostgreSQL-style space-separated timestamps with `+00` tz suffix** (e.g. `"2026-05-28 00:52:49.879228+00"`) **not ISO 8601 with `T` separator and `Z`** — DRIFT-C7. Will trip any client parsing as ISO 8601 strict.
- `account_details` returned **UNMASKED** in both POST-create response and GET-detail response — DRIFT-C6 contradicts flow-design § 3.5 which says masking format `****7890`.
- Country fields **must be alpha-2** here (`US`, `MX`, `ES`) — contradicts user-creation endpoint which accepts alpha-3 (`USA`, `MEX`, `ESP`) — DRIFT-C2 worsens GAP-20.

---

## 2. Endpoint table

> Latency is total round-trip from inside the runner (network + Lambda + RDS). n is small (single-shot per variant, not 10× repeats).

| # | Endpoint | Method | Iter to 2xx | Doc sufficiency | Drift events | Lat median (ms) | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `/v1/recipients` (SPEI) | POST | 1 | YES (for SPEI) | DRIFT-C6, DRIFT-C7 | 370.0 (1 call) | docs-only payload worked first try |
| 2 | `/v1/recipients` (ACH) | POST | 2 | **NO** | DRIFT-C2, DRIFT-C3 | 276.0 (2 calls) | First call 400'd: doc-stated `doc_type:"ssn"` is invalid (runtime enum: `id\|dni\|passport\|ein`); country was `USA` (alpha-3 doc-style) but runtime requires alpha-2 |
| 3 | `/v1/recipients` (USDT TRON) | POST | 2 | PARTIAL | DRIFT-C4 | 247.0 (2 calls) | First call 400'd because purely-fake T-prefix address failed base58check validation. Test addr `TLsV52sRDL79HXGGm9yzwKibb6BeruhUzy` works |
| 4 | `/v1/recipients` (SWIFT) | POST | 2 | **NO** | DRIFT-C2, DRIFT-C5, DRIFT-C8 | 277.9 (2 calls) | First call 400'd: needs recipient-level `address` (flow-design said ACH-only), country fields must be alpha-2 not alpha-3 |
| 5 | `/v1/recipients?user_id=…` | GET | 1 | PARTIAL | DRIFT-C9 (envelope) | 279.8 | Envelope is `{recipients:[...], total:N}` — **third distinct list-envelope** on the API (vs `/v1/users` = `{data, pagination}`; flow-design predicted flat array) |
| 6 | `/v1/recipients/{id}` (detail SPEI) | GET | 1 | PARTIAL | DRIFT-C6 (unmasked) | 240.6 | account_details returned unmasked |
| 7 | `/v1/recipients/{id}` (detail ACH) | GET | 1 | PARTIAL | DRIFT-C6 | 272.9 | same |
| 8 | `/v1/recipients/{id}` (detail USDT) | GET | 1 | PARTIAL | DRIFT-C6 | 230.8 | full wallet address returned |
| 9 | `/v1/recipients/{id}` (detail SWIFT) | GET | 1 | PARTIAL | DRIFT-C8 | 262.0 | bank_address fully populated here (vs POST-response gaps) |
| 10 | `/v1/recipients` idem-replay-same | POST | 1 | **NO** | DRIFT-C10 (201 not 202) | 245.6 | Returns **201** with the original recipient_id — **flow-design § 3.5 documented 202-on-replay quirk is FALSE in runtime** |
| 11 | `/v1/recipients` idem-conflict (mutated body) | POST | 1 | YES | DRIFT-C11 (empty details) | 277.2 | **409** with Shape B envelope: `{error:{code:"IDEMPOTENCY_CONFLICT", message, details:{}}}`. `details` is empty — no field-level diff info |
| 12 | `/v1/recipients` idem-omit | POST | 1 | YES | DRIFT-C12 (envelope mix) | 224.6 | **400** but Shape A envelope: `{error:"Invalid request data", details:[{path:"idempotency-key", message:"Required", code:"invalid_type"}]}` — **DIFFERENT envelope shape than the 409 above on the same endpoint** |
| 13 | `/v1/recipients` mutation M1 (SPEI + wallet fields) | POST | 1 | (probe) | DRIFT-C13 (silent strip) | 296.4 | **201 — extra fields silently stripped**; mass-assignment-friendly behavior |
| 14 | `/v1/recipients` mutation M2 (SPEI + country=USA) | POST | 1 | (probe) | DRIFT-C14 (silent override) | 272.8 | **201 — `country: "USA"` silently OVERRIDDEN to `"MX"`** in response (derived from CLABE). Integrator gets no warning their declared country was wrong |
| 15 | `DELETE /v1/recipients/{id}` | DELETE | n/a | (probe) | DRIFT-C15 (gateway leak) | 250.8 | **403 ForbiddenException** with **AWS IAM SigV4 error message** leaking through (`"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '…'"`). No `Allow` header. Method not supported — but the error type leaks gateway-layer plumbing. Same class as DRIFT-1 (`/sandbox/auth` 403 ForbiddenException) |
| 16 | `GET /v1/recipients/{id}` (after attempted DELETE) | GET | 1 | (probe) | — | 300.7 | **200 — recipient still exists**, confirming DELETE never executed |

**Overall latency** (n=19 across this batch): min 224.6, median 268.3, max 370.0 ms. POST creates only (n=12): min 224.6 / median 272.8 / max 370.0 ms.

---

## 3. Drift events (Batch C namespace)

> Prefixed `DRIFT-C` to avoid collision with the global DRIFT-1..5 from `integration-log.md`.

### DRIFT-C2 — Recipient country fields require ISO 3166-1 **alpha-2**, contradicting `/v1/users` which accepts **alpha-3**
- **Doc claim:** `flow-design.md` § 3.5 + § 2.6 + GAP-20 — Users uses alpha-3; banks use alpha-2; recipient country was ambiguous.
- **Runtime:** Recipient `address.country`, `account.bank_address.country`, `account.doc_country_code`, and `account.country` **all require alpha-2** (e.g., `US`, `MX`, `ES`). Sending alpha-3 (`USA`, `MEX`, `ESP`) returns 400 `too_big — "Country must be a 2-character ISO code"` / `"Document country code must be exactly 2 characters"`. **Two endpoints on the same API now demand DIFFERENT country code formats** (users=alpha-3, recipients=alpha-2). This is GAP-20 made worse by empirical data: previously suspected one had to "win"; now confirmed they enforce DIFFERENT formats simultaneously.
- **Evidence:** `recipients/02-fail-400-ach.json`, `recipients/04-fail-400-swift.json`.
- **Severity:** HIGH. Integrator who consistently uses alpha-3 (the docs-recommended user format) will be 400-blocked on every non-MX/non-trivial recipient.
- **Doc-sufficiency for affected variants:** NO.

### DRIFT-C3 — Documented `doc_type: "ssn"` for ACH is **rejected at runtime**
- **Doc claim:** `flow-design.md` § 3.5 row ACH lists `doc_type` examples implying SSN/EIN style; `run_flow.py` `fake_individual_payload` uses `doc_type: "ssn"`.
- **Runtime enum:** `id | dni | passport | ein`. `ssn` returns 400 `invalid_enum_value — "Invalid enum value. Expected 'id' | 'dni' | 'passport' | 'ein', received 'ssn'"`.
- **Evidence:** `recipients/02-fail-400-ach.json` line 84-87.
- **Severity:** HIGH. US-bank ACH recipients are the API's bread-and-butter. The Reference page neither enumerates these values nor warns SSN is excluded.
- **Doc-sufficiency:** NO.

### DRIFT-C4 — WALLET TRON address actually validated against base58check at runtime (good!), but **not documented as a hard validation**
- **Doc claim:** `flow-design.md` § 3.5 says TRON addresses start with `T` and are 34 chars — implying string-length validation only.
- **Runtime:** Performs base58check decoding — pure-fake `T...` strings fail with `"Tron wallet address must start with T and be 34 characters long (base58check encoded)"`. **This is the right behavior, but it means an integrator can't generate a fake-but-format-valid TRON address for testing without using a publicly known burn / zero address.**
- **Evidence:** `recipients/03-fail-400-usdt.json`.
- **Severity:** MEDIUM — positive-side finding for security, but a sandbox-friction issue for integrators who need testable fake data. Sandbox should expose a "test wallet address generator" or document that the burn address is testing-safe.
- **Doc-sufficiency:** PARTIAL.

### DRIFT-C5 — SWIFT recipients require recipient-level `address` object — flow-design listed this as ACH-only
- **Doc claim:** `flow-design.md` § 3.5 ACH row mentions `+ recipient-level address object required`; SWIFT row does not.
- **Runtime:** SWIFT returns 400 `"address is required for SWIFT accounts (structured object with street_name, city, state, postal_code, country)"`.
- **Evidence:** `recipients/04-fail-400-swift.json` line 87-91.
- **Severity:** MEDIUM. Easy to fix once you see the 400, but the Reference page doesn't render it → first-iteration failure.
- **Doc-sufficiency:** NO.

### DRIFT-C6 — `account_details` is returned UNMASKED on both POST-create and GET-detail, contradicting docs claim of `****7890` masking
- **Doc claim:** `flow-design.md` § 3.5: "`account_details` is masked (e.g., `account_number: "****7890"`)".
- **Runtime:** Full `clabe`, `account_number`, `routing_number`, `swift_code`, wallet `address`, `doc_number`, etc. returned in plaintext on both POST and GET. No masking observed across any of the four variants.
- **Evidence:** all `26-31-*.json`, `01-success-201-spei.json`, `06-success-200-detail-spei.json`.
- **Severity:** **HIGH — security-adjacent.** If the docs promise masking and engineers build downstream PII-handling on that assumption, a leak surface opens. Either docs need to drop the masking claim, or runtime needs to mask. The **CLABE includes the destination bank code + account number** in plaintext — these are bank-secrecy-sensitive in MX. Should be escalated to `api-security-auditor` for Phase 3 BOLA/info-leak coverage.
- **Doc-sufficiency:** NO (the docs are *more conservative* than runtime — a rare inversion).

### DRIFT-C7 — Timestamp format is **non-ISO**: `"2026-05-28 00:52:49.879228+00"` (space separator + `+00` tz)
- **Doc claim:** No format specified in flow-design § 3.5; implicit assumption is ISO 8601 (`2026-05-28T00:52:49.879228Z` or `+00:00`).
- **Runtime:** Returns PostgreSQL-default timestamp formatting — **space separator, 6-digit microseconds, `+00` not `+00:00`, no `Z`**. JS `new Date("2026-05-28 00:52:49.879228+00")` works in V8/Chrome but fails in strict ISO parsers; Python's `datetime.fromisoformat` (3.10) accepts it; Go `time.Parse(time.RFC3339, …)` **fails**. Bad for codegen / strongly-typed clients.
- **Evidence:** Every success response — see e.g. `01-success-201-spei.json` line 79.
- **Severity:** MEDIUM. Will silently break ISO 8601 deserializers across the typed-client surface (Go, Rust, Swift).
- **Doc-sufficiency:** N/A — format isn't documented at all.

### DRIFT-C8 — SWIFT POST-create response **loses** `bank_address.state` and `bank_address.postal_code` (returns empty strings), but GET-detail returns them correctly
- **Doc claim:** Both fields should round-trip per `flow-design.md` § 3.5 SWIFT row.
- **Runtime:** POST request had `state:"Madrid"`, `postal_code:"28001"`; **POST-response has both as `""`**. Subsequent GET-detail of the same recipient returns both populated correctly. Implies the POST response is built from a different (incomplete) projection than the GET-detail.
- **Evidence:** `recipients/30-success-201-swift-iter2.json` line 95-99 vs `recipients/31-success-200-detail-swift-iter2.json` line 64-69.
- **Severity:** HIGH. Integrators who echo the POST-response to their own UI without re-fetching will store/display empty state and postal code. Worse, **idempotent-replay clients that hash the response to confirm "no change" will get false positives.**
- **Doc-sufficiency:** N/A — divergence isn't a documentable contract, it's a bug.

### DRIFT-C9 — `GET /v1/recipients` envelope is `{recipients:[...], total:N}` — a **third distinct list-envelope shape** on the API
- **Doc claim:** `flow-design.md` § 3.5 says "flat array — no pagination (GAP-15)"; api-reference-coverage suspected `{data:[...]}`.
- **Runtime:** Wrapped object `{recipients: [...], total: 1}`. Not flat. Not `{data, pagination}` (which is what `/v1/users` returns). Not the array implied by GAP-15.
- **Cross-endpoint comparison (this run alone):**
  - `/v1/users` (prior Batch A/B) → `{data:[...], pagination:{total, limit, offset, has_more}}`
  - `/v1/recipients` → `{recipients:[...], total}`  *(no pagination params at all — GAP-15 confirmed)*
  - Predicted: `/v1/virtual-accounts` and others may diverge further.
- **Evidence:** `recipients/05-success-200-list-by-user.json`.
- **Severity:** HIGH. This is the **list-envelope-uniformity finding** — three list endpoints on one API, three different envelopes, no consistent `total` field name, no consistent pagination model.
- **Doc-sufficiency:** NO.

### DRIFT-C10 — Idempotent-replay returns **201 not 202** — flow-design § 3.5 "unusual 202-on-replay" claim is FALSE
- **Doc claim:** `flow-design.md` § 3.5: "**202 on idempotent reuse for existing recipient** (unusual — most APIs use 200 / 201)."
- **Runtime:** Same idempotency-key + same body → **201** with the original `recipient_id`. The replayed body's field order is different (response is built from cache differently), but the status code is the same as a fresh create.
- **Evidence:** `recipients/07-success-201-idem-replay-same-spei.json` — `recipient_id` `ff9828b2-…` identical to original `01-success-201-spei.json`.
- **Severity:** MEDIUM. The 202-quirk was singled out in flow-design as a "generic-SDK-killer." It turns out the docs predicted a quirk that doesn't exist. **Two possibilities:**
  1. The docs description in `account-types-reference.md` is wrong, and runtime always returns 201.
  2. The 202 is reserved for some specific replay scenario we didn't hit (e.g., the *idempotency window expired but the recipient exists*).
  Either way the docs need to be reconciled.
- **Doc-sufficiency:** NO.
- **Cross-link to GAP-08:** This is one of the two GAP-08 sub-confirmations. See § 5.

### DRIFT-C11 — Idempotency-conflict 409 returns `details: {}` (empty) — no field-level diff
- **Doc claim:** `flow-design.md` § 2.4 / GAP-08 says either Shape A `{code, message}` or Shape B `{error:{code, message, details}}` envelope. Implicitly assumed `details` carries diff info.
- **Runtime:** Shape B envelope `{error:{code:"IDEMPOTENCY_CONFLICT", message:"Idempotency key has already been used with different request data", details:{}}}`. **`details` is the empty object** — no indication of which field changed, what the cached body looked like, or which fields are the discriminator.
- **Evidence:** `recipients/08-fail-409-idem-conflict-spei.json`.
- **Severity:** HIGH-for-DX. Integrator debugging an idempotency conflict has zero actionable info. Combined with `metadata: {}` on success responses (every recipient creates with empty metadata; recipient creation accepts no metadata input that we tested), this is a pattern of empty-object responses without explanation.
- **Doc-sufficiency:** NO. Reference page never enumerates this code.

### DRIFT-C12 — `/v1/recipients` returns TWO DIFFERENT error-envelope SHAPES on the same endpoint
- **Doc claim:** `flow-design.md` § 2.3 noted two shapes (Shape A flat, Shape B nested-error) coexist across the API.
- **Runtime on this single endpoint:**
  - 409 idempotency conflict → **Shape B** `{error:{code:"…", message, details:{}}}` (`08-fail-409-…`)
  - 400 validation (ACH, SWIFT, USDT, idem-omit) → **Shape A** `{error:"…", details:[{path, message, code}, …]}` (`02-fail-400-…`, `04-fail-400-…`, `09-fail-400-…`)
- The 400 details use a different inner shape (`{path, message, code}`) than the 409 (`details: {}` as object).
- **Evidence:** `recipients/02, 03, 04, 08, 09`.
- **Severity:** HIGH. **Single endpoint, two error envelopes, two different `details` types.** Type-safe codegen breaks. This is the per-endpoint version of GAP-05 (envelope-shape inconsistency).
- **Doc-sufficiency:** NO.

### DRIFT-C13 — Cross-pollution: SPEI body + WALLET fields → **201 silent strip**
- **Probe:** Send a SPEI body but inject `wallet_address`, `network: "tron"`, `token: "USDT"` inside `account`.
- **Runtime:** **201 success.** Extra fields are silently stripped from the response. The recipient is created as a clean SPEI. No 400, no warning, no `unknown_fields` echo.
- **Evidence:** `recipients/10-success-201-m1-spei-with-wallet-fields.json`.
- **Severity:** MEDIUM (security-adjacent — feeds into mass-assignment / API3 territory). Confirms the API does **whitelist-by-account_type** field-extraction. Better than blacklist, but the *silent* part means typos go undetected — no `additionalProperties: false` style 400.
- **Doc-sufficiency:** N/A — undefined behavior.

### DRIFT-C14 — SPEI with `country: "USA"` → **201 silent OVERRIDE** to `country: "MX"` (derived from CLABE)
- **Probe:** Submit SPEI body with `account.country: "USA"` instead of `"MX"`.
- **Runtime:** **201 success.** Response `account_details.doc_country_code: "MX"` — the API derived MX from the CLABE prefix and silently overrode the integrator's stated country. No warning. The integrator's UI may still show "USA" while the database stores "MX".
- **Evidence:** `recipients/11-success-201-m2-spei-country-mismatch.json`.
- **Severity:** HIGH. **Silent data correction is worse than an error** — it persists divergent state between the integrator's view and Kira's view. An integrator's reconciliation report will not match.
- **Doc-sufficiency:** N/A.

### DRIFT-C15 — `DELETE /v1/recipients/{id}` returns 403 with **AWS-IAM SigV4-style error leaking through**, no `Allow` header
- **Doc claim:** No DELETE endpoint documented for recipients in `flow-design.md` § 3.5.
- **Runtime:** `DELETE` returns **403** with body `{"message":"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '…'."}`. This is the same gateway-layer error class as DRIFT-1 (`/sandbox/auth` returned `ForbiddenException`). It exposes AWS API Gateway internals through a method-not-allowed response.
- **Severity:** MEDIUM (DX + minor security info-leak). A proper unsupported-method should return 405 with `Allow: GET, POST` header.
- **Evidence:** `recipients/12-fail-403-delete-spei.json`.
- **Follow-up:** GET-after-DELETE (`13-success-200-…`) confirms the DELETE had no side effect — the recipient still exists.
- **Doc-sufficiency:** N/A — recipients DELETE is undocumented, but the error class is a quality finding.

---

## 4. Idempotency behavior (consolidated)

> This is the **GAP-08 empirical resolution**. Three probes on `POST /v1/recipients`.

| Probe | Idempotency-Key | Body | Status | Body / envelope shape | Returned recipient_id behavior |
|---|---|---|---|---|---|
| First create | `21962c69-…d70d` | SPEI body S | **201** | `{recipient_id, type, first_name, …, account_details, …}` | `ff9828b2-9e83-4c71-ae3e-040ffb52c894` |
| Replay same body | `21962c69-…d70d` (same) | SPEI body S (same) | **201** *(NOT 202)* | Same fields, **different field order**, identical content | **`ff9828b2-…` (IDENTICAL — true replay)** |
| Replay mutated body | `21962c69-…d70d` (same) | SPEI body S' (last_name changed to "MutatedSurname", doc_number changed) | **409** | **Shape B**: `{error:{code:"IDEMPOTENCY_CONFLICT", message:"Idempotency key has already been used with different request data", details:{}}}` | n/a — error |
| Omit key | (no header) | SPEI body | **400** | **Shape A**: `{error:"Invalid request data", details:[{path:"idempotency-key", message:"Required", code:"invalid_type"}]}` | n/a — error |

**Empirical conclusions for `POST /v1/recipients`:**
- ✅ Idempotency IS enforced — true replay returns identical record.
- ❌ Status code on replay is **201, not the 202 the docs promised** (DRIFT-C10).
- ✅ Conflict detection works — different body with same key → 409.
- ❌ The 409 carries **empty `details: {}`** — zero actionable info for the integrator (DRIFT-C11).
- ❌ **Error envelope is INCONSISTENT on the same endpoint** — 400 uses Shape A, 409 uses Shape B (DRIFT-C12).
- ✅ Omitting the key is correctly rejected with `400 / "Required"`.
- **Not tested in this batch (deferred):** TTL expiry (24h), concurrent N-parallel same-key races, key-from-different-tenant.

---

## 5. GAP-08 resolution (`/v1/recipients` slice)

**GAP-08 (original):** the idempotency.md guide claims 7 endpoints require the header; runtime evidence suggests 9. Multiple envelope shapes on conflict. Recipients allegedly returns 202-on-replay.

**Empirical answer for `/v1/recipients` only:**
1. ✅ **Idempotency IS required** on `POST /v1/recipients` — omit-key returns 400 (matches docs).
2. ❌ **The "202 on replay for existing recipient" claim is FALSE** (DRIFT-C10) — replay returns 201 with the cached body. The docs' "unusual 202" quirk does not exist in the sandbox.
3. ❌ **The on-conflict envelope is Shape B** (`{error:{code, message, details}}`) — **but the on-missing-key envelope on the SAME endpoint is Shape A** (`{error:"…", details:[]}`). GAP-08 is **worse than documented**: not just inconsistent across endpoints, but **inconsistent within a single endpoint depending on which validation tier rejected the call**.
4. ❌ **`details: {}` is empty on the 409** — no field-level diff. The integrator can't debug an idempotency conflict from the response alone.
5. ❓ **Header name casing:** docs say `idempotency-key` lowercase. Our client sent lowercase. Both `Idempotency-Key` and `idempotency-key` were not differentially tested in this batch (deferred to a follow-up probe).

**Status of GAP-08:** Partially resolved for `/v1/recipients`. Requires similar empirical sweep on the other 7 required-idempotency endpoints to fully close. **Recommended priority for PM consideration in the README top-5:** the per-endpoint envelope split (DRIFT-C12) is a strong candidate for slot 5 — it's reproducible in 2 calls, breaks all typed clients, and combines with GAP-05.

---

## 6. Files created (this batch)

- `evidence/work/probes/batch_C.py` — main probe script (Phase C1–C4)
- `evidence/work/probes/batch_C_iter2.py` — iter2 with corrected schemas after iter1 surfaced DRIFT-C2/C3/C4/C5
- `evidence/work/recipients/01..13` and `26..31` — 19 per-call evidence files (skipping 14-25 which were claimed by parallel Batch A worker)
- `evidence/work/recipients/_batch_C_summary.json` — redacted batch-level summary

**Not modified:** `evidence/work/run_flow.py` (per coordination rule).

---

## 7. Open questions / hand-offs

- **For `api-security-auditor` (Phase 3):**
  - DRIFT-C6 (unmasked `account_details` despite docs claim) — escalate to BOLA/info-leak Phase 3 scope.
  - DRIFT-C15 (AWS-IAM-style 403 leak on DELETE) — fingerprintable gateway plumbing.
  - DRIFT-C13 (silent extra-field stripping) — mass-assignment-friendly behavior worth a deeper probe with privileged fields (`status`, `is_admin`, etc.).
- **For `data-architect` (flow-design update):**
  - Update § 3.5 to reflect alpha-2 country requirement, real doc_type enums, recipient-level `address` requirement for SWIFT, drop "masked" claim on account_details, drop "202 on replay" claim, replace timestamp claim with PG-style note, list `{recipients, total}` as the actual list envelope.
- **For `product-manager` (README ranking):**
  - DRIFT-C12 (per-endpoint envelope split) + DRIFT-C8 (SWIFT POST-response field loss) + DRIFT-C14 (silent country override) are the three highest-impact Batch C findings, each worthy of consideration for the README top-5.
  - DRIFT-C9 (`/v1/recipients` envelope) folds into the existing list-envelope-uniformity finding.
- **For `@Nicolle` (PD) / `@Diego` (Eng):**
  - Confirm: is the 202-on-replay-recipient documented quirk a doc bug or a runtime regression? Affects DEC-pending.
  - Confirm: should `account_details` be masked at GET? The docs imply yes; the runtime says no.

---

## 8. Confirmations (per Batch C report requirements)

- Fake data only — no real PII, account numbers, or wallet keys. All values are obviously test (e.g. `000-00-0000`, `FAKE000000`, `TFakeTronAddr…`, the publicly known TRON zero address). ✅
- No raw secrets logged — every evidence file passes through `_redact.redact_headers` + `_redact.redact_body`. ✅
- `evidence/work/run_flow.py` NOT modified — only `auth()` and `capture()` are imported, not patched. ✅
- 19 per-call evidence files written under `evidence/work/recipients/`. ✅
- 4 polymorphic variants successfully created (SPEI, ACH, USDT, SWIFT). ✅
