# I43 — Theory Core II; Lean for the Promoted Set

## Context
- **Iteration**: `I43` (Milestone `M3`)
- **Branch**: `claude/i43-theory-core-ii`
- **Preregistration**: `spec/M3/lib/theory_core_ii.json`, `tests_m3/_i43.py`, `tests_m3/test_theory_core_ii.py`, `spec/M3/predictions.json` (`"I43"`)
- **Whitepaper**: `whitepaper.md` §§6.1–6.2, §6.4, §8.8
- **Human answers**: `docs/HUMAN_ANSWERS.md` (`Q2b`, `Q6`, `Q8`, `Q11b`, `Q12`, `Q14c`)

## Objective
1. Extend `holon/gen/core.py` with `THEORY_CORE_II` (10 polymorphic Bend 2 laws across `equivariance` and `pasting`: `core_equivar_compose`, `core_equivar_whisker`, `core_equivar_obs`, `core_equivar_pred`, `core_equivar_homotopy` — 2-cell homotopy transport of equivariance across a pointwise equal source step — and `core_paste_grid_2x2`, `core_paste_h_3`, `core_paste_v_obs`, `core_paste_square_trans`, `core_paste_whisker_interchange`) and emit them into `gen/M3/core/{LAWS,PROOF}.bend` (bringing `gen/M3/core` to `31 + 12 + 10 = 53` laws while keeping `gen/M2/core/{LAWS,PROOF}.bend` untouched at 31 laws per `AGENTS.md`).
2. Extend `holon/gen/basis.py` to emit:
   - `gen/M3/basis/equivariance/{LAWS,PROOF}.bend` (4 concrete equivariance laws over `gen/M1/model/morph_rollup.bend`: `basis_equivar_mig_legacy_wait`, `basis_equivar_mig_legacy_send_msg`, `basis_equivar_mig_eta2_wait`, and `basis_equivar_mig_compose_wait` via `C.core_equivar_whisker`).
   - `gen/M3/basis/pasting/{LAWS,PROOF}.bend` (4 concrete pasting laws over `gen/M1/model/morph_rollup.bend`: `basis_paste_lci_mig_legacy`, `basis_paste_lci_mig_eta2`, `basis_paste_lci_mig_chain`, and `basis_paste_tags_mig_chain` via `C.core_paste_v_obs`).
   - Preserve `gen/M3/basis/{header,header_length,congruence}` and `results/M3/basis.json` from I42 byte-for-byte.
3. Extend `holon/lean.py` (and `holon/gen/lean_*.py`) to generate the Lean 4.34.0 Lake project in `gen/M3/lean/` (`lean-toolchain`, `lakefile.toml`, `Holon.lean`, `Holon/...`, `report.json`) and emit `results/M3/lean.json`:
   - `gen/M3/lean/lakefile.toml` uses `[[lean_lib]]` with `name = "Holon"` and `globs = ["Holon.*"]`, `Holon.lean` is a doc-only root module without `import` statements, and every `Holon/**/*.lean` file is self-contained without `import` statements so `holon.lean.forbidden(txt)` is `[]` (G3 compliance). `gen/M3/lean/report.json` is written alongside `results/M3/lean.json`.
   - Verify all 92 `PROVED` laws across M0..M3 (`5` M0 + `8` M1 + `6` M2 + `73` M3) in Lean 4.34.0 and promote them to `independence_class: "I2"` with a checked `lean4` kernel entry (`role: "second-independent"`, axioms subset of `{"Quot.sound", "propext"}`, zero `sorry`/`admit`/`axiom`/`native_decide`/`unsafe`, `holon.lean.forbidden(txt) == []`).
   - Verify all 10 `THEORY_CORE_II` laws and 8 concrete `equivariance`/`pasting` basis laws in both Bend (`bend` + `bend --verdict`) and Lean 4.34.0.
   - Verify all 5 negative canaries (`canary_equivar_compose_swapped`, `canary_paste_grid_2x2_missing_v`, `canary_equivar_mig_eta2_unmigrated_rhs`, `canary_paste_csr_last_mig_legacy` under both `bend` and `bend --verdict`, plus the Lean 4 canary `canary_lean_flipped_claim` semantically rejected by `holon.lean.check_text`).
