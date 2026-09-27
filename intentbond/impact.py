"""Derived change impact from OFT's graph and conservative source-line classification."""

import re

from . import boundaries
from .common import CheckError, canonical, digest, read_json, within
from .config import load_scope
from .evidence import check_artifacts, read_statement
from .explain import graph_report
from .oft import OFT_SHA256, OFT_VERSION
from .snapshot import read_entry

TAG = re.compile(
    r"\s*(?:#|//|--|<!--)\s*\[(?:[A-Za-z]+(?:~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+)?)->[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+\]\s*(?:-->)?\s*"
)


def source_changes(base, candidate, before, after, scope):
    """Only recognize complete OFT-imported standalone tag lines; never parse code semantics."""
    selected = boundaries.inventory(base.manifest, candidate.manifest, scope)
    manifests = [{e["path"]: e for e in snap.manifest} for snap in (base, candidate)]
    result = []
    for change in selected["paths"]:
        path = change["path"]
        kind = "unclassified_source_change"
        left, right = (entries.get(path) for entries in manifests)
        if (
            left
            and right
            and left["mode"] == right["mode"]
            and left["mode"] in {"100644", "100755"}
        ):
            stripped = []
            removed = 0
            try:
                for snap, items in ((base, before), (candidate, after)):
                    imported = {i["line"] for i in items if i["path"] == path}
                    text = read_entry(snap.root, path)[1].decode("utf-8")
                    lines = []
                    for number, line in enumerate(text.splitlines(keepends=True), 1):
                        if number in imported and TAG.fullmatch(line):
                            removed += 1
                        else:
                            lines.append(line)
                    stripped.append("".join(lines))
                if removed and stripped[0] == stripped[1]:
                    kind = "recognized_annotation_lines_only"
                elif within(path, scope["specification_paths"]):
                    kind = "specification_source_changed"
                elif within(path, scope["test_paths"]):
                    kind = "assertion_or_test_source_changed"
                elif within(path, scope["inputs"]):
                    kind = "implementation_or_other_source_changed"
                else:
                    kind = "other_captured_source_changed"
            except UnicodeDecodeError:
                pass
        result.append({"path": path, "classification": kind})
    return result


def key(identifier):
    return identifier.rsplit("~", 1)[0]


def compare_graphs(before, after, scope):
    old = {key(i["id"]): i for i in before.values()}
    new = {key(i["id"]): i for i in after.values()}
    if len(old) != len(before) or len(new) != len(after):
        raise CheckError("Multiple active revisions prevent an unambiguous impact comparison")
    changes = []
    for name in sorted(old.keys() | new.keys()):
        left, right = old.get(name), new.get(name)
        if not left or not right:
            kind = "added" if right else "removed"
        elif (left["title"], left["description"]) != (right["title"], right["description"]):
            kind = (
                "normative_text_changed"
                if name.split("~")[0] in scope["required_coverage"]
                else "artifact_text_changed"
            )
        elif left["needs"] != right["needs"]:
            kind = "coverage_policy_changed"
        elif (left["id"], left["covers"]) != (right["id"], right["covers"]):
            kind = "link_or_revision_only"
        elif (left["path"], left["line"]) != (right["path"], right["line"]):
            kind = "location_only"
        else:
            continue
        changes.append(
            {
                "key": name,
                "classification": kind,
                "before": left["id"] if left else None,
                "after": right["id"] if right else None,
                "path": (right or left)["path"],
            }
        )
    edge_sets = [
        {(i["id"], target) for i in items.values() for target in i["covers"]}
        for items in (before, after)
    ]
    prior, current = edge_sets

    def logical(edges):
        grouped = {}
        for source, target in sorted(edges):
            grouped.setdefault((key(source), key(target)), []).append([source, target])
        return grouped

    old_logical, new_logical = logical(prior), logical(current)
    ambiguous = [
        {"logical_pair": list(k), "before": old_logical.get(k, []), "after": new_logical.get(k, [])}
        for k in sorted(old_logical.keys() | new_logical.keys())
        if len(old_logical.get(k, [])) > 1 or len(new_logical.get(k, [])) > 1
    ]
    updates = [
        {"from": old_logical[k][0], "to": new_logical[k][0]}
        for k in sorted(old_logical.keys() & new_logical.keys())
        if len(old_logical[k]) == len(new_logical[k]) == 1 and old_logical[k] != new_logical[k]
    ]
    return {
        "declarations": changes,
        "counts": {
            "base_declarations": len(old),
            "added_declarations": sum(c["classification"] == "added" for c in changes),
            "removed_declarations": sum(c["classification"] == "removed" for c in changes),
            "candidate_declarations": len(new),
            "changed_declarations_excluding_location": sum(
                c["classification"] != "location_only" for c in changes
            ),
            "normative_text_changed": sum(
                c["classification"] == "normative_text_changed" for c in changes
            ),
            "link_or_revision_only_declarations": sum(
                c["classification"] == "link_or_revision_only" for c in changes
            ),
            "base_edges": len(prior),
            "candidate_edges": len(current),
            "added_exact_edges": len(current - prior),
            "removed_exact_edges": len(prior - current),
            "continuing_edges_with_revised_endpoints": len(updates),
            "ambiguous_logical_edge_pairs": len(ambiguous),
        },
        "edges": {
            "added": [list(e) for e in sorted(current - prior)],
            "removed": [list(e) for e in sorted(prior - current)],
            "revision_updates": updates,
            "ambiguous_pairs": ambiguous,
        },
    }


