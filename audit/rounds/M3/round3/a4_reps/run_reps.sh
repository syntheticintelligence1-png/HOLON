#!/bin/bash
T=/tmp/audit-m3-r3/t
cd $T
export BEND_NO_TELEMETRY=1 PATH="$HOME/.holon/bin:$HOME/.elan/bin:$PATH" TMPDIR=/tmp/audit-m3-r3/tmp GOPROXY=off
for L in L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatch_366 L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatchWithProof_366 L_disch_rev_rollup_228_79cc3e9a L_disch_blk_rollup_228_79cc3e9a_onlyOwner; do
  echo "=== $L start $(date -u +%H:%M:%S)"
  ( time timeout 1200 python -m holon run --milestone M3 --laws $L ) > /tmp/audit-m3-r3/a4/run_$L.log 2>&1
  echo "=== $L end $(date -u +%H:%M:%S) rc=$?"
  tail -n 4 /tmp/audit-m3-r3/a4/run_$L.log
done
