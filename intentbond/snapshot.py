import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import CheckError, canonical, digest, relative_path


def git(repo, *args, data=None):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            input=data,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckError(f"Cannot run Git: {exc}") from exc
    if result.returncode:
        raise CheckError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def repository(path):
    repo = path.resolve(strict=True)
    root = Path(os.fsdecode(git(repo, "rev-parse", "--show-toplevel")).strip()).resolve()
    if repo != root:
        raise CheckError(f"--repo must name the Git repository root: {root}")
    return repo


def resolve_commit(repo, ref):
    return (
        git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    )


@dataclass
class Snapshot:
    root: Path
    commit: str
    kind: str
    manifest: list

    @property
    def sha256(self):
        return digest(canonical(self.manifest))

    def identity(self):
        return {
            "kind": self.kind,
            "commit": self.commit,
            "sha256": self.sha256,
            "file_count": len(self.manifest),
        }


def source_path(root, name):
    relative_path(name)
    path = root / name
    if any(p.is_symlink() for p in path.parents if p != root and p.is_relative_to(root)):
        raise CheckError(f"Source path has a symlink parent: {name}")
    return path


def read_entry(root, name):
    """Read Git entry bytes: a symlink's content is its target, never the referent."""
    path = source_path(root, name)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return "120000", os.fsencode(os.readlink(path))
    if not stat.S_ISREG(info.st_mode):
        raise CheckError(f"Expected a regular source file or symlink: {name}")
    return "100755" if info.st_mode & stat.S_IXUSR else "100644", path.read_bytes()


def validate_symlinks(root, manifest):
    """Keep links portable and confined to captured source, including dangling links."""
    for entry in manifest:
        if entry["mode"] != "120000":
            continue
        name = entry["path"]
        path = source_path(root, name)
        target = os.readlink(path)
        if os.path.isabs(target) or "\\" in target or ".git" in Path(target).parts:
            raise CheckError(f"Symlink must use a relative target outside Git metadata: {name}")
        try:
            try:
                resolved = path.resolve(strict=True)
            except FileNotFoundError:
                resolved = path.resolve()
        except (OSError, RuntimeError) as exc:
            raise CheckError(f"Cannot resolve symlink (possibly cyclic): {name}") from exc
        if not resolved.is_relative_to(root) or ".git" in resolved.relative_to(root).parts:
            raise CheckError(
                f"Symlink target escapes captured source or enters Git metadata: {name}"
            )


def put_file(root, name, mode, data):
    if mode not in ("100644", "100755", "120000"):
        raise CheckError(f"Unsupported Git entry {name} ({mode}); submodules are not supported")
    target = source_path(root, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or (mode == "120000" and target.exists()):
        target.unlink()
    if mode == "120000":
        target.symlink_to(os.fsdecode(data))
    else:
        target.write_bytes(data)
        target.chmod(0o755 if mode == "100755" else 0o644)
    return {"path": name, "mode": mode, "sha256": digest(data)}


def worktree_entries(repo):
    index = git(repo, "ls-files", "--stage", "-z").split(b"\0")
    for entry in filter(None, index):
        metadata, name = entry.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if stage != b"0":
            raise CheckError("Resolve Git merge conflicts before checking")
        if mode not in (b"100644", b"100755", b"120000"):
            raise CheckError(f"Unsupported Git entry: {os.fsdecode(name)} ({mode.decode()})")
    names = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    entries = []
    for name in sorted(set(filter(None, names.split(b"\0")))):
        relative = os.fsdecode(name)
        try:
            mode, data = read_entry(repo, relative)
        except FileNotFoundError:
            continue  # A tracked deletion is represented by absence from the snapshot.
        entries.append((relative, mode, data))
    return entries


def snapshot(repo, selection, destination):
    destination.mkdir()
    commit = resolve_commit(repo, "HEAD" if selection == "worktree" else selection)
    if selection == "worktree":
        entries = worktree_entries(repo)
    else:
        records = []
        for record in filter(None, git(repo, "ls-tree", "-rz", "--full-tree", commit).split(b"\0")):
            header, name = record.split(b"\t", 1)
            mode, kind, oid = header.split()
            if kind != b"blob" or mode not in (b"100644", b"100755", b"120000"):
                raise CheckError(f"Unsupported Git entry: {os.fsdecode(name)} ({mode.decode()})")
            records.append((os.fsdecode(name), mode.decode(), oid))
        # Read Git objects, not git archive: export-ignore/export-subst must not change checked bytes.
        blobs = git(
            repo, "cat-file", "--batch", data=b"".join(oid + b"\n" for _, _, oid in records)
        )
        entries = []
        offset = 0
        for name, mode, oid in records:
            end = blobs.index(b"\n", offset)
            actual_oid, kind, length = blobs[offset:end].split()
            size = int(length)
            if actual_oid != oid or kind != b"blob":
                raise CheckError("Unexpected Git object response")
            entries.append((name, mode, blobs[end + 1 : end + 1 + size]))
            offset = end + size + 2
    manifest = sorted((put_file(destination, *entry) for entry in entries), key=lambda f: f["path"])
    validate_symlinks(destination, manifest)
    return Snapshot(
        destination, commit, "worktree" if selection == "worktree" else "commit", manifest
    )


def changed_source(snap):
    changed = []
    for entry in snap.manifest:
        try:
            mode, data = read_entry(snap.root, entry["path"])
            if digest(data) != entry["sha256"] or mode != entry["mode"]:
                changed.append(entry["path"])
        except (CheckError, OSError):
            changed.append(entry["path"])
    return changed


def archive_snapshot(source, commit, destination):
    """Capture a caller-supplied source archive; commit attribution is external."""
    source = source.resolve(strict=True)
    destination.mkdir()
    manifest = []
    for parent, directories, names in os.walk(source):
        directories[:] = [name for name in directories if name != ".git"]
        links = [name for name in directories if (Path(parent) / name).is_symlink()]
        directories[:] = [name for name in directories if name not in links]
        for name in names + links:
            if name == ".git":
                continue
            path = Path(parent) / name
            relative = path.relative_to(source).as_posix()
            mode, data = read_entry(source, relative)
            manifest.append(put_file(destination, relative, mode, data))
    validate_symlinks(destination, manifest)
    return Snapshot(
        destination, commit, "archive", sorted(manifest, key=lambda entry: entry["path"])
    )