def impact(evidence_path, jar, java="java"):
    evidence_path = evidence_path.resolve()
    directory = evidence_path.parent
    evidence = read_statement(read_json(evidence_path))
    if evidence.get("schema_version") != 2 or evidence.get("oft") != {
        "version": OFT_VERSION,
        "sha256": OFT_SHA256,
    }:
        raise CheckError("Unsupported check evidence or OFT version")
    check_artifacts(
        evidence,
        directory,
        {
            "scope.json",
            "review.json",
            "base-items.xml",
            "candidate-items.xml",
            "base-manifest.json",
            "candidate-manifest.json",
        },
    )
    scope = load_scope(directory / "scope.json")
    if (
        scope != evidence["scope"]["configuration"]
        or digest(canonical(scope)) != evidence["scope"]["sha256"]
    ):
        raise CheckError("Scope differs from recorded policy")
    for label in ("base", "candidate"):
        if (
            digest(canonical(read_json(directory / f"{label}-manifest.json")))
            != evidence[label]["sha256"]
        ):
            raise CheckError("Manifest differs from recorded source identity")
    before, old_trace = graph_report(directory / "base-items.xml", jar, java)
    after, new_trace = graph_report(directory / "candidate-items.xml", jar, java)
    report = compare_graphs(before, after, scope)
    review = read_json(directory / "review.json")
    report.update(
        schema_version=1,
        evidence=str(evidence_path),
        base=evidence["base"],
        candidate=evidence["candidate"],
        scope_sha256=evidence["scope"]["sha256"],
        source_boundaries=boundaries.retained(evidence, directory, scope),
        source_changes=review.get("source_changes"),
        source_classification_status="recorded_at_check"
        if "source_changes" in review
        else "not_recorded_in_legacy_bundle",
        trace={"base": old_trace["status"], "candidate": new_trace["status"]},
        recorded_check_status=evidence["status"],
        review=evidence.get("review"),
        human_review_minutes=None,
        limitations=[
            "OFT computes graph validity and coverage. This report compares its exported artifacts and exact edges; it does not implement a second tracing engine.",
            "Normative text means a textual change to a selected requirement declaration, not a proven semantic change. Source classifications describe file text, not assertion adequacy or behavioral equivalence.",
            "Advancing a link or declaration revision requires review of continued coverage; it never establishes that an assertion satisfies the revised promise.",
            "Source-line classifications are unsigned producer observations retained at check time. Old bundles do not gain invented classifications. Use ib verify to match current source.",
            "Counts do not establish avoided maintenance or lower review effort. Human review time and causal ROI were not measured.",
        ],
    )
    return report


def render_impact(report):
    lines = ["Change impact for saved evidence: " + report["evidence"]]
    lines += [
        name.replace("_", " ") + ": " + str(value) for name, value in report["counts"].items()
    ]
    lines += [c["key"] + ": " + c["classification"] for c in report["declarations"]]
    lines += [c["path"] + ": " + c["classification"] for c in (report["source_changes"] or [])]
    lines += [
        "Recorded check: " + report["recorded_check_status"],
        "Source-line classification: " + report["source_classification_status"],
        "Human review effort: not measured",
        *report["limitations"],
    ]
    return "\n".join(lines)
