# Phase 1 — Documentation Quality Findings

**Closeout date:** 2026-05-27
**Source artifacts:**
- evidence/analysis/08-flow-design.md (30 endpoints, 37 canonical gaps catalogued; GAP-01..GAP-37 — extended via DEC-005 reconciliation 2026-05-27)
- evidence/analysis/11-docs-coverage-matrix.md (Guides sweep × 8 agents; 23% sidebar dead-link rate; Shape D auth envelope; sourced canonical GAP-35 / GAP-36)
- evidence/analysis/10-product-catalog.md (9 products, 3 dead sidebar entries; product-vs-API mismatches; sourced canonical GAP-37)
- evidence/analysis/12-api-reference-coverage.md (14 of ~30 Reference pages probed, 62 net-new findings, canonical GAP-29..GAP-34 added)

> **Scope of this file:** docs-quality findings only — the Phase 1 lens. Empirical Phase 2 latency/iteration findings and Phase 3 abuse/security findings are out of scope and listed only in the handoff section. Findings are ordered by integrator impact (time lost on day 1, silent breakage in prod, blocks go-live, fraud exposure at the docs level), not by GAP number.

---

## Executive Summary

### Four-Pillar Scoring

| Pillar | Score (1-5) | One-line verdict |
|---|---|---|
| Documentation Quality | **2/5** | 23% of the sidebar 404s, ~80% of error codes never appear in the dedicated error page, every Reference page hides its response JSON behind "Click Try It!", and one core endpoint (Quotations) has two disjoint published schemas. |
| Ease of Connection | **2/5** | `/auth` Reference page omits the `x-api-key` requirement and lists no Bearer; `createuser` hides the `business` half of the product; no Java/Kotlin code samples for LATAM-bank buyers; no end-to-end copy-paste quickstart beyond a single `/auth` curl. |
| Docs↔Runtime Congruence | **2/5** | `/banks` has no `/v1/` prefix while every other endpoint does; Reference page for `createvirtualaccount` is missing ~60% of body fields after the Apr-14 changelog; payout status casing (`PENDING` vs `pending`, `returned` missing from detail schema) drifts within the same docs portal. |
| Integration Hardening | **2/5** | Webhook contract specifies neither signature encoding (hex/base64/`sha256=`) nor retry/DLQ/replay window/timestamp header; `secret` is documented as **optional** on `/webhooks/register`; no `request_id` is ever returned, yet the error-handling page tells support to attach one; no rate-limit error is documented despite a published 10rps cap. |

### Top-line headline

Kira's docs read more like an early-access pitch than a production payments contract — the Reference layer is materially less complete than the Guides, the Guides contradict the Reference on a core endpoint (Quotations), and three sidebar entries that real enterprise buyers (Banco Industrial, N1co) would open on Day 0 (versioning, metadata, api-upgrades) all 404. An integrator following the docs literally will get a 401 on their first call, will have no idea what `quotations` accepts, and will discover the webhook signature encoding by reverse-engineering.

---

## Ranked Findings (docs-quality only — Phase 1 scope)

---

## Finding #1 — Quotations Reference and Guides describe two disjoint endpoint schemas

**Severity:** CRITICAL
**Pillar:** Documentation Quality (sub-axis: cross-page consistency) / Docs↔Runtime Congruence (one of the two docs sets must be lying about runtime)
**Category:** docs-runtime drift / cross-page contradiction
**Why this matters to a client:** Quotations sits between Recipients and Payouts in Recipe B (USD → MXN via SPEI) and Recipe D (SWIFT EUR) — every fiat-to-fiat or fiat-to-stablecoin payout has to call `POST /v1/quotations` first to lock an FX rate. An integrator following `docs/quotation-guide.md` will send `{base_currency, quote_currency, amount}`; an integrator following `/reference/createquotation` will send `{account_type, wallet_network, wallet_token, amount}`. One of those two will 400 (best case) or be silently accepted with garbage results (worst case). Until the team probes which is canonical, every payout recipe in the docs is blocked. Cost estimate: 1-2 days lost debugging the schema mismatch on what should be a 5-minute integration step.
**Evidence:**
- evidence/analysis/12-api-reference-coverage.md § Family 5 — Quotations → "MASSIVE schema drift between Reference and Guides for the same endpoint. Reference Quotations body fields: `amount`, `recipient_id`, `account_type`, `wallet_network`, `wallet_token`, `inverse_calculation`... Guides describe `base_currency`, `quote_currency`, `amount`, `amount_in_destination`."
- evidence/analysis/12-api-reference-coverage.md § F-REF-2 — Quotations Reference-vs-Guides schema drift (GAP-31)
- evidence/analysis/08-flow-design.md § 3.6 Quotations — Guides-version contract
**Related GAP(s):** GAP-31 (schema disjoint); GAP-29 (Quotations Reference hidden from `llms.txt`, only reachable via `/v2026-04-14/reference/createquotation`)
**README top-5 candidate?** **YES** — this is the highest-impact docs-quality finding in Phase 1. Single endpoint that is documented two ways and blocks the most important integration recipe.
**Phase 2/3 probe needed?** YES — send both schemas to `POST /v1/quotations` and capture which returns 200. Whichever wins is the real contract; the other docs page is the one to fix. Until this probe runs, this finding is "two docs pages disagree"; after the probe it becomes a docs↔runtime drift with a named winner.

---

## Finding #2 — Three sidebar entries 404 (versioning, metadata, api-upgrades) — 23% dead-link rate

