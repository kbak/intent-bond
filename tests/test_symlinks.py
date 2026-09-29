"""Links retain Git identity without importing aliases or losing recovery evidence."""

import os
from pathlib import Path

from test_recovery import RecoveryFixture
from test_workflow import WorkflowFixture

from intentbond.common import CheckError, digest, read_json, write_json, xml_tree
from intentbond.oft import export_items
from intentbond.recovery import read_bundle
from intentbond.review import changes, review_diff
from intentbond.runner import verify
from intentbond.snapshot import archive_snapshot, changed_source, snapshot


def add_links(repo):
    links = {
        "alias.py": "session.py",
        "guide.md": "README.md",
        "linked-tests": "tests",
        "dangling": "absent.txt",
        "chain": "alias.py",
        "tests/parent-link": "../session.py",
    }
    for name, target in links.items():
        (repo / name).symlink_to(target)
    return links


class SymlinkWorkflowTests(WorkflowFixture):
    def test_snapshots_preserve_link_bytes_and_modes_including_dangling_links(self):
        links = add_links(self.repo)
        self.commit()
        committed = snapshot(self.repo, "HEAD", self.root / "committed")
        working = snapshot(self.repo, "worktree", self.root / "working")
        archived = archive_snapshot(committed.root, committed.commit, self.root / "archive")
        # [utest->req~ib-safe-symlinks~1]
        self.assertEqual(committed.manifest, working.manifest)
        self.assertEqual(committed.manifest, archived.manifest)
        for snap in (committed, working, archived):
            self.assertEqual(changed_source(snap), [])
            entries = {e["path"]: e for e in snap.manifest}
            for name, target in links.items():
                self.assertEqual(os.readlink(snap.root / name), target)
                self.assertEqual(entries[name]["mode"], "120000")
                self.assertEqual(entries[name]["sha256"], digest(os.fsencode(target)))
        (working.root / "alias.py").unlink()
        (working.root / "alias.py").symlink_to("README.md")
        self.assertEqual(changed_source(working), ["alias.py"])
        # Replacing a link with identical target bytes is still a mode change.
        (working.root / "alias.py").unlink()
        (working.root / "alias.py").write_text("session.py")
        self.assertEqual(changed_source(working), ["alias.py"])

    def test_unsafe_and_cyclic_links_fail_in_commit_and_worktree_snapshots(self):
        link = self.repo / "alias"
        for index, target in enumerate(
            ("../outside", str(self.repo / "session.py"), ".git/config", "alias", "cycle")
        ):
            with self.subTest(target=target):
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(target)
                if target == "cycle":
                    (self.repo / "cycle").symlink_to("alias")
                self.commit()
                for selection in ("HEAD", "worktree"):
                    # [utest->req~ib-safe-symlinks~1]
                    with self.assertRaisesRegex(CheckError, "[Ss]ymlink"):
                        snapshot(self.repo, selection, self.root / f"unsafe-{index}-{selection}")

    def test_symlink_parents_do_not_substitute_tracked_contents(self):
        (self.repo / "tests").rename(self.repo / "other-tests")
        (self.repo / "tests").symlink_to("other-tests")
        with self.assertRaisesRegex(CheckError, "symlink parent"):
            snapshot(self.repo, "worktree", self.root / "unsafe-parent")

    def test_checks_run_with_links_but_trace_each_actual_file_once(self):
        add_links(self.repo)
        runner = self.repo / "run_tests.py"
        runner.write_text(
            "from pathlib import Path\n"
            "assert Path('alias.py').is_symlink()\n"
            "assert Path('alias.py').read_bytes() == Path('session.py').read_bytes()\n"
            "assert Path('linked-tests/test_session.py').is_file()\n"
            "assert Path('dangling').is_symlink()\n" + runner.read_text()
        )
        self.configure(lambda scope: scope.update(inputs=["."]))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        result = self.run_check()
        # [utest->req~ib-safe-symlinks~1]
        self.assertEqual(result["status"], "passed", result)
        items = read_json(self.out / "evidence.json")["predicate"]["requirements"]["candidate"]
        self.assertEqual(len(items), 1)
        evidence = self.out / "evidence.json"
        self.assertEqual(
            verify(self.repo, self.scope, self.base, "worktree", evidence)["status"], "matched"
        )
        (self.repo / "alias.py").unlink()
        (self.repo / "alias.py").symlink_to("tests/test_session.py")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(self.repo, self.scope, self.base, "worktree", evidence)

    def test_link_mutation_during_tests_invalidates_evidence(self):
        (self.repo / "alias").symlink_to("session.py")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.configure(
            lambda scope: scope.update(
                tests={
                    "format": "command",
                    "command": [
                        "python3",
                        "-c",
                        "from pathlib import Path; p = Path('alias'); p.unlink(); p.symlink_to('README.md')",
                    ],
                    "timeout_seconds": 30,
                }
            )
        )
        result = self.run_check()
        self.assert_problem(result, "alias")
        self.assertEqual(os.readlink(self.repo / "alias"), "session.py")

    def test_explicit_alias_input_requests_the_actual_path(self):
        (self.repo / "alias.py").symlink_to("session.py")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        self.configure(lambda scope: scope["inputs"].append("alias.py"))
        # [utest->req~ib-safe-symlinks~1]
        self.assert_problem(self.run_check(), "actual source path instead of symlink")

    def test_adding_aliases_does_not_change_imported_artifact_ids(self):
        before = snapshot(self.repo, "HEAD", self.root / "before")
        add_links(self.repo)
        after = snapshot(self.repo, "worktree", self.root / "after")
        old = export_items(before, ["."], self.jar, "java", self.root, "before")[0]
        new = export_items(after, ["."], self.jar, "java", self.root, "after")[0]
        self.assertEqual({i["id"] for i in old}, {i["id"] for i in new})

    def test_review_diff_shows_retargeting_instead_of_referent_contents(self):
        link = self.repo / "guide.md"
        link.symlink_to("README.md")
        self.commit()
        before = snapshot(self.repo, "HEAD", self.root / "before")
        link.unlink()
        link.symlink_to("requirements.md")
        after = snapshot(self.repo, "worktree", self.root / "after")
        scope = {"specification_paths": ["guide.md"], "test_paths": []}
        patch = review_diff(before, after, changes(before, after, [], [], scope))
        self.assertIn("-README.md", patch)
        self.assertIn("+requirements.md", patch)
        self.assertNotIn("Needs:", patch)


