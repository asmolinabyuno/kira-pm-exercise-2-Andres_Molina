# API Reference Coverage — Kira `/reference/*` Sweep (8 families)

> **Lens:** This sweep walks the **API Reference** sidebar (not Guides). The Reference layout exposes things Guides hides: code samples per language, parameter tables with regex/enum constraints, Try It widget, Recent Requests panel, response examples, per-endpoint auth notes. Companion docs: `evidence/analysis/08-flow-design.md` (30-endpoint catalog + 28 GAPs), `evidence/analysis/11-docs-coverage-matrix.md` (Guides sweep), `evidence/analysis/10-product-catalog.md` (product-vs-API mismatches).
> **Sweep date:** 2026-05-27.
> **Pages fetched:** 14 of ~30 reference pages (sampling strategy below). Two `/reference/post_v1-quotations` and `/reference/createquotation` 404'd at first; the latter was reachable under `/v2026-04-14/reference/createquotation`. The fact that the canonical URL slug doesn't resolve is itself a Reference-layer finding (GAP-29 candidate).
> **Sampling strategy:** For each of the 8 families, fetch ≥1 CREATE/write + ≥1 LIST endpoint. Auth, Webhooks, Quotations, Payment Link, Reference-Data are single representative pages. GET-detail endpoints sampled out unless they expose canonical response schema (getuser kept). Total = 14.

---

## TL;DR — what the Reference layer uniquely revealed

1. **Every single reference page hides its response body behind a "Click Try It!" placeholder.** No verbatim 2xx JSON is rendered statically on any of 14 pages — including `POST /auth`. An integrator reading docs without clicking Try It cannot see what shape comes back. This is a **catastrophic Pillar-1 documentation-quality gap that flow-design.md cannot capture** (because flow-design was built from `*.md` flavors which the Guides crawler synthesised). The HTML reference is materially less complete than the markdown crawler suggests. → **GAP-30 (new)**.
2. **Quotations Reference page (`createquotation`) documents a different schema than the Guides describe.** Reference shows `account_type`/`wallet_network`/`wallet_token`/`inverse_calculation`. Guides describe `base_currency`/`quote_currency`/`amount`/`amount_in_destination`. Same endpoint, two completely disjoint field sets. → **GAP-31 (new)**.
3. **`GET /banks` has NO `/v1/` prefix** — the full URL on the reference page is `https://api.balampay.com/sandbox/banks`, while every other endpoint is `/v1/...`. This isn't in flow-design's appendix; the path-inconsistency was hidden inside the markdown render. → **GAP-32 (new)**.
4. **Code-sample languages: every page offers ONLY Shell/Node/Ruby/PHP/Python**. Absent: Go, Java, Kotlin, C#, .NET, TypeScript, Swift, Rust. For a B2B fintech selling to banks (Banco Industrial, N1co), the absence of Java/Kotlin/.NET is a Pillar-2 ease-of-connection gap visible only at the Reference layer.
5. **Status-code coverage is uneven**. 429, 503, 403, 422 are missing from most pages. `POST /auth` documents only `200/403/422/500`. List endpoints document only `200/400/401/500`. `POST /webhooks/register` documents **zero error codes** statically. → enlarges GAP-05.
6. **`POST /webhooks/register` reference page has no documented error codes, no auth section, no body validation rules, no signature header spec**. SSRF rejection (localhost, 169.254.169.254, private IPs) is completely unmentioned. The widget is live (clicking Try It is a potential SSRF probe). → fuels GAP-11 / GAP-04 / new security findings.
7. **Recent Requests panel** on every page is gated: "Log in to see full request history." So Reference-level telemetry leakage is *not* visible to anonymous integrators — but **if Kira authenticated buyers see other tenants' recent requests via this panel, it's an OWASP API3 (BOLA at the docs layer)**. Probe explicitly.
8. **"Try It" widget for `POST /v1/virtual-accounts/{id}/payout` is identical to other Try It widgets** — no guardrail messaging, no "this will move sandbox money" warning. A copy-paste reviewer could click Try It and initiate a real sandbox payout against the demo credentials (if pre-filled).

---

## Family 1 — Authentication
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/post_auth`
**Pages NOT fetched (sampled out):** None — single-endpoint family.

**Reference-page surface highlights (what only the Reference exposes):**
- **Code-sample languages:** Shell, Node, Ruby, PHP, Python. NO Go/Java/Kotlin/.NET/TypeScript.
- **Recent Requests panel:** Present, gated to logged-in users. Anonymous integrators see "Log in to see full request history" — anonymous leakage = none observed.
- **Try It widget:** Present; would presumably need the user's actual `client_id` + `password`. No warning about credential persistence between visits, no documented session model for whether a previous user's credentials remain in the form.
- **Cross-page schema drift:** None within this family (one endpoint).
- **Per-page auth note vs global:** Reference page provides NO authentication note. Doesn't list `x-api-key` requirement (which flow-design §2.2 says is required even for `/auth`). The page documents `client_id` and `password` body fields only — no header schema. **An integrator reading just this page would conclude `/auth` requires no headers.**
- **Status codes documented:** `200, 403, 422, 500`. **Missing:** `400, 401, 429, 503`. Notably no `401` for /auth (curious — that's the natural response to bad credentials) and no `429` rate-limit code despite the auth guide stating a global rate limit applies.
- **No verbatim response JSON.** The 200 success body shape (`{message, data: {access_token, expires_in, token_type}}`) documented in flow-design §2.1 is **not visible on the reference page**.

### Per-agent contributions (net-new probes / findings)

**`product-manager`**
- The Reference page for `/auth` does not specify `x-api-key` in the header table; an integrator following the Reference alone (without reading the Guides) will get `401`. Pillar-1 docs-quality finding: **the Reference page is incomplete on the very first endpoint an integrator calls**.
- The Try It widget on `/auth` would receive plaintext `password` field — if Kira's docs portal isn't itself TLS-strict (HSTS, no mixed content), a careless integrator could leak the password through browser history or a logged man-in-the-middle.

**`data-engineer`**
- Probe `POST /auth` with `Accept: application/xml` and `Accept: text/plain` — the Reference page says nothing about supported response content types; expect `200` JSON regardless, OR a `406 Not Acceptable` (currently undocumented).
- Probe `POST /auth` with missing `x-api-key` to confirm whether the Reference page's omission means the header is actually optional, or whether the docs are simply incomplete.

**`api-security-auditor`**
- **API2:2023 user-enum via /auth:** the only documented `403` body is `{"message":"Forbidden"}` with no `code` field. Probe: send `client_id=<valid>` + `password=<wrong>` vs `client_id=<garbage>` + `password=<garbage>` — if response *timing* or *message* differs, that's user enumeration.
- **API4:2023 unrestricted resource consumption:** Reference page does NOT document a `429` code. Probe: hit `POST /auth` 100x/s for 30 seconds. Does the global 10rps cap apply, or is `/auth` exempt? If exempt → credential stuffing is wide open.
- **Reference page does not say `Cache-Control: no-store`** is set on the auth response. Probe response headers — JWT cached at any intermediary is a CWE-525 finding.

**`devil-advocate`**
- The Reference page for `/auth` is the integrator's first impression. If it doesn't even list `x-api-key` and doesn't show the response JSON, severity of GAP-30 (response examples missing across Reference) should ride at **HIGH not MEDIUM**. Re-rank.

---

## Family 2 — Users
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/createuser`, `https://kira-financial-ai.readme.io/reference/listusers`, `https://kira-financial-ai.readme.io/reference/getuser`
**Pages NOT fetched (sampled out):** `updateuser`, `createverification` — GAP-14 (dual enum) already captured; PUT path shape is uniform.

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5 (Shell/Node/Ruby/PHP/Python) on all three pages.
- **`createuser` Required Headers (per the Reference page itself):** `x-api-key` (string, required) + `idempotency-key` (uuid, required). **`Authorization: Bearer` is NOT listed on the page.** This contradicts global auth doc and contradicts even flow-design §2.2 which says it's required. Same omission on `listusers` and `getuser` — only `x-api-key` shown. This is a **systemic reference-page omission of the Bearer header** that materially affects every integrator.
- **`createuser` body schema is partial.** The page lists `type` as enum with **only `"individual"` shown — no `"business"` value rendered** despite flow-design and the Guides making this central. An integrator on the Reference alone would never know business onboarding exists. This is **Reference-vs-Guides taxonomy drift** that flow-design didn't catch.
- **`createuser` enums newly exposed in Reference (not in flow-design):**
  - `source_of_funds`: 19 values (salary, self_employment_income, investment_proceeds, …)
  - `account_purpose`: 18 values (manage_personal_funds, receive_payments, …)
  - `expected_monthly_payments`: 4 banded buckets (`0_4999`, `5000_9999`, `10000_49999`, `50000_plus`) — **note the underscore separator, not the conventional `-`. Easy typo source.**
  - `gender`: `male|female|other` (BUT no `prefer_not_to_say` or `null` — fails most modern KYC compliance frameworks)
  - `immigration_status`: literal-string values with spaces and capitalisation: `"Permanent U.S. Resident"`, `"Non-Permanent U.S. Resident"`, `"Non-Resident of U.S."`. **These are display strings used as enum values.** Devastatingly bad for type-safe codegen — extends GAP-17 (Spanish-string enums) from recipients into users.
