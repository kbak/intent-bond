"""Run Spacer and validate its safety certificate or reconstructed finite trace."""

import importlib.metadata
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intentbond.chc import Reachability, System  # noqa: E402
from intentbond.smt import Z3_PACKAGE_VERSION  # noqa: E402
from intentbond.smt_worker import solve  # noqa: E402


def validate(obligation, kind):
    import z3
    from z3.z3util import get_vars

    if not isinstance(obligation, Reachability) or obligation.kind != kind:
        raise ValueError("Expected a Reachability obligation with the selected kind")
    system = obligation.system
    if not isinstance(system, System) or not system.state or not system.steps:
        raise ValueError("A CHC system needs state and named transitions")
    for mapping in (system.state, system.next_state, system.inputs, system.steps):
        if not isinstance(mapping, dict) or any(
            not isinstance(k, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", k) for k in mapping
        ):
            raise ValueError("Use simple identifiers for state, inputs and transitions")
    if set(system.state) != set(system.next_state):
        raise ValueError("Current and next state must have the same field names")
    variables = [*system.state.values(), *system.next_state.values(), *system.inputs.values()]
    if any(not z3.is_const(v) or v.decl().kind() != z3.Z3_OP_UNINTERPRETED for v in variables):
        raise ValueError("State and inputs must be native uninterpreted Z3 constants")
    if len({v.get_id() for v in variables}) != len(variables):
        raise ValueError("State, next state and inputs must use distinct constants")
    if any(system.state[n].sort() != system.next_state[n].sort() for n in system.state):
        raise ValueError("Current and next state sorts must match")
    for formula, allowed in [
        (system.initial, list(system.state.values())),
        (obligation.target, list(system.state.values())),
        *((step, variables) for step in system.steps.values()),
    ]:
        if not z3.is_bool(formula):
            raise ValueError("Initial states, transitions and targets must be Z3 Boolean formulas")
        if any(v.get_id() not in {x.get_id() for x in allowed} for v in get_vars(formula)):
            raise ValueError("Formula references an undeclared or out-of-scope variable")
    return system


def build(obligation, timeout):
    import z3

    system = obligation.system
    state = list(system.state.values())
    following = [system.next_state[n] for n in system.state]
    variables = [*state, *following, *system.inputs.values()]
    # Fresh declarations avoid collisions with application state names.
    reach = z3.FreshFunction(*[v.sort() for v in state], z3.BoolSort())
    target = z3.FreshFunction(z3.BoolSort())
    fp = z3.Fixedpoint()
    fp.set(
        engine="spacer",
        timeout=timeout,
        **{
            "spacer.random_seed": 0,
            "xform.slice": False,
            "xform.inline_eager": False,
            "xform.inline_linear": False,
        },
    )
    fp.register_relation(reach, target)
    fp.declare_var(*variables)
    fp.rule(reach(*state), system.initial, name="initial")
    clauses = [z3.ForAll(variables, z3.Implies(system.initial, reach(*state)))]
    for name, step in system.steps.items():
        body = z3.And(reach(*state), step)
        fp.rule(reach(*following), body, name="step." + name)
        clauses.append(z3.ForAll(variables, z3.Implies(body, reach(*following))))
    fp.rule(target(), z3.And(reach(*state), obligation.target), name="target")
    clauses.append(
        z3.ForAll(variables, z3.Implies(z3.And(reach(*state), obligation.target), False))
    )
    portable = z3.SolverFor("HORN")
    portable.add(*clauses)
    horn = (
        "; check-sat convention: SAT means the target is unreachable\n(set-logic HORN)\n"
        + portable.to_smt2()
    )
    return fp, reach, target, horn


def certify(system, target, invariant, directory, timeout):
    import z3

    next_invariant = z3.substitute(
        invariant, *[(v, system.next_state[n]) for n, v in system.state.items()]
    )
    violations = {
        "initial": z3.And(system.initial, z3.Not(invariant)),
        "target": z3.And(invariant, target),
    }
    violations.update(
        {
            "step." + name: z3.And(invariant, step, z3.Not(next_invariant))
            for name, step in system.steps.items()
        }
    )
    checks = {
        name: solve(formula, None, {}, directory / f"certificate-{name}.smt2", timeout)
        for name, formula in violations.items()
    }
    return {
        "status": "validated"
        if all(c["result"] == "unsat" for c in checks.values())
        else "invalid",
        "invariant_smt2": invariant.sexpr(),
        "checks": checks,
    }


def reconstruct(system, target, rule_names, directory, timeout):
    """Solve the native derivation's step sequence; no bounded search for a proof."""
    import z3

    names = [name for name in reversed(rule_names) if name != "<null>"]
    if not names or names[0] != "initial" or names[-1] != "target":
        raise ValueError("Unsupported Spacer derivation: missing initial/target rule")
    sequence = names[1:-1]
    if any(not name.startswith("step.") or name[5:] not in system.steps for name in sequence):
        raise ValueError("Unsupported Spacer derivation rule")
    frames = [
        {n: z3.FreshConst(v.sort(), prefix="state_" + n) for n, v in system.state.items()}
        for _ in range(len(sequence) + 1)
    ]
    inputs = [
        {n: z3.FreshConst(v.sort(), prefix="input_" + n) for n, v in system.inputs.items()}
        for _ in sequence
    ]

    def current(formula, index):
        return z3.substitute(formula, *[(v, frames[index][n]) for n, v in system.state.items()])

    constraints = [current(system.initial, 0), current(target, len(sequence))]
    for index, name in enumerate(sequence):
        substitutions = [(v, frames[index][n]) for n, v in system.state.items()]
        substitutions += [(v, frames[index + 1][n]) for n, v in system.next_state.items()]
        substitutions += [(v, inputs[index][n]) for n, v in system.inputs.items()]
        constraints.append(z3.substitute(system.steps[name[5:]], *substitutions))
    observe = {f"state.{i}.{n}": v for i, frame in enumerate(frames) for n, v in frame.items()}
    observe.update({f"input.{i}.{n}": v for i, row in enumerate(inputs) for n, v in row.items()})
    result = solve(z3.And(*constraints), None, observe, directory / "trace.smt2", timeout)
    if result["result"] != "sat":
        return {"status": "invalid", "validation": result}
    values = result["values"]
    states = [{n: values[f"state.{i}.{n}"] for n in system.state} for i in range(len(frames))]
    return {
        "status": "validated",
        "initial": states[0],
        "steps": [
            {
                "name": name[5:],
                "before": states[i],
                "after": states[i + 1],
                "inputs": {n: values[f"input.{i}.{n}"] for n in system.inputs},
            }
            for i, name in enumerate(sequence)
        ],
        "validation": result,
    }


def main():
    try:
        import z3
    except ImportError as exc:
        raise RuntimeError("Install intentbond[smt] to run Spacer checks") from exc
    version = importlib.metadata.version("z3-solver")
    if version != Z3_PACKAGE_VERSION:
        raise RuntimeError(f"Expected z3-solver {Z3_PACKAGE_VERSION}, found {version}")
    root, model_path, name, kind, destination, timeout = sys.argv[1:]
    root, directory, timeout = Path(root), Path(destination), int(timeout)
    module_path = root / model_path
    sys.path[:0] = [str(module_path.parent), str(root)]
    spec = importlib.util.spec_from_file_location("ib_application_chc_model", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    obligations = module.obligations()
    if not isinstance(obligations, dict) or name not in obligations:
        raise ValueError(f"Missing named CHC obligation: {name}")
    obligation = obligations[name]
    system = validate(obligation, kind)
    fp, reach, target, horn = build(obligation, timeout)
    (directory / "query.smt2").write_text(
        f"(set-option :fp.engine spacer)\n(set-option :timeout {timeout})\n"
        "(set-option :fp.xform.slice false)\n(set-option :fp.xform.inline_eager false)\n"
        "(set-option :fp.xform.inline_linear false)\n(set-option :fp.spacer.random_seed 0)\n"
        + fp.to_string([target()])
    )
    (directory / "horn.smt2").write_text(horn)
    record = {
        "name": name,
        "kind": kind,
        "engine": "spacer",
        "query_convention": "sat_means_reachable",
        "tool": {"package_version": version, "version": z3.get_full_version()},
        "transition_names": list(system.steps),
        "preconditions": solve(
            system.initial, None, system.state, directory / "preconditions.smt2", timeout
        ),
    }
    if record["preconditions"]["result"] == "sat":
        try:
            result = fp.query(target())
            record["query"] = {"result": str(result)}
            if result == z3.unknown:
                record["query"]["reason_unknown"] = fp.reason_unknown()
            else:
                record["query"]["answer_smt2"] = fp.get_answer().sexpr()
                if result == z3.unsat:
                    invariant = z3.substitute_vars(
                        fp.get_cover_delta(-1, reach), *system.state.values()
                    )
                    record["certificate"] = certify(
                        system, obligation.target, invariant, directory, timeout
                    )
                else:
                    names = [str(n) for n in fp.get_rule_names_along_trace()]
                    record["query"]["rule_names"] = names
                    record["trace"] = reconstruct(
                        system, obligation.target, names, directory, timeout
                    )
        except z3.Z3Exception as exc:
            record["query"] = {"result": "unknown", "reason_unknown": str(exc)}
    (directory / "receipt.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
