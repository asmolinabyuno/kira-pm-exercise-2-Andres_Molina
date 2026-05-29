# API Security Auditor Quality Review

Reviewer lens: `.claude/agents/api-security-auditor.md` — OWASP API Top 10 (2023), CVSS rigor, threat-actor realism, sandbox-only discipline, reproducibility.

Scope reviewed:
- `evidence/analysis/05-security-audit.md` Findings F1–F5 (audit doc has 9 findings; brief lists F1–F5 — interpreted as the 5 most relevant: F1 SSRF, F2 PII-users, F3 PII-recipients, F4 TLS, F5 mass-assignment).
- `README.md` Findings #2, #3, #4 (security ones).
- `features/02-webhook-triple-vector.feature`, `features/03-pii-unmasked.feature`, `features/04-tls-1-0-1-1-accepted.feature`.
- `evidence/work/security/{ssrf-webhook-delivery-confirm, info-disclosure-account-details, security-headers-and-tls, mass-assignment-user-create, bola-id-enumeration}/`.
- Disclosure language across README + features.

---

## What's strong

- **OWASP mappings are correct and explicit on every finding.** F1→API7, F2/F3/F5→API3, F4→API8. No reach mappings. F2/F3 are correctly the "excessive data exposure" sub-class of API3, not API1 (BOLA was correctly negated by the BOLA probe — that restraint is itself a quality signal).
- **F1 SSRF is defended well.** The probe sequence (register safe → observe receipt → re-register to IMDS → re-trigger → observe zero deliveries → cleanup) is a clean differential test. The audit-doc verdict ("attempts the HTTP call to the supplied URL") is honest — it does NOT overclaim that IMDS credentials were exfiltrated. We confirmed only the *fetch behavior*, not the *credential leak*. That's the right line for a public deliverable.
- **No real PII.** Every SSN/EIN in the evidence is the literal `000-00-0000` / `FAKE-DOC-*` / `00-0000000`. Verified across `01-disclosure-sweep.json`.
- **Negative results documented.** BOLA probe (16 attempts, 0 cross-tenant 200s) and JWT attack suite (9 attempts, 0 forgeries accepted) are explicitly written up as non-findings. That's the discipline a CISO wants to see — we know what we tested and ruled out.
- **TLS finding is dual-confirmed.** Python `ssl.SSLContext` + `openssl s_client` both succeed at TLS 1.0/1.1. Two-tool corroboration kills "macOS-LibreSSL-quirk" rebuttal.
- **CVSS calibration is largely realistic.** F4 explicitly says "technical exploit needs MITM + downgrade — compliance is the bigger lever" — that's an auditor framing the regulator-risk correctly. F2/F3 at 7.5 (not 9.x) is right — single-tenant scope, no integrity impact.
- **The mass-assignment finding (F5) deliberately refuses to climb to CRITICAL.** README notes "verification_status itself is NOT settable — server returns unverified regardless." That's honest negative-control work; the integrator can't actually grant themselves approval.
- **Disclosure scope was respected during testing.** Sandbox base only, no out-of-scope hosts, IMDS was registered briefly then overwritten with a benign URL within 3 minutes, cleanup confirmed at step G of the probe.
- **Feature files are tagged `@security` consistently.** All three security features carry the right tag. F02 also carries `@webhook` and `@fraud-vector` — appropriate compound classification.

---

## What needs fixing — BLOCKING

### B1 — README cites four evidence paths that DO NOT EXIST
File: `README.md`
- Line 33 cites `evidence/work/security/webhook-ssrf/` → actual folder is `ssrf-webhook-delivery-confirm/`.
- Line 33 cites `evidence/work/abuse/webhook-spoof/` → actual folder is `webhook-spoof-no-event-filter/`.
- Line 44 cites `evidence/work/security/pii-unmasked-users/` → does not exist; evidence lives under `info-disclosure-account-details/`.
- Line 44 cites `evidence/work/security/pii-unmasked-recipients/` → same as above; does not exist.

A reviewer clicking through these gets four 404s in a row on the three most severe security findings. **Fix:** rewrite Findings #2 and #3 evidence lines to point at the real folders.

### B2 — Disclosure language LIES about pre-disclosure to Diego
Files: `README.md` line 121, every `features/*.feature` line 6.
- README line 121: "security disclosures (Findings #2, #3, #4) raised privately; awaiting acknowledgement before publishing reproduction details beyond what is necessary in this README." — **we did not pre-disclose to Diego.** This is presented as fact.
- All five feature files line 6: "Disclosure status: raised with @Diego on the security disclosure track" — same false claim, repeated five times.

The brief explicitly says we are publishing without pre-disclosure. Asserting otherwise is a credibility hit if Diego ever reads it (he will). **Fix:** replace with truthful language — "Disclosure status: included in this public exercise deliverable; NOT pre-disclosed to Kira. Recommended next step before broader distribution: coordinate with @Diego on remediation timeline." The "Disclosure status: documented in this deliverable; recommended next step is coordination with @Diego before broader publication" framing on Findings #1 and #5 is fine — extend that to #2/#3/#4 and the features.

