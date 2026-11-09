# I99: G9 checks every record's premises against its law's assume clauses

The coordinator's brief for I99 (2026-11-09). It fixes a high finding of M3 audit round 5, F-M3-19, on the lead's
`b4664e4c` (I98, landed via #125).

## The finding (F-M3-19, high, gate_evasion)

13 M3 result records list 0 premises although their laws assume 1-4 clauses (`statement.assume`):

- `L_contract_C_o12_m3` (PROVED, 4 clauses);
- `L_par_push_L1CrossDomainMessenger_proveAndRelayMessage_154` (PROVED, 2: a keccak256 collision-freedom hypothesis and
  a leaf equality);
- `L_sort_cons_{L1CrossDomainMessenger_receive, L1CrossDomainMessenger_replayMessage,
  L1CrossDomainMessenger_sendMessage_5f7b1577, L1CrossDomainMessenger_sendMessage_b2267a7b, Rollup_challengeState,
  Rollup_commitBatch, Rollup_receive, Submitter_stake}` (1 clause each);
- `L_sort_payer_L1CrossDomainMessenger_{replayMessage_201, sendMessage_5f7b1577_291, sendMessage_b2267a7b_291}` (1
  clause each).

To reproduce: for each `laws/M3/L_*.json`, compare `len(statement.assume)` with `len(premises)` in
`results/M3/<id>.json`. M0, M1 and M2 have no such records.

G9 only validates records against the v1 and v2 schemas. That holds for `holon/gate.py`'s g9 and for M3's per-family
G9, the one that prints "I30 laws … bundle laws … contract laws … the 207 other laws". So it passes these 13. It also
passes a scratch tree where `results/M3/L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned.json` has `premises: []`; its law
has 12 clauses.

The contract it breaks:

- the frozen `schemas/result_record.schema.json` defines premises as "every assume clause of the law plus any
  oracle/cryptographic premise";
- M0_SPEC §6 and D2 in `tests_m3/test_derivation_laws.py` want one readable string per clause;
- Appendix G defines G9 as "result records complete (§8.6)".

## What to build

1. Branch `claude/brave-wright-2c5d0o-i99` from `origin/claude/holon-v2-bend2-c6z3cd` (`b4664e4c`).
2. Amendment and predictions first: `spec/M3/amendments/I99.jsonl` and `spec/M3/predictions/I99.json`, following I97
   and I98. Get PREREG OK before building.
   - Predict 0 status moves and 0 law hash changes.
   - Predict that the 13 records gain premises: one per clause, plus oracle/crypto premises where the law has them.
   - Predict that the new G9 fails on the old records and passes on the new ones.
3. Fix the writers, not the records.
   - The bundle-law, contract-law, and SORT conservation and payer writers emit one readable premise per assume
     clause, hypotheses included.
   - Render them the way the M3 writers that already do this render them (the cc writer gives 12 for 12).
   - Re-make the 13 records through the generators.
   - Edit no law, and add no premise to a law or drop one from it.
4. G9 in every milestone, including M3's per-family G9, must fail any record whose premises don't cover its law's
   assume clauses, one string per clause.
   - A count check at least; a content check too if the rendering is canonical.
   - Name the law ids in the failure.
5. Add `tests_m3/test_g9_i99.py` and put it in CI next to the other tests_m3 jobs. It checks that:
   - the committed tree passes;
   - a planted `premises: []` on a PROVED record fails;
   - a planted missing clause fails;
   - all 13 records have their premises.
6. Validate on a clean scratch tree:
   - the checks gate-M3-partial runs, plus G7, G4 and G6;
   - G9 on M0, M1 and M2;
   - `python tools/freeze.py check`;
   - the frozen suite if the disk allows. Say so if it doesn't.
7. Open a draft PR against `claude/holon-v2-bend2-c6z3cd` with Done / Surprises / Questions for the human / Not done and
   the footer.

The contract is the docstring of `tests_m3/test_g9_i99.py`; the instrument is `tests_m3/_i99.py`. AGENTS.md's hard
rules apply: no frozen files, no audit/ files.
