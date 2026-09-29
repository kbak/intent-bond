"""Sequential source/evidence lifecycle properties using real Git, OFT and tests.

The reference model stores raw bytes and executable bits, not ib digests. Search
is bounded to a tiny valid project and sequential operations. No concurrency,
external dependencies, malicious reporters or semantic requirement inference is
modeled.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from intentbond.common import CheckError, read_json, write_json
from intentbond.oft import default_jar, validate_jar
from intentbond.runner import check, verify
from intentbond.snapshot import git, snapshot

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/session"
EXTRA_PATHS = st.sampled_from(["notes/a.bin", "notes/b.bin", "notes/space name.bin"])


class EvidenceLifecycle(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.directory = tempfile.TemporaryDirectory(prefix="ib-lifecycle-property-")
        try:
            self.root = Path(self.directory.name)
            self.repo = self.root / "repo"
            shutil.copytree(
                EXAMPLE, self.repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
            (self.repo / ".gitignore").write_text("cache/\n")
            scope = read_json(self.repo / "scope.json")
            scope["tests"]["command"][0] = sys.executable
            scope["policy"] = {"require_revision_increase": True}
            write_json(self.repo / "scope.json", scope)
            self.scope = self.root / "trusted-scope.json"
            write_json(self.scope, scope)
            self.model = {}
            for path in self.repo.rglob("*"):
                if path.is_file():
                    path.chmod(0o644)
                    self.model[path.relative_to(self.repo).as_posix()] = (path.read_bytes(), 0o644)
            git(self.repo, "init", "-q")
            git(self.repo, "config", "core.filemode", "true")
            self.commit()
            self.base = git(self.repo, "rev-parse", "HEAD").decode().strip()
            self.original = self.model.copy()
            self.jar = default_jar().resolve()
            validate_jar(self.jar)
            self.sequence = 0
            self.checks = 0
            self.fresh_check()
        except BaseException:
            self.directory.cleanup()
            raise

    def teardown(self):
        self.directory.cleanup()

    def destination(self, label):
        self.sequence += 1
        return self.root / f"{self.sequence}-{label}"

    def put(self, name, data, mode=0o644):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        self.model[name] = (data, mode)

    @rule(name=EXTRA_PATHS, data=st.binary(max_size=32))
    def edit(self, name, data):
        self.put(name, data, self.model.get(name, (b"", 0o644))[1])

    @rule(name=EXTRA_PATHS)
    def delete(self, name):
        if name in self.model:
            (self.repo / name).unlink()
            del self.model[name]

    @rule(source=EXTRA_PATHS, destination=EXTRA_PATHS)
    def rename(self, source, destination):
        if source in self.model and source != destination:
            (self.repo / source).replace(self.repo / destination)
            self.model[destination] = self.model.pop(source)

    @rule(name=EXTRA_PATHS)
    def change_mode(self, name):
        if name in self.model:
            data, mode = self.model[name]
            self.put(name, data, mode ^ 0o111)

    @rule()
    def stage(self):
        git(self.repo, "add", "-A")

    @rule()
    def commit(self):
        self.stage()
        git(
            self.repo,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Lifecycle fixture",
            "--allow-empty",
        )

    @rule(data=st.binary(max_size=32))
    def ignored_noise(self, data):
        cache = self.repo / "cache"
        cache.mkdir(exist_ok=True)
        (cache / "runtime.bin").write_bytes(data)

    @rule()
    def touch(self):
        for name in self.model:
            os.utime(self.repo / name, (1, 1))

    @rule(increase=st.integers(1, 3))
    def revise_and_retarget(self, increase):
        # Preserve meaning while advancing the same requirement and all its references.
        name = "requirements.md"
        prose = self.model[name][0].decode()
        revision = int(prose.split("req~session-expiration~", 1)[1].split("`", 1)[0])
        old, new = (f"req~session-expiration~{n}" for n in (revision, revision + increase))
        for path in (name, "session.py", "tests/test_session.py"):
            data, mode = self.model[path]
            self.put(path, data.replace(old.encode(), new.encode()), mode)

    @rule()
    def restore_checked_contents(self):
        for name in self.model.keys() - self.checked_model.keys():
            (self.repo / name).unlink()
        self.model = self.checked_model.copy()
        for name, (data, mode) in self.model.items():
            self.put(name, data, mode)

    @precondition(lambda self: self.checks < 2)
    @rule()
    def fresh_check(self):
        self.checks += 1
        self.output = self.destination("check")
        result = check(self.repo, self.scope, self.base, "worktree", self.output, self.jar)
        changed_contract = any(
            self.model[name] != self.original[name]
            for name in ("requirements.md", "tests/test_session.py")
        )
        expected = "review_required" if changed_contract else "passed"
        assert result["status"] == expected, result["diagnostics"]
        self.checked_model = self.model.copy()
        self.checked_digest = result["candidate"]["sha256"]

    @invariant()
    def identity_and_evidence_follow_contents(self):
        current = snapshot(self.repo, "worktree", self.destination("snapshot"))
        captured = {
            item["path"]: (
                (current.root / item["path"]).read_bytes(),
                0o755 if (current.root / item["path"]).stat().st_mode & 0o100 else 0o644,
            )
            for item in current.manifest
        }
        # [utest->req~ib-evidence-verification~1]
        assert captured == self.model
        same_contents = self.model == self.checked_model
        assert (current.sha256 == self.checked_digest) == same_contents
        try:
            result = verify(
                self.repo,
                self.scope,
                self.base,
                "worktree",
                self.output / "evidence.json",
                allow_pending_review=True,
            )
        except CheckError as exc:
            assert not same_contents, str(exc)
            assert "Candidate contents differ" in str(exc), str(exc)
        else:
            assert same_contents, "Changed source was accepted by saved evidence"
            assert result["status"] == "matched"


TestEvidenceLifecycle = EvidenceLifecycle.TestCase
TestEvidenceLifecycle.settings = settings(
    max_examples=12,
    stateful_step_count=12,
    database=None,
    derandomize=True,
    deadline=None,
    print_blob=True,
)


class LifecycleRegressionTests(unittest.TestCase):
    def test_edit_stage_commit_restore_and_revision(self):
        machine = EvidenceLifecycle()
        try:
            machine.edit("notes/a.bin", b"first")
            machine.identity_and_evidence_follow_contents()
            machine.stage()
            machine.commit()
            machine.identity_and_evidence_follow_contents()
            machine.restore_checked_contents()
            machine.ignored_noise(b"runtime data")
            machine.touch()
            machine.identity_and_evidence_follow_contents()
            machine.revise_and_retarget(1)
            machine.identity_and_evidence_follow_contents()
            machine.fresh_check()
            machine.identity_and_evidence_follow_contents()
            machine.edit("notes/a.bin", b"second")
            machine.identity_and_evidence_follow_contents()
            machine.rename("notes/a.bin", "notes/b.bin")
            machine.identity_and_evidence_follow_contents()
            machine.change_mode("notes/b.bin")
            machine.identity_and_evidence_follow_contents()
            machine.delete("notes/b.bin")
            machine.identity_and_evidence_follow_contents()
        finally:
            machine.teardown()
