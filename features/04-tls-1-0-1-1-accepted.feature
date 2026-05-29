# Finding #4 — TLS 1.0 and TLS 1.1 accepted by api.balampay.com:443
# Severity: CRITICAL
# Pillar: Integration Hardening (transport security) + Regulatory (PCI-DSS Req 4.1 / FFIEC / state money-transmitter)
# Evidence: evidence/analysis/05-security-audit.md § Finding 4 · evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json
# Related: F4 (security), OWASP-API8:2023, T-P3-SEC-F4
# Disclosure status: included in this public deliverable; no prior private coordination with Kira
@security @tls @transport
Feature: api.balampay.com:443 must enforce TLS 1.2 minimum (TLS 1.0 and TLS 1.1 handshakes must fail)
  As a regulated buyer (BIA, N1co) running an InfoSec review on Kira's API
  I want the TLS endpoint to reject TLSv1 and TLSv1.1 handshakes
  So that PCI-DSS Req 4.1, FFIEC, and state money-transmitter procurement gates can open

  Background:
    Given the production-fronting host "api.balampay.com" on port 443
    And the spec baseline is "TLS 1.2 minimum, TLS 1.3 preferred" (AWS CloudFront security policy TLSv1.2_2021 or ALB ELBSecurityPolicy-TLS-1-2-2017-01 or newer)

  # ----------------------------------------------------------------------
  # Sub-finding A — TLS 1.0 and TLS 1.1 handshakes must fail
  # Anchor: Security Finding F4
  # ----------------------------------------------------------------------

  Scenario Outline: Spec — TLS handshake at the listed legacy protocol version MUST fail
    When I run "openssl s_client -connect api.balampay.com:443 -servername api.balampay.com <openssl_flag>" with no client cert
    Then the openssl exit code MUST be non-zero
    And the handshake MUST NOT complete
    And the stderr MUST contain an SSL alert (e.g., "ssl handshake failure", "no protocols available", or "tlsv1 alert protocol version")
    And no server certificate MUST be received

    Examples:
      | openssl_flag |
      | -tls1        |
      | -tls1_1      |

  # Observed 2026-05-28 — see evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json
  Scenario Outline: Observed — TLS 1.0 and TLS 1.1 handshakes complete successfully with legacy ciphers
    When I run "openssl s_client -connect api.balampay.com:443 -servername api.balampay.com <openssl_flag>" with no client cert
    Then the openssl exit code equals 0
    And the handshake completes
    And a valid server certificate for CN "balampay.com" is received
    And the negotiated cipher equals "<negotiated_cipher>"
    And the negotiated protocol equals "<negotiated_protocol>"

    Examples:
      | openssl_flag | negotiated_protocol | negotiated_cipher        |
      | -tls1        | TLSv1               | ECDHE-RSA-AES128-SHA     |
      | -tls1_1      | TLSv1.1             | ECDHE-RSA-AES128-SHA     |

  # ----------------------------------------------------------------------
  # Sub-finding B — Python ssl.SSLContext pinned probe corroborates openssl
  # Anchor: Security Finding F4, second-tool corroboration
  # ----------------------------------------------------------------------

  Scenario Outline: Observed — Python ssl.SSLContext pinned to legacy protocols also connects
    When I open a TLS socket to "api.balampay.com:443" with ssl.SSLContext pinned to "<python_proto>"
    Then the socket "connected" attribute equals true
    And ssock.version() equals "<negotiated_protocol>"
    And ssock.cipher()[0] equals "<negotiated_cipher>"

    Examples:
      | python_proto | negotiated_protocol | negotiated_cipher                  |
      | TLSv1        | TLSv1               | ECDHE-RSA-AES128-SHA               |
      | TLSv1.1      | TLSv1.1             | ECDHE-RSA-AES128-SHA               |

  # ----------------------------------------------------------------------
  # Sub-finding C — TLS 1.2 and TLS 1.3 connect cleanly (modern ciphers
  # available; the question is whether legacy is also tolerated, not
  # whether modern is supported). Captures the "delta" between expected
  # and observed: modern works AND legacy works.
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json openssl_probes[-tls1_2]
  Scenario: Observed — TLS 1.2 also connects cleanly with modern ECDHE-ECDSA-CHACHA20-POLY1305 cipher
    When I run "openssl s_client -connect api.balampay.com:443 -servername api.balampay.com -tls1_2" with no client cert
    Then the openssl exit code equals 0
    And the negotiated protocol equals "TLSv1.2"
    And the negotiated cipher equals "ECDHE-ECDSA-CHACHA20-POLY1305"
    # This proves modern TLS works — the finding is that legacy is ALSO accepted, not that modern is missing.

  # ----------------------------------------------------------------------
  # Sub-finding D — PCI-DSS Req 4.1 / FFIEC compliance assertion
  # Anchor: Security Finding F4 compliance framing
  # ----------------------------------------------------------------------

  # Observed 2026-05-28 — see evidence/analysis/05-security-audit.md § Finding 4
  Scenario: Observed — Neither public docs nor partner guide acknowledges or commits to a TLS minimum
    Given the public docs portal "https://kira-financial-ai.readme.io/v2026-04-14/"
    And the partner-distributed "kira-sandbox-integration-guide.docx"
    And the partner-distributed "kira-prod-certification-matrix.docx"
    When I search every page for the strings "TLS 1.2", "TLSv1.2", "PCI-DSS", or "minimum TLS"
    Then zero acknowledgements of a TLS minimum policy are found in any of the three surfaces
    # For a Banco Industrial or N1co InfoSec review, this is a procurement-gate finding independent of any
    # technical exploit. The buyer cannot ship until TLS 1.2 is enforced as the minimum.