### B3 — README #2 OVER-CLAIMS "IMDS reachability empirically confirmed"
File: `README.md` line 32.
- Quote: "Kira's egress fetcher (`54.201.149.241`) does reach the URL at delivery time (IMDS reachability empirically confirmed)."
- The audit doc (`05-security-audit.md` § Finding 1) and the probe README say only that Kira *attempts the outbound* — the safe URL stops receiving deliveries when re-registered to IMDS. We did NOT confirm the IMDS server itself was reached; we have NO IMDS response evidence (we wouldn't, ethically — that's exfil). The two surfaces disagree on the strength of the claim.

This is the single most important defendability gap. A skeptical reader (Diego, his InfoSec team) will read the README claim and ask "where's the proof Kira reached IMDS?" Answer: we don't have it. **Fix:** rewrite to "Kira's egress fetcher (`54.201.149.241`) *attempts* the outbound HTTP call to the registered URL — confirmed by the differential test where the previously-active webhook.site URL stops receiving deliveries the moment the IMDS URL is registered (last-write-wins). Whether Kira's VPC egress policy permits the actual IMDS hit is unverified from outside."

### B4 — Feature 02 Example row pins concrete UUIDs as "foreign client_uuid"
File: `features/02-webhook-triple-vector.feature` lines 84–86.
- The Scenario Outline lists three specific UUIDs as "Examples" of foreign tenant IDs. The first one (`cbc5d344-9def-471b-a135-cfc208c48bb1`) was the random UUID generated by `uuid.uuid4()` at probe runtime. The probe's intent was "any random UUID Kira's API will accept." Publishing it as a literal example creates two risks: (a) if that UUID happens to map to a real Kira tenant, anyone re-running the test hits that tenant's webhook config; (b) it implies we tested cross-tenant takeover against three specific known-tenant IDs, which would be out-of-scope by the auditor persona's "no customer data" rule.

**Fix:** replace concrete UUIDs in the Examples table with placeholders (`<random-uuid-1>`, `<random-uuid-2>`, `<random-uuid-3>`) and add a Background note: "Each `<random-uuid-N>` is generated fresh per test run via `uuid.uuid4()`; collision with a real tenant UUID is astronomically unlikely but the test framework MUST use freshly-generated IDs, never the literal values shown in the original probe evidence."

---

## What should improve — SHOULD-FIX