class RecoverySymlinkFixture(RecoveryFixture):
    def linked_draft(self):
        links = add_links(self.repo)
        self.commit()
        self.draft()
        workspace = Path(self.record["workspace"])
        scope = read_json(workspace / "scope.json")
        scope["inputs"] = ["."]
        scope["specification_paths"].extend(["README.md", "guide.md"])
        write_json(workspace / "scope.json", scope)
        return workspace, links


class RecoverySymlinkTests(RecoverySymlinkFixture):
    def test_recovery_preserves_links_and_uses_canonical_citation_and_trace_paths(self):
        workspace, links = self.linked_draft()
        inventory = {e["path"]: e for e in read_json(self.bundle / "inventory.json")}
        for name, target in links.items():
            self.assertEqual(inventory[name]["target"], target)
            self.assertFalse(inventory[name]["text"])
            self.assertEqual(os.readlink(workspace / name), target)
            self.assertEqual(os.readlink(self.bundle / "source" / name), target)
        result = self.run_check()
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["proposal_checks"], "passed")
        if self.isolated:
            for name, target in links.items():
                self.assertEqual(os.readlink(self.out / "proposed" / name), target)
                self.assertEqual(
                    result["artifacts"][f"proposed/{name}"], digest(os.fsencode(target))
                )
        # OFT's generated IDs must not multiply through file/directory aliases.
        tree = xml_tree(self.out / "check/candidate-items.xml")
        self.assertEqual(len(tree.findall(".//specobject")), 3)

    def test_recovery_rejects_link_retargeting_even_for_specification_alias(self):
        workspace, _ = self.linked_draft()
        (workspace / "guide.md").unlink()
        (workspace / "guide.md").symlink_to("requirements.md")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertIn("preserve existing symlink: guide.md", " ".join(result["diagnostics"]))

    def test_original_link_target_remains_immutable(self):
        self.linked_draft()
        source = self.bundle / "source/guide.md"
        source.unlink()
        source.symlink_to("session.py")
        with self.assertRaisesRegex(CheckError, "Captured recovery source changed: guide.md"):
            read_bundle(self.bundle)

    def test_citations_cannot_hash_a_link_but_quote_its_referent(self):
        self.linked_draft()
        self.claims["items"][0]["sources"][0]["path"] = "guide.md"
        self.save_claims()
        result = self.run_check()
        self.assertEqual(result["status"], "error", result)
        self.assertIn("outside inventoried text sources: guide.md", " ".join(result["diagnostics"]))


class InPlaceRecoverySymlinkTests(RecoverySymlinkFixture):
    # Exercise checkout link handling in both modes; immutable-source and
    # citation validation use the same captured bundle in either mode.
    isolated = False
    test_recovery_preserves_links_and_uses_canonical_citation_and_trace_paths = RecoverySymlinkTests.test_recovery_preserves_links_and_uses_canonical_citation_and_trace_paths
    test_recovery_rejects_link_retargeting_even_for_specification_alias = (
        RecoverySymlinkTests.test_recovery_rejects_link_retargeting_even_for_specification_alias
    )
