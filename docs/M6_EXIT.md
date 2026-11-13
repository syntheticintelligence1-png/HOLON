# M6 exit

**The M6 exit is met.** The rule is `docs/BUILD_PLAN.md`'s M6 exit criterion:

> The generality run (I107) is reported. Its prereg comes before the reveal of I106's sealed targets. It covers the
> corpus rerun (labelled contaminated), the fresh sealed targets, and Morph under `--roles auto`, scored against I48
> and I52/I52b's baselines. No number is a gate: a miss is a result. Tests live in `tests_m6/`.

The lead records the decision on 2026-11-12, on the lead after I109's landing (#182, `13e8386b`).
`tests_m6/test_m6_exit.py` recomputes each clause and checks this table against it.

**What the exit says, and what it does not.** M6's purpose was to make HOLON general (the human's direction,
2026-11-12). The criterion holds because the generality run happened before anyone saw the targets and is reported
as it came out. It does not hold because HOLON is now general: on the two fresh targets, no law was derived. "The
outcome", below, says where it stops.

| Clause | Text | Holds | Evidence |
|---|---|---|---|
| X1 | the generality run (I107) is reported | yes | `docs/iterations/I107.md` scores P1-P12. `tools/i107_generality.py assemble --check` regenerates `results/eval/generality/summary.json` from the committed outcomes. Landed in #181 (`6c02f2e3`) |
| X2 | its prereg comes before the reveal of I106's sealed targets | yes | `holon audit prereg --milestone M6` prints `I107: OK prereg 480516bb9c9d`, committed 05:43:52Z, before the reveal commit `7d78b3b4` (09:13:49Z). VERIFY OK. The transcripts agree: A4 was pushed at 09:13:16, before the sealer's reveal command at 09:13:46, and I107 first read `target.json` at 09:14:15 |
| X3 | it covers the corpus rerun (labelled contaminated), the fresh sealed targets, and Morph under `--roles auto` | yes | `summary.json`: the corpus (20 rows, "contaminated: post-I51"), the sealed targets (eigenlayer, aave-v3), and Morph ("contaminated: the development target") |
| X4 | scored against I48 and I52/I52b's baselines | yes | On I48's corpus: 0 detected, a delta of -5 against the agent reviewer and -1 against slither (I52). On the sealed targets: slither on both (compile_failed). The agent reviewer and I52's other baselines did not run there, as preregistered |
| X5 | no number is a gate: a miss is a result | yes | The misses and the withheld prediction are named below. The decision does not depend on them |
| X6 | tests live in `tests_m6/` | yes | Each M6 key's prereg names its tests under `tests_m6/`. CI runs one job per key, `tests-m6-i103` to `tests-m6-i109`; `tests-m6-i106` is added at this exit |

Misses and withheld predictions of I107: P5, P6 and P7 (missed), and P8 (withheld, embargo).

## The outcome

### What M6 built

- **I103, frontend reach.** solc is chosen by pragma from a pinned set, and go by its directive. The sort pass is
  total: an unknown term becomes an opaque variable plus coverage debt, never a PROVED through it.
- **I104, role inference.** `holon roles` (static, plus an AI proposal channel) writes the role sidecars that hand
  work used to supply.
- **I105, Go state machines.** Go struct-field and KV machines in the Solidity IR, with sound havoc.
- **I106, fresh sealed targets.** Two of nine preregistered public systems, drawn by commit-reveal over a public
  beacon.
- **I108 and I109, pipeline totality.**
  - signed sort rules;
  - Foundry remappings and submodules;
  - SYM per model;
  - nil maps UNKNOWN by default, and Q60's constructor rule;
  - the Go rendering's types gaps;
  - D9's sign rule SG1;
  - opaque string keys;
  - a recorded term budget;
  - remapped pragmas;
  - Q62's empty codec layer.

### What the generality run measured

I107 measured on the tools as landed after I108 (its amendment A2).

- **The corpus** (contaminated): 14 of 20 entries extract (I51: 9), with 0 toolchain refusals. 0 laws are derived,
  so 0 of 20 are detected.
- **The fresh sealed targets** (EigenLayer v1.13.0, Aave V3 v1.19.4):
  - 87 of 95 contract documents extract;
  - the sort pass times out at 1,800 s on both, so 0 laws are derived and 0 decided;
  - slither fails to compile both;
  - both bundles are the empty-list hash, so nothing is withheld.
- **Morph under `--roles auto`:**
  - role precision is 4/11 and recall 4/6;
  - 96 of 99 decided role-dependent laws are re-derived with the same status;
  - all 330 new laws are UNKNOWN.

### Where the wall is now

