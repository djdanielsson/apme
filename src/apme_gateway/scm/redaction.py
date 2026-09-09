"""Credential redaction helpers for SCM operations."""

from __future__ import annotations

import re

_CRED_REDACT_RE = re.compile(r"(https?://)[^@]+@")
_BASIC_REDACT_RE = re.compile(r"(?i)(Basic\s+)[A-Za-z0-9+/_=-]{8,}")


def redact_credentials(text: str) -> str:
    """Redact embedded credentials from URLs and auth headers in text.

    Replaces ``https://user:token@host`` with ``https://[REDACTED]@host``
    and masks ``Basic <base64>`` tokens (including ``AUTHORIZATION: Basic``
    ``http.extraHeader`` values surfaced via ``GIT_TRACE`` /
    ``GIT_CURL_VERBOSE`` stderr) with ``Basic [REDACTED]`` to prevent token
    exposure in logs or error messages.

    Args:
        text: Text potentially containing URLs with credentials.

    Returns:
        Text with credentials redacted.
    """
    redacted = _CRED_REDACT_RE.sub(r"\1[REDACTED]@", text)
    return _BASIC_REDACT_RE.sub(r"\1[REDACTED]", redacted)