4. Target-agnosticism and prior-milestone immutability:
   - Generators in `holon/` (`holon/gen/core.py`, `holon/gen/basis.py`, `holon/lean.py`, `holon/gen/lean_*.py`) must remain target-agnostic: any concrete Morph rollup/header law specifications for basis or Lean generation must be read from data files under `spec/M3/`, `facts/`, `laws/`, or `gen/M1/model/morph_rollup.bend` rather than hardcoding Morph identifier strings inside `holon/*.py`, so `tests_m2/test_target_agnostic_exhaustive.py` continues to pass.
   - `gen/M0/`, `gen/M1/`, `gen/M2/`, and `results/M0/` are NOT modified in M3; `results/M1/L_*.json`, `results/M2/L_*.json`, and `results/M3/L_*.json` have only their `"generator_sha256"` field updated because `holon.records.generator_sha256("holon-ir/0.2")` and `holon.records.generator_sha256("holon-ir/0.3")` hash `holon/gen/core.py` (enforced by `tests_m2/test_gate.py` and `tests_m3/test_m3_pipeline.py`), while the 92-law `I2` promotion ledger is recorded in `results/M3/lean.json` and `gen/M3/lean/report.json`.

## Predictions (`spec/M3/predictions.json` → `I43`)
- `I43-P1`: `holon.gen.core.THEORY_CORE_II` registers all 10 preregistered polymorphic laws (5 equivariance including `core_equivar_homotopy` + 5 pasting); `holon.gen.core.emit` reproduces `gen/M3/core/{LAWS,PROOF}.bend` (53 laws = `31 CATALOG + 12 THEORY_CORE_I + 10 THEORY_CORE_II`) and `gen/M2/core/{LAWS,PROOF}.bend` (31 laws) byte-for-byte, passing `bend` and `bend --verdict` (`LAWS.bend` alone fails `bend --verdict`) while keeping `holon/` target-agnostic.
- `I43-P2`: `gen/M3/basis/equivariance/{LAWS,PROOF}.bend` proves all 4 concrete equivariance laws (`basis_equivar_mig_legacy_wait`, `basis_equivar_mig_legacy_send_msg`, `basis_equivar_mig_eta2_wait`, `basis_equivar_mig_compose_wait`) under `bend` and `bend --verdict`.
- `I43-P3`: `gen/M3/basis/pasting/{LAWS,PROOF}.bend` proves all 4 concrete pasting laws (`basis_paste_lci_mig_legacy`, `basis_paste_lci_mig_eta2`, `basis_paste_lci_mig_chain`, `basis_paste_tags_mig_chain`) under `bend` and `bend --verdict`.
- `I43-P4`: All 5 negative canaries across `theory_core_ii`, `equivariance`, `pasting`, and `lean` (4 Bend canaries + 1 Lean 4 canary `canary_lean_flipped_claim`) are `REFUTED` / semantically rejected with genuine type/tactic mismatches.
- `I43-P5`: `gen/M3/lean/` builds cleanly under `lake build --no-cache` with Lean 4.34.0, `holon.lean.forbidden(txt) == []`, and `#print axioms` verification, and `gen/M3/lean/report.json` + `results/M3/lean.json` record all 92 promoted `PROVED` laws across M0..M3 (`5` M0 + `8` M1 + `6` M2 + `73` M3) at `independence_class == "I2"` with axioms within `{"Quot.sound", "propext"}`.
- `I43-P6`: `spec/M3/lib/theory_core_ii.json` is byte-identical to `tests_m3._i43.theory_core_ii_doc(ROOT)` over verified input sha256s and `tests_m3/_i43.py` does not import `holon.gen.{basis,core,mproofs,lean_*}` or `holon.lean`.

## Verification Commands
```bash
python3 -m unittest tests_m3/test_theory_core_ii.py -v
python3 -m holon audit prereg --milestone M3
```
