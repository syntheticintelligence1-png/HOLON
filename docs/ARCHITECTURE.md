# HOLON v2: architecture, status and next steps

This file maps the whitepaper (HOLON v2, October 2026) onto the code. It records what M0 delivered and lays out the foundations M1 will build on. The M0 contract itself lives in `docs/M0_SPEC.md`. Bend facts are in `docs/BEND_PRIMER.md` (frozen) and `docs/BEND_NOTES.md` (measured here).

## 1. The factory loop, as built

```
facts/*.json ──holon.gen.model──▶ gen/M0/model/morph_header.bend ──bend -o .mjs──▶ compiled model (node)
laws/M0/*.json (frozen IR) ──holon.gen.laws──▶ gen/M0/<law>/LAWS.bend   (one law, premises by pinning)
                             holon.gen.proofs ─▶ gen/M0/<law>/PROOF.bend  (open_refl | version_split)
                 if Bend rejects: holon.refute (search on compiled model) ─▶ counter-law (exs, witness literal)
Bend 2 (bend2) ─▶ PROVED / REFUTED / UNKNOWN ─▶ BendTT --verdict (Lean-proven kernel) ─▶ results/M0/*.json
holon replay: witnesses ─▶ real Go (go test) + real Solidity (forge, harness inherits Rollup) ─▶ replay/M0/report.json
holon gate:  GENV → G2 → G1 → G5 → G3 → G11 → G7 → G4 (canaries) ─▶ results/M0/gate_report.json
```

| Whitepaper | Code | Notes |
|---|---|---|
| §4 protocol diagram (carriers, edges) | `facts/` + `holon/facts.py` | M0: one interface carrier (header bytes), record carrier Header, CODEC edges. Facts are hand-written until M2. |
| §8.9 law IR, statement hash = IR hash | `holon/ir.py`, `laws/M0/REGISTRY.json` | Kernel-agnostic. The Bend text is derived from it, never the other way round. |
| §8.3 compiling 𝔇 to 𝔅 | `holon/gen/model.py` | One type per carrier, one def per edge. Definedness explicit: 0xDEAD bytes mark a revert or unwritten memory. Version dispatch through `<fn>_at(n: Nat, ..)`. |
| §10.2 layout algebra | `holon/layout.py`, `python -m holon layout FN V` | Symbolic layouts; Appendix C reproduced. |
| §8.4 law schemas, §8.5 hypothesis discipline | `holon/gen/laws.py` | PAR only in M0. Premises are pinned, never dropped; an inexpressible premise raises `Unsupported`, giving UNKNOWN. No axioms exist anywhere. |
| §10.4 proof generators per class | `holon/gen/proofs.py` | `open_refl` (proof by computation), `version_split` (case split on the version byte with a lemma), `counter` (refutation). |
| §10.5 refutation engines | `holon/refute.py` | Deterministic boundary-value and fixed-seed search, evaluated on the compiled Bend model, never in Python. Every intermediate subterm must be defined. |
| §8.6 three outcomes, result records | `holon/pipeline.py`, `schemas/result_record.schema.json` | Records carry the statement hash, facts hash, premises, scope, kernel and verdict, artifacts, attempts, triage and replay. |
| §8.7 refinement evidence by replay | `holon/replay.py`, `replay/M0/` | Go and Solidity harnesses read the witnesses from the records. A replay counts for a record only if the witness hash matches. |
| §8.8 trusting the kernel | `holon/bend.py`, gate G4/G7 | Canaries (must be rejected for a *semantic* reason), BendTT second kernel, pinned version, Bun-config tamper guard. |
| §9.3 gate | `holon/gate.py` | G1, G2, G3, G4, G5, G7, G11, GENV. G6 is covered by `holon replay` plus `tests/test_50_replay.py`. G8–G10 arrive with extraction (M2) and the intent lane (M5). |
| §9.4 statement freezing | `FROZEN.sha256`, `tools/freeze.py`, G2 | Provers and generators have no write path to `laws/`. |

## 2. M0 status: exit criteria (whitepaper §15.2)

| Criterion | Result |
|---|---|
| v0 and v1 PROVED | `L_par_hdr_v0` and `L_par_hdr_v1` PROVED (`open_refl`), plus `L_rt_go_v{0,1,2}` PROVED |
| v2 and the domain law REFUTED with the predicted witnesses | `L_par_hdr_v2`: zero header, version 2, byte 0 is 2 vs 1. `L_dom_hdr`: 250 zero bytes, Solidity true / Go false. Also `L_par_hdr_ssvh` REFUTED, first difference at 185, triaged as an intent question. |
| All canaries rejected | 16 canaries (pin_const, swap_fn, negated), all rejected with an expected/observed mismatch |
| One law dual-kernel | **All 8** re-checked by BendTT `--verdict` (Lean-proven kernel) |
| Witnesses replay on the real code | Go: all 3 REFUTED witnesses replay at morph `3e44e79`. Solidity: `L_dom_hdr` replays through the real `Rollup._loadBatchHeader`. The commit-path replays (v2 byte 0, ssvh) need deployment wiring and belong to M1. |
| Mutation adequacy (A1 in miniature) | All 4 planted bugs move outcomes as predicted. MUT3 reaches **PROVED** (case-split proof), not just UNKNOWN. |
| Predictions vs. outcomes | 8/8 preregistered outcomes matched on the first mechanized run |

