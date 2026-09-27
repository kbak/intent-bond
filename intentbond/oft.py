import os
import re
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import RECOVERY_RECORDS, CheckError, digest, run, within, xml_tree

OFT_VERSION = "4.9.0"
OFT_SHA256 = "d4ed42503ae066f51d55c3aad7c6e4b16acb80365921951ef5a065a4dc3d94f3"
OFT_URL = f"https://github.com/itsallcode/openfasttrace/releases/download/{OFT_VERSION}/openfasttrace-{OFT_VERSION}.jar"

# OFT 4.9.0's tag importer accepts ts/js but omits their JSX variants.
# Reuse that importer on byte-identical temporary aliases, then restore origins.
TAG_ALIASES = {".tsx": ".ts", ".jsx": ".js"}


def annotation_diagnostics(snap, inputs, items):
    """Detect ignored standalone short tags, not program-language semantics."""
    imported = {(i["path"], i["line"], i["type"]) for i in items}
    pattern = re.compile(
        r"\s*(?:#|//|--|<!--)\s*\[([A-Za-z]+)->"
        r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+\]\s*(?:-->)?\s*"
    )
    missing = []
    for entry in snap.manifest:
        name = entry["path"]
        if (
            entry.get("mode") == "120000"
            or not within(name, inputs)
            or within(name, [RECOVERY_RECORDS])
        ):
            continue
        markdown = Path(name).suffix.lower() in {".md", ".markdown"}
        fence = None
        for line, text in enumerate(
            (snap.root / name).read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if markdown:
                marker = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", text)
                if fence:
                    # A shorter or different fence inside an example does not close it.
                    if (
                        marker
                        and marker[1][0] == fence[0]
                        and len(marker[1]) >= len(fence)
                        and not marker[2].strip()
                    ):
                        fence = None
                    continue
                if marker and (marker[1][0] == "~" or "`" not in marker[2]):
                    fence = marker[1]
                    continue
            match = pattern.fullmatch(text)
            if match and (name, line, match[1]) not in imported:
                missing.append(f"{name}:{line}")
    return missing


def default_jar():
    return Path(
        os.environ.get(
            "INTENTBOND_OFT_JAR",
            Path.home() / ".cache" / "intentbond" / f"openfasttrace-{OFT_VERSION}.jar",
        )
    )


def validate_jar(path):
    try:
        if digest(path.read_bytes()) != OFT_SHA256:
            raise CheckError(f"OFT checksum mismatch: expected {OFT_SHA256}")
    except OSError as exc:
        raise CheckError(
            f"OFT {OFT_VERSION} is unavailable at {path}; run ib install-oft or pass --oft-jar"
        ) from exc


def install_jar(destination):
    destination.mkdir(parents=True, exist_ok=True)
    jar = destination / f"openfasttrace-{OFT_VERSION}.jar"
    if jar.exists():
        validate_jar(jar)
        return jar
    try:
        with urllib.request.urlopen(OFT_URL, timeout=60) as response:
            content = response.read()
    except OSError as exc:
        raise CheckError(f"OFT download failed: {exc}") from exc
    if digest(content) != OFT_SHA256:
        raise CheckError("Downloaded OFT checksum does not match pinned release")
    with jar.open("xb") as output:
        output.write(content)
    return jar


def element_value(element):
    """Normalize OFT-exported data, excluding location separately; no source parsing."""
    if not len(element):
        return element.text or ""
    return sorted([[child.tag, element_value(child)] for child in element], key=repr)


def import_items(path, root):
    tree = xml_tree(path)
    if tree.tag != "specdocument":
        raise CheckError("Unexpected OFT SpecObject root")
    items = []
    for group in tree.findall("specobjects"):
        kind = group.get("doctype")
        for element in group.findall("specobject"):
            name = element.findtext("id")
            version = element.findtext("version")
            source = element.findtext("sourcefile")
            if not kind or not name or version is None or not source:
                raise CheckError("Incomplete OFT SpecObject item")
            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = root / source_path
            try:
                relative = source_path.relative_to(root).as_posix()
                revision = int(version)
            except ValueError as exc:
                raise CheckError("Invalid OFT source location or revision") from exc
            items.append(
                {
                    "key": f"{kind}~{name}",
                    "id": f"{kind}~{name}~{revision}",
                    "type": kind,
                    "revision": revision,
                    "path": relative,
                    "line": int(element.findtext("sourceline", "0")),
                    "needs": sorted(n.text for n in element.findall("needscoverage/needsobj")),
                    "content": {
                        child.tag: element_value(child)
                        for child in element
                        if child.tag not in {"id", "version", "sourcefile", "sourceline"}
                    },
                }
            )
    return items


def artifact_inputs(root, path, links=()):
    """Exclude historical annotations and symlink aliases from OFT traversal."""
    if within(path, [RECOVERY_RECORDS]) or path in links:
        return []
    if (root / path).is_dir() and (
        (within(RECOVERY_RECORDS, [path]) and (root / RECOVERY_RECORDS).exists())
        or any(within(link, [path]) for link in links)
    ):
        paths = [
            item
            for child in sorted((root / path).iterdir())
            for item in artifact_inputs(root, child.relative_to(root).as_posix(), links)
        ]
        return [f"./{item}" for item in paths] if path == "." else paths
    return [path]


def export_items(snap, inputs, jar, java, out, label):
    """Import artifacts through OFT without requiring an already complete graph."""
    for path in inputs:
        if not any(within(entry["path"], [path]) for entry in snap.manifest):
            raise CheckError(f"{label}: input path has no source files: {path}")
    # Relative inputs keep OFT's generated annotation IDs stable across snapshots.
    inputs = list(dict.fromkeys(inputs))
    # Overlapping roots otherwise import the same requirement more than once.
    inputs = [p for p in inputs if not within(p, [q for q in inputs if p != q])]
    links = [e["path"] for e in snap.manifest if e["mode"] == "120000"]
    for path in inputs:
        if path in links:
            raise CheckError(f"{label}: select the actual source path instead of symlink: {path}")
    # Do not let directory import follow aliases (duplicating IDs), dangling links,
    # or recursive directory links. Tests still receive the original links.
    inputs = [item for path in inputs for item in artifact_inputs(snap.root, path, links)]
    selected_inputs = [Path(path).as_posix() for path in inputs]
    if not inputs:
        raise CheckError(f"{label}: select project artifacts outside {RECOVERY_RECORDS}")
    command = [java, "-jar", str(jar)]
    exported = out / f"{label}-items.xml"
    convert = run(
        command + ["convert", "-f", str(exported), *inputs], snap.root, out / f"{label}-import.log"
    )
    if convert["status"] != "passed":
        raise CheckError(f"{label}: OFT import failed; see {convert['log']}")
    # OFT may warn and skip malformed items while returning 0. Treat import diagnostics as errors.
    if (out / convert["log"]).read_text(errors="replace").strip():
        raise CheckError(f"{label}: OFT import emitted diagnostics; see {convert['log']}")
    aliases = [
        e["path"]
        for e in snap.manifest
        if e["mode"] != "120000"
        and Path(e["path"]).suffix in TAG_ALIASES
        and within(e["path"], selected_inputs)
        and not within(e["path"], [RECOVERY_RECORDS])
    ]
    if aliases:
        tree = xml_tree(exported)
        with tempfile.TemporaryDirectory(prefix="ib-oft-tags-") as temporary:
            root = Path(temporary)
            originals = {}
            for name in aliases:
                alias = name + TAG_ALIASES[Path(name).suffix]
                target = root / alias
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((snap.root / name).read_bytes())
                originals[alias] = name
            extra = out / f"{label}-tags.xml"
            imported = run(
                command + ["convert", "-f", str(extra), "."],
                root,
                out / f"{label}-tags-import.log",
            )
            if imported["status"] != "passed" or (out / imported["log"]).read_text().strip():
                raise CheckError(f"{label}: OFT tag import failed; see {imported['log']}")
            for group in xml_tree(extra):
                for item in group.findall("specobject"):
                    source = item.find("sourcefile")
                    path = Path(source.text)
                    key = (
                        path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
                    )
                    source.text = originals[key]
                tree.append(group)
            extra.unlink()
            ET.ElementTree(tree).write(exported, encoding="utf-8", xml_declaration=True)
            convert["additional_import"] = imported
    items = import_items(exported, snap.root)
    missing = annotation_diagnostics(snap, selected_inputs, items)
    if missing:
        raise CheckError(
            f"{label}: OFT ignored standalone coverage comments at "
            + ", ".join(missing)
            + ". Check the file format and annotation syntax before running tests."
        )
    return items, convert, inputs


def trace(snap, scope, jar, java, out, label):
    items, convert, inputs = export_items(snap, scope["inputs"], jar, java, out, label)
    command = [java, "-jar", str(jar)]
    result = run(
        command + ["trace", "-c", "BLACK_AND_WHITE", str(out / f"{label}-items.xml")],
        snap.root,
        out / f"{label}-trace.log",
    )
    if result["status"] == "error" or result["exit_code"] not in (0, 1):
        raise CheckError(f"{label}: OFT could not execute tracing; see {result['log']}")
    return items, {
        "status": result["status"],
        "import": convert,
        "trace": result,
        "item_count": len(items),
    }


def policy_diagnostics(items, scope, label):
    diagnostics = []
    selected = [item for item in items if item["type"] in scope["required_coverage"]]
    keys = set()
    for item in selected:
        if item["key"] in keys:
            diagnostics.append(f"{label}: multiple active items for {item['key']}")
        keys.add(item["key"])
        missing = set(scope["required_coverage"][item["type"]]) - set(item["needs"])
        if missing:
            diagnostics.append(
                f"{label}: {item['id']} must retain Needs: {', '.join(sorted(missing))}"
            )
        if not within(item["path"], scope["specification_paths"]):
            diagnostics.append(f"{label}: {item['id']} is outside specification_paths")
    return selected, diagnostics