### S1 — F1 CVSS vector should be sanity-checked against the IMDS uncertainty
The 9.1 score (`AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N`) assumes the SSRF *can* exfil IMDS credentials (high confidentiality + integrity, scope changed). If we honestly say we only confirmed the outbound *attempt* — not credential exfil — the more defensible score is closer to 8.6 (`AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N`) or even 7.7 (`AV:N/AC:H/PR:L/UI:N/S:C/C:H/I:L/A:N` if we condition on Kira running IMDSv1, which we don't know). The 9.1 is defensible in court if pressed but pulls some of its weight from an unverified premise. Recommend: keep the 9.1 in the audit doc as "if Kira's fetcher runs in a VPC with IMDSv1, this is 9.1; if IMDSv2, this is ~7.5"; in the README finding #2 headline, say "CVSS 8.6–9.1 depending on Kira's fetcher VPC configuration" instead of bare 9.1.

### S2 — F4 TLS finding should land on the audit doc's better framing in README too
The audit doc honestly says "technical exploit requires MITM + downgrade — well within nation-state / advanced-fraud-group capabilities" — i.e., the CVSS is 5.9, the compliance impact is the bigger lever. The README finding #4 implies CRITICAL purely on compliance. Both are true, but the README phrasing slightly hides the "MITM required" caveat that a sharp InfoSec reviewer will probe. Add one sentence: "Technical exploit requires an active MITM (uncommon outside hostile networks); the CRITICAL severity is driven by procurement-gate compliance (PCI-DSS Req 4.1, FFIEC), not by exploit ease."

### S3 — F5 mass assignment is in the audit doc but absent from README top-5 — flag the rationale
F5 (`verification_mode` mass-assignment, HIGH) is in the audit but not in README top-5. That's the right call — phishing-by-proxy is theoretical until we observe an actual email delivery. But add a one-liner to the "Honorable mentions" block noting F5 explicitly: "Mass assignment on `verification_mode` (Security F5) — HIGH but theoretical until the verification-link email delivery is observed; deferred for follow-up."

### S4 — Background in features/02 doesn't establish threat-actor framing
The Background says "valid bearer token … x-api-key … client_uuid" — purely a happy-path setup. The auditor persona expects the security scenario Background to read like an attacker's setup. Recommend adding one line: "Given an attacker has obtained ONE valid (`x-api-key`, Bearer) pair (insider, leaked CI secrets, or one compromised integrator)." This is already strongly implied in the feature title and the audit doc but the .feature file itself doesn't say it.

### S5 — Reproduction step in README #2 references the wrong URL
Line 35: `POST https://api.balampay.com/webhooks/register`. Probe evidence shows that's correct (no `/v1/` prefix), but it's worth a parenthetical "(no `/v1/` prefix — per DRIFT-G6)" so the reader doesn't try `/v1/webhooks/register` and get a 403 and dismiss the finding.

### S6 — Probe README for SSRF speculates about pivots that weren't tested
The probe README (`ssrf-webhook-delivery-confirm/README.md` § "Attack chain" steps 4–5) speculates about IMDSv1 vs IMDSv2 behavior and "DNS rebinding / Host header injection." That's auditor-persona content (we explicitly call out DNS rebinding as a follow-up in `05-security-audit.md` § Open questions), but in a public deliverable readers may take the speculation as confirmed. Reword to clearly separate "what we observed" from "what an attacker could do next if conditions hold."

---

## What I'd add — NICE-TO-HAVE

### N1 — A redaction audit appendix
We claim every evidence file passes `_redact.py`. A 1-page appendix that lists the redaction rules (`Authorization`, `x-api-key`, `password`, `client_id` in bodies) and shows the diff "before/after redaction" on one representative file would head off any "did you leak a token?" challenge from Diego's InfoSec team.

### N2 — Cross-reference each finding against PCI-DSS / GLBA control numbers
F2/F3 (unmasked PII) → GLBA Safeguards Rule Reg P, PCI-DSS Req 3.x (mask PAN — applies by analogy to account numbers). F4 (TLS) → PCI-DSS Req 4.1, FFIEC IT Handbook ch. on cryptography. We mention these in narrative; pin them in a control table so a regulated-buyer (BIA, N1co) InfoSec reviewer can cross-walk in 30 seconds.

### N3 — A short "scope discipline" appendix
Two paragraphs documenting what we did NOT do: (a) we did not test prod; (b) we did not harvest IMDS data; (c) we did not test a second tenant for cross-tenant `client_uuid` takeover; (d) we did not attempt to exfiltrate any actual SSN beyond the test 000-00-0000. This protects us from "you went beyond scope" pushback.

### N4 — Webhook signature scheme probe
The audit notes the webhook signature secret behavior on `secret: null` wasn't probed. One additional probe — register with `secret: null`, capture an inbound delivery's `x-signature-sha256` header, verify whether the signature is computed against `null` or omitted entirely — would close GAP-11 cleanly. Half-day of work; high payoff because it tells the integrator whether they can trust the signature at all.

### N5 — Add `@cvss-9-1` and `@owasp-api7-2023` tags
The features carry `@security` but not severity tags. CI / triage systems benefit from `@cvss-critical` and `@owasp-api-N` tags for filtering. Optional; cosmetic.

---

## Disclosure-language verdict

**Is the public-publish-without-pre-disclosure stance defensible? YES — but ONLY after B2 is fixed.**

Reasoning:
1. This is a PM take-home exercise on a public sandbox endpoint Kira advertises. The findings are reproducible from the public docs + sandbox credentials provided to all candidates. That is fundamentally different from a paid pentest engagement.
2. We didn't escalate (no IMDS exfil, no real-tenant cross-`client_uuid` testing, no prod probes, no real PII used).
3. All evidence is redacted; no live credentials in the public repo.
4. The findings benefit Kira — they're getting a free, evidence-backed security audit from a candidate.

**BUT** the README and feature files currently lie about having pre-disclosed to Diego. If Diego reads "raised privately; awaiting acknowledgement" in the README and the feature files when no such email/Slack thread exists, the entire deliverable's credibility collapses. The fix is straightforward: state the truth. "Included in this public exercise deliverable; the candidate (per the exercise framing) was not in a position to pre-disclose. Recommended remediation: Diego confirms whether IMDS is actually reachable from the webhook fetcher's VPC, and prioritizes the TLS-1.2-minimum migration and PII-masking layer in v2026-XX-XX."

Once B2 is fixed, the stance is defensible. As written today, it is not.

---

## Overall security verdict

**Ship: NOT YET.**

Three blocking items (B1 evidence paths, B2 disclosure honesty, B3 IMDS over-claim). All three are 5-minute text fixes; none requires re-running a probe or generating new evidence. The underlying findings are solid — F1 is the highest-value technical security finding in this whole exercise; F2/F3 are the highest-value regulatory/compliance findings; F4 is the procurement-gate finding. They deserve to ship — but with truthful framing and working evidence links.

After fixing B1/B2/B3, also action B4 (UUID literals in feature 02). Then ship.

The deliverable's security track is at probably 92% quality once the four blockers are cleared. The remaining 8% is the SHOULD-FIX items (CVSS uncertainty band, TLS exploit-difficulty caveat, mass-assignment honorable mention) which can land as a "v1.1" update after publication.
