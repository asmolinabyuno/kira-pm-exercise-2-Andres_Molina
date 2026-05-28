# Kira Guides — Product Catalog (Marketing × API Reality)

> **Lens:** PM channeling `product-manager` agent. We are reading Kira's Guides **as a product brochure**, not as engineering documentation. The question: *if you only read Kira's marketing and Guides, what products would you believe they sell? And does the API actually deliver each of them?*
> **Companion docs (do not duplicate):** `evidence/analysis/08-flow-design.md` (endpoint truth, 30 endpoints, 28 GAPs) · `evidence/analysis/11-docs-coverage-matrix.md` (technical coverage sweep, 13 sidebar sections). This file is the *product-vs-API mismatch* layer.
> **Sources crawled fresh for this pass:** `docs/use-case-product-comparison.md` · `docs/kira-api-overview.md` · `docs/users-and-verification.md` · `docs/verification.md` · `docs/virtual-accounts.md` · `docs/payment-link.md` · `docs/use-cases-remittances-top-up-account.md` · `docs/recipient-management-1.md` · `docs/webhooks-guide.md` · `docs/payouts.md` · `docs/deposits.md` · `docs/getting-started.md`. Plus carry-over from `docs-coverage-matrix.md` for the rest.
> **Date:** 2026-05-27.

---

## 0. Executive read of the brochure

The Guides give an integrator **two competing product taxonomies** to choose from:

1. **The `kira-api-overview` taxonomy.** A loose "all-in-one platform" pitch: "Receive, hold, and disburse international funds with one API." No customer names, no specific bank names, no SLA, no AI claims, no Stellar claims. This page is *bland* — surprisingly so given the company's positioning as "AI + Stellar" infrastructure.
2. **The `use-case-product-comparison` taxonomy (THE GOLD PAGE).** A crisp 5-column matrix naming **Wallets · Payment Link · Virtual Account · cashPay · Payout API** as the catalog. This is the only place in the Guides where Kira commits to a product list. It is therefore the closest thing Kira has to a price-card.

The two taxonomies don't match. `kira-api-overview` names "Virtual accounts, Wallets, Payment links" and trails off into "other financial products." The comparison page promotes **cashPay to a peer of Payment Link** even though the API treats cashPay as a delivery channel inside Payment Link (`barcode_generated` event on a single `POST /v1/payment-link` endpoint).

Beyond the explicit five, the Guides also implicitly market three more capabilities the comparison table doesn't list: **On-Ramps (PayIns)**, **Liquidation Addresses**, and **KYC/KYB Verification** (presented as a prerequisite, not a product). And there are three sidebar entries that **404** (`metadata`, `versioning`, `api-upgrades`) — a 23% dead-link rate that becomes an aggregate finding in its own right.

Net inventory walked through below: **9 distinct products / capabilities** + **3 dead sidebar entries**.

---

## Product 1 — Wallets (custody / stablecoin hold)
**Marketing pitch (from Guides):** "Generate a wallet address on Solana, Polygon, or Tron to hold digital dollars (USDC/T)." (use-case-product-comparison). Pitched as **goal = "Hold Funds"**, operation = "Custody", with **Global coverage**, **No KYC/B required**, **Fully Customizable UI**, **Embedded in Website = ✅**.
**Target use case:** "Treasury management, Payroll & Remittances" for "Freelancers, contractors, Small and Medium-sized Business." (use-case-product-comparison)
**Promises made in Guides:**
- Global geographic coverage (the only product in the catalog claiming Global).
- "Not required" KYC — i.e. a no-friction custody product.
- Three chain options: Solana, Polygon, Tron.
- "Fully Customizable" UI and embeddable in a website.
**Examples given in Guides:** None. No sample request, no sample response, no `/v1/wallets` curl. The product is named in the matrix and never elaborated.
**API endpoints that implement it:**
- `POST /v1/users/{userId}/wallets` — appears **only** in the idempotency.md endpoint list (flow-design §2.4) with no reference page. Not in `llms.txt`. No GET, no LIST, no DELETE documented.
- Tangentially: `account_type: "WALLET"` exists as a payout/recipient option (`token: USDC|USDT|COPm`, `network: polygon|solana|tron`) — but that is a recipient address, not a custody product.

**Contrast — does the API deliver the pitch?**
- Match: Crypto rails (Solana, Polygon, Tron) and stablecoin token list (USDC/USDT) exist in recipient/wallet enums. Customer can definitely send / receive stablecoins on these chains via other endpoints.
- Gap: **There is no published `/v1/wallets` reference page.** No documented "create wallet → get address → query balance → send out" surface. The marketed product is the one product in the matrix with the *thinnest* API surface in the docs.
- Gap: **"No KYC required"** is a strong claim. On the integration side `POST /v1/users/{userId}/wallets` is *under* the user resource — implying you must create a user first, which auto-triggers KYC. The Guides do not reconcile "no KYC required" (matrix) with "wallets attach to users who must be verified" (idempotency.md).
- Gap: "Global coverage" claim has no countries page backing it. `GET /v1/countries` returns 250 countries but the wallet capability is not country-scoped in any reference page we found.
- Undocumented assumption: integrator must already know to call an unpublished endpoint under the user resource. Sales pitch suggests a standalone product; API treats it as a sub-resource.
**Severity of gap:** **HIGH** — a marketed product with no discoverable API surface is the worst kind of trust-breaker for a buyer doing a 2-week eval.
**Related GAP:** **GAP-37 — Wallets product marketed without reference page** (canonical assignment per DEC-005, 2026-05-27). Touches existing GAP-04 (auth model) and GAP-08 (idempotency list inconsistency).

---

