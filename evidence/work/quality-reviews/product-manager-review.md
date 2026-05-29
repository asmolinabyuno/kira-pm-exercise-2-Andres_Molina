# Product Manager Quality Review

**Date:** 2026-05-28
**Pre-push review of:** README.md + 03-phase-1-findings.md + 13-docs-vs-partner-guide-delta.md + decision-log.md
**Reviewer lens:** Senior PM evaluating APIs for procurement-stage enterprise buyers (Banco Industrial / N1co lens). Grading rubric weights: Prioritization 40%, Specificity 30%, Integration depth 20%, Communication 10%.

---

## What's strong

- **README Finding #1 (META) is properly framed as structural, not "more docs needed."** The line "Kira's public docs are the broken layer; the real contract is partner-distributed" is the highest-leverage PM observation in the whole deliverable — it reframes ~80% of Phase 1 findings as symptoms of one root cause, and it's grounded in a quantified claim ("22 of our 53 drifts are acknowledged by the partner guide; 0 of 53 are acknowledged by the public docs"). That single sentence is the kind of insight that wins prioritization on a real evaluation.
- **Cost framing on Finding #1 is concrete in PM terms.** "4–8 engineering days lost vs. <1 day for a partner-doc-equipped integrator" + the explicit "for a Banco Industrial / N1co procurement evaluation this is the difference between 'ship a prototype' and 'fail the eval'" is exactly the unit-of-cost language the brief asks for. None of the other four findings clear this bar as cleanly (see push-back below).
- **Finding #5 (sandbox base URL compound) is well-defended despite being "just" a docs bug.** The reframing as "even the partner guide is wrong" + the 2026-05-28 revalidation block + the DRIFT-1b/-1c compound naming makes the case that this is universal Day-1 friction, not a minor doc nit. The reproduction is the cleanest in the README — 4 copy-pasteable curls that demonstrate the contradiction.
- **The Honorable mentions section signals calibration discipline.** Demoting the 6-error-envelope finding and idempotency/webhook-CRUD findings to honorable mentions despite their pre-delta CRITICAL status is exactly the severity calibration the brief rewards. It shows the integrator can tell the difference between "a partner concedes + ships a fix" and "no one acknowledges this."
- **The Postscript on `03-phase-1-findings.md` is honest about the reframe.** It explicitly notes Findings #1, #3, #4 were demoted and absorbed into the META-finding, and Finding #5 (Wallets) was inverse-invalidated. No spin — just the reclassification. Devil-advocate notes section also documents which Phase 1 candidates were trimmed and why.

---

## What needs fixing — BLOCKING (must address before push)

### B1. Three of five Findings reference evidence directories that don't exist.

**File:** `README.md` lines 33, 44
**Findings affected:** #2 (Webhook triple-vector) and #3 (PII unmasked)
**The problem:** README cites these paths as the load-bearing evidence anchors:
  - `evidence/work/security/webhook-ssrf/` → does not exist. Actual: `evidence/work/security/ssrf-webhook-delivery-confirm/`
  - `evidence/work/abuse/webhook-spoof/` → does not exist. Actual: `evidence/work/abuse/webhook-spoof-no-event-filter/`
  - `evidence/work/security/pii-unmasked-users/` → does not exist. Actual: `evidence/work/security/info-disclosure-account-details/`
  - `evidence/work/security/pii-unmasked-recipients/` → does not exist. Actual: same `info-disclosure-account-details/` (one dir covers both surfaces).

A reviewer clicking any of these links gets a 404. For a deliverable graded 30% on Specificity, a broken evidence path on a CRITICAL/CVSS-9.1 finding is a high-cost miss — it undercuts the central PM claim ("every finding needs evidence").

**Fix:** Update the four paths in README.md to match the actual directory names, or rename the directories to match the README. Renaming the directories is preferable because the README names are more readable (`webhook-ssrf` > `ssrf-webhook-delivery-confirm`), but either fix works as long as one is applied consistently and the `features/*.feature` files are checked for the same drift.

### B2. The "Disclosure status" wording is internally contradictory on a public GitHub deliverable.

**File:** `README.md` lines 25, 36, 47, 58, 69
**Findings affected:** all 5
**The problem:** Every finding ends with "recommended next step is coordination with @Diego before broader publication" — but the README itself **is** the broader publication (public GitHub repo per the brief). Finding #2 in particular discloses a CVSS 9.1 SSRF chain with full reproduction steps (exact IMDS payload, exact Kira egress IP `54.201.149.241`), then claims it's a private disclosure. The framing is incoherent and looks like the integrator hedged without thinking through that the artifact is public on push.

