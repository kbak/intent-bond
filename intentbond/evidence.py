"""Unsigned in-toto statements; no signing, transport, or approval framework."""

from .common import CheckError, digest, relative_path

EXIT_CODES = {
    "passed": 0,
    "rejected": 1,
    "error": 2,
    "empty": 3,
    "review_required": 4,
    "incomplete": 5,
}

STATEMENT = "https://in-toto.io/Statement/v1"
CHECK_TYPE = "https://github.com/kbak/intentbond/check/v0.2"
TEST_TYPE = "https://in-toto.io/attestation/test-result/v0.1"


def check_artifacts(evidence, directory, required):
    """Match bundle files to recorded hashes; producer trust remains external."""
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict) or not set(required).issubset(artifacts):
        raise CheckError("Evidence artifact inventory is incomplete")
    for name, expected in artifacts.items():
        relative_path(name)
        path = directory / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(directory)
            or digest(path.read_bytes()) != expected
        ):
            raise CheckError(f"Evidence artifact missing or changed: {name}")
    return artifacts


def statement(predicate, predicate_type=CHECK_TYPE):
    candidate = predicate.get("candidate")
    return {
        "_type": STATEMENT,
        "subject": (
            [{"name": "candidate-manifest.json", "digest": {"sha256": candidate["sha256"]}}]
            if candidate
            else []
        ),
        "predicateType": predicate_type,
        "predicate": predicate,
    }


def read_statement(value):
    if (
        not isinstance(value, dict)
        or value.get("_type") != STATEMENT
        or value.get("predicateType") != CHECK_TYPE
        or not isinstance(value.get("predicate"), dict)
    ):
        raise CheckError("Unsupported traceability statement")
    evidence = value["predicate"]
    if value.get("subject") != statement(evidence)["subject"]:
        raise CheckError("Statement subject differs from checked candidate")
    return evidence


def test_statement(evidence, scope_digest):
    if evidence["tests"].get("source_status") != "matched":
        raise CheckError("Cannot attest a test result without matching stable source")
    value = statement(evidence, TEST_TYPE)
    value["predicate"] = {
        "result": "PASSED" if evidence["tests"]["status"] == "passed" else "FAILED",
        "configuration": [{"name": "scope.json", "digest": {"sha256": scope_digest}}],
    }
    return value
