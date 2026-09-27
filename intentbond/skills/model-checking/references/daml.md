# Daml implementation correspondence

Select a contract lifecycle with existing Daml Script tests. For split/merge
operations, check quantity conservation, authorization, input consumption, and
preservation of owner and business identity.

Inspect the pinned SDK/LF version, template/interface implementations, controller
and signatory expressions, consuming versus nonconsuming choices, and nested
exercises. Model active contracts and party relationships explicitly. Track
authorization context through a transaction; a controller name alone does not
capture Daml authorization. Include rejected transactions and atomic rollback.
Do not model rejection by assuming every submitted operation is authorized.

For an exercise, model its child authorization context from that contract's
signatories and choice controllers. A nested archive can require signatories
absent from the primary contract. Include a witness for that rejection and a
successful witness with inherited signatory authority. Give callers read access
without granting write authority when testing authorization independently of
visibility. Keep visibility restrictions explicit if they are also modeled.

Use exact integer quanta for quantities and relate them to the actual
`Numeric` scale, representable range, rounding and rejection behavior. Small Alloy
integer scopes cannot establish the full decimal arithmetic contract. With Z3,
use scaled `Int` values and explicit representability checks at every evaluated
operation. `Numeric s` has precision 38: quanta range from `-(10^38 - 1)` to
`10^38 - 1` at scale `10^-s`. Addition/subtraction are exact when representable;
model rounding separately before extending to multiplication or division.
Do not evaluate arithmetic on a branch the implementation skips (for example,
summing discarded slices during an exposure reset). Preserve
nonnegative/positive input distinctions and zero/remainder cases.

Replay via Daml Script against a fresh IDE ledger for each trace, building the
test DAR with the project's pinned SDK. Query active output contracts and consumed
inputs, submit under the modeled parties, and check expected failures. Reuse the
project's existing generated-input driver when available. Retain
DAR digest, SDK version, inputs, native diagnostics and JUnit results. A pure
Python simulation cannot validate ledger authorization or contract consumption.

Decode native Alloy XML, exact Z3 observations or reconstructed Spacer traces into the parameterized script's JSON input. Map contract
atoms to actual returned IDs and compare the full active contract set across all
modeled templates and parties after each transition. Compare amounts, owners,
signatories, and business data as well as accepted/rejected outcomes. For a
rejection, compare complete before/after payloads to detect partial effects.
Preserve native rejection reasons. Required witnesses should isolate individual
rejection reasons so an unrelated failure cannot mask the missing check.

Build from the captured source files and pinned dependency DARs used for the
check. Include every source package and its build configuration in that capture;
do not reuse a test DAR after a failed build. Bind saved witness fixtures to the
model digest, and treat replay against changed source as regression evidence.
To test sensitivity, remove a concrete guard in a disposable source copy, rebuild
the test DAR, and require the expected ledger assertion failure. A build or input
decoding failure does not demonstrate that replay detects the mutation.

Start with single-ledger transaction semantics. State explicitly that participant
visibility, distributed Canton behavior, external valuations and orchestration
are outside that slice unless separately modeled and exercised.

For CHC loop models, relate recursive rules to the actual folds and their order.
Distinguish source arithmetic from unbounded ghost accounting. Derive whether
prefix checks are equivalent to whole-list validation under the stated domain;
nonnegative inputs matter to that argument. Do not promote internal loop steps
to separately committed transactions. Include all caller-supplied lists in replay,
and distinguish those supplied IDs from every active contract on the ledger.
