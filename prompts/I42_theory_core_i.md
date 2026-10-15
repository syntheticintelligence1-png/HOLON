# Session prompt — Iteration I42: Theory core I (whiskering, domain locality, spanning-tree basis sufficiency)

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, `docs/BUILD_PLAN.md` (I42), `docs/HUMAN_ANSWERS.md` (Q18–Q22), and `whitepaper.md` (§6.1–6.2) first.

## Context

In `whitepaper.md` §6.1–6.2, the spanning-tree cycle basis of size $|E| - |V| + \kappa$ generates all cycle equations of a diagram $D = (V, E)$ up to whiskering and 2-cell pasting on the valid domain:

1. **Whiskering & 2-cell pasting (§6.1):** Given a 2-cell $e : \forall a:A.\, f(a) = g(a)$, pre-whiskering with $r : X \to A$ yields $\forall x:X.\, f(r(x)) = g(r(x))$, post-whiskering with $l : B \to Y$ yields $\forall a:A.\, l(f(a)) = l(g(a))$, and horizontal/vertical pasting composes 2-cells along walks and commuting squares without record-unpacking or `match`.
2. **Domain locality (§6.1):** Equations proved on a restricted domain (represented via a domain retractor/embedding $r : X \to A$ or a guard $p : A \to \mathrm{Bool}$) lift through pre/post-whiskering and pasting on that same domain without requiring totality on $A$.
3. **Spanning-tree cycle-basis sufficiency (§6.2):** For any connected component with spanning tree $T \subseteq E$, the unique tree path between any two vertices and the $|E| - |V| + \kappa$ fundamental cycles (one per non-tree edge $e \in E \setminus T$) suffice to reduce any walk through a non-tree edge to the tree walk (`core_tree_unique_2`, `core_cycle_basis_2`).
4. **Congruence-first round-trip proofs (§6.1–6.2):** For the 2 M0 (`L_rt_go_v0`, `L_rt_go_v1`) and 32 M3 (`L_par_rt_enc_sol_BatchHeaderBytes_<Field>_v{0,1,2}`, all non-`Version` decoders) cross-language round-trip obligations (34 laws total), post-whiskering the parallel encoder law (`L_par_hdr_v{0,1}` or `L_par_cc_<go_enc>_enc_sol_v{0,1,2}_pinned`) with the decoder via `core_whisker_post` (and chaining the Go encoder round-trip law in M3) proves the law in 1–2 body lines per law (`100` def+body lines vs `136` `open_refl` def+body lines; `215` total lines vs `340` baseline total lines) with zero `match` expressions.

The preregistered expectation is in `spec/M3/lib/theory_core_i.json` and `tests_m3/_i42.py`, and registered under `"I42"` in `spec/M3/predictions.json`.

## Task

1. **`holon/gen/core.py`:**
   - Add `THEORY_CORE_I` containing the 12 polymorphic Bend 2 laws (`core_whisker_pre`, `core_whisker_post`, `core_whisker_both`, `core_walk_2`, `core_walk_3`, `core_square_paste_h`, `core_square_paste_v`, `core_domain_local_pre`, `core_domain_local_post`, `core_domain_local_paste`, `core_tree_unique_2`, `core_cycle_basis_2`) and emit them into `gen/M3/core/{LAWS,PROOF}.bend` alongside the 20 existing `CATALOG` lemmas while leaving `gen/M2/core/{LAWS,PROOF}.bend` untouched (per `AGENTS.md`: never edit `gen/M0`–`M2`).
2. **`holon/gen/basis.py` and `holon/gen/mproofs.py`:**
   - Implement spanning-tree cycle-basis sufficiency and congruence-first proof generation (`holon/gen/basis.py`, wired into `holon/gen/mproofs.py` and `holon/__main__.py`), emitting:
     - `gen/M3/basis/header/{LAWS,PROOF}.bend` (3 laws: `basis_sufficient_header_v0`, `basis_sufficient_header_v1`, `basis_sufficient_header`);
     - `gen/M3/basis/header_length/{LAWS,PROOF}.bend` (5 laws: `basis_hl_gen_blob_hashes_hash`, `basis_hl_gen_blob_versioned_hash`, `basis_hl_gen_batch_header_v1_bytes`, `basis_hl_gen_load_sol`, `basis_sufficient_header_length`);
     - `gen/M3/basis/congruence/{LAWS,PROOF}.bend` (34 congruence-derived round-trip laws: 2 M0 + 32 M3, proved via `C.core_whisker_post` without `match`);
     - `results/M3/basis.json` recording the Bend + `bend --verdict` verification of all 54 positive laws (`PROVED`), all 7 negative canaries (`REFUTED`), and the congruence vs `open_refl` line-count comparison.

## Verification

- `python3 -m holon audit prereg --milestone M3`
- `python3 -m unittest tests_m3/test_theory_core_i.py -v`
- `python3 -m unittest discover -s tests -t . -v`
- `python3 -m unittest discover -s tests_m3 -t . -v`
