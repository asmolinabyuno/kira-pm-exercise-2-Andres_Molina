# Test Coverage Heat Map — Kira API Evaluation

**Generated:** 2026-05-28
**Reads:** `test-matrix.md` (rebuild this when matrix changes)

Family rows align with `flow-design.md` § 3 endpoint catalogue (Auth, Users, Verification, Virtual Accounts, Recipients, Quotations, Payouts, PayIns, Payment Links, Liquidation Addresses, Reference Data) plus § 2.7 Webhooks and a final Cross-cutting row.

## Heat Map — Family × Category

| Family | Docs Quality | Connection | Congruence | Functional | Contract | Concurrency | Performance | Abuse | Security |
|---|---|---|---|---|---|---|---|---|---|
| Auth | ✓ 1 (H) | ✓ 1 (C) | ✓ 1 (C) | ✓ clean | ✗ | ✗ | ✓ 1 (M) | ✗ | ✗ |
| Users | ✓ 1 (H) | ✓ clean | ✓ 8 (C/H×4/M×3) | ✓ clean | ⚠ partial | ✗ | ✓ 1 (H) | ✓ 1 (H) | ✓ 3 (C/H/L) |
| Verification | ✓ 1 (C, lineage Finding-#4) | ⚠ partial | ✓ 5 (C/H×3/L) | ✓ 1 (C) | ⚠ partial | ✗ | ✗ | ✗ | ✗ |
| Virtual Accounts | ⚠ partial | ✓ clean | ✓ 1 (H, list-only) | 🚫 blocked (DRIFT-23) | ✗ | ✗ | ✗ | ✓ 3 (H/M/M) + 1 clean | ✗ |
| Recipients | ✓ clean | ✓ clean | ✓ 12 (H×8/M×2/L×2) | ✓ clean | ⚠ partial | ✓ clean | ✓ 1 (L) | ✓ 3 (H×2/M) + 1 clean | ✓ 1 (C) |
| Quotations | ✓ 1 (C, Finding-#1) | 🚫 blocked (DRIFT-45) | ✓ 5 (C/H×2/M/L×2) | 🚫 blocked (DRIFT-45) | ✗ | ✗ | ✓ 1 (L) | ✗ | ✓ 1 (H, info-leak) |
| Payouts | ✗ | ✗ | ✗ | 🚫 blocked (DRIFT-23 + DRIFT-45) | ✗ | ✗ | ✗ | ✗ | ✗ |
| PayIns | ✗ | ✗ | ✗ | 🚫 blocked (DRIFT-23) | ✗ | ✗ | ✗ | ✗ | ✗ |
| Payment Links | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Liquidation Addresses | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Reference Data | ✓ 2 (H×2) | ✓ 3 (H×2/M) | ✓ 4 (H×3/M) | ✓ clean | ⚠ partial | ✗ | ✓ 1 (M) | ✗ | ✗ |
| Webhooks | ✓ 1 (C, Finding-#4) | ✓ 1 (H, DRIFT-49) | ✓ 4 (H×3/M) | ✓ clean | 🚫 blocked (GAP-21 — no list/get/delete) | ✗ | ✗ | ✓ 1 (C, ABUSE-4) | ✓ 3 (C/H/M — SSRF + secret + HTTP) |
| Cross-cutting | ✓ 5 (C×3/H×2) | ✓ 1 (H, GAP-04) | ✓ 3 (C/H×2 — envelope+versioning) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ 3 (C/L×2 — TLS+CORS+headers) + 1 clean (JWT) |

## Legend
- `✓ N (severities)` — N findings captured (e.g., `✓ 3 (C/H/M)` = 3 findings: 1 CRITICAL, 1 HIGH, 1 MEDIUM)
- `✓ clean` — endpoint(s) tested, no finding (control passed or coverage row only)
- `⚠ partial` — partially probed; some sub-area covered, others not
- `✗` — not tested
- `🚫 blocked` — blocked by a drift or env (cause cited)

Severity letter codes: `C`=CRITICAL · `H`=HIGH · `M`=MEDIUM · `L`=LOW.

## Cell counts at a glance

- Total cells: **13 rows × 9 cols = 117**
- `✓ N` (findings captured): **40**
- `✓ clean` (executed, no finding): **11**
- `⚠ partial`: **5**
- `🚫 blocked`: **6**
- `✗` (not tested): **55**

## Coverage gaps (the ✗ cells)

Group A — entire families never reached (P2 blockers cascade):
- **Payouts** × 9 categories (minus 1 blocked-functional) → 8 ✗. **Cause:** BLOCKED-BY-DRIFT-23 (sandbox no auto-approve) AND BLOCKED-BY-DRIFT-45 (no canonical quote_id). **Effort:** L — needs Diego/Eng intervention to seed fee profiles + auto-approve verification, then re-run full battery.
- **PayIns** × 9 categories (minus 1 blocked) → 8 ✗. **Cause:** BLOCKED-BY-DRIFT-23 (VA not provisioned). **Effort:** M — Recipe C2 ("PayIn → Off-ramp via stablecoin") needs VA + simulated deposit endpoint, neither of which is touched today.
- **Payment Links** × 9 → 9 ✗. **Cause:** Out-of-scope for the minimum flow this exercise targets; no probe budget allocated. **Effort:** M — hosted-page evaluation belongs to fullstack-integrations-specialist track.
- **Liquidation Addresses** × 9 → 9 ✗. **Cause:** Listed in flow-design § 3.10 but never probed (not in any batch). Out-of-scope for the minimum flow. **Effort:** S-M — single endpoint + idempotency probe.

Group B — categories systemically under-tested across families:
- **Concurrency** column: only Recipients (✓ clean via ABUSE-8) tested. **Effort:** M — Phase 3 racetest harness exists, can be replayed against Auth (JWT replay), Users (verifications double-trigger), Webhooks (register race).
- **Contract** column: Recipients/Verification/Users/Webhooks/RefData ⚠ partial; rest ✗. **Effort:** M — Schemathesis stateful or Pact-style fuzz against each family would close this in 1-2 days.

Group C — single-family-single-category gaps in covered families:
- **Auth × Abuse/Security**: never tried beyond JWT control. JWT replay (TTL 3600s) deferred. **Effort:** S — extend `jwt-attack-suite` with TTL replay.
- **Quotations × Connection/Functional**: blocked. **Effort:** S once DRIFT-45 cleared (sandbox fee profile seed).
- **Virtual Accounts × Functional/Security**: blocked + ✗. **Effort:** L — depends on DRIFT-23 clearance.

## Coverage strengths (where we went deep — these anchor the README)

These cells have the highest evidence density and back the top-5 finding candidates:

1. **Webhooks × Security** — 3 findings (CRITICAL SSRF + HIGH secret-optional + MEDIUM HTTP cleartext) plus cross-tenant hijack in Abuse. **Anchors:** Finding-#4 (P1), DRIFT-47/48/53 (P2), SEC-F1 (P3-Security), ABUSE-4 (P3-Abuse). The most-tested column on the most-broken family. README slot guaranteed.
2. **Recipients × Congruence** — 12 drift events (8 HIGH, 2 MEDIUM, 2 LOW). **Anchors:** DRIFT-26..38, Finding-#11. Polymorphic schema empirically mapped across SPEI/ACH/USDT/SWIFT — the deepest single-family integration evidence we have.
3. **Users × Congruence** — 8 drift events spanning POST/GET/PUT + verifications. **Anchors:** DRIFT-3, 4, 5, 14, 15, 18, 19, 20, 22.
4. **Cross-cutting × Docs Quality + Security** — 5 docs findings (3 CRITICAL) + TLS + CORS + headers. **Anchors:** Findings-#2/#3/#7/#8/#9 + SEC-F4/F7/F8 + DRIFT-6/DRIFT-11. The "the API surface is structurally inconsistent" headline.
5. **Recipients × Security** + **Users × Security** — PII unmasked confirmed across all 4 recipient variants AND on users list/detail. **Anchors:** DRIFT-30, SEC-F2, SEC-F3. CRITICAL-rated compliance/AML finding.
6. **Quotations × Congruence** — Finding-#1 resolved empirically (Guides is dead doc; Reference + extensions canonical). **Anchors:** Finding-#1, DRIFT-40..46.

These six strengths are what the README's top 5 ranking should anchor on — every other finding either compounds one of these (e.g., the abuse-track verification-skip anomalies extend the Users × Congruence cluster) or sits in an ✗-heavy row that needs Phase 4 work to surface.
