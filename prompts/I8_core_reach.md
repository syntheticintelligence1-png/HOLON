# I8: core library and Reach

Rendered from `docs/BUILD_PLAN.md` §4, I8. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Q14a default: core lemmas are emitted by per-class proof generators, never hand-proved.

## What to build

- **Probe first: `bend/notes/p_core_import/`.**
  - (a) `a/core/LAWS.bend` states laws `c_ok` and `c_open`. `a/core/PROOF.bend` proves only `c_ok`. `a/user/PROOF.bend` imports `../core/LAWS.bend` alone and uses `c_open` as a lemma. Does the user's check fail? (Predicted: yes.)
  - (b) Does importing a `PROOF.bend` put that file's proofs into the checked closure?
  - The design does not depend on either answer:
    - generated proofs import `core/PROOF.bend`, never `core/LAWS.bend` alone;
    - G3 bans a bare core LAWS import textually;
    - a G4 canary leaves one core law unproved.
- **`holon/gen/core.py`.**
  - `emit(gen_dir, omit=None) -> [law names]` writes `<gen_dir>/core/{LAWS.bend, PROOF.bend}`: Nat/Bool lemmas stated as laws and proved by per-class generators. `omit` leaves one law unproved (the canary).
  - `bare_laws_imports(text)`: the lines importing a core LAWS module.
  - M2+ milestones (every milestone other than M0 and M1) import `../core/PROOF.bend`. `holon run --core paste` pastes the same core text instead; that is the baseline for the G5 cost prediction.
  - M0 and M1 keep their pasted `CORE`, byte-identical.
  - G3, G5 and G7 cover the core.
- **`Reach`.** For M2+ milestones, `machine.py` emits `Reach : HSt -> Type`, with a constructor for s0 and one for a step (fallback encoding: `Σ p. s == run(p, s0)`). gen/M0 and gen/M1 do not change.
  - The IR 0.3 binder type `Reach` quantifies over reachable states: one state binder plus its Reach evidence.
- **`mproofs.reach_invariant`.** It proves an invariant by induction on `Reach`: one step lemma per action, generalised over each action's decision.
  - `holon/js/houdini.mjs` (untrusted) proposes strengthenings: field facts that hold on every explored reachable state.
  - A strengthening lives only in the proof file. The law file is the frozen statement.
- **Refutation.** A witness for a Reach binder is a reachable state given as a trace from s0, and its Reach evidence is the s0 / step chain along that trace.
- **G11V.** A `Reach` premise is inhabited by an s0 / step chain.
- **Toy machine:** `tests_m2/fixtures/toy_reach/` (registers x, y, k and a flag). Laws: `tests_m2/fixtures/reach/L8_reach_{y,x,k,flag}.json`.

## Rules

Never hand-write a proof or a lemma. A fix goes into a generator. The toy laws are frozen at the prereg.
