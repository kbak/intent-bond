"""Prepare and validate OFT proposals in a clean checkout or an isolated draft."""

import difflib
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from .common import (
    RECOVERY_RECORDS,
    CheckError,
    canonical,
    digest,
    read_json,
    relative_path,
    within,
    write_json,
)
from .config import load_scope
from .oft import export_items, import_items
from .recovery_report import render_review
from .runner import check
from .snapshot import (
    git,
    put_file,
    read_entry,
    repository,
    resolve_commit,
    snapshot,
    validate_symlinks,
    worktree_entries,
)

RECOVERY_SKILL = "skills/recover-baseline"


def initialize(repo, message):
    git(repo, "init", "-q", "--template=", "-b", "recovery")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "core.hooksPath", "/dev/null")
    return commit(repo, message)


def commit(repo, message):
    git(repo, "add", "--force", "--all", "--", ".")
    git(
        repo,
        "-c",
        "user.name=IntentBond",
        "-c",
        "user.email=recovery@example.invalid",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "--allow-empty",
        "-qm",
        message,
    )
    return resolve_commit(repo, "HEAD")


def recovery_storage(repo):
    return (
        Path(git(repo, "rev-parse", "--absolute-git-dir").decode().strip()).resolve()
        / "intentbond"
        / "recovery"
    )


def active_recovery(repo_path):
    repo = repository(repo_path)
    active = recovery_storage(repo) / "active.json"
    if not active.is_file():
        raise CheckError(
            "No active in-place recovery; run ib recover or supply --recovery for an isolated bundle"
        )
    path = Path(read_json(active)["bundle"])
    record, _ = read_bundle(path)
    if record.get("mode") != "in_place" or Path(record["workspace"]).resolve() != repo:
        raise CheckError("Active recovery belongs to another workspace; supply --recovery")
    return path


def workspace_path(directory, record):
    # Schema 1 bundles were always isolated, with claims beside their draft.
    return Path(record["workspace"]) if record.get("mode") == "in_place" else directory / "draft"


def claims_path(directory, record):
    if record.get("mode") == "in_place":
        return workspace_path(directory, record) / record["claims_path"]
    return directory / "claims.json"


def head_ref(repo):
    return git(repo, "rev-parse", "--symbolic-full-name", "HEAD").decode().strip()


def current_manifest(repo):
    return sorted(
        (
            {"path": name, "mode": mode, "sha256": digest(data)}
            for name, mode, data in worktree_entries(repo)
        ),
        key=lambda entry: entry["path"],
    )


