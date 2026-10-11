# I3: non-vacuity (G11V), D2 zero-blob check, checker pin and upgrade procedure

Rendered from `docs/BUILD_PLAN.md` §4, I3 (debts D-c and D-e(2)). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Why

- **G11 is not a non-vacuity check (D-c).** It checks law names only. Nine PROVED laws have premises but no kernel-checked inhabitant:
  - M0: `L_par_hdr_v0`, `L_par_hdr_v1`, `L_rt_go_v0`, `L_rt_go_v1`, `L_rt_go_v2`;
  - M1: `L_undo_CSR`, `L_undo_BD`, `L_disch_stale`, `L_disch_stale_commit`.

  A law with unsatisfiable premises is true and useless (whitepaper §12.3, L21).
- **D2 is unchecked (D-e(2)).** It says ZERO_VERSIONED_HASH equals the KZG versioned hash of the zero blob. Until now, no code checked it.
- **GENV checks a version string, not the checker that actually runs.** An accepted canary does not quarantine anything, and there is no upgrade procedure (§8.8).

## What to build

1. **Prereg commit first.** It contains the `I3` key, the red tests `tests_m2/test_nonvacuity.py`, `test_zero_blob.py` and `test_pins.py`, and this prompt.
2. **`holon/inhabit.py`.** `inhabit(law, m, root, out_dir, cfg, cm=None) -> dict` returns the `non_vacuity` record of a law. For a law that has premises and a PROVED status, it writes `<out_dir>/nonvac/{LAWS.bend, PROOF.bend}` and checks them with both kernels.
   - **holon-ir/0.2.** The inhabitant law is generated from the parent IR: the same binders made existential, and the claim is the conjunction of the parent's premises. It is emitted by the same emitter, so the premise texts are identical, and proved by evaluation.
     - The witness comes from the compiled model's search, `explore.mjs`, run on the parent with its claim replaced. When two binders are states, the replacement claim is `s_a == s_b`, so a found inhabitant is non-degenerate. Otherwise it is `true == false`.
   - **holon-ir/0.1.** The premises are pins of header fields. The inhabitant states them explicitly through the model's getters, `M.get_<field>(h) == [bytes]`, for the header carrying the pin bytes with zeros elsewhere.
   - **Record.** `{status, law, witness, reachable, degenerate, parent_statement_hash, bound}`.
     - `status` is one of: `inhabited`, `counter_witness` (a REFUTED law: its accepted counter-law already inhabits the premises), `no_premises`, `unknown`.
     - `reachable` is true when every state binder is `run(p, s0)`.
     - `degenerate` is true when two state binders are equal.
3. **Gate check G11V.** Every premised PROVED law needs an accepted inhabitant. The inhabitant's `LAWS.bend` states exactly `nv_<id>`, and its premises equal the parent's. G11's frozen meaning stays as it is. The v2 schema replaces `pending:I3`.
4. **`holon/oracles/zero_blob.py`.**
   - `compute()` gives `0x01 ‖ sha256(0xc0 ‖ 0^47)[1:]`.
   - `check(morph)` compares it with `ZERO_VERSIONED_HASH` (Rollup.sol:25) and `EmptyVersionedHash` (common/blob/payload.go:22).
   - `python -m holon oracle zero-blob --morph PATH` writes `results/M2/hypotheses.json["Hyp-Z0-kzg"]`.
5. **Checker pin.**
   - `bend.fingerprint()` hashes the resolved checkout's git HEAD, every `bend2/*.ts`, `bend2/bendtt.lean` and the bun version, giving `fingerprint: "sha256:..."`. It is pinned as `config/holon.json: bend.pinned_fingerprint`.
   - **GENV** fails on any of: a fingerprint mismatch, an override that cannot be resolved, a global bunfig (`$HOME/.bunfig.toml`, `$XDG_CONFIG_HOME/.bunfig.toml`), or a quarantine for the current fingerprint.
   - `bend._env()` sets `BEND_NO_TELEMETRY=1`.
   - An accepted canary writes `results/quarantine.json` through `gate.quarantine(root, fingerprint, ids)`. This is an agent-writable tripwire, and is labelled as one.
   - **Time budget.** `bend.budget_s_per_file`, default 120. G5 fails a proof that goes over budget. Timings go to `results/<m>/gate_timing.json`, which G1 excludes.
   - `python -m holon checker-upgrade --to FINGERPRINT [--bend-cmd CMD] [--milestones M0,M1] --out PATH` runs the gates and `holon run` in a scratch copy under the candidate checker, and reports every record diff. Adopting the candidate is a human config change.

## Rules

Never edit frozen files or `spec/M1/facts/`. Statement hashes do not change. A missed prediction is a Surprise. An inhabitant that cannot be found is UNKNOWN with its bound, and G11V fails for that law: it is never "fixed" by editing premises.