- **`listusers` query parameter `verification_status` enum** shows only `UNVERIFIEDVERIFIED` (two values) — but `createuser` exposes `status` with `CREATEDVERIFYINGVERIFIEDREJECTEDREVIEWACTIVEINACTIVESUSPENDED` (8 values). Same field name, two filterable enum sets, two reference pages disagree. **Reinforces GAP-14 from a Reference-only angle.**
- **Try It widget on `createuser`** would post a full KYB payload to sandbox — if the page form prefills with someone else's test data (a known ReadMe.io pattern via cookie persistence), that's data leakage across docs visitors.
- **Recent Requests panel:** Gated. Cannot anonymous-probe.
- **Status codes documented:** `createuser`: `201/400/401/409/500`. `listusers`: `200/400/401/500`. `getuser`: `200/400/401/404/500`. **403, 422, 429, 503 missing across all three.**
- **`createuser` 422 absent** — but the user body has Pydantic-style validation per `/auth` (`{error, details:[{loc, msg, code}]}`). Either the page is wrong (422 IS returned in reality) or the runtime contract is silently 400. Probe.
- **No cross-references** to `/v1/users/{id}/verifications` (legacy verification) or to `POST /v1/virtual-accounts` (the next step in the happy path). Reference layout breaks the happy-path chain.

### Per-agent contributions

**`product-manager`**
- Pillar-1 finding: `createuser` Reference page documents `type` enum as `["individual"]` only — the `business` half of the product line is **invisible at the Reference layer**. Integrators reading only `/reference/createuser` cannot discover business onboarding. Sharpen this against the marketing claim of "Wallets · Payment Link · Virtual Account · cashPay · Payout API" (product-catalog) where business is a target customer.
- Time-to-first-call: the missing `Authorization: Bearer` header on the createuser Reference page means a literal copy-paste integrator gets `401`. The expected vs observed gap (Reference says "x-api-key only" — runtime requires both) is a first-call-failure pattern.

**`data-architect`**
- The two `status`-enum sources (`createuser` modern set vs `listusers` `verification_status` two-value set) need a state-machine reconciliation entry under §3.3 of flow-design. Add **GAP-14a** sub-gap: list-endpoint filter exposes a *different* enum than the resource model. An integrator filtering by `verification_status=verified` against the `createuser`-documented enum will hit a 400 because the listusers filter doesn't accept `VERIFIED` (uppercase) — only `UNVERIFIED|VERIFIED` per the listusers page.

**`data-engineer`**
- Fuzz `expected_monthly_payments` against the buckets `"0_4999"`, `"5000_9999"`, `"10000_49999"`, `"50000_plus"` PLUS mutations: `"0-4999"` (hyphen), `"0_4999_"` (trailing), `"50000+"` (plus sign), `null`, omitted. Assert which return 400 vs 422 vs silent acceptance.
- Probe `immigration_status` enum case sensitivity: send `"permanent u.s. resident"` (lowercased) vs `"Permanent US Resident"` (no periods) — both should reject; if either accepts, it's case-insensitive enum matching (potential bypass vector if any consumer of this field downstream depends on exact strings).
- Probe `gender` enum: send `"non-binary"`, `"prefer_not_to_say"`, `""` (empty), `null`. Document the 4-row table.

**`qa-engineer`**
- Schemathesis-fuzz `POST /v1/users` against the **createuser Reference page's published schema only** (ignoring Guides). Capture the responses where required fields differ from runtime — this directly measures Reference-completeness.
- Author `.feature` file `createuser-business-type-undocumented.feature`: GIVEN the Reference page lists `type: "individual"` only, WHEN the integrator submits `type: "business"`, THEN assert the API accepts it AND returns a usable `business_legal_name`-bearing user object — i.e., test that the unpublished enum value works (proving the docs are incomplete, not the API).

**`api-functional-tester`**
- Mass-assignment probe: `POST /v1/users` with `verification_status: "VERIFIED"`, `status: "VERIFIED"`, `eligible_products: [...]`, `requires_reverification: false`, `external_id: <attacker-controlled>`. The Reference page does NOT explicitly forbid these. If any honored → mass-assignment finding bypassing KYC.
- `source_of_funds` enum has 19 values; one of them might map differently in the OFAC/AML pipeline (e.g., `"gambling_winnings"` vs `"investment_proceeds"`). Probe: does the choice of `source_of_funds` change the verification SLA or fail-rate?