def prepare(repo_path, candidate_ref, inputs, out=None, *, isolated=False):
    repo = repository(repo_path)
    start = resolve_commit(repo, "HEAD")
    branch = head_ref(repo)
    if not isolated:
        if git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
            raise CheckError(
                "In-place recovery needs a clean checkout, including staged and untracked files; finish existing work or use --isolated"
            )
        if candidate_ref != "worktree" and resolve_commit(repo, candidate_ref) != start:
            raise CheckError(
                "In-place recovery must start at HEAD; use --isolated for another version"
            )
    run_id = uuid4().hex
    if out is None:
        out = recovery_storage(repo) / "runs" / run_id
    out = out.resolve()
    if out.is_relative_to(repo) and not out.is_relative_to(recovery_storage(repo)):
        raise CheckError(
            "Recovery output must be outside the source repository or in its recovery storage"
        )
    if not inputs or len(set(inputs)) != len(inputs):
        raise CheckError("Recovery inputs must be a nonempty, unique path list")
    for path in inputs:
        relative_path(path)
    out.mkdir(parents=True, exist_ok=False)
    source = snapshot(repo, candidate_ref if isolated else start, out / "source")
    if not isolated and (
        resolve_commit(repo, "HEAD") != start
        or head_ref(repo) != branch
        or current_manifest(repo) != source.manifest
    ):
        raise CheckError(
            "Checkout changed during preparation or differs from HEAD bytes; retry from a clean checkout or use --isolated"
        )
    inventory = []
    for path in inputs:
        if not any(within(entry["path"], [path]) for entry in source.manifest):
            raise CheckError(f"Recovery input has no source files: {path}")
    for entry in source.manifest:
        if not within(entry["path"], inputs):
            continue
        mode, content = read_entry(source.root, entry["path"])
        try:
            text = content.decode("utf-8")
            is_text = mode != "120000" and "\x00" not in text
        except UnicodeDecodeError:
            text, is_text = "", False
        inventory.append(
            {
                **entry,
                "bytes": len(content),
                "text": is_text,
                "lines": len(text.splitlines()) if is_text else None,
                **({"target": os.fsdecode(content)} if mode == "120000" else {}),
            }
        )
    seed = None
    if isolated:
        shutil.copytree(source.root, out / "draft", symlinks=True)
        seed = initialize(
            out / "draft", "Captured source for baseline recovery (not historical intent)"
        )
    (out / "source-manifest.json").write_bytes(canonical(source.manifest))
    write_json(out / "inventory.json", inventory)
    # Carry guidance into the bundle so standalone agents need no package-relative lookup.
    skill = files("intentbond") / RECOVERY_SKILL
    (out / "instructions.md").write_text(
        (skill / "SKILL.md").read_text(encoding="utf-8")
        + "\n\n"
        + (skill / "references/recovery.md").read_text(encoding="utf-8")
        + "\n\n"
        + files("intentbond")
        .joinpath("skills/intentbond/references/semantics.md")
        .read_text(encoding="utf-8")
        + '\n\n<skill-reference path="skills/property-testing/SKILL.md">\n'
        + files("intentbond")
        .joinpath("skills/property-testing/SKILL.md")
        .read_text(encoding="utf-8")
        + "\n</skill-reference>",
        encoding="utf-8",
    )
    record = {
        "schema_version": 2,
        "id": run_id,
        "mode": "isolated" if isolated else "in_place",
        "bundle": str(out),
        "source_repo": str(repo),
        "workspace": str(out / "draft" if isolated else repo),
        "start_ref": branch,
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source.identity(),
        "inputs": inputs,
        "draft_seed": seed,
        "inventory_sha256": digest((out / "inventory.json").read_bytes()),
        "instructions_sha256": digest((out / "instructions.md").read_bytes()),
    }
    if not isolated:
        record["claims_path"] = f"{RECOVERY_RECORDS}/{run_id}/claims.json"
        record["source_record_path"] = f"{RECOVERY_RECORDS}/{run_id}/source.json"
        source_record = {
            "schema_version": 1,
            "source": source.identity(),
            "inputs": inputs,
            "status": "proposed",
        }
        record["source_record_sha256"] = digest(canonical(source_record))
        target = repo / record["source_record_path"]
        if any(p.is_symlink() for p in [target, *target.parents] if p.is_relative_to(repo)):
            raise CheckError("Recovery record path contains a symlink")
        ignored = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "check-ignore",
                "--no-index",
                "--",
                record["source_record_path"],
                record["claims_path"],
            ],
            capture_output=True,
            timeout=120,
        )
        if ignored.returncode == 0:
            raise CheckError(
                f"Git ignores recovery records under {RECOVERY_RECORDS}; make this location trackable or use --isolated"
            )
        if ignored.returncode != 1:
            raise CheckError(ignored.stderr.decode(errors="replace"))
        target.parent.mkdir(parents=True, exist_ok=False)
        write_json(target, source_record)
        write_json(out / "source-record.json", source_record)
    write_json(
        claims_path(out, record),
        {
            "schema_version": 1,
            "items": [],
            "open_issues": [],
            "document_changes": [],
            "requirement_mappings": [],
        },
    )
    if not isolated:
        after = current_manifest(repo)
        added = {record["claims_path"], record["source_record_path"]}
        if not added.issubset({e["path"] for e in after}):
            raise CheckError(
                f"Git ignores recovery records under {RECOVERY_RECORDS}; make these files visible before retrying"
            )
        if (
            [e for e in after if e["path"] not in added] != source.manifest
            or resolve_commit(repo, "HEAD") != start
            or head_ref(repo) != branch
        ):
            raise CheckError(
                "Checkout changed during preparation; inspect the retained files before retrying"
            )
    write_json(out / "recovery.json", record)
    if not isolated:
        storage = recovery_storage(repo)
        storage.mkdir(parents=True, exist_ok=True)
        write_json(storage / "active.json", {"bundle": str(out)})
    return record


