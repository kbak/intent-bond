"""Real OFT graph reporting over saved evidence, with no test re-execution."""

import json
import shutil
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond.common import CheckError, run
from intentbond.explain import explain, explain_many, render_context, render_explanation

REQ = "req~session-expiration~1"


class ExplainTests(WorkflowFixture):
    def test_draft_status_and_native_coverage_are_distinct_in_both_views(self):
        self.replace("requirements.md", f"`{REQ}`", f"`{REQ}`\nStatus: draft")
        self.run_check()
        result = self.explained()
        artifact = result["artifact"]
        self.assertEqual(artifact["oft_status"], "draft")
        self.assertEqual(artifact["coverage"]["deep"], "UNCOVERED")
        self.assertEqual(artifact["coverage"]["uncovered_types"], [])
        batch = explain_many([REQ], self.out / "evidence.json", self.jar)
        for rendered in (render_explanation(result), render_context(batch)):
            self.assertIn("OFT item status: draft", rendered)
            self.assertIn("deep=UNCOVERED", rendered)
            self.assertIn("Uncovered types: (none)", rendered)
            self.assertIn("OFT trace: passed", rendered)
            self.assertIn("draft status is not approval", rendered)
            self.assertIn("Recorded review gate: required", rendered)
        self.replace("tests/test_session.py", "# [utest->" + REQ + "]", "# Missing link")
        self.run_check()
        missing = self.explained()
        self.assertEqual(missing["recorded_check_status"], "rejected")
        self.assertIn("Uncovered types: utest", render_explanation(missing))
        self.assertIn("OFT trace: failed", render_explanation(missing))

    def explained(self, identifier=REQ, snapshot="candidate"):
        return explain(identifier, self.out / "evidence.json", self.jar, snapshot)

    def test_oft_reports_both_directions_and_keeps_execution_separate(self):
        self.run_check()
        result = self.explained()
        self.assertEqual(result["artifact"]["coverage"]["deep"], "COVERED")
        self.assertEqual(result["artifact"]["needs"], ["impl", "utest"])
        self.assertEqual(
            {ref["path"] for ref in result["related"]}, {"session.py", "tests/test_session.py"}
        )
        implementation = next(
            ref for ref in result["artifact"]["covered_by"] if ref.startswith("impl~")
        )
        self.assertEqual(self.explained(implementation)["artifact"]["covers"], [REQ])
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["tests"]["level"], "suite")
        self.assertEqual(result["linked_test_execution"], "not_established")

    def test_cli_uses_relocated_bundle_without_repo_or_test_execution(self):
        self.run_check()
        relocated = self.root / "relocated bundle"
        shutil.move(self.out, relocated)
        shutil.rmtree(self.repo)
        with patch(
            "intentbond.runner.execute_tests",
            side_effect=AssertionError("must not rerun"),
        ):
            code, output, error = self.run_cli(
                "explain",
                REQ,
                "--evidence",
                str(relocated / "evidence.json"),
                "--format",
                "json",
                cwd=self.root,
            )
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["artifact"]["id"], REQ)
        self.assertEqual(result["evidence"], str(relocated / "evidence.json"))
        code, output, error = self.run_cli(
            "explain", REQ, "--evidence", str(relocated / "evidence.json"), cwd=self.root
        )
        self.assertEqual(code, 0, error)
        self.assertIn("not established", output)
        self.assertIn("tests/test_session.py", output)

    def test_base_selection_does_not_attribute_candidate_tests_to_old_requirement(self):
        for path in ("requirements.md", "session.py", "tests/test_session.py"):
            self.replace(path, REQ, "req~session-expiration~2")
        self.run_check()
        candidate = self.explained("req~session-expiration~2")
        self.assertEqual(candidate["review"]["status"], "required")
        self.assertEqual(candidate["recorded_check_status"], "review_required")
        baseline = self.explained(snapshot="base")
        self.assertEqual(baseline["tests"]["status"], "not_recorded_for_baseline")
        with self.assertRaisesRegex(CheckError, "Unknown OFT item in candidate"):
            self.explained()

    def test_failed_test_results_remain_inspectable_without_passing_claim(self):
        self.replace("session.py", "30 * 60", "60 * 60")
        self.run_check()
        result = self.explained()
        self.assertEqual(result["artifact"]["coverage"]["deep"], "COVERED")
        self.assertEqual(result["recorded_check_status"], "rejected")
        self.assertEqual(result["tests"]["status"], "failed")
        self.assertEqual(result["linked_test_execution"], "not_established")

    def test_native_oft_uncovered_status_is_preserved(self):
        self.replace("tests/test_session.py", "# [utest->" + REQ + "]", "# Missing trace")
        self.run_check()
        result = self.explained()
        self.assertEqual(result["artifact"]["coverage"]["deep"], "UNCOVERED")
        self.assertEqual(result["artifact"]["coverage"]["uncovered_types"], ["utest"])
        self.assertEqual(result["oft_trace_status"], "failed")

    def test_command_results_do_not_gain_test_counts(self):
        self.configure(
            lambda scope: scope.update(
                tests={
                    "format": "command",
                    "command": ["python3", "-c", "pass"],
                    "timeout_seconds": 30,
                }
            )
        )
        self.run_check()
        result = self.explained()
        self.assertEqual(result["tests"]["level"], "command")
        self.assertNotIn("counts", result["tests"])

    def test_changed_export_is_rejected_before_oft_reporting(self):
        self.run_check()
        path = self.out / "candidate-items.xml"
        path.write_text(path.read_text().replace("session-expiration", "invented"))
        with patch("intentbond.explain.run", side_effect=AssertionError("must not run")):
            with self.assertRaisesRegex(CheckError, "artifact missing or changed"):
                self.explained()

    def test_unknown_id_and_revision_are_errors(self):
        self.run_check()
        for identifier in ("req~invented~1", "req~session-expiration~99", "req~session-expiration"):
            with self.subTest(identifier=identifier):
                code, output, error = self.run_cli(
                    "explain", identifier, "--evidence", str(self.out / "evidence.json")
                )
                self.assertEqual(code, 2)
                self.assertFalse(output)
                self.assertIn("Unknown OFT item", error)

    def test_batch_loads_one_graph_and_preserves_single_item_semantics(self):
        self.run_check()
        single = self.explained()
        implementation = next(
            ref for ref in single["artifact"]["covered_by"] if ref.startswith("impl~")
        )
        with patch("intentbond.explain.run", wraps=run) as traced:
            batch = explain_many([REQ, implementation, REQ], self.out / "evidence.json", self.jar)
        self.assertEqual(traced.call_count, 1)
        self.assertEqual([e["artifact"]["id"] for e in batch["artifacts"]], [REQ, implementation])
        entry = batch["artifacts"][0]
        for key in (
            "artifact",
            "linked_tests",
            "linked_test_execution",
            "execution_link_diagnostics",
        ):
            self.assertEqual(entry[key], single[key])
        for key in ("source", "tests", "review", "recorded_diagnostics", "limitations"):
            self.assertEqual(batch[key], single[key])
        self.assertEqual(len(batch["related"]), len({ref["id"] for ref in batch["related"]}))
        self.assertNotIn("artifacts", single)

    def test_batch_cli_fails_atomically_for_one_unknown_revision(self):
        self.run_check()
        code, output, error = self.run_cli(
            "explain",
            REQ,
            "req~session-expiration~99",
            "--evidence",
            str(self.out / "evidence.json"),
        )
        self.assertEqual(code, 2)
        self.assertFalse(output)
        self.assertIn("Unknown OFT item", error)

    def test_compact_cli_json_is_explicit_and_text_shares_status(self):
        self.run_check()
        code, output, error = self.run_cli(
            "explain", REQ, REQ, "--evidence", str(self.out / "evidence.json"), "--format", "json"
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(len(json.loads(output)["artifacts"]), 1)
        code, output, error = self.run_cli(
            "explain", REQ, "--compact", "--evidence", str(self.out / "evidence.json")
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(output.count("Recorded check:"), 1)
        self.assertIn("not exhaustive impact analysis", output)
        self.assertIn("not established", output)
        self.assertIn("tests/test_session.py", output)

    def test_compact_retains_failures_uncovered_status_and_baseline_uncertainty(self):
        self.replace("session.py", "30 * 60", "60 * 60")
        self.replace("tests/test_session.py", "# [utest->" + REQ + "]", "# Missing trace")
        self.run_check()
        result = explain_many([REQ], self.out / "evidence.json", self.jar)
        output = render_context(result)
        self.assertIn("deep=UNCOVERED", output)
        self.assertIn("Tests: failed", output)
        self.assertIn("Recorded check: rejected", output)
        baseline = explain_many([REQ], self.out / "evidence.json", self.jar, "base")
        self.assertEqual(baseline["tests"]["status"], "not_recorded_for_baseline")

    def test_compact_collapses_shared_locations_without_losing_edges(self):
        self.run_check()
        result = explain_many([REQ], self.out / "evidence.json", self.jar)
        original = result["related"][0]
        duplicate = {**original, "id": "impl~second-claim~0"}
        result["related"].append(duplicate)
        result["artifacts"][0]["artifact"]["covered_by"].append(duplicate["id"])
        output = render_context(result)
        self.assertEqual(output.count(f"{original['path']}:{original['line']}"), 1)
        self.assertIn(duplicate, result["related"])
