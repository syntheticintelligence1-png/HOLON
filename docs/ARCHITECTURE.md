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
holon gate:  GENV → G2 → G1 → G5 → G3 → G11 → G11V → G6 → G9 → G7 → G4 (canaries) ─▶ results/M0/gate_report.json
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
| §8.6 three outcomes, result records | `holon/pipeline.py`, `holon/records.py`, `schemas/result_record.schema.json`, `spec/schemas/result_record_v2.schema.json` | Records carry the statement hash, facts hash, premises, scope, kernel and verdict, artifacts, attempts, triage and replay. Since I1, records also carry the v2 fields of §4b. |
| §8.7 refinement evidence by replay | `holon/replay.py`, `holon/mreplay.py`, `holon/consumers.py`, `replay/M0/`, `replay/M1/` | Go and Solidity harnesses read the witnesses from the records. A replay counts for a record only if the witness hash matches. Since I4 every side the witness claims is replayed: the M0 codec witnesses also on the commit path of a deployed Rollup, and `L_tag_BVH` / `L_fact_Z` also at a Go consumer fed the bytes the chain replay logged. Each side records `provenance` and `obstruction_observed`, set from the real code's output. The toolchain (forge, solc, Solidity deps) is pinned by sha256 in `config/holon.json` `replay`. |
| §9.6, §10.9 provisional finding filter (I4) | `holon/filter.py` | REFUTED records carry `witness_provenance` (side → public_schedule, internal_harness, emulated_storage or library_api) and `filter_bin` (finding, model_defect, pending), recomputed by G6 from the replay report. `known_limitation` waits for I40. Bins are about reproducibility; v1 `triage` (intent) is untouched. |
| §11 case-study coverage (I4) | `tools/casestudy.py`, `spec/ledger/maps_to.json` | `results/casestudy_coverage.json` and `docs/CASESTUDY.md`, computed from the whitepaper catalog, the law mappings, the records and the replay reports. |
| §8.8 trusting the kernel | `holon/bend.py`, gate G4/G7 | Canaries (must be rejected for a *semantic* reason), a pinned version, and a Bun-config tamper guard. BendTT `--verdict` re-checks bend2's elaboration of the same file. It shares the front end, so dual-checked results are class `I1-shared`, not the independent `I2` of §8.8. Since I9, the M0 laws are also re-proved in Lean 4.34.0 (`holon/lean.py`, `holon/gen/lean_*.py`: own emitters, Lean's elaborator and kernel), which makes them `I2`; M1 stays `I1-shared` until I43. |
| §9.3 gate | `holon/gate.py` | GENV, G1, G2, G3, G4, G5, G6, G7, G9, G11, G11V. G6 binds REFUTED records to the committed replay report; the replays themselves run through `holon replay` and `tests/test_50_replay.py`. G8 (coverage) arrives with extraction (M2) and G10 with the intent lane (M5). G11 checks only law names; non-vacuity is G11V (I3, `holon/inhabit.py`): every PROVED law that has premises has a dual-checked inhabitant. The inhabitant is regenerated from the parent's IR and the recorded witness, and must be reachable and non-degenerate where states are involved. |
| §8.8 checker pin (I3) | `holon/bend.py fingerprint()`, GENV, `holon/checker_upgrade.py` | Pinned in `config/holon.json`. The fingerprint hashes the resolved checkout's HEAD, every `.ts`, `.lean` and `.bend` file under `bend2/`, and bun. GENV refuses a mismatch, an unresolvable override, a global bunfig, a `BENDTT` override, or a quarantine. Bend runs without `BUN_OPTIONS` and with `BEND_NO_TELEMETRY=1`. An accepted canary writes `results/quarantine.json`, an agent-writable tripwire. G5 enforces a per-file time budget. `python -m holon checker-upgrade` reports every record diff under a candidate checker. |
| §11.6 D2 (I3) | `holon/oracles/zero_blob.py`, `results/M2/hypotheses.json` | `0x01 ‖ sha256(0xc0 ‖ 0^47)[1:]` equals ZERO_VERSIONED_HASH (Rollup.sol:25) and EmptyVersionedHash (common/blob/payload.go:22), checked on a clean checkout at the target commit. |
| §9.4 statement freezing | `FROZEN.sha256`, `tools/freeze.py`, G2 | Provers and generators have no write path to `laws/`. |