def read_bundle(directory):
    directory = directory.resolve(strict=True)
    record = read_json(directory / "recovery.json")
    if (
        not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record["schema_version"] not in {1, 2}
    ):
        raise CheckError("Unsupported recovery bundle")
    if record["schema_version"] == 2:
        if record.get("mode") not in {"in_place", "isolated"}:
            raise CheckError("Unsupported recovery mode")
        if not isinstance(record.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", record["id"]):
            raise CheckError("Invalid recovery ID")
        if record["mode"] == "in_place":
            for field, name in (
                ("claims_path", "claims.json"),
                ("source_record_path", "source.json"),
            ):
                if record.get(field) != f"{RECOVERY_RECORDS}/{record['id']}/{name}":
                    raise CheckError("Invalid recovery record path")
            if not Path(record["workspace"]).is_absolute():
                raise CheckError("Recovery workspace must be absolute")
    manifest = read_json(directory / "source-manifest.json")
    if digest(canonical(manifest)) != record["source"]["sha256"]:
        raise CheckError("Recovery source manifest changed")
    if digest((directory / "inventory.json").read_bytes()) != record["inventory_sha256"]:
        raise CheckError("Recovery inventory changed")
    names = set()
    for entry in manifest:
        name = relative_path(entry["path"])
        if name in names:
            raise CheckError(f"Invalid recovery source path: {name}")
        names.add(name)
        mode, content = read_entry(directory / "source", name)
        if mode != entry["mode"] or digest(content) != entry["sha256"]:
            raise CheckError(f"Captured recovery source changed: {name}")
    validate_symlinks(directory / "source", manifest)
    actual = {
        p.relative_to(directory / "source").as_posix()
        for p in (directory / "source").rglob("*")
        if p.is_file() or p.is_symlink()
    }
    if actual != names:
        raise CheckError("Captured recovery source file inventory changed")
    return record, manifest


def validate_citation(citation, directory, inventory):
    if not isinstance(citation, dict) or set(citation) != {
        "path",
        "start_line",
        "end_line",
        "quote",
        "role",
    }:
        raise CheckError("Citation requires path, start_line, end_line, quote and role")
    name = relative_path(citation["path"])
    if name not in inventory or not inventory[name]["text"]:
        raise CheckError(f"Citation is outside inventoried text sources: {name}")
    if citation["role"] not in {"intent", "implementation", "test", "context"}:
        raise CheckError(f"Unknown citation role for {name}")
    start, end = citation["start_line"], citation["end_line"]
    lines = (directory / "source" / name).read_text(encoding="utf-8").splitlines()
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise CheckError(f"Citation line range is invalid: {name}")
    quote = citation["quote"]
    if (
        not isinstance(quote, str)
        or not quote.strip()
        or quote != "\n".join(lines[start - 1 : end])
    ):
        raise CheckError(f"Citation quote does not match captured source: {name}:{start}")
    return {**citation, "source_sha256": inventory[name]["sha256"]}


def validate_claims(claims, selected, directory, inventory):
    required = {"schema_version", "items", "open_issues"}
    optional = {"document_changes", "requirement_mappings"}
    if not isinstance(claims, dict) or required - set(claims) or set(claims) - required - optional:
        raise CheckError("claims.json requires schema_version, items and open_issues")
    if type(claims["schema_version"]) is not int or claims["schema_version"] != 1:
        raise CheckError("Unsupported claims schema")
    if not isinstance(claims["items"], list) or not isinstance(claims["open_issues"], list):
        raise CheckError("Claim items and open_issues must be lists")
    imported = {item["id"] for item in selected}
    seen, records = set(), []
    for item in claims["items"]:
        if not isinstance(item, dict) or set(item) != {"id", "origin", "sources", "notes"}:
            raise CheckError("Each claim requires id, origin, sources and notes")
        if not isinstance(item["id"], str) or item["id"] not in imported or item["id"] in seen:
            raise CheckError(f"Unknown or duplicate claim ID: {item['id']}")
        seen.add(item["id"])
        if item["origin"] not in {"documented", "inferred"} or not isinstance(item["notes"], str):
            raise CheckError(f"Invalid claim origin or notes: {item['id']}")
        if not isinstance(item["sources"], list) or not item["sources"]:
            raise CheckError(f"Claim has no source citations: {item['id']}")
        sources = [validate_citation(s, directory, inventory) for s in item["sources"]]
        if item["origin"] == "documented" and not any(s["role"] == "intent" for s in sources):
            raise CheckError(f"Documented claim has no intent citation: {item['id']}")
        records.append({**item, "sources": sources})
    if imported - seen:
        raise CheckError("Missing claim provenance: " + ", ".join(sorted(imported - seen)))
    issues = []
    for issue in claims["open_issues"]:
        if not isinstance(issue, dict) or set(issue) != {"description", "items", "sources"}:
            raise CheckError("Open issues require description, items and sources")
        if not isinstance(issue["description"], str) or not issue["description"].strip():
            raise CheckError("Open issue description must be nonempty")
        if not isinstance(issue["items"], list) or any(i not in imported for i in issue["items"]):
            raise CheckError("Open issue references an unknown requirement")
        if not isinstance(issue["sources"], list):
            raise CheckError("Open issue sources must be a list")
        issues.append(
            {
                **issue,
                "sources": [validate_citation(s, directory, inventory) for s in issue["sources"]],
            }
        )
    return {"schema_version": 1, "items": records, "open_issues": issues}


# Permit standalone OFT annotations while preserving non-annotation lines.
# OFT validates the graph; this check does not parse program or Markdown semantics.
COMMENT_PREFIXES = {
    ".py": "#",
    ".sh": "#",
    ".yaml": "#",
    ".yml": "#",
    ".toml": "#",
    ".js": "//",
    ".mjs": "//",
    ".cjs": "//",
    ".jsx": "//",
    ".ts": "//",
    ".tsx": "//",
    ".java": "//",
    ".c": "//",
    ".h": "//",
    ".cpp": "//",
    ".hpp": "//",
    ".cs": "//",
    ".go": "//",
    ".rs": "//",
    ".kt": "//",
    ".swift": "//",
    ".sql": "--",
}
ITEM_ID = r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+"
TAG = r"\[[A-Za-z]+->" + ITEM_ID + r"\]"


def annotation_changes_only(path, before, after, *, specification=False):
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".markdown"}:
        pattern = r"<!--\s*" + TAG + r"\s*-->"
        if specification:
            # Metadata-only additions do not require a document rewrite record.
            # Deleting/changing these lines does require one.
            pattern += (
                r"|`" + ITEM_ID + r"`|Needs:[ \t]+[A-Za-z]+(?:[ \t]*,[ \t]*[A-Za-z]+)*"
                r"|Status:[ \t]+draft|[ \t]*"
            )
    elif suffix in COMMENT_PREFIXES:
        pattern = re.escape(COMMENT_PREFIXES[suffix]) + r"\s*" + TAG
    else:
        return False
    pattern = r"\s*(?:" + pattern + r")\s*"
    try:
        left = before.decode("utf-8").splitlines(keepends=True)
        right = after.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return False
    deletion_pattern = r"\s*<!--\s*" + TAG + r"\s*-->\s*" if specification else pattern
    for kind, a, b, j, k in difflib.SequenceMatcher(
        None, left, right, autojunk=False
    ).get_opcodes():
        if kind == "equal":
            continue
        if not all(re.fullmatch(deletion_pattern, line) for line in left[a:b]) or not all(
            re.fullmatch(pattern, line) for line in right[j:k]
        ):
            return False
    return True


