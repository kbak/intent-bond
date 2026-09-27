"""Human reports must preserve evidence limits without additional execution."""

import copy
import unittest
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond import runner
from intentbond.common import CheckError, read_json
from intentbond.runner import verify
from intentbond.summary import render_summary


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "status": "passed",
            "diagnostics": [],
            "tests": {"status": "passed", "level": "command", "source_status": "matched"},
            "review": {"status": "not_needed"},
        }

    def item(self, description, revision=1):
        return {
            "id": f"req~session-expiration~{revision}",
            "path": "requirements.md",
            "line": 3,
            "content": {"description": description},
        }

    def test_long_description_shows_changed_behavior_and_escapes_markup(self):
        prefix = "Shared context. " * 100
        suffix = " More details." * 100
        before = self.item(prefix + "Expire after 30 minutes. <old>|" + suffix)
        after = self.item(prefix + "Expire after 5 minutes. <new>|" + suffix)
        changed = [{"kind": "requirement", "before": before, "after": after}]
        original = copy.deepcopy(changed)
        text = render_summary(self.evidence, changed, {"review.json", "review.patch"})
        self.assertIn("Expire after 30 minutes.", text)
        self.assertIn("Expire after 5 minutes.", text)
        self.assertIn("&lt;new&gt;&#124;", text)
        self.assertNotIn("<new>", text)
        self.assertNotIn(prefix, text)
        self.assertNotIn(suffix, text)
        self.assertIn("…", text)
        self.assertIn("may omit later differences", text)
        self.assertEqual(changed, original)

    def test_added_removed_and_revision_only_changes_retain_their_meaning(self):
        unchanged = "Sessions expire after 30 minutes."
        changed = [
            {"kind": "requirement", "before": None, "after": self.item("New promise.")},
            {"kind": "requirement", "before": self.item("Old promise."), "after": None},
            {
                "kind": "requirement",
                "before": self.item(unchanged),
                "after": self.item(unchanged, 2),
            },
        ]
        text = render_summary(self.evidence, changed, {"review.json", "review.patch"})
        self.assertIn("| Added | — |", text)
        self.assertIn("New promise.", text)
        self.assertIn("| Removed |", text)
        self.assertIn("Old promise.</code> | — |", text)
        self.assertEqual(text.count(unchanged), 2)
        self.assertIn("req~session-expiration~2", text)
        self.assertIn("metadata changes", text)

    def test_missing_and_structured_descriptions_do_not_prevent_a_report(self):
        before = self.item("")
        after = self.item([["detail", "Nested description"]])
        text = render_summary(
            self.evidence,
            [{"kind": "requirement", "before": before, "after": after}],
            {"review.json", "review.patch"},
        )
        self.assertIn("no description recorded", text)
        self.assertIn("See review.json for the structured description.", text)

    def test_command_success_does_not_invent_case_execution_or_approval(self):
        original = copy.deepcopy(self.evidence)
        text = render_summary(self.evidence, [], {"review.json", "review.patch", "tests.log"})
        self.assertIn("Individual linked-test execution is not established", text)
        self.assertIn("does not record approval", text)
        self.assertNotIn("Reported cases:", text)
        self.assertNotIn("[tests.xml]", text)
        self.assertEqual(self.evidence, original)

    def test_missing_comparison_is_not_reported_as_zero_changes(self):
        self.evidence.update(status="error", diagnostics=["OFT unavailable"])
        self.evidence["tests"].update(status="not_run", source_status="unchecked")
        self.evidence.pop("review")
        text = render_summary(self.evidence, None, set())
        self.assertIn("comparison did not complete", text)
        self.assertIn("matching stable source was not established", text)
        self.assertNotIn("Changed specification items: 0", text)
        self.assertNotIn("[review.json]", text)

    def test_skipped_missing_and_ambiguous_cases_remain_visible_on_passing_suite(self):
        self.evidence["tests"].update(
            level="suite",
            counts={"passed": 1, "failed": 0, "errors": 0, "skipped": 1},
            execution_links={
                "status": "recorded",
                "unlinked_cases": 1,
                "artifacts": [
                    {"id": f"utest~{status}~1", "status": status, "cases": []}
                    for status in ("passed", "skipped", "not_observed", "ambiguous")
                ],
            },
        )
        text = render_summary(self.evidence, [], {"tests.xml"})
        for status in ("skipped", "not_observed", "ambiguous"):
            self.assertIn(f"utest~{status}~1", text)
            self.assertLess(text.index(f"utest~{status}~1"), text.index("utest~passed~1"))
        self.assertIn("1 skipped", text)
        self.assertIn("reported cases without a resolved execution link: 1", text)
        self.evidence["tests"]["source_status"] = "changed"
        text = render_summary(self.evidence, [], {"tests.xml"})
        self.assertIn("Test results are diagnostic", text)


class SummaryWorkflowTests(WorkflowFixture):
    def test_report_retains_same_revision_change_and_runs_existing_checks_once(self):
        self.replace("requirements.md", "30 minutes", "60 minutes")
        with (
            patch.object(runner, "trace", wraps=runner.trace) as trace,
            patch.object(runner, "execute_tests", wraps=runner.execute_tests) as tests,
        ):
            result = self.run_check()
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(trace.call_count, 2)  # The existing baseline and candidate traces.
        tests.assert_called_once()
        text = (self.out / "summary.md").read_text()
        self.assertIn("Changed specification items: 1", text)
        self.assertIn("Changed specification/test files: 1", text)
        self.assertEqual(text.count("req~session-expiration~1"), 2)
        self.assertIn("| Modified |", text)
        self.assertIn("inactivity reaches 30 minutes", text)
        self.assertIn("inactivity reaches 60 minutes", text)
        self.assertIn(result["candidate"]["sha256"], text)
        self.assertIn("Candidate: worktree based on commit", text)
        self.assertIn(result["scope"]["sha256"], text)
        self.assertIn("summary.md", result["artifacts"])
        self.assertEqual(read_json(self.out / "evidence.json")["predicate"], result)
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )
        (self.out / "summary.md").write_text("Approved and fully verified.\n")
        with self.assertRaisesRegex(CheckError, "summary.md"):
            verify(
                self.repo,
                self.scope,
                self.base,
                "worktree",
                self.out / "evidence.json",
                allow_pending_review=True,
            )


if __name__ == "__main__":
    unittest.main()
