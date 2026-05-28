> **MERGED INTO MASTER `integration-log.md` on 2026-05-27.** Canonical drift IDs renumbered: DRIFT-B1..B12 → DRIFT-14..DRIFT-25. See `evidence/analysis/04-integration-log.md` for the consolidated audit trail.

# Batch B — User Lifecycle & Verification (parallel probe run)

**Run script:** `evidence/work/probes/batch_B.py` (+ follow-up `batch_B_poll.py` and `batch_B_latency.py`)
**Captured:** 2026-05-28 (~00:50 – 01:00 UTC, ~10 min wall)
**Auth:** single `POST /auth` per script run; tokens kept in-memory only.
**Coordination:** `run_flow.py` shared module — Batch B imports from it; **did not modify**.

## Verification flow discovered

Empirically, Kira sandbox runs a **three-step funnel** to put a user into the verification queue:

1. **`POST /v1/users` with `verification_mode: "automatic"` (default)** — drops user into `status: CREATED`. The undocumented **trigger gate** is: *at least one product's `missing_fields[product]` list must be empty*. As long as *any* product's `missing_fields` list contains entries, `verification_triggered` stays `false` and the user sits in `CREATED` forever.
2. When the integrator's payload fully satisfies *any one product*'s required fields, the create response flips `verification_triggered: true` and the user transitions `CREATED → VERIFYING` server-side within seconds.
3. **The legacy `POST /v1/users/{id}/verifications` is INERT for state transitions.** It returns an AiPrise hosted-link (the API's verification partner) but doesn't move the user's `status` field at all. It exists to mint an embedded-link URL for the integrator's UI; the actual approval still has to come from AiPrise's webhook.

**Critical sandbox reality:** users land in `REVIEW` (`verification_status: in_review`) within ~10 seconds and **stay stuck there indefinitely** (still REVIEW after 2 minutes of polling, no further movement). The docs (`flow-design.md § 5.2`) claim `CREATED --> VERIFIED: sandbox auto-approves` — **this is empirically false.** No sandbox `simulate-deposit`-shaped endpoint surfaces; the only way to move past REVIEW is presumably to either (a) complete AiPrise's hosted flow with real KYC data, or (b) have Kira manually approve via support. **This is the new top-impact blocker** for Batches D and F.

## Endpoint table

| # | Endpoint | Iter to 2xx | Doc sufficiency | Drift events | Lat median (ms) | Notes |
|---|---|---|---|---|---|---|
| B1 | `GET /v1/users/{userId}` | 1 | PARTIAL | DRIFT-B1 | 339.8 (N=10) p95 642 | Existing DRIFT-3 user reachable; response shape mostly matches flow-design § 3.2 but `verification_triggered` field is **missing** entirely on read (only present on create response). 21 → 11 → 11 `missing_fields` after PUTs landed. |
| B2 | `PUT /v1/users/{userId}` | 3 | NO | DRIFT-B2, B6, B7 | 351.2 (N=10) p95 498 | First iter (`account_purpose: operating_business_payments`) → 400 with full enum revealed. Second iter with valid enum → 200. **Empty body returns 200 (not 400).** Metadata values must be strings (numbers/bools → 400). |
| B3 | `POST /v1/users/{userId}/verifications` | 1 | PARTIAL | DRIFT-B3, B4 | 440.0 (N=10) p95 532 | Returns AiPrise hosted-link in `verification_link` / `provider_link`. **Idempotency NOT enforced** — same key + different body returns NEW verification ID (no 409). |
| B4 | `POST /verification/send` (GAP-23) | 2 | NO | DRIFT-B8 | n=1 (251ms) | **Found! Path is `/verification/send` (no `/v1/`, no `/users/{id}/`).** Body shape revealed via 400: `{ "email": "..." }` works → `200 { success, message, expiresAt }`. `{ "client_uuid": "<user_id>" }` returns `400 "Client not found"` — `client_uuid` means CLIENT (tenant), not USER. |
| B5 | `POST /v1/users` (mass-assignment) | 1 | NO | DRIFT-B9 | 200 | Inputting `status: "active"` is rejected only on enum mismatch (not on "not-allowed-on-input") — server discloses input enum `'active' \| 'inactive' \| 'suspended'` (legacy, different from output) so it **does accept that field at create time** — only the value choice is wrong. Strong mass-assignment surface. |
| B6 | `POST /v1/users` (zero-missing) | 2 | NO | DRIFT-3 resolved | 201 | Adding `occupation` to maximal individual → `missing_fields: {}` everywhere → `verification_triggered: TRUE`. **DRIFT-3 root cause confirmed: published "minimal" payload omits `account_purpose`, `source_of_funds`, `employment_status`, `current_employer`, `occupation`. Docs do not list these as required.** |

**Mutation probes on B3** (all 200/201 unless noted):

| # | Probe | Status | Finding |
|---|---|---|---|
| M1 | Replay same key + same body | 201 + 201 | Cached replay works — same `id` returned (`9ca4bd35…`) on both calls. |
| M2 | Replay same key + diff body | 201 + 201 | **NEW** verification IDs (`fdb4…` then `4f7d…`) — **idempotency completely broken**. |
| M3 | Empty body | 400 | `{path: "type", code: "invalid_union_discriminator", message: "Expected 'embedded-link' \| 'api'"}` — undocumented `api` type revealed. |
| M4 | Bad enum (`type: NONEXISTENT`) | 400 | Same envelope — discriminator enum revealed. |
| M5 | Omit `Idempotency-Key` | 400 | `{path: "idempotency-key", code: "invalid_type", message: "Required"}` — confirms required, but case-sensitive (lowercase). |

## Drift events (Batch B namespace)

### DRIFT-B1 — `verification_triggered` field disappears on `GET /v1/users/{id}`
- **Doc claim:** `flow-design.md § 3.2` documents `verification_triggered` as part of `UserResponse`. The field is returned by `POST /v1/users` (as DRIFT-4 already noted in the response).
- **Runtime fact:** `GET /v1/users/{id}` against the same user returns the user object **without** the `verification_triggered` key. The integrator has no way to read this flag after the create response — they must store it client-side or re-issue a no-op PUT to get it returned.
- **Evidence:** `evidence/work/users/12-batchB-get-initial.json` (no `verification_triggered`), vs `evidence/work/users/03-success.json` (create response had it `false`).

### DRIFT-B2 — `PUT /v1/users/{id}` with empty body returns 200 (not 400)
- **Doc claim:** Not explicit, but standard REST PATCH/PUT semantics suggest an empty body should be a no-op or 400. `flow-design.md § 3.2` says PUT returns `200 — UserResponse with updated_fields[]`.
- **Runtime fact:** `PUT` with `{}` returns 200 with full user body + `updated_fields: []` + `requires_reverification: false`. No error. **An integrator can flush state without realizing**, or worse — script a polling-via-PUT loop that succeeds silently with no semantics.
- **Evidence:** `evidence/work/users/15-batchB-put-empty.json` (status 200, `updated_fields: []`).

### DRIFT-B3 — Idempotency NOT enforced on `POST /v1/users/{id}/verifications`
- **Doc claim:** `flow-design.md § 2.4` lists `POST /v1/users/{userId}/verifications` as one of seven endpoints requiring `idempotency-key`. Same-key + different-body should return `409 idempotency_key_reused` (Shape A) or `409 IDEMPOTENCY_CONFLICT` (Shape B).
- **Runtime fact:** Sent same `idempotency-key` UUID + two different `redirect_uri` values. Both calls returned **201** with **different** verification IDs (`fdb4…` and `4f7d…`) and different AiPrise session URLs. **No 409.** Same-key + same-body did return cached replay (same ID). So idempotency is only honored when the body is byte-identical; differing bodies silently create new resources.
- **Severity:** HIGH. A naive integrator retrying with a slightly altered body (e.g., re-encoding the redirect URI) will create a duplicate verification session per retry — billable if AiPrise charges per session.
- **Evidence:** `evidence/work/verification/01-post-verifications-idem-diff-1.json` + `02-idem-diff-2.json`.

### DRIFT-B4 — `POST /v1/users/{id}/verifications` does NOT move the user state machine
- **Doc claim:** `flow-design.md § 5.2` state-machine arrow: `CREATED --> CREATED: POST /verifications (legacy embedded-link)` — note no state change. But § 3.2 calls it "Trigger verification manually after creating a user without all required fields", implying it activates the verification flow.
- **Runtime fact:** Fired this endpoint 3+ times against `ae80515c-…` (the DRIFT-3 user with 11 `missing_fields`). Every call returned 201 with a fresh AiPrise URL. **However**, polling `GET /v1/users/{id}` over 2 minutes after these calls showed **no change** — `status` stayed `CREATED`, `verification_status` stayed `unverified`. The endpoint provisions a hosted-link session but the user record's state is unchanged until the actual KYC flow completes externally.
- **Implication:** the docs imply this endpoint is the manual fallback to "trigger" KYC. Empirically, it produces a URL — but the **state machine moves only when AiPrise reports back**. Integrator must NOT treat `POST /verifications → 201` as "verification started". The actual `VERIFYING` state was observed only on users created with `missing_fields: {}` (B8 — `02e4e953-…` and `0ba8a87a-…`).
- **Evidence:** `evidence/work/verification/01-post-verifications-happy.json` + `evidence/work/verification/poll-drift3-*-success.json` (12 polls × no state change).

### DRIFT-B5 — `account_purpose` enum DIFFERS by user `type` (individual vs business)
- **Doc claim:** `flow-design.md` § 3.2 lists `account_purpose` as a field but does NOT enumerate values. `api-reference-coverage.md` shows `source_of_funds` enum has 19 values; `account_purpose` is similarly undocumented.
- **Runtime fact:** Submitting `account_purpose: "operating_business_payments"` on a business → 400 with **18-value** enum. Same value on an individual → 400 with **14-value** enum. **The two enums overlap but are not equal.** Business-only values include `receive_payments_for_goods_and_services`, `internal_treasury`, `third_party_money_transmission`, `receive_payment_for_freelancing`, `operating_a_company`. Individual-only values include `manage_personal_funds`. Common values include `receive_payments`, `make_payments`, `personal_or_living_expenses`, `protect_wealth`, etc.
- **Severity:** MEDIUM-HIGH. A docs-only integrator has no way to know the field exists, much less that it's polymorphic on the user type. Discovery requires deliberately sending an invalid value.
- **Evidence:** `evidence/work/users/13-batchB-put-complete-act.json` (business 400 — 18 values), `evidence/work/users/21-batchB-maximal-individual.json` previous run (individual 400 — 14 values; superseded by 23 file after fix).

### DRIFT-B6 — `business_industry` is a NAICS-coded ARRAY enum (90+ values), not the string the docs imply
- **Doc claim:** Not enumerated in any of our docs sweeps — `business_industry` is mentioned only in the `missing_fields` block per DRIFT-3.
- **Runtime fact:** Submitting `business_industry: "technology"` (string) → 400 `Expected array, received string`. Submitting `business_industry: ["technology"]` → 400 with **90+ NAICS-coded enum values** revealed: `crop_production`, `animal_production`, `food_manufacturing`, `data_processing_hosting_related_services` (closest to "tech"), etc. **This is the US Census NAICS list, snake_cased**, and the docs publish zero of it.
- **Severity:** HIGH for any non-trivial business segmentation. Integrator must guess at a 90-value list with no doc.
- **Evidence:** `evidence/work/users/22-batchB-maximal-business-act.json` (string-rejected), `evidence/work/users/24-batchB-zero-missing-business.json` previous run (full enum revealed).

### DRIFT-B7 — `metadata` values must be strings (silent type constraint)
- **Doc claim:** None — `metadata` is documented as an opaque key-value map.
- **Runtime fact:** `PUT /v1/users/{id}` with `metadata: { "latency_probe": true }` (Python bool / JSON `true`) → 400 `path: "metadata.latency_probe", message: "Expected string, received boolean"`. Numbers presumably fail too. Forces integrator to stringify everything (lose type semantics) without any doc warning.
- **Severity:** LOW-MEDIUM (will cause client-side wrangling but won't lose data).
- **Evidence:** `evidence/work/probes/batch_B_latency.py` first run output (lines 1-10 of PUT 400s, see in-repo diff).

### DRIFT-B8 — GAP-23 RESOLVED: OTP endpoint exists at `POST /verification/send` (root, not `/v1/`)
- **Doc claim:** `flow-design.md § 3.7` and `evidence/analysis/08-flow-design.md § 6 GAP-23`: "OTP endpoint `POST /verification/send` named in payouts guide but **no reference page exists**." Naming was ambiguous — `/v1/verification/send`? `/v1/users/{id}/verification/send`?
- **Runtime fact:** Empirically the path is **`POST /verification/send`** (no `/v1/` prefix — like `/auth`). Body shape: `{ "email": "<registered email>" }` → `200 { success: true, message: "OTP sent to registered email address", expiresAt: "<ISO timestamp>" }`. The `{ "client_uuid": "<user_id>" }` variant returns `400 "Client not found"` — `client_uuid` here means **tenant-client UUID**, NOT the Kira user ID we passed. **HUGE finding:** the docs conflate `client_uuid` (tenant) and `user_id` (end customer) — this endpoint is keyed on **email**, not user, and the integrator has no doc clue.
- **Side discovery:** Three other guessed paths returned `403 IncompleteSignatureException` — they exist at the AWS gateway layer but require **AWS SigV4 signing**, not Bearer JWT. These are likely internal-only / admin endpoints — DO NOT publish.
- **Evidence:** `evidence/work/verification/10-otp-send-probe-02-verification_send.json` (400 revealing body shape), `evidence/work/verification/12-otp-send-email.json` (200 success).

### DRIFT-B9 — Mass-assignment: `status` accepts the LEGACY enum on input (different from output)
- **Doc claim:** `flow-design.md § 3.3` documents output `status` enum as `CREATED|VERIFYING|VERIFIED|REJECTED|REVIEW` (modern uppercase). No mention of which values are accepted as INPUT.
- **Runtime fact:** Sending `status: "VERIFIED"` on `POST /v1/users` returns 400 with the **input** enum: `'active' | 'inactive' | 'suspended'` — a third enum, distinct from the modern output set AND distinct from the legacy `verification_status` lowercase enum. So Kira has *three* enums for the same concept:
  - Input (modern): `active|inactive|suspended` (3 values)
  - Output (modern): `CREATED|VERIFYING|VERIFIED|REJECTED|REVIEW` (5 values)
  - Output (legacy): `unverified|started|in_review|verified|rejected|needs_action` (6 values)
- **Mass-assignment implication:** the API **does accept `status` as an input field** — the integrator can choose `active|inactive|suspended` at create time. Whether `status: "active"` lets an unverified user bypass KYC is a Phase 3 / security-auditor probe.
- **Evidence:** `evidence/work/users/20-batchB-mass-assignment-probe.json`.

### DRIFT-B10 — Sandbox does NOT auto-approve verification; stuck in `REVIEW` indefinitely
- **Doc claim:** `flow-design.md § 5.2` state-machine: `CREATED --> VERIFIED: sandbox auto-approves`. Also `flow-design.md § 4.6 Recipe F` shows `Kira->>Webhook: user.verification.accepted` as the happy-path async event.
- **Runtime fact:** After triggering verification (B8 — empty `missing_fields`), the user transitions `CREATED → VERIFYING → REVIEW` within ~10s. Then it **stays in REVIEW for the full 2-minute poll window** with no further movement. `eligible_products[*].eligible` remains `false` for everything. The doc claim "sandbox auto-approves" is empirically false on at least a 2-minute timescale.
- **Severity:** **CRITICAL** for the exercise. Without auto-approve, an integrator cannot validate the full flow end-to-end in sandbox — every test session would require a human approval. This **blocks Batches D and F** as designed (they need `status: VERIFIED`).
- **Open question for `@Diego`:** how is a sandbox user marked `VERIFIED`? Is there an undocumented sandbox endpoint, a partner-side toggle, or a fixed wait time we just didn't hit? OR is sandbox simply non-functional for the verified state?
- **Evidence:** `evidence/work/verification/poll-individual-*-success.json` (12 polls — frozen at REVIEW), `evidence/work/verification/poll-business-*-success.json` (same).

### DRIFT-B11 — S3 presigned URLs in API responses leak `production` bucket name + tenant `client_id`
- **Doc claim:** None — file upload mechanism is undocumented.
- **Runtime fact:** When `POST /v1/users` body contains `documents[*].file` as a base64 data URI, the response replaces it with a 10-minute presigned S3 URL like:
  `https://kirafin-user-files-production.s3.us-west-2.amazonaws.com/clients/<tenant_uuid>/users/<user_uuid>/associated-persons/person-0/<ts>-<token>-drivers_license-front.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=600&X-Amz-Security-Token=...`
- **Two issues:**
  1. **`production` in the bucket name even on sandbox** — confirms sandbox + prod share a bucket (cross-tenant S3 vector, Phase 3 BOLA / SSRF surface).
  2. **Tenant `client_id` UUID leaks via the path** — confirms the data engineer's API key maps to one specific tenant, exposed in every file URL. (Mostly cosmetic, but defense-in-depth: tenant IDs should not be in public URLs.)
- **Severity:** MEDIUM-HIGH (the cross-bucket finding); LOW (the path leak).
- **Evidence:** `evidence/work/users/21-batchB-maximal-individual.json` (look for `s3.us-west-2.amazonaws.com/kirafin-user-files-production`).

### DRIFT-B12 — Undocumented verification type `api` (in addition to documented `embedded-link`)
- **Doc claim:** `flow-design.md § 3.2` documents only `type: "embedded-link"` for `POST /v1/users/{id}/verifications`.
- **Runtime fact:** Sending empty body / invalid `type` value reveals the discriminator enum: `'embedded-link' | 'api'`. The `api` value is undocumented — presumably for headless KYC flows (vs hosted UI). Worth a separate iteration in Phase 3 to discover the request shape and how the verification then advances without a redirect.
- **Severity:** MEDIUM (undocumented surface = undocumented bug surface).
- **Evidence:** `evidence/work/verification/01-post-verifications-missing-required.json` (line 56), `evidence/work/verification/01-post-verifications-bad-enum.json` (line 59).

## Verification state machine — observed vs documented

| State | Documented? (§ 5.2) | Observed? | Trigger to enter |
|---|---|---|---|
| `CREATED` | YES | YES | `POST /v1/users` (success) — landing state regardless of `missing_fields` |
| `VERIFYING` | YES | YES | Auto when `missing_fields: {}` on create; observed within ~10s of create (transient — only seen on poll #1 of 12) |
| `REVIEW` | YES | **YES (terminal in sandbox!)** | Reached ~10s after `VERIFYING`. **Stays here indefinitely** — see DRIFT-B10. Docs imply this is transient (`REVIEW --> VERIFIED`); empirically it's stuck. |
| `VERIFIED` | YES | **NO — never reached** | Docs claim sandbox auto-approves; empirically didn't happen in 2-minute window. |
| `REJECTED` | YES | NO — not probed | Would require AiPrise to reject; not in our control. |
| Legacy `unverified` | YES | YES | Maps to `CREATED` initially. |
| Legacy `started` | YES | **NO observed** | Docs claim it exists; we observed only `unverified → in_review` (skipped `started`). |
| Legacy `in_review` | YES | YES | Maps to modern `REVIEW`. |
| Legacy `verified` | YES | NO — not reached | Same blocker as modern `VERIFIED`. |
| Legacy `needs_action` | YES | NO observed | Possible target after PUT-with-sensitive-field on a verified user (we couldn't get to that state). |

**Observed transition timeline** (zero-missing individual, see `poll-individual-*.json`):
```
T+0s   POST /v1/users (verification_triggered: true) → status: CREATED
T+10s  GET → status: VERIFYING, verification_status: unverified
T+20s  GET → status: REVIEW, verification_status: in_review
T+30s..120s  GET → status: REVIEW (stuck)
```

## DRIFT-3 follow-up

**RESOLVED.** The verification-trigger gate is **`missing_fields: {}` for at least one product**. The published "minimal" payloads in `flow-design.md § 3.2.1` are missing five undocumented-as-required fields:

| Field | Where required | First learned via |
|---|---|---|
| `account_purpose` | All user types (different enum per type — DRIFT-B5) | 400 on `PUT /v1/users` first iter (`13-batchB-put-complete-act.json`) |
| `source_of_funds` | Individual | Not yet probed for required-ness (we added it speculatively) |
| `employment_status` | Individual | Same |
| `current_employer` | Individual (when employed) | Same |
| `occupation` | Individual (both products) | `21-batchB-maximal-individual.json` `missing_fields: [occupation]` after we'd added all others |
| `business_industry` | Business (NAICS-coded ARRAY — DRIFT-B6) | `22-batchB-maximal-business-act.json` 400 |
| `doing_business_as`, `phone`, `formation_country`, `address_*` | Business | DRIFT-3 user's `missing_fields` list |

The docs need a NEW section: **"Minimum payload to AUTO-TRIGGER verification"** distinct from "Minimum payload accepted by `POST /v1/users`". The two are completely different. The first triggers a state machine the second does not.

**A successful auto-trigger create:**
- See `evidence/work/users/23-batchB-zero-missing-individual.json` (status 201, `verification_triggered: true`, `missing_fields: {}`).
- See `evidence/work/users/24-batchB-zero-missing-business.json` (status 201, `verification_triggered: true`, `missing_fields: {usa-virtual-accounts: [5 fields]}` — but the **ACT** product is happy, so the trigger fires for ACT only).

## Phase 2 unblocking status

- **Are Batches D (Virtual Accounts) and F (Payouts) unblocked?** **PARTIALLY (with a hard caveat).**
  - We now know HOW to trigger verification (zero-missing-fields create), and we have a user (`02e4e953-…`) that's in `REVIEW`. So Batch D can proceed with this user against `POST /v1/virtual-accounts` and capture **whether `REVIEW` is treated as `VERIFIED` for the purpose of VA creation**, or if the API enforces `status: VERIFIED` strictly (the doc's strong dependency claim).
  - However, **the sandbox does NOT auto-approve verification** (DRIFT-B10). Batches D and F can only validate the "user has no VA yet" / "user has REVIEW" branches — they cannot exercise the canonical happy path (active VA, executable payout) without a `VERIFIED` user.
  - **Recommendation for the next dispatch:** Batch D should proceed with the REVIEW-state user we created (`02e4e953-…` or `0ba8a87a-…`) and BOTH capture (a) what `POST /v1/virtual-accounts` returns when user is in REVIEW (expect 400 per the doc's verification gate), AND (b) escalate the sandbox-auto-approve question to `@Diego` immediately — this is now the critical blocker on the rest of Phase 2.

## Files created/modified

**Created:**
- `evidence/work/probes/batch_B.py` — main probe (B0–B8 + mutations)
- `evidence/work/probes/batch_B_poll.py` — 2-minute state polling for 3 users (12 polls × 3 = 36 captures)
- `evidence/work/probes/batch_B_latency.py` — N=10 latency baselines for 3 endpoints
- `evidence/work/integration-log-batch-B.md` — THIS file
- `evidence/work/users/10-batchB-get-existing.json` through `24-batchB-zero-missing-business.json` (15 new files)
- `evidence/work/verification/01-post-verifications-*.json` (8 mutation captures)
- `evidence/work/verification/02-post-verifications-omit-idem.json`
- `evidence/work/verification/10-otp-send-probe-*.json` (4 path-guess captures)
- `evidence/work/verification/11-otp-send-client_uuid.json` + `12-otp-send-email.json`
- `evidence/work/verification/poll-{individual,business,drift3}-{01..12}-success.json` (36 poll captures)
- `evidence/work/latency/get__v1_users_id.json`
- `evidence/work/latency/post__v1_users_id_verifications.json`
- `evidence/work/latency/put__v1_users_id.json`

**NOT modified:**
- `evidence/work/run_flow.py` (shared with parallel batches — read-only)
- Any existing `users/01-*.json` through `users/06-*.json` (preserved from Batch A's earlier work)

## Open questions for `@Diego` / `@Nicolle`

1. **`@Diego`:** How does a sandbox user reach `VERIFIED`? Empirically we land in `REVIEW` and stay there 2+ minutes with no movement. Is there a sandbox-only endpoint to mark a user verified? A timer (>2 min)? A partner-side toggle?
2. **`@Nicolle`:** Docs publish `flow-design.md § 3.2.1` "Minimal business — ACT product" payload as enough to trigger KYB. Empirically it leaves the user in `CREATED` with 21 missing fields. Can the docs add a "Minimum to auto-trigger verification" example distinct from the "minimum the API accepts" example?
3. **`@Diego`:** Is the `idempotency-key` honored on `POST /v1/users/{id}/verifications`? Same-key + different-body returned 201 with a new ID — we expected 409 per the idempotency.md guide. Is this an implementation bug or by-design?
4. **`@Nicolle`:** `POST /verification/send` exists at the **root path** (no `/v1/`) — should the docs add a reference page? Also it's keyed on `email` (not `user_id`/`client_uuid`) — worth disambiguating in the docs because the field is currently named `client_uuid` in the response when really it's the tenant-level client UUID.
5. **`@Diego`:** `business_industry` is a 90+ value NAICS enum and `account_purpose` is a 14- or 18-value polymorphic enum (by user type) — neither is documented. Can these be added to the API Reference field tables?
6. **`@Diego`:** Are file-upload S3 URLs supposed to point to a bucket named `kirafin-user-files-**production**` even from the sandbox? Confirming whether sandbox + prod share a bucket is critical for Phase 3 security work.

## Confirmation

- **No real PII used.** All names "Test", SSN `000-00-0000`, EIN `00-0000000`, DL `FAKE-DL-000000`, document number `FAKE-DOC-*`. Emails are `test+...@example.com` / `ops+...@example.com`. Tiny 1×1 PNG for document images.
- **No raw secrets logged.** Every evidence file went through `_redact.py` (`Authorization`, `x-api-key`, `set-cookie` all `REDACTED(<len>)`).
- **`run_flow.py` not modified.** All Batch B code is in `evidence/work/probes/batch_B*.py`.
