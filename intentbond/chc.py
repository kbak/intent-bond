"""Native transition systems checked as linear Horn clauses by Z3 Spacer."""

from dataclasses import dataclass, field

from .common import CheckError
from .smt import Z3_PACKAGE_VERSION


@dataclass(frozen=True)
class System:
    """Z3 constants and formulas; every step explicitly relates current/next state."""

    state: dict
    next_state: dict
    initial: object
    steps: dict
    inputs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Reachability:
    """A check's target is a violation; a run's target is a required witness."""

    system: System
    target: object
    kind: str = "check"


def interpret(receipt, command):
    if (
        not isinstance(receipt, dict)
        or receipt.get("name") != command["name"]
        or receipt.get("kind") != command["kind"]
        or receipt.get("engine") != "spacer"
        or receipt.get("query_convention") != "sat_means_reachable"
        or not isinstance(receipt.get("tool"), dict)
        or receipt["tool"].get("package_version") != Z3_PACKAGE_VERSION
    ):
        raise CheckError("Missing or mismatched CHC identity, engine, convention or version")
    names = receipt.get("transition_names")
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(n, str) for n in names)
        or len(set(names)) != len(names)
    ):
        raise CheckError("Missing or invalid CHC transition names")
    pre = receipt.get("preconditions")
    if not isinstance(pre, dict):
        raise CheckError("Missing CHC initial-state result")
    if pre.get("result") == "unsat":
        return "failed", "unsatisfiable_initial_states"
    if pre.get("result") == "unknown":
        return "error", "unknown"
    if pre.get("result") != "sat":
        raise CheckError("Invalid CHC initial-state result")
    query = receipt.get("query")
    if not isinstance(query, dict) or query.get("result") not in {"sat", "unsat", "unknown"}:
        raise CheckError("Missing CHC reachability result")
    if query["result"] == "unknown":
        return "error", "unknown"
    if not isinstance(query.get("answer_smt2"), str) or not query["answer_smt2"]:
        raise CheckError("Missing native Spacer answer")
    if query["result"] == "unsat":
        certificate = receipt.get("certificate")
        if not isinstance(certificate, dict) or certificate.get("status") != "validated":
            raise CheckError("Spacer invariant has not passed SMT induction checks")
        checks = certificate.get("checks")
        names = receipt.get("transition_names")
        if (
            not isinstance(names, list)
            or not names
            or not isinstance(checks, dict)
            or set(checks) != {"initial", "target", *(f"step.{n}" for n in names)}
            or any(not isinstance(c, dict) or c.get("result") != "unsat" for c in checks.values())
            or not certificate.get("invariant_smt2")
        ):
            raise CheckError("Incomplete or failed CHC induction certificate")
        return (
            ("passed", "unreachable")
            if command["kind"] == "check"
            else ("failed", "unreachable_witness")
        )
    trace = receipt.get("trace")
    if (
        not isinstance(trace, dict)
        or trace.get("status") != "validated"
        or not isinstance(trace.get("initial"), dict)
        or not trace["initial"]
        or not isinstance(trace.get("validation"), dict)
        or trace["validation"].get("result") != "sat"
        or not isinstance(trace.get("steps"), list)
        or not isinstance(query.get("rule_names"), list)
        or any(
            not isinstance(step, dict) or step.get("name") not in receipt["transition_names"]
            for step in trace["steps"]
        )
    ):
        raise CheckError("Reachable target lacks a validated concrete trace")
    current = trace["initial"]
    for step in trace["steps"]:
        if (
            step.get("before") != current
            or not isinstance(step.get("after"), dict)
            or set(step["after"]) != set(current)
            or not isinstance(step.get("inputs"), dict)
        ):
            raise CheckError("Malformed or discontinuous concrete CHC trace")
        current = step["after"]
    return ("failed", "reachable") if command["kind"] == "check" else ("passed", "witness")


def required_queries(receipt):
    required = {"preconditions.smt2", "query.smt2", "horn.smt2"}
    certificate, trace = receipt.get("certificate"), receipt.get("trace")
    if isinstance(certificate, dict) and certificate.get("status") == "validated":
        required.update(f"certificate-{name}.smt2" for name in certificate["checks"])
    if isinstance(trace, dict) and trace.get("status") == "validated":
        required.add("trace.smt2")
    return required


def check_models(root, manifest, out):
    from .smt import check_models as run_models

    return run_models(root, manifest, out, backend="chc")


def assign(state, next_state, **updates):
    """Constrain every next field; omitted updates retain the current value."""
    import z3

    if set(state) != set(next_state) or set(updates) - set(state):
        raise ValueError("Assignments require matching state fields and known update names")
    return z3.And(*(next_state[n] == updates.get(n, value) for n, value in state.items()))