**`api-security-auditor`**
- **API3:2023 broken object-property-level auth** — probe `GET /v1/users/{id}` response fields for: internal flags (`ofac_score`, `risk_band`, `manual_review_note`), audit fields (`created_by`, `tenant_id`), provider-specific data (`portage_internal_id`). Reference page is silent on response shape; this is a property-level enumeration target.
- **API3 mass assignment via PUT** — `updateuser` not fetched, but probe is: does PUT honor `verification_status`, `status`, `eligible_products`, `requires_reverification`? Particularly: can a user be downgraded `VERIFIED → CREATED` via PUT, then re-verified for free against AML cost (cost amplification)?

**`devil-advocate`**
- The "Reference page omits Bearer header" finding is brittle if it's just a parsing artifact of WebFetch. **Verify by viewing the page raw in a browser** before publishing the finding. If confirmed, this single finding moves up the top-5.

---

## Family 3 — Recipients
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/post_v1recipients`, `https://kira-financial-ai.readme.io/reference/get_v1recipients`
**Pages NOT fetched (sampled out):** `get_v1recipientsrecipientid` — single-detail endpoint, same shape as `getuser`.

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5.
- **CRITICAL — `post_v1recipients` lists 19 account-type variants by name** (SPEI, ACH, WIRE, SWIFT, INSTANT_PAY, PSE, WALLET, ARS, BRL, CLP, PEN, PEUSD, UYU, DOP, ECUSD, CRC, GTQ, PAUSD, PYG, SVUSD) **but does NOT render the per-variant field schemas.** The page collapses them. An integrator cannot read the Reference and know what a SPEI body looks like vs a SWIFT body. flow-design §3.5 captured this from the `docs/account-types-reference.md` Guides page; the Reference page itself is **structurally inadequate** for the polymorphic schema.
- **`post_v1recipients` does NOT enumerate error codes** — only `400/401/404/409/500` with generic descriptions. The SCREAMING_SNAKE codes (`VALIDATION_ERROR`, `INVALID_BANK_CODE`, `IDEMPOTENCY_CONFLICT`) that flow-design §2.3 derived from runtime are **invisible on the Reference page**.
- **`get_v1recipients` query params: ONLY `user_id` (uuid, required).** No `limit`, no `offset`, no `cursor`. Reference page **confirms GAP-15** (unpaginated list). The response shape is described as "List of recipients" with no envelope detail — could be flat array, could be wrapped object. Reference layer doesn't disambiguate.
- **Try It widget** on `post_v1recipients` is dangerous in a different way: filling it for `WALLET` account type with a real attacker-controlled `address` would persist a recipient under the integrator's tenant.
- **Status codes documented (per page):** `post_v1recipients`: `201/202/400/401/404/409/500`. **The 202 is unique** — recipients use 202 for idempotent reuse on existing recipient, contradicting the conventional 200/201. `get_v1recipients`: `200/400/401/404`. **403, 422, 429, 503 missing.**

### Per-agent contributions

**`product-manager`**
- Pillar-1 finding: 19 polymorphic account-type variants on one endpoint, **zero per-variant schema rendering on the Reference page**. The integrator pain is days lost guessing which fields a SPEI vs a SWIFT recipient needs. Severity: HIGH.

**`data-architect`**
- Add §3.5a to flow-design: "The Reference page for `POST /v1/recipients` is structurally inadequate for the polymorphic schema. The canonical per-variant requirements only live in `docs/account-types-reference.md` (a Guides page). Reference and Guides must be aligned." → GAP-33 (new — polymorphic schema not rendered at Reference).

**`data-engineer`**
- Pagination probe on `GET /v1/recipients`: create 1000 recipients under one user_id, then call list. Capture response size, latency, server-side limit (if any), and whether the response is truncated silently. Today GAP-15 says "unbounded array" — measure the actual ceiling.
- Probe `GET /v1/recipients` envelope: is it flat array, or `{data:[...]}`, or `{recipients:[...]}`. Three pages-prior list endpoints disagree; Reference page for recipients doesn't say.

**`qa-engineer`**
- Author `.feature` file `recipients-list-envelope-drift.feature`: GIVEN three list endpoints (`/v1/users`, `/v1/virtual-accounts`, `/v1/recipients`), WHEN called, THEN assert the same envelope shape. Today they differ. The cross-page test fails by construction — this is the contract-uniformity .feature for GAP-15+GAP-09.
- Schemathesis-fuzz `POST /v1/recipients` per variant; the Reference page lists 19 — only 7-8 are deeply documented in `account-types-reference.md`. The 11 sparsely-documented variants are the test target.

**`api-functional-tester`**
- The 202 idempotent-reuse semantics on recipients is unique. Probe: send same `idempotency-key` + same body → 202. Send same key + *different* body → ??? (the Reference says 409; the Guides say 409 with a code). Race: send 10 parallel POST with same key + same body in <100ms — confirm only one recipient is created, all 10 get 202 (vs the first getting 201 and the rest a different code).

**`api-security-auditor`**
- **WALLET account-type variant** is the SSRF-adjacent target. Probe: create a recipient with `account.type: "WALLET"`, `network: "polygon"`, `address: "0x<attacker>"`. Does the API perform any address-validation by fetching an explorer URL (potential SSRF)? Reference page shows no such validation; runtime may.

---

## Family 4 — Virtual Accounts
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/createvirtualaccount`, `https://kira-financial-ai.readme.io/reference/listvirtualaccounts`, `https://kira-financial-ai.readme.io/reference/getvirtualaccountdeposits`
**Pages NOT fetched (sampled out):** `getvirtualaccount`, `getuservirtualaccounts`, `getvirtualaccountbalance`, `getvirtualaccountdeposit` — get-detail shape uniform across resources.

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5.
- **`createvirtualaccount` body fields visible on Reference: ONLY `user_id`, `type`, `bank`.** The `provider`, `mode`, `destination.{currency, network, address}`, `markup.{fx_bps, fee_bps}` fields that flow-design §3.4 catalogued are **NOT VISIBLE** on the Reference page. The dual-product story (`portage` vs `austin_capital_trust` vs `slovak_savings_bank`) is partially visible via the `bank` enum, but **`provider` (the Apr-14-changelog alias) is missing entirely from the Reference**. The Reference page is **stale relative to its own changelog**.
- **`listvirtualaccounts` status enum:** `pending`, `activating`, `active`, `failed`, `deactivated` (lowercase). Note: `deactivated` exists in the filter (GAP-27 confirmation) but no Reference page documents an endpoint that transitions to it. **The list endpoint exposes a state that's unreachable.** Functional-tester gold.
- **`listvirtualaccounts` mode enum:** `crypto`, `fiat` (lowercase). flow-design §3.4 used `CRYPTO`/omit. Reference disagrees. Casing drift.
- **`getvirtualaccountdeposits` has ONLY `limit` param (no offset, no cursor)** — confirms GAP-09 (deposits list is special-cased: limit-only on Reference). **No pagination model documented for it.**
- **`createvirtualaccount` documents only `400/401/409/500`** — no `403/422/429/503`. No `404` (which the API surely returns for unknown `user_id`).
- **No cross-references** to webhooks (despite VA being the canonical "create resource → wait for webhook to activate" pattern). Reference page leaves integrators stranded after the 201.
- **Try It widget on `createvirtualaccount`** would attempt to provision a real sandbox VA under the docs-visitor's tenant if credentials are persistent in the form. No safeguard messaging.

