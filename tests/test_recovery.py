"""Recover real OFT baselines from unannotated source and run their actual tests."""

import contextlib
import io
import shutil
import subprocess
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from intentbond.cli import main
from intentbond.common import CheckError, read_json, write_json
from intentbond.oft import default_jar, import_items, validate_jar
from intentbond.recovery import check_recovery, claims_path, prepare
from intentbond.runner import check

FIXTURE = Path(__file__).resolve().parents[1] / "examples/session"


class RecoveryFixture(unittest.TestCase):
    isolated = True

    @classmethod
    def setUpClass(cls):
        cls.jar = default_jar().resolve()
        validate_jar(cls.jar)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ib-recovery-acceptance-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "legacy project"
        shutil.copytree(FIXTURE, self.repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for path in [self.repo / "session.py", self.repo / "tests/test_session.py"]:
            path.write_text(
                "".join(
                    line
                    for line in path.read_text().splitlines(keepends=True)
                    if "->req~" not in line
                )
            )
        (self.repo / "scope.json").unlink()
        (self.repo / "requirements.md").unlink()
        (self.repo / "README.md").write_text(
            "# Sessions\n\nSessions expire after 30 minutes of inactivity.\n"
        )
        self.git("init", "-q", "-b", "main")
        self.commit()
        self.source_commit = self.git("rev-parse", "HEAD").strip()
        self.bundle = self.root / "recovery"
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
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Fixture",
        )

    def prepare(self, inputs=None):
        self.record = prepare(
            self.repo, "HEAD", inputs or ["."], self.bundle, isolated=self.isolated
        )
        self.claims_file = claims_path(self.bundle, self.record)
        return self.record

    def draft(self, inputs=None):
        self.prepare(inputs)
        for name in ("requirements.md", "scope.json", "session.py", "tests/test_session.py"):
            shutil.copyfile(FIXTURE / name, Path(self.record["workspace"]) / name)
        self.claims = {
            "schema_version": 1,
            "items": [
                {
                    "id": "req~session-expiration~1",
                    "origin": "documented",
                    "notes": "Boundary assertions match the guide.",
                    "sources": [
                        {
                            "path": "README.md",
                            "start_line": 3,
                            "end_line": 3,
                            "quote": "Sessions expire after 30 minutes of inactivity.",
                            "role": "intent",
                        }
                    ],
                }
            ],
            "open_issues": [],
        }
        self.save_claims()

    def save_claims(self):
        write_json(self.claims_file, self.claims)

    def run_check(self, **extra):
        self.counter += 1
        self.out = self.root / f"result-{self.counter}"
        return check_recovery(self.bundle, None, self.out, extra.get("jar", self.jar))


