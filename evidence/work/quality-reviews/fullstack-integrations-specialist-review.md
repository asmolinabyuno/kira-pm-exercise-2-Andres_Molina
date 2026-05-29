# Full-Stack Integrations Specialist Quality Review

**Reviewer lens:** Full-Stack Integrations Specialist (consumer-side counterpart to the data-engineer).
**Scope:** pre-publish review of the Kira PM Exercise 2 deliverable, focused on the hosted-page / SDK / payment-link / serverless-receiver / mobile angles that raw-HTTP probes miss.
**Date:** 2026-05-28.
**Coordination:** Read-only review. Do NOT modify any deliverable file.

---

## TL;DR

The deliverable is **shippable as a backend-API evaluation**, and the four security findings (#2 webhook triple-vector, #3 PII unmasked, #4 TLS 1.0/1.1, #5 sandbox base URL) are independently strong. **But the README never says "this is a backend-only view."** A full-stack integrator reading the top-5 walks away thinking Kira's worst integration problems are the ones listed — when in fact the entire hosted-onboarding surface (`verification_link` → `verify.aiprise.com`), the payment-link product (`/v1/payment-link`), and the serverless-webhook-receiver patterns were never probed. That gap is acknowledged inside `11-docs-coverage-matrix.md` (rows §4, §7, §8 list explicit `fullstack-integrations-specialist` TODOs) and inside Bucket E of `13-docs-vs-partner-guide-delta.md`, but it does not surface in the README the buyer reads. Verdict: **ship YES with one mandatory README caveat** ("this evaluation covers the raw HTTP surface; hosted pages, payment links and serverless-receiver patterns were not executed in this pass — see § Coverage").

---

## What's strong

1. **The full-stack-relevant probes that were planned are well-documented.** `evidence/analysis/11-docs-coverage-matrix.md` §4 (Users), §7 (Payment Link), §8 (Webhooks) each carry an explicit `fullstack-integrations-specialist` block listing iframe-embed probes, redirect-contract probes, mobile-WebView probes, and Vercel/Cloudflare serverless probes. Anyone re-running this evaluation has a ready playbook — the planning was real.
2. **The hosted-KYC response was captured cleanly.** `evidence/work/verification/01-post-verifications-happy.json` returns `verification_link: https://verify.aiprise.com/?business_onboarding_session_id=…` plus the API's *own* CSP/`X-Frame-Options` headers (`frame-ancestors 'self'`, `SAMEORIGIN`). The raw evidence is sitting there waiting for a full-stack pass.
3. **Finding #2 (webhook triple-vector) implicitly covers some serverless-receiver concerns.** SSRF + cleartext HTTP + opaque CRUD-less webhook lifecycle directly affect any Vercel/Cloudflare receiver design — even though the finding is framed as a security issue, an integrator deploying on serverless will read it as a full-stack constraint too.
4. **Bucket E of the delta doc is honest** about what wasn't validated (`Magic-trigger emails`, AiPrise-vs-SumSub server-side routing, payment-link not probed, simulate-deposit not probed). The delta doc is the "what we missed" inventory done right.
5. **Phase 1 Finding #5 (Wallets) and the public-docs gap framing protect the buyer** from believing they get "Global, no-KYC" wallets. That is full-stack-relevant: a frontend integrator who picks Wallets for a low-friction prototype is the exact persona that would get burned, and the META-finding (#1) does flag the product-brochure-vs-reality gap.
6. **The integrator-impact framing throughout the README is consistent.** Even without iframe data, the "Banco Industrial / N1co InfoSec review" framing is the right consumer-side voice.

---

## What's a structural gap (missed angle)

For each: angle we didn't cover · why it matters · could we add a SHOULD-FIX note?

### Gap 1 — Hosted KYC URL (AiPrise) iframe / CSP / mobile behavior **was not probed at all**
- **Angle:** `POST /v1/users/{id}/verifications` returns `verification_link: https://verify.aiprise.com/?business_onboarding_session_id=…`. An integrator who wants to embed this in their own React app needs to know: (a) does `verify.aiprise.com` set `X-Frame-Options: DENY` (it almost certainly does — AiPrise is a third-party identity-vendor and they default-deny embedding), (b) what is the redirect contract when the user finishes (what params come back appended to `redirect_uri`), (c) is the `redirect_uri` value validated against an allowlist or accepted blindly (we sent `https://example.com/done` and it was accepted with no validation visible), (d) does it work in iOS Safari, Android Chrome, Slack/Instagram in-app browsers.
- **Why it matters:** This is the single most common full-stack integration question for any KYC-bearing product. Every fintech buyer (BIA, N1co, Borderless) will run this probe in their evaluation. If `verify.aiprise.com` denies embedding (highly likely), the entire "embed Kira in our app" pitch falls back to top-level redirect — which has its own UX implications (loss of branding, hard back-button, lost session on iOS in-app browsers).
- **SHOULD-FIX note candidate:** YES. Add a Bucket-E entry to delta doc § 1 and a one-line caveat to META-finding (#1). The probe is cheap: `curl -I https://verify.aiprise.com/?business_onboarding_session_id=…` for `X-Frame-Options` and a `<iframe src="…">` on a different origin to confirm. Even *one* captured header would close this gap empirically; without it, the deliverable cannot answer "can I embed Kira's KYC in my React app?" — a Day-1 question.

### Gap 2 — `/v1/payment-link` was never probed (Batch F blocked by DRIFT-23)
- **Angle:** The product brochure (`evidence/analysis/10-product-catalog.md`) and the hosted payment-link page template (`https://your-domain.kirafin.ai/v3/{txn_uuid}` per flow-design §3.9) are advertised as **the on-ramp UX**. Every PSE/SPEI/ACH inbound the buyer will sell against is mediated by this page. The README says nothing about it — not even "we didn't reach it." It's the highest-value product on the brochure (Wallets is fiction; Payment Link is real and is the way Banco Industrial would top up a customer wallet).
- **Why it matters:** A real integrator will get to payment-link before they get to TLS audits. The redirect contract (`?status=success|cancelled` per flow-design §3.9), branding/expiry/abandonment, iframe-fit, mobile-browser matrix, deep-link handling (Instagram in-app browser is notorious for breaking redirects) — none of this is captured. The probe was planned in `11-docs-coverage-matrix.md` §7 in detail; only execution is missing. **The reader of the README has no way to know this entire surface is untested.**
- **SHOULD-FIX note candidate:** YES. Promote payment-link from a Bucket-E line to a flagged-gap in the README's "Honorable mentions" or in a new "Coverage caveats" section. Even *unprobed*, calling it out as a known coverage gap protects the deliverable's credibility.

### Gap 3 — SDK-absence-as-finding is missing from the public surface
- **Angle:** Per the persona brief, "if Kira ships no SDK, that's a finding (raises time-to-first-call)." The deliverable mentions "TS-SDK killer" in passing (DRIFT-41, `amount` as string) as if a TS SDK exists or will exist. **There is no top-level finding stating "Kira ships zero first-party client libraries (no TypeScript, no Python, no Go) — time-to-first-call is therefore bounded by partner-doc + Postman acquisition (gated by Sales) + hand-rolled fetch."** That is a true integrator-experience finding the data-engineer would not surface (they probe HTTP, they don't measure SDK ergonomics that don't exist).
- **Why it matters:** Stripe ships SDKs in 7 languages; Plaid ships 5; Adyen ships 6. A buyer comparing Kira against any of them has the SDK gap as a first-line evaluation criterion. The Postman collection (per partner doc L141) is **not** a substitute for an SDK — it is a one-off worked example, not a typed, versioned, retry-aware, idempotency-keyed client library.
- **SHOULD-FIX note candidate:** YES — strong. Could be added either as an honorable-mention or folded into the META-finding (#1) as "and there is no SDK to bridge the gap between public docs and runtime — every integrator hand-rolls HTTP."

### Gap 4 — Serverless webhook-receiver behavior is **inferred, not tested**
- **Angle:** Finding #2 covers the webhook-register security holes (SSRF, optional secret, cross-tenant `client_uuid`) but does not address what happens **at delivery time on a Vercel/Cloudflare/Lambda receiver**. Specifically: (a) Kira's acknowledgement timeout SLO is undocumented (Phase-1 Finding #4 mentions it, but it didn't make the top-5), (b) Cloudflare Workers cap free-tier request bodies at 1 MB and Kira's verification webhook with embedded documents could exceed that, (c) cold-start interaction with Kira's (unstated) retry policy means a Vercel function on its first cold start could miss the timeout and trigger duplicate deliveries with no `event_id` for de-duplication (because partner-doc L132 says `kira-signature: t=,v1=` is still future). These are *delivery-side* concerns that the SSRF finding doesn't capture.
- **Why it matters:** Every modern integrator (especially the procurement-stage prospects the META-finding targets) deploys webhooks on serverless. "Will my Vercel function survive Kira's retry behavior?" is a top-3 integration question. It's planned in `11-docs-coverage-matrix.md` §8 (rows 205-206) and called out by `prod-cert L80-83` (event de-duplication) but no probe ran.
- **SHOULD-FIX note candidate:** PUSH-BACK — minor. The existing webhook finding implicitly covers some of this. But there's room for a one-line caveat in Finding #2: "delivery-side serverless interactions (cold-start timeout, body-size, de-dup) not probed."

### Gap 5 — Mobile in-app browser behavior is unaddressed across **every** hosted surface
- **Angle:** Payment Link, KYC verification, and any future hosted UX (cashPay barcode, liquidation-address copy-page) all have to render correctly inside Instagram/Slack/X/Telegram in-app browsers. These browsers (especially iOS Instagram and Android WebView before Chrome 102) have known bugs around: `Storage Access API`, third-party cookies, redirect handling, deep-link `intent://` and `app://` schemes, autoplay video, and crucially `window.open` from inside an iframe. None of this is probed because none of the hosted surfaces are probed.
- **Why it matters:** Banco Industrial's customers are mobile-first; the in-app-browser quirks dominate their drop-off telemetry. Any payment-link or hosted-KYC integration that doesn't handle Instagram in-app browser will fail real-world adoption.
- **SHOULD-FIX note candidate:** PUSH-BACK — out of scope for this exercise. Flag as future work, not a finding gap.

### Gap 6 — `redirect_uri` validation on `POST /v1/users/{id}/verifications` was empirically accepted as `https://example.com/done` with **no observable allowlist enforcement**
- **Angle:** Sending `redirect_uri: "https://example.com/done"` returned 201 with a `verification_link` minted. No allowlist enforcement appears to fire (we'd need to probe with `http://`, `localhost`, an attacker domain, and with fragments to confirm). This is **open-redirector adjacent** if there's no tenant-side allowlist. Could be a security finding paired with Finding #2, but it's currently uncaptured.
- **Why it matters:** Open-redirector via a verified Kira-vendor (AiPrise) page is a phishing primitive. The page is on `verify.aiprise.com`, not `kirafin.ai`, so the brand-impersonation impact is partially mitigated by AiPrise being the visible host — but the *integrator's* `redirect_uri` is where attacker-controlled URLs would land.
- **SHOULD-FIX note candidate:** YES, as a probe to add — but small. Could be paired with the Mass-assignment finding (#5 in security audit). One additional probe: send `redirect_uri: "https://attacker.example.com"` and `redirect_uri: "http://169.254.169.254"` to test the same SSRF vector applied to the redirect contract.

---

## Should we add a finding?

Specific candidates for additional findings from the full-stack lens:

1. **Coverage caveat / "Backend-only view" note in META-finding (#1).** Highest priority. One paragraph: *"This evaluation covers Kira's raw HTTP surface (auth, users, recipients, quotations, webhooks-register, banks, countries). The hosted onboarding URL (`verify.aiprise.com`), the Payment Link product (`/v1/payment-link`), and the serverless-receiver behavior at webhook-delivery time were planned but not executed in this pass (see `evidence/analysis/13-docs-vs-partner-guide-delta.md` Bucket E and `evidence/analysis/11-docs-coverage-matrix.md` §4, §7, §8). A frontend or full-stack integrator evaluating Kira's embed-ability or in-app browser behavior should treat the entire hosted-surface coverage as untested."* Cost: 5 lines. Benefit: protects deliverable credibility against the obvious "what about Payment Link?" pushback in any Slack review.
2. **SDK-absence as honorable-mention or fold into META.** Medium priority. One bullet under "Honorable mentions": *"No first-party SDK — Kira ships no TypeScript/Python/Go client library. Postman collection (partner-doc only) is the canonical worked example. Compared to Stripe/Plaid/Adyen this is a Day-0 friction; every integrator hand-rolls HTTP, retry, and idempotency wiring. Compounded by DRIFT-41 (`amount` as string) which breaks any naive `amount: number` TS type."*
3. **Hosted-KYC iframe-deniability — one-shot probe, then upgrade to finding if confirmed.** Medium priority. Cost: one `curl -I https://verify.aiprise.com/?…` + one html-file with `<iframe>`. If `X-Frame-Options: DENY` is set (likely), this becomes a real finding: "Kira's KYC vendor disables iframe embedding — every integrator must do top-level redirect, breaking the 'embed Kira in your app' pitch." Severity: MEDIUM. Could land as Finding #6 in an extended set, or honorable-mention in the top-5 version.
4. **Payment-link coverage caveat under "Honorable mentions" or "Methodology."** Low priority but worth the line. Cost: 2 lines. Benefit: head off "you didn't test the main on-ramp product" pushback.

---

## Caveats to add to existing findings

Where META or other findings should acknowledge "this is a backend-only view":

- **META-finding (#1) — top of the body:** add the coverage caveat described above. The current text says *"Cost estimate: 4–8 engineering days lost vs. <1 day for a partner-doc-equipped integrator"* — that estimate is **for a backend-only integrator**. A full-stack integrator who needs hosted-page embedding probably loses more, because Bucket E (sandbox-guide L141 "Postman is canonical") doesn't cover the hosted-page contract either.
- **Finding #2 (webhook triple-vector) — one line under "Why this matters":** add *"Delivery-side concerns for serverless receivers (Vercel/Cloudflare Workers cold-start vs Kira's unstated ack-timeout SLO, body-size against the 1 MB CF Workers free-tier cap, event de-dup with the still-undocumented signature encoding) are not separately probed but inherit the same opaque-CRUD posture."*
- **Finding #3 (PII unmasked) — no full-stack caveat needed** — already strong as a backend finding; full-stack doesn't change it.
- **Finding #4 (TLS 1.0/1.1) — no full-stack caveat needed** — already strong.
- **Finding #5 (sandbox base URL) — one line in "Reproduction":** worth noting that the partner-doc Postman collection (the only artifact that uses the working URL) is itself a *backend artifact* — there is no SDK or frontend example that would carry the correct base URL into a hosted-page context. Increases the META-finding's bite for the full-stack reader.
- **Honorable mentions block** — add one bullet: *"Hosted KYC (`verification_link` → `verify.aiprise.com`) and Payment Link (`/v1/payment-link`, `/v3/{txn_uuid}` hosted page) — iframe-fit, CSP, redirect contract, mobile in-app browser behavior — NOT PROBED in this pass; planned in `11-docs-coverage-matrix.md` §4/§7/§8."*

---

## Overall full-stack verdict

**Ship: YES — with one mandatory README caveat.**

Justification:
- The four security findings (#2, #3, #4) and the base-URL finding (#5) are independently strong and survive any full-stack pushback. None of them are weakened by the missing hosted-page coverage.
- The META-finding (#1) is the right top-1, but its **scope is backend-only** and the README must say so. Otherwise a Slack reader asks "what about Payment Link?" and the deliverable looks incomplete.
- The deliverable's own analysis docs (`11-docs-coverage-matrix.md`, `13-docs-vs-partner-guide-delta.md` Bucket E) are honest about the gap. The README is not — the README and the analysis are inconsistent on coverage scope. Fix the README.
- SDK absence is a real Day-0 friction worth one line in honorable-mentions, not a top-5 slot.

**Required pre-ship action (single highest-priority fix):**

Add a 3-5 line **Coverage scope** note immediately under the "Top 5 Findings" header (before Finding #1) that says: *"Scope of this evaluation: raw HTTP surface (auth, users, recipients, banks, countries, quotations, webhooks-register). Hosted pages (`verify.aiprise.com` KYC URL, `/v3/{txn_uuid}` payment-link page), the `/v1/payment-link` API itself, and serverless webhook-receiver behavior were planned but not executed — see `11-docs-coverage-matrix.md` §4/§7/§8 and the Bucket E inventory in `13-docs-vs-partner-guide-delta.md`. A full-stack integrator evaluating embed-ability should treat hosted-surface coverage as untested."*

That one paragraph closes the credibility gap without re-opening any probe or re-ranking any finding.

---

## Quality bar — final check (PASS / PUSH-BACK)

**Finding coverage:**
- [PUSH-BACK] Payment Link hosted-page evaluation present? — Not present. Probe was planned (`11-docs-coverage-matrix.md` §7), never executed (Batch F blocked).
- [PUSH-BACK] Hosted KYC verification URL iframe-tested / CSP-tested / mobile-tested? — Not tested. Captured (`evidence/work/verification/01-post-verifications-happy.json`) but not probed for iframe-fit.
- [PUSH-BACK] SDK absence acknowledged? — Not acknowledged at the top-level. Only mentioned in passing as "TS-SDK killer" inside DRIFT-41.
- [PUSH-BACK] Webhook receiver patterns for serverless (Vercel, Cloudflare Workers) discussed? — Partially; covered indirectly inside Finding #2 and inside `11-docs-coverage-matrix.md` §8 planning rows, but not as a delivery-side finding.
- [PASS] Magic-trigger emails flagged as future frontend dependency? — Flagged in Bucket E + DRIFT-23 reclassification; appears in delta doc L43 and L166. Acknowledged adequately.

**META-finding completeness:**
- [PUSH-BACK] Backend integrators vs frontend integrators — META currently reads as backend-only. Fix with the coverage caveat.
- [PUSH-BACK] Mobile in-app browser quirks acknowledged — not mentioned.
- [PUSH-BACK] Cross-origin concerns mentioned — not mentioned. CSP header *captured* on the verification response (`frame-ancestors 'self'`) but not analyzed.

**Full-stack gaps as findings:**
- [PUSH-BACK] Hosted pages NOT tested — flagged as a gap (vs missed)? — Not flagged in the README. Buried in `11-docs-coverage-matrix.md` and Bucket E.
- [PASS] Frontend-touching things found during basic probing noted? — The `verification_link` is captured in raw evidence; not analyzed but the data is preserved. Honest about what was probed.
