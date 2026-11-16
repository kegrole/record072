"""Reconciliation classification rules."""

from __future__ import annotations

from .match import Record

TOLERANCE_CENTS = 1
SUSPICIOUS_SECONDS = 24 * 60 * 60
LOCAL_ONLY_SIDE = "本地有对端缺"
REMOTE_ONLY_SIDE = "本地缺对端有"


def _amount_detail(
    key: str, local_record: Record, remote_record: Record
) -> dict[str, int | str]:
    return {
        "key": key,
        "local_amount_cents": local_record.amount_cents,
        "remote_amount_cents": remote_record.amount_cents,
        "diff_cents": remote_record.amount_cents - local_record.amount_cents,
    }


def classify(
    local_groups: dict[str, list[Record]],
    remote_groups: dict[str, list[Record]],
) -> dict[str, list[dict[str, object]]]:
    """Classify every key according to the documented priority."""
    sections: dict[str, list[dict[str, object]]] = {
        "matched": [],
        "amount_mismatch": [],
        "missing": [],
        "duplicate": [],
        "suspicious": [],
    }

    for key in sorted(set(local_groups) | set(remote_groups)):
        local_rows = local_groups.get(key, [])
        remote_rows = remote_groups.get(key, [])

        if len(local_rows) > 1 or len(remote_rows) > 1:
            sections["duplicate"].append(
                {
                    "key": key,
                    "local_count": len(local_rows),
                    "remote_count": len(remote_rows),
                }
            )
            continue

        if not local_rows:
            sections["missing"].append(
                {
                    "key": key,
                    "side": REMOTE_ONLY_SIDE,
                    "amount_cents": remote_rows[0].amount_cents,
                }
            )
            continue

        if not remote_rows:
            sections["missing"].append(
                {
                    "key": key,
                    "side": LOCAL_ONLY_SIDE,
                    "amount_cents": local_rows[0].amount_cents,
                }
            )
            continue

        local_record = local_rows[0]
        remote_record = remote_rows[0]
        diff_cents = remote_record.amount_cents - local_record.amount_cents

        if abs(diff_cents) > TOLERANCE_CENTS:
            sections["amount_mismatch"].append(
                _amount_detail(key, local_record, remote_record)
            )
            continue

        time_diff_seconds = abs(
            remote_record.timestamp_seconds - local_record.timestamp_seconds
        )
        if time_diff_seconds > SUSPICIOUS_SECONDS:
            sections["suspicious"].append(
                {
                    "key": key,
                    "local_amount_cents": local_record.amount_cents,
                    "remote_amount_cents": remote_record.amount_cents,
                    "time_diff_seconds": time_diff_seconds,
                }
            )
            continue

        sections["matched"].append(
            _amount_detail(key, local_record, remote_record)
        )

    return sections
