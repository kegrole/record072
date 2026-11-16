"""Parsing of Unix and ISO-8601 timestamps as UTC seconds."""

from __future__ import annotations

import calendar
import re
from datetime import datetime

_ISO_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[T ]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?P<zone>Z|[+-]\d{2}:\d{2})?$"
)


def parse_timestamp(raw: str) -> int:
    """Return a timestamp as integer seconds since the Unix epoch."""
    if raw is None:
        raise ValueError("timestamp is required")

    text = raw.strip()
    if not text:
        raise ValueError("timestamp is required")

    if text.isdigit():
        if len(text) == 10:
            return int(text)
        if len(text) == 13:
            return int(text) // 1000
        raise ValueError(f"invalid timestamp: {raw!r}")

    match = _ISO_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid timestamp: {raw!r}")

    dt = datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        int(match.group("hour")),
        int(match.group("minute")),
        int(match.group("second")),
    )
    seconds = calendar.timegm(dt.timetuple())

    zone = match.group("zone")
    if zone and zone != "Z":
        offset_seconds = int(zone[1:3]) * 3600 + int(zone[4:6]) * 60
        seconds -= offset_seconds if zone[0] == "+" else -offset_seconds

    return seconds
