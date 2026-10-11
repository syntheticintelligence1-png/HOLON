# Session P2: Bend model generator and model evaluation (about half a day)

Read `AGENTS.md`, `docs/M0_SPEC.md` (§4–§6), `docs/BEND_PRIMER.md` (§4–§5) and `docs/BEND_NOTES.md`.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

## Tasks

1. **`holon/gen_model.py`: facts → Bend source of `morph_header.bend`.** The output must be deterministic.
   - `type Hdr is Data:` with one `U32` field per header byte. Name fields `<field>_<k>`, in facts field order.
   - Prelude:
     - `overlay` and `put` (BEND_PRIMER §5.1);
     - `zeros`;
     - slicing;
     - `len_ge` / `len_eq`;
     - equality functions per output type (`bytes_eq`, `bool_eq`, `fields_eq`, `maybe_fields_eq`);
     - `is_true : Bool -> Type`, needed later for counter-laws.
   - One Bend def per facts function, with the same name: `enc_sol`, `enc_go_v0`, `enc_go_v1`, `ok_sol`, `ok_go`, `dec_go`, `view`.
     - Version-dependent behaviour (`length_by_version`, `when`, `version_in`) is done by dispatching on `U32.to_nat(version)` through helper defs, because `match` cannot inspect computed values.
     - `enc_sol` outside its domain (version > 2) may return `Nil{}`.
   - Use dirty-memory sentinel `57005` for EVM memory.
   - Lists are `List<&2, U32>`. Use `+` params where values are reused.
2. **`holon/model_eval.py`: `eval_batch(fn, inputs, facts_path=None)`.**
   - Generate the model.
   - Compile it with the pinned Bend: `bend model.bend -o model.mjs`, into `build/`.
   - Run it in node with batched inputs.
   - Convert values to and from canonical JSON (M0_SPEC §4).
   - Return `engine`, `source`, `artifact`, `artifact_sha256` and `outputs`.
3. The model file must type-check: `bend gen/.../morph_header.bend` prints `ALL PROOFS CHECK`.

## Definition of done

- `python -m unittest tests.test_20_model_eval -v` passes. It checks about 600 inputs against the oracle, and that the artifact you executed is the compilation of the source you reported.
- Tests 00–12 still pass.
- No model logic in Python: Python only formats inputs and outputs.
