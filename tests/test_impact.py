"""An equivalent bounded policy change preserves unrelated promises and exact-revision checks."""

import shutil
from pathlib import Path
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond.common import CheckError, read_json
from intentbond.impact import impact


class ImpactTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.repo)
        shutil.copytree(
            Path(__file__).resolve().parents[1] / "examples/granular-retries", self.repo
        )
        self.git("init", "-q", "-b", "main")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        shutil.copyfile(self.repo / "scope.json", self.scope)

    def revised(self, behavior=True, stale=False):
        for path in ("requirements.md", "retry.py", "tests/test_retry.py"):
            if path != "tests/test_retry.py" or not stale:
                self.replace(path, "req~retry-cap~1", "req~retry-cap~2")
        self.replace("retry.py", "impl~retry-cap~1", "impl~retry-cap~2")
        self.replace("tests/test_retry.py", "utest~retry-cap~1", "utest~retry-cap~2")
        if behavior:
            self.replace("requirements.md", "and 8 seconds", "and 16 seconds")
            self.replace("retry.py", "min(delay, 8)", "min(delay, 16)")
            self.replace(
                "tests/test_retry.py",
                "self.assertEqual(cap(100), 8)",
                "self.assertEqual(cap(16), 16)\n        self.assertEqual(cap(100), 16)",
            )

    def report(self):
        return impact(self.out / "evidence.json", self.jar)

    def test_policy_change_affects_only_cap_promise_and_consumers(self):
        self.revised()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required")
        report = self.report()
        counts = report["counts"]
        self.assertEqual(counts["base_declarations"], 6)
        self.assertEqual(counts["candidate_declarations"], 6)
        self.assertEqual(counts["changed_declarations_excluding_location"], 3)
        self.assertEqual(counts["normative_text_changed"], 1)
        self.assertEqual(counts["base_edges"], 4)
        self.assertEqual(counts["candidate_edges"], 4)
        self.assertEqual(counts["continuing_edges_with_revised_endpoints"], 2)
        changed = [d for d in report["declarations"] if d["classification"] != "location_only"]
        self.assertEqual(
            {d["key"] for d in changed}, {"req~retry-cap", "impl~retry-cap", "utest~retry-cap"}
        )
        kinds = {c["path"]: c["classification"] for c in report["source_changes"]}
        self.assertEqual(kinds["retry.py"], "implementation_or_other_source_changed")
        self.assertEqual(kinds["tests/test_retry.py"], "assertion_or_test_source_changed")
        self.assertIsNone(report["human_review_minutes"])

    def test_revision_only_annotations_are_distinct_and_do_not_establish_adequacy(self):
        self.revised(behavior=False)
        self.run_check()
        report = self.report()
        self.assertEqual(report["counts"]["normative_text_changed"], 0)
        self.assertEqual(report["counts"]["link_or_revision_only_declarations"], 3)
        kinds = {c["path"]: c["classification"] for c in report["source_changes"]}
        self.assertEqual(kinds["retry.py"], "recognized_annotation_lines_only")
        self.assertEqual(kinds["tests/test_retry.py"], "recognized_annotation_lines_only")
        self.assertEqual(report["review"]["status"], "required")
        self.assertTrue(any("never establishes" in text for text in report["limitations"]))

    def test_stale_test_link_is_rejected_even_when_changed_assertions_pass(self):
        self.revised(stale=True)
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "rejected")
        report = self.report()
        self.assertEqual(report["trace"]["candidate"], "failed")
        self.assertGreater(report["counts"]["ambiguous_logical_edge_pairs"], 0)
        self.assertTrue(report["edges"]["ambiguous_pairs"])

    def test_cli_reproduces_report_without_repository_or_tests(self):
        self.revised()
        self.run_check()
        original = (self.out / "evidence.json").read_bytes()
        shutil.rmtree(self.repo)
        with patch(
            "intentbond.runner.execute_tests",
            side_effect=AssertionError("No test execution"),
        ):
            code, text, error = self.run_cli(
                "impact",
                "--evidence",
                str(self.out / "evidence.json"),
                "--format",
                "json",
                cwd=self.root,
            )
        self.assertEqual(code, 0, error)
        import json

        report = json.loads(text)
        self.assertEqual(report["counts"], self.report()["counts"])
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)
        code, text, error = self.run_cli(
            "impact", "--evidence", str(self.out / "evidence.json"), cwd=self.root
        )
        self.assertEqual(code, 0, error)
        self.assertIn("Human review effort: not measured", text)

    def test_changed_export_or_report_is_rejected(self):
        self.revised()
        self.run_check()
        path = self.out / "review.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(CheckError, "artifact missing or changed"):
            self.report()

    def test_test_body_edit_cannot_be_hidden_by_relinking(self):
        self.revised(behavior=False)
        self.replace(
            "tests/test_retry.py", "self.assertEqual(cap(100), 8)", "self.assertTrue(True)"
        )
        self.run_check()
        source = read_json(self.out / "review.json")["source_changes"]
        self.assertEqual(
            next(c["classification"] for c in source if c["path"] == "tests/test_retry.py"),
            "assertion_or_test_source_changed",
        )