### Per-agent contributions

**`product-manager`**
- Pillar-3 finding (docs-runtime congruence): Reference page documents 3 body fields; the actual create body has 8+ fields per flow-design (after Apr-14 changelog). **The Reference page is missing 60% of the create body schema.** This is the integrator's go-to page when implementing the integration; gap is HIGH-severity.
- The Reference exposes `deactivated` as a filterable status but no Reference page documents how to reach it — **the integrator can list deactivated VAs they themselves cannot create or transition to**. This is observable contract drift visible at the Reference layer.

**`data-architect`**
- Add to flow-design GAP-32: virtual-account reference page does not document `provider` alias. The April-14 changelog added it; the Reference page wasn't updated. **Changelogs are publishing structural changes that don't reach the Reference pages.** This is a systemic content-freshness gap. → GAP-34 (new — Reference not updated to match changelog).

**`data-engineer`**
- Probe `POST /v1/virtual-accounts` with the *full* body (provider, mode, destination, markup) and capture which fields the API accepts vs rejects. If markup.fx_bps is silently honored, that's runtime behavior not in the Reference docs. Capture as `evidence/work/virtual-accounts/{NN}-fields-not-in-docs.json`.
- Probe `GET /v1/virtual-accounts?status=deactivated` — does it return an empty list? An error? Confirm whether the status is actually filterable as documented or returns nothing because the state is unreachable.

**`qa-engineer`**
- Author `.feature` file `va-status-enum-reference-vs-runtime.feature`: Reference page documents lowercase enums (`pending`, `active`); flow-design has both uppercase and lowercase. Filter probe per state — assert which casing the runtime accepts.

**`api-functional-tester`**
- **State-machine bypass**: try `POST /v1/virtual-accounts` with `status: "active"` directly in the body (mass assignment). Reference page doesn't say the field is read-only. If accepted, the VA skips the `pending → activating → active` provisioning chain entirely.
- Probe `markup.fx_bps` and `markup.fee_bps` for negative values. If accepted → integrator can credit themselves a negative fee on every payout (free money).

**`api-security-auditor`**
- **API3:2023 mass assignment** — body fields beyond `{user_id, type, bank}` that the API will honor without rejecting: probe `client_id` (cross-tenant), `partner_bank_routing_number`, `tenant_id`, `source_deposit_instructions` (set them directly, then create), `created_at` (backdating).

---

## Family 5 — Quotations
**Pages fetched:** `https://kira-financial-ai.readme.io/v2026-04-14/reference/createquotation` (only reachable via version-prefixed URL — see GAP-29).
**Pages NOT fetched (sampled out):** quote-detail / list endpoints — none exist per flow-design §3.6 (single-endpoint family).

**Reference-page surface highlights:**
- **`/reference/post_v1-quotations` and `/reference/createquotation` BOTH 404**. Only `/v2026-04-14/reference/createquotation` resolves. The slug `createquotation` is canonical-but-not-discoverable from llms.txt. → **GAP-29 (new — Reference page hidden from llms.txt index)**.
- **Code-sample languages:** Same 5.
- **MASSIVE schema drift between Reference and Guides for the same endpoint.** Reference Quotations body fields: `amount`, `recipient_id`, `account_type`, `wallet_network`, `wallet_token`, `inverse_calculation`, `payment_instructions`, `client_markup`. **Guides (per flow-design §3.6) describe:** `base_currency`, `quote_currency`, `amount`, `amount_in_destination`. These are **two different fundamental shapes of the same endpoint**. An integrator following the Guides will submit `base_currency`/`quote_currency` and get a 400 (or worse, silent acceptance with garbage results). → **GAP-31 (new — Reference and Guides describe disjoint Quotations schemas)**.
- **Enums newly exposed in Reference (Quotations):**
  - `account_type`: `WIRE, SWIFT, WALLET, ACH, INSTANT_PAY` — note: SPEI, PSE, BRL, ARS, CLP, PEN, etc. are MISSING. The Reference Quotations page only supports US/crypto destinations, **not LATAM payouts** that the Guides advertise. Contract surface area is materially narrower than marketing implies.
  - `wallet_network`: `solana, polygon, tron` (lowercase, Reference-uniform).
  - `wallet_token`: `USDC, USDT` (no COPm despite recipient enum supporting it).
- **Status codes documented:** `400/401/404/500`. **No 422, 429, 503.** No `409` (despite quote TTL implying a conflict on used quotes).
- **Auth note** on the Quotations Reference page: "missing or invalid API key / bearer token" — finally a Reference page that describes both headers. Outlier — most Reference pages omit Bearer.
- **No verbatim response JSON.** The promised `kira_rate` field cannot be confirmed at the Reference layer.

### Per-agent contributions

**`product-manager`**
- Pillar-3 finding: Quotations Reference vs Guides describe **two disjoint endpoints**. This is the single most severe docs-vs-docs drift in the entire sweep — it makes the Quotations endpoint untestable from docs alone. Severity: **CRITICAL**.
- Pillar-1 finding: the Reference Quotations page only documents US/crypto destinations (`WIRE`, `SWIFT`, `ACH`, `INSTANT_PAY`, `WALLET`). The LATAM payout types (`SPEI`, `PSE`, `BRL`, etc.) are missing — yet Kira markets 14 LATAM currencies for payouts. **The Reference page does not cover the marketed product surface.**

**`data-architect`**
- The disjoint schema implies one of two truths: (a) `account_type`/`wallet_*` is a new schema replacing `base_currency`/`quote_currency` (Apr-14 changelog never said so), or (b) the docs were updated in opposite directions on accident. Open question for @Diego (Eng) explicitly.
- Add **GAP-31** to flow-design §6 with `category: schema-drift, severity: CRITICAL`.

**`data-engineer`**
- Probe `POST /v1/quotations` with BOTH schemas in parallel: one body with `base_currency`/`quote_currency`, one body with `account_type`/`wallet_network`. Capture which returns 200 vs 400. Whichever returns 200 is the actual contract; the other doc page is wrong.
- Probe `account_type: "SPEI"` (or `"PSE"`) against the Reference-documented Quotations endpoint to confirm whether LATAM types are silently rejected vs accepted-but-undocumented.

**`qa-engineer`**
- Author `.feature` file `quotations-reference-vs-guides-schema-drift.feature`: GIVEN the Reference page documents `account_type`, the Guides document `base_currency`, WHEN both bodies are sent, THEN exactly one returns 200. Assert that one (whichever it is) AND assert the other returns 400 (NOT 422 silently passing).

