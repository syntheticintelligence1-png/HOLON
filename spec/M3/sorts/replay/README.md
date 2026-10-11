# M3 sorts: replay evidence for REFUTED witnesses

| law | replay | how |
|---|---|---|
| L_sort3_remaining | Foundry (M1) | same statement as M1 `L_sort_remaining`; its witness replays on the real Rollup with `('rev', 'panic:0x11')` (results/M1/L_sort_remaining.json) |
| L_sort3_width_l1num | Go | `go/holon_l1num_test.go` copied into `common/batch/` of morph @ 3e44e795 and run with `go test -run TestHolonL1NumWidth -v .` (log: `go/holon_l1num_test.log`): `l1TxNum=0 hashes=65536` |
| L_sort3_prin_challenger | model-only pending replay | needs a Foundry run of `addChallenger(address(0))` + `challengeState` from `address(0)` (not callable from an EOA; only via a contract with no code at address(0)), see docs/M3_SORTS_REPORT.md |
| L_sort3_enq_sentinel | model-only pending replay | needs pre-upgrade storage (messageEnqueueTime absent) on a fork; see docs/M3_SORTS_REPORT.md |
