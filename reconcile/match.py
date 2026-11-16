"""CSV loading and key grouping."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .money import parse_amount
from .timefmt import parse_timestamp


@dataclass(frozen=True)
class Record:
    key: str
    amount_cents: int
    timestamp_seconds: int


def load_csv(path: str | Path) -> list[Record]:
    """Load a CSV by column name, regardless of column order."""
    with Path(path).open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fieldnames = set(reader.fieldnames or [])
        missing = {"key", "amount", "ts"} - fieldnames
        if missing:
            raise ValueError(
                f"{path} is missing required columns: {sorted(missing)}"
            )

        records = []
        for row in reader:
            records.append(
                Record(
                    key=str(row["key"]).strip(),
                    amount_cents=parse_amount(str(row["amount"])),
                    timestamp_seconds=parse_timestamp(str(row["ts"])),
                )
            )
        return records


def group_records(records: list[Record]) -> dict[str, list[Record]]:
    """Group records by exact, case-sensitive stripped key."""
    grouped: dict[str, list[Record]] = {}
    for record in records:
        grouped.setdefault(record.key, []).append(record)
    return grouped
