# Finding #3 — PII unmasked across /v1/users LIST/DETAIL and /v1/recipients GET (SSN, document_number, CLABE, routing, IBAN, SWIFT, wallet plaintext)
# Severity: CRITICAL
# Pillar: Integration Hardening (security) + Regulatory (PCI / GLBA-adjacent)
# Evidence: evidence/analysis/05-security-audit.md § Findings 2-3 · DRIFT-30 (broadened in Phase 3) · evidence/work/security/info-disclosure-account-details/01-disclosure-sweep.json · evidence/work/recipients/06,27,29,31-*.json
# Related: DRIFT-30, F2 (security), F3 (security), OWASP-API3:2023
# Disclosure status: included in this public deliverable; no prior private coordination with Kira
@security @info-disclosure @docs-runtime-drift
Feature: PII fields (SSN, document_number, account_details) must be masked to last-4 on every read
  As an integrator handling regulated PII (SSN, ACH routing+account, SPEI CLABE, SWIFT IBAN, USDT wallet)
  I want every GET/LIST response to mask sensitive identifiers to last-4 by default
  So that one leaked credential cannot bulk-scrape the entire customer book in plaintext

  Background:
    Given the Kira working base URL "https://api.balampay.com" (no prefix)
    And a valid bearer token obtained via POST /auth at the no-prefix base
    And the header "x-api-key" set to the sandbox API key
    And the header "Authorization" set to "Bearer <bearer-token-here>"
    And the public docs (kira-financial-ai.readme.io) show account_details masked as the literal string "****7890"

  # ----------------------------------------------------------------------
  # Sub-finding A — /v1/users LIST leaks SSN + document_number plaintext
  # Anchor: Security Finding F2, DRIFT-30 broadened
  # ----------------------------------------------------------------------

  Scenario: Spec — GET /v1/users masks document_number and SSN to last-4 in the list view
    When I GET "/v1/users?limit=5" with valid Bearer + x-api-key
    Then the response status MUST equal 200
    And for every item in JSON path "$.data[*]" the field "document_number" MUST match the regex "^\\*{4,}\\d{4}$" OR be absent
    And for every item in JSON path "$.data[*].associated_persons[*]" the field "ssn" MUST match the regex "^\\*{4,}\\d{4}$" OR be absent
    And no field across the response body MUST contain a 9-digit US SSN in plaintext (regex "\\d{3}-?\\d{2}-?\\d{4}")

  # Observed 2026-05-28 — see evidence/work/security/info-disclosure-account-details/01-disclosure-sweep.json analysis[label=users-list].sensitive_fields_found
  Scenario: Observed — GET /v1/users returns full SSN + document_number plaintext in the list response
    When I GET "/v1/users?limit=5" with valid Bearer + x-api-key
    Then the response status equals 200
    And at least 3 items at JSON path "$.data[*].associated_persons[*].ssn" return full 9-digit SSN values (regex "^\\d{9}$" or "^\\d{3}-\\d{2}-\\d{4}$")
    And at least 1 item at JSON path "$.data[*].document_number" returns the full document_number (more than 4 digits, no leading asterisks)
    And the response body MUST NOT contain a single occurrence of the masked-pattern literal "****" preceding any document_number or SSN field value

  # ----------------------------------------------------------------------
  # Sub-finding B — GET /v1/users/{id} (detail) leaks the same PII
  # Anchor: Security Finding F2, DRIFT-30 broadened
  # ----------------------------------------------------------------------

  Scenario: Spec — GET /v1/users/{id} masks document_number to last-4 in detail view
    Given a known user id "<user-id>" owned by my tenant
    When I GET "/v1/users/<user-id>" with valid Bearer + x-api-key
    Then the response status MUST equal 200
    And the response JSON path "$.document_number" MUST match the regex "^\\*{4,}\\d{4}$"
    And for every item in JSON path "$.associated_persons[*].ssn" the value MUST match the regex "^\\*{4,}\\d{4}$"

  # Observed 2026-05-28 — see evidence/work/security/info-disclosure-account-details/01-disclosure-sweep.json analysis[label=user-detail].sensitive_fields_found = 7
  Scenario: Observed — GET /v1/users/{id} returns 7 unmasked sensitive fields per detail call
    Given a known user id "<user-id>" owned by my tenant
    When I GET "/v1/users/<user-id>" with valid Bearer + x-api-key
    Then the response status equals 200
    And the response JSON path "$.document_number" returns the full plaintext value (regex "^\\d{6,}$", not the masked pattern)
    And at least 7 sensitive fields across the response body are returned in plaintext (per the probe's sensitive_fields_found count)

  # ----------------------------------------------------------------------
  # Sub-finding C — GET /v1/recipients/{id} leaks account_details plaintext
  # across all 4 variants: SPEI / ACH / SWIFT / USDT
  # Anchor: Security Finding F3, DRIFT-30 broadened
  # ----------------------------------------------------------------------

  Scenario Outline: Spec — GET /v1/recipients/{id} masks account_details to last-4 across all 4 recipient variants
    Given a known recipient id "<recipient-id>" of type "<variant>" owned by my tenant
    When I GET "/v1/recipients/<recipient-id>" with valid Bearer + x-api-key
    Then the response status MUST equal 200
    And the response JSON path "$.type" MUST equal "<variant>"
    And the response JSON path "<masked_field_path>" MUST match the regex "^\\*{4,}.{0,4}$"
    And no field in the response body MUST contain the full plaintext "<plaintext_pattern_regex>"

    Examples:
      | variant      | masked_field_path                 | plaintext_pattern_regex |
      | SPEI_MX      | $.account_details.clabe           | ^\d{18}$                 |
      | ACH_USD      | $.account_details.account_number  | ^\d{6,17}$               |
      | SWIFT_EUR    | $.account_details.account_number  | ^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$ |
      | USDT_TRON    | $.account_details.address         | ^T[1-9A-HJ-NP-Za-km-z]{33}$ |

  # Observed 2026-05-28 — see evidence/work/recipients/06-success-200-detail-spei.json, 27-success-200-detail-ach-iter2.json, 29-success-200-detail-usdt-iter2.json, 31-success-200-detail-swift-iter2.json
  Scenario Outline: Observed — GET /v1/recipients/{id} returns full plaintext account_details on every variant
    Given a known recipient id "<recipient-id>" of type "<variant>" owned by my tenant
    When I GET "/v1/recipients/<recipient-id>" with valid Bearer + x-api-key
    Then the response status equals 200
    And the response JSON path "$.type" equals "<variant>"
    And the response JSON path "<plaintext_field_path>" matches the regex "<plaintext_value_regex>"
    And the response JSON path "<plaintext_field_path>" MUST NOT match the masked-pattern regex "^\\*+\\d{4}$"
    And the response JSON path "$.account_details.doc_number" returns the full plaintext document number (regex "^[A-Za-z0-9]{5,}$")

    Examples:
      | variant      | plaintext_field_path                | plaintext_value_regex                                    |
      | SPEI_MX      | $.account_details.clabe             | ^\d{18}$                                                  |
      | ACH_USD      | $.account_details.routing_number    | ^\d{9}$                                                   |
      | ACH_USD      | $.account_details.account_number    | ^\d{6,17}$                                                |
      | SWIFT_EUR    | $.account_details.swift_code        | ^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$                      |
      | SWIFT_EUR    | $.account_details.account_number    | ^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$                            |
      | USDT_TRON    | $.account_details.address           | ^T[1-9A-HJ-NP-Za-km-z]{33}$                              |

  # ----------------------------------------------------------------------
  # Sub-finding D — Docs vs runtime: public docs show "****7890" example,
  # runtime returns full digits. Direct contradiction.
  # Anchor: DRIFT-30 original framing
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/04-integration-log.md § DRIFT-30 and kira-financial-ai.readme.io/v2026-04-14/reference (account_details example)
  Scenario: Observed — Public docs show "****7890" masked example; runtime returns full plaintext (direct contradiction)
    Given the public docs Recipients Reference page shows the literal example string "****7890" in the account_details field
    When I GET "/v1/recipients/<any-recipient-id>" with valid Bearer + x-api-key for any of the 4 variants
    Then the response status equals 200
    And the response body MUST NOT contain the literal substring "****" anywhere in any account_details field value
    And the response body returns the full plaintext digits/address per the runtime variants above
    # Neither public docs nor the partner guide (kira-sandbox-integration-guide.docx) mentions that masking is
    # not applied — see evidence/analysis/13-docs-vs-partner-guide-delta.md Bucket D.