def specification_document(name, scope):
    return (
        Path(name).suffix.lower() in {".md", ".markdown"}
        and within(name, scope["specification_paths"])
        and not within(name, [RECOVERY_RECORDS])
    )


def authored_specification_items(items, root, scope):
    """Exclude unnamed coverage tags using OFT's source location, not ID shape.

    SpecObject exports do not label generated IDs. For Markdown, OFT locates
    coverage items at their standalone HTML comment. Explicitly named tags and
    ordinary Markdown IDs still require accounting, including revision zero.
    """
    documents, authored = {}, []
    for item in items:
        name = item["path"]
        if not specification_document(name, scope):
            continue
        if name not in documents:
            documents[name] = (root / name).read_text(encoding="utf-8").splitlines()
        lines = documents[name]
        if not 1 <= item["line"] <= len(lines):
            raise CheckError(f"Invalid OFT specification location: {name}:{item['line']}")
        line = lines[item["line"] - 1]
        if re.fullmatch(r"\s*<!--.*-->\s*", line):
            # OFT normalizes numeric revisions in its export.
            number = "0*" + str(item["revision"])
            named = re.search(r"\[\s*" + re.escape(item["key"]) + "~" + number + r"\s*->", line)
            revision = r"\s*~~\s*" + number
            if item["revision"] == 0:
                revision = "(?:" + revision + ")?"
            unnamed = re.search(r"\[\s*" + re.escape(item["type"]) + revision + r"\s*->", line)
            if unnamed and not named:
                continue
        authored.append(item)
    return authored


