"""Optional bounded-model checks using the unmodified Alloy 6.2 command line."""

import json
import os
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import CheckError, canonical, digest, read_json, relative_path, run, write_json

ALLOY_VERSION = "6.2.0"
ALLOY_SHA256 = "6b8c1cb5bc93bedfc7c61435c4e1ab6e688a242dc702a394628d9a9801edb78d"
ALLOY_URL = (
    "https://github.com/AlloyTools/org.alloytools.alloy/releases/download/"
    f"v{ALLOY_VERSION}/org.alloytools.alloy.dist.jar"
)


def default_jar():
    return Path(
        os.environ.get(
            "INTENTBOND_ALLOY_JAR",
            Path.home() / ".cache" / "intentbond" / f"alloy-{ALLOY_VERSION}.jar",
        )
    )


def validate_jar(jar):
    if digest(jar.read_bytes()) != ALLOY_SHA256:
        raise CheckError(f"Alloy checksum mismatch: expected {ALLOY_SHA256}")


def install_jar(destination):
    destination.mkdir(parents=True, exist_ok=True)
    jar = destination / f"alloy-{ALLOY_VERSION}.jar"
    if jar.exists():
        validate_jar(jar)
        return jar
    with urllib.request.urlopen(ALLOY_URL, timeout=60) as response:
        content = response.read()
    if digest(content) != ALLOY_SHA256:
        raise CheckError("Downloaded Alloy checksum does not match pinned release")
    with jar.open("xb") as output:
        output.write(content)
    return jar


