"""Optional Z3 checks with explicit assumptions and retained native queries."""

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .common import CheckError, canonical, digest, read_json, relative_path, run, write_json

Z3_PACKAGE_VERSION = "5.1.0.0"


@dataclass(frozen=True)
class Obligation:
    """Native Z3 expressions, authored by the application; no source translation."""

    assumptions: object
    goal: object
    observe: dict = field(default_factory=dict)
    kind: str = "check"


def load_manifest(root, manifest):
    config = read_json(root / manifest)
    if (
        not isinstance(config, dict)
        or type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
    ):
        raise CheckError("Expected SMT manifest schema_version 1")
    model = relative_path(config["model"])
    inputs = config["inputs"]
    if not isinstance(inputs, list) or not inputs or any(not isinstance(p, str) for p in inputs):
        raise CheckError("SMT inputs must be a nonempty list of relative files")
    inputs = sorted({relative_path(p) for p in inputs} | {manifest})
    if model not in inputs or not model.endswith(".py"):
        raise CheckError("Include the Python model in inputs")
    for name in inputs:
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise CheckError(f"SMT input must be a regular file inside root: {name}")
    timeout = config.get("timeout_seconds", 30)
    solver_timeout = config.get("solver_timeout_ms", 10000)
    for value, maximum, name in [
        (timeout, 3600, "timeout_seconds"),
        (solver_timeout, 3600000, "solver_timeout_ms"),
    ]:
        if type(value) is not int or not 1 <= value <= maximum:
            raise CheckError(f"{name} must be an integer in 1..{maximum}")
    if not isinstance(config.get("assumptions"), str) or not config["assumptions"].strip():
        raise CheckError("Document arithmetic semantics, assumptions, and scope")
    commands = config["commands"]
    if not isinstance(commands, list) or not commands:
        raise CheckError("SMT commands must be a nonempty list")
    names = set()
    for command in commands:
        if not isinstance(command, dict):
            raise CheckError("Each SMT command must be an object")
        name = command["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise CheckError("Use an exact named SMT obligation")
        if name in names or command["kind"] not in {"check", "run"}:
            raise CheckError("SMT command names must be unique and kinds must be check/run")
        names.add(name)
        artifact = command.get("artifact_id")
        if artifact is not None and (
            not isinstance(artifact, str)
            or not re.fullmatch(r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[1-9][0-9]*", artifact)
        ):
            raise CheckError("Invalid OFT artifact_id in SMT manifest")
    return config, inputs, timeout, solver_timeout


def interpret(receipt, command):
    if (
        not isinstance(receipt, dict)
        or receipt.get("name") != command["name"]
        or receipt.get("kind") != command["kind"]
    ):
        raise CheckError("Missing or mismatched SMT obligation identity/kind")
    if (
        not isinstance(receipt.get("tool"), dict)
        or receipt["tool"].get("package_version") != Z3_PACKAGE_VERSION
    ):
        raise CheckError("Unexpected Z3 package version")
    for name in ("preconditions", "query"):
        if name == "query" and receipt.get("preconditions", {}).get("result") != "sat":
            continue
        part = receipt.get(name)
        if not isinstance(part, dict) or part.get("result") not in {"sat", "unsat", "unknown"}:
            raise CheckError(f"Invalid SMT {name} result")
        if part["result"] == "sat" and (
            not isinstance(part.get("values"), dict) or not isinstance(part.get("model_smt2"), str)
        ):
            raise CheckError(f"Missing native SMT {name} model")
        if part["result"] == "unknown" and not isinstance(part.get("reason_unknown"), str):
            raise CheckError(f"Missing SMT {name} unknown reason")
    pre = receipt["preconditions"]["result"]
    if pre == "unsat":
        return "failed", "unsatisfiable_preconditions"
    if pre == "unknown":
        return "error", "unknown"
    if pre != "sat":
        raise CheckError("Invalid precondition result")
    query = receipt["query"]["result"]
    if query == "unknown":
        return "error", "unknown"
    if query not in {"sat", "unsat"}:
        raise CheckError("Invalid SMT query result")
    if command["kind"] == "check":
        return (
            ("passed", "proved_under_assumptions")
            if query == "unsat"
            else ("failed", "counterexample")
        )
    return ("passed", "witness") if query == "sat" else ("failed", "unsatisfiable_witness")


def write_junit(result, path):
    import json

    cases = result["commands"]
    suite_name = "z3-spacer" if result["method"] == "z3-spacer-check" else "z3"
    suite = ET.Element(
        "testsuite",
        name=suite_name,
        tests=str(len(cases)),
        failures=str(sum(c["status"] == "failed" for c in cases)),
        errors=str(sum(c["status"] == "error" for c in cases)),
    )
    metadata = {k: v for k, v in result.items() if k not in {"commands", "artifacts"}}
    for case in cases:
        element = ET.SubElement(suite, "testcase", classname=suite_name, name=case["name"])
        properties = ET.SubElement(element, "properties")
        if case.get("artifact_id"):
            ET.SubElement(properties, "property", name="oft_id", value=case["artifact_id"])
        ET.SubElement(properties, "property", name="method", value=result["method"])
        if case["status"] != "passed":
            ET.SubElement(
                element,
                "error" if case["status"] == "error" else "failure",
                message=case["outcome"],
            )
        # JSON escaping preserves native diagnostics without invalid XML controls.
        ET.SubElement(element, "system-out").text = json.dumps(
            {"evidence": metadata, "result": case}, sort_keys=True
        )
    ET.indent(suite)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def check_models(root, manifest, out, *, backend="smt"):
    if backend == "chc":
        from .chc import interpret as interpret_result
        from .chc import required_queries
    elif backend == "smt":
        interpret_result = interpret

        def required_queries(receipt):
            return (
                {"preconditions.smt2", "query.smt2"}
                if receipt["preconditions"]["result"] == "sat"
                else {"preconditions.smt2"}
            )
    else:
        raise CheckError(f"Unknown solver backend: {backend}")
    if out.is_symlink():
        raise CheckError("SMT output must not be a symlink")
    root, out = root.resolve(), out.resolve()
    manifest = relative_path(manifest)
    config, inputs, timeout, solver_timeout = load_manifest(root, manifest)
    if any((root / name).resolve().is_relative_to(out) for name in inputs):
        raise CheckError("SMT output must not contain input files")
    if out.exists():
        if not out.is_dir() or any(out.iterdir()):
            raise FileExistsError(f"SMT output must be new or empty: {out}")
    else:
        out.mkdir(parents=True)
    captured = out / "inputs"
    hashes = {}
    for name in inputs:
        target = captured / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
        hashes[name] = digest(target.read_bytes())
    if read_json(captured / manifest) != config:
        raise CheckError("SMT manifest changed during input capture")
    result = {
        "schema_version": 1,
        "method": "z3-spacer-check" if backend == "chc" else "z3-smt-check",
        "status": "error",
        "model": config["model"],
        "inputs": hashes,
        "inputs_sha256": digest(canonical(hashes)),
        "assumptions": config["assumptions"],
        "solver_timeout_ms": solver_timeout,
        "timeout_seconds": timeout,
        "correspondence": "Solver results establish only the encoding under its assumptions; source correspondence requires separate evidence",
        "commands": [],
    }
    # -I removes the caller's cwd/PYTHONPATH. Load this installed worker explicitly;
    # only the captured model directory/root are added for application imports.
    worker = str(
        Path(__file__).with_name("chc_worker.py" if backend == "chc" else "smt_worker.py").resolve()
    )
    for spec in config["commands"]:
        directory = out / spec["name"]
        directory.mkdir()
        case = {**spec, "status": "error", "outcome": "error"}
        execution = run(
            [
                sys.executable,
                "-I",
                "-B",
                worker,
                str(captured),
                config["model"],
                spec["name"],
                spec["kind"],
                str(directory),
                str(solver_timeout),
            ],
            captured,
            directory / "process.log",
            timeout,
        )
        case["execution"] = execution
        case["diagnostics"] = (directory / "process.log").read_text(errors="replace")
        try:
            if execution["status"] != "passed":
                raise CheckError(execution.get("error", "SMT worker failed; see diagnostics"))
            receipt = read_json(directory / "receipt.json")
            case["receipt"] = receipt
            case["status"], case["outcome"] = interpret_result(receipt, spec)
            required = required_queries(receipt)
            case["queries"] = {p.name: p.read_text() for p in directory.glob("*.smt2")}
            if not required <= case["queries"].keys():
                raise CheckError("Missing required native solver queries")
            if not all(case["queries"].values()):
                raise CheckError("Missing native SMT-LIB queries")
        except (CheckError, KeyError, TypeError, OSError, ValueError) as exc:
            case.update(status="error", outcome="error", error=str(exc))
        result["commands"].append(case)
    changed = []
    for name, sha in hashes.items():
        try:
            if (
                digest((root / name).read_bytes()) != sha
                or digest((captured / name).read_bytes()) != sha
            ):
                changed.append(name)
        except OSError:
            changed.append(name)
    if changed:
        for case in result["commands"]:
            case.update(
                status="error", outcome="error", error=f"Inputs changed during checking: {changed}"
            )
    result["status"] = (
        "error"
        if any(c["status"] == "error" for c in result["commands"])
        else "failed"
        if any(c["status"] == "failed" for c in result["commands"])
        else "passed"
    )
    write_junit(result, out / "junit.xml")
    result["artifacts"] = {
        str(p.relative_to(out)): digest(p.read_bytes())
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }
    write_json(out / "result.json", result)
    return result
