import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__, alloy, chc, smt
from .check_output import render_check
from .common import CheckError
from .evidence import EXIT_CODES
from .explain import explain, explain_many, render_context, render_explanation
from .impact import impact, render_impact
from .oft import default_jar, install_jar
from .recovery import active_recovery, check_recovery, prepare
from .runner import check, verify
from .snapshot import git, resolve_commit


def default_base(repo):
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == b"HEAD":
        return resolve_commit(repo, "HEAD")
    refs = dict(
        line.split(" ", 1)
        for line in git(
            repo,
            "for-each-ref",
            "--format=%(refname) %(symref)",
            "refs/heads",
            "refs/remotes/origin/HEAD",
        )
        .decode()
        .splitlines()
    )
    remote_default = refs.get("refs/remotes/origin/HEAD")
    if remote_default:
        local = "refs/heads/" + remote_default.removeprefix("refs/remotes/origin/")
        target = local if local in refs else remote_default
    elif "refs/heads/main" in refs:
        target = "refs/heads/main"
    elif "refs/heads/master" in refs:
        target = "refs/heads/master"
    else:
        raise CheckError(
            "Cannot identify the default branch; supply --base with the starting commit"
        )
    try:
        bases = git(repo, "merge-base", "--all", "HEAD", target).decode().splitlines()
    except CheckError as exc:
        raise CheckError(
            f"Cannot find a common ancestor with {target}; supply --base with the starting commit"
        ) from exc
    if len(bases) != 1:
        raise CheckError("No unique branch baseline; supply --base with the starting commit")
    return bases[0]


