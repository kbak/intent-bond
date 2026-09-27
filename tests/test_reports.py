import tempfile
import unittest
from pathlib import Path

from intentbond.common import CheckError, run
from intentbond.testing import junit_counts


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ib-report-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "report.xml"

    def parse(self, xml):
        self.path.write_text(xml)
        return junit_counts(self.path)

    def test_nested_suites_count_cases_once(self):
        result = self.parse(
            '<testsuites tests="2"><testsuite tests="1"><testcase name="one"/></testsuite><testsuite tests="1"><testcase name="two"/></testsuite></testsuites>'
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["passed"], 2)

    def test_report_with_omitted_case_is_invalid(self):
        with self.assertRaisesRegex(CheckError, "declared test count"):
            self.parse('<testsuite tests="3"><testcase name="one"/></testsuite>')

    def test_unsupported_wrappers_cannot_hide_failing_cases(self):
        for wrapper in ("testsuites", "unexpected"):
            with (
                self.subTest(wrapper=wrapper),
                self.assertRaisesRegex(CheckError, "not every testcase was parsed"),
            ):
                self.parse(
                    '<testsuites tests="2"><testsuite><testcase name="ok"/></testsuite>'
                    f'<{wrapper}><testsuite><testcase name="broken"><failure/></testcase>'
                    f"</testsuite></{wrapper}></testsuites>"
                )

    def test_suite_failure_without_failed_case_is_visible(self):
        result = self.parse('<testsuite errors="1"><testcase name="one"/></testsuite>')
        self.assertTrue(result["suite_failed"])
        result = self.parse(
            '<testsuite><testcase name="one"/><error>setup failed</error></testsuite>'
        )
        self.assertTrue(result["suite_failed"])

    def test_disabled_case_is_not_executed(self):
        result = self.parse('<testsuite><testcase name="one" status="notrun"/></testsuite>')
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_suite_skip_summary_cannot_make_unexecuted_cases_look_passed(self):
        with self.assertRaisesRegex(CheckError, "skip count"):
            self.parse(
                '<testsuite tests="1" skipped="1"><testcase name="not executed"/></testsuite>'
            )

    def test_invalid_xml_and_entity_are_rejected(self):
        for xml in ("<testsuite>", '<!DOCTYPE foo [<!ENTITY x "foo">]><testsuite/>'):
            with self.subTest(xml=xml), self.assertRaises(CheckError):
                self.parse(xml)

    def test_timeout_is_an_execution_error(self):
        import sys

        result = run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            self.root,
            self.root / "log",
            timeout=0.05,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["error"])


if __name__ == "__main__":
    unittest.main()
