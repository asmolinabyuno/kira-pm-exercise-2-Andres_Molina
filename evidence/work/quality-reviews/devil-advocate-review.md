# Devil's Advocate Review — Pre-publish Pass (2026-05-28)

Final filter. The point of being last is to catch what the other agents won't push back on. Skip the praise; focus on what a skeptical reader will tear apart.

---

## Prioritization audit — top-5 defensibility

### Finding #1 — META "public docs materially incomplete"
- **Defensible?** YES on integrator-impact framing. NO on novelty: the brief itself points integrators at `docs.kira.finance` (not `kira-financial-ai.readme.io`). We never address that the brief's link and the URL we evaluated do not match. A skeptical Kira reader will say: "you evaluated the wrong portal, then turned that into your #1 finding."
- **Could a Kira engineer dismiss it?** YES — "the partner doc IS the contract; the public Readme is a marketing surface." Our framing fights that, but we never quote a Kira PM/PD/Eng saying "the public docs are the source of truth." The whole META rests on an unspoken assumption the reader may not share.
- **Severity inflated?** A bit. The 22/53 partner-acknowledged metric is real and good, but **22 of 53 means 31 of 53 drifts are NOT in either doc** — that's a stronger Bucket-D headline than "Bucket C is big." The META reframes findings that the partner doc already concedes; the unfixed-anywhere ones are sharper.
- **30-second Kira rebuttal:** "Of course public docs are incomplete — that's why we have a partner-onboarding flow. Your META finding is 'Kira's onboarding model is partner-led' which we know. Show us the things partners don't know."
- **Verdict:** HOLD slot #1, but tighten the framing — lead with the 31/53 partner-doc gap rather than the 22/53 reframe.