**Severity:** CRITICAL
**Pillar:** Documentation Quality (findability + completeness)
**Category:** docs gap / versioning / sales-readiness
**Why this matters to a client:** An enterprise buyer doing a procurement-stage docs walkthrough (Banco Industrial, N1co) clicks on three sidebar entries that any payments-API buyer would open on Day 0 — *Versioning*, *Metadata*, *API upgrades* — and gets a 404 on each. The Apr-14 changelog explicitly promised a Versioning guide that does not exist; the same changelog announced an `X-Api-Version` header with two values (`2025-01-01` default, `2026-04-14` latest) that no example request anywhere sets. Without a published upgrade/deprecation policy, multi-year contracts are unsignable: today's "default" client is silently on `2025-01-01` and there is no published EOL date. Without `metadata`, no reconciliation key can be attached to a payment for the integrator's bookkeeping (every modern payments API has this — Stripe, Plaid, Adyen). This is a deal-stage blocker, not a typo.
**Evidence:**
- evidence/analysis/11-docs-coverage-matrix.md § Section 11 — Metadata (MISSING/404), § Section 12 — Versioning (MISSING/404), § Section 13 — API upgrades (MISSING/404)
- evidence/analysis/10-product-catalog.md § Dead sidebar entries (3 products that don't exist) — `metadata`, `versioning`, `api-upgrades`
- evidence/analysis/08-flow-design.md § 1.2 Versioning model → "That guide page does not actually exist at /docs/api-versioning.md or /docs/versioning.md (both return 404). The header is announced but never specified."
- evidence/analysis/08-flow-design.md § 6 — GAP-01 (Versioning header announced but no spec — CRITICAL)
**Related GAP(s):** GAP-01 (versioning), GAP-35 (api-upgrades 404 — no deprecation policy), GAP-36 (metadata 404) — canonical numbering per DEC-005 (2026-05-27 reconciliation).
**README top-5 candidate?** **YES** — promotes GAP-01 from "one missing page" to "three missing pages = a pattern". The pattern is the headline.
**Phase 2/3 probe needed?** YES — send `X-Api-Version: 2025-01-01` vs `2026-04-14` vs omitted vs garbage to two endpoints known to have changed (`POST /v1/users`, `POST /v1/quotations`) and diff the response schemas. This empirically confirms whether un-versioned clients are silently on the old schema.

---

## Finding #3 — Three (now four) coexisting error envelope shapes; generic error handlers cannot be written

**Severity:** CRITICAL
**Pillar:** Documentation Quality (accuracy / cross-page consistency) / Integration Hardening (error UX)
**Category:** error envelope / error UX
**Why this matters to a client:** Every integrator writes a single error handler on Day 1. Kira returns **four** different error envelope shapes from the same API surface: (A) flat `{code, message}` on user/VA/balance endpoints, (B) nested `{error: {code, message, details}}` on recipients/payouts/payins/quotations with codes in SCREAMING_SNAKE_CASE, (C) Pydantic-style `{error, details:[{loc/path, msg, code}]}` on `/auth` 422, and (D) bare `{message}` on `/auth` 401 expired-token (no `code`, no `error`). Generic error parsers will null-deref on `.code`, miss the validation details, and fail to surface the actual problem. Cost estimate: every error path must be wrapped in a per-endpoint try/catch — multiply by ~30 endpoints. This is the failure mode that puts a feature in prod and then leaks support tickets for a week before someone notices the parser never fires.
**Evidence:**
- evidence/analysis/08-flow-design.md § 2.3 Error envelope — three coexisting shapes (canonical inventory of Shapes A, B, C with code lists)
- evidence/analysis/11-docs-coverage-matrix.md § Section 3 — Getting Started — fourth shape D ("the auth guide documents a 401 expired-token body that has only `message`, no `code` — neither Shape A nor B")
- evidence/analysis/08-flow-design.md § 6 — GAP-05 (Three error envelope shapes coexisting — CRITICAL)
- evidence/analysis/12-api-reference-coverage.md § Aggregate updates → "Reference pages document a fourth envelope flavor: bare-status (no body) — e.g., POST /webhooks/register documents only 200 with no body schema. This is Shape E."
**Related GAP(s):** GAP-05 (envelope inconsistency); touches GAP-06 (no `request_id` in any error body); GAP-19 (status casing inside error bodies)
**README top-5 candidate?** **YES**
**Phase 2/3 probe needed?** YES — Data Engineer should build `evidence/work/error-envelopes/matrix.md` by triggering one error of each kind (401, 400 validation, 422 on `/auth`, 409 idempotency conflict on users vs VAs, 404, 403, 429 if reachable) and capture the empirical shape. Today the team has the docs claim; the matrix would seal the finding with raw HTTP.

---

## Finding #4 — Webhook delivery contract has no signature encoding, no retry policy, no replay protection, and `secret` is documented as optional

**Severity:** CRITICAL
**Pillar:** Integration Hardening (webhook contract)
**Category:** webhook contract / security-adjacent
**Why this matters to a client:** Webhooks are how Kira tells the integrator that money moved (`payout.completed`, `virtual_account.deposit_funds_received`, `payin.completed`). Today the docs do not specify: (1) the encoding of `x-signature-sha256` (hex? base64? `sha256=` prefix?) — so signature verification code is a coin-flip until you reverse-engineer one delivery, (2) retry schedule or DLQ behavior — Vercel/Lambda cold-starts can exceed Kira's unstated ack timeout and silently produce duplicate deliveries, (3) replay-protection window or a `x-timestamp`/`x-delivery-id` header — meaning a captured signature is replayable forever, (4) signature-secret rotation flow — there is no `PUT /webhooks/register` documented (GAP-21), so a leaked secret = open ticket with support. Compounding all of the above: the Reference page `/reference/post_webhooks-register` documents **zero error codes**, marks `secret` as **optional**, and (per WebFetch) does not list a single required header. If `secret` is genuinely optional, a webhook registered without one cannot be verifiably authenticated at all — every "completed payout" event becomes spoofable.
**Evidence:**
- evidence/analysis/08-flow-design.md § 2.7 Webhooks → "The docs say 'Acknowledge receipt immediately, process asynchronously' but do not specify: Retry policy / backoff schedule · Dead-letter behavior or max attempts · Replay protection (no timestamp header; no nonce) · Signature header format (raw hex? base64? sha256= prefix?) · Whether `secret` can be rotated"
- evidence/analysis/08-flow-design.md § 6 — GAP-11 (Webhook delivery semantics absent — CRITICAL), GAP-21 (no webhook update/delete endpoint — HIGH)
- evidence/analysis/12-api-reference-coverage.md § Family 7 — Webhooks → "Body fields documented: webhook_url (uri, required), secret (string, OPTIONAL), client_uuid (string, required). `secret` being OPTIONAL is a finding... Status codes documented: ZERO error codes documented. Only 200."
- evidence/analysis/12-api-reference-coverage.md § F-REF-6 — Webhook register reference page has ZERO error code / auth / validation documentation
**Related GAP(s):** GAP-11 (delivery semantics); GAP-21 (no management endpoint); GAP-12 (legacy events coexist)
**README top-5 candidate?** **YES**
**Phase 2/3 probe needed?** YES (Phase 3, security harness) — register with `secret: ""` / `secret: null` / omitted; capture whether `x-signature-sha256` is still emitted on deliveries. Also probe whether a different `client_uuid` than the one tied to the API key is accepted (cross-tenant webhook hijack). This finding is supported by docs evidence today; Phase 3 probes will elevate from "underspecified" to "exploitable" if `secret` is genuinely optional at runtime.

---

## Finding #5 — Wallets is on the product-comparison matrix but has no `/v1/wallets` Reference page

**Severity:** HIGH
**Pillar:** Documentation Quality (completeness) / Ease of Connection (time-to-first-call → infinity)
**Category:** docs gap / product-vs-API mismatch
**Why this matters to a client:** `use-case-product-comparison` lists five products as Kira's catalog: Wallets · Payment Link · Virtual Account · cashPay · Payout API. Wallets is the **only product in the matrix claiming "Global coverage" and "KYC: Not Required"** — i.e., the most attractive low-friction product for a buyer scoping a fast prototype. An integrator picks Wallets, opens the docs, and finds *nothing*. `POST /v1/users/{userId}/wallets` is named once, in the idempotency.md endpoint list, with no Reference page in `llms.txt`. No GET, no LIST, no balance endpoint, no send/transfer endpoint. The buyer spends 2-4 days asking on Slack, asking on support, before concluding the product as advertised doesn't ship. Compounding: the matrix says "no KYC" but `POST /v1/users/{id}/wallets` is a sub-resource of `users` which auto-triggers KYC on creation — even if the endpoint exists, the no-KYC claim is contradicted by the resource hierarchy. This is the single worst trust hit in the product brochure.
**Evidence:**
- evidence/analysis/10-product-catalog.md § Product 1 — Wallets → "Endpoint not in reference... `POST /v1/users/{userId}/wallets` appears only in the idempotency.md endpoint list (flow-design §2.4) with no reference page. Not in `llms.txt`."
- evidence/analysis/10-product-catalog.md § Mismatch #1 — Wallets is on the matrix but has no reference page
- evidence/analysis/11-docs-coverage-matrix.md § Section 2 — Use Case Product Comparison → "NEW FINDING-CANDIDATE: 'Wallets' product is on the comparison table but absent from flow-design's §3 Resource Catalog"
- evidence/analysis/08-flow-design.md § 2.4 Idempotency — confirms `POST /v1/users/{userId}/wallets` exists in the idempotency list only
**Related GAP(s):** **GAP-37 — Wallets product marketed without reference page** (canonical assignment per DEC-005, 2026-05-27 — was product-catalog's proposed GAP-31; renumbered to resolve collision with api-reference-coverage's GAP-31 for Quotations schema drift).
**README top-5 candidate?** **YES**
**Phase 2/3 probe needed?** YES — Data Engineer: probe `POST /v1/users/{id}/wallets` with a minimal body; capture response. Then probe `GET /v1/users/{id}/wallets`, `GET /v1/wallets`, `GET /v1/wallets/{id}`, `POST /v1/wallets/{id}/transfer`. Confirm whether the surface exists undocumented (HIGH severity → CRITICAL) or genuinely missing (HIGH severity holds).

---

## Finding #6 — `/banks` is unversioned (no `/v1/` prefix) — codegen pipelines silently break

**Severity:** HIGH
**Pillar:** Docs↔Runtime Congruence (path-level inventory inconsistency)
**Category:** versioning / docs-runtime drift / codegen pain
**Why this matters to a client:** Every Kira endpoint is `/v1/...` except `GET /banks`, which the Reference page documents as `https://api.balampay.com/sandbox/banks`. Every OpenAPI/Postman/codegen tool will assume a uniform prefix and produce broken stubs for `/banks`. For LATAM integrators (the marketed customer for the Payouts API across 14 currencies), `/banks` is the bootstrap call that supplies the `bank_code` enum for every PSE/PSE/CLP/ARS recipient — getting it wrong breaks every payout creation downstream. Worse: an unversioned endpoint has **no path-level versioning recovery** if its shape ever changes; this becomes a structural inheritance of GAP-01. This is the kind of finding that ships without anyone noticing because runtime returns 200, until codegen lands and `/v1/banks` silently 404s.
**Evidence:**
- evidence/analysis/12-api-reference-coverage.md § Family 8 — Reference Data → "`GET /banks` path: confirmed as `https://api.balampay.com/sandbox/banks` — NO `/v1/` prefix. Every other endpoint uses `/v1/...`. The Reference page is the only place this discrepancy is fully visible."
- evidence/analysis/12-api-reference-coverage.md § F-REF-3 — `/banks` endpoint has no `/v1/` prefix (GAP-32)
- evidence/analysis/08-flow-design.md § 3.11 Reference data — `GET /banks?country_code=XX` (the unversioned shape was hidden in the markdown render; Reference layer exposes it)
**Related GAP(s):** GAP-32 (api-reference-coverage); inherits GAP-01 (no path-level version recovery); compounds with GAP-20 (ISO 3166 alpha-2 vs alpha-3 inconsistency on this same endpoint)
**README top-5 candidate?** **MAYBE** — fights with Finding #5 for the bottom slot. Wins if Wallets turns out to exist undocumented (then Wallets demotes to MEDIUM and `/banks` takes its slot). Loses if Phase 2 Quotations probe reveals an even more egregious docs↔runtime drift.
**Phase 2/3 probe needed?** YES — Data Engineer: hit `https://api.balampay.com/sandbox/v1/banks?country_code=MX` and `https://api.balampay.com/sandbox/banks?country_code=MX`. If both work → unversioned shadow surface (potential API9). If only `/banks` works → confirm the docs-runtime gap is real, not a docs-only finding.

---

## Finding #7 — Reference pages strip response JSON behind "Click Try It!" — integrator cannot see response shapes without authenticating

**Severity:** HIGH
**Pillar:** Documentation Quality (completeness — examples that actually run) / Ease of Connection (time-to-first-call)
**Category:** docs gap
**Why this matters to a client:** All 14 fetched Reference pages — including the integrator's first stop, `POST /auth` — render *"Click Try It! to see the response here!"* instead of a static 2xx JSON body. A copy-paste integrator reading `/reference/post_auth` does not learn that the response is wrapped in `{message, data: {access_token, expires_in: 3600, token_type: "Bearer"}}` — they have to log in to ReadMe.io, click the Try It widget, and submit real sandbox credentials to see the shape. This inflates time-to-first-call from minutes to hours and makes the docs unusable from offline LLM context (a real workflow for the Banco Industrial / N1co engineering teams who restrict outbound traffic). The Guides hint at response shapes; the Reference — which should be the canonical contract — does not.
**Evidence:**
- evidence/analysis/12-api-reference-coverage.md § TL;DR (#1) → "Every single reference page hides its response body behind a 'Click Try It!' placeholder. No verbatim 2xx JSON is rendered statically on any of 14 pages — including POST /auth."
- evidence/analysis/12-api-reference-coverage.md § F-REF-1 — Response examples missing on EVERY reference page (GAP-30)
- evidence/analysis/12-api-reference-coverage.md § Family 1 — Authentication → "No verbatim response JSON. The 200 success body shape... documented in flow-design §2.1 is not visible on the reference page."
**Related GAP(s):** GAP-30 (api-reference-coverage)
**README top-5 candidate?** **MAYBE** — strong but slightly cosmetic. If Phase 2 produces an obvious "Reference says A, runtime returns B" drift, this becomes the foundation for that finding and gets promoted. If Phase 2 produces no surprises on this front, it stays at HIGH but may not crack top-5.
**Phase 2/3 probe needed?** Soft — Data Engineer should diff one or two real runtime responses against any docs claim (Guides hint or Reference Try-It output) to anchor this. The finding is real today; Phase 2 sharpens it.

---

## Finding #8 — Reference pages stale relative to Apr-14 changelog (`createvirtualaccount` missing ~60% of body fields; `createuser` hides `type: "business"`; Quotations Reference doesn't list stablecoin base currencies)

**Severity:** HIGH
**Pillar:** Documentation Quality (accuracy) / Docs↔Runtime Congruence
**Category:** docs gap / changelog desync
**Why this matters to a client:** The Reference page is supposed to be the canonical contract — but the Apr-14 changelog added structural features (the `provider` alias replacing `bank`, the `mode: CRYPTO` field on VA create, stablecoin `base_currency: USDC|USDT` on quotations, idempotency-key on liquidation-address) that the Reference pages do not show. `createvirtualaccount` Reference renders only `{user_id, type, bank}` while runtime accepts at least 8 documented fields per the same changelog. `createuser` Reference shows `type` as `["individual"]` only — the entire `business` half of the product (a target customer per the matrix) is invisible at the Reference layer. The result: an integrator implementing against the Reference misses 60% of the supported surface, including the only path to crypto-mode VAs. Changelog and Reference are not co-authored; the integrator has to read the changelog *and* the Reference *and* the Guides to assemble the contract.
**Evidence:**
- evidence/analysis/12-api-reference-coverage.md § Family 4 — Virtual Accounts → "createvirtualaccount body fields visible on Reference: ONLY user_id, type, bank. The provider, mode, destination.{currency, network, address}, markup.{fx_bps, fee_bps} fields that flow-design §3.4 catalogued are NOT VISIBLE on the Reference page."
- evidence/analysis/12-api-reference-coverage.md § Family 2 — Users → "createuser body schema is partial. The page lists `type` as enum with only 'individual' shown — no 'business' value rendered despite flow-design and the Guides making this central."
- evidence/analysis/12-api-reference-coverage.md § F-REF-4 — Reference pages stale relative to Apr-14 changelog (GAP-34)
- evidence/analysis/12-api-reference-coverage.md § Family 5 — Quotations → "wallet_token: USDC, USDT (no COPm despite recipient enum supporting it)"; stablecoin base from Apr-14 changelog not listed
**Related GAP(s):** GAP-34 (changelog desync); compounds GAP-31 (Quotations) and GAP-14 (dual enum); related to GAP-04 (Reference omits Bearer header on 5 of 14 pages)
**README top-5 candidate?** **MAYBE** — overlaps with Finding #1 (Quotations) and the meta-finding about Reference layer being broken. Probably folded into a "Reference-layer is structurally incomplete" headline if it makes top-5.
**Phase 2/3 probe needed?** YES — Data Engineer: send `POST /v1/virtual-accounts` with the *full* changelog-promised body (provider, mode, destination, markup); capture which fields are honored vs silently dropped. Same probe for `POST /v1/users` with `type: "business"`. Empirical evidence that the Reference is the wrong source of truth.

---

## Finding #9 — Error-handling guide documents ~6 codes; runtime has 12+ codes across 4 envelope shapes

**Severity:** HIGH
**Pillar:** Documentation Quality (completeness)
**Category:** docs gap / error inventory
**Why this matters to a client:** The dedicated `/docs/error-handling` page is the integrator's go-to reference when an unexpected response lands in prod. It catalogues `200/201/400/401/404/409/500` and codes `validation_error`, `unauthorized`, `not_found`, `idempotency_key_reused`, `internal_error`, `invalid_type` — about 6 codes. The actual runtime inventory (per flow-design §2.3 and the Reference pages) carries at least: `forbidden`, `resource_conflict`, `rate_limit_exceeded`, `invalid_operation`, `invalid_user_id`, `idempotency_conflict`, plus the entire Shape-B family (`USER_NOT_FOUND`, `PAYOUT_ACCESS_DENIED`, `INVALID_BANK_CODE`, `FEES_EXCEED_AMOUNT`, `QUOTE_INVALID_STATE`, `CURRENCY_PAIR_NOT_ENABLED`, `IDEMPOTENCY_CONFLICT`, `INVALID_CALCULATED_AMOUNT`, `AUTHENTICATION_ERROR`). The dedicated page misses ~80% of the real inventory. There is no `422` documented despite `/auth` returning it. There is no `429` documented despite the auth guide stating a 10rps cap exists. **Self-contradicting twist:** the page tells support to "include Request ID (if available)" — but the API never returns a request_id in any response (GAP-06).
**Evidence:**
- evidence/analysis/11-docs-coverage-matrix.md § Section 9 — Error Handling → "Page lists 7 status codes; flow-design §2.3 catalogues 12+ error codes... The dedicated guide misses ~80% of the inventory. Severity: HIGH for Pillar 1 (Completeness)."
- evidence/analysis/11-docs-coverage-matrix.md § Section 9 (PM block) → "request_id is referenced in the support contact ('Request ID (if available)') but is nowhere documented to be returned by the API"
- evidence/analysis/08-flow-design.md § 2.3 Error envelope — full list of codes in Shapes A and B
- evidence/analysis/08-flow-design.md § 6 — GAP-06 (No request-id / correlation-id — HIGH)
- evidence/analysis/12-api-reference-coverage.md § F-REF-8 — Status code coverage is uneven and inconsistent across pages (matrix included)
**Related GAP(s):** GAP-05 (envelope inconsistency — Finding #3); GAP-06 (no request-id); GAP-08 (idempotency endpoint list inconsistent — see also Finding #11)
**README top-5 candidate?** **MAYBE** — bundle candidate. If we ship a "docs are incomplete" finding, this is one anchor; if we ship a "error UX is broken" finding, this is the second anchor (alongside Finding #3 envelope inconsistency). On its own, it's a HIGH that may not crack top-5 against the four CRITICALs above.
**Phase 2/3 probe needed?** YES — Data Engineer: build empirical error-code matrix by triggering each documented code path; cross-reference against the published `/docs/error-handling` list. The gap is the finding.

---

## Finding #10 — `POST /v1/users` Reference page omits the `Authorization: Bearer` header — literal copy-paste integrators get 401 on Day 1

**Severity:** HIGH
**Pillar:** Ease of Connection (first-call success rate) / Documentation Quality (accuracy)
**Category:** docs gap / auth contract
**Why this matters to a client:** The very first non-`/auth` call any integrator makes is `POST /v1/users`. The `/reference/createuser` page lists only `x-api-key` and `idempotency-key` as required headers. Bearer is invisible. A literal copy-paste integrator submits the body, omits `Authorization: Bearer ...`, and receives a 401 with the bare-`message` Shape-D body (no `code`, see Finding #3). They cannot tell whether their token was wrong, their API key was wrong, or the body was malformed — because the docs page told them there was no token to send. This is the worst possible first-impression: the docs are confidently wrong on the most-trafficked endpoint. The same omission repeats on `listusers`, `getuser`, `createvirtualaccount`, `/v1/countries` — **5 of 14 Reference pages drop the Bearer header from their headers section**. Sharpens GAP-04 (the auth-model contradiction) from a Reference-content-correctness angle.
**Evidence:**
- evidence/analysis/12-api-reference-coverage.md § Family 2 — Users → "createuser Required Headers (per the Reference page itself): x-api-key (string, required) + idempotency-key (uuid, required). Authorization: Bearer is NOT listed on the page. This contradicts global auth doc and contradicts even flow-design §2.2 which says it's required. Same omission on listusers and getuser — only x-api-key shown."
- evidence/analysis/12-api-reference-coverage.md § Family 1 — Authentication → "Reference page provides NO authentication note. Doesn't list x-api-key requirement... An integrator reading just this page would conclude /auth requires no headers."
- evidence/analysis/12-api-reference-coverage.md § F-REF-7 — Reference page omits `Authorization: Bearer` header on most endpoints
- evidence/analysis/08-flow-design.md § 6 — GAP-04 ("Bearer OR API key" vs "both required" — HIGH)
**Related GAP(s):** GAP-04 (auth contract contradictory); compounds with GAP-30 (no response JSON to even see a 401 body)
**README top-5 candidate?** **MAYBE** — strong day-1 pain finding. Wins a slot if we frame the top-5 around "every integrator's first hour is broken"; loses to the four CRITICALs otherwise.
**Phase 2/3 probe needed?** Data Engineer (Phase 2 mandatory probe): submit `POST /v1/users` with only `x-api-key`, only `Authorization`, both, neither — capture the 4-way table. This is the empirical proof of GAP-04 + this finding combined.

---

## Finding #11 — ISO 3166 alpha-2 vs alpha-3 inconsistency: `/banks` and recipient.country fields demand alpha-2, but `user.address_country` and `user.nationality` demand alpha-3

**Severity:** HIGH
**Pillar:** Docs↔Runtime Congruence
**Category:** schema drift / silent breakage
**Why this matters to a client:** Country codes appear at half a dozen places in the API: `GET /banks?country_code=`, `recipient.account.country`, `recipient.bank_address.country`, `user.address_country`, `user.nationality`, `recipient.doc_country_code`. Some demand `MX`/`CO`/`US` (ISO 3166-1 alpha-2); others demand `MEX`/`COL`/`USA` (alpha-3). The two are visually similar enough that an integrator who normalizes on one (a sensible engineering choice) will get 404s from `/banks` (alpha-3 not accepted) **or** silent revalidation failures from user creation (alpha-2 silently rejected). The Reference page for `/banks` does not state which it accepts — it just says `country_code: string, required`. This is exactly the silent-breakage class the PM rubric prioritizes: docs do not flag the convention divergence, and an integrator discovers it in prod when a recipient creation 400s while user creation just succeeded.
**Evidence:**
- evidence/analysis/08-flow-design.md § 3.11 Reference data → "Uses ISO 3166-1 alpha-2 (CO, MX, US) while everything else in the platform uses alpha-3 (COL, MEX, USA). → GAP-20."
- evidence/analysis/08-flow-design.md § 6 — GAP-20 (ISO 3166 alpha-2 vs alpha-3 inconsistency — HIGH)
- evidence/analysis/12-api-reference-coverage.md § Family 8 — Reference Data → "`GET /banks` country_code format: Reference page does NOT state alpha-2 vs alpha-3 — just says 'string, required'. GAP-20 from flow-design is therefore unfixable from the Reference page alone."
**Related GAP(s):** GAP-20 (ISO 3166 inconsistency); compounds Finding #6 (`/banks` unversioned) since both findings hit the same endpoint
**README top-5 candidate?** **MAYBE** — pairs naturally with Finding #6 as a "`/banks` is a minefield" combined finding. Standalone HIGH if Phase 2 confirms a recipient-creation 400 from alpha-3 mismatch.
**Phase 2/3 probe needed?** YES — Data Engineer: send `GET /banks?country_code=MX`, `MEX`, `mx`, `Mexico`, omitted. Send recipient creates with each country variant. Build the empirical accept/reject matrix.

---

## Devil-Advocate Notes That Survived to the Final Cut

The PM draft initially carried 14 candidates. Devil-advocate review trimmed to 11. Rationale:

- **Demoted product-comparison matrix overclaims** ("Embedded ✅" on 5/5 products; "KYC: Not Required" on Payouts despite source VA requiring KYC; 50k vs 90k retail-location contradiction) **from HIGH (PM draft) → not in final cut as a standalone finding.** A real integrator reads past the matrix into the deep pages; the matrix overclaims hurt sales/buyer perception, not the engineer's day-1 integration time. They live in `product-catalog.md` as evidence and resurface only via the dead-link pattern (Finding #2). Reason: the grading rubric prioritizes integrator pain, not buyer-perception drift, and Phase 1's bias should be toward findings an engineer can fix.
- **Demoted "OTP endpoint `/verification/send` named in payouts guide but no Reference page" (GAP-23) from HIGH → dropped from final cut.** Only affects opt-in fiat-payout OTP, which is risk-gated. An integrator never hits this on the happy path. Kept in flow-design.md as a GAP; not surfaced here because it's a narrower pain than the 11 finalists.
- **Dropped "Code-sample languages limited to Shell/Node/Ruby/PHP/Python"** despite F-REF-5 flagging it as a Pillar-2 ease-of-connection finding. Buyers can use Postman/curl; the LATAM-bank-Java argument is real but doesn't pass the "engineer-can-fix-without-a-DM" test — they can ask for a Java sample. Kept as a future enhancement note, not a top-5 candidate.
- **Dropped "Recent Requests panel post-login telemetry leakage" (F-REF-9).** Severity is UNVERIFIED in the source artifact — pending an authorized probe. Including an unprobed CRITICAL is exactly the inflation the devil-advocate persona is meant to prevent. Moved entirely to the Phase 3 security-harness work.
- **Promoted Finding #1 (Quotations schema drift, GAP-31) above GAP-01 (versioning).** Both are CRITICAL; the impact difference is that GAP-01 affects long-term contract pinning (a deal-blocker) while GAP-31 affects whether the *current* integration works at all (a build-blocker). The build-blocker hurts more during a 2-week PM evaluation cycle, so it ranks #1.
- **Bundled the 3 sidebar 404s into one finding (Finding #2)** rather than splitting versioning, metadata, and api-upgrades into three. The headline ("23% dead-link rate") only lands when they're grouped — splitting dilutes the pattern claim, which is what makes this a CRITICAL.
- **Kept Finding #4 (webhook contract) at CRITICAL despite some review pressure to demote.** The push-back: "an integrator can fall back to polling." Counter-push that survived: every Phase 2 recipe (A, B, C, D, E in flow-design §4) depends on webhooks for state transitions, and the docs *recommend* webhooks over polling. Falling back to polling means re-architecting the integration. CRITICAL holds.
- **Kept Finding #7 (response JSON hidden) at HIGH despite "cosmetic" pressure.** The push-back: "every Reference page hides the response shape" — for `/auth`, that means the first endpoint's contract is invisible without authenticating. HIGH holds, top-5 maybe.
- **Kept Finding #11 (ISO 3166) at HIGH instead of MEDIUM.** Silent breakage in prod beats annoying-but-loud breakage at integration time per the PM persona's bias. Promoted from MEDIUM (architect's initial severity in flow-design §6 GAP-20) to HIGH based on integrator-impact framing.

---

## README Top-5 Candidates from Phase 1

| Rank candidate | Finding # | Why this would win a top-5 slot |
|---|---|---|
| 1 | #1 — Quotations Reference vs Guides disjoint schemas | The only docs gap that *directly* blocks the most-important integration recipe (fiat payout) until empirically resolved. Highest specificity, highest integrator-pain dollar cost, narrowest fix surface (one endpoint, two docs pages disagree). |
| 2 | #2 — 3 sidebar entries 404 (23% dead-link rate) | Pattern-level finding that pulls versioning (GAP-01), metadata (no reconciliation key), and api-upgrades (no deprecation policy) into one headline. Sales-blocker for enterprise contracts. |
| 3 | #3 — Four coexisting error envelope shapes | The classic Pillar-4 hardening finding: every integrator writes one error handler; Kira forces four. CRITICAL on Day 1, gets worse in prod. |
| 4 | #4 — Webhook delivery contract absent + `secret` documented as optional | The most-security-sensitive endpoint with the least documentation. Compounds across all 5 recipes. |
| 5 (contested) | #5 — Wallets marketed without Reference page, **or** #10 — `createuser` omits Bearer header, **or** #6 — `/banks` unversioned | All three are HIGH. Choice depends on which Phase 2 probe lands first. Wallets wins if Phase 2 confirms the endpoint is genuinely missing (deal-stage trust hit); `createuser`-Bearer wins if Phase 2 confirms a 401 on copy-paste (day-1 friction); `/banks`-unversioned wins if Phase 2 reveals a runtime `/v1/banks` 404 (the slow-rolling codegen breakage). |

**Honest read on slots 6-11:** Findings #6, #7, #8, #9, #10, #11 are all real HIGH-severity docs-quality issues, but they would only enter the final README top-5 if Phase 2 produces no stronger empirical findings. Realistically the README top-5 will mix 2-3 Phase 1 findings with 2-3 Phase 2/3 findings (e.g., a latency surprise, a webhook spoofing exploit, a state-machine race). Phase 1's contribution should be the *cross-cutting* docs gaps (#1 - #4) that no amount of empirical probing will move; the remaining slots go to Phase 2/3 surprises.

---

## Phase 1 → Phase 2 Handoff

What Phase 2 (Data Engineer) needs to probe empirically to either confirm or undercut these Phase 1 findings:

- **Finding #1 (Quotations schema drift)** → Send `POST /v1/quotations` with `{base_currency: USD, quote_currency: MXN, amount: 1000}` and with `{account_type: SPEI, amount: 1000, recipient_id: ...}` in parallel. Capture which returns 200. The winner is the real schema; the other docs page is the fix surface. Capture which `account_type` values the Reference-documented schema accepts (LATAM types are not listed — SPEI/PSE/BRL/etc. probe).
- **Finding #2 (sidebar 404s + versioning)** → Send `X-Api-Version: 2025-01-01` vs `2026-04-14` vs omitted vs `garbage` to two endpoints that changed in the Apr-14 changelog (`POST /v1/users` and `POST /v1/virtual-accounts`). Diff response schemas. This empirically confirms whether un-versioned clients are silently on the old schema.
- **Finding #3 (4 error envelopes)** → Trigger one error of each shape: 401 expired token (Shape D), 400 validation on createuser (Shape A), 422 malformed UUID on `/auth` (Shape C), 409 idempotency conflict on `POST /v1/recipients` (Shape B). Capture raw bodies in `evidence/work/error-envelopes/{NN}-{shape}.json`. Confirm the four-shape inventory and look for a fifth on `/webhooks/register` (Shape E candidate — bare 200 no body).
- **Finding #4 (webhook contract)** → Phase 3 security harness mandatory. Register with `secret: ""`, `secret: null`, omitted. Capture whether signed deliveries still arrive. Probe whether a `client_uuid` other than the API-key owner is accepted. Probe whether the signature is hex or base64 by decoding one real delivery and verifying both ways.
- **Finding #5 (Wallets no Reference)** → Probe `POST /v1/users/{id}/wallets`, `GET /v1/users/{id}/wallets`, `GET /v1/wallets`, `GET /v1/wallets/{id}`. If any 2xx → endpoint exists undocumented (severity stays HIGH but pivots to "documented field hidden" framing). If all 4xx/404 → product is marketing fiction; promote to CRITICAL.
- **Finding #6 (`/banks` unversioned)** → Hit both `/sandbox/banks?country_code=MX` and `/sandbox/v1/banks?country_code=MX`. Capture which 200s. Also probe `/sandbox/users`, `/sandbox/virtual-accounts`, `/sandbox/payouts` without `/v1/` — if any 2xx, unversioned shadow surface (API9 inventory finding).
- **Finding #7 (response JSON hidden)** → No empirical probe needed; the finding is purely a docs-completeness gap. Sharpens via any Phase 2 capture that shows runtime returns a field not visible at the Reference layer.
- **Finding #8 (Reference stale vs changelog)** → Send `POST /v1/virtual-accounts` with the full Apr-14-changelog body (`provider`, `mode: CRYPTO`, `destination.{}`, `markup.{}`). Capture which fields are honored, which are dropped, which 400. Send `POST /v1/users` with `type: "business"` to confirm the business half exists at runtime despite being absent from the Reference page.
- **Finding #9 (error-handling page incomplete)** → Catalogue every error code observed during Phase 2 integration. Compare against the `/docs/error-handling` published list. The delta is the finding.
- **Finding #10 (`createuser` Bearer omission)** → Submit `POST /v1/users` with each auth-header permutation (x-api-key only / Bearer only / both / neither). Capture the 4-way table; confirm the docs-runtime gap from a copy-paste integrator's exact path.
- **Finding #11 (ISO 3166 alpha-2 vs alpha-3)** → Send `GET /banks?country_code=` with `MX`, `MEX`, `mx`, `Mexico`, omitted. Send recipient creates with each country variant in each country field. Build the alpha-2 vs alpha-3 acceptance matrix per field — this is the silent-breakage proof.

**Cross-artifact reconciliation (DEC-005, RESOLVED 2026-05-27):** GAP-NN numbering collisions across `docs-coverage-matrix.md`, `api-reference-coverage.md`, and `product-catalog.md` have been reconciled by the data-architect into `flow-design.md` § 6 as canonical authority. Final assignments: `api-reference-coverage.md` GAP-29..GAP-34 stay canonical (zero churn); `docs-coverage-matrix.md`'s proposed GAP-29 (api-upgrades) → canonical **GAP-35**; `docs-coverage-matrix.md`'s proposed GAP-30 (metadata) → canonical **GAP-36**; `product-catalog.md`'s proposed GAP-31 (Wallets) → canonical **GAP-37**. See `flow-design.md` § 6 "Renumbering reconciliation (DEC-005, 2026-05-27)" for the full table. From this DEC forward, only the data-architect assigns new GAP-NN numbers.

---

## Postscript — Partner-Doc Delta Analysis Impact (added 2026-05-28, DEC-008)

After the two partner-distributed Word docs (`kira-sandbox-integration-guide.docx`, `kira-prod-certification-matrix.docx`) became available, the Phase 1 findings above were reclassified against them. Full reclassification in `evidence/analysis/13-docs-vs-partner-guide-delta.md`. The headline impact:

- **A new META-finding supersedes most of the Phase 1 docs-quality top-5 candidates.** The headline isn't "Kira's API is broken" — it's "Kira's public docs are the broken layer; the real contract is partner-distributed." This meta-finding subsumes Phase 1 Findings #2 (sidebar 404s), #7 (response JSON hidden), #8 (Reference stale), #9 (error-handling incomplete), and #10 (Bearer omission). All five remain real public-doc gaps; they collapse into one pattern. The META-finding sits at README slot #1. Tracked as new test-matrix row **T-P1-META-01** (CRITICAL).

- **Finding #1 (Quotations Reference vs Guides schema drift)** — partner guide does not fix this directly; the v2026-XX-XX primitive renames (Quote/Transfer/Route) plus the canonical Postman collection (L139-149) imply normalization. **Severity DOWNGRADED CRITICAL → HIGH** for partner-side cost; public-doc severity stays CRITICAL since the public Reference is still wrong. Slot in README top-5 ceded to security findings + META; falls to Honorable Mentions.

- **Finding #2 (sidebar 404s, versioning, metadata, api-upgrades)** — partner guide fills the versioning gap (L14-15: explicit `POST /v1/versioning/upgrade` pin spec). Public-doc sidebar 404s stand. **Reframed as evidence for the META-finding** rather than a standalone top-5 candidate.

- **Finding #3 (Four error envelope shapes)** — partner guide acknowledges + ships fix (L122-124 + L135 unified `{type, code, message, param, agent_hint}` shape in v2026-XX-XX). **Severity DOWNGRADED CRITICAL → HIGH.** Falls out of README top-5.

- **Finding #4 (Webhook contract underspecified)** — partner guide concedes no CRUD, no retry policy (8-attempt backoff in v2026-XX-XX, L132), and introduces the new `kira-signature: t=,v1=` format. Public-doc severity stays CRITICAL. **Replaced in README top-5 by the broader webhook triple-vector finding** (SSRF + cross-tenant `client_uuid` + optional secret + cleartext URL + opaque response, slot #2), which folds in the contract gap and the Phase 3 security findings.

- **Finding #5 (Wallets product without Reference page)** — partner guide's "What you CAN do" list (L84-95) does NOT include Wallets, and the "What's shipping end of June" list (L125-138) does not mention Wallets. **Inverse-invalidation:** the partner-doc omission independently confirms the product is absent from the v2026-04-14 surface, not just from the Reference layer. **Reframed** from "docs gap" to "product-truth gap" — the marketing matrix claim doesn't match the product as shipped. Severity HIGH holds (matrix row T-P1-005 annotated).

- **Findings #6 / #7 / #8 / #9 / #10 / #11** — partner guide acknowledges most of the underlying drifts. Public-doc severity holds; partner-side severity drops. These all reframe as evidence of the META-finding pattern (public docs are not the source of truth). No standalone top-5 slots.

**Net effect on README top-5:** the four Phase 1 CRITICALs collapse into the META-finding (slot #1). The remaining four top-5 slots go to Phase 3 security/abuse findings (SSRF triple-vector, PII unmasked, TLS 1.0/1.1) and to a compound DRIFT-1 finding (sandbox base URL wrong in BOTH docs). The Phase 1 individual findings live on as cited evidence of the META-finding pattern. See `README.md` for the published top-5.
