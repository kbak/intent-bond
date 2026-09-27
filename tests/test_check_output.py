import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond.check_output import render_check
from intentbond.cli import main
from intentbond.evidence import EXIT_CODES


class CheckOutputTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.out = Path(directory.name)
        self.result = {
            "status": "rejected",
            "diagnostics": ["Test execution did not pass"],
            "tests": {"status": "failed", "level": "suite", "source_status": "matched"},
            "artifacts": {},
        }

    def test_failure_excerpt_retains_names_and_points_to_unmodified_report(self):
        report = self.out / "tests.xml"
        report.write_text(
            '<testsuite tests="4">'
            + "".join(
                f'<testcase classname="Boundary" name="case{i}">'
                f'<failure message="expected expiry">{"details " * 200}</failure></testcase>'
                for i in range(4)
            )
            + "</testsuite>"
        )
        self.result["artifacts"] = {report.name: "retained digest"}
        before = report.read_bytes()
        text = render_check(self.result, self.out)
        self.assertIn("Boundary::case0: expected expiry", text)
        self.assertIn("1 more failing cases", text)
        self.assertNotIn("Boundary::case3", text)
        self.assertIn(f"tests.xml: {report}", text)
        self.assertIn("[excerpt]", text)
        self.assertLess(len(text), 3000)
        self.assertEqual(report.read_bytes(), before)

    def test_diagnostics_are_bounded_with_full_evidence_reference(self):
        self.result["diagnostics"] = [f"problem{i} " + "x" * 2000 for i in range(8)]
        text = render_check(self.result, self.out)
        self.assertIn(f"rejected: {self.out / 'evidence.json'}", text)
        self.assertIn("problem4", text)
        self.assertNotIn("problem5", text)
        self.assertIn("3 more diagnostics in evidence.json", text)
        self.assertLess(len(text), 4000)
        self.assertEqual(len(self.result["diagnostics"]), 8)

    def test_missing_or_invalid_report_falls_back_to_bounded_log(self):
        (self.out / "tests.log").write_text("setup noise\n" * 300 + "actual command failure\n")
        self.result["tests"]["error"] = "Invalid report"
        for report in (None, "<broken", "<!DOCTYPE bad><testsuite/>"):
            with self.subTest(report=report):
                if report is not None:
                    (self.out / "tests.xml").write_text(report)
                text = render_check(self.result, self.out)
                self.assertIn("actual command failure", text)
                self.assertIn("test error: Invalid report", text)
                self.assertIn("Test log excerpt", text)
                self.assertLess(len(text), 2500)

    def test_command_success_has_no_invented_counts_or_report(self):
        self.result.update(status="passed", diagnostics=[])
        self.result["tests"] = {"status": "passed", "level": "command", "source_status": "matched"}
        self.result["artifacts"] = {"tests.log": "digest"}
        text = render_check(self.result, self.out)
        self.assertIn("tests: passed (command); source=matched", text)
        self.assertNotIn("counts:", text)
        self.assertNotIn("tests.xml:", text)
        self.assertIn(f"tests.log: {self.out / 'tests.log'}", text)

    def test_early_error_handles_unrun_tests_and_absent_review(self):
        self.result.update(status="error", diagnostics=["OFT unavailable"])
        self.result["tests"].update(status="not_run", source_status="unchecked")
        text = render_check(self.result, self.out)
        self.assertIn("OFT unavailable", text)
        self.assertIn("review: not_recorded; changes=unknown", text)
        self.assertNotIn("review.json:", text)

    def test_cli_preserves_each_native_exit_and_does_not_rerun_checks(self):
        for status, expected in EXIT_CODES.items():
            with self.subTest(status=status):
                self.result["status"] = status
                output = io.StringIO()
                with (
                    patch("intentbond.cli.check", return_value=self.result) as check,
                    contextlib.redirect_stdout(output),
                ):
                    code = main(
                        [
                            "check",
                            "--repo",
                            str(self.out),
                            "--base",
                            "fixed-base",
                            "--out",
                            str(self.out / "bundle"),
                        ]
                    )
                self.assertEqual(code, expected)
                check.assert_called_once()
                self.assertEqual(
                    output.getvalue().splitlines()[0],
                    f"{status}: {self.out / 'bundle/evidence.json'}",
                )
