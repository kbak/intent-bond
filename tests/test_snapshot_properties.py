"""Bounded properties of the source identity contract in docs/contract.md.

Exercise real Git and filesystem captures, including binary data and executable
bits. Symlinks, submodules, checkout filters and concurrent writers are outside
these generators; their existing example tests remain necessary.
"""

import os
import tempfile
import unittest
from pathlib import Path

from hypothesis import example, given, settings
from hypothesis import strategies as st

from intentbond.snapshot import archive_snapshot, git, snapshot

SEARCH = settings(max_examples=30, database=None, derandomize=True, deadline=None, print_blob=True)
FILES = st.dictionaries(
    st.sampled_from(["a.txt", "nested/b.bin", "space dir/c.txt", "unicode-λ.txt"]),
    st.tuples(st.binary(max_size=32), st.booleans()),
    min_size=1,
    max_size=4,
)


def commit(repo):
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "Property fixture",
        "--allow-empty",
    )


class SnapshotPropertyTests(unittest.TestCase):
    @SEARCH
    @example(files={"a.txt": (b"", True)})
    @given(files=FILES)
    def test_git_and_archive_agree_before_and_after_staging(self, files):
        with tempfile.TemporaryDirectory(prefix="ib-snapshot-property-") as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            git(repo, "config", "core.filemode", "true")
            commit(repo)
            for name, (data, executable) in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(0o755 if executable else 0o644)
            untracked = snapshot(repo, "worktree", root / "untracked")
            self.assertEqual({item["path"] for item in untracked.manifest}, set(files))
            git(repo, "add", ".")
            staged = snapshot(repo, "worktree", root / "staged")
            commit(repo)
            committed = snapshot(repo, "HEAD", root / "committed")
            archived = archive_snapshot(repo, committed.commit, root / "archived")
            self.assertEqual(untracked.manifest, committed.manifest)
            self.assertEqual(staged.sha256, committed.sha256)
            self.assertEqual(archived.sha256, committed.sha256)
            for name, (data, executable) in files.items():
                self.assertEqual((committed.root / name).read_bytes(), data)
                self.assertEqual(bool((committed.root / name).stat().st_mode & 0o100), executable)
                os.utime(repo / name, (1, 1))
            touched = snapshot(repo, "worktree", root / "touched")
            self.assertEqual(touched.sha256, committed.sha256)

    @SEARCH
    @example(data=b"", executable=False)
    @given(data=st.binary(max_size=32), executable=st.booleans())
    def test_path_bytes_and_mode_each_change_identity_and_restore_exactly(self, data, executable):
        with tempfile.TemporaryDirectory(prefix="ib-identity-property-") as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            path = repo / "original.bin"
            path.write_bytes(data)
            mode = 0o755 if executable else 0o644
            path.chmod(mode)
            commit(repo)
            baseline = snapshot(repo, "worktree", root / "baseline").sha256
            path.rename(repo / "renamed.bin")
            self.assertNotEqual(snapshot(repo, "worktree", root / "renamed").sha256, baseline)
            (repo / "renamed.bin").rename(path)
            path.write_bytes(data + b"\x00")
            self.assertNotEqual(snapshot(repo, "worktree", root / "edited").sha256, baseline)
            path.write_bytes(data)
            path.chmod(mode ^ 0o111)
            self.assertNotEqual(snapshot(repo, "worktree", root / "chmod").sha256, baseline)
            path.chmod(mode)
            self.assertEqual(snapshot(repo, "worktree", root / "restored").sha256, baseline)

    @SEARCH
    @given(data=st.binary(max_size=32))
    def test_ignored_noise_is_excluded_but_tracked_ignored_source_is_retained(self, data):
        with tempfile.TemporaryDirectory(prefix="ib-ignore-property-") as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init", "-q")
            (repo / ".gitignore").write_text("cache/\n")
            (repo / "cache").mkdir()
            tracked = repo / "cache/tracked.bin"
            tracked.write_bytes(data)
            git(repo, "add", "-f", "cache/tracked.bin")
            commit(repo)
            baseline = snapshot(repo, "worktree", root / "baseline")
            self.assertIn("cache/tracked.bin", {item["path"] for item in baseline.manifest})
            (repo / "cache/runtime.bin").write_bytes(data + b"noise")
            self.assertEqual(snapshot(repo, "worktree", root / "noise").sha256, baseline.sha256)
            tracked.write_bytes(data + b"changed")
            self.assertNotEqual(
                snapshot(repo, "worktree", root / "changed").sha256, baseline.sha256
            )