Reproduce:

```
tools/setup_env.sh                          # Bend 2.0.36 (pinned) + Lean 4.34.0
python -m holon run --milestone M0          # about 10 s including --verdict
python -m holon gate --milestone M0         # about 35 s
python -m unittest discover -s tests -t .   # about 4 min
tools/setup_env.sh --replay && PATH=~/.holon/foundry:$PATH \
  python -m holon replay --morph ~/.holon/morph --solc ~/.holon/solc-0.8.24
HOLON_REPLAY=1 python -m unittest tests.test_50_replay
```

## 3. Design decisions worth knowing

1. **Premises by pinning, not implication.** `∀h. P(pin(h))` is equivalent to `∀h. prem(h) → P(h)`, because `pin` is onto the premise set and is the identity on it. It keeps proofs computational: no hypothesis to thread through. A contradictory pin set is refused, which guards vacuity (G11, L21).
2. **The refuter evaluates IR terms on the compiled model** (`holon/js/eval.mjs`), so witnesses are model behaviour. The only Python involvement is moving values in and out. Bend's acceptance of the counter-law is still what makes a law REFUTED. Gate G4 exists to catch a refuter or emitter that lies.
3. **Generators dispatch on statement shape, never on law ids** (AGENTS.md rule 4). A new law of an existing class needs no code.
4. **Records are deterministic functions of (facts, laws, replay report).** Only `seconds` fields vary. G1 compares the generated `.bend` files and `summary.json` byte for byte.
5. **Canaries must fail for a semantic reason.** A canary that Bend rejects because of a parse error would count as rejected while proving nothing, so G4 requires the checker's `- expected :` mismatch.

## 4. M1: the rollup state-machine slice (next)

Scope (whitepaper §15.2): registers CB, CSR, BVH, BD, CH, LCI, LFI, P, T, L, enq, inChallenge, s, W, D; actions commit (three kinds), revert, challenge, prove, finalize, pause; rules UNDO, DISCH, SORT, NAT, SYM-ω. Predictions to hit are the M1 rows of whitepaper §11.8.

The foundations M1 builds on, all present now:

- **Kept:** `holon/bend.py` (runner, verdict), `holon/ir.py` (hashing, freezing), `holon/gate.py` (G1–G11 skeleton, canaries), `holon/replay.py` (witness-hash-bound replay), the result-record schema, and the run/gate/replay CLI.
- **To extend:**
  1. **IR `holon-ir/0.2`.** Add binders of state and action-sequence types; claim forms `obs(trace) == obs(trace')` (UNDO), `exs strategy` and `invariant` (DISCH); explicit `scope: bounded(H)`. Bump the IR version: 0.1 laws keep hashing the same.
  2. **Facts `holon-facts/0.2` for transitions.** Per action: guard (`require` list), reads and writes (index-sensitive), principal class, and time as an environment move. Hand-written for the slice until M2, with the same source-line discipline as `morph_header.json`.
  3. **Model generator for state.** State as a record of small per-index maps (BEND_NOTES §3: keep each law under about 1 000 fields). `step_a : S → In → Env → Result(S, Obs)`, revert as a result variant, plus `Reach` as an inductive predicate.
  4. **New proof generator classes:**
     - `bisim_step`: UNDO dead residue, via the relation "equal outside Res" (Thm 6.9(i)), one step lemma per action.
     - `strategy`: a DISCH profile point, as a terminating program.
     - `invariant`: DISCH blocking (Thm 6.10).
     - `sort_coercion`: `realize(d, proof)` for sign obligations (§7.8).
  5. **Refuter for traces.** Bounded action sequences over a small index window, evaluated on the compiled model. Witnesses become Foundry tests against a deployed `Rollup` (whitepaper §10.9), which also closes the two `not_applicable` Solidity replays from M0.
  6. **Carrier ranges from ABI types** (facts audit A1), so the refuter prefers reachable witnesses (`numL1Messages` is `uint16`).
- **First experiments, in order:**
  1. `L_undo_CSR` / `L_undo_BD` PROVED and `L_undo_BVH` REFUTED (the BVH pin, O11). This is the smallest state slice: CB, CSR, BVH, BD at indices i and i+1.
  2. `L_sort_remaining` REFUTED (O27, unsigned underflow at `t = s + W + 1`).
  3. `L_tag_BVH` REFUTED (O26, ghost tag across revert).
  4. `L_disch_delay` profile and `L_disch_stale` blocking.

## 5. Known gaps (whitepaper §12, as they stand today)

| Gap | Current mitigation | Planned |
|---|---|---|
| L1 model ≠ code | Facts audit (all match); witness replay on real Go and Solidity | Per-edge replay on historical inputs (M2) |
| L2 reachable set | Header fields range over all bytes, an over-approximation (facts audit A1) | ABI ranges; `Reach` predicate (M1) |
| L16 young kernel | Dual kernel on every certificate; canaries; pin; Bun guard | Lean export of the law IR (whitepaper §8.9) if BendTT and bend2 share a bug |
| L17 termination and scope | M0 laws are unbounded (structural proofs) | `scope: bounded(H)` in IR 0.2 for trace laws |
| Installer runner | Only the pinned checkout runner is verified (installer host blocked here) | Verify where `bend-lang.com` is reachable |
