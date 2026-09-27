"""In-place recovery retains original evidence and follows ordinary Git review."""

import contextlib
import io
import shutil
from pathlib import Path
from unittest.mock import patch

from test_recovery import RecoveryFixture

from intentbond.cli import main
from intentbond.common import CheckError, read_json, write_json
from intentbond.oft import import_items
from intentbond.recovery import active_recovery, prepare
from intentbond.runner import check


class InPlaceRecoveryTests(RecoveryFixture):
    isolated = False

    def test_default_preparation_preserves_snapshot_and_leaves_git_review_records(self):
        original = (self.repo / "session.py").read_bytes()
        record = self.prepare()
        self.assertEqual(record["mode"], "in_place")
        self.assertEqual(Path(record["workspace"]), self.repo)
        self.assertEqual(active_recovery(self.repo), self.bundle)
        self.assertFalse((self.bundle / "draft").exists())
        self.assertEqual((self.bundle / "source/session.py").read_bytes(), original)
        self.assertEqual((self.repo / "session.py").read_bytes(), original)
        self.assertTrue(self.claims_file.is_file())
        self.assertEqual(
            read_json(self.repo / record["source_record_path"])["source"]["commit"],
            self.source_commit,
        )
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.source_commit)
        self.assertEqual(self.git("diff", "--cached"), "")
        self.assertIn(
            ".traceability/recovery/", self.git("status", "--porcelain", "--untracked-files=all")
        )

    def test_in_place_proposal_adopts_without_applying_a_patch(self):
        self.draft()
        before = self.git("diff")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(self.git("diff"), before)
        self.assertEqual(self.git("diff", "--cached"), "")
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.source_commit)
        self.assertIn("impl->req~session-expiration~1", before)
        self.assertNotIn("impl->", (self.bundle / "source/session.py").read_text())
        self.assertTrue((self.out / "proposal.patch").is_file())
        self.assertFalse((self.out / "proposed").exists())
        self.commit()  # Represents this test caller's review and acceptance.
        adopted = check(self.repo, None, "HEAD", "HEAD", self.root / "adopted", self.jar)
        self.assertEqual(adopted["status"], "passed", adopted)
        path = self.repo / "session.py"
        path.write_text(path.read_text().replace("30 * 60", "1800"))
        subsequent = check(self.repo, None, "HEAD", "worktree", self.root / "subsequent", self.jar)
        self.assertEqual(subsequent["status"], "passed", subsequent)

    def test_dirty_checkouts_fail_before_writing_recovery_files(self):
        for change in ("tracked", "staged", "untracked"):
            with self.subTest(change=change):
                path = self.repo / ("extra.txt" if change == "untracked" else "README.md")
                original = path.read_bytes() if path.exists() else None
                path.write_text("Existing work\n")
                if change == "staged":
                    self.git("add", "README.md")
                with self.assertRaisesRegex(CheckError, "clean checkout"):
                    self.prepare()
                self.assertFalse(self.bundle.exists())
                self.assertEqual(path.read_text(), "Existing work\n")
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)
                if change == "staged":
                    self.git("reset", "HEAD", "--", "README.md")

    def test_other_source_version_requires_isolation(self):
        self.empty_commit()
        with self.assertRaisesRegex(CheckError, "must start at HEAD"):
            prepare(self.repo, self.source_commit, ["."], self.bundle)
        self.assertFalse(self.bundle.exists())

    def empty_commit(self):
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "Concurrent commit",
        )

    def test_starting_commit_change_prevents_check(self):
        self.draft()
        self.empty_commit()
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("starting commit or branch changed", " ".join(result["diagnostics"]))

    def test_branch_change_at_same_commit_prevents_check(self):
        self.draft()
        self.git("switch", "-c", "other-work")
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("starting commit or branch changed", " ".join(result["diagnostics"]))

    def test_concurrent_commit_invalidates_checked_proposal(self):
        self.draft()
        from intentbond.runner import check as real_check

        def commit_after_check(*args, **kwargs):
            result = real_check(*args, **kwargs)
            self.empty_commit()
            return result

        with patch("intentbond.recovery.check", side_effect=commit_after_check):
            result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("starting commit or branch", " ".join(result["diagnostics"]))

    def test_unexpected_edits_stay_visible_and_are_rejected(self):
        self.draft()
        (self.repo / "unrelated.txt").write_text("Other work\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("unrelated.txt", " ".join(result["diagnostics"]))
        self.assertEqual((self.repo / "unrelated.txt").read_text(), "Other work\n")
        self.assertTrue((self.repo / "requirements.md").exists())

    def test_original_snapshot_and_durable_source_record_are_protected(self):
        self.draft()
        path = self.repo / self.record["source_record_path"]
        value = read_json(path)
        value["source"]["commit"] = "0" * 40
        write_json(path, value)
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("Original source record changed", " ".join(result["diagnostics"]))
        (self.bundle / "source/README.md").write_text("Changed original evidence\n")
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("Captured recovery source changed", " ".join(result["diagnostics"]))

    def test_ignored_record_location_is_rejected_without_overwriting_project(self):
        (self.repo / ".gitignore").write_text(".traceability/\n")
        self.commit()
        with self.assertRaisesRegex(CheckError, "Git ignores recovery records"):
            self.prepare()
        self.assertFalse((self.repo / ".traceability").exists())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_historical_quoted_annotations_cannot_supply_live_coverage(self):
        history = self.repo / ".traceability/recovery/old"
        history.mkdir(parents=True)
        write_json(history / "claims.json", {"quote": "# [utest->req~session-expiration~1]"})
        self.commit()
        self.draft()
        scope = read_json(self.repo / "scope.json")
        scope["inputs"] = ["."]
        write_json(self.repo / "scope.json", scope)
        # A quoted historical link must not satisfy the coverage need.
        shutil.copyfile(
            self.bundle / "source/tests/test_session.py", self.repo / "tests/test_session.py"
        )
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertEqual(result["check_status"], "rejected", result)
        imported = import_items(self.out / "check/candidate-items.xml", self.repo)
        self.assertFalse(
            any(item["path"].startswith(".traceability/recovery/") for item in imported)
        )
        self.assertEqual(
            read_json(self.out / "check/evidence.json")["predicate"]["tests"]["status"], "passed"
        )

    def test_cli_recovers_into_git_storage_and_discovers_active_run(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["recover", "--repo", str(self.repo)])
        self.assertEqual(code, 0, stderr.getvalue())
        bundle = active_recovery(self.repo)
        self.assertTrue(bundle.is_relative_to(self.repo / ".git"))
        self.assertFalse((bundle / "draft").exists())
        self.assertEqual(
            read_json(bundle / "recovery.json")["source"]["commit"], self.source_commit
        )

    def test_cli_check_from_subdirectory_needs_no_bundle_or_output_path(self):
        self.draft()
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch("pathlib.Path.cwd", return_value=self.repo / "tests"),
        ):
            code = main(["recover-check", "--oft-jar", str(self.jar)])
        self.assertEqual(code, 4, (stdout.getvalue(), stderr.getvalue()))
        self.assertIn("working-tree changes", stdout.getvalue())
        self.assertIn(".git/intentbond/recovery/checks", stdout.getvalue())

    def test_git_worktree_uses_its_own_storage_and_preserves_original_checkout(self):
        worktree = self.root / "linked-worktree"
        self.git("worktree", "add", "-b", "recovery-work", str(worktree))
        record = prepare(worktree, "HEAD", ["."])
        self.assertEqual(active_recovery(worktree), Path(record["bundle"]))
        self.assertTrue(Path(record["bundle"]).is_relative_to(self.repo / ".git/worktrees"))
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertTrue((worktree / record["claims_path"]).is_file())
