# Standalone setup for implementation

Discussion alone does not require installing or running tooling. For authorized
implementation, use the chosen tool checkout/revision and its matching skill.
When only a skill link is supplied, clone its repository/ref over HTTPS into a
new directory outside the target project and resolve it to a commit. For an
unversioned copy without a supplied source, use
`https://github.com/kbak/intent-bond.git` at main. Reread the matching
skill and references, and retain the tooling revision for the handoff.
Resolve relative references there, not in the target project. Reuse a supplied
local checkout, packaged skill/runtime or inline reference when available. If an
installed ib cannot be tied to that source, install from the chosen checkout into
a fresh external environment; a version number alone does not establish a match.

The runtime needs Python 3.11+, Git, Java 17+, the portable package and the target
project's test dependencies. Keep tool checkouts and environments outside the target
project and preserve existing local work. After choosing absolute paths in
ib_checkout and ib_env:

```sh
python3 -m venv "$ib_env"
"$ib_env/bin/python" -m pip install "$ib_checkout"
"$ib_env/bin/python" -m intentbond check --help
"$ib_env/bin/python" -m intentbond verify --help
"$ib_env/bin/python" -m intentbond install-oft
```

Reuse an existing pinned OFT JAR via INTENTBOND_OFT_JAR when available. Use the same
interpreter for checks and verification, with an explicit target --repo after
setup. Prepare the project's real test runner using its instructions; installing
ib does not install those dependencies. Resolve routine setup within task
permissions and report concrete blockers. Do not change project dependency
manifests solely to install the checker or silently substitute an unavailable
requested tool revision.
