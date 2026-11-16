import csv
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reconcile.cli import main
from reconcile.money import parse_amount
from reconcile.report import build_report, render_report
from reconcile.timefmt import parse_timestamp


LOCAL_CSV = """key,amount,ts
K01,100.00,2026-01-02T00:00:00Z
K02,"1,200.50",2026-01-02T00:00:00Z
K03,300.00,2026-01-02T00:00:00Z
K04,400.00,2026-01-02T00:00:00Z
K05,500.00,2026-01-02T00:00:00Z
K06,600.00,2026-01-02T00:00:00Z
K07,700.00,2026-01-02T00:00:00Z
K08,(800.00),2026-01-02T00:00:00Z
K09,100.00-,2026-01-02T00:00:00Z
K10,900.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K13,1.005,2026-01-02T00:00:00Z
K14,250.00,2026-01-02T00:00:00Z
K15,350.00,2026-01-02T00:00:00Z
"""

REMOTE_CSV = """key,amount,ts
K01,100.00,2026-01-02T00:00:00Z
K02,1200.5,2026-01-02T00:00:00Z
K03,USD 300.01,2026-01-02T00:00:00Z
K04,USD 400.02,2026-01-02T00:00:00Z
K05,500.0,2026-01-02T00:00:00Z
K06,600.00,2026-01-02 08:00:00+08:00
K07,700.00,2026-01-03T01:00:00Z
K08,800.00,2026-01-02T00:00:00Z
K09,100.00,2026-01-02T00:00:00Z
K11,900.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K12,700.00,2026-01-02T00:00:00Z
K13,1.01,2026-01-02T00:00:00Z
K14,250.00,1767312000
K15,350.00,2026-01-03T00:00:00Z
"""


def write_csv(path, rows, fieldnames=("key", "amount", "ts")):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def data_rows(csv_text):
    return list(csv.DictReader(csv_text.splitlines()))


class ReconcileFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.local_path = self.base / "local.csv"
        self.remote_path = self.base / "remote.csv"
        self.local_path.write_text(LOCAL_CSV, encoding="utf-8")
        self.remote_path.write_text(REMOTE_CSV, encoding="utf-8")
        self.report = build_report(self.local_path, self.remote_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def details(self, section):
        return {item["key"]: item for item in self.report[section]}

    def test_01_fixture_files_are_exact_and_have_17_lines_each(self):
        self.assertEqual(
            (ROOT / "demo" / "local.csv").read_text(encoding="utf-8"),
            LOCAL_CSV,
        )
        self.assertEqual(
            (ROOT / "demo" / "remote.csv").read_text(encoding="utf-8"),
            REMOTE_CSV,
        )
        self.assertEqual(len(LOCAL_CSV.splitlines()), 17)
        self.assertEqual(len(REMOTE_CSV.splitlines()), 17)

    def test_02_section_counts(self):
        counts = {
            section: len(self.report[section])
            for section in (
                "matched",
                "amount_mismatch",
                "missing",
                "duplicate",
                "suspicious",
            )
        }
        self.assertEqual(
            counts,
            {
                "matched": 8,
                "amount_mismatch": 3,
                "missing": 2,
                "duplicate": 1,
                "suspicious": 1,
            },
        )

    def test_03_section_membership_and_key_order(self):
        self.assertEqual(
            [item["key"] for item in self.report["matched"]],
            ["K01", "K02", "K03", "K05", "K06", "K13", "K14", "K15"],
        )
        self.assertEqual(
            [item["key"] for item in self.report["amount_mismatch"]],
            ["K04", "K08", "K09"],
        )
        self.assertEqual(
            [item["key"] for item in self.report["missing"]],
            ["K10", "K11"],
        )
        self.assertEqual(
            [item["key"] for item in self.report["duplicate"]], ["K12"]
        )
        self.assertEqual(
            [item["key"] for item in self.report["suspicious"]], ["K07"]
        )

    def test_04_one_cent_tolerance_is_matched(self):
        self.assertEqual(
            self.details("matched")["K03"],
            {
                "key": "K03",
                "local_amount_cents": 30000,
                "remote_amount_cents": 30001,
                "diff_cents": 1,
            },
        )
        self.assertNotIn("K03", self.details("amount_mismatch"))

    def test_05_amount_mismatch_values_and_negative_accounting(self):
        mismatches = self.details("amount_mismatch")
        self.assertEqual(
            mismatches["K04"],
            {
                "key": "K04",
                "local_amount_cents": 40000,
                "remote_amount_cents": 40002,
                "diff_cents": 2,
            },
        )
        self.assertEqual(
            mismatches["K08"],
            {
                "key": "K08",
                "local_amount_cents": -80000,
                "remote_amount_cents": 80000,
                "diff_cents": 160000,
            },
        )
        self.assertEqual(
            mismatches["K09"],
            {
                "key": "K09",
                "local_amount_cents": -10000,
                "remote_amount_cents": 10000,
                "diff_cents": 20000,
            },
        )

    def test_06_half_cent_rounds_up_without_floating_point(self):
        self.assertEqual(parse_amount("1.005"), 101)
        k13 = self.details("matched")["K13"]
        self.assertEqual(k13["local_amount_cents"], 101)
        self.assertEqual(k13["remote_amount_cents"], 101)
        self.assertEqual(k13["diff_cents"], 0)

    def test_07_thousands_separator_and_short_decimal_are_equal(self):
        self.assertEqual(parse_amount("1,200.50"), 120050)
        self.assertEqual(parse_amount("1200.5"), 120050)
        k02 = self.details("matched")["K02"]
        self.assertEqual(k02["local_amount_cents"], 120050)
        self.assertEqual(k02["remote_amount_cents"], 120050)

    def test_08_timestamp_offsets_unix_seconds_and_24_hour_boundary(self):
        self.assertEqual(
            parse_timestamp("2026-01-02T00:00:00Z"),
            parse_timestamp("2026-01-02 08:00:00+08:00"),
        )
        self.assertEqual(parse_timestamp("1767312000"), 1767312000)
        self.assertEqual(
            parse_timestamp("2026-01-02T00:00:00Z"),
            parse_timestamp("1767312000"),
        )
        self.assertEqual(
            self.details("suspicious")["K07"]["time_diff_seconds"], 90000
        )
        self.assertIn("K15", self.details("matched"))
        self.assertNotIn("K15", self.details("suspicious"))
        self.assertEqual(
            parse_timestamp("2026-01-03T00:00:00Z")
            - parse_timestamp("2026-01-02T00:00:00Z"),
            86400,
        )

    def test_09_duplicate_counts(self):
        self.assertEqual(
            self.report["duplicate"],
            [
                {
                    "key": "K12",
                    "local_count": 3,
                    "remote_count": 3,
                }
            ],
        )

    def test_10_missing_direction_and_amount(self):
        self.assertEqual(
            self.report["missing"],
            [
                {
                    "key": "K10",
                    "side": "本地有对端缺",
                    "amount_cents": 90000,
                },
                {
                    "key": "K11",
                    "side": "本地缺对端有",
                    "amount_cents": 90000,
                },
            ],
        )

    def test_11_summary_totals_and_alignment(self):
        self.assertEqual(
            self.report["summary"],
            {
                "matched": 8,
                "amount_mismatch": 3,
                "missing": 2,
                "duplicate": 1,
                "suspicious": 1,
                "local_total_cents": 350151,
                "remote_total_cents": 530154,
                "raw_diff_cents": 180003,
                "aligned_remote_total_cents": 530153,
                "total_diff_cents": 180002,
                "sum_of_diffs_cents": 180002,
                "tolerance_cents": 1,
            },
        )

    def test_12_report_and_detail_field_shapes(self):
        self.assertEqual(
            list(self.report.keys()),
            [
                "matched",
                "amount_mismatch",
                "missing",
                "duplicate",
                "suspicious",
                "summary",
            ],
        )
        amount_fields = [
            "key",
            "local_amount_cents",
            "remote_amount_cents",
            "diff_cents",
        ]
        for section in ("matched", "amount_mismatch"):
            for item in self.report[section]:
                self.assertEqual(list(item.keys()), amount_fields)

        for item in self.report["missing"]:
            self.assertEqual(
                list(item.keys()), ["key", "side", "amount_cents"]
            )
        for item in self.report["duplicate"]:
            self.assertEqual(
                list(item.keys()),
                ["key", "local_count", "remote_count"],
            )
        for item in self.report["suspicious"]:
            self.assertEqual(
                list(item.keys()),
                [
                    "key",
                    "local_amount_cents",
                    "remote_amount_cents",
                    "time_diff_seconds",
                ],
            )
        self.assertEqual(
            list(self.report["summary"].keys()),
            [
                "matched",
                "amount_mismatch",
                "missing",
                "duplicate",
                "suspicious",
                "local_total_cents",
                "remote_total_cents",
                "raw_diff_cents",
                "aligned_remote_total_cents",
                "total_diff_cents",
                "sum_of_diffs_cents",
                "tolerance_cents",
            ],
        )

    def test_13_shuffled_rows_reordered_columns_and_integer_money(self):
        rng = random.Random(20260102)
        local_rows = data_rows(LOCAL_CSV)
        remote_rows = data_rows(REMOTE_CSV)
        rng.shuffle(local_rows)
        rng.shuffle(remote_rows)

        shuffled_local = self.base / "shuffled_local.csv"
        shuffled_remote = self.base / "shuffled_remote.csv"
        write_csv(shuffled_local, local_rows, ("ts", "key", "amount"))
        write_csv(shuffled_remote, remote_rows, ("amount", "ts", "key"))

        shuffled_report = build_report(shuffled_local, shuffled_remote)
        self.assertEqual(
            render_report(shuffled_report), render_report(self.report)
        )
        rendered = render_report(self.report)
        self.assertNotIn("300.01", rendered)
        self.assertNotIn("300.00", rendered)
        decoded = json.loads(rendered)
        for section in ("matched", "amount_mismatch", "suspicious"):
            for item in decoded[section]:
                for field in (
                    "local_amount_cents",
                    "remote_amount_cents",
                ):
                    self.assertIsInstance(item[field], int)

    def test_14_modified_input_reclassifies_tolerance_and_time_boundary(self):
        modified_remote = REMOTE_CSV.replace(
            "USD 300.01", "USD 300.02"
        ).replace(
            "K15,350.00,2026-01-03T00:00:00Z",
            "K15,350.00,2026-01-03T00:00:01Z",
        )
        modified_path = self.base / "modified_remote.csv"
        modified_path.write_text(modified_remote, encoding="utf-8")
        report = build_report(self.local_path, modified_path)

        self.assertEqual(
            {
                section: len(report[section])
                for section in (
                    "matched",
                    "amount_mismatch",
                    "missing",
                    "duplicate",
                    "suspicious",
                )
            },
            {
                "matched": 6,
                "amount_mismatch": 4,
                "missing": 2,
                "duplicate": 1,
                "suspicious": 2,
            },
        )
        modified_details = {
            item["key"]: item
            for item in report["amount_mismatch"]
        }
        self.assertEqual(modified_details["K03"]["diff_cents"], 2)
        suspicious = {item["key"]: item for item in report["suspicious"]}
        self.assertEqual(
            suspicious["K15"]["time_diff_seconds"], 86401
        )
        self.assertEqual(
            report["summary"],
            {
                "matched": 6,
                "amount_mismatch": 4,
                "missing": 2,
                "duplicate": 1,
                "suspicious": 2,
                "local_total_cents": 350151,
                "remote_total_cents": 530155,
                "raw_diff_cents": 180004,
                "aligned_remote_total_cents": 530155,
                "total_diff_cents": 180004,
                "sum_of_diffs_cents": 180004,
                "tolerance_cents": 1,
            },
        )


class ParserEdgeCaseTest(unittest.TestCase):
    def test_money_symbols_codes_padding_and_negative_forms(self):
        cases = {
            "  $1,200.50  ": 120050,
            "€50.2": 5020,
            "£10": 1000,
            "¥0.5": 50,
            "￥1.005": 101,
            "usd 300.00": 30000,
            "EUR 12.34": 1234,
            "gbp 1.004": 100,
            "CNY 1.006": 101,
            "Rmb 7.89": 789,
            "(800.00)": -80000,
            "100.00-": -10000,
            "  ( usd 12.50 ) ": -1250,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), expected)

    def test_invalid_money_rejected(self):
        for raw in ("", "abc", "1.2.3", "100--"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_amount(raw)

    def test_timestamps_naive_unix_milliseconds_and_negative_offset(self):
        base = parse_timestamp("2026-01-02T00:00:00Z")
        self.assertEqual(parse_timestamp("2026-01-02 00:00:00"), base)
        self.assertEqual(parse_timestamp("1767312000123"), base)
        self.assertEqual(
            parse_timestamp("2026-01-01T16:00:00-08:00"), base
        )
        self.assertEqual(
            parse_timestamp("2026-01-02 08:00:00+08:00"), base
        )

    def test_invalid_timestamp_rejected(self):
        for raw in ("", "12345", "not-a-time", "2026/01/02T00:00:00Z"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_timestamp(raw)


class RulePriorityTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, name):
        return self.base / name

    def test_duplicate_takes_priority_over_missing(self):
        write_csv(
            self.path("local.csv"),
            [
                {"key": "DUP", "amount": "1.00", "ts": "1000000000"},
                {"key": "DUP", "amount": "1.00", "ts": "1000000000"},
            ],
        )
        write_csv(self.path("remote.csv"), [])
        report = build_report(self.path("local.csv"), self.path("remote.csv"))
        self.assertEqual(
            report["duplicate"],
            [
                {
                    "key": "DUP",
                    "local_count": 2,
                    "remote_count": 0,
                }
            ],
        )
        self.assertEqual(report["missing"], [])

    def test_amount_mismatch_takes_priority_over_suspicious_time(self):
        write_csv(
            self.path("local.csv"),
            [{"key": "A", "amount": "1.00", "ts": "1000000000"}],
        )
        write_csv(
            self.path("remote.csv"),
            [{"key": "A", "amount": "3.00", "ts": "1000086401"}],
        )
        report = build_report(self.path("local.csv"), self.path("remote.csv"))
        self.assertEqual([item["key"] for item in report["amount_mismatch"]], ["A"])
        self.assertEqual(report["suspicious"], [])

    def test_key_is_stripped_and_case_sensitive(self):
        write_csv(
            self.path("local.csv"),
            [{"key": " A ", "amount": "1.00", "ts": "1000000000"}],
        )
        write_csv(
            self.path("remote.csv"),
            [{"key": "a", "amount": "1.00", "ts": "1000000000"}],
        )
        report = build_report(self.path("local.csv"), self.path("remote.csv"))
        self.assertEqual(len(report["missing"]), 2)
        self.assertEqual(
            [item["key"] for item in report["missing"]], ["A", "a"]
        )


class CommandLineTest(unittest.TestCase):
    def test_cli_writes_report_and_prints_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local = base / "local.csv"
            remote = base / "remote.csv"
            out = base / "nested" / "report.json"
            local.write_text(LOCAL_CSV, encoding="utf-8")
            remote.write_text(REMOTE_CSV, encoding="utf-8")

            import io
            from contextlib import redirect_stdout

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(
                    [
                        "--local",
                        str(local),
                        "--remote",
                        str(remote),
                        "--out",
                        str(out),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(out.exists())
            self.assertEqual(
                buffer.getvalue().strip(),
                "对平数=8，差异数=3，缺失数=2，重复数=1，可疑数=1，差异金额（分）=180002",
            )
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["tolerance_cents"], 1)


if __name__ == "__main__":
    unittest.main()
