"""Exercise the producer in a fresh interpreter, then use the real evidence parser."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from intentbond.common import xml_tree
from intentbond.testing import counts_pass, junit_counts


class UnittestProducerTests(unittest.TestCase):
    def produce(self, source, links=None, *, preexisting=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "test_example.py").write_text("import unittest\n" + source)
        (root / "links.json").write_text(json.dumps(links or {}))
        report = root / "results.xml"
        if preexisting:
            report.write_text("old evidence")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "intentbond.unittest_junit",
                "--start",
                str(root),
                "--links",
                str(root / "links.json"),
                "--report",
                str(report),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return result, report

    def test_subtests_preserve_failure_skip_and_explicit_identity(self):
        result, report = self.produce(
            """
class Cases(unittest.TestCase):
    def test_pass(self):
        for i in range(2):
            with self.subTest(i=i): self.assertEqual(i, i)
    def test_fail(self):
        for i in range(2):
            with self.subTest(i=i): self.assertEqual(i, 0)
    def test_skip(self):
        with self.subTest(i=1): self.skipTest("not exercised")
""",
            {"test_example.Cases.test_fail": ["utest~boundary~1"]},
        )
        # [utest->req~ib-unittest-evidence~1]
        self.assertEqual(result.returncode, 1, result.stderr)
        counts = junit_counts(report)
        self.assertEqual(
            [counts[k] for k in ("total", "passed", "failed", "skipped")], [3, 1, 1, 1]
        )
        self.assertFalse(counts_pass(counts, {"policy": {"allow_skipped_tests": False}}))
        case = xml_tree(report).find("testcase[@name='test_fail']")
        self.assertEqual(case.find("properties/property").get("value"), "utest~boundary~1")
        self.assertIn("i=1", case.findtext("failure"))

    def test_class_and_module_setup_cannot_report_unexecuted_methods_as_passed(self):
        for setup in (
            "def setUpModule(): raise RuntimeError('setup failed')\n",
            "def setUpModule(): raise unittest.SkipTest('setup skipped')\n",
            "",
        ):
            with self.subTest(setup=setup):
                body = """
class Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("class setup failed")
    def test_missing(self): pass
"""
                _, report = self.produce(
                    setup + body, {"test_example.Cases.test_missing": ["utest~missing~1"]}
                )
                # [utest->req~ib-unittest-evidence~1]
                self.assertEqual(junit_counts(report)["passed"], 0)
                case = xml_tree(report).find("testcase[@name='test_missing']")
                self.assertIsNotNone(case.find("skipped"))
                self.assertEqual(case.find("properties/property").get("value"), "utest~missing~1")

    def test_expected_failure_unexpected_success_and_teardown_error(self):
        result, report = self.produce("""
class Cases(unittest.TestCase):
    @classmethod
    def tearDownClass(cls): raise RuntimeError("teardown")
    @unittest.expectedFailure
    def test_expected(self): self.fail("known")
    @unittest.expectedFailure
    def test_unexpected(self): pass
""")
        # [utest->req~ib-unittest-evidence~1]
        self.assertEqual(result.returncode, 1)
        counts = junit_counts(report)
        self.assertEqual([counts[k] for k in ("failed", "errors", "skipped")], [1, 1, 1])

    def test_empty_discovery_unknown_mapping_and_stale_reports_fail(self):
        result, report = self.produce("")
        # [utest->req~ib-unittest-evidence~1]
        self.assertEqual(result.returncode, 1)
        self.assertFalse(counts_pass(junit_counts(report), {}))
        result, report = self.produce("", {"missing.Test.test_absent": ["utest~missing~1"]})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(report.exists())
        result, report = self.produce("", preexisting=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(report.read_text(), "old evidence")

    def test_interrupt_does_not_leave_a_passing_case(self):
        result, report = self.produce("""
class Cases(unittest.TestCase):
    def test_interrupted(self): raise KeyboardInterrupt()
    def test_unreached(self): pass
""")
        # [utest->req~ib-unittest-evidence~1]
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(junit_counts(report)["passed"], 0)
        self.assertEqual(junit_counts(report)["errors"], 1)
