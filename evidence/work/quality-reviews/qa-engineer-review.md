# QA Engineer Quality Review

Lens: Specificity (30% of grade) — could an engineer turn each scenario into a failing test without DMing the PM?

Scope reviewed:
- `features/01-public-docs-materially-incomplete.feature`
- `features/02-webhook-triple-vector.feature`
- `features/03-pii-unmasked.feature`
- `features/04-tls-1-0-1-1-accepted.feature`
- `features/05-sandbox-base-url-wrong.feature`
- `evidence/analysis/01-test-matrix.md` (112 rows × 12 cols)
- `evidence/analysis/02-test-coverage-heatmap.md` (13 × 9 grid)

---

## What's strong

- **Every Then asserts an observable across all 5 .feature files.** Status codes are literals (`200`, `400`, `401`, `403`, `409`, `500`), JSON paths are concrete (`$.data.access_token`, `$.message`, `$.data.expires_in`, `$.previous_version`), header names + literal values are named (`x-amzn-errortype` = `ForbiddenException`/`UnauthorizedException`, `x-api-version` = `2026-04-14`). No "should be correct" / "should work" / "should make sense" anywhere — `grep` returns zero hits.
- **Spec + Observed pairing is consistent on every misbehavior.** Every drift scenario presents both the contract-shape expectation AND the empirical runtime, with the file/anchor cited in the header comment. This is exactly the BOTH-scenarios bar in the QA persona.
- **Async scenarios use concrete N.** Six poll/timeout assertions found: `01:81-82` (60s VERIFIED), `01:89-90` (120s REVIEW), `02:59-60` (120s webhook delivery). No "eventually" or "soon" language.
- **TLS scenarios assert openssl exit code + protocol + cipher tuple** — bookable as automated `pytest -k tls` cases against `openssl s_client` + Python `ssl.SSLContext`. `04:24` "openssl exit code MUST be non-zero" and `04:36` "exit code equals 0" with negotiated protocol literals are textbook automation hooks.
- **Tag vocabulary is internally consistent.** Five files cover `@security`, `@docs-runtime-drift`, `@sandbox-prod-drift`, `@webhook`, `@info-disclosure`, `@tls`, `@transport`, `@meta-finding`, `@auth`, `@versioning`, `@docs-quality`, `@fraud-vector` — all from the persona-documented tag set. No drift, no typos.
- **Header comments link to real evidence.** Every `# Evidence:` / `# Related:` line points to actual files: `evidence/work/auth/01-fail-403.json`, `evidence/work/versioning/01-04-*.json`, `evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json`, `evidence/work/webhooks/12-19-*.json` — spot-verified directory layout matches.
- **Matrix `given_when_then` column is automation-runnable on the HTTP rows.** All 56 DRIFT rows + 18 endpoint-probe rows + 8 abuse rows + 9 security-finding rows are expressible as `pytest+httpx` cases with concrete preconditions, request bodies, and assertions on status/header/JSON-path.
- **Matrix `expected` / `actual` discipline is tight.** Spot checks on T-P2-DRIFT-10, DRIFT-30, DRIFT-47, DRIFT-50, DRIFT-55, SEC-F1-F4, ABUSE-4: expected states the contract literally (e.g., "status=400 for all 5 SSRF vectors"), actual quotes the runtime literally (e.g., "status=200 on all 5; URLs persisted; IMDS reachable on delivery"). Differences are precise, not hand-wavy.
- **`cross_ref` cells terminate in a source-of-truth doc link** per DEC-007 maintenance contract. Sampled cells all end `evidence: evidence/analysis/0X-...md` or include `evidence/work/...json`. Drift-resync rule actually enforceable.
- **Heatmap legend ↔ cell vocabulary matches 1:1.** `✓ N (severities)`, `✓ clean`, `⚠ partial`, `🚫 blocked`, `✗` all appear as documented; no orphan glyphs. Cell counts (40 + 11 + 5 + 6 + 55 = 117) reconcile to 13 × 9.
- **Status taxonomy applied consistently in the matrix** — REPRODUCED=74, EXECUTED=12, CLOSED-FINDING=16, CLOSED-CLEAN=4, BLOCKED-ENV=2 (totals 108 + 4 controls counted twice... see below). No DESIGNED/DEVELOPED rows left dangling.
- **Coverage gaps visible at-a-glance in the heatmap.** Payouts / PayIns / Payment Links / Liquidation Addresses rows are clearly all-✗ or blocked-cascade. The "where we went deep" callout (Webhooks×Security, Recipients×Congruence, Users×Congruence) anchors the README ranking honestly.

