import difflib

from .common import canonical, digest, within
from .snapshot import read_entry


def review_diff(base, candidate, changed):
    chunks = []
    for change in changed:
        if change["kind"] != "file":
            continue
        path = change["path"]
        left = (
            read_entry(base.root, path)[1].decode(errors="replace").splitlines(keepends=True)
            if change["before"]
            else []
        )
        right = (
            read_entry(candidate.root, path)[1].decode(errors="replace").splitlines(keepends=True)
            if change["after"]
            else []
        )
        chunks.extend(
            difflib.unified_diff(left, right, fromfile=f"base/{path}", tofile=f"candidate/{path}")
        )
    return "".join(chunks)


def changes(base, candidate, before, after, scope):
    result = []
    old = {item["key"]: item for item in before}
    new = {item["key"]: item for item in after}
    for key in sorted(old.keys() | new.keys()):
        left, right = old.get(key), new.get(key)

        # Location-only moves remain visible through file changes below.
        def meaning(item):
            return {k: item[k] for k in ("id", "revision", "content")} if item else None

        if meaning(left) != meaning(right):
            result.append({"kind": "requirement", "key": key, "before": left, "after": right})
    left = {f["path"]: f for f in base.manifest}
    right = {f["path"]: f for f in candidate.manifest}
    roots = scope["specification_paths"] + scope["test_paths"]
    for path in sorted(left.keys() | right.keys()):
        if within(path, roots) and left.get(path) != right.get(path):
            result.append(
                {"kind": "file", "path": path, "before": left.get(path), "after": right.get(path)}
            )
    return result


def revision_diagnostics(changed, scope):
    if not scope.get("policy", {}).get("require_revision_increase", False):
        return []
    result = []
    for change in changed:
        if change["kind"] != "requirement":
            continue
        old, new = change["before"], change["after"]
        if old and new:
            if new["revision"] < old["revision"]:
                result.append(f"{change['key']}: requirement revision must not decrease")
            elif new["content"] != old["content"] and new["revision"] <= old["revision"]:
                result.append(
                    f"{change['key']}: changed requirement content needs a revision increase and reviewed references"
                )
    return result


def review_record(base, candidate, scope_sha256, changed):
    return {
        "schema_version": 1,
        "base_commit": base.commit,
        "base_sha256": base.sha256,
        "candidate_sha256": candidate.sha256,
        "scope_sha256": scope_sha256,
        "changes_sha256": digest(canonical(changed)),
        "changes": changed,
    }
