# Requirements and design

Write concrete behavior and constraints in the project's existing Markdown
documents. Give them OpenFastTrace (OFT) IDs and link related design, code, and
tests so later changes can be checked and reviewed.

Use the shared [concepts and result meanings](semantics.md), included alongside this guidance
in agent contexts. Keep coverage, origin, approval and execution evidence distinct.

Normal checks read root scope.json from the adopted baseline; omit --scope to
use it. Use external scope only when supplied by the caller. Candidate scope
edits cannot authorize themselves; proposed starting requirements and scope need review before use.

## Author requirements and design

Read the trusted scope and relevant repository guidance. Use existing headings,
capability tables or targeted searches to locate affected requirements, then read
their full promises and acceptance criteria and follow links to code and tests.
Reuse supplied context; retrieve more only to resolve a gap. Flag uncertainty:
trace links support consistency assessment but do not prove semantic agreement.

Distinguish exploration, proposed and agreed requirements, and open questions.
Formalize concrete, testable promises when useful; brainstorming is not agreement.
For changed promises, summarize the ID, before → after behavior, reason and
affected acceptance checks in the existing task or PR. Flag contradictions and
unknown rationale instead of inventing intent. Reuse this summary in the handoff.
For authorized mid-task revisions, reconcile affected design, code and assertions
through their links; preserve work and decisions that still apply.

Reuse OFT names for continuing promises. Search before assigning a new unique
name and initial revision. Follow the project's revision policy; editorial edits
and document moves need not increase the revision unless that policy requires it.

Use existing Markdown structure, OFT types and Needs/Covers chains; preserve
design/architecture links. Put meaningful rationale and rejected alternatives
in existing task/design notes when useful. Keep intended files within the
specification paths; flag scope conflicts instead of silently expanding them.

For critical or ambiguous rules, optionally add a logical statement beside the
requirement's prose and ID. Define its domain (variables, types, units), assumptions,
and guarantee, including quantifiers and relevant state or time boundaries. Use
preconditions, postconditions, invariants, or temporal properties as appropriate;
do not require every requirement to have a formula. Follow the
[property-testing guidance](../../property-testing/SKILL.md). Keep assumptions and
test-search limits distinct from promised behavior. Conflicting prose and logic
need a review decision, and a stronger precondition or narrower domain can weaken
the promise. A textual formula is not proof or evidence that a test ran.

Carry agreed text, IDs/revisions, acceptance criteria, documentation paths and
authorized promise changes into the existing handoff. Keep unapproved proposals
and unresolved questions separate. No extra document, planning pass or approval
step is required; drafting does not authorize implementation or scope changes.

## Keep independently evolving promises distinct

Choose stable IDs for independently reviewable behavior (for example ordering,
visibility, retry timing and errors), rather than requiring every consumer of a
large umbrella interface declaration to acknowledge every change. Avoid splitting
sentences mechanically. Multiple clauses can define the outcomes, exceptions or
invariants of one operation. When a change affects one promise independently of
the others, assess whether separate IDs would let their wording and assertions
evolve independently while preserving the accepted obligations.
For an intentional split, record the old ID/revision,
successor IDs, preserved obligations, authorized changes and migrated consumers;
keep one authoritative active set and preserve history separately. Advancing a
reference requires review of continued assertion coverage, never just a bulk bump.
Use `ib impact --evidence PATH` to inspect derived declaration/edge changes and,
for new bundles, source-line categories. Metadata-only revision changes do not
establish semantic adequacy or reduced review effort.
