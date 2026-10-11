#!/usr/bin/env bash
set -Eeuo pipefail

cat >&2 <<'MESSAGE'
This in-place release migration entry point is retired and performs no changes.
Use the guarded VPS candidate workflow, review its candidate receipt, then run
guarded-vps-activate.yml with the exact prepared commit and maintenance confirmation.
MESSAGE
exit 2
