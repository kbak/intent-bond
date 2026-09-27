# Z3 execution and evidence

Use Z3 for arithmetic, bit-vectors, arrays or other supported theories where a
small explicit encoding fits the selected implementation. Install
`intentbond[smt]` in the checking interpreter. The extra pins the
existing `z3-solver` package; no separate solver service is needed.

## Native model

Write a Python module exporting `obligations()`, returning named
`intentbond.smt.Obligation` values:

```python
from z3 import And, Implies, Int
from intentbond.smt import Obligation


def obligations():
    amount, requested = Int("amount"), Int("requested")
    pre = And(amount >= 0, requested >= 0)
    accepted = requested <= amount
    remainder = amount - requested
    values = {"amount": amount, "requested": requested, "remainder": remainder}
    return {
        "Conservation": Obligation(
            pre, Implies(accepted, requested + remainder == amount), values
        ),
        "CanSplit": Obligation(
            pre, And(accepted, requested > 0, remainder > 0), values, kind="run"
        ),
    }
```

`assumptions` and `goal` must be native Z3 Boolean expressions. `observe` maps
names to native Z3 expressions. Python `if`, `and`, `or` and `not` are not symbolic
control flow; use Z3 `If`, `And`, `Or` and `Not`. Derive goals from requirements and
transition/output expressions independently from source. Do not assume the goal
or use an idealized output equation in place of the implemented calculation.

`Int` is mathematical integer arithmetic, `Real` is exact real arithmetic, and
`BitVec` uses fixed-width operations. Match the source semantics explicitly:
range checks and rejecting overflow for checked integers/decimals, signedness
and wrapping for machine operations, rounding for division and conversion.
Linear scaled-integer encodings work well for exact fixed-scale addition and
subtraction. A bounded transition unrolling still has bounded depth even when
its values range over all integers. State the domain of every claim.

## Manifest and command

```json
{
  "schema_version": 1,
  "model": "amounts.py",
  "inputs": ["amounts.py", "README.md"],
  "assumptions": "Exact nonnegative integers; one split; no machine overflow.",
  "timeout_seconds": 30,
  "solver_timeout_ms": 10000,
  "commands": [
    {"name": "Conservation", "kind": "check"},
    {"name": "CanSplit", "kind": "run"}
  ]
}
```

Paths are relative to the root. Include the model, its local helpers, mapped
implementation and requirement files, replay code and build configuration as
inputs; the manifest is included automatically. The model executes from the
captured files. It is ordinary trusted Python with the caller's privileges;
process isolation and timeout are not a security sandbox. List or pin other
runtime dependencies explicitly in the project's checking environment.

Run:

```sh
ib smt-check --root examples/smt-checking --manifest checks.json --out /tmp/smt-check
```

The output must be new or empty. Each command has an independent process timeout
covering model construction, and each solver query has a solver timeout. Add
`artifact_id`, such as `itest~numeric-check~1`, to a command to emit its declared
OFT identity in JUnit. Declare that artifact in a supported source file.

## Results

The runner first checks each obligation's assumptions for satisfiability.
Unsatisfiable assumptions fail, even if the corresponding implication would be
vacuously true. For `check`, it solves `assumptions AND NOT goal`: SAT fails with
a counterexample; UNSAT proves the encoding's goal under its assumptions.
For `run`, it solves `assumptions AND goal` and requires SAT. Include successful
and rejected boundary witnesses for each important branch; satisfiable assumptions
alone cannot rule out an unreachable guarded conclusion.

Timeout, `unknown`, malformed results, wrong names/kinds and solver failures are
errors, never success. CLI exit codes are 0 for all passes, 1 for a failed
obligation and 2 for an execution/configuration error. Solver success establishes
the encoding, not its correspondence to the implementation.

Each command retains `preconditions.smt2`, `query.smt2` when applicable,
`receipt.json` and `process.log`. The receipt records solver version, native
models, unknown reasons and selected observations. Integers and bit-vectors have
exact decimal-string `value` fields, Booleans have Boolean `value` fields, and all
observations retain their sort and native SMT-LIB representation. Other theories
need a suitable exact decoder; never convert rational or large integer values
through a float for replay.

`result.json` binds captured input hashes, assumptions and separate outcomes.
`junit.xml` embeds native queries and receipts so ordinary traceability checks
retain them with the report. Add the command/report to the project's existing
test configuration to require fresh solving. Saved counterexample/witness
fixtures can also replay in ordinary tests without importing Z3; bind them to the
model digest and label them as regression evidence against the tested source.
Preserve both model and real-implementation mutation results where practical.
