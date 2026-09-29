"""Run stdlib unittest discovery with explicit, collection-time OFT identities.

Usage: python -m intentbond.unittest_junit --start tests --report results.xml
       [--links tests/oft-links.json] [--pattern test_*.py]
"""

import argparse
import json
import re
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


def cases(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from cases(test)
        else:
            yield test


def load_links(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate test identity: {key}")
            result[key] = value
        return result

    links = json.loads(Path(path).read_text(), object_pairs_hook=unique) if path else {}
    if not isinstance(links, dict):
        raise ValueError("Execution links must map unittest IDs to lists of OFT IDs")
    for name, refs in links.items():
        if (
            not name
            or not isinstance(refs, list)
            or not refs
            or any(
                not isinstance(ref, str)
                or not re.fullmatch(r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+", ref)
                for ref in refs
            )
            or len(set(refs)) != len(refs)
        ):
            raise ValueError(f"Invalid execution links for {name!r}")
    return links


# [impl->req~ib-unittest-evidence~1]
class JUnitResult(unittest.TextTestResult):
    """One case per collected method; subtest failures/skips affect that case.

    Class/module fixture failures also get their native synthetic error case.
    Collected methods which never start stay explicitly skipped, never passed.
    """

    def __init__(self, *args, collected, links, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = {}
        self.links = links
        for test in collected:
            name = test.id()
            if name in self.records:
                raise ValueError(f"Duplicate collected unittest identity: {name}")
            self.records[name] = {"outcomes": [("skipped", "Not executed")], "time": 0.0}

    def startTest(self, test):
        super().startTest(test)
        self.records[test.id()] = {"outcomes": [], "start": time.monotonic(), "time": 0.0}

    def stopTest(self, test):
        record = self.records[test.id()]
        record["time"] = time.monotonic() - record["start"]
        # An interrupted test may have started without any final outcome.
        if not record.get("finished") and not record["outcomes"]:
            record["outcomes"].append(("error", "Test interrupted without a final outcome"))
        super().stopTest(test)

    def outcome(self, test, kind, detail):
        record = self.records.setdefault(test.id(), {"outcomes": [], "time": 0.0})
        record["outcomes"].append((kind, detail))
        record["finished"] = True

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records[test.id()]["finished"] = True

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcome(test, "failure", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.outcome(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        # unittest calls addSkip with a _SubTest for skipped subtests.
        self.outcome(getattr(test, "test_case", test), "skipped", f"{test.id()}: {reason}")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcome(test, "skipped", "Expected failure: " + self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcome(test, "failure", "Unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            kind = "failure" if issubclass(err[0], test.failureException) else "error"
            self.outcome(test, kind, f"{subtest.id()}\n{self._exc_info_to_string(err, test)}")

    def write_report(self, path):
        suite = ET.Element("testsuite", name="unittest", tests=str(len(self.records)))
        counts = {"failure": 0, "error": 0, "skipped": 0}
        for name, record in self.records.items():
            classname, _, method = name.rpartition(".")
            case = ET.SubElement(
                suite,
                "testcase",
                classname=classname,
                name=method or name,
                time=str(record["time"]),
            )
            if name in self.links:
                properties = ET.SubElement(case, "properties")
                for ref in self.links[name]:
                    ET.SubElement(properties, "property", name="oft_id", value=ref)
            outcomes = record["outcomes"]
            if outcomes:
                # A failing subtest must not be hidden by another skipped subtest.
                kind = next(
                    k for k in ("error", "failure", "skipped") if any(o[0] == k for o in outcomes)
                )
                counts[kind] += 1
                ET.SubElement(case, kind).text = "\n".join(detail for _, detail in outcomes)
        for kind, attribute in (
            ("failure", "failures"),
            ("error", "errors"),
            ("skipped", "skipped"),
        ):
            suite.set(attribute, str(counts[kind]))
        # Never overwrite a previous run's result.
        with Path(path).open("xb") as output:
            ET.ElementTree(suite).write(output, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="tests")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--top-level")
    parser.add_argument("--report", required=True)
    parser.add_argument("--links")
    args = parser.parse_args(argv)
    links = load_links(args.links)
    suite = unittest.defaultTestLoader.discover(args.start, args.pattern, args.top_level)
    collected = list(cases(suite))
    unknown = links.keys() - {test.id() for test in collected}
    if unknown:
        raise ValueError("Execution links name uncollected tests: " + ", ".join(sorted(unknown)))
    report = Path(args.report)
    if report.exists() or report.is_symlink():
        raise FileExistsError(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    result = JUnitResult(
        unittest.runner._WritelnDecorator(sys.stderr), True, 2, collected=collected, links=links
    )
    runner = unittest.TextTestRunner(verbosity=2, resultclass=lambda *args: result)
    try:
        runner.run(suite)
    finally:
        result.write_report(report)
    return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__ == "__main__":
    sys.exit(main())
