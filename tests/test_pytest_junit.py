"""Exercise the pinned producer in subprocesses; never repair counts after parsing."""

import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from intentbond.common import CheckError
from intentbond.testing import counts_pass, junit_counts


@unittest.skipUnless(pytest.__version__ == "9.1.1", "adapter targets CI's pinned pytest 9.1.1")
class PytestJUnitTests(unittest.TestCase):
    def produce(self, source, *, adapter=True, extra=(), conftest=None, expect_report=True):
        directory = tempfile.TemporaryDirectory(prefix="ib-subtests-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "test_cases.py").write_text(source)
        if conftest:
            (root / "conftest.py").write_text(conftest)
        report = root / "report.xml"
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        if adapter:
            command += ["-p", "intentbond.pytest_junit"]
        command += ["--junitxml", str(report), *extra]
        result = subprocess.run(
            command,
            cwd=root,
            env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(report.is_file(), expect_report, result.stdout + result.stderr)
        return result, report

    def test_unittest_subtests_are_separate_cases_with_stable_names(self):
        source = """import unittest
class Cases(unittest.TestCase):
    def test_loop(self):
        for n in (1, 1):
            with self.subTest(n=n):
                self.assertEqual(n, 1)
"""
        native, broken = self.produce(source, adapter=False)
        self.assertEqual(native.returncode, 0)
        with self.assertRaisesRegex(CheckError, "declared test count"):
            junit_counts(broken)
        result, report = self.produce(source)
        self.assertEqual(result.returncode, 0, result.stdout)
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(
            junit_counts(report), {"total": 3, "passed": 3, "failed": 0, "errors": 0, "skipped": 0}
        )
        names = [case.get("name") for case in ET.parse(report).iter("testcase")]
        self.assertEqual(len(set(names)), 3)
        _, second = self.produce(source)
        self.assertEqual(names, [case.get("name") for case in ET.parse(second).iter("testcase")])

    def test_mixed_subtest_outcomes_and_setup_teardown_errors_survive(self):
        source = """import pytest
def test_mixed(subtests, record_property, record_testsuite_property):
    record_property('oft.covers', 'utest~mixed~1')
    record_testsuite_property('suite', 'retained')
    for outcome in ('pass', 'fail', 'skip', 'error'):
        with subtests.test(outcome=outcome):
            print('subtest output ' + outcome)
            if outcome == 'fail':
                assert False, 'subtest assertion failed'
            if outcome == 'skip':
                pytest.skip('subtest skipped')
            if outcome == 'error':
                raise RuntimeError('subtest exception')
@pytest.fixture
def setup_error():
    raise RuntimeError('setup failed')
def test_setup(setup_error):
    pass
@pytest.fixture
def teardown_error():
    yield
    raise RuntimeError('teardown failed')
def test_teardown(teardown_error):
    pass
def test_failure_and_teardown(teardown_error):
    assert False, 'call also failed'
"""
        result, report = self.produce(
            source, extra=("-o", "junit_family=xunit1", "-o", "junit_logging=system-out")
        )
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        counts = junit_counts(report)
        self.assertGreaterEqual(counts["failed"], 2)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(counts["errors"], 3)
        self.assertFalse(counts_pass(counts, {}))
        cases = list(ET.parse(report).iter("testcase"))
        subcases = [
            c for c in cases if c.find("properties/property[@name='pytest.subtest']") is not None
        ]
        self.assertEqual(len(subcases), 4)
        self.assertEqual(sum(c.find("failure") is not None for c in subcases), 2)
        self.assertEqual(sum(c.find("skipped") is not None for c in subcases), 1)
        for case in subcases:
            properties = {p.get("name"): p.get("value") for p in case.iter("property")}
            self.assertEqual(properties["oft.covers"], "utest~mixed~1")
            self.assertIn("outcome", properties["pytest.subtest"])
            self.assertIn("subtest output", case.findtext("system-out"))
        self.assertEqual(
            ET.parse(report).find("testsuite/properties/property[@name='suite']").get("value"),
            "retained",
        )

    def test_unsupported_producer_version_stops_before_writing_junit(self):
        result, _ = self.produce(
            "def test_pass(): pass\n",
            conftest="import pytest\npytest.__version__ = '9.1.2'\n",
            expect_report=False,
        )
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("requires pytest 9.1.1", result.stderr)

    def test_skips_still_obey_policy_and_deleted_cases_are_rejected(self):
        result, report = self.produce("""import pytest
def test_skip(subtests):
    with subtests.test():
        pytest.skip('not executed')
""")
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(result.returncode, 0, result.stdout)
        counts = junit_counts(report)
        self.assertEqual(counts["skipped"], 1)
        self.assertFalse(counts_pass(counts, {"policy": {"allow_skipped_tests": False}}))
        tree = ET.parse(report)
        suite = tree.find("testsuite")
        suite.remove(suite.find("testcase"))
        tree.write(report)
        with self.assertRaisesRegex(CheckError, "declared test count"):
            junit_counts(report)

    def test_collection_errors_remain_errors(self):
        result, report = self.produce("raise RuntimeError('collection failed')\n")
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(result.returncode, 2)
        self.assertEqual(junit_counts(report)["errors"], 1)

    def test_unittest_failures_skips_and_exceptions_are_retained(self):
        result, report = self.produce("""import unittest
class Cases(unittest.TestCase):
    def test_mixed(self):
        with self.subTest(outcome='pass'):
            self.assertTrue(True)
        with self.subTest(outcome='fail'):
            self.fail('assertion failed')
        with self.subTest(outcome='skip'):
            self.skipTest('not executed')
        with self.subTest(outcome='exception'):
            raise RuntimeError('unexpected exception')
""")
        # [utest->req~ib-pytest-subtests~1]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        counts = junit_counts(report)
        self.assertEqual(counts["skipped"], 1)
        self.assertGreaterEqual(counts["failed"], 2)
        self.assertFalse(counts_pass(counts, {}))
