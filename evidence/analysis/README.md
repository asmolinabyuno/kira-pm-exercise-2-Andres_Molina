# Evidence — Analysis (high-value deliverables)

This folder contains the 12+1 analysis docs that are the primary output of the Kira API evaluation exercise. Supporting raw evidence (per-call JSONs, harness scripts, batch logs) lives in `../work/`.

## Reading order

### Start here — Master views (~30 min)
- [01 — Test Matrix](01-test-matrix.md) — 108 tests with Given/When/Then, severity, status, cross-refs. The single source of truth.
- [02 — Test Coverage Heat Map](02-test-coverage-heatmap.md) — family × category coverage at a glance.

### Phase reports
- [03 — Phase 1 Findings](03-phase-1-findings.md) — Docs Quality, top 11 ranked.
- [04 — Integration Log](04-integration-log.md) — Phase 2 empirical drift ledger (53 drifts across 18 endpoints).
- [05 — Security Audit](05-security-audit.md) — Phase 3 OWASP API Top 10.
- [06 — Abuse Scenarios](06-abuse-scenarios.md) — Phase 3 business-logic exploits.
- [07 — Load Summary](07-load-summary.md) — Phase 3 stress & latency.

### Architectural references
- [08 — Flow Design](08-flow-design.md) — endpoint catalog + state machines + canonical GAP-NN.
- [09 — Integration Plan](09-integration-plan.md) — Phase 2 master playbook.

### Phase 1 supporting analyses
- [10 — Product Catalog](10-product-catalog.md) — Guides as product brochure + API contrast.
- [11 — Docs Coverage Matrix](11-docs-coverage-matrix.md) — Guides sweep × 8 agents.
- [12 — API Reference Coverage](12-api-reference-coverage.md) — Reference layer findings.

### Project ledger
- [Decision Log](decision-log.md) — DEC-001..DEC-007 chronological.

## Where the evidence lives

- Per-call HTTP captures: `../work/{auth,users,recipients,...}/{NN}-{outcome}.json`
- Phase 2 batch logs (merged into 04-integration-log.md): `../work/integration-log-batch-{A,B,C,E,G}.md`
- Probe scripts: `../work/probes/batch_*.py`
- Phase 3 harnesses: `../work/{security,abuse}/{slug}/` + `../work/automation/load/{slug}/`
- Latency baselines: `../work/latency/{endpoint}.json`
- Matrix proposal debate inputs: `../work/matrix-proposals/`
- Engineer notes + inbox: `../work/observations.md`, `../work/comments.md`
- Orchestrator + helpers: `../work/run_flow.py`, `../work/_redact.py`

## Maintenance contract

- Adding a new analysis doc → place in `evidence/analysis/` with next NN- prefix; update this README
- Moving a doc → use `git mv`; grep for old path and update all refs
- The `cross_ref` column in [01-test-matrix.md](01-test-matrix.md) must keep its last link as the source-of-truth doc. Update if a doc moves.
