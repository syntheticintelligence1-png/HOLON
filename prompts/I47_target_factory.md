# I47 (M4): target-agnostic factory, parallel checking, performance loop, drift trigger

Rendered from docs/BUILD_PLAN.md §4 I47 and the coordinator's brief for this session. Read AGENTS.md, docs/M0_SPEC.md,
docs/BEND_PRIMER.md, BUILD_PLAN §0.1, §0.2, §2, §3 and the M4 header, whitepaper §9.2(7), L20, L22 and §13, and
docs/HUMAN_ANSWERS.md ("I47: its tests require that nothing in holon/ names a target").

Base: `claude/holon-v2-bend2-c6z3cd` at 4fd64a52. One draft PR against it; the lead lands M4 code only after M3's exit
commit is fixed, so the PR waits.

## Goal

- Move target specifics into `targets/<name>/target.json` (schema `spec/M4/lib/target.schema.json`).
- Parallel per-law work with a deterministic merge: `concurrent.futures.ProcessPoolExecutor` in the run and the gate.
- The §9.2(7) performance loop with veto: `tools/perf_loop.py`.
- The L22 drift trigger: `python -m holon drift --target NAME`.
- A toy second target, `abacus` (tests_m4/fixtures/i47_abacus/), that runs with no edit to holon/.

The contract is the docstring of `tests_m4/test_i47_factory.py` (T0-T6). The key is `I47` in
`spec/M4/predictions.json` (source `spec/M4/predictions/I47.json`).

## What I47 must not change

No M0-M3 result, law, record or generated file. Every committed record carries `generator_sha256`, the digest of the
source bytes of its generators and every holon module they import (holon.records and 16 other modules' own
`generator_sha256`). At BASE these closures read 286 of holon/'s files, among them holon/pipeline.py,
holon/mpipeline.py, holon/bend.py and the replay adapters. A byte change to any of them moves the digest of committed
M1-M3 records, and G1 then fails (or the records must be re-made, which the brief forbids). So:

- I47 edits no record-pinned file (`tests_m4/_i47_probe.py` lists them for any tree). New behaviour goes into new
  modules and into the unpinned entry points (`holon/__main__.py`, `holon/gate.py`, ...).
- No new file may match the closures' globs (`spec/lib/*.lib.json`, `spec/*/lib/*.lib.json`, `spec/*/policy_hints.mjs`,
  `spec/*/lib/*.pointwise.json`, `spec/*/lib/window_*.json`, `spec/*/lib/oracles.json`).

## The conflict this prereg states up front (P5)

"Nothing in holon/ names a target" and "no committed record moves" cannot both hold in full: at BASE, 19 record-pinned
files name the development target in code (`morph_commit` report keys, `config replay.morph`, the default
`facts/morph_header.json`, `--morph` flags, the replay adapters). I47 cannot change them without moving committed
digests. P5 therefore claims: every other holon/ file names no declared target after I47 (17 such files name it at
BASE), and the 19 are exactly the residue, byte-identical to BASE. Clearing the residue is a question for the human
(re-make the M1-M3 records' generator_sha256 after M3's exit, or accept the residue).

## Predictions and regressions

See the key. In short: P1 the toy runs with zero edits to holon/; P2 the M1 gate is at least 2x faster with 4 workers;
P3 parallel outputs equal the sequential run's under G1's normalization; P4 a simulated new tag triggers re-extraction
and marks exactly `[L_abacus_small]` stale; P5 the scan above. R1 no generator digest moves; R2 no committed M0-M3
outcome changes; R3-R5 construction checks; R6 the CI gates, freeze check and frozen suite stay green.

## Environment

No GPU. The CPU substitute is per-law worker processes; no GPU enumeration is attempted. The container has 4 CPUs.

Before this prereg the session ran, for sizing only: one sequential M1 gate at BASE (279 s: G2 151, G1 75, G7 23,
G4 21; recorded in the key's thresholds), `git ls-remote` of the development target's upstream, and the closure probe
and the scan at BASE. It did not run the factory on the toy fixture, `holon drift`, or any parallel code (none existed).

## Hard constraints

AGENTS.md's rules, all of them; never clone, fetch or read anything under scroll-tech/ or spec/heldout/; no model
identifiers in any file, commit or PR text; author commits as Claude <noreply@anthropic.com>; merge commits only.

## The prereg review (folded before the prereg commit)

One fresh adversarial reviewer read this prereg before any build. Its blocking and major findings were folded in:

- The run, toy and parallel tests remove the committed outputs in their copy before running, so a command that writes
  nothing fails; the parallel run must also say it merged shards.
- P1 is tested by running the toy on the holon/ of the parent of the commit that adds targets/abacus/; claims about the
  tree (P5, R1) are evaluated at I47's exit commit and claims about history (P1, R2) over I47's own first-parent
  commits, so a later iteration's edit or a merge of the lead does not turn them red.
- Every fixture file is pinned by sha256 in the key; the scan always includes morph, morph-l2, morphl2 and abacus,
  whatever the target files say, and a file's path counts.
- Dropping `--morph` from holon/__main__.py's code needs an amendment of the M2 exhaustive scan's allowlist:
  spec/M2/amendments/I47.jsonl, preregistered here. The flag's spelling on the command line does not change.
- P2's baseline is BASE's sequential gate (BASE's own code, so HEAD's sequential path cannot be slowed to inflate the
  ratio), measured alternately, two runs each; below 4 CPUs the test fails with a message, never skips.
- P4 gains a third tag (v3: inc_b's effect also changes), predicted to make all three laws stale.

Not folded, and stated here instead: P5 is weaker than the coordinator's wording because of the conflict above. The
coordinator did not accept the weaker claim before the prereg (nobody watches this session live); the PR asks.
