# Python implementation correspondence

Select arithmetic rules, explicit state machines or relational constraints. Read the actual guards,
transaction boundaries, callers, and error handling; translating only annotations
or docstrings can model a promise without modeling its implementation.

Use pytest/Hypothesis and fresh state per trace. Decode Alloy instances or exact Z3 observations into
operation sequences and concrete parameters, execute actual Python functions, and
compare projected state after every operation. Map rejected calls explicitly and
check that they preserve required state. Distinguish public API replay from a
storage-boundary harness using private functions; the latter does not cover its
callers, validation, scheduler, or public API automatically.

Z3 mathematical `Int` matches Python integer arithmetic for addition and
subtraction; model division, shifts and conversions with their actual Python
semantics. Python integers are not Alloy fixed-width integers. SQLite integers have another
range. State the abstraction for amounts, timestamps, counters, equality, and
aliasing. Make nondeterministic clocks, failures, retries, and scheduler choices
explicit where they affect the property. A successful sequential replay of modeled
atomic operations does not test real process interleavings or SQLite durability.
