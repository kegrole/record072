"""Exact parsing of monetary amounts into integer cents."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

_CURRENCY_PATTERN = re.compile(
    r"(?:USD|EUR|GBP|CNY|RMB|[\\$€£¥￥])", re.IGNORECASE
)
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def parse_amount(raw: str) -> int:
    """Parse a monetary value and return its value in integer cents.

    Floating point arithmetic is intentionally never used.
    """
    if raw is None:
        raise ValueError("amount is required")

    text = raw.strip()
    if not text:
        raise ValueError("amount is required")

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    if text.endswith("-"):
        negative = True
        text = text[:-1].strip()

    text = _CURRENCY_PATTERN.sub("", text).strip().replace(",", "")
    if not _NUMBER_PATTERN.fullmatch(text):
        raise ValueError(f"invalid amount: {raw!r}")

    cents = int(
        (Decimal(text) * Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    return -cents if negative else cents
