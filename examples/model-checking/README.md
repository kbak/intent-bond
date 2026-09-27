# Alloy runner example

Run `ib alloy-check --root examples/model-checking --manifest checks.json --out
/tmp/ownership-check-1` from the tool checkout, after `ib install-alloy`.
The model checks a small access relation and requires an allowed-access witness.
It tests runner behavior; it does not represent an application implementation.

The runner tests deliberately widen `allowed` to permit any user: `OwnerOnly`
must produce a counterexample. They also exercise impossible witnesses, missing
commands, invalid models, altered kinds and execution failures.