## 2. M0 status: exit criteria (whitepaper §15.2)

| Criterion | Result |
|---|---|
| v0 and v1 PROVED | `L_par_hdr_v0` and `L_par_hdr_v1` PROVED (`open_refl`), plus `L_rt_go_v{0,1,2}` PROVED |
| v2 and the domain law REFUTED with the predicted witnesses | `L_par_hdr_v2`: zero header, version 2, byte 0 is 2 vs 1. `L_dom_hdr`: 250 zero bytes, Solidity true / Go false. Also `L_par_hdr_ssvh` REFUTED, first difference at 185, triaged as an intent question. |
| All canaries rejected | 16 canaries (pin_const, swap_fn, negated), all rejected with an expected/observed mismatch |
| One law dual-kernel | **All 8** re-checked by BendTT `--verdict` (a Lean-proven kernel). BendTT shares bend2's front end, so this is the `I1-shared` class, not an independent second kernel. The frozen M0 spec allowed the substitution. Since I9, all 8 are also re-checked in Lean 4.34.0 from the IR (the 5 laws proved, the 3 counter-laws at the recorded witnesses; axioms within {propext, Quot.sound}), so the records say `I2` (`docs/iterations/I9.md`). |
| Witnesses replay on the real code | Go: all 3 REFUTED witnesses replay at morph `3e44e79`. Solidity: `L_dom_hdr` replays through the real `Rollup._loadBatchHeader` (an internal harness). Since I4 the commit-path replays run on a deployed Rollup: version 2 commits byte 0 = 0x02, and version 1 writes the ssvh cells as zero, with keccak(header) == committedBatches. |
| Mutation adequacy (A1 in miniature) | All 4 planted bugs move outcomes as predicted. MUT3 reaches **PROVED** (case-split proof), not just UNKNOWN. |
| Predictions vs. outcomes | 8/8 preregistered outcomes matched on the first mechanized run |

Reproduce:

```
tools/setup_env.sh                          # Bend 2.0.36 (pinned) + Lean 4.34.0
python -m holon run --milestone M0          # about 10 s including --verdict
python -m holon gate --milestone M0         # about 35 s
python -m unittest discover -s tests -t .   # about 4 min
tools/setup_env.sh --replay                 # forge, solc, a morph checkout
python -m holon replay --milestone M0       # paths and sha256 pins from config/holon.json replay
python -m holon replay --milestone M1       # (--write-pins records new pins, for human review)
HOLON_REPLAY=1 python -m unittest tests.test_50_replay tests_m1.test_m1_replay
python tools/casestudy.py                   # results/casestudy_coverage.json, docs/CASESTUDY.md
```

## 3. Design decisions worth knowing

1. **Premises by pinning, not implication.** `∀h. P(pin(h))` is equivalent to `∀h. prem(h) → P(h)`, because `pin` is onto the premise set and is the identity on it. It keeps proofs computational: no hypothesis to thread through. A contradictory pin set is refused, which guards vacuity (G11, L21).
2. **The refuter evaluates IR terms on the compiled model** (`holon/js/eval.mjs`), so witnesses are model behaviour. The only Python involvement is moving values in and out. Bend's acceptance of the counter-law is still what makes a law REFUTED. Gate G4 exists to catch a refuter or emitter that lies.
3. **Generators dispatch on statement shape, never on law ids** (AGENTS.md rule 4). A new law of an existing class needs no code.
4. **Records are deterministic functions of (facts, laws, replay report).** Only `seconds` fields vary. G1 compares the generated `.bend` files and `summary.json` byte for byte.
5. **Canaries must fail for a semantic reason.** A canary that Bend rejects because of a parse error would count as rejected while proving nothing, so G4 requires the checker's `- expected :` mismatch.