## Product 2 — Payment Link (hosted USD request)
**Marketing pitch (from Guides):** "Create a payment link to allow recipients to request a USD payment." (use-case-product-comparison). "Payment Link simplifies international payment requests by allowing recipients to share a link with their contacts in the United States." (payment-link.md). Sold as: integrator does 2 API calls; Kira owns the sender-side UI, sender KYC, and processing.
**Target use case:** "Remittances, Wallet/Bank account Top-Up & Product/Services purchases" for "Individuals, Small and Medium-sized Business" (matrix). Concrete vignettes in `use-cases-remittances-top-up-account.md`: a default *remittance* flow ("Send to [recipient]", with exchange-rate shown) vs a *top-up* flow ("Add funds to wallet", recipient hidden, exchange rate hidden).
**Promises made in Guides:**
- Senders pay via **debit card or cash**.
- Cash payment is redeemable at **"more than 90,000 stores across the United States"** (payment-link.md). The comparison matrix says cashPay (its peer column) covers **"more than 50,000 retail locations"**. *Two numbers, same product line, two different Guide pages* — see Product 4.
- Geographic exclusions: cash unavailable in **New York and Louisiana**; debit-card unavailable in **New York and Alaska**.
- "Limited Customization" UI per the matrix; "the generated payment link can be customized with your brand colors and logo. Fees, texts and payment methods can also be customized." (payment-link.md). *Two pages disagree on whether customization is "Limited" or substantial.*
- Recipient sides: "United States, Mexico, El Salvador, Guatemala (via bank account) or Solana wallets (global)" (payment-link.md). Sender must be U.S.-based.
- Two product modes via `link_type`: default `remittance` vs `link-type: "top-up"`.
**Examples given in Guides:** JSON `{"link-type": "top-up"}` shown for top-up mode (remittance is the empty default). No full sample request/response on this page. Sample payment-link URL pattern: `https://your-domain.kirafin.ai/v3/{txn_uuid}`. Redirect contract: `?status=success` / `?status=cancelled` appended.
**API endpoints that implement it:**
- `POST /v1/payment-link` (flow-design §3.9) — single endpoint. No GET, no LIST, no PATCH, no DELETE documented.
- Webhook events: `card_payment`, `barcode_generated`.

