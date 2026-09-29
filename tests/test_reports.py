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

    def test_invalid_xml_is_rejected(self):
        with self.assertRaises(CheckError):
            self.parse("<testsuite>")

    def test_doctype_is_rejected_in_supported_xml_encodings(self):
        declarations = (
            "<!DOCTYPE testsuite>",
            '<!DOCTYPE testsuite [<!ENTITY x "foo">]>',
            '<!DOCTYPE testsuite SYSTEM "urn:intentbond:external-dtd">',
        )
        for encoding in ("utf-8", "utf-16", "utf-16le", "utf-16be"):
            for declaration in declarations:
                with self.subTest(encoding=encoding, declaration=declaration):
                    xml = (
                        f'<?xml version="1.0" encoding="{encoding}"?>'
                        f'{declaration}<testsuite><testcase name="one"/></testsuite>'
                    )
                    self.path.write_bytes(xml.encode(encoding))
                    # [utest->req~ib-junit-completion~1]
                    with self.assertRaisesRegex(CheckError, "DTDs/entities are unsupported"):
                        junit_counts(self.path)

    def test_supported_xml_encodings_and_predefined_entities_remain_valid(self):
        for encoding in ("utf-8", "utf-16", "utf-16le", "utf-16be"):
            with self.subTest(encoding=encoding):
                xml = (
                    f'<?xml version="1.0" encoding="{encoding}"?>'
                    '<testsuite tests="1"><testcase name="one &amp; two"/></testsuite>'
                )
                self.path.write_bytes(xml.encode(encoding))
                # [utest->req~ib-junit-completion~1]
                self.assertEqual(junit_counts(self.path)["passed"], 1)

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