## 4. M1: the rollup state-machine slice (DONE, see docs/M1_REPORT.md)

M1 was built along the plan below. Where it differs:
- **Window/shadow representation.** It makes UNDO non-interference structural.
- **Absolute-index arrays for challenges.** These make the DISCH proofs need only generic list and Nat lemmas.
- **A second machine for the Go OWN law.**
- **Proof generators:** `noninterference`, `deadline`, `chain_revert`, `nat_split`, `evaluate` and `counter`.

The original plan follows for the record.

Scope (whitepaper §15.2): registers CB, CSR, BVH, BD, CH, LCI, LFI, P, T, L, enq, inChallenge, s, W, D; actions commit (three kinds), revert, challenge, prove, finalize, pause; rules UNDO, DISCH, SORT, NAT, SYM-ω. Predictions to hit are the M1 rows of whitepaper §11.8.

The foundations M1 builds on, all present now:

- **Kept:** `holon/bend.py` (runner, verdict), `holon/ir.py` (hashing, freezing), `holon/gate.py` (G1–G11 skeleton, canaries), `holon/replay.py` (witness-hash-bound replay), the result-record schema, and the run/gate/replay CLI.
- **To extend:**
  1. **IR `holon-ir/0.2`.** Add binders of state and action-sequence types; claim forms `obs(trace) == obs(trace')` (UNDO), `exs strategy` and `invariant` (DISCH); explicit `scope: bounded(H)`. Bump the IR version: 0.1 laws keep hashing the same.
     *As built, this differs.* 0.2 has `forall`/`exists` binders and a claim that is one equation or a conjunction. It has no `invariant` form and no `scope` key. Strategies are ∃-trace laws, and blocking is a ∀-step law over states. The grammar is in `holon/gen/mlaws.py`, and the schema in `spec/schemas/law_ir_0_2.schema.json`. Scope lives in each record's `scope_v2`.
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

## 4b. Records v2 and the assumption ledger (I1)

Every result record now carries one field per §8.6 item, next to the frozen v1 fields. The builder is `holon/records.py`, and the schema is `spec/schemas/result_record_v2.schema.json`.

- `premises` are exactly the rendered assume clauses of the frozen statement.
- `cone` is the set of generated model definitions that the emitted statement reaches.
- `model_assumptions` are the entries of `spec/ledger/assumptions.json` whose introducing definitions meet the cone. The ledger classifies every definition of every generated model.
- `kernels` and `independence_class`: BendTT shares bend2's elaboration, so dual-checked results are class `I1-shared`, not `I2`.
- Fields that a later iteration fills hold `pending:I<n>`.

The gate now also runs:
- **G1** over records;
- **G6**: every REFUTED record is bound to a passed replay of the same witness for the facts' target commit, and a side not replayed is labelled `model-only pending replay`. Strict since I4: exactly the claimed sides, well-formed, with the record's provenance and bin recomputed from the report and the toolchain hashes equal to the pins;
- **G9**: every record validates against the v1 and v2 schemas.

`python -m holon audit prereg --milestone M2` checks the preregistration order (`docs/BUILD_PLAN.md` §0.1).

## 5. Known gaps (whitepaper §12, as they stand today)

| Gap | Current mitigation | Planned |
|---|---|---|
| L1 model ≠ code | Facts audit (all match); witness replay on real Go and Solidity | Per-edge replay on historical inputs (M2) |
| L2 reachable set | Header fields range over all bytes, an over-approximation (facts audit A1) | ABI ranges; `Reach` predicate (M1) |
| L16 young kernel | Dual kernel on every certificate; canaries; pin; Bun guard | Lean export of the law IR (whitepaper §8.9) if BendTT and bend2 share a bug |
| L17 termination and scope | M0 laws are unbounded (structural proofs) | `scope: bounded(H)` in IR 0.2 for trace laws |
| Installer runner | Only the pinned checkout runner is verified (installer host blocked here) | Verify where `bend-lang.com` is reachable |
