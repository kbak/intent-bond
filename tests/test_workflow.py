"""Acceptance cases execute the pinned OFT JAR and real tests in disposable Git repos."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond.cli import main
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.evidence import statement
from intentbond.oft import default_jar, validate_jar
from intentbond.runner import check, verify

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "session"


class WorkflowFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jar = default_jar().resolve()
        # Deliberately fail setup if missing, instead of silently skipping the real-engine tests.
        validate_jar(cls.jar)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ib-acceptance-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repository with spaces"
        shutil.copytree(FIXTURE, self.repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.git("init", "-q", "-b", "main")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.scope = self.root / "policy.json"
        shutil.copyfile(self.repo / "scope.json", self.scope)
        self.counter = 0

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout

    def commit(self):
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Fixture revision",
        )

    def replace(self, name, before, after):
        path = self.repo / name
        self.assertIn(before, path.read_text())
        path.write_text(path.read_text().replace(before, after))

    def configure(self, edit):
        scope = read_json(self.scope)
        edit(scope)
        write_json(self.scope, scope)

    def run_check(self, **kwargs):
        self.counter += 1
        self.out = self.root / f"evidence-{self.counter}"
        options = dict(
            repo_path=self.repo,
            scope_path=self.scope,
            base_ref=self.base,
            candidate_ref="worktree",
            out=self.out,
            jar=self.jar,
        )
        options.update(kwargs)
        result = check(**options)
        self.assertTrue((self.out / "evidence.json").is_file())
        return result

    def assert_problem(self, result, fragment):
        self.assertNotEqual(result["status"], "passed", result)
        self.assertIn(fragment, "\n".join(result["diagnostics"]), result["diagnostics"])

    def run_cli(self, *args, cwd=None, temp_root=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.chdir(cwd or self.repo),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch.dict("os.environ", {"INTENTBOND_OFT_JAR": str(self.jar)}),
            patch("tempfile.tempdir", str(temp_root or self.root)),
        ):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()


class WorkflowTests(WorkflowFixture):
    def test_unparsed_junit_failure_cannot_pass_check_or_verification(self):
        report = (
            '<testsuites tests="2"><testsuites tests="1"><testsuite tests="1">'
            '<testcase name="broken"><failure/></testcase></testsuite></testsuites>'
            '<testsuite tests="1"><testcase name="ok"/></testsuite></testsuites>'
        )
        self.run_check()
        (self.out / "tests.xml").write_text(report)
        evidence = read_json(self.out / "evidence.json")
        evidence["predicate"]["artifacts"]["tests.xml"] = digest(report.encode())
        write_json(self.out / "evidence.json", evidence)
        with self.assertRaisesRegex(CheckError, "not every testcase was parsed"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        self.configure(
            lambda scope: scope["tests"].update(
                command=[
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path('test-results.xml').write_text({report!r})",
                ]
            )
        )
        result = self.run_check()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["tests"]["status"], "error")
        self.assertIn("not every testcase was parsed", result["tests"]["error"])

    def test_cli_defaults_check_local_changes_from_subdirectory_and_verify(self):
        self.replace("session.py", "30 * 60", "1800")
        before = self.git("status", "--porcelain")
        code, stdout, stderr = self.run_cli("check", cwd=self.repo / "tests")
        self.assertEqual(code, 0, (stdout, stderr))
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertFalse(evidence.is_relative_to(self.repo))
        result = read_json(evidence)["predicate"]
        self.assertIn("tests: passed (suite); source=matched", stdout)
        self.assertIn(f"tests.xml: {evidence.parent / 'tests.xml'}", stdout)
        self.assertIn("counts:", stdout)
        self.assertEqual(result["base"]["commit"], self.base)
        self.assertEqual(result["candidate"]["kind"], "worktree")
        self.assertEqual(result["scope"]["configuration"], read_json(self.scope))
        self.assertEqual(self.git("status", "--porcelain"), before)
        code, stdout, stderr = self.run_cli(
            "verify", "--evidence", str(evidence), cwd=self.repo / "tests"
        )
        self.assertEqual(code, 0, (stdout, stderr))
        self.assertEqual(json.loads(stdout)["status"], "matched")

        self.replace("session.py", "1800", "0")
        code, stdout, stderr = self.run_cli("verify", "--evidence", str(evidence))
        self.assertEqual(code, 2, stdout)
        self.assertIn("Candidate contents differ", stderr)
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 1, (stdout, stderr))
        failed_evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertNotEqual(failed_evidence.parent, evidence.parent)
        self.assertEqual(read_json(evidence)["predicate"]["status"], "passed")
        self.assertEqual(read_json(failed_evidence)["predicate"]["status"], "rejected")
        self.assertIn("Reported failures", stdout)
        self.assertIn("test_expiration_boundary", stdout)

    def test_cli_default_scope_cannot_be_weakened_by_candidate_edits(self):
        self.replace("requirements.md", "Needs: impl, utest", "Needs: impl")
        self.replace(
            "tests/test_session.py", "# [utest->req~session-expiration~1]", "# Removed reference"
        )
        local = read_json(self.repo / "scope.json")
        local["required_coverage"] = {"req": ["impl"]}
        write_json(self.repo / "scope.json", local)
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 1, (stdout, stderr))
        self.assertIn("must retain Needs: utest", stdout)
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertEqual(read_json(evidence.parent / "scope.json"), read_json(self.scope))

    def test_cli_branch_default_includes_commits_and_edits_using_original_scope(self):
        self.git("checkout", "-qb", "topic")
        self.replace("requirements.md", "30 minutes", "60 minutes")
        self.commit()
        local = read_json(self.repo / "scope.json")
        local["name"] = "candidate-policy"
        write_json(self.repo / "scope.json", local)
        self.commit()
        self.git("checkout", "-q", "main")
        (self.repo / "unrelated.txt").write_text("Another change on main\n")
        self.commit()
        self.git("checkout", "-q", "topic")
        self.replace("session.py", "30 * 60", "1800")
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 4, (stdout, stderr))
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertEqual(read_json(evidence)["predicate"]["base"]["commit"], self.base)
        self.assertEqual(read_json(evidence.parent / "scope.json"), read_json(self.scope))
        self.assertIn("60 minutes", (evidence.parent / "review.patch").read_text())
        self.commit()
        code, stdout, stderr = self.run_cli(
            "verify", "--evidence", str(evidence), "--allow-pending-review"
        )
        self.assertEqual(code, 0, (stdout, stderr))
        self.assertEqual(json.loads(stdout)["review"], "required")
        code, stdout, stderr = self.run_cli("check", "--base", "HEAD")
        self.assertEqual(code, 0, (stdout, stderr))
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertEqual(
            read_json(evidence)["predicate"]["base"]["commit"],
            self.git("rev-parse", "HEAD").strip(),
        )
        self.assertEqual(read_json(evidence.parent / "scope.json"), local)

    def test_cli_remote_default_branch_uses_local_tip_when_available(self):
        self.git("branch", "-m", "trunk")
        self.git("update-ref", "refs/remotes/origin/trunk", self.base)
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.replace("session.py", "30 * 60", "1800")
        self.commit()
        base = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-qb", "topic")
        self.replace("requirements.md", "30 minutes", "60 minutes")
        self.commit()
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 4, (stdout, stderr))
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertEqual(read_json(evidence)["predicate"]["base"]["commit"], base)
        self.git("update-ref", "refs/remotes/origin/trunk", base)
        self.git("branch", "-D", "trunk")
        code, stdout, stderr = self.run_cli(
            "verify", "--evidence", str(evidence), "--allow-pending-review"
        )
        self.assertEqual(code, 0, (stdout, stderr))

    def test_cli_unknown_default_branch_requires_explicit_base(self):
        self.git("branch", "-m", "trunk")
        self.git("checkout", "-qb", "topic")
        self.replace("requirements.md", "30 minutes", "60 minutes")
        self.commit()
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 2, stdout)
        self.assertIn("Cannot identify the default branch", stderr)
        code, stdout, stderr = self.run_cli("check", "--base", self.base)
        self.assertEqual(code, 4, (stdout, stderr))

    def test_cli_detached_head_defaults_to_checked_out_commit(self):
        self.git("checkout", "-q", "--detach", self.base)
        self.replace("session.py", "30 * 60", "1800")
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 0, (stdout, stderr))
        evidence = Path(stdout.splitlines()[0].split(": ", 1)[1])
        self.assertEqual(read_json(evidence)["predicate"]["base"]["commit"], self.base)

    def test_cli_missing_baseline_scope_does_not_fall_back_to_worktree(self):
        (self.repo / "scope.json").unlink()
        self.commit()
        shutil.copyfile(self.scope, self.repo / "scope.json")
        code, stdout, stderr = self.run_cli("check")
        self.assertEqual(code, 2, (stdout, stderr))
        self.assertIn("Cannot read scope.json from the baseline", stdout)
        code, stdout, stderr = self.run_cli("check", "--scope", str(self.scope))
        self.assertEqual(code, 0, (stdout, stderr))

    def test_cli_invalid_baseline_scope_does_not_fall_back_to_valid_worktree_file(self):
        for content in ("{", '{"schema_version": 1, "schema_version": 1}'):
            with self.subTest(content=content):
                (self.repo / "scope.json").write_text(content)
                self.commit()
                shutil.copyfile(self.scope, self.repo / "scope.json")
                code, stdout, stderr = self.run_cli("check")
                self.assertEqual(code, 2, (stdout, stderr))

    def test_cli_default_output_cannot_be_created_inside_repository(self):
        before = self.git("status", "--porcelain")
        code, stdout, stderr = self.run_cli("check", temp_root=self.repo)
        self.assertEqual(code, 2, stdout)
        self.assertIn("supply --out outside", stderr)
        self.assertEqual(self.git("status", "--porcelain"), before)

    def test_valid_dirty_candidate_can_match_later_exported_commit(self):
        self.replace("session.py", "30 * 60", "1800")
        (self.repo / "new-helper.txt").write_text("Git-visible untracked source\n")
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["tests"]["counts"]["passed"], 1)
        evidence = self.out / "evidence.json"
        self.commit()
        matched = verify(self.repo, self.scope, self.base, "HEAD", evidence)
        self.assertEqual(matched["status"], "matched")
        self.assertNotEqual(matched["candidate"]["commit"], result["candidate"]["commit"])

    def test_commit_candidate_ignores_uncommitted_changes(self):
        self.replace("session.py", "30 * 60", "0")
        result = self.run_check(candidate_ref=self.base)
        self.assertEqual(result["status"], "passed", result)

    def test_statement_subject_and_manifest_preserve_executable_modes(self):
        result = self.run_check()
        saved = read_json(self.out / "evidence.json")
        self.assertEqual(saved["_type"], "https://in-toto.io/Statement/v1")
        self.assertEqual(
            saved["subject"][0]["digest"]["sha256"], result["artifacts"]["candidate-manifest.json"]
        )
        (self.repo / "session.py").chmod(0o755)
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")

    def test_pending_review_cannot_be_relabelled_as_success(self):
        self.replace("requirements.md", "30 minutes", "60 minutes")
        result = self.run_check()
        result["status"] = "passed"
        result["review"]["status"] = "not_needed"
        write_json(self.out / "evidence.json", statement(result))
        with self.assertRaisesRegex(CheckError, "pending change review"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")

    def test_missing_implementation_reference(self):
        self.replace("session.py", "# [impl->req~session-expiration~1]", "# Missing reference")
        self.assert_problem(self.run_check(), "Candidate trace defects")

    def test_missing_test_reference(self):
        self.replace(
            "tests/test_session.py", "# [utest->req~session-expiration~1]", "# Missing reference"
        )
        self.assert_problem(self.run_check(), "Candidate trace defects")

    def test_stale_revision_reference(self):
        self.replace("requirements.md", "~1`", "~2`")
        self.assert_problem(self.run_check(), "Candidate trace defects")

    def test_prose_change_is_pending_review_without_mandatory_revision_bump(self):
        self.replace("requirements.md", "30 minutes", "60 minutes")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["review"]["status"], "required")
        self.configure(lambda s: s.update(policy={"require_revision_increase": True}))
        self.assert_problem(self.run_check(), "revision increase")

    def test_removed_needs_cannot_turn_green_by_editing_candidate_policy(self):
        self.replace("requirements.md", "Needs: impl, utest", "Needs: impl")
        self.replace(
            "tests/test_session.py", "# [utest->req~session-expiration~1]", "# Removed reference"
        )
        local = read_json(self.repo / "scope.json")
        local["required_coverage"] = {"req": ["impl"]}
        write_json(self.repo / "scope.json", local)
        write_json(self.repo / "approval.json", {"decision": "I approve my own change"})
        result = self.run_check()
        self.assertEqual(result["trace"]["candidate"]["status"], "passed")
        self.assert_problem(result, "must retain Needs: utest")

    def test_removed_requirement_is_visible(self):
        self.replace("requirements.md", "`req~session-expiration~1`", "Removed promise")
        result = self.run_check()
        self.assert_problem(result, "no selected requirements")
        changed = read_json(self.out / "review.json")["changes"]
        self.assertTrue(any(c["kind"] == "requirement" and c["after"] is None for c in changed))

    def test_passing_test_edit_stays_reviewable_without_an_approval_file(self):
        self.replace(
            "tests/test_session.py", "self.assertTrue(expired(1800))", "self.assertTrue(True)"
        )
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["status"], "review_required")
        self.assertIn("self.assertTrue(True)", (self.out / "review.patch").read_text())
        evidence = self.out / "evidence.json"
        with self.assertRaisesRegex(CheckError, "successful check"):
            verify(self.repo, self.scope, self.base, "worktree", evidence)
        matched = verify(
            self.repo, self.scope, self.base, "worktree", evidence, allow_pending_review=True
        )
        self.assertEqual(matched["review"], "required")
        self.replace("session.py", "30 * 60", "1800")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(
                self.repo, self.scope, self.base, "worktree", evidence, allow_pending_review=True
            )

    def test_requirement_revision_and_references_remain_reviewable(self):
        for path in ("requirements.md", "session.py", "tests/test_session.py"):
            self.replace(path, "~1", "~2")
        self.replace("requirements.md", "A session expires", "The session expires")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)

    def test_pending_review_does_not_hide_failing_test(self):
        self.replace(
            "tests/test_session.py", "assertTrue(expired(1800))", "assertFalse(expired(1800))"
        )
        result = self.run_check()
        self.assert_problem(result, "Test execution did not pass")
        self.assertEqual(result["review"]["status"], "required")

    def test_oft_artifact_chain_needs_no_direct_requirement_test_link(self):
        self.replace("requirements.md", "Needs: impl, utest", "Needs: dsn")
        with (self.repo / "requirements.md").open("a") as handle:
            handle.write(
                "\n### Session design\n`dsn~session-design~1`\n\nUse the elapsed time.\n\nCovers:\n- req~session-expiration~1\n\nNeeds: impl, utest\n"
            )
        self.replace("session.py", "impl->req~session-expiration", "impl->dsn~session-design")
        self.replace(
            "tests/test_session.py", "utest->req~session-expiration", "utest->dsn~session-design"
        )
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.configure(lambda s: s.update(required_coverage={"req": ["dsn"]}))
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        self.replace("requirements.md", "Use the elapsed time.", "Use a monotonic clock.")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertTrue(
            any(
                c.get("key") == "dsn~session-design"
                for c in read_json(self.out / "review.json")["changes"]
            )
        )

    def test_skips_are_policy_and_all_skipped_still_means_no_executed_tests(self):
        with (self.repo / "tests/test_session.py").open("a") as handle:
            handle.write(
                "\nclass OptionalTests(unittest.TestCase):\n    @unittest.skip('other platform')\n    def test_optional(self):\n        pass\n"
            )
        result = self.run_check()
        self.assertEqual(result["tests"]["status"], "passed", result)
        self.assertEqual(result["tests"]["counts"]["skipped"], 1)
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )
        self.configure(lambda s: s.update(policy={"allow_skipped_tests": False}))
        self.assert_problem(self.run_check(), "Test execution did not pass")

    def test_command_adapter_uses_real_execution_without_claiming_case_counts(self):
        self.configure(
            lambda s: s.update(
                tests={
                    "format": "command",
                    "command": ["python3", "-m", "unittest", "discover", "-s", "tests"],
                    "timeout_seconds": 30,
                }
            )
        )
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["tests"]["level"], "command")
        self.assertNotIn("counts", result["tests"])
        verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        self.replace("session.py", "30 * 60", "60 * 60")
        self.assert_problem(self.run_check(), "Test execution did not pass")

    def test_linked_but_failing_test(self):
        self.replace("session.py", "30 * 60", "60 * 60")
        result = self.run_check()
        self.assertEqual(result["trace"]["candidate"]["status"], "passed")
        self.assert_problem(result, "Test execution did not pass")
        self.assertEqual(result["tests"]["counts"]["failed"], 1)
        self.assertEqual(read_json(self.out / "test-result.json")["predicate"]["result"], "FAILED")

    def test_skipped_test(self):
        self.replace(
            "tests/test_session.py",
            "    def test_expiration_boundary",
            "    @unittest.skip('not executed')\n    def test_expiration_boundary",
        )
        result = self.run_check()
        self.assert_problem(result, "Test execution did not pass")
        self.assertEqual(result["tests"]["counts"]["skipped"], 1)

    def test_zero_discovered_tests(self):
        self.replace(
            "tests/test_session.py",
            "def test_expiration_boundary",
            "def unused_expiration_boundary",
        )
        result = self.run_check()
        self.assert_problem(result, "Test execution did not pass")
        self.assertEqual(result["tests"]["counts"]["total"], 0)

    def test_missing_report_even_when_command_returns_zero(self):
        self.configure(lambda s: s["tests"].update(command=[sys.executable, "-c", "pass"]))
        result = self.run_check()
        self.assertEqual(result["tests"]["exit_code"], 0)
        self.assert_problem(result, "Test execution did not pass")

    def test_stale_report_is_rejected(self):
        (self.repo / "stale.xml").write_text('<testsuite><testcase name="old"/></testsuite>')
        self.configure(lambda s: s["tests"].update(report="stale.xml"))
        self.assert_problem(self.run_check(), "already exists in candidate")

    def test_source_mutation_by_test_is_detected(self):
        self.replace(
            "run_tests.py",
            "suite_xml = ET.Element",
            "open('session.py', 'a').write('# test mutation\\n')\nsuite_xml = ET.Element",
        )
        result = self.run_check()
        self.assert_problem(result, "modified captured source")
        self.assertNotIn("test mutation", (self.repo / "session.py").read_text())
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertFalse((self.out / "test-result.json").exists())

    def test_test_command_repair_cannot_attest_original_broken_candidate_passed(self):
        self.replace("session.py", "30 * 60", "60 * 60")
        self.replace(
            "run_tests.py",
            "suite_xml = ET.Element",
            "from pathlib import Path\n"
            "source = Path('session.py')\n"
            "source.write_text(source.read_text().replace('60 * 60', '30 * 60'))\n"
            "suite_xml = ET.Element",
        )
        for test_format in ("junit", "command"):
            with self.subTest(format=test_format):
                if test_format == "command":
                    self.configure(
                        lambda s: (s["tests"].update(format="command"), s["tests"].pop("report"))
                    )
                result = self.run_check()
                self.assertEqual(result["status"], "rejected")
                self.assert_problem(result, "modified captured source: session.py")
                self.assertEqual(result["tests"]["exit_code"], 0)
                self.assertEqual(result["tests"]["status"], "passed")
                self.assertEqual(result["tests"]["source_status"], "changed")
                self.assertTrue((self.out / "tests.log").is_file())
                self.assertIn("60 * 60", (self.repo / "session.py").read_text())
                self.assertFalse((self.out / "test-result.json").exists())
                self.assertNotIn("test-result.json", result["artifacts"])

    def test_unchecked_source_cannot_produce_a_test_attestation(self):
        with patch("intentbond.runner.changed_source", side_effect=OSError("unreadable source")):
            result = self.run_check()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tests"]["status"], "passed")
        self.assertEqual(result["tests"]["source_status"], "unchecked")
        self.assertFalse((self.out / "test-result.json").exists())

    def test_original_candidate_changes_during_validation(self):
        from intentbond.runner import execute_tests

        def mutate(*args):
            result = execute_tests(*args)
            self.replace("session.py", "30 * 60", "1800")
            return result

        with patch("intentbond.runner.execute_tests", side_effect=mutate):
            result = self.run_check()
        self.assert_problem(result, "Original candidate changed")
        self.assertFalse((self.out / "test-result.json").exists())

    def test_inherited_baseline_defect_is_not_silently_absorbed(self):
        self.replace("session.py", "# [impl->req~session-expiration~1]", "# Missing reference")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.replace("session.py", "# Missing reference", "# [impl->req~session-expiration~1]")
        result = self.run_check()
        self.assertEqual(result["trace"]["candidate"]["status"], "passed")
        self.assert_problem(result, "Inherited baseline trace defects")

    def test_empty_scope_requires_explicit_non_success(self):
        self.configure(lambda s: s.update(required_coverage={"feat": ["impl", "utest"]}))
        self.assert_problem(self.run_check(), "no selected requirements")
        self.configure(lambda s: s.update(allow_empty=True))
        result = self.run_check()
        self.assertEqual(result["status"], "empty", result)
        self.assertEqual(result["tests"]["status"], "not_run")

    def test_missing_and_invalid_tools_produce_error_evidence(self):
        self.assert_problem(self.run_check(jar=self.root / "missing.jar"), "unavailable")
        bad = self.root / "bad.jar"
        bad.write_bytes(b"not OFT")
        self.assert_problem(self.run_check(jar=bad), "checksum mismatch")
        self.assert_problem(
            self.run_check(java=str(self.root / "missing-java")), "OFT import failed"
        )

    def test_invalid_scope_or_base_never_passes(self):
        self.assert_problem(self.run_check(base_ref="missing-reference"), "revision")
        self.configure(lambda s: s.update(inputs=["../outside"]))
        self.assert_problem(self.run_check(), "Unsafe")

    def test_missing_input_never_passes(self):
        self.configure(lambda s: s["inputs"].append("missing-directory"))
        self.assert_problem(self.run_check(), "no source files")

    def test_external_symlinks_fail_explicitly(self):
        (self.repo / "shortcut.py").symlink_to("../outside.py")
        self.assert_problem(self.run_check(), "Symlink target escapes")

    def test_evidence_detects_dependency_scope_base_and_artifact_changes(self):
        self.assertEqual(self.run_check()["status"], "passed")
        evidence = self.out / "evidence.json"
        self.replace("session.py", "30 * 60", "1800")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(self.repo, self.scope, self.base, "worktree", evidence)
        self.git("checkout", "--", "session.py")
        self.configure(lambda s: s.update(name="different-policy"))
        with self.assertRaisesRegex(CheckError, "Scope differs"):
            verify(self.repo, self.scope, self.base, "worktree", evidence)
        shutil.copyfile(self.repo / "scope.json", self.scope)
        self.replace("session.py", "30 * 60", "1800")
        self.commit()
        with self.assertRaisesRegex(CheckError, "Base differs"):
            verify(self.repo, self.scope, "HEAD", "HEAD", evidence)
        (self.out / "tests.xml").write_text("damaged")
        with self.assertRaisesRegex(CheckError, "artifact missing or changed"):
            verify(self.repo, self.scope, self.base, "HEAD", evidence)

    def test_git_export_ignore_does_not_omit_source(self):
        (self.repo / ".gitattributes").write_text("session.py export-ignore\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check(candidate_ref="HEAD")
        self.assertEqual(result["status"], "passed", result)
        self.assertTrue(
            any(f["path"] == "session.py" for f in read_json(self.out / "candidate-manifest.json"))
        )

    def test_verify_rejects_incomplete_outcome_record(self):
        result = self.run_check()
        self.assertEqual(result["status"], "passed")
        for field in ("tests", "trace", "oft", "runner", "review"):
            with self.subTest(field=field):
                incomplete = {key: value for key, value in result.items() if key != field}
                write_json(self.out / "evidence.json", statement(incomplete))
                with self.assertRaisesRegex(CheckError, "incomplete or malformed"):
                    verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")

    def test_input_overlap_does_not_duplicate_import(self):
        self.configure(lambda s: s.update(inputs=[".", "requirements.md", "tests"]))
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)

    def test_cli_exit_codes_and_output_location(self):
        args = [
            "check",
            "--repo",
            str(self.repo),
            "--scope",
            str(self.scope),
            "--base",
            self.base,
            "--candidate",
            "worktree",
            "--oft-jar",
            str(self.jar),
        ]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args + ["--out", str(self.root / "cli-pass")]), 0)
            self.replace("session.py", "30 * 60", "0")
            self.assertEqual(main(args + ["--out", str(self.root / "cli-reject")]), 1)
            self.assertEqual(main(args + ["--out", str(self.repo / "evidence")]), 2)
        self.assertFalse((self.repo / "evidence").exists())


if __name__ == "__main__":
    unittest.main()