### Finding #2 — Webhook triple-vector (SSRF + cross-tenant + optional secret + cleartext + opaque)
- **Defensible?** YES on the registration-surface (200 returned for SSRF URLs, foreign UUIDs, null secret, http://). NO on the "delivery actually reaches IMDS" claim — the SSRF README's own verdict says "Kira may or may not have reached IMDS." The probe **infers** outbound delivery from absence (the safe webhook.site URL stopped getting deliveries after re-registering to IMDS). The README escalates this to "IMDS reachability empirically confirmed." That's overclaim.
- **Cross-tenant claim:** the abuse evidence proves random UUIDs are *accepted at registration*, NOT that another tenant's events are routed to the attacker. We never registered a webhook on tenant-A and triggered an event on tenant-B to prove cross-tenant delivery. A Kira engineer will say "client_uuid is just a routing key — accepting random UUIDs means we drop the registration into a void, not into another tenant's event stream." That counterargument is plausible and we don't refute it.
- **Severity inflated?** CVSS 9.1 is aggressive given the inference gap. A defensible read is CVSS 7.5–8.5: confirmed surface (accepts hostile URLs, no signing, opaque response) but not confirmed end-to-end IMDS exfil.
- **30-second Kira rebuttal:** "Last-write-wins on a single client_uuid is not cross-tenant; it's just our registration overwriting your registration. The SSRF surface is real and we'll fix it, but the 'pivot to IMDS' is theoretical."
- **Verdict:** HOLD slot #2 but reword the README claim from "IMDS reachability empirically confirmed" to "outbound fetcher honors the registered URL; IMDS reachability inferred from absence-of-delivery to safe URL." And add a positive cross-tenant test as a probe gap.

### Finding #3 — PII unmasked
- **Defensible?** Weakest of the five on evidence quality. The "SSN" values returned are `000-00-0000` — our own synthetic test data echoed back. The `document_number` values are `FAKE-DOC-00000001`. A Kira engineer will reasonably push back: "You're describing schema echo of test data, not exposure of real PII. In sandbox we don't have real PII to mask." We have no production capture, no proof of plaintext for a different tenant, no proof of what production behavior is.
- **The framing as written collapses two findings:** (a) the schema *shape* returns unmasked fields (real finding, regulatory issue), (b) we observed real PII (we did not). The README implies (b).
- **30-second Kira rebuttal:** "Sandbox echoes what you sent. Production has masking middleware. The schema returning a `ssn` key is by design — the masking happens at the response layer in prod. Show us a prod capture or this is a sandbox artifact."
- **README also claims**: "neither doc mentions masking" — true and useful — but doesn't survive the rebuttal that this is sandbox-only behavior.
- **Verdict:** AT RISK OF DEMOTION. Either downgrade to HIGH and reframe as "docs do not commit to masking semantics — sandbox returns plaintext for synthetic test PII, and there is no documented contract that production behaves differently," or get a second test tenant and prove cross-tenant exposure. **This is the single most likely finding to be demoted by a skeptical reader.**

### Finding #4 — TLS 1.0 / 1.1 accepted
- **Defensible?** YES. openssl + Python ssl.SSLContext both confirm the handshake. The compliance angle (PCI-DSS Req 4.1) is real and procurement-blocking.
- **Severity calibration:** The security audit itself rates CVSS 5.9 ("HIGH attack complexity, requires MITM and a client that consents to downgrade"). The README labels this CRITICAL on compliance grounds. That's a defensible reframe — compliance > technical-exploit for this finding class — but a skeptical reader will note we used "CVSS HIGH-complexity" evidence to back a "CRITICAL" label, which looks like cherry-picking.
- **30-second Kira rebuttal:** "AWS CloudFront default + this is sandbox; prod has a stricter security policy. Did you check prod?" We did not check prod TLS separately — we treat `api.balampay.com` as production-fronting, but we never confirm prod ≠ sandbox on TLS posture.
- **Verdict:** HOLD slot #4. Add a one-line acknowledgement that the finding is on the public-facing host shared by sandbox+prod (or note the ambiguity), and let the compliance frame carry the severity.

### Finding #5 — Sandbox base URL wrong
- **Defensible?** YES, technically airtight (probes 1–6 are clean, evidence captures are dated and reproducible).
- **But is it really #5?** It is the same finding-class as #1 (META). The README puts the META at #1 and the base-URL drift at #5; structurally #5 IS the empirical proof of the META finding. A skeptical reader will say: "you double-counted — #1 says 'public docs are wrong' and #5 says 'public docs are wrong about the base URL.' Pick one."
- **What got displaced for #5?** The honorable-mentions list contains the silent country override (DRIFT-38 + ABUSE-2) — that's a real compliance/AML finding the delta doc explicitly recommends as slot #5 candidate. We dropped it for the base-URL finding, which has lower integrator-impact (every integrator hits and fixes it in <1 hour, by definition, since you can't proceed otherwise).
- **30-second Kira rebuttal:** "If they get a 403 on call #1 they DM us and we tell them. This is a 10-minute fix on the integrator side; the integrators who hit it are unblocked by 11am. Why is it more severe than the ACH-country-override compliance hole?"
- **Verdict:** AT RISK. Either consolidate #1+#5 into one finding and promote ACH-country-override to slot #5, OR explicitly justify why DRIFT-1 is independent of the META rather than a subset.

---

## Specificity audit — worst 3 Gherkin scenarios

### Worst #1 — `01-public-docs-materially-incomplete.feature:78-83` ("Spec — Following the public docs end-to-end gets a user to verification_status=VERIFIED within 60s")
```
Given a fresh business user was created via POST /v1/users at the no-prefix base
And POST /v1/users/{id}/verifications was called per the docs flow
When I poll GET /v1/users/{id} every 5 seconds for up to 60 seconds
Then within 60 seconds the response JSON path "$.verification_status" MUST equal "VERIFIED"
```
- **Why vague:** "fresh business user" with what payload? "per the docs flow" with what body? An engineer cannot write a failing test without knowing the canonical user-creation body. The Background does not name it. The integrator hit a sandbox auto-reject — but the spec assertion says VERIFIED within 60s, while the Observed scenario asserts REVIEW within 120s. Same poll cadence (5s), two different timeouts (60s vs 120s). Which is the contract?
- **Engineer's question:** "What 'docs flow' are we encoding here? The public-docs flow that doesn't work, or the partner-doc flow that does (with Slack ping)?"

### Worst #2 — `01-public-docs-materially-incomplete.feature:114-120` (Quotations Spec)
```
When I POST to "/v1/quotations" with the Guides-shape body {"base_currency": "USD", "quote_currency": "MXN", "amount": "100", "amount_in_destination": false}
Then the response status equals 400
And the response JSON body mentions field names not present in the Guides body (e.g., "recipient_id" or "account_type")
And the Guides field names "base_currency", "quote_currency", "amount_in_destination" MUST NOT appear in the validator's error list
```
- **Why vague:** "mentions field names" is unobservable. "Field names not present" — engineer must enumerate the canonical Reference field list, which is not in the feature file. "MUST NOT appear in the validator's error list" — what's the error-list shape? The Background and Background do not anchor a specific envelope.
- **Engineer's question:** "Where do I get the canonical Reference field list to compare against, and which of the four error envelopes does this endpoint return?"

### Worst #3 — `03-pii-unmasked.feature:53-58` (Observed user-detail leak)
```
Then the response status equals 200
And the response JSON path "$.document_number" returns the full plaintext value (regex "^\\d{6,}$", not the masked pattern)
And at least 7 sensitive fields across the response body are returned in plaintext (per the probe's sensitive_fields_found count)
```
- **Why vague:** "(per the probe's sensitive_fields_found count)" is not a runtime assertion. The engineer needs to know which 7 fields and where. The regex `^\d{6,}$` will not match `FAKE-DOC-00000001` (which is what's in evidence). The Observed assertion is **self-contradictory with the actual evidence file** — the evidence has alphanumeric `FAKE-DOC-…`, the spec asserts digits-only `^\d{6,}$`.
- **Engineer's question:** "Did you copy this from a real-PII tenant, or are you generalizing from synthetic test data? The regex doesn't match what's in `01-disclosure-sweep.json`."

---

## Integration depth audit — the BLOCKED 6 endpoints

The README says 18/30 + 6 BLOCKED. Specifically: Items 6, 7, 8, 10, 11 of the prod-cert checklist (VERIFIED user, VA create, simulate deposit, preview payout, execute payout) are blocked by DRIFT-23 (sandbox manual approval).

**Honest blocked or gave up?** Half and half.
- **Honest:** DRIFT-23 (sandbox does not auto-approve) is empirically real. The blocker exists.
- **Gave up:** The partner doc (which we have) explicitly says the workaround is "ping your Kira contact in Slack." We never exercised that workaround. The disclosure section in CLAUDE.md and the brief explicitly grade outreach (10%). We had a documented unblock path, a documented Slack channel, and 4 hours to send a message. We chose not to and labeled the work BLOCKED.
- **What we could have done without escalation:** The partner guide mentions a `POST /v1/virtual-accounts/{id}/simulate-deposit` and magic emails like `verify+approved@kira.test` shipping in v2026-XX-XX. Today's workaround was specifically "Slack." We did probe `POST /v1/versioning/upgrade` (Bucket E item 1) and got it working — proving we CAN follow partner-doc leads when we want to. We just did not pull the trigger on the human-in-the-loop workaround for DRIFT-23, despite Bucket E item 2 noting "MEDIUM — requires user VERIFIED via Slack ping."

**Result:** 12/30 ≈ 40% of endpoints were not exercised, including the entire money-movement surface (deposit, payout). The README's "18/30 endpoints empirically validated" understates how much of the *core flow* (the literal thing the brief asked us to integrate end-to-end) is missing. The brief says: "Run at minimum: create customer → submit KYB → **create virtual account → simulate inbound deposit → initiate payout**." We did **none** of the bolded.

**This is a real grading risk** — Integration Depth is 20% of the grade.

---

## Communication audit — disclosure language

### The .feature files say:
> "Disclosure status: raised with @Diego on the security disclosure track" (features 02, 03, 04)

### The README says:
> "Disclosure status: documented in this deliverable; recommended next step is coordination with @Diego before broader publication."

### The decision-log says:
> "10 outreach questions to @Diego / @Nicolle ... **not yet sent**"

**Verdict on the language change:** SANDBAG, and worse — internally inconsistent. The .feature files actively claim "raised with @Diego on the security disclosure track" which is **factually false** per our own decision log. The README's softer language ("recommended next step") is more honest but still misleading: it implies we are pausing publication for coordination, when in fact we never started coordination.

The brief is explicit: "We will check the channel and DMs for evidence. Zero outreach is a flag, not a feature." Kira's grader can verify in 30 seconds that nothing was sent. The grade on Communication (10%) will be near-zero. Worse, finding the .feature files claim "raised" while no DM exists damages credibility on the higher-weighted dimensions.

**The honest move:** change every "Disclosure status: raised with @Diego" to "Disclosure status: NOT YET DISCLOSED — recommend Kira's security team be contacted before this repo is made public. Open questions logged in evidence/analysis/13...md § 6." And then actually send the message before the deadline. The 4 critical security findings (esp. SSRF) being on a public GitHub repo without disclosure is itself an ethics issue — for a fintech-PM evaluation, that should weigh heavier than the grade.

---

## Where a competing PM beats us

A competing candidate who submits a tighter, more focused deliverable would:

1. **Run the actual minimum flow.** Send a Slack DM to Diego at 10am Wed asking for manual user-approval. Get unblocked by noon. Hit `simulate-deposit` and `payout-create` by EOD Wed. Then have 100% of the brief's bolded items checked, not 0%. We have 78 findings, 0 payouts.
2. **Cap at 4 truly sharp findings instead of 5 padded ones.** Drop the META + base-URL collision; ship one consolidated docs-quality finding and use the freed slot for ACH-country-override (compliance angle, AML-relevant for a fintech audience).
3. **Send the disclosure email in the deliverable thread.** Even one paragraph forwarded to @Diego before publishing wins the Communication 10% outright. Reading the .feature files and the decision log side-by-side, our story is "we wrote down what we'd ask but didn't ask." That's a tell.
4. **Lead with evidence, not narrative.** The 13-docs-vs-partner-guide-delta.md is 310 lines of taxonomy. A competing PM produces a 3-page README with 5 raw HTTP captures and lets the captures argue the case.

## Lowest-quality 10% of this deliverable

**The Quotations spec scenario (Sub-finding E of feature 01).** It asserts a non-observable property ("response body mentions field names not present in the Guides body"), conflates two error-envelope variants without naming which one, and fails the "an engineer can write a failing test without DMing the author" bar. The honorable-mentions section of the README is also weak: it lists 4 items but compresses each to one sentence — none of them survive a follow-up question.

Also low-quality: **the cross-tenant `client_uuid` claim**. The abuse evidence is "3/3 random UUIDs returned 200 at registration." That is not the same as "cross-tenant webhook hijack." We never proved another tenant's events get routed to our URL. The leap from "accepted" to "hijack vector" is asserted, not demonstrated.

## Where we substituted volume for sharpness

- **78 findings** vs. brief's "Quantity is not the point — sharpness of prioritization is."
- **13 analysis docs** for what could be 1 README + 5 evidence captures.
- **53 drifts** — many are MEDIUM/LOW and inflate the "we found a lot" frame, but the partner-doc delta concedes 22 of them are already known. Net new sharp findings ≈ 31; net critical-or-high ≈ 12.
- **6 sub-findings in feature 01** for one META finding. Each sub-finding is a scenario; some scenarios duplicate Sub-finding C and D into the same Bucket-Section-3 evidence. The reader feels exhaustion before they feel persuasion.

The 108-row test matrix is technically impressive but it is **not the deliverable the brief asked for**. The brief asked for 5 findings + 5 features. We shipped a small enterprise-quality QA program. Volume here may *hurt* the prioritization score because it dilutes the top-5 framing.

---

## BLOCKING items before publish

1. **Disclosure language is internally inconsistent and factually wrong.** The .feature files claim "raised with @Diego" — they were not. Fix every "Disclosure status" line OR actually send the DM. Brief grades this 10%; mismatch costs the score.
2. **PII evidence shows synthetic data.** Finding #3 needs reframing as "schema returns plaintext fields; sandbox echo proves no masking middleware; production behavior undocumented" OR get a second-tenant or prod confirmation. As written, a skeptical reader will demote this to HIGH or below.
3. **SSRF "IMDS reachability empirically confirmed" overclaim.** The probe README itself concedes uncertainty. README finding #2 should read "outbound fetcher honors registered URL; IMDS reachability inferred." Otherwise the strongest finding is the most attackable on its weakest line.
4. **The brief asked for a deposit + payout. We delivered neither.** Either run the partner-doc Slack workaround for DRIFT-23 today, or label the README "Integration depth: 47% of prod-cert checklist; 0 of 3 money-movement endpoints exercised — known gap." The current framing ("18/30 empirically validated") understates this.
5. **Finding #5 is finding #1 with extra steps.** Either consolidate, or promote ACH-country-override (DRIFT-38 / ABUSE-2) to slot #5 — the delta doc itself recommends this.
6. **Cross-tenant claim needs proof or hedging.** Either run a 2-tenant test or rewrite from "cross-tenant hijack" to "accepts foreign client_uuid values at registration; cross-tenant routing impact not empirically verified."
7. **Specificity issues in feature 01 (Quotations spec scenario) and feature 03 (regex contradicts evidence file).** Fix or downgrade.

## Overall verdict

- **Ship: NOT YET.**
- **Required fixes to flip to YES (90 minutes of work):**
  1. Send the actual Slack DM to @Diego (5 min) — flips Communication from 0 to ~70%.
  2. Reword every "Disclosure status: raised with @Diego" to match reality (10 min).
  3. Rewrite #2 README claim from "empirically confirmed IMDS reachability" to "outbound fetcher honors registered URL; IMDS exfil inferred from absence-of-safe-URL delivery" (5 min).
  4. Reframe #3 as schema-no-masking + sandbox-only evidence; add explicit "production capture needed to confirm" caveat (10 min).
  5. Either consolidate #1+#5 or promote ACH-country-override to slot #5 (20 min).
  6. Fix the contradicting regex in features/03 (5 min).
  7. **If 4 hours available before deadline:** run the partner-doc DRIFT-23 workaround, do simulate-deposit + payout-create, and the Integration Depth score climbs from "47% of partner-cert checklist" to ~80% (45 min once unblocked).

Ship after items 1–6. Item 7 is the difference between a B+ and an A.