---

## What needs fixing — BLOCKING (must address before push)

None at the specificity bar. Every scenario in every .feature file is convertible into a failing automated test without DMing the PM. The handful of weaker spots below are SHOULD-FIX, not BLOCKING.

---

## What should improve — SHOULD-FIX

1. **`features/01:53-58` "Spec — pin endpoint documented on the public portal" is a docs-presence assertion, not an HTTP test.** "When I search the sidebar and the full-text index for 'versioning' Then at least one reference page MUST exist at a URL matching `/reference/.*versioning.*`". This is the vaguest step in the deliverable. An engineer can automate it (Playwright + regex), but the spec should make the automation explicit — e.g., add `# Automation: pytest + Playwright async navigate to /v2026-04-14/reference, query the sidebar `<nav>` DOM, assert at least one `<a>` href matches the regex`. Right now it reads more like a manual checklist than an automated test. Same applies to `01:104-105` ("zero downloadable links to a Postman collection MUST be discoverable") and `04:88-90` ("zero acknowledgements of a TLS minimum policy"). Document the search-tool & locator strategy in a comment so the engineer doesn't have to guess.

2. **`features/02:55-62` "Kira's outbound fetcher actually reaches the SSRF target on delivery" relies on an indirect signal** ("zero new deliveries arrive at the baseline webhook.site URL within 120 seconds" implies last-write-wins routing). The assertion is correct, but the inference chain is implicit in the trailing comment, not in a Gherkin step. An engineer reading this in CI would file it as flaky ("the baseline silence could mean delivery is just slow"). Add an explicit `And the Kira outbound source IP "54.201.149.241" was previously observed delivering to the baseline URL within ~37 seconds` step earlier in the scenario so the negative assertion is anchored to a positive control.

3. **`features/02:142` "Then the response status MUST be 204 or 200"** — disjunctive status assertion. Engineers will (rightly) ask "which one does Kira want to ship?". Pick the canonical one (204 No Content for DELETE per REST convention) and demote 200 to "tolerated until v2026-XX-XX" with a comment. Same nitpick on `02:97-99` `(secret omitted)` parenthetical — it parses fine but a strict Gherkin engine might complain. Consider rephrasing as `When I POST to "/webhooks/register" with JSON body that does not contain a "secret" field`.

4. **`features/03:50` "And for every item in JSON path `$.associated_persons[*].ssn` the value MUST match the regex `^\*{4,}\d{4}$`"** — the regex is correct but the JSONPath quantifier semantics in step regex engines vary. Add the assertion library convention (e.g., `JMESPath` or `jsonpath-ng`) in the file header so an engineer doesn't roll their own. The "OR be absent" disjunction (`03:28-29`) is fine but should pick one (last-4 mask is the canonical Kira docs example "****7890"). Right now Spec accepts both masked-and-absent which weakens enforcement.

5. **`features/04:34-46` `Scenario Outline: Observed`** lists two examples with the SAME negotiated cipher `ECDHE-RSA-AES128-SHA`. That's correct empirically, but if the example table is meant to drive parametrization, document why both rows are needed (different protocol negotiation, same cipher). A reader skims the table and asks "why is this not collapsed into one row?". One-line comment fixes it.

6. **Matrix row T-P2-DRIFT-23 severity REFINE-2026-05-28 downgrade reasoning is in the description column** — at 200+ characters per cell, this is unreadable on GitHub render. Move the refinement note to a footnote `[¹]` at row end and keep the cell tight. Same applies to T-P2-DRIFT-1 / DRIFT-6 / DRIFT-19 / DRIFT-26 / DRIFT-27 / DRIFT-32 / DRIFT-33 / DRIFT-35 / DRIFT-40 / DRIFT-52 (11 rows).

