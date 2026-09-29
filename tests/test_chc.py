"""Real Spacer results, independently checked induction, and concrete traces."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import z3

from intentbond import chc, cli, smt
from intentbond.chc_worker import certify, reconstruct
from intentbond.common import read_json, write_json
from intentbond.testing import junit_counts

FIXTURE = Path(__file__).resolve().parents[1] / "examples/chc-checking"


class ChcTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ib-chc-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project with spaces"
        shutil.copytree(FIXTURE, self.project)
        self.out = self.root / "evidence"

    def check(self):
        return chc.check_models(self.project, "checks.json", self.out)

    def change(self, before, after):
        p = self.project / "allocation.py"
        p.write_text(p.read_text().replace(before, after))

    def test_model_supports_dataclasses_with_postponed_annotations(self):
        path = self.project / "allocation.py"
        path.write_text(
            "from __future__ import annotations\n"
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class ModelConfig:\n"
            "    minimum: int = 0\n\n" + path.read_text()
        )
        self.change("initial >= 0", "initial >= ModelConfig().minimum")
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(self.check()["status"], "passed")

    def test_command_names_do_not_collide_with_evidence_directories(self):
        self.change('"Conservation"', '"inputs"')
        self.change('"SeveralRows"', '"native"')
        config = read_json(self.project / "checks.json")
        for command, name in zip(config["commands"], ("inputs", "native"), strict=True):
            command["name"] = name
        write_json(self.project / "checks.json", config)
        result = self.check()
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(read_json(self.out / "inputs" / "checks.json"), config)
        for case in result["commands"]:
            receipt = f"native/{case['name']}/receipt.json"
            self.assertIn(receipt, result["artifacts"])
            self.assertEqual(read_json(self.out / receipt), case["receipt"])
        self.assertEqual(junit_counts(self.out / "junit.xml")["passed"], 2)

    def test_safety_certificate_trace_and_portable_polarity(self):
        result = self.check()
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(result["status"], "passed")
        proof, witness = result["commands"]
        self.assertEqual(proof["outcome"], "unreachable")
        self.assertEqual(proof["receipt"]["certificate"]["status"], "validated")
        self.assertEqual(proof["receipt"]["query"]["result"], "unsat")
        for name, text in proof["queries"].items():
            if name.startswith("certificate-"):
                solver = z3.Solver()
                solver.from_string(text)
                self.assertEqual(solver.check(), z3.unsat)
        # Standard Horn satisfiability and fixedpoint reachability have opposite polarity.
        portable = z3.SolverFor("HORN")
        portable.from_string(proof["queries"]["horn.smt2"])
        self.assertEqual(portable.check(), z3.sat)
        trace = witness["receipt"]["trace"]
        self.assertEqual(len(trace["steps"]), 4)
        for step in trace["steps"]:
            before, after = step["before"], step["after"]
            row = int(step["inputs"]["row"]["value"])
            self.assertEqual(
                int(after["remaining"]["value"]), int(before["remaining"]["value"]) - row
            )
            self.assertEqual(
                int(after["allocated"]["value"]), int(before["allocated"]["value"]) + row
            )
        self.assertIn("trace.smt2", witness["queries"])
        self.assertFalse(list((self.out / "inputs").rglob("__pycache__")))
        from intentbond.common import xml_tree

        embedded = json.loads(next(xml_tree(self.out / "junit.xml").iter("system-out")).text)
        self.assertEqual(embedded["result"]["receipt"], proof["receipt"])

    def test_mutation_yields_reachable_bad_state_and_validated_trace(self):
        self.change("na == allocated + row", "na == allocated + row + 1")
        case = self.check()["commands"][0]
        self.assertEqual(case["status"], "failed")
        self.assertEqual(case["outcome"], "reachable")
        self.assertEqual(case["receipt"]["trace"]["status"], "validated")
        portable = z3.SolverFor("HORN")
        portable.from_string(case["queries"]["horn.smt2"])
        self.assertEqual(portable.check(), z3.unsat)
        final = case["receipt"]["trace"]["steps"][-1]["after"]
        self.assertNotEqual(
            int(final["allocated"]["value"]) + int(final["remaining"]["value"]),
            int(final["initial"]["value"]),
        )

    def test_no_initial_states_is_not_a_proof(self):
        self.change("initial >= 0", "And(initial >= 0, initial < 0)")
        result = self.check()
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(
            [c["outcome"] for c in result["commands"]], ["unsatisfiable_initial_states"] * 2
        )

    def test_unreachable_required_behavior_fails(self):
        self.change("count == 4", "count == -1")
        result = self.check()
        self.assertEqual(result["commands"][0]["status"], "passed")
        self.assertEqual(result["commands"][1]["outcome"], "unreachable_witness")

    def test_initial_state_can_be_a_zero_step_counterexample(self):
        self.change("remaining == initial", "remaining == initial + 1")
        case = self.check()["commands"][0]
        self.assertEqual(case["outcome"], "reachable")
        self.assertEqual(case["receipt"]["trace"]["steps"], [])

    def test_bad_certificate_and_infeasible_trace_are_rejected(self):
        current, following = z3.Ints("current following")
        system = chc.System(
            {"x": current}, {"x": following}, current == 0, {"stay": following == current}
        )
        certificate = certify(system, current != 0, z3.BoolVal(True), self.root, 1000)
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(certificate["status"], "invalid")
        self.assertEqual(certificate["checks"]["target"]["result"], "sat")
        trace = reconstruct(
            system, current == 1, ["<null>", "target", "step.stay", "initial"], self.root, 1000
        )
        self.assertEqual(trace["status"], "invalid")
        with self.assertRaises(ValueError):
            reconstruct(system, current == 0, ["target", "unknown", "initial"], self.root, 1000)

    def test_incomplete_evidence_cannot_pass(self):
        original = smt.run
        for mode in ("certificate", "query_file", "trace", "trace_validation", "polarity"):
            with self.subTest(mode=mode):
                self.out = self.root / mode

                def tamper(*args, **kwargs):
                    result = original(*args, **kwargs)
                    p = args[2].parent / "receipt.json"
                    receipt = read_json(p)
                    if mode == "certificate" and "certificate" in receipt:
                        receipt["certificate"]["checks"].pop("initial")
                    elif mode == "query_file":
                        (p.parent / "horn.smt2").unlink()
                    elif mode == "trace" and "trace" in receipt:
                        receipt["trace"]["status"] = "invalid"
                    elif mode == "trace_validation" and "trace" in receipt:
                        receipt["trace"]["validation"]["result"] = "unsat"
                    elif mode == "polarity":
                        receipt["query_convention"] = "sat_means_safe"
                    write_json(p, receipt)
                    return result

                with patch.object(smt, "run", side_effect=tamper):
                    # [utest->req~ib-chc-certificates~1]
                    self.assertEqual(self.check()["status"], "error")

    def test_missing_obligation_wrong_kind_and_bad_frame_declarations(self):
        self.change('"Conservation": Reachability', '"Absent": Reachability')
        self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "bad_state"
        self.change('"Absent": Reachability', '"Conservation": Reachability')
        self.change("next_state=dict(initial=ni", "next_state=dict(initial=initial")
        self.assertEqual(self.check()["status"], "error")
        self.out = self.root / "wrong_kind"
        config = read_json(self.project / "checks.json")
        config["commands"] = [{"name": "SeveralRows", "kind": "check"}]
        write_json(self.project / "checks.json", config)
        self.assertEqual(self.check()["status"], "error")

    def test_unknown_from_unsupported_theory_is_not_a_pass(self):
        self.change("from z3 import And, Ints", "from z3 import And, Ints, Function, IntSort")
        self.change(
            "na == allocated + row", "na == Function('uninterpreted', IntSort(), IntSort())(row)"
        )
        result = self.check()
        # [utest->req~ib-chc-certificates~1]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["commands"][0]["outcome"], "unknown")
        self.assertTrue(result["commands"][0]["receipt"]["query"]["reason_unknown"])

    def test_construction_timeout_and_cli_failure(self):
        self.change("def obligations():", "def obligations():\n    while True:\n        pass")
        config = read_json(self.project / "checks.json")
        config.update(timeout_seconds=1, commands=config["commands"][:1])
        write_json(self.project / "checks.json", config)
        self.assertEqual(
            cli.main(
                [
                    "chc-check",
                    "--root",
                    str(self.project),
                    "--manifest",
                    "checks.json",
                    "--out",
                    str(self.out),
                ]
            ),
            2,
        )

    def test_frame_helper_preserves_omitted_fields_and_rejects_unknown_updates(self):
        x, y, nx, ny = z3.Ints("x y nx ny")
        state, following = dict(x=x, y=y), dict(x=nx, y=ny)
        solver = z3.Solver()
        solver.add(chc.assign(state, following, x=x + 1), ny != y)
        self.assertEqual(solver.check(), z3.unsat)
        with self.assertRaises(ValueError):
            chc.assign(state, following, typo=0)

    def test_source_changes_invalidate_chc_results(self):
        original = smt.run

        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            self.change("na == allocated + row", "na == allocated + row + 1")
            return result

        with patch.object(smt, "run", side_effect=mutate):
            self.assertEqual(self.check()["status"], "error")
