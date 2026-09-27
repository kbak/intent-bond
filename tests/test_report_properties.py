"""Executable properties of the documented JUnit completion contract.

Domains: ordinary final outcomes, unique case identities, supported suite roots,
and correctly escaped XML. Retry dialects, conflicting outcomes, resource limits
and arbitrary XML are outside these searches; existing example tests remain.
"""

import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st

from intentbond.common import CheckError
from intentbond.testing import counts_pass, junit_counts, merge_reports

OUTCOMES = st.sampled_from(["passed", "failed", "errors", "skipped"])
REPORTS = st.lists(st.lists(OUTCOMES, min_size=1, max_size=12), min_size=1, max_size=4)
SEARCH = settings(max_examples=100, database=None, derandomize=True, deadline=None, print_blob=True)


def report(path, outcomes, *, wrapped=False):
    suite = ET.Element("testsuite", name="same-suite", tests=str(len(outcomes)))
    for index, outcome in enumerate(outcomes):
        case = ET.SubElement(suite, "testcase", classname="Sample", name=f"case-{index}")
        if outcome != "passed":
            ET.SubElement(
                case, {"failed": "failure", "errors": "error", "skipped": "skipped"}[outcome]
            )
    root = ET.Element("testsuites", tests=str(len(outcomes))) if wrapped else suite
    if wrapped:
        root.append(suite)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return root


class ReportPropertyTests(unittest.TestCase):
    @SEARCH
    @example(reports=[["passed", "skipped"]], wrapped=True, allow_skipped=None)
    @example(reports=[["passed"], ["failed"]], wrapped=False, allow_skipped=True)
    @given(
        reports=REPORTS, wrapped=st.booleans(), allow_skipped=st.sampled_from([None, False, True])
    )
    def test_merge_preserves_outcomes_and_completion_policy(self, reports, wrapped, allow_skipped):
        """Splitting outcomes across reports cannot erase failures or strict-policy skips."""
        expected = Counter(outcome for outcomes in reports for outcome in outcomes)
        with tempfile.TemporaryDirectory(prefix="ib-property-") as directory:
            root = Path(directory)
            paths = []
            for index, outcomes in enumerate(reports):
                path = root / f"report-{index}.xml"
                report(path, outcomes, wrapped=wrapped)
                paths.append((path.name, path))
            merged = root / "merged.xml"
            ET.ElementTree(merge_reports(paths)).write(merged, encoding="utf-8")
            counts = junit_counts(merged)
            self.assertEqual(counts["total"], sum(expected.values()))
            for outcome in ("passed", "failed", "errors", "skipped"):
                self.assertEqual(counts[outcome], expected[outcome])
            scope = (
                {} if allow_skipped is None else {"policy": {"allow_skipped_tests": allow_skipped}}
            )
            permits_skips = allow_skipped is not False
            expected_pass = bool(
                expected["passed"]
                and not expected["failed"]
                and not expected["errors"]
                and (permits_skips or not expected["skipped"])
            )
            self.assertEqual(counts_pass(counts, scope), expected_pass)

    @SEARCH
    @example(passed=1, declared=1, failure="errors", wrapped=True)
    @given(
        passed=st.integers(1, 30),
        declared=st.integers(1, 30),
        failure=st.sampled_from(["errors", "failures"]),
        wrapped=st.booleans(),
    )
    def test_suite_failure_survives_passing_cases_and_merge(
        self, passed, declared, failure, wrapped
    ):
        """A suite-level failure without a failed case still prevents completion."""
        with tempfile.TemporaryDirectory(prefix="ib-property-") as directory:
            root = Path(directory)
            broken, healthy, merged = (
                root / name for name in ("broken.xml", "healthy.xml", "merged.xml")
            )
            tree = report(broken, ["passed"] * passed, wrapped=wrapped)
            tree.set(failure, str(declared))
            ET.ElementTree(tree).write(broken, encoding="utf-8")
            report(healthy, ["passed"] * passed)
            ET.ElementTree(merge_reports([(broken.name, broken), (healthy.name, healthy)])).write(
                merged
            )
            counts = junit_counts(merged)
            self.assertEqual(counts["passed"], 2 * passed)
            self.assertFalse(counts_pass(counts, {"policy": {"allow_skipped_tests": True}}))

    @SEARCH
    @given(
        outcomes=st.lists(OUTCOMES, min_size=1, max_size=20),
        omitted=st.integers(1, 20),
        wrapped=st.booleans(),
    )
    def test_missing_reported_cases_are_rejected(self, outcomes, omitted, wrapped):
        """A larger declared count cannot supply evidence for absent cases."""
        with tempfile.TemporaryDirectory(prefix="ib-property-") as directory:
            path = Path(directory) / "report.xml"
            tree = report(path, outcomes, wrapped=wrapped)
            tree.set("tests", str(len(outcomes) + omitted))
            ET.ElementTree(tree).write(path, encoding="utf-8")
            with self.assertRaises(CheckError):
                junit_counts(path)
            with self.assertRaises(CheckError):
                merge_reports([(path.name, path)])
