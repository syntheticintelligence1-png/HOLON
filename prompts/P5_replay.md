# Session P5: replay witnesses on the real Morph code (about half a day)

Read `AGENTS.md`, `docs/M0_SPEC.md` §8, and the REFUTED records in `results/M0/`.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

## Why

A refutation of the model is a hypothesis about the code. It becomes a finding only when the real implementation shows the same behaviour on the same input. A witness that does not replay is a model defect: report it loudly.

## Tasks

1. Clone `https://github.com/morph-l2/morph`. Resolve `3e44e79` to the full SHA and check it out outside this repo.
2. **Facts audit (do this first).**
   - For every `code` string and source reference in `facts/morph_header.json`, find the code in the real repo at that commit.
   - Write `replay/M0/facts_audit.md` with a table: fact → file:line in the real repo → matches / differs.
   - The facts were extracted from an audit bundle, not from the repo. Differences are important. Report them; do not edit the facts.
3. **Go replay.** In a scratch copy of `common/batch`, add `holon_replay_test.go`. It reads the witnesses from `results/M0/*.json` and asserts:
   - **L_par_hdr_v2:** `BatchHeaderV1{...witness fields...}.Bytes()[0] == 1`, while the witness's version is 2.
   - **L_dom_hdr:** `BatchHeaderBytes(witness).Hash()` returns `ErrInvalidBatchHeaderLength`. Also check `Version()` and the other getters on the witness.
   - **L_par_hdr_ssvh:** `Bytes()[185:217]` equals the witness's nonzero `SequencerSetVerifyHash`.
4. **Solidity replay** with Foundry, using the repo's own contracts:
   - Write a harness contract that inherits `Rollup` and exposes `_loadBatchHeader` as an external function.
   - Show that it does **not** revert on the 250-byte version-0 witness, and does revert on a 249-byte header with version 3.
   - Full `commitBatch` replay (byte 0 = 2 for v2, ssvh written as zero) needs deployment wiring; mark it `not_applicable` with that reason. It belongs to M1.
5. **Write `replay/M0/report.json`** (format in M0_SPEC §8), with the exact commands and the observed outputs. Commit the harness sources under `replay/M0/`.
6. Set `replay.status` in the affected result records **only through the pipeline**: add a `--replay-report` input to `holon run`, or a `holon replay` command that rewrites the records deterministically. Re-run the gate.

## Definition of done

- `HOLON_REPLAY=1 python -m unittest tests.test_50_replay -v` passes.
- The full suite still passes.
- The facts audit is complete.
