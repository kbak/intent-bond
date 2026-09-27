"""Report source selection boundaries without expanding policy or inferring approval."""

from .common import CheckError, read_json, within


def inventory(base_manifest, candidate_manifest, scope):
    before = {entry["path"]: entry for entry in base_manifest}
    after = {entry["path"]: entry for entry in candidate_manifest}
    paths = []
    for path in sorted(before.keys() | after.keys()):
        if before.get(path) == after.get(path):
            continue
        selection = (
            "specification"
            if within(path, scope["specification_paths"])
            else "test"
            if within(path, scope["test_paths"])
            else None
        )
        paths.append(
            {
                "path": path,
                "change": "added"
                if path not in before
                else "deleted"
                if path not in after
                else "modified",
                "tracing_input": within(path, scope["inputs"]),
                "semantic_review_selection": selection,
            }
        )
    selected = sum(p["semantic_review_selection"] is not None for p in paths)
    return {
        "schema_version": 1,
        "counts": {
            "all_changed_captured_source_paths": len(paths),
            "changed_tracing_input_paths": sum(p["tracing_input"] for p in paths),
            "changed_selected_semantic_review_paths": selected,
            "changed_paths_outside_selected_semantic_review": len(paths) - selected,
        },
        "paths": paths,
        "meaning": "All paths remain covered by full source identity. Tracing input membership and specification/test review selection are narrower policy boundaries. Selection does not establish semantic approval or missing requirements.",
    }


def retained(evidence, directory, scope):
    expected = inventory(
        read_json(directory / "base-manifest.json"),
        read_json(directory / "candidate-manifest.json"),
        scope,
    )
    if "source_boundaries" in evidence:
        review = read_json(directory / "review.json")
        if evidence["source_boundaries"] != expected or review.get("source_boundaries") != expected:
            raise CheckError("Source boundary inventory differs from retained manifests and scope")
    return expected


def lines(value):
    if not value:
        return []
    counts = value["counts"]
    return [
        "Changed captured source paths: " + str(counts["all_changed_captured_source_paths"]),
        "Changed tracing-input paths: " + str(counts["changed_tracing_input_paths"]),
        "Changed selected specification/test review paths: "
        + str(counts["changed_selected_semantic_review_paths"]),
        "Changed paths outside selected semantic review: "
        + str(counts["changed_paths_outside_selected_semantic_review"]),
        "Source identity, structural coverage, executed assertions and semantic approval are separate results. review_required records a pending review gate, neither approval nor rejection.",
    ]
