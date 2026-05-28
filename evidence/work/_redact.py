"""Redact sensitive values from request/response payloads before writing evidence.

Public API:
    redact_headers(headers)  — mask header values for known-sensitive header names.
    redact_body(body)        — recursively mask known-sensitive JSON field values.
    redact_text(text)        — last-resort regex pass over raw text.

Mask format: ``REDACTED(<n>)`` where ``n`` is the original string length.

Test: ``python3 _redact.py`` runs an inline assertion suite.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Header names are compared case-insensitively.
SECRET_HEADER_NAMES = {
    "x-api-key",
    "authorization",
    "x-validation-header",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}

# JSON field names are compared case-insensitively, exact match on the key.
SECRET_FIELD_NAMES = {
    "password",
    "client_id",
    "api_key",
    "apikey",
    "x-api-key",
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "bearer",
    "authorization",
    "secret",
    "client_secret",
    "x-validation-header",
}

# Regexes for last-resort text redaction.
# JWT-shaped: three base64url segments separated by dots, starting with eyJ.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")
# Long opaque tokens: 40+ alphanumeric chars (covers many API keys / hex secrets).
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9]{40,}\b")
# Bearer <token> in raw text
_BEARER_RE = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9_\-\.]+)")


def _mask(value: Any) -> str:
    """Return the standard mask for *value*.

    For strings, encodes original length so engineers can sanity-check shape.
    For non-strings, falls back to a generic mask.
    """
    if isinstance(value, str):
        return f"REDACTED({len(value)})"
    return "REDACTED"


# -----------------------------------------------------------------------------
# Headers
# -----------------------------------------------------------------------------


def redact_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *headers* with sensitive values masked.

    Header names are compared case-insensitively. Original key casing is preserved.
    """
    if headers is None:
        return {}
    out: Dict[str, Any] = {}
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() in SECRET_HEADER_NAMES:
            out[k] = _mask(v)
        else:
            out[k] = v
    return out


# -----------------------------------------------------------------------------
# Body
# -----------------------------------------------------------------------------


def _redact_body_inplace(node: Any) -> Any:
    """Recursively walk *node*. Mutates dicts/lists in place; returns scalars."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            if isinstance(key, str) and key.lower() in SECRET_FIELD_NAMES:
                node[key] = _mask(node[key])
            else:
                node[key] = _redact_body_inplace(node[key])
        return node
    if isinstance(node, list):
        for i, item in enumerate(node):
            node[i] = _redact_body_inplace(item)
        return node
    if isinstance(node, str):
        # Catch bare JWTs / Bearer-prefixed strings even outside known field names.
        return redact_text(node)
    return node


def redact_body(body: Any) -> Any:
    """Return a deep copy of *body* with sensitive string field values masked.

    Preserves structure so engineers can read the shape.
    """
    if body is None:
        return None
    cloned = copy.deepcopy(body)
    return _redact_body_inplace(cloned)


# -----------------------------------------------------------------------------
# Raw text
# -----------------------------------------------------------------------------


def redact_text(text: str) -> str:
    """Last-resort regex redaction on raw text.

    Replaces JWT-shaped tokens, ``Bearer <token>`` substrings, and long opaque
    tokens with ``REDACTED(<n>)`` markers.
    """
    if not isinstance(text, str):
        return text

    def _jwt_sub(m: "re.Match[str]") -> str:
        return _mask(m.group(0))

    def _bearer_sub(m: "re.Match[str]") -> str:
        return f"{m.group(1)}{_mask(m.group(2))}"

    def _long_sub(m: "re.Match[str]") -> str:
        return _mask(m.group(0))

    out = _JWT_RE.sub(_jwt_sub, text)
    out = _BEARER_RE.sub(_bearer_sub, out)
    out = _LONG_TOKEN_RE.sub(_long_sub, out)
    return out


# -----------------------------------------------------------------------------
# Self-tests
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 1) Header redaction (case-insensitive match, original casing preserved).
    h_in = {
        "Content-Type": "application/json",
        "X-Api-Key": "abcd1234abcd1234",
        "authorization": "Bearer eyJabc.def.ghi",
        "Cookie": "session=longvalue",
    }
    h_out = redact_headers(h_in)
    assert h_out["Content-Type"] == "application/json", h_out
    assert h_out["X-Api-Key"].startswith("REDACTED("), h_out
    assert h_out["authorization"].startswith("REDACTED("), h_out
    assert h_out["Cookie"].startswith("REDACTED("), h_out
    # Original input must not be mutated.
    assert h_in["X-Api-Key"] == "abcd1234abcd1234", "redact_headers mutated input"

    # 2) JSON body redaction by field name (nested).
    b_in = {
        "client_id": "11111111-2222-3333-4444-555555555555",
        "password": "s3cret-value",
        "data": {
            "access_token": "eyJalg.eyJ.sig",
            "expires_in": 3600,
            "token_type": "Bearer",
            "nested": {"refresh_token": "rt-deadbeef"},
        },
        "list": [{"secret": "x"}, {"public": "ok"}],
    }
    b_out = redact_body(b_in)
    assert b_out["client_id"].startswith("REDACTED("), b_out
    assert b_out["password"].startswith("REDACTED("), b_out
    assert b_out["data"]["access_token"].startswith("REDACTED("), b_out
    assert b_out["data"]["expires_in"] == 3600, b_out
    assert b_out["data"]["token_type"] == "Bearer", b_out
    assert b_out["data"]["nested"]["refresh_token"].startswith("REDACTED("), b_out
    assert b_out["list"][0]["secret"].startswith("REDACTED("), b_out
    assert b_out["list"][1]["public"] == "ok", b_out
    # Deep-copy: original unchanged.
    assert b_in["password"] == "s3cret-value", "redact_body mutated input"

    # 3) JWT-shaped string redaction via regex pass.
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMifQ.signaturebits"
    txt = f"got token={jwt} ok"
    txt_out = redact_text(txt)
    assert jwt not in txt_out, txt_out
    assert "REDACTED(" in txt_out, txt_out

    # 4) Bearer prefix in raw text.
    bearer_in = "Authorization: Bearer abc123def456ghi789jkl012mno345pqr678stu901vwx"
    bearer_out = redact_text(bearer_in)
    assert "abc123def456" not in bearer_out, bearer_out
    assert "Bearer REDACTED(" in bearer_out, bearer_out

    # 5) Long opaque token in raw text (>= 40 alphanumeric).
    raw = "key=abcdefghijklmnopqrstuvwxyz0123456789ABCD trail"
    raw_out = redact_text(raw)
    assert "abcdefghijklmnopqrstuvwxyz0123456789ABCD" not in raw_out, raw_out

    print("_redact.py self-tests passed")
