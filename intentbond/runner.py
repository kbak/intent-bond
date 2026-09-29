import platform
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, boundaries
from .common import CheckError, canonical, digest, read_json, within, write_json, xml_tree
from .config import load_baseline_scope, load_scope
from .evidence import check_artifacts, read_statement, statement, test_statement
from .execution import (
    collect_execution_links,
    required_execution_diagnostics,
    retained_execution_links,
)
from .impact import source_changes
from .oft import OFT_SHA256, OFT_VERSION, policy_diagnostics, trace, validate_jar
from .review import changes, review_diff, review_record, revision_diagnostics
from .snapshot import changed_source, repository, resolve_commit, snapshot
from .summary import render_summary
from .testing import counts_pass, execute_tests, junit_counts, merge_reports


def source_digest():
    return digest(
        canonical(
            {p.name: digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))}
        )
    )


def check(
    repo_path, scope_path, base_ref, candidate_ref, out, jar, java="java", *, preflight=False
):
    out = out.resolve()
    if out.is_relative_to(repo_path.resolve()):
        raise CheckError("Evidence output must be outside the checked repository")
    out.mkdir(parents=True, exist_ok=False)
    evidence = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "error",
        "diagnostics": [],
        "runner": {
            "version": __version__,
            "source_sha256": source_digest(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "oft": {"version": OFT_VERSION, "sha256": OFT_SHA256},
        "requested": {
            "repo": str(repo_path.resolve()),
            "base": base_ref,
            "candidate": candidate_ref,
        },
        "tests": {"status": "not_run", "level": "suite", "source_status": "unchecked"},
        "limitations": [
            "Structural tracing and suite results do not prove requirement satisfaction or assertion adequacy.",
            "Caller supplies trusted scope; changed specifications/tests require external review. Evidence is unsigned.",
            "Source identity excludes ignored untracked files, Git metadata, external dependencies, and environment inputs.",
        ],
    }
    changed = None
    try:
        repo = repository(repo_path)
        base_ref = resolve_commit(repo, base_ref)
        # [impl->req~ib-policy-source~1]
        scope = (
            load_scope(scope_path)
            if scope_path is not None
            else load_baseline_scope(repo, base_ref)
        )
        scope_sha256 = digest(canonical(scope))
        evidence["scope"] = {"name": scope["name"], "sha256": scope_sha256, "configuration": scope}
        write_json(out / "scope.json", scope)
        jar = jar.resolve()
        validate_jar(jar)
        with tempfile.TemporaryDirectory(prefix="ib-check-") as directory:
            scratch = Path(directory)
            base = snapshot(repo, base_ref, scratch / "base")
            candidate = snapshot(repo, candidate_ref, scratch / "candidate")
            evidence["base"] = base.identity()
            evidence["candidate"] = candidate.identity()
            (out / "base-manifest.json").write_bytes(canonical(base.manifest))
            (out / "candidate-manifest.json").write_bytes(canonical(candidate.manifest))
            evidence["source_boundaries"] = boundaries.inventory(
                base.manifest, candidate.manifest, scope
            )
            # [impl->req~ib-coverage~1]
            before, base_trace = trace(base, scope, jar, java, out, "base")
            after, candidate_trace = trace(candidate, scope, jar, java, out, "candidate")
            evidence["trace"] = {"base": base_trace, "candidate": candidate_trace}
            old_requirements, base_problems = policy_diagnostics(before, scope, "base")
            new_requirements, candidate_problems = policy_diagnostics(after, scope, "candidate")
            evidence["requirements"] = {"base": old_requirements, "candidate": new_requirements}
            problems = evidence["diagnostics"]
            problems.extend(base_problems + candidate_problems)
            if base_trace["status"] != "passed":
                problems.append(
                    "Inherited baseline trace defects; see base-trace.log. Establish a clean bounded baseline."
                )
            if candidate_trace["status"] != "passed":
                problems.append("Candidate trace defects; see candidate-trace.log")
            # Compare all authored specification artifacts, including intermediate
            # OFT chains, while OFT remains responsible for graph validity.
            changed = changes(
                base,
                candidate,
                [i for i in before if within(i["path"], scope["specification_paths"])],
                [i for i in after if within(i["path"], scope["specification_paths"])],
                scope,
            )
            review = review_record(base, candidate, scope_sha256, changed)
            review["source_boundaries"] = evidence["source_boundaries"]
            review["source_changes"] = source_changes(base, candidate, before, after, scope)
            write_json(out / "review.json", review)
            (out / "review.patch").write_text(
                review_diff(base, candidate, changed), encoding="utf-8"
            )
            evidence["review"] = {
                "changes_sha256": review["changes_sha256"],
                "change_count": len(changed),
                "status": "required" if changed else "not_needed",
            }
            problems.extend(revision_diagnostics(changed, scope))
            empty = not new_requirements
            if not old_requirements and not (empty and scope.get("allow_empty", False)):
                problems.append(
                    "Baseline has no selected requirements; establish a clean baseline before validation"
                )
            # [impl->req~ib-empty-scope~1]
            if empty:
                if not scope.get("allow_empty", False):
                    problems.append("Candidate has no selected requirements")
                evidence["status"] = "rejected" if problems else "empty"
            # [impl->req~ib-recovery-preflight~1]
            elif preflight:
                evidence["status"] = "rejected" if problems else "incomplete"
            else:
                # Run tests even when tracing/policy fails, to provide useful repair evidence.
                evidence["tests"] = {
                    **execute_tests(candidate, scope, out),
                    "source_status": "unchecked",
                }
                if evidence["tests"]["status"] != "passed":
                    problems.append("Test execution did not pass; see tests.log and test outcome")
                if "execution_links" in scope["tests"] and "counts" in evidence["tests"]:
                    links = collect_execution_links(out / "tests.xml", after, scope)
                    evidence["tests"]["execution_links"] = links
                    problems.extend(links["diagnostics"])
                    problems.extend(required_execution_diagnostics(links, scope))
                # [impl->req~ib-source-stability~1]
                mutated = changed_source(candidate)
                if mutated:
                    problems.append("Test command modified captured source: " + ", ".join(mutated))
                evidence["tests"]["source_status"] = "changed" if mutated else "matched"
                evidence["status"] = (
                    "rejected" if problems else ("review_required" if changed else "passed")
                )
            current = snapshot(repo, candidate_ref, scratch / "current")
            if current.sha256 != candidate.sha256 or current.commit != candidate.commit:
                problems.append(
                    "Original candidate changed during validation; rerun on current contents"
                )
                evidence["status"] = "rejected"
                evidence["tests"]["source_status"] = "changed"
    except (CheckError, OSError, ValueError) as exc:
        evidence["status"] = "error"
        evidence["diagnostics"].append(str(exc))
        evidence["tests"]["source_status"] = "unchecked"
    # [impl->req~ib-source-stability~1]
    if evidence["tests"]["status"] != "not_run" and evidence["tests"]["source_status"] == "matched":
        write_json(
            out / "test-result.json",
            test_statement(evidence, digest((out / "scope.json").read_bytes())),
        )
    (out / "summary.md").write_text(
        render_summary(evidence, changed, {path.name for path in out.iterdir()})
    )
    evidence["artifacts"] = {
        path.name: digest(path.read_bytes()) for path in sorted(out.iterdir()) if path.is_file()
    }
    write_json(out / "evidence.json", statement(evidence))
    return evidence


# [impl->req~ib-evidence-verification~1]
def verify(
    repo_path, scope_path, base_ref, candidate_ref, evidence_path, allow_pending_review=False
):
    evidence = read_statement(read_json(evidence_path))
    if (
        not isinstance(evidence, dict)
        or type(evidence.get("schema_version")) is not int
        or evidence["schema_version"] != 2
    ):
        raise CheckError("Unsupported evidence schema")
    acceptable = {"passed", "review_required"} if allow_pending_review else {"passed"}
    if evidence.get("status") not in acceptable:
        raise CheckError("Evidence does not record a successful check")
    try:
        if (
            evidence["oft"] != {"version": OFT_VERSION, "sha256": OFT_SHA256}
            or not evidence["runner"]["source_sha256"]
        ):
            raise CheckError("Evidence tool identity is missing or incompatible")
        if (
            evidence["diagnostics"]
            or evidence["tests"]["status"] != "passed"
            or evidence["tests"]["exit_code"] != 0
            or evidence["tests"]["source_status"] != "matched"
        ):
            raise CheckError("Evidence contains nonpassing or incomplete test/diagnostic outcomes")
        for label in ("base", "candidate"):
            traced = evidence["trace"][label]
            if (
                traced["status"] != "passed"
                or traced["import"]["exit_code"] != 0
                or traced["trace"]["exit_code"] != 0
            ):
                raise CheckError("Evidence contains nonpassing trace outcomes")
            if not evidence["requirements"][label]:
                raise CheckError("Passing evidence has no selected requirements")
    except (KeyError, TypeError) as exc:
        raise CheckError("Evidence outcome fields are incomplete or malformed") from exc
    directory = evidence_path.resolve().parent
    required = {
        "scope.json",
        "base-manifest.json",
        "candidate-manifest.json",
        "review.json",
        "base-items.xml",
        "candidate-items.xml",
        "base-trace.log",
        "candidate-trace.log",
        "base-import.log",
        "candidate-import.log",
        "review.patch",
        "tests.log",
        "test-result.json",
    }
    repo = repository(repo_path)
    base_commit = resolve_commit(repo, base_ref)
    # [impl->req~ib-policy-source~1]
    scope = (
        load_scope(scope_path) if scope_path is not None else load_baseline_scope(repo, base_commit)
    )
    if scope["tests"].get("format", "junit") == "junit":
        required.add("tests.xml")
    reports = [
        {"source": name, "artifact": f"tests-{index}.xml"}
        for index, name in enumerate(scope["tests"].get("reports", []), 1)
    ]
    required.update(r["artifact"] for r in reports)
    artifacts = check_artifacts(evidence, directory, required)
    test_format = scope["tests"].get("format", "junit")
    if (
        evidence["tests"].get("format") != test_format
        or evidence["tests"].get("command") != scope["tests"]["command"]
    ):
        raise CheckError("Test execution differs from configured command/format")
    if test_format == "junit":
        if reports:
            if evidence["tests"].get("reports") != reports:
                raise CheckError("Retained JUnit reports differ from configured paths")
            # [impl->req~ib-report-merge~1]
            merged = merge_reports((r["source"], directory / r["artifact"]) for r in reports)
            if ET.tostring(merged) != ET.tostring(xml_tree(directory / "tests.xml")):
                raise CheckError("Combined JUnit report differs from retained individual reports")
        counts = junit_counts(directory / "tests.xml")
        if counts != evidence["tests"].get("counts") or not counts_pass(counts, scope):
            raise CheckError("Retained test report does not support passing evidence")
    links = retained_execution_links(evidence, directory, scope)
    if links is not None and links["status"] != "recorded":
        raise CheckError("Retained evidence contains invalid execution links")
    if links is not None:
        # [impl->req~ib-required-execution~1]
        required_problems = required_execution_diagnostics(links, scope)
        if required_problems:
            raise CheckError(
                "Retained evidence fails required execution: " + "; ".join(required_problems)
            )
    if read_json(directory / "test-result.json") != test_statement(
        evidence, artifacts["scope.json"]
    ):
        raise CheckError("Test attestation does not match the retained test outcome")
    review = read_json(directory / "review.json")
    if not isinstance(review, dict) or not isinstance(review.get("changes"), list):
        raise CheckError("Malformed retained review record")
    if digest(canonical(review["changes"])) != review.get("changes_sha256"):
        raise CheckError("Review change digest does not match retained changes")
    try:
        expected_review = {
            "schema_version": 1,
            "base_commit": evidence["base"]["commit"],
            "base_sha256": evidence["base"]["sha256"],
            "candidate_sha256": evidence["candidate"]["sha256"],
            "scope_sha256": evidence["scope"]["sha256"],
            "changes_sha256": evidence["review"]["changes_sha256"],
        }
        if any(review.get(key) != value for key, value in expected_review.items()) or evidence[
            "review"
        ]["change_count"] != len(review["changes"]):
            raise CheckError("Review binding does not match evidence")
        # [impl->req~ib-change-review~1]
        expected_status = "review_required" if review["changes"] else "passed"
        expected_review_status = "required" if review["changes"] else "not_needed"
        if (
            evidence["status"] != expected_status
            or evidence["review"]["status"] != expected_review_status
        ):
            raise CheckError("Evidence does not preserve pending change review")
    except (KeyError, TypeError) as exc:
        raise CheckError("Evidence review fields are incomplete or malformed") from exc
    if (
        digest(canonical(scope)) != evidence["scope"]["sha256"]
        or read_json(directory / "scope.json") != scope
    ):
        raise CheckError("Scope differs from checked policy")
    if base_commit != evidence["base"]["commit"]:
        raise CheckError("Base differs from the checked baseline")
    for label in ("base", "candidate"):
        if (
            digest(canonical(read_json(directory / f"{label}-manifest.json")))
            != evidence[label]["sha256"]
        ):
            raise CheckError(f"{label} manifest does not match evidence identity")
    boundaries.retained(evidence, directory, scope)
    with tempfile.TemporaryDirectory(prefix="ib-verify-") as directory:
        current = snapshot(repo, candidate_ref, Path(directory) / "candidate")
        if current.sha256 != evidence["candidate"]["sha256"]:
            raise CheckError("Candidate contents differ from tested evidence; rerun checks")
    return {
        "status": "matched",
        "review": evidence["review"]["status"],
        "candidate": current.identity(),
        "evidence": str(evidence_path.resolve()),
    }
