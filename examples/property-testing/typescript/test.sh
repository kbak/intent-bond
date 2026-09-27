#!/bin/sh
# Install outside the captured source, including when ib runs a clean snapshot.
set -eu
source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
work=$(mktemp -d /tmp/ib-fast-check.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cp "$source_root/package.json" "$source_root/package-lock.json" \
    "$source_root/session.js" "$source_root/session.test.js" "$work/"
cd "$work"
npm ci --ignore-scripts --no-audit --no-fund --cache "$work/cache"
npm test
