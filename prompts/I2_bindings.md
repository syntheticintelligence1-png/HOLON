# I2: semantic bindings and dependency index

Rendered from `docs/BUILD_PLAN.md` §4, I2 (debt D-h). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Why

A frozen statement's hash covers its IR and the facts hash, but not the model definitions the statement calls. Several names lie outside the statement hash:
- generator-defined names: `perm`, `runs_ok`, `no_code`, `cost`, `elapsed`, `last_ok`, `is_<act>`, `view_intact`;
- the observers;
- the `b_*` builtins.

Any of these can change meaning while G2 still passes.

## What to build

1. **Prereg commit first.** It contains the `I2` key of `spec/M2/predictions.json`, the red test `tests_m2/test_bindings.py` and this prompt. Push it before implementing.
2. **Kernel definitions.** `holon/bindings.py` translates each generated model with the pinned checker (`bend model.bend -o model.bendtt`). It parses the BendTT entries: the name, and the alpha-normalized type and body of every definition and datatype, including the Base definitions the model uses. Constructor tags are mapped to the datatype that declares them.
   - This is a dependency graph from the checker's own elaborator, not from HOLON's text.
   - It replaces the plan's "index from the generator's def list".
   - The I1 token cone and this kernel cone must agree on the model's own definitions.
3. **Kernel cone of a law.**
   - Roots: the `M.<name>` references of the emitted frozen statement (constructors map to their type).
   - Closure: the BendTT graph.
4. **Index file.** `gen/<m>/model/<model>.defs.json` maps each kernel definition to `{sha256 of its BendTT entry, refs}`. It is generated, so G1 compares it.
5. **Bindings.** `spec/bindings/<m>.json` maps law_id to `{statement_hash, cone: {def: sha256}}`. These files are not under `laws/M0`, which is frozen: no file may be added there.
   - `python -m holon bind --milestone M` writes a bindings file if it is absent.
   - It refuses to change an existing binding unless given `--accept-change "<reason>"`. That flag appends `{laws, defs, reason}` to `spec/bindings/changes.jsonl`.
   - The channel is self-certified until I10 and Q1.
6. **Dependents.** `results/<m>/deps.json` maps each definition to the laws whose kernel cone contains it: the stale index.
7. **G2 extension.** Re-derive the bindings from the committed `gen/<m>/model/*.bend`. A mismatch FAILS, naming each law and definition. Renaming a local variable or editing a comment changes no BendTT entry, so it fails nothing.

## Rules

- Never edit frozen files or `spec/M1/facts/`.
- Statement hashes do not change: the bindings are a sidecar.
- A missed prediction is a Surprise.
