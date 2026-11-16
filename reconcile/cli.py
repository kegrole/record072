"""Command-line entry point."""

from __future__ import annotations

import argparse

from .report import build_report, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile two CSV ledgers.")
    parser.add_argument("--local", required=True, help="local CSV path")
    parser.add_argument("--remote", required=True, help="remote CSV path")
    parser.add_argument("--out", required=True, help="output JSON path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_report(args.local, args.remote)
    write_report(report, args.out)

    summary = report["summary"]
    print(
        f"对平数={summary['matched']}，"
        f"差异数={summary['amount_mismatch']}，"
        f"缺失数={summary['missing']}，"
        f"重复数={summary['duplicate']}，"
        f"可疑数={summary['suspicious']}，"
        f"差异金额（分）={summary['total_diff_cents']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
