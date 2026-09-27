"""Concise CLI feedback; the retained evidence remains the complete record."""

from junitparser import JUnitXmlError

from . import boundaries
from .common import CheckError, xml_tree
from .testing import report_cases


def _excerpt(value, limit):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "… [excerpt]"


def _failure_lines(out):
    try:
        failures = [
            case
            for case in report_cases(xml_tree(out / "tests.xml"))
            if case.is_failure or case.is_error
        ]
        if failures:
            lines = ["Reported failures (excerpt; full details in test report):"]
            for case in failures[:3]:
                name = "::".join(part for part in (case.classname, case.name) if part)
                detail = "\n".join(
                    "\n".join(part for part in (result.message, result.text) if part)
                    for result in case.result
                )
                lines.append(f"  {_excerpt(name, 180)}: {_excerpt(detail, 650)}")
            if len(failures) > 3:
                lines.append(f"  {len(failures) - 3} more failing cases in test report")
            return lines
    except (CheckError, JUnitXmlError, ValueError, TypeError):
        pass  # Missing or malformed reports cannot replace the recorded check outcome.
    try:
        with (out / "tests.log").open("rb") as log:
            log.seek(0, 2)
            log.seek(max(0, log.tell() - 1800))
            tail = log.read().decode("utf-8", errors="replace")
        if tail.strip():
            return ["Test log excerpt (last 1800 bytes, up to 24 lines):", *tail.splitlines()[-24:]]
    except OSError:
        pass
    return []


def render_check(result, out):
    out = out.resolve()
    lines = [f"{result['status']}: {out / 'evidence.json'}"]
    if "base" in result:
        lines.append(f"baseline: {result['base']['commit']}")
    if "candidate" in result:
        lines.append(f"source: {result['candidate']['sha256']}")
    tests = result["tests"]
    lines.append(f"tests: {tests['status']} ({tests['level']}); source={tests['source_status']}")
    if "counts" in tests:
        lines.append("counts: " + ", ".join(f"{k}={v}" for k, v in tests["counts"].items()))
    if "error" in tests:
        lines.append("test error: " + _excerpt(tests["error"], 600))
    review = result.get("review", {})
    lines.append(
        f"specification/test review: {review.get('status', 'not_recorded')}"
        f"; changes={review.get('change_count', 'unknown')}"
    )
    lines.extend(boundaries.lines(result.get("source_boundaries")))
    diagnostics = result["diagnostics"]
    lines.extend("- " + _excerpt(message, 600) for message in diagnostics[:5])
    if len(diagnostics) > 5:
        lines.append(f"- {len(diagnostics) - 5} more diagnostics in evidence.json")
    for name in (
        "review.json",
        "review.patch",
        "base-import.log",
        "candidate-import.log",
        "base-trace.log",
        "candidate-trace.log",
        "tests.xml",
        "tests.log",
    ):
        if name in result.get("artifacts", {}):
            lines.append(f"{name}: {out / name}")
    if tests["status"] in {"failed", "error"}:
        lines.extend(_failure_lines(out))
    if result["status"] == "review_required":
        lines.append("Automated checks passed; external specification/test review is required.")
    lines.append(
        "Review the full candidate diff and linked behavior; checks do not prove conformance."
    )
    return "\n".join(lines)
