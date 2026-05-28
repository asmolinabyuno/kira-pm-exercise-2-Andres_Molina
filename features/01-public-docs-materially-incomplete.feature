# Finding #1 — Public docs are materially incomplete; the real Kira contract is partner-distributed (META)
# Severity: CRITICAL
# Pillar: Documentation Quality + Ease of Connection
# Evidence: evidence/analysis/13-docs-vs-partner-guide-delta.md § 3 · evidence/analysis/03-phase-1-findings.md (Findings #1, #2, #7, #8) · evidence/analysis/12-api-reference-coverage.md · evidence/analysis/11-docs-coverage-matrix.md
# Related: META-finding (T-P1-META-01), Phase-1 Finding-#1/#2/#7/#8, GAP-01, GAP-30, GAP-31, GAP-37, DRIFT-1, DRIFT-23, DRIFT-40
# Disclosure status: raised with @Diego — see README "Outreach to Kira"
# Note: This feature Gherkinizes a docs-quality META-finding. Scenarios assert observable runtime behavior an
# integrator hits when they follow the public docs literally, vs the partner-doc / no-prefix behavior the
# integrator never learns about from the public surface. The "spec" scenarios encode the hardened-API behavior
# (currently failing); the "Observed" scenarios encode today's runtime.
@docs-runtime-drift @docs-quality @meta-finding @sandbox-prod-drift
Feature: Public documentation portal is the canonical source of truth for sandbox integration
  As an integrator whose only Day-0 surface is the public docs portal at kira-financial-ai.readme.io
  I want every documented base URL, endpoint, header, workflow and example to match runtime
  So that I can reach my first 2xx without needing a partner-only Word doc or Slack ping

  Background:
    Given the documented Kira sandbox base URL "https://api.balampay.com/sandbox" (per kira-financial-ai.readme.io/v2026-04-14)
    And the runtime-working tenant-facing base URL "https://api.balampay.com" (no prefix, undocumented publicly)
    And valid credentials in .env: KIRA_CLIENT_ID, KIRA_COGNITO_SECRET, KIRA_API_KEY
    And the header "x-api-key" set to KIRA_API_KEY on every request

  # ----------------------------------------------------------------------
  # Sub-finding A — Documented base URL is broken on the first call any
  # public-docs integrator makes (POST /auth at /sandbox prefix).
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /sandbox/auth at the documented base URL returns a 200 with a JWT
    Given the public docs claim the sandbox base URL is "https://api.balampay.com/sandbox"
    When I POST to "https://api.balampay.com/sandbox/auth" with JSON body {"client_id": KIRA_CLIENT_ID, "password": KIRA_COGNITO_SECRET}
    And the header "Content-Type: application/json"
    Then the response status MUST be 200
    And the response JSON path "$.data.access_token" MUST be a non-empty string
    And the response JSON path "$.data.token_type" MUST equal "Bearer"
    And the response JSON path "$.data.expires_in" MUST equal 3600

  # Observed 2026-05-28 — see evidence/work/auth/01-fail-403.json
  Scenario: Observed — POST /sandbox/auth at the documented base URL returns 403 ForbiddenException
    When I POST to "https://api.balampay.com/sandbox/auth" with JSON body {"client_id": KIRA_CLIENT_ID, "password": KIRA_COGNITO_SECRET}
    And the header "Content-Type: application/json"
    Then the response status equals 403
    And the response header "x-amzn-errortype" equals "ForbiddenException"
    And the response JSON path "$.message" equals "Forbidden"
    And the public docs portal contains zero references to the working no-prefix base URL "https://api.balampay.com/auth"

  # ----------------------------------------------------------------------
  # Sub-finding B — The "pin to v2026-04-14" versioning endpoint, which
  # the partner Word doc cites as required, is undocumented publicly.
  # The public-docs-only integrator cannot pin.
  # ----------------------------------------------------------------------

  Scenario: Spec — The pin endpoint POST /v1/versioning/upgrade is documented on the public portal
    Given I open "https://kira-financial-ai.readme.io/v2026-04-14/reference"
    When I search the sidebar and the full-text index for "versioning"
    Then at least one reference page MUST exist at a URL matching "/reference/.*versioning.*"
    And that page MUST document the request body {"target_version": "2026-04-14"}
    And that page MUST state the canonical base URL on which the call works
    And the response shape MUST be documented as JSON path "$.previous_version" and "$.current_version"

  # Observed 2026-05-28 — see evidence/analysis/03-phase-1-findings.md Finding #2 and evidence/work/versioning/01-pin-no-prefix-success.json
  Scenario: Observed — Versioning sidebar entry 404s on public docs; pin endpoint only works at the no-prefix base
    When I HEAD-fetch the sidebar URL "https://kira-financial-ai.readme.io/v2026-04-14/reference/versioning"
    Then the response status equals 404
    When I POST to "https://api.balampay.com/sandbox/v1/versioning/upgrade" (the partner-doc-documented URL) with body {"target_version": "2026-04-14"} and a valid Bearer + x-api-key
    Then the response status equals 401
    And the response header "x-amzn-errortype" equals "UnauthorizedException"
    When I POST to "https://api.balampay.com/v1/versioning/upgrade" (no prefix, undocumented publicly) with the same body and headers
    Then the response status equals 200
    And the response JSON path "$.previous_version" equals "2026-04-14"
    And the response JSON path "$.current_version" equals "2026-04-14"

  # ----------------------------------------------------------------------
  # Sub-finding C — Sandbox manual approval workflow is undocumented
  # publicly. Public docs claim auto-approve; runtime rejects in ~90s.
  # The "ping your Kira contact in Slack" workaround is partner-only.
  # ----------------------------------------------------------------------

  Scenario: Spec — Following the public docs end-to-end gets a user to verification_status=VERIFIED within 60s
    Given a fresh business user was created via POST /v1/users at the no-prefix base
    And POST /v1/users/{id}/verifications was called per the docs flow
    When I poll GET /v1/users/{id} every 5 seconds for up to 60 seconds
    Then within 60 seconds the response JSON path "$.verification_status" MUST equal "VERIFIED"
    And no out-of-band action (Slack ping, email to Kira contact, manual approval ticket) MUST be required per the public docs

  # Observed 2026-05-28 — see evidence/analysis/04-integration-log.md § DRIFT-23 and evidence/analysis/13-docs-vs-partner-guide-delta.md Bucket B (sandbox-guide L36-42)
  Scenario: Observed — User auto-rejects in REVIEW state within 120s with no public-docs explanation
    Given a fresh business user created with the docs-canonical body
    When I POST /v1/users/{id}/verifications at the no-prefix base
    And I poll GET /v1/users/{id} every 5 seconds for up to 120 seconds
    Then within 120 seconds the response JSON path "$.verification_status" equals "REVIEW"
    And the public docs portal contains zero instances of the substrings "ping your Kira contact" or "shared Slack channel" or "verify+approved@kira.test"
    And the partner-only kira-sandbox-integration-guide.docx documents the workaround at line range L36-L42

  # ----------------------------------------------------------------------
  # Sub-finding D — Canonical worked examples (Postman collection) are
  # referenced 7x in the partner Word doc, distributed nowhere public.
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/12-api-reference-coverage.md and evidence/analysis/13-docs-vs-partner-guide-delta.md § 3 anchor "Postman collection canonical"
  Scenario: Observed — Postman collection is partner-only; public Reference pages hide JSON behind "Click Try It!"
    When I navigate to any of the 14 public API Reference endpoint pages under "https://kira-financial-ai.readme.io/v2026-04-14/reference"
    Then 14 of 14 Response sections render the literal string "Click Try It!" instead of a static 2xx JSON example
    And the page MUST NOT (per spec) require an interactive Try-It click to reveal the response shape
    When I search the public docs for the strings "postman" or "Postman collection"
    Then zero downloadable links to a Postman collection MUST be discoverable
    And the partner-only kira-sandbox-integration-guide.docx references the Postman collection 7 times at line ranges L11 and L139-L150

  # ----------------------------------------------------------------------
  # Sub-finding E — Quotations Reference vs Guides ship two disjoint
  # schemas; the Guides body is silently dropped at runtime.
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/04-integration-log.md § DRIFT-40 and evidence/work/quotations/01-e1-guides-validation-400.json
  Scenario: Observed — The Guides-documented POST /v1/quotations body returns 400 with Reference-only field names
    Given a valid Bearer token from POST /auth at the no-prefix base
    When I POST to "https://api.balampay.com/v1/quotations" with the Guides-shape body {"base_currency": "USD", "quote_currency": "MXN", "amount": "100", "amount_in_destination": false}
    And the headers "Authorization: Bearer <bearer-token-here>", "x-api-key: <REDACTED>", "Content-Type: application/json"
    Then the response status equals 400
    And the response JSON body mentions field names not present in the Guides body (e.g., "recipient_id" or "account_type")
    And the Guides field names "base_currency", "quote_currency", "amount_in_destination" MUST NOT appear in the validator's error list

  # ----------------------------------------------------------------------
  # Sub-finding F (rollup) — META coverage assertion.
  # 22 of 53 drifts are acknowledged in the partner doc; 0 of 53 in the
  # public docs. This is the META-finding's single observable metric.
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/13-docs-vs-partner-guide-delta.md Section 2 and § 3
  Scenario: Observed — Public docs acknowledge 0 of 53 captured drifts; partner doc acknowledges 22 of 53
    Given the 53 drift events catalogued in evidence/analysis/04-integration-log.md
    When I search every public docs page under "https://kira-financial-ai.readme.io/v2026-04-14/" for direct acknowledgements (workaround, known issue, or scheduled fix)
    Then the count of public-docs-acknowledged drifts equals 0
    When I search the partner-distributed kira-sandbox-integration-guide.docx for the same acknowledgements
    Then the count of partner-doc-acknowledged drifts equals 22
    And the docs-quality ratio "partner_acknowledged / total_drifts" MUST equal 22/53 (~41.5%)
    And the docs-quality ratio "public_acknowledged / total_drifts" MUST equal 0/53 (0%)
