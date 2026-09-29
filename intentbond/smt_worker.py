"""Run one captured Z3Py obligation in a process bounded by the parent runner."""

import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path

# Support direct, isolated execution from installed wheels and source checkouts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from intentbond.smt import Z3_PACKAGE_VERSION, Obligation  # noqa: E402


def solve(assumptions, extra, observe, path, timeout_ms):
    import z3

    solver = z3.Solver()
    solver.set(timeout=timeout_ms, random_seed=0)
    solver.add(assumptions)
    if extra is not None:
        solver.add(extra)
    path.write_text(solver.to_smt2(), encoding="utf-8")
    result = solver.check()
    record = {"result": str(result)}
    if result == z3.unknown:
        record["reason_unknown"] = solver.reason_unknown()
    elif result == z3.sat:
        model = solver.model()
        values = {}
        for name, expression in observe.items():
            value = model.eval(expression, model_completion=True)
            values[name] = {"sort": value.sort().sexpr(), "smt2": value.sexpr()}
            if z3.is_int_value(value):
                values[name]["value"] = str(value.as_long())
            elif z3.is_true(value) or z3.is_false(value):
                values[name]["value"] = z3.is_true(value)
            elif z3.is_bv_value(value):
                values[name]["value"] = str(value.as_long())
        record["values"] = values
        record["model_smt2"] = model.sexpr()
    return record


def main():
    try:
        import z3
    except ImportError as exc:
        raise RuntimeError("Install intentbond[smt] to run Z3 checks") from exc
    version = importlib.metadata.version("z3-solver")
    if version != Z3_PACKAGE_VERSION:
        raise RuntimeError(f"Expected z3-solver {Z3_PACKAGE_VERSION}, found {version}")
    root, model_path, name, kind, destination, timeout = sys.argv[1:]
    root, destination = Path(root), Path(destination)
    module_path = root / model_path
    sys.path[:0] = [str(module_path.parent), str(root)]
    spec = importlib.util.spec_from_file_location("ib_application_smt_model", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    obligations = module.obligations()
    if not isinstance(obligations, dict) or name not in obligations:
        raise ValueError(f"Missing named SMT obligation: {name}")
    obligation = obligations[name]
    if not isinstance(obligation, Obligation) or obligation.kind != kind:
        raise ValueError(f"Wrong obligation type/kind: {name}")
    if not z3.is_bool(obligation.assumptions) or not z3.is_bool(obligation.goal):
        raise ValueError("Assumptions and goal must be native Z3 Boolean expressions")
    if not isinstance(obligation.observe, dict) or any(
        not isinstance(k, str) or not isinstance(v, z3.ExprRef)
        for k, v in obligation.observe.items()
    ):
        raise ValueError("Observations must map names to native Z3 expressions")
    record = {
        "name": name,
        "kind": kind,
        "tool": {"package_version": version, "version": z3.get_full_version()},
        "preconditions": solve(
            obligation.assumptions,
            None,
            obligation.observe,
            destination / "preconditions.smt2",
            int(timeout),
        ),
    }
    if record["preconditions"]["result"] == "sat":
        record["query"] = solve(
            obligation.assumptions,
            z3.Not(obligation.goal) if kind == "check" else obligation.goal,
            obligation.observe,
            destination / "query.smt2",
            int(timeout),
        )
    (destination / "receipt.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
