# I13: sorts I (grammar, constraints, union-find, unsat cores, frozen assignment)

Rendered from `docs/BUILD_PLAN.md` §4, I13 (whitepaper §7.1–§7.4, §7.7 steps 1–4, Thm 6.18 freezing condition). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact CLI, file formats and APIs are in the docstring of `tests_m2/test_sorts_morph.py`; the other `tests_m2/test_sorts_*.py` modules read the same contract.

## Goal

Infer refined sorts mechanically, and freeze the assignment before any typed check. I13 is moved before evidence because E5 is "identical refined sorts". No laws are generated here (the first generated SORT laws are I15's).

## What to build

- **`holon/sorts/`:**
  - `grammar.py`: the sort grammar of §7.1 as text (`Time`, `Dur`, `SDur`, `Idx[κ]`, `SIdx[κ]`, `Cnt[κ]`, `SCnt[κ]`, `Prin[role]`, `Amt[asset]`, `Dig[kind]`, `Ver`, `Bool`, `Mach(w)`, records, unions `σ₁ + σ₂`, and `Nat (unrefined)`), writer labels (`Idx[queue]_fin`), `parse`/`render`, and `affine(op, a, b)`: the §7.2 table (Time is a torsor over Dur, Idx[κ] over Cnt[κ]; mixing index families is ill-sorted).
  - `constraints.py`: constraints from types, value flow, the affine rules, comparisons, cross-component linking and lexical seeds (§7.7 step 1). A seed is a unit constraint: at most one per variable, listing all its grounds.
  - `flow.py`: value flow and writer sets per variable (§7.3), read from the facts actions, migrations and definitions.
  - `solve.py`: a pure-Python union-find carrying writer and role labels (§7.7 step 2); `satisfiable(constraints) -> bool`.
  - `core.py`: minimal unsatisfiable cores by deletion (QuickXplain); `minimal_core(items, satisfiable)`.
  - `unions.py`: untagged unions (§7.4): a register written along edges with distinct refined sorts carries `σ₁ + σ₂`.
- **`spec/schemas/sorts.schema.json`:** one `$defs` entry per output document, top level a `oneOf` over them.
- **`python -m holon sorts [--milestone M2] [--root DIR] [--out DIR] [--facts PATH ...]`** writes `gen/M2/sorts/{constraints, assignment, conflicts, unions, unresolved}.json` (default `--out`), from the milestone's fact documents (`facts/morph_header.json`, `spec/M1/facts/morph_rollup.json`, `spec/M1/facts/morph_batchdata.json`) or the documents `--facts` names. Commit the generated `gen/M2/sorts/`.
- **Sites are keyed by source span.** One site per subtraction and span; the copies of a guard that the M1 facts repeat per action collapse into one site, whose entry points are those actions. A site's span is the narrowest of the src containing the subtraction and the src of a same-action guard that checks its non-negativity (the contract has the exact rule). A signed sort realized in `Nat` carries a sign obligation.
- **Frozen assignment.** `assignment.json` carries `sorts_sha256` (canonical JSON of the file without `sorts_sha256` and `inputs`). The plan puts this value into `laws/M2/REGISTRY.json`, which does not exist yet and holds laws; I15 creates it with the first generated laws and copies `sorts_sha256` into it. Whenever an M2 registry exists, its `sorts_sha256` must equal `assignment.json`'s (tested).
- **Tests:** `tests_m2/test_sorts_morph.py`, `test_sorts_fixture.py` (the planted Time+Time fixture `tests_m2/fixtures/sorts/time_plus_time.json`), `test_sorts_unit.py`, `test_sorts_honesty.py`, with the helper `tests_m2/_sorts.py`. They were committed red in the prereg commit; do not edit them (amendments go to `spec/M2/amendments.jsonl` and are reported under Surprises).

## Predictions (frozen before the solver first runs on the Morph facts)

1. `t` is Time and `wait.dt` is Dur; W, F and D are Dur; `Ch.start` (key `Ch.s`) is Time.
2. `W + cstart − t` is SDur at **one** source site, Rollup.sol:363. Three entry points reach it through `_commitBatchWithBatchData`: `commitBatch` (:268), `commitState` (:285) and `commitBatchWithProof` (:411). The M1 facts duplicate the guard per action (`morph_rollup.json` lines 1110, 1502, 2017); deduplication by span yields one site.
3. `qpend` and `Entry.tot` get distinct sorts, `Idx[queue]_fin` and `Idx[queue]_inc`, through writer provenance.
4. `win.bvh` (key `Entry.bvh`) and `s_bvh` form the union `Dig[VH] + Dig[Agg]`.
5. 0 SORT-affine conflicts on the M1 facts.
6. The planted Time+Time fixture's minimal core has exactly 2 constraints.

Exit: byte-identical assignments across two runs; tests green.

## Rules fixed at the prereg

The contract docstring of `tests_m2/test_sorts_morph.py` fixes R1–R6:
- **R1, realization (§7.8):** a signed subtraction realized in Nat records SDur and a sign obligation at its site, and its value flows on as Dur.
- **R2, base sorts:** flow unifies base sorts only, never labels.
- **R3, writer refinement (§7.3):** "no value flow between them" means not in one strongly connected flow component, so a one-way copy keeps labels distinct.
- **R4, labels:** names come from the frozen sidecar.
- **R5, unions (§7.4):** these follow the rule given in the contract.
- **R6, coherence:** obligation-coherence conflicts are I15's.

## Rules

- **Mechanical inference only.** The facts carry hand-written sort hints: the `site` annotations on the :363 guards, guard `note`s, docs that state sorts or sites, and the ghost tag (`Entry.tag`, `s_tag`, `tag_at`, `tags_ok`), which records by hand which member of the bvh union each write has. The solver must not read any of them. `test_sorts_honesty.py` strips them, erases the ghost tag, and renames the facts' abbreviations (`t`, `W`, `F`, `D`, `qpend`, ...); the assignment must not change beyond the renaming.
- **Lexical seeds are generic.** They may read docs, constants docs, source text and library builtin names (real-code identifiers such as `block.timestamp`, `proofWindow`, `pendingQueueIndex`, `ZERO_VERSIONED_HASH`), through target-agnostic rules. They never key on a fact variable's name, a law id or a Morph identifier. `holon/sorts/*.py` holds no Morph identifiers and no quoted Morph field names, even in docstrings; the only target vocabulary is `spec/M2/lib/sort_seeds.json` (lexical seed rules and writer-label names), frozen in the prereg commit and listed in `inputs`. Do not add vocabulary elsewhere. A seed rule that turns out wrong is a Surprise, not a fix.
- **Nothing is guessed.** A weakly seeded variable stays `Nat (unrefined)` and is listed in `unresolved.json`.
- **Never fix a prediction by tuning.** A predicted sort that does not come out is a Surprise, reported with the constraints and the core that explain it. Do not special-case variables, sites or labels to hit a prediction. The writer labels are a deterministic function of the writer set, documented in `grammar.py`.
- **A type error is never fixed by changing an assignment** (§7.8). Conflicts are results: `holon sorts` exits 0 with conflicts.
- **The diagram is upstream.** `gen/M2/diagram/` does not change in I13 (carrier `sort_ref` stays null); sorts live in `gen/M2/sorts/`.
- Pure Python, standard library only; deterministic output (sorted keys, stable ids, no timestamps). No external solver.
- M0/M1 statements, records and generated files do not change; gates M0 and M1 pass.