def editing_problems(source, candidate, scope, directory, inputs, record_paths=()):
    problems = []
    old = {entry["path"]: entry for entry in source}
    new = {entry["path"]: entry for entry in candidate.manifest}
    for name, entry in old.items():
        if entry == new.get(name):
            continue
        if entry["mode"] == "120000":
            problems.append(f"Recovery must preserve existing symlink: {name}")
            continue
        if within(name, inputs) and specification_document(name, scope):
            if name in new and entry["mode"] != new[name]["mode"]:
                problems.append(f"Recovery must preserve existing file mode: {name}")
            continue
        if name not in new or entry["mode"] != new[name]["mode"]:
            problems.append(f"Recovery must preserve existing file and mode: {name}")
        elif (
            within(name, [RECOVERY_RECORDS])
            or not within(name, inputs)
            or not annotation_changes_only(
                name,
                (directory / "source" / name).read_bytes(),
                (candidate.root / name).read_bytes(),
            )
        ):
            problems.append(
                f"Recovery changed original content beyond OFT annotation changes: {name}"
            )
    for name in new.keys() - old.keys():
        if new[name]["mode"] == "120000" or (
            name not in {"scope.json", *record_paths} and not specification_document(name, scope)
        ):
            problems.append(f"Recovery added a non-specification file: {name}")
    return problems


def document_review(claims, source, candidate, scope, directory, inventory):
    """Require cited explanations for substantive edits to original documents."""
    new = {entry["path"]: entry for entry in candidate.manifest}
    changed, required = {}, set()
    for entry in source:
        name = entry["path"]
        if (
            name not in inventory
            or not specification_document(name, scope)
            or entry == new.get(name)
        ):
            continue
        changed[name] = "modified" if name in new else "deleted"
        if name not in new or not annotation_changes_only(
            name,
            (directory / "source" / name).read_bytes(),
            (candidate.root / name).read_bytes(),
            specification=True,
        ):
            required.add(name)
    entries = claims.get("document_changes", [])
    if not isinstance(entries, list):
        raise CheckError("document_changes must be a list")
    seen, records = set(), []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "summary", "meaning", "sources"}:
            raise CheckError("Document changes require path, summary, meaning and sources")
        name = relative_path(entry["path"])
        if name not in changed or name in seen:
            raise CheckError(f"Unknown, unchanged or duplicate document change: {name}")
        seen.add(name)
        if not isinstance(entry["summary"], str) or not entry["summary"].strip():
            raise CheckError(f"Document change summary must be nonempty: {name}")
        if entry["meaning"] not in {"preserved", "changed", "uncertain"}:
            raise CheckError(f"Invalid document meaning assessment: {name}")
        if not isinstance(entry["sources"], list):
            raise CheckError(f"Document change sources must be a list: {name}")
        sources = [validate_citation(s, directory, inventory) for s in entry["sources"]]
        if (directory / "source" / name).read_text(encoding="utf-8").strip() and not any(
            s["path"] == name for s in sources
        ):
            raise CheckError(f"Document change must cite its original content: {name}")
        records.append({**entry, "change": changed[name], "sources": sources})
    if required - seen:
        raise CheckError("Missing document change review: " + ", ".join(sorted(required - seen)))
    return records


