# Finding #5 — /sandbox base URL is wrong everywhere — and even the partner guide directs to a broken URL (DRIFT-1 + DRIFT-1b + DRIFT-1c compound)
# Severity: CRITICAL
# Pillar: Docs↔Runtime Congruence + Documentation Quality
# Evidence: evidence/analysis/04-integration-log.md § DRIFT-1, DRIFT-2 (with 2026-05-28 revalidation block) · evidence/work/auth/01-fail-403.json · evidence/work/auth/02-success.json · evidence/work/versioning/01-pin-no-prefix-success.json · evidence/work/versioning/02-pin-sandbox-prefix-fail-401.json · evidence/work/versioning/03-sandbox-auth-after-pin-fail-403.json · evidence/work/versioning/04-sandbox-users-after-pin-fail-401.json
# Related: DRIFT-1, DRIFT-1b, DRIFT-1c, DRIFT-2, T-P2-DRIFT-1, T-P2-DRIFT-54, T-P2-DRIFT-55, DELTA-Bucket-C
# Disclosure status: raised with @Diego — see README "Outreach to Kira"
@docs-runtime-drift @sandbox-prod-drift @auth @versioning @meta-finding
Feature: Sandbox base URL contract must be one canonical, documented URL that runtime honors
  As an integrator copy-pasting URLs from either the public docs OR the partner Sandbox Integration Guide
  I want every documented base URL to return a 2xx on call #1 with valid credentials
  So that I do not waste a day diagnosing gateway-level 403/401 errors before any business logic runs

  Background:
    Given the public docs portal (kira-financial-ai.readme.io/v2026-04-14) documents sandbox base URL as "https://api.balampay.com/sandbox"
    And the partner-distributed kira-sandbox-integration-guide.docx (received 2026-05-28) documents sandbox base URL as "https://api.balampay.com/sandbox"
    And the partner guide L15 documents a one-time pin call "POST /sandbox/v1/versioning/upgrade" body {"target_version":"2026-04-14"} that "unlocks the stage"
    And valid credentials in .env: KIRA_CLIENT_ID, KIRA_COGNITO_SECRET, KIRA_API_KEY
    And the header "Content-Type: application/json" on every request

  # ----------------------------------------------------------------------
  # Sub-finding 1 — DRIFT-1: documented /sandbox/auth returns 403
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /sandbox/auth at the documented base URL returns a 200 with a JWT
    When I POST to "https://api.balampay.com/sandbox/auth" with JSON body {"client_id": KIRA_CLIENT_ID, "password": KIRA_COGNITO_SECRET} and header "x-api-key: <REDACTED>"
    Then the response status MUST equal 200
    And the response JSON path "$.data.access_token" MUST be a non-empty string
    And the response JSON path "$.data.token_type" MUST equal "Bearer"
    And the response JSON path "$.data.expires_in" MUST equal 3600

  # Observed 2026-05-28 — see evidence/work/auth/01-fail-403.json
  Scenario: Observed — POST /sandbox/auth returns 403 ForbiddenException
    When I POST to "https://api.balampay.com/sandbox/auth" with JSON body {"client_id": KIRA_CLIENT_ID, "password": KIRA_COGNITO_SECRET} and header "x-api-key: <REDACTED>"
    Then the response status equals 403
    And the response header "x-amzn-errortype" equals "ForbiddenException"
    And the response JSON path "$.message" equals "Forbidden"

  # ----------------------------------------------------------------------
  # Sub-finding 2 — Documented /sandbox/v1/users returns 401 (DRIFT-2)
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/work/versioning/04-sandbox-users-after-pin-fail-401.json
  Scenario: Observed — GET /sandbox/v1/users returns 401 UnauthorizedException with valid Bearer + x-api-key
    Given a valid bearer token obtained via POST /auth at the no-prefix base
    When I GET "https://api.balampay.com/sandbox/v1/users?limit=1" with headers "Authorization: Bearer <bearer-token-here>", "x-api-key: <REDACTED>", "X-Api-Version: 2026-04-14"
    Then the response status equals 401
    And the response header "x-amzn-errortype" equals "UnauthorizedException"
    And the response JSON path "$.message" equals "Unauthorized"
    # Note the gateway error type INCONSISTENCY across the same /sandbox/* tree: /sandbox/auth returns
    # ForbiddenException (403); /sandbox/v1/users returns UnauthorizedException (401). Same gateway, two
    # error types — its own minor finding tracked under DRIFT-2.

  # ----------------------------------------------------------------------
  # Sub-finding 3 — DRIFT-1b: the versioning pin endpoint the partner
  # guide documents is at the BROKEN /sandbox prefix; the working version
  # is at the no-prefix base, which the partner guide never names.
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/work/versioning/02-pin-sandbox-prefix-fail-401.json
  Scenario: Observed — POST /sandbox/v1/versioning/upgrade (the partner-guide URL verbatim) returns 401
    Given a valid bearer token obtained via POST /auth at the no-prefix base
    When I POST to "https://api.balampay.com/sandbox/v1/versioning/upgrade" with JSON body {"target_version": "2026-04-14"} and headers "Authorization: Bearer <bearer-token-here>", "x-api-key: <REDACTED>"
    Then the response status equals 401
    And the response header "x-amzn-errortype" equals "UnauthorizedException"
    And the response JSON path "$.message" equals "Unauthorized"

  # Observed 2026-05-28 — see evidence/work/versioning/01-pin-no-prefix-success.json
  Scenario: Observed — POST /v1/versioning/upgrade at the no-prefix base (undocumented publicly) returns 200
    Given a valid bearer token obtained via POST /auth at the no-prefix base
    When I POST to "https://api.balampay.com/v1/versioning/upgrade" with JSON body {"target_version": "2026-04-14"} and headers "Authorization: Bearer <bearer-token-here>", "x-api-key: <REDACTED>"
    Then the response status equals 200
    And the response header "x-api-version" equals "2026-04-14"
    And the response JSON path "$.previous_version" equals "2026-04-14"
    And the response JSON path "$.current_version" equals "2026-04-14"
    # Net effect: the only working pin URL is at the base the partner guide NEVER mentions, and the only
    # documented pin URL (in either doc surface) returns 401. An integrator following the partner guide cannot
    # complete step 2 of the prod-certification checklist (item #2 "Pin to 2026-04-14").

  # ----------------------------------------------------------------------
  # Sub-finding 4 — DRIFT-1c: after a successful pin, /sandbox/* still
  # returns the same 403/401 envelopes (pin does not unlock the prefix).
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/work/versioning/03-sandbox-auth-after-pin-fail-403.json
  Scenario: Observed — After a successful no-prefix pin, POST /sandbox/auth still returns 403
    Given POST "https://api.balampay.com/v1/versioning/upgrade" returned 200 with the version-state body (per Sub-finding 3)
    When I retry POST to "https://api.balampay.com/sandbox/auth" with headers "x-api-key: <REDACTED>", "X-Api-Version: 2026-04-14" and an empty JSON body
    Then the response status equals 403
    And the response header "x-amzn-errortype" equals "ForbiddenException"
    And the response JSON path "$.message" equals "Forbidden"

  # Observed 2026-05-28 — see evidence/work/versioning/04-sandbox-users-after-pin-fail-401.json
  Scenario: Observed — After a successful no-prefix pin, GET /sandbox/v1/users still returns 401
    Given POST "https://api.balampay.com/v1/versioning/upgrade" returned 200 with the version-state body (per Sub-finding 3)
    And a valid bearer token obtained via POST /auth at the no-prefix base
    When I GET "https://api.balampay.com/sandbox/v1/users?limit=1" with headers "Authorization: Bearer <bearer-token-here>", "x-api-key: <REDACTED>", "X-Api-Version: 2026-04-14"
    Then the response status equals 401
    And the response header "x-amzn-errortype" equals "UnauthorizedException"
    And the response JSON path "$.message" equals "Unauthorized"
    # The partner guide claims the pin "unlocks the stage." Empirically it does not. Two parallel auth/base-URL
    # models coexist (public docs + partner guide); neither matches runtime.

  # ----------------------------------------------------------------------
  # Sub-finding 5 — The actual working base is no-prefix (working URL
  # contradicts BOTH the public docs AND the partner guide)
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/work/auth/02-success.json
  Scenario: Observed — POST /auth at the no-prefix base returns 200 with a JWT (the working URL is documented by neither surface)
    When I POST to "https://api.balampay.com/auth" with JSON body {"client_id": KIRA_CLIENT_ID, "password": KIRA_COGNITO_SECRET} and header "x-api-key: <REDACTED>"
    Then the response status equals 200
    And the response JSON path "$.message" equals "Auth token"
    And the response JSON path "$.data.access_token" is a non-empty string of length >= 800
    And the response JSON path "$.data.token_type" equals "Bearer"
    And the response JSON path "$.data.expires_in" equals 3600
    And the response header "x-api-version" equals "2026-04-14"
    # The working base contradicts both public docs (which require the /sandbox prefix) and the partner guide
    # (which requires the /sandbox prefix + a pin call). The only surface that uses the working URL is the
    # partner-distributed Postman collection, which is not publicly available.
