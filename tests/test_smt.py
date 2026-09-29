"""Real solver checks, native evidence retention, and fail-closed outcomes."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import z3

from intentbond import cli, smt
from intentbond.common import read_json, write_json, xml_tree
from intentbond.testing import junit_counts

FIXTURE = Path(__file__).resolve().parents[1] / "examples/smt-checking"


class SmtTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="ib-smt-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.project = self.root / "project with spaces"
        shutil.copytree(FIXTURE, self.project)
        self.out = self.root / "evidence"

    def check(self):
        return smt.check_models(self.project, "checks.json", self.out)

    def change(self, before, after):
        path = self.project / "amounts.py"
        path.write_text(path.read_text().replace(before, after))

    def configure(self, change):
        config = read_json(self.project / "checks.json")
        change(config)
        write_json(self.project / "checks.json", config)

    def test_real_proof_witness_and_retained_queries(self):
        self.out.mkdir()  # ib precreates report parents.
        result = self.check()
        # [utest->req~ib-smt-outcomes~1]
        self.assertEqual(result["status"], "passed")
        self.assertFalse(list((self.out / "inputs").rglob("__pycache__")))
        self.assertEqual(
            [c["outcome"] for c in result["commands"]], ["proved_under_assumptions", "witness"]
        )
        case = result["commands"][1]
        values = case["receipt"]["query"]["values"]
        self.assertEqual(
            int(values["amount"]["value"]),
            int(values["requested"]["value"]) + int(values["remainder"]["value"]),
        )
        # Re-execute the actual SMT-LIB, independently of the Python authoring API.
        solver = z3.Solver()
        solver.from_string(result["commands"][0]["queries"]["query.smt2"])
        self.assertEqual(solver.check(), z3.unsat)
        cases = list(xml_tree(self.out / "junit.xml").iter("testcase"))
        embedded = json.loads(cases[1].findtext("system-out"))
        self.assertEqual(embedded["result"]["queries"], case["queries"])
        self.assertIn("amounts.py", embedded["evidence"]["inputs"])
        self.assertEqual(junit_counts(self.out / "junit.xml")["passed"], 2)
        with self.assertRaises(FileExistsError):
            self.check()

    def test_counterexample_is_failure_even_when_worker_succeeds(self):
        self.change("amount - requested", "amount")
        result = self.check()
        case = result["commands"][0]
        # [utest->req~ib-smt-outcomes~1]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(case["execution"]["exit_code"], 0)
        self.assertEqual(case["outcome"], "counterexample")
        self.assertGreater(int(case["receipt"]["query"]["values"]["requested"]["value"]), 0)

    def test_unsatisfiable_preconditions_cannot_prove_anything(self):
        self.change("amount >= 0, requested >= 0", "amount >= 0, amount < 0")
        result = self.check()
        # [utest->req~ib-smt-assumptions~1]
        self.assertEqual(
            [c["outcome"] for c in result["commands"]], ["unsatisfiable_preconditions"] * 2
        )
        self.assertEqual(junit_counts(self.out / "junit.xml")["failed"], 2)

    def test_unsatisfiable_witness_fails_without_rejecting_valid_proof(self):
        self.change("requested > 0, remainder > 0", "requested < 0, remainder > 0")
        # [utest->req~ib-smt-outcomes~1]
        self.assertEqual(
            [c["outcome"] for c in self.check()["commands"]],
            ["proved_under_assumptions", "unsatisfiable_witness"],
        )

    def test_missing_wrong_kind_and_invalid_models_fail(self):
        self.configure(lambda c: c["commands"][0].update(name="Absent"))
        self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "wrong-kind"
        self.configure(lambda c: c["commands"][0].update(name="CanSplit", kind="check"))
        self.configure(lambda c: c.update(commands=c["commands"][:1]))
        self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "invalid"
        (self.project / "amounts.py").write_text("not valid python !")
        self.assertEqual(self.check()["status"], "error")

    def test_python_boolean_is_not_a_symbolic_goal(self):
        self.change("Implies(accepted, requested + remainder == amount)", "True")
        self.assertEqual(self.check()["commands"][0]["status"], "error")

    def test_model_construction_is_bounded_by_process_timeout(self):
        self.configure(lambda c: c.update(timeout_seconds=1, commands=c["commands"][:1]))
        self.change("def obligations():", "def obligations():\n    while True:\n        pass")
        result = self.check()
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["commands"][0]["error"])

    def test_unknown_is_inconclusive_with_reason_retained(self):
        # A native, deterministic unknown (incomplete nonlinear arithmetic).
        (self.project / "amounts.py").write_text(
            "from z3 import *\nfrom intentbond.smt import Obligation\n"
            "def obligations():\n"
            " x = Real('x')\n"
            " return {'Conservation': Obligation(BoolVal(True), x ** x != 2)}\n"
        )
        self.configure(lambda c: c.update(commands=c["commands"][:1]))
        case = self.check()["commands"][0]
        # [utest->req~ib-smt-outcomes~1]
        self.assertEqual(case["outcome"], "unknown")
        self.assertEqual(case["status"], "error")
        self.assertTrue(case["receipt"]["query"]["reason_unknown"])

    def test_missing_local_import_is_not_loaded_from_original_checkout(self):
        (self.project / "local_unlisted.py").write_text("amount = 1")
        self.change(
            '"""Native Z3Py obligations over exact integer amounts."""', "import local_unlisted"
        )
        self.assertEqual(self.check()["status"], "error")

    def test_changed_source_invalidates_results(self):
        original = smt.run

        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.change("amount - requested", "amount")
            return result

        with patch.object(smt, "run", side_effect=mutate):
            self.assertEqual(self.check()["status"], "error")

    def test_cli_returns_failure_for_counterexample(self):
        self.change("amount - requested", "amount")
        self.assertEqual(
            cli.main(
                [
                    "smt-check",
                    "--root",
                    str(self.project),
                    "--manifest",
                    "checks.json",
                    "--out",
                    str(self.out),
                ]
            ),
            1,
        )

    def test_malformed_receipts_and_missing_queries_are_errors(self):
        original = smt.run
        for mode in ("empty", "tool", "preconditions", "model", "query_file"):
            with self.subTest(mode=mode):
                self.out = self.root / mode

                def tamper(*args, **kwargs):
                    result = original(*args, **kwargs)
                    path = args[2].parent / "receipt.json"
                    receipt = read_json(path)
                    if mode == "query_file":
                        (path.parent / "query.smt2").unlink()
                    elif mode == "empty":
                        write_json(path, {})
                    elif mode == "model":
                        del receipt["preconditions"]["model_smt2"]
                        write_json(path, receipt)
                    else:
                        receipt[mode] = None
                        write_json(path, receipt)
                    return result

                with patch.object(smt, "run", side_effect=tamper):
                    self.assertEqual(self.check()["status"], "error")

    def test_invalid_manifests_and_paths_are_rejected(self):
        cases = [
            {"solver_timeout_ms": 0},
            {"timeout_seconds": True},
            {"assumptions": ""},
            {"model": "../outside.py"},
            {"inputs": ["amounts.py", "../outside.py"]},
            {"commands": []},
            {"commands": [{"name": "Bad/name", "kind": "check"}]},
            {"commands": [{"name": "Conservation", "kind": "check", "artifact_id": "bad"}]},
        ]
        config = read_json(self.project / "checks.json")
        for updates in cases:
            with self.subTest(updates=updates):
                write_json(self.project / "checks.json", {**config, **updates})
                with self.assertRaises(smt.CheckError):
                    self.check()
        write_json(self.project / "checks.json", config)
        with self.assertRaises(smt.CheckError):
            smt.check_models(self.project, "checks.json", self.project)
