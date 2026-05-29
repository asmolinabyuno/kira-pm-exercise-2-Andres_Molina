# API Functional Tester Quality Review

**Reviewer lens:** `api-functional-tester` (fraud, abuse, business-logic exploit hunter)
**Reviewed artifacts:**
- `evidence/analysis/06-abuse-scenarios.md` (6 scenarios → 8 ABUSE findings + 3 controls)
- `README.md` Finding #2 (webhook triple-vector) and ABUSE-4 citation
- `features/02-webhook-triple-vector.feature`
- Spot-check evidence in `evidence/work/abuse/{slug}/`

---

## What's strong

- **Reproducibility is excellent.** Every scenario has `run.py`, per-call evidence JSON, and a `_summary.json` that machine-summarizes counts and shapes. Spot-checked `webhook-spoof-no-event-filter/02-P2-bogus-client_uuid-00.json`, `idempotency-replay-race/_summary.json`, `delete-recipient-pollution/_summary.json`, `silent-country-override-exploit/_summary.json` and `verification-skip-attempt/_summary.json` — all line up with the narrative.
- **N-of-M honesty.** Every finding cites repeatability counts (20/20, 3/3, 10/10, 23/23) rather than hand-waving.
- **The race-safe idempotency control (Scenario 2 / ABUSE-8) is excellent technique.** Probes A/B/C/D cover the four possible idempotency contract failure modes (same-key/same-body, diff-keys/same-body, same-key/mutated-body conflict path, synchronized-T0 race). 10 workers per probe is borderline but defensible for a sandbox; Probe C correctly observed 1 winner + 9× 409 IDEMPOTENCY_CONFLICT — the strongest possible positive evidence.
- **The cross-tenant `client_uuid` framing in the doc is honest about confirmation level.** Scenario 5 explicitly flags "To be 100% confirmed in Phase 3: trigger an event from a separate-tenant account (out-of-scope today) and check whether the attacker-registered webhook fires. The registration-time acceptance is already a CRITICAL pre-exploit posture finding." That's exactly the right caveat.
- **Country-handling matrix (Scenario 4) is one of the most novel findings in the deliverable** — three different country-handling behaviours (override / accept / strip) on the same endpoint discriminated by `account_type`. The ACH+MX-address+US-routing case has real compliance teeth (OFAC, beneficiary address coherence).
- **Verification-skip scenario is presented as a positive (Scenario 6 / state-machine integrity holds for MX_SPEI)** without overclaiming that the whole API enforces verification — explicitly notes the US_BANK branch is schema-gated before reaching the check.

---

## What needs fixing — BLOCKING

**None.** No blocking defects in the abuse track. The findings as written are publishable.

---

## What should improve — SHOULD-FIX

1. **README Finding #2 over-claims `client_uuid` impact in the headline sentence.** The headline ("3/3 random UUIDs registered (foreign-tenant webhooks)") and the closing sentence ("Combined chain: one leaked API key + Bearer token registers a cross-tenant webhook pointing at attacker infrastructure, unsigned, over HTTP, with Kira's fetcher reaching AWS IMDS on delivery") imply end-to-end siphoning of victim-tenant events. But the abuse-scenarios.md is more careful: we only proved **registration-time acceptance** of bogus UUIDs. We did **not** prove fan-out routing actually uses `client_uuid` as the partition key, nor that a victim tenant's events arrive at our attacker URL. README should add a one-line caveat — something like "Cross-tenant fan-out confirmation is pending Phase-3 dual-tenant probe; registration-time acceptance is empirically proven, full event-siphon is the inferred posture." Otherwise a Devil's-Advocate reader can sink it by asking "did you observe a victim event arrive?" and the honest answer is "no, we only observed the registration".

2. **ABUSE-4 needs a dedicated line in the README's "Honorable mentions" or as a sub-bullet of Finding #2 to credit the abuse track.** Currently ABUSE-4 is mentioned once at the end of the Finding #2 evidence trail (`DRIFT-47, DRIFT-48, DRIFT-51, DRIFT-53, ABUSE-4`) but a reader skimming the README cannot tell which sub-vector (SSRF vs cross-tenant vs secret-optional vs cleartext vs opaque) came from which agent. SSRF is security-auditor; ABUSE-4 (the cross-tenant `client_uuid` acceptance) is functional-tester. That attribution matters because the cross-tenant vector is the one with the weakest empirical proof (registration-only), so the reader needs to know who owns it for follow-up Q&A.

