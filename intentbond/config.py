import re
from pathlib import Path

from .common import CheckError, parse_json, read_json, relative_path, within
from .snapshot import git


def load_scope(path: Path):
    return validate_scope(read_json(path))


def load_baseline_scope(repo, commit):
    try:
        content = git(repo, "show", f"{commit}:scope.json")
    except CheckError as exc:
        raise CheckError(
            "Cannot read scope.json from the baseline; commit it before starting "
            "the change or supply a trusted file with --scope"
        ) from exc
    try:
        return validate_scope(parse_json(content))
    except ValueError as exc:
        raise CheckError(f"Invalid scope.json in baseline: {exc}") from exc


def validate_scope(scope):
    required = {
        "schema_version",
        "name",
        "inputs",
        "specification_paths",
        "test_paths",
        "required_coverage",
        "tests",
    }
    if (
        not isinstance(scope, dict)
        or set(scope) - required - {"allow_empty", "policy"}
        or required - set(scope)
    ):
        raise CheckError("Scope has unknown or missing fields; see docs/contract.md")
    if type(scope["schema_version"]) is not int or scope["schema_version"] != 1:
        raise CheckError("Unsupported scope schema_version (expected 1)")
    if not isinstance(scope["name"], str) or not scope["name"].strip():
        raise CheckError("Scope name must be nonempty")
    if type(scope.get("allow_empty", False)) is not bool:
        raise CheckError("allow_empty must be boolean")
    for key in ("inputs", "specification_paths", "test_paths"):
        values = scope[key]
        if not isinstance(values, list) or not values:
            raise CheckError(f"{key} must be a nonempty path list")
        for value in values:
            relative_path(value)
        if len(set(values)) != len(values):
            raise CheckError(f"Duplicate paths in {key}")
    for group in ("specification_paths", "test_paths"):
        if any(not within(p, scope["inputs"]) for p in scope[group]):
            raise CheckError(f"{group} must be inside inputs")
    if any(within(p, scope["test_paths"]) for p in scope["specification_paths"]) or any(
        within(p, scope["specification_paths"]) for p in scope["test_paths"]
    ):
        raise CheckError("Specification and test paths must not overlap")
    coverage = scope["required_coverage"]
    if not isinstance(coverage, dict) or not coverage:
        raise CheckError("required_coverage must map requirement artifact types to coverage floors")
    for kind, needs in coverage.items():
        if not re.fullmatch(r"[A-Za-z]+", kind):
            raise CheckError(f"Invalid artifact type: {kind}")
        if not isinstance(needs, list) or any(
            not isinstance(n, str) or not re.fullmatch(r"[A-Za-z]+", n) for n in needs
        ):
            raise CheckError(f"Invalid coverage floor for {kind}")
        if len(set(needs)) != len(needs):
            raise CheckError(f"Duplicate coverage floor for {kind}")
    policy = scope.get("policy", {})
    if (
        not isinstance(policy, dict)
        or set(policy) - {"require_revision_increase", "allow_skipped_tests"}
        or any(type(value) is not bool for value in policy.values())
    ):
        raise CheckError("policy accepts boolean require_revision_increase and allow_skipped_tests")
    tests = scope["tests"]
    if (
        not isinstance(tests, dict)
        or set(tests)
        - {"command", "report", "reports", "timeout_seconds", "format", "execution_links"}
        or {"command", "timeout_seconds"} - set(tests)
        or tests.get("format", "junit") not in {"junit", "command"}
    ):
        raise CheckError("tests requires command, timeout_seconds, and format junit or command")
    command = tests["command"]
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(s, str) or not s or "\x00" in s for s in command)
    ):
        raise CheckError("tests.command must be a nonempty argv array (no implicit shell)")
    if tests.get("format", "junit") == "junit":
        if ("report" in tests) == ("reports" in tests):
            raise CheckError("JUnit tests require either report or reports")
        reports = tests.get("reports", [tests.get("report")])
        if not isinstance(reports, list) or not reports:
            raise CheckError("tests.reports must be a nonempty list")
        for report in reports:
            relative_path(report)
            if report == ".":
                raise CheckError("JUnit report must name a file")
        if len(set(reports)) != len(reports):
            raise CheckError("Duplicate JUnit report paths")
    elif "report" in tests or "reports" in tests:
        raise CheckError("command format records execution/logs and does not consume a report")
    if "execution_links" in tests:
        links = tests["execution_links"]
        if (
            tests.get("format", "junit") != "junit"
            or not isinstance(links, dict)
            or {"format", "artifact_types"} - set(links)
            or set(links) - {"format", "artifact_types", "required_artifacts"}
            or links["format"] != "junit-properties-v1"
            or not isinstance(links["artifact_types"], list)
            or not links["artifact_types"]
            or any(
                not isinstance(kind, str) or not re.fullmatch(r"[A-Za-z]+", kind)
                for kind in links["artifact_types"]
            )
            or len(set(links["artifact_types"])) != len(links["artifact_types"])
        ):
            raise CheckError(
                "tests.execution_links requires JUnit, format junit-properties-v1, "
                "and a nonempty unique artifact_types list"
            )
        if "required_artifacts" in links:
            required_artifacts = links["required_artifacts"]
            if (
                not isinstance(required_artifacts, list)
                or not required_artifacts
                or any(
                    not isinstance(key, str)
                    or not re.fullmatch(r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*", key)
                    or key.split("~", 1)[0] not in links["artifact_types"]
                    for key in required_artifacts
                )
                or len(set(required_artifacts)) != len(required_artifacts)
            ):
                raise CheckError(
                    "tests.execution_links.required_artifacts must be a nonempty unique list "
                    "of named OFT keys (type~name, without revisions) of selected artifact types"
                )
    if type(tests["timeout_seconds"]) is not int or not 1 <= tests["timeout_seconds"] <= 86400:
        raise CheckError("tests.timeout_seconds must be between 1 and 86400")
    return scope