class RecoveryTests(RecoveryFixture):
    def test_schema_one_isolated_bundles_remain_checkable(self):
        self.draft()
        record = read_json(self.bundle / "recovery.json")
        legacy = {
            key: record[key]
            for key in (
                "status",
                "created_at",
                "source",
                "inputs",
                "draft_seed",
                "inventory_sha256",
                "instructions_sha256",
            )
        }
        write_json(self.bundle / "recovery.json", {"schema_version": 1, **legacy})
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertTrue((self.out / "proposed").is_dir())

    def test_malformed_bundle_still_produces_an_error_report(self):
        self.draft()
        write_json(self.bundle / "recovery.json", [])
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertTrue((self.out / "recovery-result.json").exists())

    def test_prepare_preserves_source_and_records_inventory_without_tests(self):
        before = self.git("status", "--porcelain")
        record = self.prepare(["README.md", "session.py", "tests"])
        self.assertEqual(record["source"]["commit"], self.source_commit)
        self.assertEqual(self.git("status", "--porcelain"), before)
        self.assertEqual(read_json(self.bundle / "claims.json")["items"], [])
        self.assertEqual(
            {entry["path"] for entry in read_json(self.bundle / "inventory.json")},
            {"README.md", "session.py", "tests/test_session.py"},
        )
        self.assertFalse((self.bundle / "source/test-results.xml").exists())
        self.assertFalse((self.bundle / "draft/requirements.md").exists())
        self.assertTrue((self.bundle / "draft/.git").is_dir())
        semantics = (
            files("intentbond")
            .joinpath("skills/intentbond/references/semantics.md")
            .read_text(encoding="utf-8")
        )
        self.assertIn(semantics, (self.bundle / "instructions.md").read_text(encoding="utf-8"))
        property_directory = files("intentbond") / "skills/property-testing"
        instructions = (self.bundle / "instructions.md").read_text(encoding="utf-8")
        self.assertEqual(
            instructions.count((property_directory / "SKILL.md").read_text(encoding="utf-8")),
            1,
        )
        for reference in (property_directory / "references").iterdir():
            self.assertNotIn(reference.read_text(encoding="utf-8"), instructions)

    def test_real_baseline_recovery_patch_and_adoption_then_normal_development(self):
        self.draft()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["review"], "required")
        self.assertEqual(result["source"]["commit"], self.source_commit)
        checked = read_json(self.out / "check/evidence.json")["predicate"]
        self.assertEqual(checked["tests"]["status"], "passed")
        self.assertEqual(checked["candidate"]["sha256"], result["candidate"]["sha256"])
        self.assertEqual(checked["tests"]["counts"]["total"], 1)
        provenance = read_json(self.out / "provenance.json")
        self.assertTrue(provenance["items"][0]["sources"][0]["source_sha256"])
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse((self.repo / "requirements.md").exists())
        # Simulate the caller accepting this fixture's proposed baseline.
        self.git("apply", "--check", str(self.out / "proposal.patch"))
        self.git("apply", str(self.out / "proposal.patch"))
        self.commit()
        baseline = self.git("rev-parse", "HEAD").strip()
        adopted = check(self.repo, None, baseline, baseline, self.root / "adopted", self.jar)
        self.assertEqual(adopted["status"], "passed", adopted)
        path = self.repo / "session.py"
        path.write_text(path.read_text().replace("30 * 60", "1800"))
        subsequent = check(
            self.repo, None, baseline, "worktree", self.root / "subsequent", self.jar
        )
        self.assertEqual(subsequent["status"], "passed", subsequent)

    def test_citations_cannot_be_invented_or_self_supporting(self):
        self.draft()
        self.claims["items"][0]["sources"][0]["quote"] = "Sessions last forever."
        self.save_claims()
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("quote does not match", " ".join(result["diagnostics"]))
        self.claims["items"][0]["sources"][0]["path"] = "requirements.md"
        self.save_claims()
        result = self.run_check()
        self.assertIn("outside inventoried text", " ".join(result["diagnostics"]))

    def test_module_annotations_are_accepted_and_imported_by_oft(self):
        # Exercise the editing boundary and the real OFT importer for common
        # JavaScript module extensions, without adding a runtime dependency to the suite.
        modules = self.repo / "modules"
        modules.mkdir()
        names = {}
        for suffix in (".mjs", ".cjs"):
            esm = suffix == ".mjs"
            implementation = (
                "export const timeout = 1800;\n" if esm else "exports.timeout = 1800;\n"
            )
            test = (
                f"import {{ timeout }} from './session{suffix}';\n"
                if esm
                else f"const {{ timeout }} = require('./session{suffix}');\n"
            ) + "if (timeout !== 1800) throw new Error('Wrong timeout');\n"
            for stem, kind, content in (
                ("session", "impl", implementation),
                ("test_session", "utest", test),
            ):
                name = f"modules/{stem}{suffix}"
                (self.repo / name).write_text(content)
                names[name] = kind
        self.commit()
        self.draft()
        for name, kind in names.items():
            path = self.bundle / "draft" / name
            path.write_text(f"// [{kind}->req~session-expiration~1]\n" + path.read_text())
        scope = read_json(self.bundle / "draft/scope.json")
        scope["inputs"].append("modules")
        scope["test_paths"].extend(name for name, kind in names.items() if kind == "utest")
        write_json(self.bundle / "draft/scope.json", scope)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["check_status"], "passed", result)
        imported = import_items(self.out / "check/candidate-items.xml", self.bundle / "draft")
        self.assertTrue(set(names).issubset({item["path"] for item in imported}), imported)

    def test_existing_specification_can_receive_draft_metadata_with_original_citations(self):
        original = (
            "".join(
                line
                for line in (FIXTURE / "requirements.md").read_text().splitlines(keepends=True)
                if not line.startswith(("`req~", "Needs:"))
            ).rstrip()
            + "\n"
        )
        (self.repo / "requirements.md").write_text(original)
        self.commit()
        self.draft()
        path = self.bundle / "draft/requirements.md"
        path.write_text(
            path.read_text().replace(
                "`req~session-expiration~1`", "`req~session-expiration~1`\nStatus: draft"
            )
        )
        lines = original.splitlines()
        start = lines.index(
            "A session expires when its inactivity reaches 30 minutes. A session with less"
        )
        self.claims["items"][0]["sources"] = [
            {
                "path": "requirements.md",
                "start_line": start + 1,
                "end_line": start + 2,
                "quote": "\n".join(lines[start : start + 2]),
                "role": "intent",
            }
        ]
        self.save_claims()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual((self.bundle / "source/requirements.md").read_text(), original)
        self.assertEqual((self.repo / "requirements.md").read_text(), original)
        source = read_json(self.out / "provenance.json")["items"][0]["sources"][0]
        self.assertEqual(source["quote"], self.claims["items"][0]["sources"][0]["quote"])
        self.git("apply", "--check", str(self.out / "proposal.patch"))
        # Approval metadata is not covered by the draft-only addition exception.
        path.write_text(path.read_text().replace("Status: draft", "Status: approved"))
        result = self.run_check()
        self.assertIn("Missing document change review", " ".join(result["diagnostics"]))

    def test_metadata_additions_require_selected_specification_path(self):
        self.draft()
        path = self.bundle / "draft/README.md"
        path.write_text(path.read_text() + "\n`req~other~1`\nNeeds: impl, utest\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("README.md", " ".join(result["diagnostics"]))
        self.assertNotIn("check_status", result)

    def test_metadata_additions_require_inventoried_source(self):
        (self.repo / "requirements.md").write_text("# Session expiration\n")
        self.commit()
        self.draft(inputs=["README.md", "session.py", "tests"])
        path = self.bundle / "draft/requirements.md"
        path.write_text("# Session expiration\n`req~session-expiration~1`\nNeeds: impl, utest\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("requirements.md", " ".join(result["diagnostics"]))
        self.assertNotIn("check_status", result)

    def test_missing_provenance_and_duplicate_claims_fail(self):
        self.draft()
        item = self.claims["items"].pop()
        self.save_claims()
        result = self.run_check()
        self.assertIn("Missing claim provenance", " ".join(result["diagnostics"]))
        self.claims["items"] = [item, item]
        self.save_claims()
        result = self.run_check()
        self.assertIn("duplicate claim", " ".join(result["diagnostics"]))

    def test_inferred_intent_and_open_contradiction_never_auto_approve(self):
        self.draft()
        self.claims["items"][0]["origin"] = "inferred"
        self.claims["open_issues"] = [
            {
                "description": "Confirm that this historical behavior remains desired.",
                "items": ["req~session-expiration~1"],
                "sources": [],
            }
        ]
        self.save_claims()
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["open_issue_count"], 1)
        self.assertEqual(
            read_json(self.out / "provenance.json")["open_issues"], self.claims["open_issues"]
        )

    def test_logic_or_document_changes_are_not_hidden_by_recovery(self):
        self.draft()
        for name, content in [
            ("session.py", "def expired(value):\n    return True\n"),
            ("README.md", "Changed promise\n"),
        ]:
            with self.subTest(path=name):
                path = self.bundle / "draft" / name
                original = path.read_bytes()
                path.write_text(content)
                result = self.run_check()
                self.assertEqual(result["status"], "rejected", result)
                self.assertIn("beyond OFT annotation changes", " ".join(result["diagnostics"]))
                self.assertFalse((self.out / "check/tests.log").exists())
                path.write_bytes(original)

    def test_new_tests_cannot_manufacture_existing_evidence(self):
        self.draft()
        (self.bundle / "draft/tests/test_new.py").write_text("assert True\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("non-specification", " ".join(result["diagnostics"]))

    def test_missing_link_and_existing_test_failure_stay_failures(self):
        self.draft()
        shutil.copyfile(self.bundle / "source/session.py", self.bundle / "draft/session.py")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertNotEqual(result["check_status"], "passed")

    def test_existing_failing_suite_is_not_repaired_by_recovery(self):
        path = self.repo / "session.py"
        path.write_text(path.read_text().replace("30 * 60", "60 * 60"))
        self.commit()
        self.draft()
        path = self.bundle / "draft/session.py"
        path.write_text(path.read_text().replace("30 * 60", "60 * 60"))
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertEqual(
            read_json(self.out / "check/evidence.json")["predicate"]["tests"]["status"], "failed"
        )

    def test_source_tampering_and_missing_engine_fail(self):
        self.draft()
        result = self.run_check(jar=self.root / "absent.jar")
        self.assertEqual(result["status"], "error", result)
        (self.bundle / "source/README.md").write_text("Tampered source\n")
        result = self.run_check()
        self.assertIn("Captured recovery source changed", " ".join(result["diagnostics"]))

    def test_input_and_output_boundaries(self):
        with self.assertRaisesRegex(CheckError, "outside"):
            prepare(self.repo, "HEAD", ["."], self.repo / "recovery")
        with self.assertRaisesRegex(CheckError, "Unsafe"):
            prepare(self.repo, "HEAD", ["../outside"], self.bundle)
        with self.assertRaisesRegex(CheckError, "no source files"):
            prepare(self.repo, "HEAD", ["missing"], self.bundle)

    def test_cli_prepare_and_check_leave_review_pending(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(
                ["recover", "--isolated", "--repo", str(self.repo), "--out", str(self.bundle)]
            )
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertIn("prepared:", stdout.getvalue())
        for name in ("requirements.md", "scope.json", "session.py", "tests/test_session.py"):
            shutil.copyfile(FIXTURE / name, self.bundle / "draft" / name)
        write_json(
            self.bundle / "claims.json", {"schema_version": 1, "items": [], "open_issues": []}
        )
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(
                [
                    "recover-check",
                    "--recovery",
                    str(self.bundle),
                    "--oft-jar",
                    str(self.jar),
                    "--out",
                    str(self.root / "cli-result"),
                ]
            )
        self.assertEqual(code, 2, (stdout.getvalue(), stderr.getvalue()))

    def test_concurrent_draft_edit_invalidates_result(self):
        self.draft()
        from intentbond.runner import check as real_check

        def edit_after_check(*args, **kwargs):
            result = real_check(*args, **kwargs)
            (self.bundle / "draft/requirements.md").write_text("Changed during validation\n")
            return result

        with patch("intentbond.recovery.check", side_effect=edit_after_check):
            result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("Draft changed during validation", " ".join(result["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
