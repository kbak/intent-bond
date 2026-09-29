"""Real Alloy checks and failure semantics for the optional native runner."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from intentbond import alloy
from intentbond.common import CheckError, read_json, write_json, xml_tree
from intentbond.testing import junit_counts

FIXTURE = Path(__file__).resolve().parents[1] / "examples/model-checking"


class AlloyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jar = alloy.default_jar()
        # Optional for applications, explicitly provisioned for runner development.
        alloy.validate_jar(cls.jar)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ib-alloy-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project with spaces"
        shutil.copytree(FIXTURE, self.project)
        self.out = self.root / "evidence"

    def check(self):
        return alloy.check_models(self.project, "checks.json", self.out, self.jar)

    def configure(self, change):
        value = read_json(self.project / "checks.json")
        change(value)
        write_json(self.project / "checks.json", value)

    def test_completed_checks_and_self_contained_junit(self):
        result = self.check()
        # [utest->req~ib-alloy-assertions~1]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(
            [c["outcome"] for c in result["commands"]],
            ["no_counterexample_within_bounds", "witness"],
        )
        cases = list(xml_tree(self.out / "junit.xml").iter("testcase"))
        self.assertEqual(junit_counts(self.out / "junit.xml")["passed"], 2)
        embedded = json.loads(cases[1].findtext("system-out"))
        self.assertIn("ownership.als", embedded["evidence"]["inputs"])
        self.assertIn("<alloy", next(iter(embedded["result"]["solutions_xml"].values())))
        self.assertEqual(result["commands"][0]["receipt"]["commands"]["OwnerOnly"]["overall"], 3)
        with self.assertRaises(FileExistsError):
            self.check()

    def test_counterexample_is_a_failure_even_when_alloy_exits_zero(self):
        model = self.project / "ownership.als"
        model.write_text(model.read_text().replace("{ u = r.owner }", "{ some u and some r }"))
        result = self.check()
        # [utest->req~ib-alloy-assertions~1]
        self.assertEqual(result["status"], "failed")
        case = result["commands"][0]
        self.assertEqual(case["execution"]["exit_code"], 0)
        self.assertEqual(case["outcome"], "counterexample")
        self.assertTrue(case["solutions_xml"])
        self.assertEqual(junit_counts(self.out / "junit.xml")["failed"], 1)

    def test_precreated_report_parent_is_supported_without_overwriting_evidence(self):
        self.out.mkdir()
        self.assertEqual(self.check()["status"], "passed")
        with self.assertRaises(FileExistsError):
            self.check()

    def test_impossible_witness_is_not_vacuous_success(self):
        model = self.project / "ownership.als"
        model.write_text(model.read_text() + "\nfact empty { no Resource }\n")
        result = self.check()
        self.assertEqual(result["commands"][0]["outcome"], "no_counterexample_within_bounds")
        # [utest->req~ib-alloy-witness~1]
        self.assertEqual(result["commands"][1]["outcome"], "unsatisfiable_witness")
        self.assertEqual(result["status"], "failed")

    def test_missing_command_and_wrong_kind_are_errors(self):
        self.configure(lambda c: c["commands"][0].update(name="Absent"))
        self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "wrong-kind"
        self.configure(
            lambda c: c.update(
                commands=[
                    {"name": "CanAccess", "kind": "check"},
                    {"name": "OwnerOnly", "kind": "run"},
                ]
            )
        )
        self.assertEqual(self.check()["status"], "error")

    def test_invalid_model_produces_errors_and_reports(self):
        (self.project / "ownership.als").write_text("this is not Alloy")
        self.assertEqual(self.check()["status"], "error")
        self.assertEqual(junit_counts(self.out / "junit.xml")["errors"], 2)

    def test_duplicate_native_labels_cannot_hide_a_counterexample(self):
        model = self.project / "ownership.als"
        model.write_text(
            model.read_text().replace("{ u = r.owner }", "{ some u and some r }")
            + "\ncheck OwnerOnly for 0\n"
        )
        result = self.check()
        self.assertEqual(result["status"], "error")
        self.assertIn("exactly one", result["commands"][0]["error"])

    def test_undeclared_local_import_cannot_escape_input_capture(self):
        (self.project / "hidden.als").write_text("module hidden\nsig Hidden {}")
        model = self.project / "ownership.als"
        model.write_text(
            model.read_text().replace("module ownership", "module ownership\nopen hidden")
        )
        self.assertEqual(self.check()["status"], "error")

    def test_timeout_and_source_changes_are_never_passing(self):
        def fail(command, cwd, log, timeout):
            log.write_text("timeout")
            return {"status": "error", "error": "Command timed out", "exit_code": None}

        with patch.object(alloy, "run", side_effect=fail):
            self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "source-change"
        original = alloy.run

        def mutate(*args):
            result = original(*args)
            (self.project / "README.md").write_text("changed while checking")
            return result

        with patch.object(alloy, "run", side_effect=mutate):
            result = self.check()
        self.assertEqual(result["status"], "error")
        self.assertIn("Inputs changed", result["commands"][0]["error"])

    def test_manifest_rejects_missing_witness_and_traversal(self):
        self.configure(lambda c: c.update(commands=c["commands"][:1]))
        with self.assertRaises(CheckError):
            self.check()
        self.configure(lambda c: c.update(inputs=["../outside.als"]))
        with self.assertRaises(CheckError):
            self.check()

    def test_receipt_rejects_missing_results_malformed_solutions_and_wrong_solver(self):
        result = self.check()
        command = result["commands"][0]
        receipt = command["receipt"]
        for malformed in (None, [], {"commands": {"OwnerOnly": []}}):
            with self.assertRaises(CheckError):
                alloy.interpret_receipt(malformed, command)
        for change in (
            lambda r: r.update(commands={}),
            lambda r: r.update(solver="unrecognized"),
            lambda r: r["commands"]["OwnerOnly"].update(solution=[{}]),
            lambda r: r["commands"]["OwnerOnly"].pop("bitwidth"),
        ):
            changed = copy.deepcopy(receipt)
            change(changed)
            with self.assertRaises(CheckError):
                alloy.interpret_receipt(changed, command)
