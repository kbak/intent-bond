from test_workflow import WorkflowFixture

from intentbond.common import CheckError, read_json, write_json
from intentbond.config import validate_scope
from intentbond.oft import import_items
from intentbond.runner import verify


class TraceExclusionTests(WorkflowFixture):
    def prepare(self):
        fixture = self.repo / "tests/fixtures"
        fixture.mkdir()
        (fixture / "requirements.md").write_text("# Fixture\n`req~fixture~1`\nNeeds: impl\n")
        (fixture / "tag.tsx").write_text("// [impl->req~missing~1]\n")
        self.configure(lambda s: s.update(trace_exclude=["tests/fixtures"]))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def test_excluded_fixtures_remain_available_to_tests_and_bound_to_source_review(self):
        self.prepare()
        runner = self.repo / "run_tests.py"
        runner.write_text(
            "from pathlib import Path\nassert Path('tests/fixtures/tag.tsx').exists()\n"
            + runner.read_text()
        )
        result = self.run_check()
        # [utest->req~ib-trace-exclusions~1]
        self.assertEqual(result["status"], "review_required", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        self.assertFalse(any("fixtures" in item["path"] for item in items))
        self.assertEqual(result["tests"]["status"], "passed")
        evidence = self.out / "evidence.json"
        self.assertEqual(
            verify(
                self.repo, self.scope, self.base, "worktree", evidence, allow_pending_review=True
            )["status"],
            "matched",
        )
        (self.repo / "tests/fixtures/tag.tsx").write_text("changed fixture\n")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(
                self.repo, self.scope, self.base, "worktree", evidence, allow_pending_review=True
            )
        result = self.run_check()
        self.assertEqual(result["review"]["status"], "required", result)
        self.assertIn("tests/fixtures/tag.tsx", (self.out / "review.patch").read_text())

    def test_candidate_cannot_authorize_new_exclusions(self):
        self.prepare()
        scope = read_json(self.repo / "scope.json")
        scope["trace_exclude"] = ["session.py"]
        write_json(self.repo / "scope.json", scope)
        self.replace("session.py", "# [impl->req~session-expiration~1]", "# removed coverage")
        result = self.run_check()
        # [utest->req~ib-trace-exclusions~1]
        self.assertIn("session.py", (self.out / "scope.json").read_text())
        self.assertNotEqual(result["status"], "passed")

    def test_exclusions_use_literal_paths_inside_inputs(self):
        for paths in ([], ["../outside"], ["tests", "tests"], ["/tests"], ["unselected"]):
            scope = read_json(self.scope)
            scope["trace_exclude"] = paths
            # [utest->req~ib-trace-exclusions~1]
            with self.subTest(paths=paths), self.assertRaises(CheckError):
                validate_scope(scope)