**Fix (one of):**
  - **Option A (recommended) — own the disclosure timeline.** Replace each Disclosure status line with the actual sequence: "Raised privately with @Diego on [date] via Slack; awaiting acknowledgement before publishing this repo publicly" (if true), or "Will be raised with @Diego in the post-submission Slack thread; this repo is shared with Kira hiring only at submission" (if true), or "Disclosed inline in this submission per the brief's GitHub-repo requirement; coordination with @Diego on remediation is the next step" (if true and outreach hasn't happened).
  - **Option B — drop the Disclosure status block from Findings #4 (TLS — no live exploit) and #5 (base URL — not security-sensitive)** and keep it only on #2 and #3, with the wording above.
  - Whichever option, **align with the Outreach section** so the story is consistent (see B4).

### B3. Severity calibration: "5 / 5 CRITICAL" is the single weakest PM signal in the deliverable.

**File:** `README.md` line 16: "Severity ordering: CRITICAL → CRITICAL → CRITICAL → CRITICAL → CRITICAL."
**The problem:** The brief grades 40% on Prioritization. A top-5 where everything is the maximum severity collapses the ranking signal — the whole point of ranking is *forcing distinctions*. The internal acknowledgement on line 16 ("The 5th is downgraded internally...but kept at CRITICAL because every integrator hits it on call #1") is the exact kind of grade-inflation a skeptical CFO will flag in 30 seconds. Worse, Finding #4 (TLS 1.0/1.1) is a **regulatory blocker with no live exploit shown** — its severity is contextual (CRITICAL for a BIA / N1co procurement, MEDIUM for a tech-forward fintech with no compliance gate). Finding #5 is explicitly described as a "compound docs + congruence" issue that you decided to leave at CRITICAL by author's discretion.

**Defensibility test against a skeptical CFO:**
  - Finding #1 (META): CRITICAL defensible — concrete cost in days + procurement framing.
  - Finding #2 (Webhook triple-vector / CVSS 9.1): CRITICAL defensible — security chain with reproduced exploit.
  - Finding #3 (PII unmasked): CRITICAL defensible — regulatory + 1-credential bulk-scrape proven.
  - Finding #4 (TLS 1.0/1.1): **CRITICAL not fully defensible without a "Banco Industrial requires X" citation.** Without that, this is a HIGH that you couldn't ship the procurement gate with — which IS the framing already, but the severity should match.
  - Finding #5 (sandbox base URL): **CRITICAL not fully defensible.** Day-1 friction, yes; but a 4–8h fix, not a regulatory or data-leakage blocker. This is the textbook HIGH.

**Fix (one of):**
  - **Option A (recommended) — accept the ranking the work actually did.** Change Finding #4 to HIGH and Finding #5 to HIGH. The header becomes "Severity ordering: CRITICAL → CRITICAL → CRITICAL → HIGH → HIGH". This is honest, defensible against a skeptical CFO, and demonstrates the calibration discipline the rubric rewards.
  - **Option B — keep CRITICAL on #4 and #5 but add the explicit "compound" justification in the severity line.** E.g., "**Severity:** CRITICAL (compound — Day-1 friction blocks all integrators; ranked here because every reader hits it before any other finding can matter)." This is weaker than Option A but at least removes the meta-comment from line 16.
  - **Whichever option, delete line 16's meta-comment** ("Severity ordering: CRITICAL → CRITICAL → CRITICAL → CRITICAL → CRITICAL. The 5th is downgraded internally...") — that sentence is the tell that the calibration is fragile.

### B4. The Outreach section reads as "we wrote questions" but never confirms outreach happened.

**File:** `README.md` lines 116-126 ("Outreach to Kira" section)
**The problem:** The brief explicitly says "Zero outreach is a flag, not a feature" and lists Communication at 10% of the grade. The current Outreach section lists 6 questions framed for @Diego / @Nicolle but doesn't state whether any of them have been sent. The prompt-log only references the questions being "flagged for @Nicolle/@Diego in plan § 8" (`prompt-log.md` L152) — no Slack thread, no DM, no acknowledgement. A grader reading "Questions surfaced from the evaluation, framed for @Diego (Eng) and @Nicolle (PD)" gets no signal whether the integrator actually engaged.

**Fix:** Either:
  - (a) actually send the outreach in Slack now and update this section with the message timestamps + any response received, or
  - (b) state honestly: "These questions are queued for the post-submission Slack thread. Time-boxed by the 2-day exercise window; outreach prioritized to drop into a single high-signal Slack message rather than 10 fragmented DMs over 48h" — this owns the choice and still scores on the Communication axis because it shows the integrator thought about *how* to engage, not just *that* they should.

The current framing is the worst of both — it implies engagement without confirming it.

---

## What should improve — SHOULD-FIX (improves quality, not blocking)

### S1. Finding #2 "Why this matters to a client" is a paragraph, not a one-liner.

**File:** `README.md` lines 32 (Finding #2)
**The problem:** The brief and the persona both call for a *one-line* integrator-impact framing per finding. Finding #2's "Why this matters" runs ~12 lines and front-loads the technical reproduction (URLs, CIDR, header names). The cost-to-client line is buried at the bottom ("Combined chain..."). A skim reader can't extract the integrator pain in 5 seconds.

**Fix:** Move the one-line client-impact statement to the front of the block. Suggested rewrite (one sentence):
> "**Why this matters to a client:** One leaked Bearer + API key registers a webhook that pulls **another tenant's** payout events to an attacker-controlled URL, unsigned, over cleartext HTTP, with Kira's egress fetcher reaching AWS IMDS at delivery — and the API returns no id, no list, no delete to revoke it. Five compounding gaps in one endpoint, none acknowledged by either doc."
>
> Then the current technical detail moves below as "Mechanism:" or stays under "Reproduction:".

### S2. Finding #3 lacks one cost-of-harm anchor that a CFO can grasp.

**File:** `README.md` line 43 (Finding #3)
**The problem:** "State money-transmitter / GLBA-adjacent finding that blocks production access" is the right *framing* but a CFO would push back: "How much access? How many records? What's the dollar exposure?" The README has the empirical data to anchor this — "1 leaked credential bulk-scrapes the entire customer book in plaintext" is in the finding, but the dollar/scale framing is implicit.

**Fix:** Add one number. Suggested: "An integrator's prod API key — typically stored in CI/CD env vars and rotated quarterly — becomes a single-credential plaintext customer-book exfiltration vector. State money-transmitter examiners (NY DFS, TX Dept. of Banking) treat unmasked SSN on a list endpoint as a Tier-1 control finding; remediation timelines are typically <30 days under consent decrees." Or any equivalent that names the unit-of-harm.

### S3. Finding #4 (TLS) needs the specific compliance citation to defend its CRITICAL severity.

**File:** `README.md` line 54 (Finding #4)
**The problem:** "PCI-DSS Req 4.1, FFIEC, and US state money-transmitter rules require TLS 1.2 minimum" is correct but unanchored. A skeptical buyer will ask "PCI-DSS doesn't apply here because Kira isn't a card processor for the client" — and the integrator needs an answer ready. The defensible angle is **PCI 4.0 § 4.2.1 / NIST SP 800-52r2 / FFIEC IT Examination Handbook (Information Security booklet § "Encryption")**.

**Fix:** Replace the generic "PCI-DSS Req 4.1, FFIEC..." with one named citation — e.g., "NIST SP 800-52r2 (transport layer security guidance for federal systems, adopted by FFIEC for member banks) deprecates TLS 1.1 and below; PCI-DSS v4.0 § 4.2.1 sunset deadline (March 2025) is past." This converts the finding from "trust me, it's a blocker" to "here is the exact rule that blocks it." Same fix unblocks the severity discussion in B3.

### S4. The "Coverage" stats line at the top of the README is impressive but unattributed.

**File:** `README.md` line 10: "18/30 endpoints empirically validated · 53 drift events captured · 78 underlying findings synthesized · 108-row test matrix..."
**The problem:** Each number is real and load-bearing, but a grader can't audit any of them without spelunking. The "108-row test matrix" went to 112 per DEC-008 line 168 ("total 108 → 112 rows"), so this line is also stale.

**Fix:** Update to current totals (112-row matrix per DEC-008) and link each number to its source artifact in a footnote or parenthetical. E.g., "18/30 endpoints empirically validated ([`04-integration-log.md`](evidence/analysis/04-integration-log.md)) · 53 drift events ([same](evidence/analysis/04-integration-log.md) §) · 112-row test matrix ([`01-test-matrix.md`](evidence/analysis/01-test-matrix.md))".

### S5. The 03-phase-1-findings.md Postscript doesn't update individual finding severities inline.

**File:** `evidence/analysis/03-phase-1-findings.md` Postscript (lines 269-287)
**The problem:** The Postscript narrates the reclassification — but Finding #1 above it still reads `**Severity:** CRITICAL` on line 37 with no inline note. A reader of the file scrolls from "this is CRITICAL" at top to "actually it's DOWNGRADED CRITICAL → HIGH" in the Postscript at the bottom and the two don't visibly reconcile. Decision-log DEC-008 has the test-matrix updates but doesn't propagate them into the source doc's per-finding headers.

**Fix:** Add a one-line callout under each affected finding's Severity field — e.g., `**Severity:** CRITICAL → HIGH (partner-side; public-doc severity holds CRITICAL — see Postscript)`. Quick mechanical edit, large readability win.

### S6. Delta doc Bucket A (INVALIDATED) only has 2 entries — make sure the spin-check is real.

**File:** `evidence/analysis/13-docs-vs-partner-guide-delta.md` § Bucket A (lines 19-28)
**The problem:** "INVALIDATED" should be the bucket where the team owns getting things wrong. Today only GAP-22 (sandbox simulate-deposit endpoint) is a clean invalidation; the Wallets finding is described as "inverse-invalidation" which is really a *reframe*, not "we were wrong." The honest read: of 28+ Phase 1 GAPs, only 1 was truly invalidated by partner-doc evidence. That's actually a strong defense of the Phase 1 work — but the Bucket A heading currently obscures it.

**Fix:** Split Bucket A into two sub-buckets: "A1 — Invalidated (we were wrong)" with GAP-22 only, and "A2 — Reframed (same gap, different framing)" with the Wallets finding. Then the headline "Phase 1 had 1 false-positive out of 11 findings" becomes legible — and that's a credibility multiplier.

---

## What I'd add — NICE-TO-HAVE

### N1. One-paragraph "How a buyer should read this README" at the top.

**Rationale:** Right now the README jumps from coverage stats → top-5 → repo layout. A 4-line "If you're the engineering lead at Banco Industrial procuring Kira: read Finding #1, run the 5 reproductions, decide whether to escalate to InfoSec on #2-#4 before signing" header would orient a non-Kira reader (which is most graders) in 10 seconds.
**Cost:** 5 minutes.

### N2. Add a "What would change our top-5" section.

**Rationale:** Demonstrates calibration honesty. Two bullets:
  - "If we'd received the Postman collection on Day 0, the META-finding would split into two: one about public-docs incompleteness, one about partner-channel discovery friction."
  - "If we'd unblocked DRIFT-23 (sandbox manual approval) before Day 2, Batches D and F would have run and Findings #4 (TLS) might have been bumped by a Payout state-machine surprise."

This is the kind of meta-commentary that signals the integrator can distinguish what they found from what they didn't get to look at.
**Cost:** 15 minutes.

### N3. Add a dated "Outreach log" markdown file.

**Rationale:** Even if outreach hasn't happened by submission time, a `evidence/work/outreach-log.md` with the 6 questions + "drafted YYYY-MM-DD, to send YYYY-MM-DD in #pm-exercise" gives the grader something concrete to point at for the 10% Communication score. Sub-bullet: include the exact Slack message draft you'd send.
**Cost:** 10 minutes.

### N4. Sanity-check the "0 / 53 drifts acknowledged by public docs" claim.

**Rationale:** This number is doing a LOT of work on Finding #1 ("22 of our 53 drifts are acknowledged by the partner guide; 0 of 53 are acknowledged by the public docs"). For defensibility, list the 22 partner-acknowledged DRIFT numbers in a footnote or hyperlink to delta doc § Bucket B+C. If a single DRIFT in the public-docs error-handling page would invalidate "0 of 53", that's a finding-level credibility risk.
**Cost:** 15 minutes — scan delta doc § Bucket C + cross-check against public `/docs/error-handling` snapshot. Worth it.

---

## Overall PM verdict

- **Ship as-is:** **NOT YET**
- **Reasoning:** The substance — METHODOLOGY, top-5 selection, Bucket A/B/C analysis, severity calibration discipline — is genuinely strong. The META-finding is the kind of insight that distinguishes a PM hire. But the deliverable has three integrity-level issues that a 30%-Specificity grader will catch in their first 10 minutes (broken evidence paths, "private disclosure" wording on a public repo, 5-of-5 CRITICAL severity calibration). Each is a 15-minute fix. Shipping with them intact would undercut the credibility of the substantive work.
- **If NOT YET — smallest set of fixes that flips to YES:**
  1. Fix the four broken evidence paths (B1). ~10 min.
  2. Rewrite the 5 Disclosure status lines to match the actual disclosure mode of a public GitHub repo (B2). ~10 min.
  3. Demote Findings #4 and #5 to HIGH (or add the explicit compound justification per B3 Option B) AND delete the meta-comment on README line 16. ~10 min.
  4. State outreach mode honestly in the Outreach section — sent vs. queued (B4). ~5 min.
  - **Total: ~35 minutes of edits to convert from NOT YET to YES.** None of this requires re-doing analysis; it's all the framing layer.

Optional but high-leverage: S1 (Finding #2 one-liner), S3 (TLS citation), N3 (outreach log). Each is 5-15 minutes. With these the deliverable moves from "ship-ready" to "PM-of-the-quarter."
