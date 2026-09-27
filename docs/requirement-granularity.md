# Evolving promises without unnecessary revision churn

Choose requirement boundaries around promises that can evolve independently and can be reviewed independently. An interface can have separate guarantees for ordering, visibility, retry timing and error behavior. Keep their shared vocabulary and dependencies explicit. A single umbrella interface declaration forces all linked consumers to acknowledge any revision; splitting every sentence, conversely, creates navigation and link-maintenance work without necessarily improving understanding.

Reuse a stable ID while the same promise continues. Change its revision when its promise changes under the project's policy. Describe the old and new behavior and inspect every continuing code/test reference. Advancing a test reference is a claim of continued coverage that needs review of its assertions; it is not evidence that those assertions were updated or remain adequate. Avoid automatic bulk bumps as a substitute for that review.

When an umbrella promise genuinely splits, make the transition explicit in the accepted change: old ID and last revision, successor IDs, preserved obligations, intentional changes, migrated consumers and any gaps. Keep active declarations authoritative and unique. Record retired wording and the split decision in version history or an explicitly excluded historical document; do not leave two active declarations for one continuing ID. Native OFT Covers links describe supported trace relationships, not a general retirement mechanism, so document supersession as a decision rather than inventing new graph semantics. Merge promises only when their evolution and review need the shared boundary.

## Example and measured structural impact

[Granular retries](../examples/granular-retries) has two promises: exponential growth and a delay cap. Its bounded change increases the cap from 8 to 16 seconds. The growth requirement, implementation ID, test ID and their exact references remain unchanged. The cap promise and its two named consumers advance their revisions; implementation and boundary assertions change. A deliberately stale cap-test reference is rejected by OFT even when the updated assertions pass.

The executable example and `tests/test_impact.py` establish these structural counts for that change:

| Measure | Count |
| --- | ---: |
| Declarations before / after | 6 / 6 |
| Changed declarations, excluding location shifts | 3 |
| Required declarations with changed normative text | 1 |
| Direct OFT edges before / after | 4 / 4 |
| Continuing edges with revised endpoints | 2 |
| Exact edges removed / added | 2 / 2 |
| Observed human review effort | Not measured |

The revision-only control keeps the original promise and executable bodies unchanged, but advances the cap declaration and references. The report distinguishes those metadata edits from the behavior-changing case. This does not show that granular requirements are universally cheaper. Compare the **same contract change**, obligations, tests and review quality under plausible decompositions before claiming less work. Count authored declarations/edges, affected consumers, actual review minutes and errors; retain both cases and their misses. Do not infer avoided effort from these counts alone.

## Reproduce change impact

```sh
ib check --repo /path/to/repo --base BASE_COMMIT --out /tmp/cap-evidence
ib impact --evidence /tmp/cap-evidence/evidence.json
ib impact --evidence /tmp/cap-evidence/evidence.json --format json
```

`ib impact` asks the pinned OFT engine for both retained graphs, using the same reporting code as `ib explain`. It compares declarations by stable type/name, exact source-to-target edges, normative declaration text, coverage policy and location changes. OFT remains responsible for graph validity. A report can describe rejected evidence; its recorded check status and trace statuses remain visible. Ambiguous multiple active declaration revisions are rejected instead of silently collapsing them. Multiple exact graph edges for one logical source/target pair (including OFT diagnostics around stale references) are retained as ambiguous pairs and excluded from inferred revision-update counts.

A separate source-line classification in new `review.json` records identifies implementation/test file edits and recognized annotation-line-only changes. The latter requires that all remaining UTF-8 file text and file mode match after removing **only standalone lines that OFT actually imported**. It does not parse program semantics. Inline/unrecognized tags, binary files, additions/deletions or mode changes are conservatively reported as source changes or unclassified. A declaration's metadata can be link/revision-only while its implementation or assertions changed, so read declaration and source categories together.

These results are derived reports, not new approval gates. The active requirement documents remain authoritative. Impact works from a relocated bundle without re-running tests or changing historical evidence. Legacy bundles explicitly lack source-line classifications; they do not gain invented historical observations. Counts and hashes cannot prove assertion adequacy, semantic approval, complete scenario coverage or causal ROI.