def parser():
    root = argparse.ArgumentParser(
        prog="ib",
        description="Check requirement links and tests, compare Git versions, and save results",
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="action", required=True)
    alloy_install = commands.add_parser(
        "install-alloy", help="Download and checksum-verify optional Alloy 6.2.0"
    )
    alloy_install.add_argument("--destination", type=Path, default=alloy.default_jar().parent)
    modeling = commands.add_parser(
        "alloy-check", help="Run bounded Alloy checks and retain native evidence/JUnit"
    )
    modeling.add_argument("--root", type=Path, default=Path.cwd())
    modeling.add_argument("--manifest", required=True, help="Manifest path relative to root")
    modeling.add_argument("--out", type=Path, required=True, help="New or empty evidence directory")
    modeling.add_argument("--alloy-jar", type=Path, default=alloy.default_jar())
    modeling.add_argument("--java", default="java")
    solving = commands.add_parser(
        "smt-check", help="Check native Z3Py obligations and retain SMT-LIB evidence/JUnit"
    )
    solving.add_argument("--root", type=Path, default=Path.cwd())
    solving.add_argument("--manifest", required=True, help="Manifest path relative to root")
    solving.add_argument("--out", type=Path, required=True, help="New or empty evidence directory")
    reachability = commands.add_parser(
        "chc-check", help="Check unbounded reachability with Z3 Spacer"
    )
    reachability.add_argument("--root", type=Path, default=Path.cwd())
    reachability.add_argument("--manifest", required=True, help="Manifest path relative to root")
    reachability.add_argument(
        "--out", type=Path, required=True, help="New or empty evidence directory"
    )
    impacting = commands.add_parser(
        "impact", help="Compare saved OFT declarations, edges and source-change categories"
    )
    impacting.add_argument("--evidence", type=Path, required=True)
    impacting.add_argument("--format", choices=("text", "json"), default="text")
    impacting.add_argument("--oft-jar", type=Path, default=default_jar())
    impacting.add_argument("--java", default="java")
    explaining = commands.add_parser("explain", help="Explain OFT items using saved check evidence")
    explaining.add_argument(
        "identifiers", nargs="+", help="Complete OFT item IDs, including revisions"
    )
    explaining.add_argument(
        "--compact",
        action="store_true",
        help="Share metadata and deduplicate linked locations (automatic for multiple IDs)",
    )
    explaining.add_argument("--evidence", type=Path, required=True, help="Path to evidence.json")
    explaining.add_argument("--snapshot", choices=("base", "candidate"), default="candidate")
    explaining.add_argument("--format", choices=("text", "json"), default="text")
    explaining.add_argument("--oft-jar", type=Path, default=default_jar())
    explaining.add_argument("--java", default="java")
    install = commands.add_parser("install-oft", help="Download and checksum-verify OFT 4.9.0")
    install.add_argument("--destination", type=Path, default=default_jar().parent)
    recovery = commands.add_parser(
        "recover",
        help="Prepare to document an existing project's requirements and links",
        description=(
            "Save the original source and prepare citation records for documenting existing "
            "requirements and code/test links. A human or agent writes the proposal. "
            "Starts from a clean checkout at HEAD unless --isolated is used."
        ),
    )
    recovery.add_argument(
        "--isolated",
        action="store_true",
        help="Draft separately, leaving the original checkout unchanged",
    )
    recovery.add_argument(
        "--repo", type=Path, help="Source repository (default: current repository)"
    )
    recovery.add_argument(
        "--candidate",
        default="HEAD",
        help="Source version (default: HEAD); other versions require --isolated",
    )
    recovery.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Repository-relative path to inspect; repeat for multiple paths (default: .)",
    )
    recovery.add_argument(
        "--out",
        type=Path,
        help="New directory for originals and records (default: tool-managed Git metadata)",
    )
    recovering = commands.add_parser(
        "recover-check",
        help="Check proposed requirements, citations, links, and existing tests",
        description=(
            "Check a documentation proposal prepared with recover. Passing checks leave "
            "review pending (exit 4); --preflight skips tests and returns exit 5 when "
            "the other checks pass."
        ),
    )
    target = recovering.add_mutually_exclusive_group()
    target.add_argument(
        "--recovery",
        type=Path,
        help="Directory produced by ib recover (required for a separate draft)",
    )
    target.add_argument(
        "--repo",
        type=Path,
        help="Checkout containing the documentation proposal (default: current repository)",
    )
    recovering.add_argument(
        "--scope", type=Path, help="Proposed scope (default: workspace/scope.json)"
    )
    recovering.add_argument(
        "--out", type=Path, help="New result directory (default: tool-managed storage)"
    )
    recovering.add_argument("--oft-jar", type=Path, default=default_jar())
    recovering.add_argument("--java", default="java")
    recovering.add_argument(
        "--preflight",
        action="store_true",
        help="Check edits, source citations, and links without tests (exit 5 if these checks pass)",
    )
    checking = commands.add_parser("check", help="Check changes against a Git baseline")
    verifying = commands.add_parser(
        "verify", help="Match saved check results to source contents without rerunning tests"
    )
    for command in (checking, verifying):
        command.add_argument(
            "--repo", type=Path, help="Repository root (default: current repository)"
        )
        command.add_argument(
            "--scope",
            type=Path,
            help="Trusted scope JSON (default: scope.json from the baseline commit)",
        )
        command.add_argument(
            "--base", help="Baseline commit/ref (default: merge base with the default branch)"
        )
        command.add_argument(
            "--candidate", default="worktree", help="Git commit/ref or worktree (default: worktree)"
        )
    checking.add_argument(
        "--out",
        type=Path,
        help="New evidence directory outside target repo (default: fresh temporary directory)",
    )
    checking.add_argument("--oft-jar", type=Path, default=default_jar())
    checking.add_argument("--java", default="java")
    verifying.add_argument(
        "--allow-pending-review",
        action="store_true",
        help="Match automated evidence before external review; does not authorize changes",
    )
    verifying.add_argument("--evidence", type=Path, required=True, help="Path to evidence.json")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.action == "impact":
            result = impact(args.evidence, args.oft_jar, args.java)
            print(json.dumps(result, indent=2) if args.format == "json" else render_impact(result))
            return 0
        if args.action == "explain":
            compact = args.compact or len(args.identifiers) > 1
            result = (
                explain_many(
                    args.identifiers, args.evidence, args.oft_jar, args.snapshot, args.java
                )
                if compact
                else explain(
                    args.identifiers[0], args.evidence, args.oft_jar, args.snapshot, args.java
                )
            )
            print(
                json.dumps(result, indent=2)
                if args.format == "json"
                else render_context(result)
                if compact
                else render_explanation(result)
            )
            return 0
        if args.action == "install-oft":
            print(install_jar(args.destination))
            return 0
        if args.action == "install-alloy":
            print(alloy.install_jar(args.destination))
            return 0
        if args.action in {"smt-check", "chc-check"}:
            backend = chc if args.action == "chc-check" else smt
            result = backend.check_models(args.root, args.manifest, args.out)
            print(f"{result['status']}: {args.out.resolve() / 'result.json'}")
            for command in result["commands"]:
                print(f"- {command['name']}: {command['outcome']}")
            return {"passed": 0, "failed": 1, "error": 2}[result["status"]]
        if args.action == "alloy-check":
            result = alloy.check_models(
                args.root, args.manifest, args.out, args.alloy_jar, args.java
            )
            print(f"{result['status']}: {args.out.resolve() / 'result.json'}")
            for command in result["commands"]:
                print(f"- {command['name']}: {command['outcome']}")
            return {"passed": 0, "failed": 1, "error": 2}[result["status"]]
        if args.action == "recover-check":
            if args.recovery is None:
                repo = args.repo or Path(
                    os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")).strip()
                )
                args.recovery = active_recovery(repo)
            result = check_recovery(
                args.recovery,
                args.scope,
                args.out,
                args.oft_jar,
                args.java,
                preflight=args.preflight,
            )
            print(f"{result['status']}: {Path(result['output']) / 'recovery-result.json'}")
            print(f"Review summary: {Path(result['output']) / result['summary']}")
            for message in result["diagnostics"]:
                print(f"- {message}")
            for message in result["warnings"]:
                print(f"- {message}")
            if result["status"] == "review_required":
                print(
                    f"Review the {'working-tree changes' if result['mode'] == 'in_place' else 'proposal.patch'}, claims, scope and open issues before accepting the baseline."
                )
            return EXIT_CODES[result["status"]]
        if args.repo is None:
            args.repo = Path(os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")).strip())
        if args.action == "recover":
            result = prepare(
                args.repo, args.candidate, args.inputs or ["."], args.out, isolated=args.isolated
            )
            bundle = Path(result["bundle"])
            print(f"prepared: {bundle / 'recovery.json'} ({result['mode']})")
            print(f"source: {result['source']['commit']} ({result['source']['sha256']})")
            print(f"Read {bundle / 'instructions.md'}; work in {result['workspace']}")
            if not args.isolated:
                print(
                    f"Record citations in {Path(result['workspace']) / result['claims_path']}; review changes in Git before acceptance."
                )
            return 0
        if args.base is None:
            args.base = default_base(args.repo)
        if args.action == "verify":
            result = verify(
                args.repo,
                args.scope,
                args.base,
                args.candidate,
                args.evidence,
                args.allow_pending_review,
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.out is None:
            if Path(tempfile.gettempdir()).resolve().is_relative_to(args.repo.resolve()):
                raise CheckError(
                    "Temporary directory is inside the repository; supply --out outside it"
                )
            args.out = Path(tempfile.mkdtemp(prefix="ib-evidence-")) / "check"
        result = check(
            args.repo,
            args.scope,
            args.base,
            args.candidate,
            args.out,
            args.oft_jar,
            args.java,
        )
        print(render_check(result, args.out))
        return EXIT_CODES[result["status"]]
    except (CheckError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
