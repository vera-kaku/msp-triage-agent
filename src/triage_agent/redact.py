"""Remove personal details before ticket text is sent to a model."""

from __future__ import annotations

import re

_RULES = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # Phone numbers such as 021 555 0142, +64 21 987 6543 or (03) 555 1234.
    # The lookarounds stop it matching inside IP addresses, ranges and CVE numbers
    # (CVE-2023-4966 used to become CVE-[PHONE]).
    ("[PHONE]", re.compile(
        r"(?<![\w/])(?<!\d\.)(?<![Cc][Vv][Ee]-)"
        r"(?:\+\d{1,3}[\s-]?)?\(?0?\d{1,3}\)?[\s-]?\d{3}[\s-]?\d{3,4}"
        r"(?![\w/])(?!\.\d)"
    )),
    # Only "password: x" or "password = x", so that "my password is expired" is left alone.
    ("[SECRET]", re.compile(r"(?i)\b(?:password|passcode|pin)\s*[:=]\s*\S+")),
]


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Return the redacted text and how many items of each kind were replaced."""
    counts: dict[str, int] = {}
    for label, pattern in _RULES:
        text, n = pattern.subn(label, text)
        if n:
            counts[label] = n
    return text, counts
