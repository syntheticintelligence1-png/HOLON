#!/usr/bin/env bash
# Run every replay (must PASS) and every canary (must FAIL). Prints one verdict line per suite.
set -uo pipefail
cd "$(dirname "$0")"
FORGE=.work/foundry/forge
SKIP=()
[ -f src/uma/SkinnyOO_mainnet.sol ] || SKIP=(--no-match-path 'test/T09_*')
"$FORGE" test --no-match-path 'test/canary/*' "${SKIP[@]}" --fuzz-seed 0x7a11 2>&1 | tee .work/replay.log | grep -E '^\[(PASS|FAIL)|Suite result|tests passed'
status_replay=${PIPESTATUS[0]}
"$FORGE" test --match-path 'test/canary/*' --match-test 'invariant_noPayoutEver' --fuzz-seed 0x7a11 > .work/canary.log 2>&1
status_canary=$?
[ ${#SKIP[@]} -eq 0 ] || echo "T09: NOT RUN (UMA source not fetched; see setup.sh)"
if [ "$status_canary" -ne 0 ]; then echo "canary C11 (must fail): FAILED as required"; else echo "canary C11 (must fail): PASSED -> T11 would be vacuous"; fi
[ "$status_replay" -eq 0 ] && [ "$status_canary" -ne 0 ]
