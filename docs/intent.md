# IntentBond intent

People developing software need to keep what they wanted connected to what was
built and checked. As humans and agents change a project, the reasons behind a
decision can disappear into conversations, while documents, code, and tests drift
apart. IntentBond should make those connections explicit and usable during work.

This document describes the desired outcomes and their rationale. The
[specification](spec.md) defines the concrete behavior and constraints that
support them.

## Design direction and conversations

Keep high-level goals and rationale separate from technical requirements, with
trace links connecting them. Intent can develop in conversation with an AI agent;
the maintained document captures the current problem, decisions, reasons, useful
alternatives, and open questions. Keep proposals distinguishable from decisions
carried into the specification.

IntentBond supports people working manually, with coding agents, or in CI.
Existing project documents and tools remain usable. Factory orchestration,
approval authority, deployment, and production monitoring belong to the
surrounding workflow.

## Intended outcomes

### Keep the user's purpose connected to the software
`intent~ib-preserve-purpose~1`

I want to follow a desired outcome into the concrete promises, implementation,
and checks that support it. When a promise changes, I want the related artifacts
to stay consistent without losing the identity or history of that promise.

Needs: req

Source: [how IntentBond works](../README.md#how-it-works) and
[requirements and design guidance](../intentbond/skills/intentbond/references/requirements.md).

### Understand a change without reconstructing the whole project
`intent~ib-understand-change~1`

I want to find the requirements and neighboring work affected by a change, and
see how they have evolved. The context should help me decide what to inspect and
update, with gaps in the selected scope visible.

Needs: req

Source: [requirement evolution](../README.md#inspect-requirement-evolution) and
[saved evidence inspection](contract.md#explain-saved-evidence).

### Know what was actually checked
`intent~ib-trust-evidence~1`

I want check results tied to the software I am reviewing, with enough evidence to
tell what ran, what passed, and what remains unknown. A successful command or a
complete set of links should not hide a missing test or imply more confidence
than the evidence supports.

Needs: req

Source: [reviewing results](../README.md#understand-and-review-the-result) and
[execution evidence](../intentbond/skills/intentbond/references/semantics.md#execution-evidence-and-permissible-conclusions).

### Keep decisions about meaning and acceptance visible
`intent~ib-review-decisions~1`

I want changes to promises, tests, and checking rules to be visible for review.
Automation should help the responsible reviewer assess them while keeping
acceptance a decision in the project's workflow. A change should not be able to
approve itself or quietly lower the standard used to check it.

Needs: req

Source: [check configuration](../README.md#1-configure-the-project) and
[origin, authorization, and verification](../intentbond/skills/intentbond/references/semantics.md#origin-authorization-and-verification).

### Start from the project I already have
`intent~ib-adopt-existing-project~1`

I want to establish useful requirements and links for existing software without
rewriting its behavior to fit a newly written document. Existing sources should
remain available for review, and inferred intent, contradictions, and missing
checks should stay visible as I adopt the baseline.

Needs: req

Source: [existing-project onboarding](recovery.md).

### Investigate critical rules more deeply when needed
`intent~ib-check-critical-rules~1`

For rules whose failures matter, I want to explore more cases and states than a
few hand-picked examples cover. Stronger checks should fit the existing workflow
and make their assumptions and limits clear, so I can judge how their results
relate to the real software.

Needs: req

Source: [property testing](property-testing.md) and
[model checking](model-checking.md).