def load_manifest(root, manifest):
    config = read_json(root / relative_path(manifest))
    if (
        not isinstance(config, dict)
        or type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
    ):
        raise CheckError("Expected Alloy manifest schema_version 1")
    model = relative_path(config["model"])
    inputs = config["inputs"]
    if not isinstance(inputs, list) or not inputs or any(not isinstance(p, str) for p in inputs):
        raise CheckError("Alloy inputs must be a nonempty list of relative files")
    inputs = sorted({relative_path(p) for p in inputs} | {manifest})
    if model not in inputs:
        raise CheckError("Alloy model must be included in inputs")
    for name in inputs:
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise CheckError(f"Alloy input must be a regular file inside root: {name}")
    timeout = config.get("timeout_seconds", 60)
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise CheckError("Alloy timeout_seconds must be an integer in 1..3600 per command")
    commands = config["commands"]
    if not isinstance(commands, list) or not commands:
        raise CheckError("Alloy commands must be a nonempty list")
    names = set()
    for command in commands:
        if not isinstance(command, dict):
            raise CheckError("Each Alloy command must be an object")
        name = command["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise CheckError("Use an exact named Alloy command; wildcards are not accepted")
        if name in names or command["kind"] not in {"run", "check"}:
            raise CheckError("Alloy command names must be unique and kinds must be run/check")
        names.add(name)
        artifact = command.get("artifact_id")
        if artifact is not None and (
            not isinstance(artifact, str)
            or not re.fullmatch(r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[1-9][0-9]*", artifact)
        ):
            raise CheckError("Invalid OFT artifact_id in Alloy manifest")
    if {c["kind"] for c in commands} != {"run", "check"}:
        raise CheckError("Include both assertion checks and satisfiable witness runs")
    if not isinstance(config.get("assumptions"), str) or not config["assumptions"].strip():
        raise CheckError("Document the model assumptions and implementation correspondence")
    return config, inputs, timeout


def interpret_receipt(receipt, command):
    """A successful process is insufficient: validate the exact completed command."""
    if not isinstance(receipt, dict):
        raise CheckError("Malformed Alloy receipt")
    commands = receipt.get("commands")
    name = command["name"]
    if not isinstance(commands, dict) or set(commands) != {name}:
        raise CheckError(f"Missing or unexpected Alloy command results for {name}")
    result = commands[name]
    if not isinstance(result, dict):
        raise CheckError("Malformed Alloy command result")
    if result.get("name") != name or result.get("type") != command["kind"]:
        raise CheckError(f"Alloy command identity/kind mismatch for {name}")
    if receipt.get("solver") != "sat4j":
        raise CheckError("Unexpected Alloy solver")
    if not isinstance(result.get("source"), str) or not result["source"].strip():
        raise CheckError("Missing native Alloy command and bounds")
    for field in ("bitwidth", "overall", "minprefix", "maxprefix", "maxseq"):
        if type(result.get(field)) is not int:
            raise CheckError(f"Missing native Alloy scope field: {field}")
    solutions = result.get("solution", [])  # Alloy omits this field for UNSAT.
    if not isinstance(solutions, list) or any(
        not isinstance(s, dict)
        or not isinstance(s.get("instances"), list)
        or not s["instances"]
        or any(not isinstance(instance, dict) for instance in s["instances"])
        for s in solutions
    ):
        raise CheckError("Malformed Alloy solutions")
    sat = bool(solutions)
    if command["kind"] == "check":
        outcome = "counterexample" if sat else "no_counterexample_within_bounds"
    else:
        outcome = "witness" if sat else "unsatisfiable_witness"
    return outcome


def write_junit(result, path):
    cases = result["commands"]
    suite = ET.Element(
        "testsuite",
        name="alloy",
        tests=str(len(cases)),
        failures=str(sum(c["status"] == "failed" for c in cases)),
        errors=str(sum(c["status"] == "error" for c in cases)),
    )
    metadata = {k: v for k, v in result.items() if k not in {"commands", "artifacts"}}
    for case in cases:
        element = ET.SubElement(suite, "testcase", classname="alloy", name=case["name"])
        properties = ET.SubElement(element, "properties")
        if case.get("artifact_id"):
            ET.SubElement(properties, "property", name="oft_id", value=case["artifact_id"])
        ET.SubElement(properties, "property", name="method", value="alloy-bounded-model-check")
        if case["status"] != "passed":
            ET.SubElement(
                element,
                "error" if case["status"] == "error" else "failure",
                message=case.get("error", case["outcome"]),
            )
        # ib already retains JUnit system-out. Include native receipts/traces so
        # deleting its temporary candidate cannot erase the counterexample.
        ET.SubElement(element, "system-out").text = json.dumps(
            {"evidence": metadata, "result": case}, sort_keys=True
        )
    ET.indent(suite)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def check_models(root, manifest, out, jar, java="java"):
    if out.is_symlink():
        raise CheckError("Alloy output must not be a symlink")
    root, out, jar = root.resolve(), out.resolve(), jar.resolve()
    config, inputs, timeout = load_manifest(root, manifest)
    validate_jar(jar)
    if any((root / name).resolve().is_relative_to(out) for name in inputs):
        raise CheckError("Alloy output must not contain the input files")
    # ib creates report parents before invoking the aggregate test command.
    # Accept that empty directory, but never reuse or overwrite prior evidence.
    if out.exists():
        if not out.is_dir() or any(out.iterdir()):
            raise FileExistsError(f"Alloy output must be new or empty: {out}")
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
        raise CheckError("Alloy manifest changed during input capture")
    inventory_log = out / "commands.log"
    inventory = run(
        [java, "-jar", str(jar), "commands", str(captured / config["model"])],
        captured,
        inventory_log,
        timeout,
    )
    listing = inventory_log.read_text(errors="replace")
    declarations = re.findall(
        r"^(\d+)\s*\.\s*(Check|Run)\s+([A-Za-z][A-Za-z0-9_]*)(?:\s|$)", listing, re.MULTILINE
    )
    result = {
        "schema_version": 1,
        "method": "alloy-bounded-model-check",
        "status": "error",
        "tool": {
            "version": ALLOY_VERSION,
            "sha256": ALLOY_SHA256,
            "solver": "sat4j",
            "no_overflow": False,
        },
        "inputs": hashes,
        "inputs_sha256": digest(canonical(hashes)),
        "model": config["model"],
        "assumptions": config["assumptions"],
        "correspondence": "reviewed abstraction and replay require separate evidence; no equivalence proof",
        "commands": [],
        "inventory": {**inventory, "output": listing},
    }
    for specification in config["commands"]:
        name = specification["name"]
        directory = out / "native" / name
        directory.parent.mkdir(parents=True, exist_ok=True)
        command = [
            java,
            "-jar",
            str(jar),
            "exec",
            "-q",
            "-s",
            "sat4j",
            "-t",
            "xml",
            "-r",
            "1",
            "-c",
            name,
            "-o",
            str(directory),
            str(captured / config["model"]),
        ]
        case = {**specification, "status": "error", "outcome": "error"}
        try:
            if inventory["status"] != "passed":
                raise CheckError(inventory.get("error", "Alloy could not list model commands"))
            matches = [d for d in declarations if d[2] == name]
            if len(matches) != 1 or matches[0][1].lower() != specification["kind"]:
                raise CheckError(
                    f"Expected exactly one {specification['kind']} named {name} in the model"
                )
            # Select the native index after checking uniqueness. Duplicate command
            # labels can otherwise overwrite entries in Alloy's receipt map.
            command[command.index("-c") + 1] = matches[0][0]
            execution = run(command, captured, out / f"{name}.log", timeout)
            case["execution"] = execution
            case["log"] = (out / f"{name}.log").read_text(errors="replace")
            if execution["status"] != "passed":
                raise CheckError(execution.get("error", f"Alloy exited {execution['exit_code']}"))
            receipt = read_json(directory / "receipt.json")
            case["receipt"] = receipt
            case["outcome"] = interpret_receipt(receipt, specification)
            case["status"] = (
                "passed"
                if case["outcome"] in {"witness", "no_counterexample_within_bounds"}
                else "failed"
            )
            case["solutions_xml"] = {p.name: p.read_text() for p in sorted(directory.glob("*.xml"))}
            if case["outcome"] in {"witness", "counterexample"} and not case["solutions_xml"]:
                raise CheckError("Alloy returned SAT without a retained XML instance")
        except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
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