def requirement_review(claims, before, after):
    """Account for original OFT identities, including those removed from policy."""
    old, new = {}, {}
    for items, indexed in ((before, old), (after, new)):
        for item in items:
            if item["id"] in indexed:
                raise CheckError(f"Duplicate specification ID in recovery: {item['id']}")
            indexed[item["id"]] = item
    entries = claims.get("requirement_mappings", [])
    if not isinstance(entries, list):
        raise CheckError("requirement_mappings must be a list")
    mappings = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"from", "to", "reason"}:
            raise CheckError("Requirement mappings require from, to and reason")
        source = entry["from"]
        if not isinstance(source, str) or source not in old or source in mappings:
            raise CheckError(f"Unknown or duplicate original requirement: {source}")
        targets = entry["to"]
        if (
            not isinstance(targets, list)
            or any(not isinstance(t, str) or t not in new for t in targets)
            or len(set(targets)) != len(targets)
        ):
            raise CheckError(f"Invalid requirement mapping targets: {source}")
        if source in new and source not in targets:
            raise CheckError(f"Mapping must include the surviving original ID: {source}")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise CheckError(f"Requirement mapping reason must be nonempty: {source}")
        mappings[source] = entry
    records = []
    for identifier, item in old.items():
        mapping = mappings.get(identifier)
        if mapping is None:
            if identifier not in new or item["content"] != new[identifier]["content"]:
                raise CheckError(
                    f"Missing requirement mapping for changed or removed item: {identifier}"
                )
            mapping = {
                "from": identifier,
                "to": [identifier],
                "reason": "OFT identity and content preserved.",
            }
        records.append(
            {
                **mapping,
                "automatic": identifier not in mappings,
                "original": item,
                "proposed": [new[t] for t in mapping["to"]],
            }
        )
    return records


