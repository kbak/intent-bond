"""Check property-test sensitivity using six fixed source mutations.

Each mutation runs in a disposable source copy. The command fails if a mutation
survives or its test cannot run; it never modifies the source repository.
"""

import argparse
import ast
import difflib
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = [
    "test_snapshot_properties.py",
    "test_revision_properties.py",
    "test_lifecycle_properties.py",
]
SNAPSHOT = "tests/test_snapshot_properties.py::SnapshotPropertyTests::"
REVISION = "tests/test_revision_properties.py::RevisionPropertyTests::"
MUTATIONS = [
    (
        "omit-untracked-source",
        "snapshot.py",
        '"--cached", "--others", "--exclude-standard"',
        '"--cached", "--exclude-standard"',
        SNAPSHOT + "test_git_and_archive_agree_before_and_after_staging",
    ),
    (
        "discard-executable-mode",
        "snapshot.py",
        'return "100755" if info.st_mode & stat.S_IXUSR else "100644", path.read_bytes()',
        'return "100644", path.read_bytes()',
        SNAPSHOT + "test_path_bytes_and_mode_each_change_identity_and_restore_exactly",
    ),
    (
        "ignore-path-in-identity",
        "snapshot.py",
        "return digest(canonical(self.manifest))",
        'return digest(canonical(sorted(entry["sha256"] for entry in self.manifest)))',
        SNAPSHOT + "test_path_bytes_and_mode_each_change_identity_and_restore_exactly",
    ),
    (
        "allow-unversioned-meaning-change",
        "review.py",
        'new["revision"] <= old["revision"]',
        'new["revision"] < old["revision"]',
        REVISION + "test_changed_promise_remains_reviewable_and_needs_higher_revision",
    ),
    (
        "hide-removed-requirement",
        "review.py",
        "old.keys() | new.keys()",
        "new.keys()",
        REVISION + "test_removal_cannot_disappear_from_review",
    ),
    (
        "accept-stale-evidence",
        "runner.py",
        'if current.sha256 != evidence["candidate"]["sha256"]:',
        "if False:",
        "tests/test_lifecycle_properties.py::LifecycleRegressionTests::test_edit_stage_commit_restore_and_revision",
    ),
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_tests(source, output, selectors, env):
    output.mkdir()
    command = [
        sys.executable,
        "-m",
        "pytest",
        *selectors,
        "-p",
        "no:cacheprovider",
        "-p",
        "hypothesispytest",
        "--hypothesis-show-statistics",
        "-q",
        f"--junitxml={output / 'tests.xml'}",
    ]
    with (output / "tests.log").open("w") as log:
        try:
            result = subprocess.run(
                command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = None
    cases = []
    if (output / "tests.xml").exists():
        tree = ET.parse(output / "tests.xml")
        cases = list(tree.iter("testcase"))
    failures = [case for case in cases if case.find("failure") is not None]
    errors = [case for case in cases if case.find("error") is not None]
    skipped = [case for case in cases if case.find("skipped") is not None]
    # A timeout, collection error or unrelated exception is an evaluation error,
    # not evidence that a property detected the injected behavioral defect.
    detected = (
        code == 1
        and failures
        and not errors
        and not skipped
        and all("AssertionError" in ET.tostring(case, encoding="unicode") for case in failures)
    )
    passed = code == 0 and cases and not failures and not errors and not skipped
    return {
        "status": "detected" if detected else "passed" if passed else "error",
        "exit_code": code,
        "cases": len(cases),
        "failures": len(failures),
        "errors": len(errors),
        "command": command,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, required=True, help="New directory for retained results"
    )
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        HYPOTHESIS_STORAGE_DIRECTORY=str(output / "hypothesis-cache"),
    )
    local_jar = ROOT / ".tools/openfasttrace-4.9.0.jar"
    if "INTENTBOND_OFT_JAR" not in env and local_jar.exists():
        env["INTENTBOND_OFT_JAR"] = str(local_jar)
    results = {
        "python": platform.python_version(),
        "libraries": {
            name: importlib.metadata.version(name)
            for name in ("pytest", "hypothesis", "junitparser")
        },
        "mutations": [],
    }
    with tempfile.TemporaryDirectory(prefix="ib-property-evaluation-") as directory:
        source = Path(directory) / "source"
        source.mkdir()
        for name in ("intentbond", "examples/session"):
            shutil.copytree(
                ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        (source / "tests").mkdir()
        for name in TEST_FILES:
            shutil.copyfile(ROOT / "tests" / name, source / "tests" / name)
        manifest = [
            {
                "path": path.relative_to(source).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(source.rglob("*"))
            if path.is_file()
        ]
        write_json(output / "source-manifest.json", manifest)
        results["baseline"] = run_tests(
            source, output / "baseline", ["tests/" + name for name in TEST_FILES], env
        )
        write_json(output / "results.json", results)
        if results["baseline"]["status"] != "passed":
            print(f"Baseline failed; see {output / 'baseline/tests.log'}", flush=True)
            return 1
        for name, filename, before, after, selector in MUTATIONS:
            path = source / "intentbond" / filename
            original = path.read_text()
            if original.count(before) != 1:
                raise RuntimeError(
                    f"Update stale mutation {name}: expected one matching source fragment"
                )
            mutated = original.replace(before, after)
            ast.parse(mutated)
            (output / f"{name}.patch").write_text(
                "".join(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        mutated.splitlines(keepends=True),
                        fromfile=filename,
                        tofile=filename,
                    )
                )
            )
            try:
                path.write_text(mutated)
                result = run_tests(source, output / name, [selector], env)
            finally:
                path.write_text(original)
            if result["status"] == "passed":
                result["status"] = "survived"
            results["mutations"].append({"name": name, "file": filename, **result})
            write_json(output / "results.json", results)
            print(f"{name}: {result['status']}", flush=True)
    return 0 if all(item["status"] == "detected" for item in results["mutations"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
