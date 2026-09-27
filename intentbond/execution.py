"""Optional association of reported JUnit cases with OFT verification artifacts."""

from collections import Counter

from .common import CheckError, within, xml_tree
from .evidence import check_artifacts
from .oft import import_items
from .testing import ReportCase, junit_counts, skipped

PROPERTY = "oft_id"


def combined_status(statuses):
    values = set(statuses)
    return next(iter(values)) if len(values) == 1 else "mixed"


def collect_execution_links(path, items, scope):
    """Reuse JUnit parsing and OFT identities; never infer a link from a location."""
    junit_counts(path)  # Validate report completeness before interpreting cases.
    kinds = scope["tests"]["execution_links"]["artifact_types"]
    inventory = Counter(item["id"] for item in items)
    selected = {
        item["id"]
        for item in items
        if item["type"] in kinds and within(item["path"], scope["test_paths"])
    }
    diagnostics = []
    observations = []

    def visit(element, suites=()):
        if element.tag == "testsuite":
            suites += (element.get("name", ""),)
        if element.tag == "testcase":
            case = ReportCase.fromelem(element)
            identity = (*suites, case.classname or "", case.name or "")
            properties = element.findall("properties/property")
            refs = [prop.get("value", "") for prop in properties if prop.get("name") == PROPERTY]
            refs = sorted(set(refs))
            if refs and not case.name:
                diagnostics.append("Linked JUnit testcase has no name")
            resolved = []
            for ref in refs:
                if not ref or inventory[ref] != 1 or ref not in selected:
                    diagnostics.append(
                        f"Invalid OFT execution reference {ref!r}: require one exact ID/revision "
                        "of a selected artifact type within test_paths"
                    )
                else:
                    resolved.append(ref)
            # This profile covers ordinary final outcomes, not retry extensions.
            reasons = []
            unsupported = sorted(
                {
                    child.tag
                    for child in element
                    if child.tag
                    not in {"properties", "failure", "error", "skipped", "system-out", "system-err"}
                }
            )
            if unsupported:
                reasons.append("Unsupported outcome elements: " + ", ".join(unsupported))
            if case.status not in {None, "", "run", "passed", "skipped", "disabled", "notrun"}:
                reasons.append(f"Unsupported testcase status: {case.status}")
            if sum(bool(value) for value in (case.is_failure, case.is_error, skipped(case))) > 1:
                reasons.append("Conflicting testcase outcomes")
            if reasons:
                status = "ambiguous"
            elif case.is_failure or case.is_error:
                status = "failed"
            elif skipped(case):
                status = "skipped"
            else:
                status = "passed"
            observations.append(
                (
                    identity,
                    resolved,
                    {
                        "suite": list(suites),
                        "classname": case.classname or "",
                        "name": case.name or "",
                        "status": status,
                        "diagnostics": reasons,
                        "details": [
                            {
                                "kind": child.tag,
                                "type": child.get("type", ""),
                                "message": child.get("message", ""),
                            }
                            for child in element
                            if child.tag in {"failure", "error", "skipped"}
                        ],
                    },
                )
            )
        else:
            for child in element:
                if child.tag in {"testsuites", "testsuite", "testcase"}:
                    visit(child, suites)

    visit(xml_tree(path))
    identities = Counter(identity for identity, _, _ in observations)
    linked = {identifier: [] for identifier in sorted(selected)}
    for identity, refs, observation in observations:
        if identities[identity] > 1 or not observation["name"]:
            observation["status"] = "ambiguous"
            observation["diagnostics"].append(
                "Duplicate testcase identity"
                if identities[identity] > 1
                else "Missing testcase name"
            )
        for ref in refs:
            linked[ref].append(observation)
    return {
        "schema_version": 1,
        "format": "junit-properties-v1",
        "property": PROPERTY,
        "status": "invalid" if diagnostics else "recorded",
        "diagnostics": sorted(set(diagnostics)),
        "unlinked_cases": sum(not refs for _, refs, _ in observations),
        "artifacts": [
            {
                "id": identifier,
                "status": combined_status(case["status"] for case in cases)
                if cases
                else "not_observed",
                "cases": cases,
            }
            for identifier, cases in linked.items()
        ],
    }


def required_execution_diagnostics(links, scope):
    """Require passing observations for named identities in trusted scope policy."""
    diagnostics = []
    for key in scope["tests"].get("execution_links", {}).get("required_artifacts", []):
        matches = [item for item in links["artifacts"] if item["id"].rsplit("~", 1)[0] == key]
        if len(matches) != 1:
            diagnostics.append(
                f"Required execution artifact {key}: expected exactly one imported revision "
                f"within selected artifact types and test_paths; found {len(matches)}"
            )
        elif matches[0]["status"] != "passed":
            diagnostics.append(
                f"Required execution artifact {matches[0]['id']}: "
                f"expected passed observations; got {matches[0]['status']}"
            )
    return diagnostics


def retained_execution_links(evidence, directory, scope):
    """Recompute retained links so readers do not trust a supplied summary."""
    tests = evidence["tests"]
    recorded = tests.get("execution_links")
    enabled = "execution_links" in scope["tests"]
    if not enabled or "counts" not in tests:
        if recorded is not None:
            raise CheckError("Execution links lack configured, parsed JUnit evidence")
        return None
    check_artifacts(evidence, directory, {"tests.xml", "candidate-items.xml"})
    expected = collect_execution_links(
        directory / "tests.xml", import_items(directory / "candidate-items.xml", directory), scope
    )
    if expected != recorded:
        raise CheckError("Execution links do not match retained JUnit/OFT evidence")
    return expected


def explain_execution(identifier, graph, links, tests):
    if links is None:
        return "not_established", [], ["No execution-link evidence for this snapshot."]
    if (
        tests.get("source_status") != "matched"
        or tests.get("status") == "error"
        or tests.get("exit_code") is None
    ):
        return (
            "not_established",
            [],
            ["Execution evidence lacks stable source or a completed test command."],
        )
    by_id = {item["id"]: item for item in links["artifacts"]}
    pending, seen = [identifier], set()
    while pending:
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        pending.extend(graph.get(ref, {}).get("covered_by", []))
    artifacts = [by_id[ref] for ref in sorted(seen & by_id.keys())]
    status = (
        combined_status(item["status"] for item in artifacts)
        if artifacts and links["status"] == "recorded"
        else "not_established"
    )
    return status, artifacts, links["diagnostics"]