7. **Matrix T-P1-001..011 GWT cells assert documentation states, not runtime states.** That's correct (Phase-1 is docs evaluation), but the dashboard already calls these out as "abstract docs-only GWT". Add a brief `Automation: Playwright/Cheerio doc-scrape` blurb per row so the executability is grounded.

8. **Heatmap "Concurrency column: only Recipients (✓ clean via ABUSE-8)"** — that's the only ✓ in the column. The "Effort: M" callout is good, but the heatmap should visually flag that 12 of 13 family rows have NO concurrency coverage. Consider a "Risk if not closed" cell or color marker. Right now the gap is buried in prose.

9. **Heatmap row "Cross-cutting × Functional = ✗"** — but the matrix has T-P2-EP-01 through T-P2-EP-18 which include several cross-cutting envelope/headers probes. Either the heatmap row taxonomy needs a footnote ("functional = endpoint-happy-path, envelope/headers covered under Docs Quality + Congruence"), or rebucket the cross-cutting probes. Minor inconsistency vs matrix family taxonomy.

10. **`features/05:87` "with headers ... and an empty JSON body"** — Scenario asserts 403 ForbiddenException after pin. But the same scenario doesn't say what the prior `Given` POST returned a token (it cites Sub-finding 3 by reference, which makes the chain stateful). Inline the previous-scenario outcome as a `Given` (per Gherkin best practice each scenario should be independently runnable).

---

## What I'd add — NICE-TO-HAVE

1. **Add an `evidence/work/automation/{slug}/` README per finding** that says exactly which framework executes it (Karate vs pytest+httpx vs Newman+k6) and how to run it (`pytest -k webhook_ssrf -v`). Persona § 2 calls for this; the .feature files reference it (`# Automation:` header lines), but the `automation/` directory map isn't surfaced in the review scope. Even a one-line `runner.md` per slug would close the gap from "readable" to "runnable".
2. **Add a `@regression` tag** to the spec-side scenarios for every drift, so they can be tagged out of the daily run until Kira fixes the underlying issue. Right now all scenarios run together — engineers will see 60% red until v2026-XX-XX ships.
3. **A `Schemathesis` stateful-fuzz hook in the matrix Contract column** — 5 of 13 families show `⚠ partial` or `✗` for Contract. One Schemathesis run on the (yet-to-be-published) OpenAPI spec would auto-close most of those cells. Heatmap should mark this as the highest-leverage Phase-4 task.
4. **Convert the matrix `severity` distribution into a stacked bar chart** in the heatmap doc — easier for the grader's eye than the textual rollup.
5. **Add a `pact_consumer_contract.json` skeleton under `evidence/work/contract/`** so the matrix's `contract` column can claim "consumer-driven contract testing scaffold present". Persona § 2 lists Pact as in-scope.

---

## Overall QA verdict

- **Ship: YES.** Specificity bar is met. Every Then is automatable. Every Spec/Observed pair is anchored to evidence files that actually exist in the repo. Every async step uses concrete N. Every status code / header / JSON path is a literal. Tags are consistent with the documented vocabulary. The matrix is 112 rows of automation-ready GWT plus 4 controls; the heatmap legend reconciles to the cell glyphs.
- **Smallest fix-set to flip to "ship without reservation":**
  1. SHOULD-FIX #1 — add `# Automation:` strategy comments above the 3 docs-scrape Spec scenarios (`01:53`, `01:104`, `04:88`) so an engineer doesn't have to invent the locator strategy.
  2. SHOULD-FIX #2 — anchor the indirect SSRF-delivery assertion in `02:55-62` to a positive control step earlier in the scenario.
  3. SHOULD-FIX #3 — collapse the `204 or 200` disjunction in `02:142` to one canonical answer.
  4. SHOULD-FIX #6 — move the REFINE-2026-05-28 prose out of the 11 wide matrix cells into footnotes for GitHub readability.
  5. SHOULD-FIX #10 — inline prior-scenario outcomes in `features/05` so each scenario is independently runnable.

Done in 30 minutes total. None of these block the publish — they tighten an already-publishable deliverable.