**Contrast — does the API deliver the pitch?**
- Match: hosted URL exists, webhook events exist for both payment paths, debit + cash channels are documented in the changelog inventory.
- Gap: **Customization claim is contradictory.** Matrix page says "Limited Customization." `payment-link.md` says "brand colors and logo. Fees, texts and payment methods can also be customized." Buyer comparing column-by-column will believe "Limited"; integrator reading the deep page will expect more knobs. The actual `POST /v1/payment-link` request schema is not enumerated for customization fields in either page.
- Gap: **Retail-location count disagrees with itself.** `payment-link.md` says **90,000**; the comparison matrix says **50,000**. (And the flow-design notes "50-90k" which means they're hedging.)
- Gap: **No payment-link GET / lifecycle.** Once created, there is no way (in docs) to read its status, list links, cancel, or rotate the URL. The only signal is the webhook.
- Gap: **No link-expiry policy.** Guides don't say how long a link is valid.
- Gap: **No `acct_info` country variance enumeration.** The body's `acct_info` "varies by country" per flow-design §3.9, but neither Guide page documents what shape per country.
- Undocumented assumption: sender is U.S.-based — buyer in another market will mis-position this as "Payment Link for global senders."
**Severity of gap:** **MEDIUM** for self-contradiction, **HIGH** for missing GET/list (production ops can't reconcile what they sold without webhook archive).
**Related GAP:** GAP-12 (legacy `card_payment` / `barcode_generated` events vs modern dot-namespacing). Open-redirect risk on `redirect_url` is a separate security finding flagged in docs-coverage-matrix §7.

---

## Product 3 — Virtual Account (USD receive via US rails)
**Marketing pitch (from Guides):** "Open a US virtual account to receive Wire & ACH transfers from any US bank." (use-case-product-comparison, also virtual-accounts.md). Goal = "Receive Funds in USD." Operation = "Pay-in." Coverage = "United States."
**Target use case:** "Payroll, Remittances & Suppliers payments" for "Freelancers, contractors, Small and Medium-sized Business" (matrix). Use-case prose in virtual-accounts.md mentions "remote workers, treasury management, payment aggregation."
**Promises made in Guides:**
- Receive via **ACH ("1-3 business days," "Low/free for sender")** and **Wire ("same day or next day," "$15-$50 for sender")** (virtual-accounts.md).
- Partner banks: **Portage (non-US users)**, **Austin Capital Trust (US-based users)**, **Slovak Savings Bank (sandbox only)** (virtual-accounts.md). The deprecated `lead_bank` is "no longer supported."
- KYC/B required for account holders (matrix).
- "Fully Customizable" UI; "Embedded in Website = ✅" (matrix).
- Two account-creation shapes per April-14 changelog: `usa-virtual-accounts` (Portage, heavier KYC) and `usa-virtual-accounts-act` (ACT, lighter KYC). (flow-design §3.2.2)
**Examples given in Guides:**
- Two cURL examples (crypto mode and fiat mode VA creation) in virtual-accounts.md.
- JSON response samples in same.
- Recipe A in flow-design §4.1 captures the full onboarding chain (auth → user → verify → create VA → wait for `virtual_account.activated` → deposit instructions populated).
**API endpoints that implement it:**
- `POST /v1/virtual-accounts` (create)
- `GET /v1/virtual-accounts/{id}` (read)
- `GET /v1/virtual-accounts` (list)
- `GET /v1/users/{userId}/virtual-accounts` (list by user)
- `GET /v1/virtual-accounts/{id}/balance` (fiat mode only)
- `GET /v1/virtual-accounts/{id}/deposits` and `/deposits/{depositId}`

**Contrast — does the API deliver the pitch?**
- Match: VAs, deposit instructions, balances, deposits list — all documented endpoints.
- Match: ACH + Wire rails — both supported and documented.
- Gap: **CLAUDE.md and `product-manager` system prompt claim "FedNow / RTP / Wire / ACH" as inbound rails. virtual-accounts.md claims ONLY ACH + Wire.** The Guides under-sell what the brochure says — or the brochure over-sells what the Guides commit to. The 4-rail claim cannot be verified from public docs. (Flow-design §1 and the payouts.md page confirm FedNow on the *outbound* side as `INSTANT_PAY`. There is no inbound-FedNow surface documented for a VA.) → finding-candidate: **inbound-FedNow / RTP marketed in CLAUDE/brochure but not in Guides.**
- Gap: **FDIC-insured claim absent.** CLAUDE.md, `product-manager.md`, and external Kira brand pages claim "FDIC-insured via 4 US partner banks." The Guides name **3 banks** (Portage / ACT / Slovak Savings), and the FDIC claim does not appear anywhere on `virtual-accounts.md`. Where's bank #4? Slovak Savings is "sandbox only" — so production has 2. The "4 FDIC-insured" claim is unverifiable from Guides.
- Gap: **No "USA / Mexico / Colombia virtual account" sub-flavors in the Guides.** The exercise mentions these as if they exist. The Guides describe only `US_BANK` and only USA-located accounts. The `usa-virtual-accounts` / `usa-virtual-accounts-act` product *codes* are real (changelog) but they are both USA variants — they are not the Mexico / Colombia VA products we expected. → finding-candidate: **no Mexico / Colombia virtual accounts documented**, despite external positioning.
- Gap: **"Same business day" vs "Same day or next day" — Wire timing is inconsistent.** payouts.md says "same business day (domestic)"; virtual-accounts.md says "same day or next day." Choose one.
- Gap: **No SLA / latency on VA activation.** `pending → active` time is unspecified.
- Undocumented assumption: "Embedded in Website = ✅" — there is no hosted-page surface for VA onboarding. The only UI shown is KYC's `verification_link`. How is a VA "Embedded in Website"? Likely the matrix is overclaiming.
**Severity of gap:** **HIGH** — the rails coverage discrepancy (FedNow/RTP missing inbound) plus the bank-inventory discrepancy plus the missing Mexico/Colombia VA hits buyer-trust directly.
**Related GAP:** GAP-22 (sandbox deposit simulation undocumented), GAP-27 (no close-VA endpoint).

---

## Product 4 — cashPay (cash-payment barcode in US retail)
**Marketing pitch (from Guides):** "Generate barcodes that enable cash payments at more than 50,000 retail locations across the United States." (use-case-product-comparison). Goal = "Receive Funds in USD." Operation = "Pay-in." Sold to "Unbanked individuals in the United States."
**Target use case:** "Payroll, Remittances, Wallet/Bank account Top-Up & Prepaid card funding." Ideal for "Unbanked individuals in the United States."
**Promises made in Guides:**
- Coverage of "more than 50,000" US retail locations.
- "Required" KYC for users completing cash payments.
- "Limited Customization" UI.
- "Embedded in Website = ✅".
- Senders are explicitly individuals (the only product where "Who can use it?" = "Individuals" only, not "Individuals & Business").
**Examples given in Guides:** None on the comparison page. The `payment-link.md` page treats cash redemption as a *feature of Payment Link*, not as a separate product — using "90,000 stores" not 50,000.
**API endpoints that implement it:**
- `POST /v1/payment-link` (same endpoint as Product 2) — with cash selected as a payment method. No separate `/v1/cashpay` endpoint exists.
- Webhook: `barcode_generated`.

**Contrast — does the API deliver the pitch?**
- Match: cash redemption is real (barcode flow + `barcode_generated` webhook).
- Gap: **cashPay is not a separate product in the API.** The matrix sells it as one of the 5 products — a column equal in weight to Wallets, Virtual Account, Payout API. The API treats it as a *delivery method* inside `POST /v1/payment-link`. A buyer reading the matrix expects a `/v1/cashpay` endpoint and a separate integration path. They get neither. **This is the most clear-cut marketing-vs-API mismatch in the catalog.**
- Gap: **50,000 (matrix) vs 90,000 (payment-link.md) retail-location count.** Same product line, two pages, two answers. Pick one and commit.
- Gap: **No sample cashPay request in Guides.** The only way to figure out how to issue a barcode is to reverse-engineer the Payment Link body schema and webhook events.
- Undocumented assumption: integrator must know cashPay lives inside Payment Link, not at its own resource path.
**Severity of gap:** **HIGH** — taxonomy drift on the only page where Kira lists its products is a direct trust hit. A salesperson can mis-quote effort.
**Related GAP:** GAP-12 (legacy event `barcode_generated` not dot-namespaced).

---

## Product 5 — Payout API (off-ramp / fiat disbursement)
**Marketing pitch (from Guides):** "Transfer funds to local bank accounts in fiat currency." (use-case-product-comparison). Goal = "Convert & Transfer Funds in Fiat." Operation = "Pay-out." Sold for "Wallet/Bank account withdrawals & Remittances" to "Individuals and Small and Medium-sized Business in LATAM."
**Target use case:** Per matrix, "Individuals and SMBs in LATAM" — specifically wallet withdrawals and remittance. payouts.md frames it as: "send funds from a virtual account to a recipient's bank account via ACH, WIRE, SWIFT, or INSTANT_PAY (FedNow)."
**Promises made in Guides:**
- Coverage: **"14 LATAM countries plus USA"** (matrix). Note: payouts.md itself does NOT enumerate the 14 LATAM countries. The recipient reference (account-types-reference.md / flow-design §3.5) catalogues 14 fiat account types: SPEI (MX), PSE (CO), BRL, ARS, CLP, PEN, PEUSD, UYU, DOP, ECUSD, CRC, GTQ, PAUSD, PYG, SVUSD — that's **15 fiat account types, not 14.** Off-by-one or PEUSD/PAUSD count as USD overlays?
- Speed claims (payouts.md, verbatim):
  - **"INSTANT_PAY (FedNow) settles in seconds, 24/7/365"**
  - Wire = "Same business day (domestic)"
  - ACH = "1-3 business days"
  - SWIFT = "3-5 business days"
- "Fully Customizable" UI per the matrix — but there's no hosted UI for payouts in the API; this is server-to-server only. The matrix overclaims here too.
- "Embedded in Website = ✅" — same overclaim.
- "KYC/B = Not Required" per the matrix — but flow-design §4.2 shows you cannot create a VA (the source of funds) until the user is `VERIFIED`. So KYC is required upstream even if Payouts API itself doesn't gate it. Misleading column.
- Pricing: **"Fee configuration varies by client. Contact your account manager for specific fee details."** No public rate card.
- OTP gate via `x-validation-header` for fiat payouts (optional, risk control).
**Examples given in Guides:**
- Settlement timeline table (above).
- Recipe B (USD → MXN via SPEI) in flow-design §4.2 — full curl chain.
- Recipe D (USD → SWIFT EUR) in flow-design §4.4.
- payouts.md has invoice-reference and "consulting service payments" as memo text examples — no customer story prose.
**API endpoints that implement it:**
- `POST /v1/virtual-accounts/{id}/payout`
- `POST /v1/virtual-accounts/{id}/payout/preview`
- `GET /v1/payouts`, `GET /v1/payouts/{id}`
- `POST /v1/quotations` (FX rate locking, 10-min TTL)
- `POST /v1/recipients` (saved destinations)

**Contrast — does the API deliver the pitch?**
- Match: the rails, FedNow speed claim, 14-ish currencies, SWIFT, OTP gating, quote-then-payout flow — all implemented.
- Gap: **"Fully Customizable / Embedded in Website = ✅" makes no sense for Payouts.** This is a server-to-server resource. Either the matrix is wrong, or there's an unlisted hosted-payouts UI we couldn't find in the Guides.
- Gap: **"KYC/B = Not Required" misleads.** Source-of-funds VA *does* require KYC. Buyer reading the matrix may believe Payouts is a low-friction product when in fact it inherits the heaviest onboarding in the catalog.
- Gap: **No published 14-country list.** The matrix names a number; no Guide page enumerates the 14. Currency count from account types is 15 (or 13 if you net out USD-overlay variants). Pick one source of truth.
- Gap: **No pricing.** "Contact your account manager" is fine for sales but blocks an evaluator from comparing TCO during a 2-week PM exercise.
- Gap: **GAP-18 — `GET /v1/payouts` mandates `user_id`** — no client-wide payout feed. Audit/reconciliation users hit this on day 1.
- Gap: **GAP-19 — Payout status enum casing disagrees across pages** (`pending` lowercase in guide, `PENDING` uppercase in detail schema, `returned` missing from detail entirely).
- Gap: **GAP-28 — No documented "cancel payout" endpoint** even though `CANCELLED` is a valid filter value.
- Undocumented assumption: payouts only work *out of* a fiat-mode VA. If you opened a crypto-mode VA expecting it to pay out fiat, you'll discover this at runtime.
**Severity of gap:** **MEDIUM** for column-overclaim, **HIGH** for the cluster of state-machine + audit-list + pricing gaps.
**Related GAP:** GAP-18, GAP-19, GAP-23 (OTP endpoint named but no reference page), GAP-28.

---

## Product 6 — On-Ramps / PayIns (fiat → stablecoin)
**Marketing pitch (from Guides):** **NOT in the use-case-product-comparison matrix at all.** `kira-api-overview` mentions "Receive, hold, and disburse" but doesn't single out on-ramps. The clearest pitch is buried in the brief / external Kira positioning: **"On-Ramps — USD → USDT/USDC. Volume-tiered pricing."**
**Target use case:** Per flow-design §3.8: take MXN via SPEI (Mexico) or COP via PSE (Colombia), settle to a stablecoin wallet (Polygon / Solana / Tron). USD via ACH was also a documented inbound option in flow-design §1, but the PayIn reference page only enumerates SPEI and PSE today.
**Promises made in Guides:**
- SPEI is "reusable" (multi-deposit); PSE is single-use.
- Settlement always lands in a stablecoin wallet (no fiat-to-fiat).
- Apr-14 changelog confirms PayIn states: `CREATED|PENDING|PROCESSING|COMPLETED|FAILED|REFUNDED`.
**Examples given in Guides:** Recipe C in flow-design §4.3 (MXN → USDT via SPEI). No customer story.
**API endpoints that implement it:**
- `POST /v1/payins/fees`
- `POST /v1/payins`
- `GET /v1/payins/{payinId}`

**Contrast — does the API deliver the pitch?**
- Match: SPEI + PSE → stablecoin endpoint chain is real and documented.
- Gap: **On-Ramps is one of Kira's three named product lines (per CLAUDE.md and `product-manager`) but is INVISIBLE in the Guides' product-comparison matrix.** A buyer looking at the comparison page would not know On-Ramps exists. This is the inverse of Product 1 (Wallets) — marketed as a top-line product but the Guides matrix doesn't list it.
- Gap: **GAP-24 — Verification requirement for PayIn users is undocumented.** Is KYC required to receive a SPEI/PSE collection? Silent.
- Gap: **GAP-25 — PayIn settlement SLA absent.** "Same-day SPEI" is folklore, not contract.
- Gap: **GAP-13 — PayIn state machine partial.** `REFUNDED` and `FAILED` triggers are undocumented.
- Gap: **USD ACH on-ramp claimed in flow-design §1 / CLAUDE.md but the PayIn reference only documents SPEI + PSE.** Where's the USD on-ramp endpoint? → finding-candidate.
- Undocumented assumption: integrator must already know "On-Ramps = PayIns" — those words aren't interchanged in the Guides.
**Severity of gap:** **HIGH** — a top-level product line is missing from the product-comparison page entirely.
**Related GAP:** GAP-13, GAP-24, GAP-25 + new: PayIns absent from product comparison.

---

## Product 7 — Liquidation Addresses (auto-sweep stablecoin → fiat)
**Marketing pitch (from Guides):** Not in the use-case-product-comparison matrix. Lives only in the reference pages. Flow-design §3.10 describes it as: "Auto-sweep stablecoin → USD → recipient bank."
**Target use case:** Embedded payouts triggered by inbound stablecoin. A counterparty sends USDC/USDT to the liquidation address; Kira auto-converts to USD and pushes to a pre-configured ACH/WIRE recipient.
**Promises made in Guides:**
- USDC on solana/polygon; USDT on solana/polygon/tron.
- Cumulative stats on `GET` (`total_deposits`, `total_amount_received`, `total_amount_paid_out`).
- Pre-req: VA must be `US_BANK` + `active`, user verified.
**Examples given in Guides:** Recipe E in flow-design §4.5. No standalone Guide page found in the sidebar — discoverable only via reference.
**API endpoints that implement it:**
- `POST /v1/virtual-accounts/{id}/liquidation-address`
- `GET /v1/virtual-accounts/{id}/liquidation-address`

**Contrast — does the API deliver the pitch?**
- Match: endpoints exist; flow is implementable.
- Gap: **Not in the comparison matrix.** Same problem as PayIns — a real product the buyer can't discover from the brochure.
- Gap: **GAP-26 — recipient is embedded inline in the create payload; not a `recipient_id` reference.** This means liquidation address recipients live in a parallel namespace to Recipients (Product 8). Two recipient shapes coexist.
- Gap: **No latency/SLA on the auto-sweep** (how soon after stablecoin lands does USD reach the bank?).
- Gap: **No update/rotate flow** for the liquidation address or its embedded recipient.
- Undocumented assumption: integrator must know to look in `virtual-accounts/{id}/liquidation-address` (a sub-resource path), not in a top-level Guide.
**Severity of gap:** **MEDIUM** — useful product, completely invisible to a buyer reading the matrix.

---

## Product 8 — Recipients (saved payout destinations)
**Marketing pitch (from Guides):** **None.** `recipient-management-1.md` is pure plumbing — "no value propositions, customer benefits, or marketing claims" (fetched 2026-05-27). `account-types-reference.md` is a 22-type schema reference. The parent `recipients` sidebar entry is a **stub landing page** with no content (per docs-coverage-matrix §5).
**Target use case:** Save once → pay many times. Implicit support for repeat-payout flows.
**Promises made in Guides:**
- 22+ account types (flow-design §3.5).
- Masking of `account_details` on read (`account_number: "****7890"`).
- Idempotency-required on create.
**Examples given in Guides:** Recipient-create curls in account-types-reference.md (ACH, SWIFT, Germany example). No customer story.
**API endpoints that implement it:**
- `POST /v1/recipients`
- `GET /v1/recipients?user_id={uuid}` (filter required)
- `GET /v1/recipients/{recipientId}`

**Contrast — does the API deliver the pitch?**
- Match: 22 account types are real and documented.
- Gap: **Recipients is treated as plumbing in Guides but is the single most schema-heavy resource in the API.** A buyer should care about this (it's the data model for every payout destination they'll ever store) but the brochure invisibilizes it. Underselling, not overselling.
- Gap: **GAP-15 — `GET /v1/recipients` is not paginated.** A high-volume integrator gets an unbounded list.
- Gap: **GAP-16 — `bank_address` typing differs between ACH (string) and WIRE (object).** Cross-rail shared TypeScript interface breaks.
- Gap: **GAP-17 — Spanish-language enum values on CLP recipients** (`"Cuenta corriente"`, etc.). Type-safety ugly.
- Gap: **GAP-26 — Liquidation embeds recipient inline; payouts use `recipient_id`.** Two recipient shapes coexist.
- Gap: **The sidebar parent `recipients` 200s but renders no content** (stub).
**Severity of gap:** **MEDIUM** — recipients is plumbing, not a product per se, but the stub-parent + schema drift hurts integrator confidence.

---

## Product 9 — KYC/KYB Verification (a capability presented as a prerequisite)
**Marketing pitch (from Guides):** "Automatic Verification (Recommended): When you create a user with all required fields, the verification process starts automatically in the background. No additional API calls are needed." (users-and-verification.md). NOT pitched as a sellable product on its own. `verification.md` frames it as: "Before a user can create a virtual account, they must complete identity verification."
**Target use case:** Background compliance for everything else. Auto-trigger on user create; legacy manual flow still supported via `POST /v1/users/{id}/verifications` ("will be deprecated").
**Promises made in Guides:**
- Sandbox auto-approves verifications.
- Webhook events: `user.verification.accepted` / `user.verification.failed`.
- USA vs International branch driven by `nationality` / `formation_country` / `address_country`.
- Two product onboarding shapes per April-14 changelog: Portage (heavier — gov ID photos required) vs ACT (lighter — SSN + employment + immigration status).
**Examples given in Guides:** Curl for automatic verification with full SSN/passport payload. Three webhook payloads. Legacy two-step flow example.
**API endpoints that implement it:**
- `POST /v1/users` (auto-trigger)
- `POST /v1/users/{userId}/verifications` (legacy)
- `GET /v1/users/{userId}` (poll status)

**Contrast — does the API deliver the pitch?**
- Match: auto-verify on create is real; sandbox auto-approves; webhook chain is real.
- Gap: **No KYC vendor named.** "Powered by" is silent. Is it Persona? Sumsub? Onfido? Internal? An evaluator cannot audit the compliance chain.
- Gap: **No turnaround-time SLA.** "Runs in the background" — minutes? Hours? Days?
- Gap: **No "AI compliance" claim, despite Kira's brand being "AI agents."** This is interesting — the brand promises AI, the docs are silent. Either the AI is invisible to integrators, or it's a brand-positioning artifact with no Guide-level commitment.
- Gap: **GAP-14 — Dual enum** for user status (modern UPPERCASE `CREATED|VERIFYING|VERIFIED|REJECTED|REVIEW` vs legacy lowercase `unverified|started|in_review|verified|rejected|needs_action`, plus legacy `ACTIVE|INACTIVE|SUSPENDED` on the list filter). Mapping undocumented.
- Gap: **No "supported KYC countries" list.** Examples are all USA. International branch exists but the country eligibility for KYC is silent.
- Gap: **No re-verify SLA / re-verify lifecycle**. PUT to a sensitive field flips `requires_reverification` but the next-step timing is undocumented.
- Undocumented assumption: KYC happens silently and instantly in sandbox; integrator deploys to prod expecting the same and discovers it's a multi-minute (or longer) async flow with no SLA.
**Severity of gap:** **HIGH** — compliance is the foundation; vendor anonymity + dual enum + zero SLA together is a deal-blocker for a regulated buyer.

---

## Dead sidebar entries (3 products that don't exist)

These appear on the Guides sidebar but 404. From docs-coverage-matrix §11/§12/§13.

### Sidebar entry 10 — `metadata`
**Marketing pitch:** Sidebar implies a `metadata` capability (every modern payments API has integrator metadata for reconciliation — Stripe, Plaid, etc.).
**Reality:** **404 Not Found.** No `metadata` field documented on any endpoint. Probe needed to find out if `metadata` is accepted on POSTs and silently dropped, or accepted-and-echoed without docs.
**Severity:** **HIGH** — every payments-platform buyer expects metadata for reconciliation.

### Sidebar entry 11 — `versioning`
**Marketing pitch:** The April-14 changelog promised "API Versioning page added under Getting Started" and announced an `X-Api-Version` header.
**Reality:** **404 Not Found.** `X-Api-Version` is announced but never specified. → GAP-01 (already in flow-design top-5 seeds).
**Severity:** **CRITICAL** — buyer cannot pin a schema version. Existing top-5 candidate.

### Sidebar entry 12 — `api-upgrades`
**Marketing pitch:** Sidebar implies a deprecation / migration / EOL policy.
**Reality:** **404 Not Found.** No upgrade policy, no semver commitment, no deprecation timeline. → **GAP-35** (canonical per DEC-005).
**Severity:** **HIGH** — multi-year enterprise contracts (Banco Industrial, N1co) cannot be signed without an upgrade contract.

**The pattern:** 3 of 13 sidebar entries 404 = **23% dead-link rate**. By itself this is a Pillar-1 (Findability + Completeness) catastrophe and a candidate for its own top-5 finding.

---

## Aggregate — Products inventory

| # | Product | API-backed? | Examples in docs? | Gap severity |
|---|---|---|---|---|
| 1 | Wallets | **PARTIAL** — `/v1/users/{id}/wallets` is in idempotency list only, no reference page | None on the comparison page; none anywhere | **HIGH** |
| 2 | Payment Link | YES — `POST /v1/payment-link` | Brief; redirect contract shown; no full sample | **MEDIUM** |
| 3 | Virtual Account | YES — full VA family of endpoints | curls + Recipe A; rails undersold | **HIGH** |
| 4 | cashPay | NO standalone — collapses into Payment Link's barcode flow | Mentioned as a method, not a product | **HIGH** (taxonomy drift) |
| 5 | Payout API | YES — full payout + quotation + recipient family | Recipes B + D | **MEDIUM** (column overclaim) + **HIGH** (state/casing gaps) |
| 6 | On-Ramps (PayIns) | YES — `POST /v1/payins` family | Recipe C; no marketing | **HIGH** (invisible in matrix) |
| 7 | Liquidation Addresses | YES — `/v1/virtual-accounts/{id}/liquidation-address` | Recipe E; no Guide page | **MEDIUM** (invisible in matrix) |
| 8 | Recipients | YES — full recipients family | Curls in account-types-reference; sidebar parent is a stub | **MEDIUM** |
| 9 | KYC/KYB Verification | YES — auto-trigger on POST /v1/users | Curls + webhook payloads | **HIGH** (no vendor, no SLA, dual enum) |
| 10 | `metadata` (sidebar) | UNKNOWN — page 404s | None | **HIGH** |
| 11 | `versioning` (sidebar) | NO — header announced, never specified | None | **CRITICAL** (GAP-01) |
| 12 | `api-upgrades` (sidebar) | NO — page 404s | None | **HIGH** |

---

## Aggregate — Use-case × Product matrix (from Guides, annotated)

Reproduced from `use-case-product-comparison.md`. ✅ = the API delivers that cell as marketed. ⚠️ = partial / qualified delivery. ❌ = the matrix overclaims; the API does not deliver as stated.

| Aspect | Wallets | Payment Link | Virtual Account | cashPay | Payout API |
|--------|---------|--------------|-----------------|---------|-----------|
| **Goal** | Hold Funds | Receive Funds in USD | Receive Funds in USD | Receive Funds in USD | Convert & Transfer Funds in Fiat |
| **Operation Type** | Custody | Pay-in | Pay-in | Pay-in | Pay-out |
| **Description (matrix)** | ⚠️ Endpoint not in reference | ✅ | ⚠️ Inbound rails undersold (no FedNow/RTP) | ❌ Not a separate product in API | ✅ |
| **Common Use Cases** | ⚠️ unverifiable (no surface) | ✅ | ✅ | ✅ via Payment Link | ✅ |
| **Who can use it?** | Both | Both | Both | Individuals only | Both |
| **Ideal for** | Freelancers/SMBs | Individuals/SMBs | Freelancers/SMBs | Unbanked US individuals | LATAM individuals/SMBs |
| **Integration Effort** | Medium | Low | Medium | Medium | Medium |
| **UI Customization** | ⚠️ Fully Customizable (no UI exists per public docs) | ⚠️ "Limited" (matrix) vs "brand colors+logo+fees+texts" (deep page) — contradiction | ⚠️ Fully Customizable (no UI exists for VA onboarding in docs) | "Limited" | ❌ "Fully Customizable" — server-to-server API, no UI |
| **Embedded in Website** | ⚠️ ✅ claimed; no embed page documented | ✅ | ⚠️ ✅ claimed; no embed page documented | ⚠️ ✅ (via Payment Link) | ❌ ✅ claimed — but it's a server API |
| **Supported Payment Methods** | Cash/Debit/ACH/Wire | Cash/Debit | ACH/Wire | Cash | N/A |
| **Supported Countries** | ⚠️ "Global" — unverifiable | US senders only | ⚠️ US only; no Mexico/Colombia VA documented | US | "14 LATAM + USA" — list never enumerated |
| **User KYC/B** | "Not Required" — ⚠️ but Wallet attaches to a user resource | "Required for payers" | "Required for holders" | "Required for cash payers" | ❌ "Not Required" — but source-of-funds VA *does* require KYC |
| **Evidence of transaction** | Not Required | Not Required | Might Be Required | Not Required | Might Be Required |

**Aspirational cells (cells the matrix overclaims):**

- "Fully Customizable / Embedded in Website" for **Wallets, Virtual Account, Payout API** — no hosted UI surface exists in the public docs for any of these. The buyer reading the matrix will believe Kira ships embed widgets for all 5 products. They ship one (Payment Link) and arguably zero others.
- "Not Required" KYC for Payouts — misleading because the source VA *does* require it.
- "Global" countries for Wallets — no countries page commits to this.
- "14 LATAM countries" for Payouts — number is unverifiable from the docs.

---

## Aggregate — Top product-vs-API mismatches (ranked by integrator confusion impact)

### Mismatch #1 — Wallets is on the matrix but has no reference page
**Marketing says:** "Generate a wallet address on Solana, Polygon, or Tron to hold digital dollars" — global, no KYC, custody product.
**API does:** `POST /v1/users/{userId}/wallets` appears once, in the idempotency.md endpoint list (flow-design §2.4). No reference page in `llms.txt`. No GET, no LIST, no balance, no transfer endpoint published.
**Why this hurts a real client:** A buyer doing a 2-week eval will read the matrix, pick Wallets as their primary product (it's the only "Global, No KYC" cell), and then spend 4 days trying to find the endpoint. By the time they raise the support ticket, the deal is already losing momentum. This is the single worst trust hit in the catalog.

### Mismatch #2 — cashPay is marketed as a peer product but is a delivery method inside Payment Link
**Marketing says:** Column equal in weight to Wallets, Virtual Account, Payout API. Distinct goal, distinct use case, distinct UI claim.
**API does:** No `/v1/cashpay` endpoint. Cash is a payment method on `POST /v1/payment-link`; the only "cashPay" trace in the API is the `barcode_generated` webhook event.
**Why this hurts a real client:** A sales engineer demos cashPay to an Unbanked-focused fintech (the matrix's named ideal customer); the prospect's engineer reads the docs and realizes it's the same endpoint as Payment Link. Differentiation collapses. *Worse:* the matrix claims 50k locations while payment-link.md claims 90k locations. The deal gets re-priced based on a number that's wrong on the same docs portal.

### Mismatch #3 — "Embedded in Website ✅" claimed for Virtual Account / Payout API / Wallets — no embed surface exists
**Marketing says:** All 5 products check ✅ in the "Embedded in Website" column.
**API does:** Only Payment Link has a hosted URL (`https://your-domain.kirafin.ai/v3/{txn_uuid}`). Virtual Account creation is a server POST; the only hosted-page artifact in the user flow is the KYC `verification_link` URL. Payouts is server-to-server. Wallets has no documented hosted page.
**Why this hurts a real client:** A non-technical buyer compares Kira's matrix to a competitor's (e.g., Stripe Connect's onboarding embed, or Persona's hosted KYC). Kira's 5/5 ✅ row looks dominant on the comparison slide — and is unverifiable. By the time engineering discovers there are no embed widgets, the salesperson has already promised a UI integration timeline.

### Mismatch #4 — Top-line "On-Ramps" product line is invisible in the comparison matrix
**Marketing says:** External Kira positioning (CLAUDE.md, brand) says "three product lines: Virtual USD Accounts, On-Ramps, Off-Ramps." Comparison matrix says five products. **On-Ramps is in neither the matrix nor the api-overview page.**
**API does:** `POST /v1/payins/*` family is fully real (SPEI MX, PSE CO, → USDC/USDT on Polygon/Solana/Tron).
**Why this hurts a real client:** A buyer with a remittance use case ("I want to take MXN locally and settle to USDC") cannot find this in the Guides matrix. They look at the matrix, see no "on-ramp" column, and conclude Kira doesn't do it. Lost deal from a documentation gap alone.

### Mismatch #5 — KYC vendor anonymity + dual-enum + no SLA — compliance is unverifiable
**Marketing says:** "Automatic Verification (Recommended): verification process starts automatically in the background."
**API does:** Verification works, sandbox auto-approves, two parallel enums (`CREATED|VERIFYING|VERIFIED|REJECTED|REVIEW` modern + `unverified|started|in_review|verified|rejected|needs_action` legacy), no vendor named, no turnaround time, no country eligibility list.
**Why this hurts a real client:** Regulated buyers (Banco Industrial, N1co) require vendor attestation as part of their compliance review. "Powered by ?" doesn't pass a vendor-risk questionnaire. Combine with the dual enum (GAP-14) and the lack of an SLA, and the compliance-team gate becomes a multi-week back-and-forth — not a buyer-pleasing first impression.

### Mismatch #6 (bonus) — Inbound FedNow / RTP claimed externally but not in Guides
**Marketing says:** CLAUDE.md says "Virtual USD Accounts. Inbound rails: FedNow, RTP, ACH (same-day/standard), Wire (domestic/international)." `product-manager.md` repeats the same claim.
**API does:** virtual-accounts.md documents only ACH + Wire as inbound. FedNow appears only as `INSTANT_PAY` *outbound* in payouts.md. There is no documented inbound-FedNow surface on a VA.
**Why this hurts a real client:** A US fintech buying based on "we'll receive FedNow into our VA" discovers at runtime that the deposit instructions returned by `virtual_account.activated` are ACH/Wire only.

---

## Aggregate — Suggested findings to add to README top-5 candidates

These are the product-vs-API mismatches we'd rank against the existing top-5 seeds (GAP-01, GAP-05, GAP-11, GAP-22, GAP-20).

1. **Wallets product marketed without an API reference page** (Mismatch #1) — **promote to top-5 candidate**. Severity HIGH–CRITICAL. Pillar 1 (Completeness) + Pillar 2 (Time-to-First-Call). Even worse than GAP-22 (sandbox simulation) because GAP-22 is a single missing endpoint; Wallets is an entire product line with no published surface.
2. **Use-case-product-comparison matrix systematically overclaims** (Mismatches #2, #3, #4 bundled). The single page Kira uses to sell its product taxonomy has internal-vs-deep-page contradictions (50k vs 90k retail locations, "Limited" vs "brand colors customizable", 5/5 ✅ embed claims) and omits two real product lines (On-Ramps + Liquidation). **Bundle as one finding: "Product comparison page is the primary source of buyer confusion."** HIGH.
3. **Sidebar 23% dead-link rate** (`versioning` + `metadata` + `api-upgrades` all 404) — already a top-5 seed via GAP-01, but the *pattern* deserves promotion above the individual page. Brings versioning, deprecation, AND reconciliation into one finding.
4. **KYC vendor anonymity + dual enum + no SLA** (Mismatch #5) — keep as a HIGH that may or may not crack top-5 depending on whether GAP-05 (error envelope) or GAP-11 (webhook semantics) win on integrator-pain.
5. **Inbound FedNow / RTP claim drift** (Mismatch #6) — a precision finding the PM can use to demonstrate runtime-vs-docs congruence (Pillar 3). Worth a MEDIUM, possibly HIGH for US-fintech-segment buyers.

---

## Appendix — Quotes worth saving for the README / outreach

Concrete phrases from the Guides that an evaluator can drop into Slack to @Nicolle / @Diego:

- **Matrix on cashPay:** "Generate barcodes that enable cash payments at more than **50,000 retail locations** across the United States." vs **payment-link.md:** "**90,000 stores across the United States**." — *which number is correct?*
- **Matrix on Wallets:** "Generate a wallet address on Solana, Polygon, or Tron to hold digital dollars (USDC/T)." — *where is the `/v1/wallets` reference page?*
- **Matrix on Payouts:** "User KYC/B: Not Required" — *but the source VA requires KYC. Is this column misleading?*
- **Matrix on Payouts:** "Supported Countries: 14 LATAM countries plus USA" — *please publish the list. Account-types-reference enumerates 15 fiat account types.*
- **Matrix on all 5 products:** "Embedded in Website: ✅" — *which hosted-page URLs exist beyond Payment Link's `/v3/{txn_uuid}`?*
- **api-overview pitch:** "Receive, hold, and disburse international funds with one API" — *and yet On-Ramps and Liquidation are invisible on the comparison page. Intentional?*
- **users-and-verification.md:** "verification process starts automatically in the background" — *who is the KYC vendor? what is the turnaround SLO?*
- **April-14 changelog:** "API Versioning page added under Getting Started" — *the page at /docs/api-versioning is 404.*
- **virtual-accounts.md:** Lists ACH + Wire only as inbound rails. *CLAUDE.md and external positioning claim FedNow + RTP inbound — please reconcile.*
- **payouts.md:** "Fee configuration varies by client. Contact your account manager." — *can we get a public rate card for sandbox evaluators?*
