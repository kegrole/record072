"""Build and serialize reconciliation reports."""

from __future__ import annotations

import json
from pathlib import Path

from .match import group_records, load_csv
from .rules import TOLERANCE_CENTS, classify
from .summary import build_summary

SECTION_ORDER = (
    "matched",
    "amount_mismatch",
    "missing",
    "duplicate",
    "suspicious",
)


def build_report(local_path: str | Path, remote_path: str | Path) -> dict:
    local_groups = group_records(load_csv(local_path))
    remote_groups = group_records(load_csv(remote_path))
    sections = classify(local_groups, remote_groups)

    for section in SECTION_ORDER:
        sections[section].sort(key=lambda item: str(item["key"]))

    counts = {section: len(sections[section]) for section in SECTION_ORDER}
    summary = build_summary(
        local_groups, remote_groups, counts, TOLERANCE_CENTS
    )

    report = {section: sections[section] for section in SECTION_ORDER}
    report["summary"] = summary
    return report


def render_report(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def write_report(report: dict, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(report), encoding="utf-8")