**`devil-advocate`**
- If GAP-31 lands at CRITICAL it should be the top-1 finding in the PM's README — quotations are the bridge between recipients and payouts (Recipe B step 3). An integrator who can't write a quote can't ship payouts. This is plausibly the highest-impact finding from the entire Reference sweep.

---

## Family 6 — Payment Link
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/post_v1-payment-link`
**Pages NOT fetched (sampled out):** No other payment-link reference pages exist (one-endpoint family per flow-design §3.9).

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5.
- **Body schema visible on Reference (much more detailed than other pages):**
  - `recipient_type` enum: `business | person`
  - `country_code`: 107-value enum (**inconsistent — both `/v1/countries` and recipient.account.country imply 250 countries**; the payment-link enum is a narrower subset of 107. Why 107? Open question.)
  - `recipient_*` PII fields (first/middle/last name, phone, email, address, date_of_birth)
  - Transaction fields: `client_uuid`, `reference`, `amount`, `payin` (`card | cash`), `fixed_amount` (boolean), `max_amount`
  - `acct_info` is documented to "vary by country" with separate examples shown for US, SV (El Salvador), GT, MX, CO, and wallet accounts — **but only those 6** of the marketed 14. The remaining 8 LATAM currencies' `acct_info` shape is invisible on the Reference. flow-design §3.9 already flagged this; Reference layer confirms.
- **`link_type` enum is NOT VISIBLE on Reference** despite Guides documenting `top-up` vs `remittance` modes. Same Reference-vs-Guides drift as Quotations: the parameter exists at runtime per Guides, but Reference doesn't enumerate it.
- **Required headers:** ONLY `x-api-key` listed. No `idempotency-key` (consistent with flow-design §2.4 which has payment-link OUT of the idempotency-required list).
- **Status codes documented:** `200, 400, 401, 403, 422, 500`. **Best status-code coverage of any Reference page in the sweep** (5 codes vs the typical 3-4). Still no `429` / `503`.
- **No customization fields** (logo, brand colors, locale) documented at the Reference layer despite Guides promising them. → another Reference-Guides drift.
- **No link-expiry field** documented (Guides also silent — confirms product-catalog Product 2 finding).
- **No `redirect_url` field documented at the Reference layer** despite Guides specifying `?status=success` / `?status=cancelled` redirect-contract behavior.

### Per-agent contributions

**`product-manager`**
- Pillar-1 finding: payment-link customization fields (logo, brand colors, locale, return-URL) are advertised in Guides ("brand colors, logo. Fees, texts and payment methods can also be customized" per `docs/payment-link.md`) but **completely invisible at the Reference layer**. An integrator wiring the actual endpoint has no schema for the customization. → repeats GAP from product-catalog at the Reference dimension.
- `country_code` 107-value enum vs the broader `/v1/countries` 250-country dataset is a coverage discrepancy worth surfacing. Which 143 countries can't receive a payment link?

**`fullstack-integrations-specialist`**
- `redirect_url` is *not* in the request body per the Reference — yet the Guides describe `?status=success`/`?status=cancelled` redirect contract. Probe: where does the redirect URL come from? Is it `acct_info.redirect_url`? `client_uuid`-derived? A sandbox global config? **The Reference page erases the redirect contract entirely.**
- iframe-embed the payment_link URL on a third-party origin (per fullstack-integrations-specialist's standing probe playbook) and capture CSP/X-Frame-Options. The Reference page doesn't document iframe support.
- The `country_code` enum has 107 values, plus 6 example `acct_info` variants — probe whether countries outside the 6 examples accept a generic `acct_info` schema or are runtime-rejected.

**`data-engineer`**
- Send `POST /v1/payment-link` with `link_type: "top-up"` and `link_type: "remittance"` even though the Reference doesn't document the field. Confirm which is honored, what changes in the response shape.
- Send `POST /v1/payment-link` with `link_type: "garbage"`, `link_type: null`, `link_type: ""`. Capture envelope shape of each error.

**`api-functional-tester`**
- `max_amount` + `fixed_amount: false` allows a sender to choose any amount up to max. Probe: set `max_amount: 100000` (the maximum the API will accept), then complete the link with `amount: 99999.99`. Does anything cap this for fraud/AML? The Reference does not document any AML threshold.

**`api-security-auditor`**
- **Open redirect probe** — the Guides describe redirect-URL params; the Reference omits them. Probe `POST /v1/payment-link` with `redirect_url` smuggled into various body fields (`reference`, `external_id`, `acct_info.return_url`, `metadata.redirect`). Any path that survives → open-redirect vulnerability in the hosted payment page.

---

## Family 7 — Webhooks (security-critical per the brief)
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/post_webhooks-register`
**Pages NOT fetched (sampled out):** No other webhook reference pages exist (no PUT, no DELETE, no GET — GAP-21 confirmed).

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5.
- **Body fields documented:** `webhook_url` (uri, required), `secret` (string, OPTIONAL), `client_uuid` (string, required). **`secret` being OPTIONAL is a finding** — flow-design §2.7 had it implied-required. If you can register a webhook with no secret, signature verification is impossible / trivially bypassable (server can't sign because no secret was registered).
- **`webhook_url` validation:** NO documented constraint. The Reference page does NOT say:
  - HTTPS-only (Guides imply yes, Reference doesn't)
  - Hostname must not resolve to private IP / link-local
  - Port must not be 22/25/3306/6379/etc.
  - URL must be reachable at registration time
  - Domain must be on an allowlist
- **`secret` validation:** NO documented length / entropy requirement.
- **Required headers:** Reference page does NOT show any required header (not even `x-api-key`). **This is the only Reference page in the sweep where the auth section is completely empty.** Either the page is broken-rendered or the API genuinely accepts unauthenticated `POST /webhooks/register` (which would be CRITICAL — anyone can register a webhook against any `client_uuid`).
- **Status codes documented:** **ZERO error codes documented.** Only `200`. No `400`, no `401`, no `403`, no `409`, no SSRF rejection (`400 INVALID_URL` or `403 BLOCKED_DESTINATION` would be expected if Kira validates the URL).
- **No PUT/DELETE/GET endpoint exists per the Reference** — confirms GAP-21 (no rotation, no removal). Recovery from a leaked secret = contact support.
- **No signature-header spec on this page.** `x-signature-sha256` encoding (hex vs base64 vs `sha256=` prefix) is not specified anywhere in the Reference; the Guides also don't say. GAP-11 stays at CRITICAL.
- **Try It widget is live** — clicking it with `webhook_url: "http://169.254.169.254/latest/meta-data/"` would (a) test the SSRF posture of Kira's webhook registrar, OR (b) silently register an attacker-pointable webhook against the docs-visitor's tenant. **This is a probe-as-attack-surface that needs explicit out-of-band confirmation before any tester runs it.**
- **Recent Requests panel:** Gated. **If a logged-in user sees other tenants' recent registered webhook URLs** through this panel, that is a CRITICAL information-disclosure finding (registered webhook URLs leak the integrator's infrastructure DNS).

### Per-agent contributions

**`product-manager`**
- Pillar-4 (integration hardening) finding: the Reference page for the most security-sensitive endpoint in Kira's surface has **zero error codes, zero header documentation, zero URL-validation rules, zero signature-encoding spec**. An integrator implementing webhooks has nothing actionable from this Reference page. Severity: **CRITICAL**.

**`fullstack-integrations-specialist`**
- `secret` being optional means a Vercel/Cloudflare-Workers integrator who omits `secret` will get push deliveries without verifiable signatures. Probe: register with `secret: ""` and `secret: null` and (omit field) — does the API send signed deliveries anyway, send unsigned, or reject the registration?
- Webhook URL probe: register with `webhook_url: "https://localhost:9999/webhook"`, `https://127.0.0.1`, `https://[::1]`, `https://169.254.169.254`, `https://*.kira.local`, `https://yourapp.com:22`. Capture the response per attempt — any 200 indicates SSRF surface.

**`data-engineer`**
- Send `POST /webhooks/register` with NO `Authorization` header (just `x-api-key`) AND with NO headers at all. Capture per-permutation:
  - `x-api-key` only → 200 (per flow-design GAP-04) — confirm
  - `Authorization` only → ??? — probe
  - Neither → ??? — probe (the page documents nothing about auth)

**`api-functional-tester`**
- Race: register webhook URL → A (yours), wait for Kira to send one delivery (induce by triggering a user.created event), then register URL → B (attacker's), at the same moment as event 2 fires. Does Kira atomically swap, or does the old URL still receive a few in-flight events while the new one starts receiving? Window for spoofing.

**`api-security-auditor`**
- **API7:2023 SSRF — primary target endpoint.** Probe matrix:
  - `http://169.254.169.254/latest/meta-data/` (AWS metadata)
  - `http://169.254.170.2/v2/credentials/` (ECS task credentials)
  - `http://metadata.google.internal/computeMetadata/v1/`
  - `http://localhost:6379/info` (local Redis)
  - `http://10.0.0.1/` (RFC 1918 — Kira's own VPC)
  - `http://[::1]/`, `http://[fc00::1]/` (IPv6 private)
  - DNS-rebinding: register `attacker.com` (resolves to public IP at registration), rebind to `127.0.0.1` after registration test. Capture if Kira re-resolves on each delivery or caches.
  - `file:///etc/passwd` (file scheme — unlikely but verify rejection)
  - `gopher://localhost:6379/_AUTH...` (protocol smuggling)
  - HTTP smuggling: `https://attacker.com#@169.254.169.254/`
- **API2:2023 Broken Auth** — if Reference page omitting auth is *truthful* (API accepts unauthenticated registration), the entire webhook surface is unauthenticated. **Probe immediately** before any other webhook test runs.
- **API3:2023** — register a webhook with `client_uuid` = another tenant's UUID. Does Kira validate that `client_uuid` matches the authenticated `x-api-key`'s owner? If not → cross-tenant webhook hijack (deliveries for tenant B redirect to attacker URL registered under tenant A).
- **Recent Requests panel** post-login telemetry leakage: scrape (with consent) the panel for other tenants' webhook URLs. If visible → CRITICAL exposure of integrator infrastructure.

**`devil-advocate`**
- The "zero documented error codes on `POST /webhooks/register`" finding is concrete, ubiquitous, and a real fix. Promote to top-5 candidate.

---

## Family 8 — Reference Data
**Pages fetched:** `https://kira-financial-ai.readme.io/reference/get_banks`, `https://kira-financial-ai.readme.io/reference/get_v1countries`
**Pages NOT fetched (sampled out):** No other reference-data endpoints exist.

**Reference-page surface highlights:**
- **Code-sample languages:** Same 5.
- **`GET /banks` path:** confirmed as `https://api.balampay.com/sandbox/banks` — **NO `/v1/` prefix**. Every other endpoint uses `/v1/...`. The Reference page is the only place this discrepancy is fully visible. **→ GAP-32 (new)**.
- **`GET /banks` `country_code` format:** Reference page does NOT state alpha-2 vs alpha-3 — just says "string, required". GAP-20 from flow-design is therefore unfixable from the Reference page alone (you must read Guides to learn it's alpha-2).
- **`GET /banks` error codes:** `400 "Invalid country code or validation error"`, `401`, `500`. No `404` (so an invalid country returns 400, not 404 — confirm with runtime).
- **`GET /v1/countries` path:** correctly versioned (`/v1/countries`). Inconsistent with `/banks`.
- **`GET /v1/countries` query parameters:** NONE documented. No way to filter, no pagination — entire 250-country list returned on every call. Latency / payload-size implications.
- **`GET /v1/countries` required headers:** `x-api-key` only documented. Bearer not listed. (Pattern repeating.)
- **`GET /v1/countries` status codes:** `200, 401, 500`. **No `429`** even though this is the most-likely endpoint for an integrator to hammer (it's a reference-data lookup; many client SDKs would pre-fetch on init).
- **No verbatim response JSON** for either page — `postal_code_format` regex per-country (the only reason `/v1/countries` is useful for client-side validation) is invisible at the Reference layer.

### Per-agent contributions

**`product-manager`**
- Pillar-2 (ease of connection) finding: `/banks` path inconsistency means every code generator (OpenAPI, Postman import) that assumes `/v1` prefix will produce broken stubs. → GAP-32 should be HIGH severity.
- `/v1/countries` is a reference-data endpoint — common practice is to make these public (no auth, no rate limit) so client SDKs can pre-fetch postal-code regex during init. Kira requires `x-api-key` for this lookup, which forces SDKs to bundle auth state for static-reference data. Pillar-4 nuisance.

**`data-architect`**
- Add GAP-32 (path inconsistency: `/banks` vs `/v1/*`) to flow-design §6 with severity HIGH and the integrator-pain "every codegen pipeline breaks at this endpoint."
- Open question for @Diego: Is `/banks` intentionally unversioned, or should it be `/v1/banks`? If unversioned, it has no path-level versioning recovery if it ever changes shape (GAP-01 inheritance).

**`data-engineer`**
- Probe `GET /banks?country_code=MX` vs `MEX` vs `mx` vs `Mexico` vs (empty) vs (omitted). Capture each response per GAP-20.
- Probe `GET /v1/countries` with `?country_code=US`, `?limit=10`, `?offset=10`, etc. — confirm none are honored. Measure latency / payload size at p50/p95/p99. If payload exceeds 100KB, that's a Pillar-4 finding (every authed client pays this on every cold start).
- Probe `GET /banks` at `https://api.balampay.com/sandbox/v1/banks` (adding the `/v1/` prefix the rest of the surface uses). Does the API 404 or transparently rewrite? Either answer is content-worthy.

**`qa-engineer`**
- Schemathesis-fuzz `country_code` against alpha-2, alpha-3, lowercase, lowercase-alpha-3, with extra whitespace, with Unicode lookalikes (`М` cyrillic for `M`). Assert envelope shape per response.

**`api-functional-tester`**
- Probe whether `/banks` accepts country codes that aren't in `/v1/countries`. If yes → enum drift between reference-data endpoints; integrators can pass a country to `/banks` that they couldn't pass to a user `address_country`.

**`api-security-auditor`**
- Path inconsistency `/banks` vs `/v1/*` raises API9:2023 (improper inventory management) concern — old unversioned paths may exist for other endpoints too. Probe: `GET /sandbox/users`, `GET /sandbox/virtual-accounts`, `GET /sandbox/payouts` (without `/v1/`). If any 200 → unversioned shadow surface (CRITICAL, API9).

---

## Aggregate — Reference Coverage by Family
| Family | Pages fetched | Net-new probes added | Highest-severity new finding |
|---|---|---|---|
| 1. Authentication | 1 | 6 | Reference page omits `x-api-key` header documentation (Pillar-1) |
| 2. Users | 3 | 13 | Reference page documents only `type: "individual"`, hides `business` half of product (Pillar-1) |
| 3. Recipients | 2 | 6 | 19 polymorphic account types listed by name, ZERO per-variant schema rendered at Reference (GAP-33) |
| 4. Virtual Accounts | 3 | 7 | Reference page missing 60% of create-body fields documented in Apr-14 changelog (GAP-34) |
| 5. Quotations | 1 | 5 | Reference and Guides describe disjoint Quotations schemas (GAP-31, CRITICAL) |
| 6. Payment Link | 1 | 7 | Customization & redirect contract invisible at Reference; `link_type` enum missing |
| 7. Webhooks | 1 | 11 | Reference page documents zero error codes / zero header rules / `secret` optional (CRITICAL, security) |
| 8. Reference Data | 2 | 7 | `/banks` path has no `/v1/` prefix (GAP-32, HIGH) |
| **Totals** | **14** | **62** | **GAP-31 (Quotations schema drift) — CRITICAL** |

---

## Aggregate — Top 10 Net-New Probes (ranked by impact)

1. **Quotations Reference-vs-Guides schema drift (GAP-31).** Owner: `data-engineer` + `qa-engineer`. Target: `POST /v1/quotations`. Send both `{base_currency, quote_currency, amount}` AND `{account_type, wallet_network, wallet_token, amount}` in parallel; capture which returns 200. Whichever is the *real* schema, the other docs page is wrong. **Why this matters:** Quotations is the bridge between recipients and payouts; getting it wrong blocks every fiat-to-fiat payout. The two pages disagreeing makes this untestable from docs alone.
2. **Webhook SSRF probe matrix (GAP-11 + new).** Owner: `api-security-auditor`. Target: `POST /webhooks/register`. Probe 10 URL variants (metadata.aws, localhost, RFC 1918, IPv6 link-local, DNS rebinding, file://, gopher://). The Reference page does not document a single rejection rule. **Why this matters:** SSRF on a fintech back-end can read AWS credentials → infinite blast radius.
3. **Unauthenticated webhook registration probe.** Owner: `api-security-auditor`. Target: `POST /webhooks/register`. The Reference page lists no required headers. Probe: send the body with neither `x-api-key` nor `Authorization`. If 200 → CRITICAL unauthenticated cross-tenant webhook hijack.
4. **Unversioned-path enumeration (GAP-32).** Owner: `api-security-auditor`. Probe `https://api.balampay.com/sandbox/users`, `/virtual-accounts`, `/payouts`, `/recipients`, `/payins`, `/quotations` without the `/v1/` prefix. `/banks` is unversioned; if any of the others are too → API9 inventory finding.
5. **`POST /v1/users` mass assignment via published-but-undocumented fields.** Owner: `api-security-auditor`. The Reference page documents 30+ body fields; probe whether adding `verification_status`, `status`, `eligible_products`, `requires_reverification`, `client_id`, `tenant_id` is honored at runtime. KYC bypass = CRITICAL.
6. **Recent Requests panel cross-tenant disclosure.** Owner: `api-security-auditor`. Log in (as authorised tester) and check whether the panel exposes other tenants' webhook URLs, user_ids, va_ids, payout amounts, recipient PII. If yes → API3:2023 at the docs layer, BOLA via documentation portal.
7. **Quotations LATAM-currency runtime probe.** Owner: `data-engineer`. Reference Quotations page only documents `account_type ∈ {WIRE, SWIFT, ACH, INSTANT_PAY, WALLET}`. Probe `account_type: "SPEI"`, `"PSE"`, `"BRL"`, `"ARS"`, `"CLP"`. Capture which return 200 (runtime feature, undocumented) vs 400.
8. **Try It widget cross-visitor credential persistence.** Owner: `api-security-auditor`. After clicking Try It on `POST /auth` with sandbox creds, open a fresh incognito session and re-load the same page. Are creds pre-filled? ReadMe.io has had this bug; if Kira inherits → credential leak via shared form state.
9. **`POST /v1/virtual-accounts` mass assignment of `source_deposit_instructions`.** Owner: `api-functional-tester`. Reference page documents only `{user_id, type, bank}` — probe whether you can set `source_deposit_instructions.bank_account_number` directly. If accepted → VA spoof: integrator-controlled bank account number under Kira's claimed FDIC-insured VA.
10. **Bank-code enum drift between `/banks` and recipient.account.bank_code.** Owner: `data-engineer`. Pull all banks for a country via `/banks`; create a recipient using each `bank_code`. Assert 100% acceptance. Any rejection = enum drift between reference-data and recipient creation (silent breakage class).

---

## Aggregate — Reference-Specific Findings (only visible at Reference layer)

### F-REF-1 — Response examples missing on EVERY reference page (GAP-30)
**Severity:** HIGH
**Category:** docs gap (Pillar 1)
**Evidence:** All 14 fetched pages render "Click Try It! to see the response here!" instead of a static 2xx JSON body. Verifiable on `https://kira-financial-ai.readme.io/reference/post_auth` etc.
**Integrator pain:** Cannot understand the API response shape without an account + Try It interaction. Time-to-first-call inflated; copy-paste samples are not runnable end-to-end.

### F-REF-2 — Quotations Reference-vs-Guides schema drift (GAP-31)
**Severity:** CRITICAL
**Category:** docs-runtime congruence / sandbox-prod drift
**Evidence:** `/v2026-04-14/reference/createquotation` documents `account_type, wallet_network, wallet_token, inverse_calculation`. `docs/quotation-guide.md` + `docs/quotations.md` document `base_currency, quote_currency, amount, amount_in_destination`. Two pages, one endpoint, disjoint schemas.
**Integrator pain:** Days of debugging trying to figure out which docs page reflects reality. Direct blocker on the fiat-to-fiat payout recipe.

### F-REF-3 — `/banks` endpoint has no `/v1/` prefix (GAP-32)
**Severity:** HIGH
**Category:** versioning / inventory
**Evidence:** Reference page lists URL as `https://api.balampay.com/sandbox/banks` (no `/v1/`). Every other endpoint uses `/v1/`. Codegen tooling assuming a uniform prefix will produce broken stubs for this single endpoint.
**Integrator pain:** SDK build pipelines silently miss banks lookup; client SDKs ship without bank validation.

### F-REF-4 — Reference pages stale relative to Apr-14 changelog (GAP-34)
**Severity:** HIGH
**Category:** docs gap / Pillar 3
**Evidence:** Apr-14 changelog adds `provider` alias to `POST /v1/virtual-accounts` and `mode` enum and stablecoin base currencies to Quotations. The Reference pages do NOT reflect these additions (createvirtualaccount shows only `{user_id, type, bank}`; quotations Reference doesn't list stablecoin base currencies). Changelog and Reference are not co-authored.
**Integrator pain:** The Reference page is supposed to be the source of truth; an integrator reading it misses 60% of new fields.

### F-REF-5 — Code-sample languages limited to Shell/Node/Ruby/PHP/Python (every page)
**Severity:** MEDIUM
**Category:** ease of connection (Pillar 2)
**Evidence:** All 14 fetched pages offer the same 5 languages. Absent: Go, Java, Kotlin, C#, .NET, TypeScript, Swift, Rust.
**Integrator pain:** Kira's named buyers (Banco Industrial, N1co) are Latin American banks — likely Java/Kotlin/.NET shops. Reference offers no code path for them.

### F-REF-6 — Webhook register reference page has ZERO error code / auth / validation documentation
**Severity:** CRITICAL
**Category:** docs gap / security
**Evidence:** `/reference/post_webhooks-register` documents only `200`. No `400`, no `401`, no `403`, no `409`. No headers section. No `webhook_url` format validation rules. `secret` field marked optional.
**Integrator pain:** The most security-critical endpoint has the least documentation.

### F-REF-7 — Reference page omits `Authorization: Bearer` header on most endpoints
**Severity:** HIGH
**Category:** auth contract (Pillar 4)
**Evidence:** `createuser`, `listusers`, `getuser`, `createvirtualaccount` Reference pages list only `x-api-key` in the headers section. Yet flow-design §2.2 (synthesized from Guides) says Bearer is required on all non-`/auth` endpoints.
**Integrator pain:** Literal copy-paste integrators get 401 on first call. Sharpens GAP-04 from a Reference-content-correctness angle.

### F-REF-8 — Status code coverage is uneven and inconsistent across pages
**Severity:** MEDIUM
**Category:** docs gap / Pillar 1 + Pillar 4
**Evidence:** Sample matrix:
| Endpoint | 200 | 201 | 400 | 401 | 403 | 404 | 409 | 422 | 429 | 500 | 503 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `POST /auth` | ✓ | – | – | – | ✓ | – | – | ✓ | – | ✓ | – |
| `POST /v1/users` (createuser) | – | ✓ | ✓ | ✓ | – | – | ✓ | – | – | ✓ | – |
| `GET /v1/users` (listusers) | ✓ | – | ✓ | ✓ | – | – | – | – | – | ✓ | – |
| `POST /v1/recipients` | – | ✓ | ✓ | ✓ | – | ✓ | ✓ | – | – | ✓ | – |
| `POST /v1/payment-link` | ✓ | – | ✓ | ✓ | ✓ | – | – | ✓ | – | ✓ | – |
| `POST /webhooks/register` | ✓ | – | – | – | – | – | – | – | – | – | – |

`429` is absent from every Reference page despite the auth guide saying a global rate limit applies. `503` is never documented.
**Integrator pain:** Error handlers can't be written defensively. Each new error code in prod = surprise outage.

### F-REF-9 — Recent Requests panel telemetry surface (privacy candidate)
**Severity:** UNVERIFIED (probe required)
**Category:** privacy / API3:2023
**Evidence:** Every page shows a "Recent Requests" panel gated to logged-in users. Anonymous = no leakage. **Post-login behavior unknown — must be probed by an authorised tester.** If the panel exposes other tenants' webhook URLs, user_ids, va_ids, etc., it's a docs-portal-as-data-leak.
**Integrator pain:** Buyers do free-tier signup and immediately see other tenants' data → trust catastrophe.

### F-REF-10 — Try It widget on payout endpoint has no money-movement warning
**Severity:** MEDIUM
**Category:** integration hardening
**Evidence:** `/reference/initiatepayout` (POST /v1/virtual-accounts/{id}/payout) Try It widget has the same UX as `/reference/get_v1countries`. No banner, no confirmation. A docs visitor exploring the Reference and clicking Try It could (assuming credentials are prefilled) initiate a real sandbox payout.
**Integrator pain:** Sandbox != production but is still real reconciliation. Unintended payouts confuse new integrators' ops teams.

---

## Aggregate — Updates Recommended for flow-design.md

1. **Add GAP-29** — "Quotations Reference page hidden from `llms.txt` index; only reachable via version-prefixed `/v2026-04-14/reference/createquotation`." Category: findability. Severity: MEDIUM. Touches GAP-01.
2. **Add GAP-30** — "Every Reference page replaces verbatim response JSON with 'Click Try It!' placeholder." Category: docs gap. Severity: HIGH. This is the single biggest Reference-layer deficiency.
3. **Add GAP-31** — "Quotations Reference and Guides describe disjoint schemas (account_type/wallet_* vs base_currency/quote_currency)." Category: docs-vs-docs drift. Severity: **CRITICAL**. Likely top-5 contender for the PM's README.
4. **Add GAP-32** — "`GET /banks` endpoint is unversioned (no `/v1/` prefix), inconsistent with the rest of the surface." Category: versioning / inventory. Severity: HIGH. Touches API9.
5. **Add GAP-33** — "`POST /v1/recipients` Reference page lists 19 polymorphic account-type variants by name but renders no per-variant schema; integrator must cross-read `docs/account-types-reference.md` Guides page." Category: docs gap. Severity: HIGH.
6. **Add GAP-34** — "Reference pages stale relative to Apr-14 changelog (`provider` alias on VA create, stablecoin base on quotations, idempotency on liquidation-address)." Category: docs gap. Severity: HIGH. Reinforces GAP-01.
7. **Update §2.3 (error envelope)** to add the empirical observation that the Reference pages document a *fourth* envelope flavor: **bare-status (no body)** — e.g., `POST /webhooks/register` documents only `200` with no body schema. This is Shape E.
8. **Update §2.2 (header table)** with a "Reference-page-claimed" column that documents which Reference page omits which required header (`Authorization: Bearer` is missing on 5 of 14 pages despite being required at runtime). This is a docs-vs-docs-vs-runtime triangle.
