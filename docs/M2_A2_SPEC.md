# M2 A2: scenario laws and a held-out mutant set

A1 (`spec/M2/mutants.json`, 45 frozen mutants) is final at 19/45 = 0.4222, which misses the
preregistered 0.80. That result stands; A2 neither replaces nor re-scores it.

## Why A2 exists

A1's Rollup misses are mostly `rule_gap`: the extracted facts change, but no M0/M1 law's
status changes. The M1 laws are targeted finding laws and do not check the contract's
guards or effects.

## A2 laws (`spec/M2/A2/build_laws.py`, committed at eb4a3d0 before any A2 run)

- **Shape.** Every law is closed (no binders) and has a single equation over a concrete
  trace from `s0`. The probe is observed from the state its setup reaches, so each law
  speaks only about the probe.
- **Kinds.**
  - `rev(k)`: the probe reverts with reason code `k`.
  - `ok`: the probe succeeds.
  - `lci(n)`: after the probe, the last committed batch index is `n`.
- **Boundary pairs.** Relational guards are tested on both sides of the boundary, e.g.
  challenge window `t = 49` (ok) vs `t = 50` (reverts with 33).
- **Setup laws.** One `L_a2_setup_*` law per distinct setup trace asserts that the setup
  runs ok, so a probe cannot pass vacuously because its setup failed.
- **Predictions.** Every law is predicted `PROVED`. The predictions were written from
  Rollup.sol @3e44e79 without running the model. A law whose result differs from its
  prediction is reported, never edited to pass.
- **How a law is checked.** On truth the `evaluate` generator gives kernel-checked
  `PROVED`. On a mutant that breaks the law, the trace refuter gives kernel-checked
  `REFUTED` (both mechanics verified on probe laws).

## Held-out mutant set A2 (frozen after the A2 laws, before any A2 scoring)

- **Sites.** Every `require`, assignment, comparison and arithmetic statement inside the
  bodies of these functions in `contracts/contracts/l1/rollup/Rollup.sol` @3e44e79:
  `commitBatch`, `commitState`, `_commitBatchWithBatchData`, `revertBatch`,
  `challengeState`, `proveState`, `finalizeBatch`, `setPause`, `batchInChallenge`,
  `batchInsideChallengeWindow`, `batchExist`. Lines already used by an A1 mutant are
  excluded.
- **Operators.** The A1 classes: `relational`, `arith_drop`, `guard_deletion`,
  `statement_deletion`, `condition_drop`, `logical`, `constant`.
- **Sampling.**
  - `random.Random(seed)`, where `seed = int(sha256(sorted A2 law statement hashes), 16) mod 2**32`.
    The seed is fixed by the frozen laws and cannot be chosen.
  - For each candidate (site, operator) pair in file order, draw uniformly.
  - Keep 30 mutants that compile.
  - A mutant whose text is identical to the original is skipped before sampling.
- **Detection.** A mutant is detected when the status of some M0, M1 or A2 law changes
  relative to the extracted baseline of the same invocation. Labels, invalidity
  (compile failure only) and equivalence evidence follow `spec/M2/mutants.json`.
- **Threshold.** 0.80 on the 30 A2 mutants. It is reported as A2, separately from A1.

## Reported but not counted

The A1 Rollup mutants re-scored with the A2 laws. These numbers were seen after A1, so
they are a post-hoc diagnostic only.

## Pre-freeze log

These runs happened before the A2 mutant set was drawn. Every change made after them is
recorded here.

1. **eb4a3d0 laws, hand M1 facts.** 71 of 72 laws are `PROVED`, as predicted.
   - `L_a2_pr_timeout_blocks_commit` is `REFUTED`, so its prediction was wrong.
   - Likely cause: the timeout slashes submitter 2 (the prover removes `bds` from `active`),
     so the commit reverts with "only active submitter allowed" before the pending-revert
     check runs. Rollup.sol checks the `onlyActiveStaker` modifier first.
   - The law is kept unchanged and reported as a prediction miss.
2. **eb4a3d0 laws, S1 extracted facts.** 68 of 72 laws are `REFUTED`. There are two causes,
   and neither is a law/contract disagreement:
   - **Reason codes are numbered per facts file.** The extracted facts renumber them
     (hand 12 "incorrect batch index" is extracted 7), and the modifier reasons (`onlyOwner`,
     `onlyChallenger`, `onlyActiveStaker`, `whenNotPaused`) are absent.
   - **The extracted `sendMessage` omits `qlen += 1`.** No L1 message can ever be consumed,
     so every `n = 1` commit reverts with "message index out of range". This is an S1
     extraction defect: the write is neither extracted nor recorded as coverage debt.
3. **Fix 1 (laws, mechanical).** A revert is named by its message, `{"reason": msg}`, which
   is resolved against the facts file the law is built on. The preregistered codes are
   mapped through the hand facts' table. A reason missing from a facts file is `Unsupported`,
   so the law is `UNKNOWN` on that file; that is honest extraction debt.
4. **Fix 2 (extraction, before freezing).** S1 must extract the queue-length write, or record
   it as debt.

## Held-out mutant sampler (frozen with the A2 laws)

`spec/M2/A2/sample_mutants.py` implements the "Held-out mutant set A2" section above. It
writes `spec/M2/A2/mutants.json`.

- **Seed.** `int(sha256("\n".join(sorted statement_hash values of laws/A2/REGISTRY.json)), 16) mod 2**32`
  = 4039881274. The registry is unchanged since c70dad3; its sha256 is recorded in the output.
- **Pool.** 137 (site, operator) candidates, using the A1 operator classes as applied by the
  sampler's docstring rules (at most one candidate per line and operator). Identity
  candidates and A1 lines are skipped.
- **Draw.** `random.Random(seed).shuffle` of the file-ordered pool gives `order`. The
  campaign walks `order` and keeps the first 30 mutants that compile. A mutant that fails
  to compile is invalid, is recorded, and is replaced by the next one in order.
- **Erratum.** A first sampler (371f2dc) contradicted the section above: it had other
  operators and functions, and a seed without the mod. I discarded it unscored; its draw
  file sha256 is a530d081… and it was never run. The present sampler follows the section
  above. Its operand-parsing bugs (an arith_drop that ate a `]`, a condition_drop that left
  a stray `)`) were found by inspecting the pool and fixed before `order` was first printed.
- **Frozen.** Neither the sampler, the pool, nor `order` changes from here on.

## Pre-freeze log, continued (1374b3a, before the draw)

S1 extraction fixes, all derived from the AST:
- modifiers now run on actions;
- `finalizeBatch` drops its window head;
- the `proveState` challenge record ctor lookup now resolves;
- `challengeState` gains its batch-hash guard.

A2 on the extracted facts: 71 PROVED, 1 REFUTED (`L_a2_pr_timeout_blocks_commit`, the
preregistered miss), 0 UNKNOWN. On the hand facts it stays 70/1/1: `panic:0x11` is ambiguous
(codes 16 and 41). M1 Rollup laws on the extracted facts: 13 of 15 match results/M1;
`L_nat_eta2` and `L_sym_omega` remain UNKNOWN as S1 coverage debt.
