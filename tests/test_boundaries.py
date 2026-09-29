"""Source identity and selected review remain separate, reproducible results."""

from test_workflow import WorkflowFixture

from intentbond.check_output import render_check
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.config import validate_scope
from intentbond.evidence import statement
from intentbond.explain import explain, render_explanation
from intentbond.runner import verify


class BoundaryTests(WorkflowFixture):
    def test_review_only_fixtures_trigger_bound_review_without_importing_examples(self):
        path = self.repo / "fixtures/example.md"
        path.parent.mkdir()
        path.write_text("# Example\n\n`req~illustrative~1`\n\nNeeds: impl\n")
        self.configure(lambda scope: scope.update(review_paths=["fixtures"]))
        result = self.run_check()
        # [utest->req~ib-change-review~1]
        # [utest->req~ib-review-selection~1]
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["review"]["change_count"], 1)
        self.assertNotIn("illustrative", (self.out / "candidate-items.xml").read_text())
        self.assertEqual(
            result["source_boundaries"]["paths"],
            [
                {
                    "path": "fixtures/example.md",
                    "change": "added",
                    "tracing_input": False,
                    "semantic_review_selection": "review",
                }
            ],
        )
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )
        self.configure(lambda scope: scope.pop("review_paths"))
        with self.assertRaises(CheckError):
            verify(
                self.repo,
                self.scope,
                self.base,
                "worktree",
                self.out / "evidence.json",
                allow_pending_review=True,
            )

    def test_review_paths_use_existing_literal_path_validation(self):
        original = read_json(self.scope)
        for paths in (
            [],
            "fixtures",
            ["../fixtures"],
            [".git"],
            ["/tmp"],
            ["fixtures", "fixtures"],
        ):
            # [utest->req~ib-review-selection~1]
            with self.subTest(paths=paths), self.assertRaises(CheckError):
                validate_scope({**original, "review_paths": paths})
        self.assertEqual(
            validate_scope({**original, "review_paths": ["fixtures"]})["review_paths"], ["fixtures"]
        )

    def test_outside_docs_are_counted_hashed_and_reject_stale_evidence(self):
        (self.repo / "notes").mkdir()
        path = self.repo / "notes/assessment.md"
        path.write_text("An assessment requiring ordinary review.\n")
        result = self.run_check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["review"]["change_count"], 0)
        boundaries = result["source_boundaries"]
        # [utest->req~ib-boundary-report~1]
        self.assertEqual(
            boundaries["counts"],
            {
                "all_changed_captured_source_paths": 1,
                "changed_tracing_input_paths": 0,
                "changed_selected_semantic_review_paths": 0,
                "changed_paths_outside_selected_semantic_review": 1,
            },
        )
        self.assertEqual(boundaries["paths"][0]["path"], "notes/assessment.md")
        self.assertNotEqual(result["base"]["sha256"], result["candidate"]["sha256"])
        self.assertEqual(read_json(self.out / "review.json")["source_boundaries"], boundaries)
        rendered = render_check(result, self.out)
        self.assertIn("Changed captured source paths: 1", rendered)
        self.assertIn("neither approval nor rejection", rendered)
        explained = explain("req~session-expiration~1", self.out / "evidence.json", self.jar)
        self.assertEqual(explained["source_boundaries"], boundaries)
        self.assertIn("outside selected semantic review: 1", render_explanation(explained))
        self.assertIn("still source-hashed", (self.out / "summary.md").read_text())
        path.write_text("Edited after check.\n")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")

    def test_implementation_only_change_is_traced_but_not_selected_spec_test_review(self):
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# Behavior is unchanged.\n")
        result = self.run_check()
        self.assertEqual(result["status"], "passed")
        counts = result["source_boundaries"]["counts"]
        self.assertEqual(counts["all_changed_captured_source_paths"], 1)
        self.assertEqual(counts["changed_tracing_input_paths"], 1)
        self.assertEqual(counts["changed_selected_semantic_review_paths"], 0)
        self.assertEqual(result["source_boundaries"]["paths"][0]["path"], "session.py")

    def test_requirement_changes_keep_pending_review_and_distinct_file_counts(self):
        for path in ("requirements.md", "session.py", "tests/test_session.py"):
            self.replace(path, "req~session-expiration~1", "req~session-expiration~2")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required")
        counts = result["source_boundaries"]["counts"]
        self.assertEqual(counts["all_changed_captured_source_paths"], 3)
        self.assertEqual(counts["changed_selected_semantic_review_paths"], 2)
        self.assertGreater(
            result["review"]["change_count"], counts["changed_selected_semantic_review_paths"]
        )
        with self.assertRaises(CheckError):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )

    def test_inventory_is_recomputed_and_legacy_evidence_remains_readable(self):
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# Changed source.\n")
        result = self.run_check()
        review = read_json(self.out / "review.json")
        result["source_boundaries"]["counts"]["all_changed_captured_source_paths"] = 0
        review["source_boundaries"] = result["source_boundaries"]
        write_json(self.out / "review.json", review)
        result["artifacts"]["review.json"] = digest((self.out / "review.json").read_bytes())
        write_json(self.out / "evidence.json", statement(result))
        with self.assertRaisesRegex(CheckError, "boundary inventory"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        del result["source_boundaries"]
        del review["source_boundaries"]
        write_json(self.out / "review.json", review)
        result["artifacts"]["review.json"] = digest((self.out / "review.json").read_bytes())
        write_json(self.out / "evidence.json", statement(result))
        original = (self.out / "evidence.json").read_bytes()
        verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        explained = explain("req~session-expiration~1", self.out / "evidence.json", self.jar)
        self.assertEqual(
            explained["source_boundaries"]["counts"]["all_changed_captured_source_paths"], 1
        )
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)