def check_recovery(directory, scope_path, out, jar, java="java", *, preflight=False):
    directory = directory.resolve(strict=True)
    try:
        hint = read_json(directory / "recovery.json")
        if not isinstance(hint, dict):
            raise CheckError("Unsupported recovery bundle")
        workspace = workspace_path(directory, hint).resolve()
    except (CheckError, OSError, ValueError, KeyError, TypeError):
        # Retain an error report even when the bundle cannot supply a location.
        # read_bundle below performs the full validation and records the error.
        hint, workspace = {}, directory / "draft"
    in_place = hint.get("mode") == "in_place"
    if out is None:
        out = (
            recovery_storage(repository(workspace)) / "checks" / uuid4().hex
            if in_place
            else directory.parent / f"{directory.name}-check-{uuid4().hex}"
        )
    out = out.resolve()
    if out.is_relative_to(directory):
        raise CheckError("Recovery check output must be outside the recovery bundle")
    if out.is_relative_to(workspace) and (
        not in_place or not out.is_relative_to(recovery_storage(repository(workspace)))
    ):
        raise CheckError(
            "Recovery check output must be outside the working tree or in its recovery storage"
        )
    if (
        not in_place
        and "source_repo" in hint
        and out.is_relative_to(Path(hint["source_repo"]).resolve())
        and not out.is_relative_to(recovery_storage(repository(Path(hint["source_repo"]))))
    ):
        raise CheckError("Isolated check output must be outside the original repository")
    out.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "status": "error",
        "review": "required",
        "proposal_checks": "not_completed",
        "preflight": preflight,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output": str(out),
        "workspace": str(workspace),
        "mode": "in_place" if in_place else "isolated",
        "diagnostics": [],
        "warnings": [],
        "limitations": [
            "A recovery proposal never approves inferred intent or adopts a baseline.",
            "Citations establish source locations, not semantic support or independent corroboration.",
            "Original OFT IDs are accounted for within inventoried specification documents; unstructured prose completeness is not established.",
            "Document meaning assessments and mapping reasons are author statements pending review.",
            "OFT coverage and suite outcomes do not establish individual assertion adequacy.",
        ],
    }
    checked, normalized = {}, {}
    proposal_validated = False
    for label, path in (("Original recovery bundle", directory), ("Check output", out)):
        if path.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            result["warnings"].append(
                f"{label} is in temporary storage: {path}. Retain the complete bundle before cleanup or transfer."
            )
    try:
        record, manifest = read_bundle(directory)
        scope_path = scope_path or workspace / "scope.json"
        scope = load_scope(scope_path)
        inventory = {entry["path"]: entry for entry in read_json(directory / "inventory.json")}
        claims_file = claims_path(directory, record)
        claims = read_json(claims_file)
        write_json(out / "claims.json", claims)
        write_json(out / "scope.json", scope)
        (out / "source-manifest.json").write_bytes(canonical(manifest))
        result["source"] = record["source"]
        result["recovery_sha256"] = digest((directory / "recovery.json").read_bytes())
        with tempfile.TemporaryDirectory(prefix="ib-recovery-check-") as tmp:
            scratch = Path(tmp)
            draft = repository(workspace)
            if in_place and (
                resolve_commit(draft, "HEAD") != record["source"]["commit"]
                or head_ref(draft) != record["start_ref"]
            ):
                raise CheckError(
                    "Recovery starting commit or branch changed; reconcile the proposal before checking"
                )
            seed = snapshot(
                draft,
                record["source"]["commit"] if in_place else record["draft_seed"],
                scratch / "seed",
            )
            if seed.sha256 != record["source"]["sha256"]:
                raise CheckError("Draft seed differs from captured source")
            candidate = snapshot(draft, "worktree", scratch / "candidate")
            record_paths = ()
            if in_place:
                record_paths = (record["claims_path"], record["source_record_path"])
                captured_source = read_json(candidate.root / record["source_record_path"])
                if digest(canonical(captured_source)) != record["source_record_sha256"]:
                    raise CheckError(
                        "Original source record changed; restore it from the recovery bundle"
                    )
                if read_json(candidate.root / record["claims_path"]) != claims:
                    raise CheckError("Claims changed during source capture; rerun")
            result["candidate"] = candidate.identity()
            result["diagnostics"].extend(
                editing_problems(
                    manifest, candidate, scope, directory, record["inputs"], record_paths
                )
            )
            if result["diagnostics"]:
                result["status"] = "rejected"
            else:
                # Build a disposable baseline with the candidate bytes. This is
                # validation of an initial baseline, not a change from an empty graph.
                validation = scratch / "validation"
                shutil.copytree(directory / "source", validation, symlinks=True)
                initialize(validation, "Captured source for recovery diff")
                candidate_paths = {entry["path"] for entry in candidate.manifest}
                for entry in manifest:
                    if entry["path"] not in candidate_paths:
                        (validation / entry["path"]).unlink()
                for entry in candidate.manifest:
                    put_file(
                        validation,
                        entry["path"],
                        entry["mode"],
                        read_entry(candidate.root, entry["path"])[1],
                    )
                git(validation, "add", "--force", "--all", "--", ".")
                (out / "proposal.patch").write_bytes(
                    git(
                        validation, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv"
                    )
                )
                baseline = commit(validation, "Proposed recovered baseline (review pending)")
                checked = check(
                    validation,
                    out / "scope.json",
                    baseline,
                    "HEAD",
                    out / "check",
                    jar,
                    java,
                    preflight=preflight,
                )
                result["check_status"] = checked["status"]
                if "candidate" in checked and checked["candidate"]["sha256"] != candidate.sha256:
                    raise CheckError(
                        "Disposable Git baseline changed draft contents; inspect attributes/filters"
                    )
                result["diagnostics"].extend(checked["diagnostics"])
                if "requirements" in checked:
                    normalized = validate_claims(
                        claims, checked["requirements"]["candidate"], directory, inventory
                    )
                    write_json(out / "provenance.json", normalized)
                    result["open_issue_count"] = len(normalized["open_issues"])
                    documents = document_review(
                        claims, manifest, candidate, scope, directory, inventory
                    )
                    original_paths = [
                        name
                        for name, entry in inventory.items()
                        if entry["mode"] != "120000" and specification_document(name, scope)
                    ]
                    original_items = (
                        export_items(seed, original_paths, jar.resolve(), java, out, "original")[0]
                        if original_paths
                        else []
                    )
                    original_items = authored_specification_items(original_items, seed.root, scope)
                    proposed_items = authored_specification_items(
                        import_items(out / "check/candidate-items.xml", validation),
                        candidate.root,
                        scope,
                    )
                    requirements = requirement_review(claims, original_items, proposed_items)
                    write_json(
                        out / "documentation-review.json",
                        {
                            "schema_version": 1,
                            "review": "required",
                            "source": record["source"],
                            "candidate": candidate.identity(),
                            "document_changes": documents,
                            "requirement_mappings": requirements,
                        },
                    )
                    result["document_change_count"] = len(documents)
                    result["original_requirement_count"] = len(requirements)
                    proposal_validated = True
                else:
                    raise CheckError(
                        "OFT could not import the proposed baseline; see check/evidence.json"
                    )
                result["status"] = (
                    "review_required" if checked["status"] == "passed" else checked["status"]
                )
                # In-place changes are already visible in Git. Isolated callers
                # also receive a complete copy of the checked proposal.
                if not in_place:
                    shutil.copytree(candidate.root, out / "proposed", symlinks=True)
                (out / "candidate-manifest.json").write_bytes(canonical(candidate.manifest))
                current = snapshot(draft, "worktree", scratch / "current")
                if current.sha256 != candidate.sha256 or (
                    in_place
                    and (
                        current.commit != record["source"]["commit"]
                        or head_ref(draft) != record["start_ref"]
                    )
                ):
                    proposal_validated = False
                    result["status"] = "rejected"
                    result["diagnostics"].append(
                        "Draft changed during validation (contents, starting commit or branch); rerun recovery check"
                    )
            if read_json(claims_file) != claims or load_scope(scope_path) != scope:
                proposal_validated = False
                result["status"] = "rejected"
                result["diagnostics"].append("Claims or scope changed during validation; rerun")
            current_record, _ = read_bundle(directory)
            if current_record != record:
                raise CheckError("Recovery identity changed during validation; rerun")
            if proposal_validated:
                result["proposal_checks"] = "passed"
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        result["status"] = "error"
        result["diagnostics"].append(str(exc))
    result["review_artifacts"] = [
        name
        for name in (
            "proposal.patch",
            "scope.json",
            "claims.json",
            "provenance.json",
            "documentation-review.json",
            "check/evidence.json",
            "check/candidate-trace.log",
            "check/tests.log",
            "check/tests.xml",
        )
        if (out / name).is_file()
    ]
    result["summary"] = "recovery-review.md"
    (out / result["summary"]).write_text(
        render_review(result, checked, normalized), encoding="utf-8"
    )
    result["artifacts"] = {
        p.relative_to(out).as_posix(): digest(read_entry(out, p.relative_to(out).as_posix())[1])
        for p in sorted(out.rglob("*"))
        if p.is_symlink() or p.is_file()
    }
    write_json(out / "recovery-result.json", result)
    return result
