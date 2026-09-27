"""Render the documentation proposal and its check results for review."""


def render_review(result, checked, provenance):
    tests = checked.get("tests", {})
    trace = checked.get("trace", {}).get("candidate", {})
    items = provenance.get("items", [])
    lines = [
        "# Review the proposed requirements and links",
        "",
        f"Result: **{result['status']}**. Review the proposal before using it as the starting point for development.",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| Original source preserved, citations valid, and requirement ID changes recorded | {result['proposal_checks']} |",
        f"| Proposed requirement links (OFT) | {trace.get('status', 'not_run')} |",
        f"| Tests | {tests.get('status', 'not_run')} |",
        f"| Test source stability | {tests.get('source_status', 'unchecked')} |",
        "",
        f"Items with validated source citations: {len(items)} items, "
        f"{sum(i['origin'] == 'inferred' for i in items)} inferred. "
        "Valid citations do not establish that the proposal is complete or the requirements are satisfied.",
    ]
    if "counts" in tests:
        c = tests["counts"]
        lines += [
            "",
            f"Tests: {c['passed']} passed, {c['failed']} failed, "
            f"{c['errors']} errors, {c['skipped']} skipped ({tests['level']} evidence).",
        ]
    if "source" in result:
        lines += ["", f"Original commit: `{result['source']['commit']}`."]
    if "candidate" in result:
        lines += [f"Proposed source digest: `{result['candidate']['sha256']}`."]
    lines += ["", "## Decisions and gaps", ""]
    issues = provenance.get("open_issues", [])
    for issue in issues:
        lines.append("- " + issue["description"].replace("\n", " "))
    if not issues:
        lines.append(
            "No open questions were recorded in validated claim records. Review for omissions."
        )
    for title, messages in (
        ("Diagnostics", result["diagnostics"]),
        ("Storage", result.get("warnings", [])),
    ):
        if messages:
            lines += ["", f"## {title}", ""]
            lines += ["- " + message.replace("\n", " ") for message in messages]
    lines += ["", "## Files to review", ""]
    for name in result["review_artifacts"]:
        lines.append(f"- [{name}]({name})")
    lines += ["", "## Next step", ""]
    if result["proposal_checks"] != "passed":
        lines.append(
            "Resolve the proposal diagnostics before relying on its citations or source-preservation checks."
        )
    elif result["status"] == "incomplete":
        lines.append(
            "Preflight completed without running tests. Run a full recover-check when the test environment is ready."
        )
    elif result["status"] != "review_required":
        lines.append(
            "The proposal checks passed, but the selected validation policy is not satisfied. "
            "Review the partial proposal and assign missing behavior/tests as follow-up work. "
            "Do not remove obligations merely to obtain a pass."
        )
    else:
        lines.append(
            "Review the requirements, scope, inferred intent and open issues before accepting the baseline."
        )
    lines += [
        "",
        "Review the feature table and work left for later in the proposed documentation. "
        "Trace links and suite success do not establish every assertion or real-device/provider behavior.",
        "",
        "In-place edits already exist; do not reapply proposal.patch. For a separate draft, "
        "transfer only reviewed edits. Retain this complete result directory and the original source "
        "bundle, then check the reviewed commit with ib check. A partial proposal does not bypass "
        "the configured development checks.",
        "",
    ]
    return "\n".join(lines)
