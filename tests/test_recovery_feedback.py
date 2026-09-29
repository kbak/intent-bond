"""Bounded recovery gives useful feedback without pretending gaps are resolved."""

import contextlib
import io
import shutil
from pathlib import Path
from unittest.mock import patch

from test_recovery import RecoveryFixture

from intentbond.cli import main
from intentbond.common import CheckError, read_json, write_json
from intentbond.oft import import_items
from intentbond.recovery import check_recovery, prepare, recovery_storage
from intentbond.runner import verify


class RecoveryFeedbackTests(RecoveryFixture):
    def test_preflight_validates_provenance_without_tests_or_passing_evidence(self):
        self.draft()
        out = self.root / "preflight"
        with patch("intentbond.runner.execute_tests") as tests:
            result = check_recovery(self.bundle, None, out, self.jar, preflight=True)
        # [utest->req~ib-recovery-preflight~1]
        tests.assert_not_called()
        self.assertEqual(result["status"], "incomplete", result)
        self.assertEqual(result["proposal_checks"], "passed")
        self.assertFalse((out / "check/test-result.json").exists())
        self.assertIn("without running tests", (out / result["summary"]).read_text())
        with self.assertRaisesRegex(CheckError, "successful check"):
            verify(self.repo, None, "HEAD", "worktree", out / "check/evidence.json", True)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(
                [
                    "recover-check",
                    "--recovery",
                    str(self.bundle),
                    "--preflight",
                    "--oft-jar",
                    str(self.jar),
                    "--out",
                    str(self.root / "cli-preflight"),
                ]
            )
        self.assertEqual(code, 5)

    def test_partial_proposal_reports_valid_integrity_and_failed_graph_separately(self):
        self.draft()
        shutil.copyfile(self.bundle / "source/session.py", self.bundle / "draft/session.py")
        self.claims["open_issues"] = [
            {
                "description": "Implementation link needs review.",
                "items": ["req~session-expiration~1"],
                "sources": [],
            }
        ]
        self.save_claims()
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertEqual(result["proposal_checks"], "passed")
        summary = (self.out / result["summary"]).read_text()
        self.assertIn("Implementation link needs review.", summary)
        self.assertIn("1 passed, 0 failed", summary)
        self.assertIn("policy is not satisfied", summary)
        self.assertIn(result["summary"], result["artifacts"])
        self.claims["items"][0]["sources"][0]["quote"] = "Invented evidence"
        self.save_claims()
        result = self.run_check()
        self.assertNotEqual(result["proposal_checks"], "passed")

    def test_jsx_and_tsx_use_native_oft_tags_with_original_source_locations(self):
        for suffix in ("tsx", "jsx"):
            for stem in ("view", "test_view"):
                (self.repo / f"{stem}.{suffix}").write_text("const view = <div />;\n")
        self.commit()
        self.draft()
        scope = read_json(self.bundle / "draft/scope.json")
        scope["inputs"] = ["."]
        for suffix in ("tsx", "jsx"):
            for stem, kind in (("view", "impl"), ("test_view", "utest")):
                name = f"{stem}.{suffix}"
                target = self.bundle / "draft" / name
                target.write_text(f"// [{kind}->req~session-expiration~1]\n" + target.read_text())
                if kind == "utest":
                    scope["test_paths"].append(name)
        write_json(self.bundle / "draft/scope.json", scope)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        items = import_items(self.out / "check/candidate-items.xml", self.bundle / "draft")
        tagged = [i for i in items if Path(i["path"]).suffix in {".jsx", ".tsx"}]
        self.assertEqual(len(tagged), 4)
        self.assertTrue(all(i["line"] == 1 for i in tagged))
        before = {i["id"] for i in tagged}
        self.run_check()
        after = import_items(self.out / "check/candidate-items.xml", self.bundle / "draft")
        self.assertTrue(before.issubset({i["id"] for i in after}))
        self.assertFalse(list((self.bundle / "draft").glob("*.tsx.ts")))

    def test_isolated_defaults_keep_source_and_results_in_git_storage(self):
        record = prepare(self.repo, "HEAD", ["."], isolated=True)
        bundle = Path(record["bundle"])
        self.assertTrue(bundle.is_relative_to(recovery_storage(self.repo)))
        self.assertEqual(self.git("status", "--porcelain"), "")
        result = check_recovery(bundle, None, None, self.jar)
        self.assertTrue(Path(result["output"]).is_relative_to(recovery_storage(self.repo)))
        self.assertTrue((Path(result["output"]) / result["summary"]).is_file())
        self.assertTrue((bundle / "source/README.md").exists())
