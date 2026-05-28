# Finding #2 — Webhook subsystem is a triple-vector exploit (SSRF + cross-tenant client_uuid + optional secret + cleartext URL + opaque response)
# Severity: CRITICAL (CVSS 9.1 per evidence/analysis/05-security-audit.md § Finding 1)
# Pillar: Integration Hardening (security) + Webhook contract
# Evidence: evidence/analysis/05-security-audit.md § Finding 1 · evidence/analysis/06-abuse-scenarios.md Scenario 5 · evidence/work/security/ssrf-webhook-delivery-confirm/ · evidence/work/webhooks/12..19 · evidence/work/abuse/webhook-spoof-no-event-filter/
# Related: DRIFT-47, DRIFT-48, DRIFT-49, DRIFT-50, DRIFT-51, DRIFT-53, ABUSE-4, F1 (security), GAP-11, GAP-21, OWASP-API7:2023, OWASP-API3:2023
# Disclosure status: raised with @Diego on the security disclosure track — kept out of public outreach until acknowledged
@security @webhook @fraud-vector @sandbox-prod-drift
Feature: Webhook registration endpoint must validate URLs, tenant ownership, and require an HMAC secret
  As an integrator whose tenant is the security boundary
  I want POST /webhooks/register to reject SSRF URLs, cleartext schemes, foreign client_uuid values, and missing secrets
  So that one leaked credential cannot register a cross-tenant, unsigned, cleartext webhook that drains events to attacker infrastructure or pivots to AWS IMDS

  Background:
    Given the Kira working base URL "https://api.balampay.com" (no prefix — per DRIFT-1 the documented /sandbox prefix returns 403)
    And a valid bearer token obtained via POST /auth at the no-prefix base
    And the header "x-api-key" set to the sandbox API key
    And the header "Authorization" set to "Bearer <bearer-token-here>"
    And the integrator's own tenant client_uuid is "<own-client-uuid>"

  # ----------------------------------------------------------------------
  # Vector 1 — SSRF: webhook_url accepts loopback, IMDS, RFC1918, IPv6 loopback
  # Anchor: DRIFT-47, Security Finding F1
  # ----------------------------------------------------------------------

  Scenario Outline: Spec — POST /webhooks/register rejects SSRF-flavored URLs at registration with HTTP 400
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "<ssrf_url>", "secret": "<32-char-secret>", "client_uuid": "<own-client-uuid>"}
    Then the response status MUST equal 400
    And the response body MUST contain a validation error referencing webhook_url
    And the URL MUST NOT be persisted (no later delivery to this URL MUST be observed)

    Examples:
      | ssrf_url                                                       |
      | http://localhost                                               |
      | http://127.0.0.1                                               |
      | http://169.254.169.254/latest/meta-data/                       |
      | http://10.0.0.1                                                |
      | http://[::1]                                                   |

  # Observed 2026-05-28 — see evidence/work/webhooks/12-success-ssrf-localhost-80.json through 19-success-ssrf-dup-query.json
  Scenario Outline: Observed — POST /webhooks/register returns 200 for every SSRF URL and persists the registration
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "<ssrf_url>", "secret": "<32-char-secret>", "client_uuid": "<own-client-uuid>"}
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"
    And the response body MUST NOT contain a webhook id (no field "$.id" exists)

    Examples:
      | ssrf_url                                                       |
      | http://localhost                                               |
      | http://127.0.0.1                                               |
      | http://169.254.169.254/latest/meta-data/                       |
      | http://10.0.0.1                                                |
      | http://[::1]                                                   |

  # Observed 2026-05-28 — see evidence/work/security/ssrf-webhook-delivery-confirm/ and evidence/analysis/05-security-audit.md § Finding 1
  Scenario: Observed — Kira's outbound fetcher actually reaches the SSRF target on delivery (highest-evidence step)
    Given a webhook is registered with webhook_url "http://169.254.169.254/latest/meta-data/" and 200 was returned
    And a baseline webhook.site URL was registered prior, and one delivery was observed from source IP "54.201.149.241" with User-Agent "node" within ~37 seconds
    When I trigger any event-emitting operation (e.g., POST /v1/users with a minimal business body)
    And I poll the baseline webhook.site URL for new deliveries within 120 seconds
    Then zero new deliveries arrive at the baseline webhook.site URL within 120 seconds
    # The previously-active URL is silently superseded by the IMDS registration — strong evidence Kira routed the
    # outbound HTTP to the attacker-supplied URL (last-write-wins by client_uuid).

  # ----------------------------------------------------------------------
  # Vector 2 — Cross-tenant client_uuid: foreign UUIDs accepted, no auth-context check
  # Anchor: ABUSE-4, DRIFT-51
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /webhooks/register rejects a client_uuid that does not match the authenticated tenant
    Given a random UUIDv4 "<foreign-client-uuid>" that does not belong to my tenant
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "secret": "<32-char-secret>", "client_uuid": "<foreign-client-uuid>"}
    Then the response status MUST be 403
    And the response body MUST indicate that client_uuid does not match the auth context

  # Observed 2026-05-28 — see evidence/work/abuse/webhook-spoof-no-event-filter/02-P2-bogus-client_uuid-{00,01,02}.json (3/3 accepted with HTTP 200)
  Scenario Outline: Observed — POST /webhooks/register returns 200 for 3 of 3 random foreign client_uuid values
    Given a random UUIDv4 "<foreign-client-uuid>" not belonging to my tenant
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "secret": "<32-char-secret>", "client_uuid": "<foreign-client-uuid>"}
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"

    Examples:
      | foreign-client-uuid                  |
      | cbc5d344-9def-471b-a135-cfc208c48bb1 |
      | 11111111-2222-3333-4444-555555555555 |
      | 99999999-aaaa-bbbb-cccc-dddddddddddd |

  # ----------------------------------------------------------------------
  # Vector 3 — Secret is effectively optional (null and omission accepted)
  # Anchor: DRIFT-48
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /webhooks/register requires a non-null, non-omitted secret
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "secret": null, "client_uuid": "<own-client-uuid>"}
    Then the response status MUST equal 400
    And the response body MUST cite secret as a required field
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "client_uuid": "<own-client-uuid>"} (secret omitted)
    Then the response status MUST equal 400
    And the response body MUST cite secret as a required field

  # Observed 2026-05-28 — see evidence/work/webhooks/23-success-G6.4-secret-null.json and 24-success-G6.5-secret-omit.json
  Scenario: Observed — secret:null and secret omitted both return 200; only secret:"" is rejected
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "secret": null, "client_uuid": "<own-client-uuid>"}
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "client_uuid": "<own-client-uuid>"} (secret omitted)
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "https://webhook.site/<my-uuid>", "secret": "", "client_uuid": "<own-client-uuid>"}
    Then the response status equals 400
    And the response body contains "string_too_short"

  # ----------------------------------------------------------------------
  # Vector 4 — Cleartext http:// URL accepted as webhook_url scheme
  # Anchor: DRIFT-53
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /webhooks/register rejects cleartext http:// schemes
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "http://attacker.example/", "secret": "<32-char-secret>", "client_uuid": "<own-client-uuid>"}
    Then the response status MUST equal 400
    And the response body MUST cite an https-required validation error

  # Observed 2026-05-28 — see evidence/work/webhooks/25-success-G6.6-http-not-https.json
  Scenario: Observed — Cleartext http:// scheme is accepted with HTTP 200
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "http://webhook.site/<my-uuid>", "secret": "<32-char-secret>", "client_uuid": "<own-client-uuid>"}
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"

  # ----------------------------------------------------------------------
  # Vector 5 — Opaque registration response: no id, no list, no delete
  # Anchor: DRIFT-51, GAP-21
  # ----------------------------------------------------------------------

  Scenario: Spec — POST /webhooks/register returns a webhook id and companion GET/DELETE endpoints exist
    When I POST to "/webhooks/register" with a valid body
    Then the response status MUST equal 200
    And the response JSON path "$.id" MUST be a non-empty string (a webhook id)
    When I GET "/webhooks" with valid auth
    Then the response status MUST equal 200
    And the response JSON path "$.data" MUST be an array containing my registered webhook id
    When I DELETE "/webhooks/{id}" with valid auth and the returned id
    Then the response status MUST be 204 or 200

  # Observed 2026-05-28 — see evidence/work/webhooks/02-success-G0.2-path-webhooks-register-no-v1.json and 26-fail-403-G5.1-list.json
  Scenario: Observed — Registration response is literally {"message":"Webhook registered successfully"} with no id; GET/DELETE return 403
    When I POST to "/webhooks/register" with a valid body
    Then the response status equals 200
    And the response body equals the literal JSON {"message": "Webhook registered successfully"}
    And the response body MUST NOT contain a field at JSON path "$.id"
    When I GET "/webhooks" with valid Bearer + x-api-key
    Then the response status equals 403
    When I GET "/v1/webhooks" with valid Bearer + x-api-key
    Then the response status equals 403
    When I DELETE "/webhooks/<any-guessed-id>" with valid Bearer + x-api-key
    Then the response status equals 403
    # Net effect: once a hostile registration lands, the integrator cannot inventory or revoke it via the API —
    # cleanup requires emailing Kira support.

  # ----------------------------------------------------------------------
  # Combined chain — one credential, one POST, all five vectors stacked
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/06-abuse-scenarios.md Scenario 5 + evidence/analysis/05-security-audit.md § Finding 1
  Scenario: Observed — One POST stacks SSRF + foreign tenant + null secret + cleartext + opaque response
    Given a valid Bearer token + x-api-key on a single compromised integrator credential
    When I POST to "/webhooks/register" with JSON body {"webhook_url": "http://169.254.169.254/latest/meta-data/", "secret": null, "client_uuid": "11111111-2222-3333-4444-555555555555"}
    Then the response status equals 200
    And the response JSON path "$.message" equals "Webhook registered successfully"
    And the response body MUST NOT contain a field at JSON path "$.id"
    And neither GET /webhooks nor DELETE /webhooks/{id} can be used to revoke this registration (both return 403)