3. **The race-safe idempotency positive (ABUSE-8) is NOT mentioned in the README at all.** This is a Kira-positive finding — the API gets idempotency RIGHT on `/v1/recipients` under N=10 parallel — and it sharpens the negative finding (Idempotency-Key ignored on `/webhooks/register`, DRIFT-50, mentioned in Honorable mentions). Mentioning both in adjacency would strengthen the report's credibility ("we tested both directions; here's what passed, here's what failed"). Add a one-line "controls passed" sub-bullet under Honorable mentions.

4. **BOLA control (Scenario 3) sample-size caveat.** 23 random-UUID GETs returning 404 is "absence of leak from random enumeration", not "absence of BOLA". The scenario doc is honest about this ("Not declared clean … Recommend Phase-3 dual-tenant probe"), but if any external reader sees just the summary table (`bola-cross-tenant-stub LOW No leak`) they could conclude BOLA is absent. Consider relabeling the Status column from "No leak" to "No leak from random enumeration (stub — dual-tenant probe pending)" so the row alone communicates the caveat.

5. **Scenario 5 Probe P5 (events-field stripped) is undersold.** The doc treats it as an aside. But "events filter silently stripped" is a separate behavior worth flagging on its own: an integrator who reads the public doc, sends an `events: [...]` filter expecting per-event subscription, and gets back 200 will assume the filter is honored. It isn't. That's a documented-vs-runtime drift in its own right and could fit as an ABUSE-9 (LOW) or merge into DRIFT-G* properly. Minor.

6. **ABUSE-2 (ACH + MX address + US routing) impact framing is strong but could cite a specific regulatory hook.** "AML/OFAC implications" is correct but vague. Calling out OFAC's "50 Percent Rule" guidance or the BSA beneficiary-address requirement would convert this from a yellow flag to a buyer-stopping red flag for a Banco Industrial / N1co InfoSec review.

---

## Abuse finding realism check (per ABUSE-N)

