"""Application replay failures remain visible in native and JUnit evidence."""

import tempfile
import unittest
from pathlib import Path

from intentbond.common import read_json, xml_tree
from intentbond.model_evidence import ReplayEvidence
from intentbond.testing import junit_counts


class ReplayEvidenceTests(unittest.TestCase):
    def test_success_metadata_snapshots_and_native_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "evidence"
            with self.assertRaisesRegex(RuntimeError, "native"):
                with ReplayEvidence(out) as report:
                    report.metadata["inputs_sha256"] = "original"
                    result = report.record("success", lambda: {"accepted": True}, "itest~replay~1")
                    self.assertTrue(result["accepted"])
                    report.metadata["inputs_sha256"] = "changed"

                    def failure():
                        raise RuntimeError("native\x1b[31m\x00 failure")

                    report.record("failure", failure, "itest~replay~1")
            counts = junit_counts(out / "junit.xml")
            self.assertEqual((counts["passed"], counts["errors"]), (1, 1))
            cases = read_json(out / "result.json")["cases"]
            self.assertEqual(cases[0]["properties"]["inputs_sha256"], "original")
            self.assertIn("\x1b", cases[1]["error"])
            linked = list(xml_tree(out / "junit.xml").iter("property"))
            self.assertEqual(sum(p.get("name") == "oft_id" for p in linked), 2)
            with self.assertRaises(FileExistsError):
                ReplayEvidence(out)

    def test_failure_between_recorded_actions_is_not_a_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "evidence"
            with self.assertRaises(ValueError):
                with ReplayEvidence(out) as report:
                    report.record("setup", lambda: "done")
                    raise ValueError("missing required witness")
            counts = junit_counts(out / "junit.xml")
            self.assertEqual(counts["errors"], 1)
            self.assertEqual(read_json(out / "result.json")["cases"][-1]["name"], "pipeline")
