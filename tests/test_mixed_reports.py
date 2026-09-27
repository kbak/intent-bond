import sys
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.config import validate_scope
from intentbond.runner import verify


class MixedReportTests(WorkflowFixture):
    def configure_reports(self, second='<testsuite tests="1"><testcase name="ui"/></testsuite>'):
        script = (
            "import subprocess,sys; from pathlib import Path; "
            "result=subprocess.run([sys.executable,'run_tests.py']); "
            "Path('test-results.xml').rename('backend.xml'); "
            f"Path('frontend.xml').write_text({second!r}); "
            "sys.exit(result.returncode)"
        )
        self.configure(
            lambda s: s["tests"].update(
                reports=["backend.xml", "frontend.xml"], command=[sys.executable, "-c", script]
            )
        )
        self.configure(lambda s: s["tests"].pop("report"))

    def test_reports_are_retained_combined_and_verified(self):
        self.configure_reports()
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["tests"]["counts"]["total"], 2)
        self.assertEqual(len(result["tests"]["reports"]), 2)
        for name in ("tests-1.xml", "tests-2.xml", "tests.xml"):
            self.assertIn(name, result["artifacts"])
        verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        # A reconstructed bundle cannot silently discard one configured runner.
        evidence_path = self.out / "evidence.json"
        statement = read_json(evidence_path)
        statement["predicate"]["artifacts"].pop("tests-2.xml")
        write_json(evidence_path, statement)
        with self.assertRaisesRegex(CheckError, "inventory is incomplete"):
            verify(self.repo, self.scope, self.base, "worktree", evidence_path)
        statement["predicate"]["artifacts"]["tests-2.xml"] = digest(
            (self.out / "tests-2.xml").read_bytes()
        )
        # Even matching refreshed hashes must retain the merge relationship.
        (self.out / "tests-2.xml").write_text('<testsuite><testcase name="different"/></testsuite>')
        statement["predicate"]["artifacts"]["tests-2.xml"] = digest(
            (self.out / "tests-2.xml").read_bytes()
        )
        write_json(evidence_path, statement)
        with self.assertRaisesRegex(CheckError, "Combined JUnit report differs"):
            verify(self.repo, self.scope, self.base, "worktree", evidence_path)

    def test_failure_or_incomplete_second_report_cannot_hide_behind_first(self):
        for report in (
            '<testsuite tests="1"><testcase name="ui"><failure/></testcase></testsuite>',
            '<testsuite tests="2"><testcase name="ui"/></testsuite>',
        ):
            with self.subTest(report=report):
                # Reset configuration for each independent invocation.
                scope = read_json(self.repo / "scope.json")
                write_json(self.scope, scope)
                self.configure_reports(report)
                result = self.run_check()
                self.assertEqual(result["status"], "rejected", result)
                self.assertNotEqual(result["tests"]["status"], "passed")

    def test_missing_or_stale_report_is_rejected(self):
        self.configure_reports()
        self.configure(lambda s: s["tests"].update(command=[sys.executable, "run_tests.py"]))
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "error")
        (self.repo / "backend.xml").write_text('<testsuite><testcase name="stale"/></testsuite>')
        result = self.run_check()
        self.assertEqual(result["status"], "error")
        self.assertIn("already exists", " ".join(result["diagnostics"]))

    def test_report_configuration_is_unambiguous(self):
        for reports in ([], ["one.xml", "one.xml"], ["../outside.xml"], "one.xml"):
            scope = read_json(self.scope)
            scope["tests"].pop("report")
            scope["tests"]["reports"] = reports
            with self.subTest(reports=reports), self.assertRaises(CheckError):
                validate_scope(scope)
        scope = read_json(self.scope)
        scope["tests"]["reports"] = ["one.xml"]
        with self.assertRaises(CheckError):
            validate_scope(scope)

    def test_ignored_annotation_fails_before_running_tests_even_if_graph_is_covered(self):
        (self.repo / "component.unknown").write_text("// [impl->req~session-expiration~1]\n")
        self.configure(lambda s: s["inputs"].append("component.unknown"))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        with patch("intentbond.runner.execute_tests") as tests:
            result = self.run_check()
        tests.assert_not_called()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("component.unknown:1", " ".join(result["diagnostics"]))