| # | Finding | Realistic fraud scenario? | Verdict |
|---|---|---|---|
| ABUSE-1 | `/v1/recipients` pagination params ignored | **Realistic** — attacker pollutes recipient list to N=10k, UI un-renderable; cleanup requires Kira support intervention. Trust hit + ops $. Real. | PASS |
| ABUSE-2 | ACH USD with MX address + US routing | **Highly realistic** — real AML/OFAC reporting hole. A careless integrator unknowingly stores non-coherent beneficiary records; a sophisticated attacker exploits this for layering. Concrete $ at risk via state money-transmitter examination findings. | PASS — strongest finding in the set |
| ABUSE-3 | WALLET silently strips `account.country` | **Realistic but lower-impact** — reconciliation/compliance angle, not direct fraud. The fraud lies in inconsistency across variants (SPEI overrides, ACH accepts, WALLET strips) which is harder for an integrator to defend against. | PASS |
| ABUSE-4 | Webhook `client_uuid` foreign acceptance | **Posture-realistic, exploit unproven.** Registration-time acceptance proven (3/3). Full fan-out siphon inferred but not observed. Severity rating CRITICAL is correct *if* `client_uuid` is the partition key (Kira's hypothesis in DRIFT-G); if it isn't, severity collapses to LOW (just a missing input-validation bug). The doc is honest about this gap; the README is less so. | PASS-with-caveat |
| ABUSE-5 | 4th distinct error envelope shape | **DX hit, not fraud.** Real integrator pain — every `try/except` block needs to know 4 envelope shapes — but no money at risk. MEDIUM is calibrated correctly. | PASS |
| ABUSE-6 | Validation-layer ordering depends on `type` discriminator | **Reconnaissance-realistic.** Attacker can choose to probe schema vs verification by choosing US_BANK vs MX_SPEI. MEDIUM is correct (recon, not exploit). | PASS |
| ABUSE-7 | Error message echoes user's verification status | **Realistic recon vector.** Attacker with API key (which is single-tenant) can enumerate verification state of users they know the UUID of. Combined with the lack of GET enumeration, this is a useful primitive but not a direct fraud. MEDIUM is correct. | PASS |
| ABUSE-8 | Idempotency race-safe on `/v1/recipients` (positive control) | Not a fraud finding — it's a **positive control** that's a Kira-positive. Presenting a passed test as a "finding" is correct technique here because it sharpens DRIFT-G4 (broken on webhooks) by showing the inconsistency. | PASS |

**Net:** 7/8 ABUSE findings are genuinely exploitable in a realistic fraud or compliance scenario; ABUSE-4 is the one with the largest "could be CRITICAL or could be LOW depending on Phase-3 confirmation" gap.

**No purely theoretical findings.** Every ABUSE-N has a believable bad-actor path and an observed reproducible outcome.

---

## Cross-tenant impact framing check (ABUSE-4 + README Finding #2)

| Claim made | Where | Empirically proven? |
|---|---|---|
| Bogus `client_uuid` accepted at registration | abuse doc + README + .feature | **YES** — 3/3 with random UUIDs (`cbc5d344-9def-471b-a135-cfc208c48bb1`, `11111111-2222-3333-4444-555555555555`, `99999999-aaaa-bbbb-cccc-dddddddddddd`). Confirmed truly random, not real-tenant. |
| Cross-tenant webhook hijack (siphon victim events to attacker URL) | README implies, abuse doc explicitly caveats | **NO — only inferred.** Doc is honest, README is over-confident. |
| AWS IMDS reachable via SSRF (`169.254.169.254`) | README + Finding #2 + feature file | **YES** per security-audit cross-reference (out-of-scope for me but the abuse doc correctly cites it as a coordinated finding). |
| Stacked exploit (one POST = all 5 vectors) | feature file's combined-chain scenario | The **registration** of all 5 stacked vectors is empirically proven in one POST; the **end-to-end siphon** at delivery time is not. The feature file is careful to say "this is the registration posture", which is technically correct. |

**Verdict on framing:** abuse-scenarios.md gets it right. README gets it 80% right but the "registers a cross-tenant webhook pointing at attacker infrastructure" claim in Finding #2 needs a one-line caveat about fan-out confirmation pending. The .feature file is fine — its "Observed" scenarios only assert the 200 response, which we did observe.

**Use of random UUIDs (not real-tenant IDs):** Confirmed. The three foreign UUIDs are visibly synthetic (`11111111-...`, `99999999-aaaa-...`). No real customer's `client_uuid` was used. Ethical posture is clean.

---

## Control-finding sample-size check

| Control | Claimed status | Sample size | False-negative risk |
|---|---|---|---|
| Race-safe idempotency on `/v1/recipients` | "RACE-SAFE under N=10 parallel" | 10 workers × 4 probes = 40 calls | **LOW.** 10 parallel is enough to catch a naive non-atomic check. A pathological race window of <10ms might still exist; sandbox latency (~500ms per call observed in webhook spoof) makes that unlikely. Defensible. |
| BOLA absent (random UUID enum) | "No leak" but explicitly caveated | 23 random GETs, 2 cross-resource POSTs (schema-gated) | **HIGH false-negative risk.** Doc correctly says "Not declared clean — needs dual-tenant probe". The caveat is in the prose but the summary table at top says "LOW — No leak — random UUID enumeration returns 404 consistently" which is too clean for a casual reader. SHOULD-FIX #4 above. |
| Verification gate enforced (MX_SPEI VA) | "No bypass" for the canonical path | 3 users × 3 endpoint families = 9 probes (iter1) + 6 probes (iter2) | **MEDIUM false-negative risk.** Only MX_SPEI VA-create reached the verification layer in evidence. US_BANK path, payouts, and quotations were all schema-gated before the check fired, so we don't know whether the *check* enforces or whether *schema* is the only gate. Doc is honest about this; presented as "positive on the canonical branch" which is the right framing. |

**Net:** the race-safe idempotency claim is solid. The BOLA-absent claim needs a clearer surface-level caveat. The verification-enforced claim is correctly scoped to "MX_SPEI VA create branch only" and shouldn't be over-extrapolated.

---

## Overall verdict

**Ship: YES (with 3 SHOULD-FIX nits).**

The abuse track is the strongest empirical track in the deliverable. 8 ABUSE findings with run.py + evidence per scenario, repeatability counts on every claim, and positive controls presented as positives. The framing is honest about what was and wasn't observed — the abuse doc never claims a victim event was siphoned, only that the registration was accepted.

The three nits that would tighten this for publication:
1. README Finding #2 should add a one-line caveat that fan-out siphoning is inferred, not observed (the abuse doc has the caveat; README dropped it).
2. README should explicitly credit ABUSE-4 vs the security-auditor's DRIFT-47/SSRF — currently the reader can't tell which agent owns which vector.
3. The race-safe idempotency positive (ABUSE-8) deserves one line in the README's "Honorable mentions" — a Kira-positive finding strengthens the report's credibility.

Nothing here blocks the deliverable. The abuse track is publishable as-is.
