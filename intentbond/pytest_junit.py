"""Opt-in pytest 9.1.1 JUnit adapter: one complete testcase per subtest report.

Load with ``-p intentbond.pytest_junit --junitxml=report.xml``. Pytest remains
the report producer; only its JUnit consumer receives distinct subtest IDs.
This uses pinned pytest internals and must be revalidated before upgrading.
"""

from collections import defaultdict
from copy import copy

import pytest

SUPPORTED_PYTEST = "9.1.1"


class SubtestXML:
    def __init__(self, original, subtest_type):
        self.original = original
        self.subtest_type = subtest_type
        self.counts = defaultdict(int)

    def __getattr__(self, name):
        # Pytest's property fixtures keep using the native writer through its stash.
        return getattr(self.original, name)

    # [impl->req~ib-pytest-subtests~1]
    def pytest_runtest_logreport(self, report):
        if not isinstance(report, self.subtest_type):
            self.original.pytest_runtest_logreport(report)
            return
        subtest = copy(report)
        key = (report.nodeid, getattr(report, "node", None))
        self.counts[key] += 1
        subtest.nodeid += f"::@intentbond-subtest-{self.counts[key]}"
        subtest.user_properties = [*report.user_properties, ("pytest.subtest", report.head_line)]
        self.original.pytest_runtest_logreport(subtest)
        # Subtests have a single call report, not their own setup/teardown cycle.
        # Close this case through the native writer, retaining its outcome,
        # captured output and properties. Other pytest consumers see no changes.
        closing = copy(subtest)
        closing.when = "teardown"
        closing.outcome = "passed"
        closing.longrepr = None
        closing.duration = 0
        self.original.pytest_runtest_logreport(closing)

    def pytest_collectreport(self, report):
        self.original.pytest_collectreport(report)

    def pytest_internalerror(self, excrepr):
        self.original.pytest_internalerror(excrepr)

    def pytest_sessionstart(self):
        self.original.pytest_sessionstart()

    def pytest_sessionfinish(self):
        self.original.pytest_sessionfinish()

    def pytest_terminal_summary(self, terminalreporter, config):
        self.original.pytest_terminal_summary(terminalreporter, config)


@pytest.hookimpl(trylast=True)
# [impl->req~ib-pytest-subtests~1]
def pytest_configure(config):
    if not config.option.xmlpath or hasattr(config, "workerinput"):
        return
    if pytest.__version__ != SUPPORTED_PYTEST:
        raise pytest.UsageError(
            f"intentbond.pytest_junit requires pytest {SUPPORTED_PYTEST}; "
            "revalidate the adapter before changing the producer version"
        )
    from _pytest.junitxml import xml_key
    from _pytest.subtests import SubtestReport

    original = config.stash[xml_key]
    adapter = SubtestXML(original, SubtestReport)
    config.pluginmanager.unregister(original)
    config.pluginmanager.register(adapter)
    config.stash[xml_key] = adapter