- **Solidity whole systems:** the sort pass's scale. I110 works on it under Q73 and Q74.
- **Go:**
  - types refusals: whole-map writes (Q68) and I105's tuple gap;
  - no producer reads a Go codec document without `go_laws` or `go_ops` sidecars (I109's Not done).
- **After I107:** I109 got two Go corpus entries (c12, c16) through derive, with 0 laws.

In one sentence: M6 made HOLON's front half general, so it extracts most of a fresh system with no hand input, but
not its back half. No law is yet derived on a target nobody tuned it on.

## Disclosures

1. **Same-family sessions.** Every M6 key was built by an agent session of the builders' model family, as was I107's
   sole reader. The lead's rulings, Q54-Q74, are delegated. They are recorded in `docs/HUMAN_ANSWERS.md`, and the
   human can change any of them.
2. **Sealed in the repository, not from the agent's priors.** Both drawn systems are famous public repositories. The
   seal hides which two were drawn, not what they are.
3. **The coincidence.** The drawn pair matches the example layouts in I107's `test_scope_rule`, written before the
   reveal.
   - The lead recorded the possibility at 05:59:14Z, before the reveal.
   - Under a uniform draw, a given pair comes up with probability 1/36.
   - The Q54(e) transcript audit found no leak.
   - The coordinator's 09:12:44Z message naming the pair reached I107's context at 09:15:53, after A4 and after
     every measured run had started.
4. **Q56's embargo.**
   - No per-law output on a sealed target, and no new Morph verdict, is committed in plaintext.
   - Both sealed bundles are the empty-list hash.
   - The bundle of Morph's new laws (`08b101da…`) is committed and stays closed until the human opens it.
   - Before Q56, I104 published one changed Morph verdict, at 05:26: a role defect, with no witness.
5. **Q64.** Before I109, the default nil-map path could PROVE a law over a step that writes a possibly nil map, as
   in I105's demo. I107's measured runs used `nil_maps: "unknown"`. I109 made that the default and re-decided the
   demo law UNKNOWN.
6. **I107's amendments A1-A4** were all made before any measured run and before the reveal. A4 was checked from the
   transcripts.
7. **I106's report** (`docs/iterations/I106.md`) was written by the lead at this exit, from the sealer's committed
   records.
8. **A soundness finding after this exit (F-M6-01, HUMAN_ANSWERS Q94, 2026-11-13).** Until I117, the Go frontend's
   path reasoner read Go integers as unbounded.
   - 3 of Morph's 8 committed Go documents change under the opaque-arithmetic rule alone.
   - At least 28 of M3's 179 committed decided laws (PROVED and REFUTED together, Q56) read one of them; for 112 more
     decided laws, committed data does not say.
   - Morph's scores under `--roles auto`, against I48's and I52/I52b's baselines, rest partly on those laws. They are
     provisional until I119 (b) re-derives and re-decides them.
   - Exact counts at I119 (a)'s landing (`results/M6/I119/rederive.json`): M0-M2 are unaffected. In M3, 148 of the 179
     decided laws are affected, plus 14 UNKNOWN laws and 1 renumbered law. The re-decision is I121 (Q97).
   - I121's re-decision (HUMAN_ANSWERS Q115-Q117): of the 162 affected M3 laws, 161 compared, 158 unchanged and 3
     verdicts changed (PROVED and REFUTED together, Q56), and 1 renumbered. The flip, the re-extracted documents and the
     re-decided records are withheld until the human's call (Q96 (2), Q116), so these scores stay provisional.
9. **An instrument finding after this exit (F-M6-15, HUMAN_ANSWERS Q113, 2026-11-13).** From I115 until #212, `holon run
   --unbound unknown` (the base protocol's `run_unbound`) checked each law's binding before deciding it on the emitter's
   fallback names (`Header` as `Hdr`), which disagree with a Go-derived model's (`R_Header`).
   - Bindable laws were recorded UNKNOWN without being decided. It is fail-closed: no committed verdict is wrong because
     of it.
   - Every composed corpus measure from I115 to I123 ran it. In I122's counted run the binding check recorded 234 of the
     268 derived laws UNKNOWN, an upper bound on this defect's share, since a genuinely unbindable law counts there too.
   - **Corrected at I121's landing (HUMAN_ANSWERS Q117 (3), (4)).** This bullet first said those keys' corpus decided
     counts understate what their code could decide. That went beyond the evidence: 234 was an upper bound. I124's
     baseline (`e727d210` on its branch; base code `326dcc01`, `base_run.json` `1d45d89b…`), the first corpus measure
     after #212, has the same count, 234 of 268, refused by the binding pre-check, so the fix moved none of the corpus's
     laws. All 234 are PAR laws over Go ops that the Go-op model generator writes as unsupported (144 straight-line, 78
     loop-shape, 12 other): F-M6-05's mechanism at corpus scale. Their UNKNOWN is right, and the corpus's main wall is
     that generator's coverage, not the binding path.
