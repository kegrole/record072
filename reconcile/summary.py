"""Summary totals for non-duplicate keys present on both sides."""

from __future__ import annotations

from .match import Record
from .rules import TOLERANCE_CENTS


def build_summary(
    local_groups: dict[str, list[Record]],
    remote_groups: dict[str, list[Record]],
    section_counts: dict[str, int],
    tolerance_cents: int = TOLERANCE_CENTS,
) -> dict[str, int]:
    eligible_keys = [
        key
        for key in sorted(set(local_groups) & set(remote_groups))
        if len(local_groups[key]) == 1 and len(remote_groups[key]) == 1
    ]

    local_total = sum(
        local_groups[key][0].amount_cents for key in eligible_keys
    )
    remote_total = sum(
        remote_groups[key][0].amount_cents for key in eligible_keys
    )

    aligned_remote_total = 0
    sum_of_diffs = 0
    for key in eligible_keys:
        local_amount = local_groups[key][0].amount_cents
        remote_amount = remote_groups[key][0].amount_cents
        diff = remote_amount - local_amount
        if abs(diff) <= tolerance_cents:
            aligned_remote_total += local_amount
        else:
            aligned_remote_total += remote_amount
            sum_of_diffs += diff

    return {
        "matched": section_counts["matched"],
        "amount_mismatch": section_counts["amount_mismatch"],
        "missing": section_counts["missing"],
        "duplicate": section_counts["duplicate"],
        "suspicious": section_counts["suspicious"],
        "local_total_cents": local_total,
        "remote_total_cents": remote_total,
        "raw_diff_cents": remote_total - local_total,
        "aligned_remote_total_cents": aligned_remote_total,
        "total_diff_cents": aligned_remote_total - local_total,
        "sum_of_diffs_cents": sum_of_diffs,
        "tolerance_cents": tolerance_cents,
    }
