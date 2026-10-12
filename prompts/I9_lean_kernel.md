# I9: Lean second kernel for M0

Rendered from `docs/BUILD_PLAN.md` §4, I9 (closes D-d for M0).

## What to build

- **Emitters.** `holon/gen/lean_model.py` (`Hdr` as a structure of byte fields), `holon/gen/lean_laws.py` and `holon/gen/lean_proofs.py`, from the M0 IR and facts.
  - They must not import the Bend emitters (`holon/gen/model.py`, `laws.py`, `proofs.py`).
  - The IR statement hash goes in a doc comment.
- **Proofs.**
  - Use `rfl`, `simp` and per-cell lemmas, with `set_option maxRecDepth` per file.
  - `decide` only on closed concrete goals (counter-witnesses).
  - No `bv_decide`, `native_decide`, `sorry`, `axiom` or `unsafe`.
- **The runner, `holon/lean.py`.**
  - `python -m holon lean --milestone M0 [--json]` regenerates `gen/M0/lean/<law>.lean` and checks each file in a temporary lake project. The toolchain is `leanprover/lean4:v4.34.0`, with no Mathlib.
  - It audits `#print axioms`; allowed: `propext`, `Quot.sound`.
  - It reports `{laws: {id: {result, axioms, seconds}}}`.
  - It also provides `check_text(src, tmpdir)` and `flip_canary(src)`.
- **Records and gate.**
  - The records' `kernels[]` gain `{name: "lean4", version: "4.34.0", role: "second-independent", result}`.
  - `independence_class` is `I2` when Bend and Lean agree.
  - G7 reports the Lean kernel for M0.

## Rules

- Never edit the frozen M0 files, `tests/` or the Bend emitters' outputs.
- A goal that exceeds the budget is UNKNOWN with the reason recorded. It is never weakened.
