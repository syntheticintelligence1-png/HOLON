# I42: theory core I

Rendered from `docs/BUILD_PLAN.md` §4 I42 (whitepaper §3.1–3.3; §6: Lemma 6.2, Thm 6.3, Thm 6.4, Cor 6.5; §10.3 steps 1–3 and its last sentence; Appendix H `core/`) and the human answer Q14b in `docs/HUMAN_ANSWERS.md` (Thm 6.4, 6.6 and 6.7 may be proved once, by hand, in Lean, and kernel-checked; 6.6 and 6.7 are I43's), with the delegated Q19 (every M3 result rests on the extracted documents). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/iterations/I24.md` and `docs/iterations/I25.md`.

The exact outputs, formats and rules are in the docstring of `tests_m3/test_theory_core.py` (rules T0–T9, gaps T-G1–T-G7). The instruments are fixed at this prereg:
- `tests_m3/_i42.py`: rules T1–T8 written out a second time, independently of `holon/`: the frozen Bend and Lean core texts, the instance graphs, trees, cycles and their derivations, coverage and certificates, and the exact text of every instance's statements and of its canary's;
- `spec/M3/lib/theory_core.json`: every predicted value, computed by `tests_m3/_i42.py::theory_doc` from the inputs it lists (files by sha256, records by status).

An independent reviewer attacked this prereg before any build; its fixes are folded into this commit (no namespace in the Lean core, so the axiom audit finds every theorem; command rules after the Lean marker; a localizing Thm 6.3; rule T7's checks of "by application"; the semantic canary; construction checks moved out of the predictions).

## Goal

Make basis sufficiency kernel-checked (§10.3: "The meta-theorems are formalized once in the core library and instantiated per target, so basis sufficiency is itself kernel-checked"):
- formalize generic graphs, walks and holonomy, with Thm 6.4, Cor 6.5, Lemma 6.2 and Thm 6.3:
  - **in Lean 4.34.0**, in their textbook form (hypotheses quantified once, used freely), checked by the pinned toolchain with no axiom beyond `propext` and `Quot.sound`;
  - **in Bend 2**, in the form an instance applies (rule T1), checked by bend and BendTT. Bend makes every function value affine, so a law cannot apply "every fundamental cycle is the identity" at every step of an arbitrary walk. Each Bend result is therefore stated over per-step bundles (`Cons`, `LInv`, `Pres`, `Onto`, `WalkOk`) that a proof consumes once per step. An instance builds its bundles from top-level lemmas, which it may call freely;
- instantiate the theory over the header **by application** (`basis_sufficient_header_length_v<k>`), from the PROVED laws I24 derived, with no unfolding of the model beyond `bridge_*` pin equations (rule T7);
- certify, by the same instances, obligations no rule states: I25's six uncovered constant reads (the Go encoders' version byte, `enc_sol`'s `SequencerSetVerifyHash`) and I24's three PAR-weak pairs on both encoders' images;
- show the instantiation is not vacuous: at an unpinned start the root cycle is refuted with a witness found on the model (the semantic canary), and dropping one cycle law makes the kernel reject the proof (the construction canary).

**Which result is checked where.** Lean states each result in its textbook form. Bend states the forms an instance applies.

| result | Lean theorem | Bend law |
|---|---|---|
| Lemma 6.2 (congruence) | `lemma_6_2` | `core_cong_sym`, `core_cong_trans`, `core_whisker_post`, `core_whisker_pre` (instances use Base's `Equal.*`) |
| Thm 6.3, into / onto | `thm_6_3_into` / `thm_6_3_onto` | `core_domain_into` / `core_domain_onto` |
| Thm 6.3, localization | `thm_6_3_local` | Lean only |
| Thm 6.4 (iii) ⇒ (i) | `thm_6_4_iii_i` | `core_fundamental_potential`, `core_bwd_cons`, `core_transport`, `core_cycle_identity` |
| Thm 6.4 (i) ⇒ (ii) | `thm_6_4_i_ii` | `core_holonomy_parallel` |
| Thm 6.4 (ii) ⇒ (iii) | `thm_6_4_ii_iii` | Lean only |
| Cor 6.5 (⇒) / (⇐) | `cor_6_5_potentials` / `cor_6_5_flat` | `core_fundamental_potential` / `core_transport`, `core_cycle_identity`, `core_parallel_agree` |
| walk algebra, non-vacuity | definitional in Lean | `core_runto_*`, `core_cons_inhabited` |

## What today's tree holds (computed at the prereg)

- **I24's PAR basis over `header_length`.**
  - 80 laws, 73 of them PROVED: 70 round trips and the 3 pinned cross-component laws.
  - The 3 full cross-component laws are REFUTED.
  - The 3 PAR-weak laws are UNKNOWN: there is no byte-string proof route (I24 gap G6).
  - The domain law is REFUTED.
- **I24's cycle basis does not meet Thm 6.4's hypothesis.**
  - It spans the whole diagram: 17 carriers, 20 edges, rank 4.
  - Its non-tree edges are lossy decoders, a second Go encoder and the loader. By I25 rule L1, the invertible fragment per version is a forest.
  - None of its 4 cycle laws is PROVED.
- **The instances.**
  - **What each instance is.** One per version v: the forward-path diagram rooted at the Go record of the PROVED pinned cross-component law at v (rules T3–T5). It holds both encoders, the decoders at v and the product structure (projections, `Some`).
  - **What it states.** Thm 6.4 (ii) for forward walks from its root, in potential form. Its maps need not be invertible, because a potential here is a value: the root path's image of one pinned start.
  - **Its available equations** are the 73 PROVED laws, each in exactly one instance. Every fundamental cycle is derivable from them, and 70 of the 73 laws are needed by a shortest derivation.

| instance | root law | \|V\| | \|E\| | rank | laws available | needed | certificates |
|---|---|---|---|---|---|---|---|
| `basis_sufficient_header_length_v0` | `L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned` | 34 | 55 | 22 | 23 | 22 | 4 |
| `basis_sufficient_header_length_v1` | `L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned` | 37 | 60 | 24 | 25 | 24 | 4 |
| `basis_sufficient_header_length_v2` | `L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned` | 37 | 60 | 24 | 25 | 24 | 4 |

The three laws available but not needed are `enc_sol`'s round trips of `BlobVersionedHash` at v0 and v1 and of `BlobHashesHash` at v2. Each goes through the second of two decoders that read one slot (a PAR-weak pair's), and the shortest derivations reach those cycles through other equations.

## Deliverables (summary; the contract has the details)

- **`holon/gen/theory.py`**: the core, as fixed text (gap T-G7; generic, no target named). It writes:
  - `gen/M3/theory/core/{LAWS,PROOF}.bend` (19 laws);
  - `gen/M3/theory/lean/Theory.lean` (9 theorems).
- **`holon/gen/basis.py`** and **`python -m holon basis --milestone M3 [--kernels] [--check]`**, rules T3–T9. It writes:
  - `gen/M3/theory/basis/header_length.json`;
  - `gen/M3/theory/basis/header_length_v<k>/{LAWS,PROOF}.bend`;
  - `gen/M3/theory/basis/header_length_v<k>/canary/{LAWS,PROOF}.bend`, the canary's witness found by evaluating the model with bend;
  - with `--kernels`, `gen/M3/theory/report.json`.
- **`holon/gen/congruence.py`**: the congruence proof class, Lemma 6.2 at work.
  - It builds chains of `Equal.trans` and `Equal.sym` over the available equations, each lifted with `Equal.cong`.
  - It goes through bridge lemmas that equate two pins of one record, or a pinned field to its constant.
  - **Placement, a stated deviation** (gap T-G5): `holon/gen/mproofs.py` is a root of the holon-ir/0.2 and 0.3 generator closures, so a congruence class there would change `generator_sha256` in every M1, M2 and M3 record.
- **`docs/iterations/I42.md`**, with the prediction table.

## Predictions (key I42 of `spec/M3/predictions.json`)

| id | claim |
|---|---|
| P1 | The Bend core (19 frozen laws) is PROVED: bend and bend `--verdict` accept `core/PROOF.bend`, each within 120 s. |
| P2 | The Lean core (9 frozen theorems, Thm 6.3's localization among them) checks under the pinned Lean 4.34.0: result `checked`, every theorem audited by its bare name, axioms within {`propext`, `Quot.sound`}, within 120 s. After the marker, only theorems, defs and examples are added (rule T2). |
| P3 | The header instantiation is PROVED by application. For each instance, `basis_sufficient_header_length_v<k>` and its 4 certificates are accepted by bend and bend `--verdict`, each file within 120 s, and the proof obeys rule T7. P3 is decided by the kernels, not by the report. |
| P4 | The semantic canary: each instance's counter-law `canary_unpinned_header_length_v<k>` is accepted by bend and bend `--verdict` within 120 s. It says that at an unpinned start, the root cycle's walks differ, with a witness found on the model. So the instance law needs its pins. |

**Regressions and construction checks (not counted).**
- **R1:** no law is added and no record changes. Commits that write `gen/M3/theory/` or the three generator modules touch nothing under `laws/`, `results/`, `facts/`, `spec/M1/`, `spec/M2/`, `replay/`, `gen/M0`–`M2`, or `gen/M3` outside `gen/M3/theory/`.
- **R2:** the sidecar is the instrument's computation. The statements are well-typed:
  - the core has 19 open laws;
  - each instance has 25;
  - each canary has 2;
  - Lean elaborates the placeholders with 9 warnings and no error, and its axiom audit prints all 9 theorems.
- **R3:** the CLI is deterministic and equals the committed files. It leaves foreign files alone, `--check` passes, and a stale law file is refused (exit 2, `holon basis: refused:`).
- **R4:** an UNKNOWN round trip leaves its cycle uncovered and no files. An UNKNOWN root law removes its instance. The code is generic.
- **R5:** the partial M3 gate passes on G3, G5, G9 and GEVID. G2 (solc not installed here) and G11 (I30's missing record) already fail at the prereg, and are stated.
- **R6:** the basis document equals the instrument (the table above).
- **R7:** the construction canary. `edge_2`'s fact proved by `{==}` instead of its derivation is rejected at `edge_2` by an expected/observed mismatch.
- **R8:** the six constant-read certificates are exactly I25's six uncovered constant reads. The six weak-image certificates are the pairs of I24's three PAR-weak laws, on both encoders' images.
- **R9:** `report.json` binds every kernel result to the committed files. Each instance is labelled `kernel_checked` and each canary `refuted`.

## Outcome paths, narrowly

`gen/M3/theory/`. `docs/iterations/I42.md` is written in the report commit, as usual.

I42 writes nothing under `laws/`, `results/`, `gen/M0`–`M2`, or anywhere in `gen/M3/` outside `gen/M3/theory/`.

## Rules

- **AGENTS.md is binding.** The statements are frozen in the sidecar. The build writes only proofs, generators and documents.
  - A statement that turns out false or unprovable is a MISS, reported with the kernel's output; it is never edited.
  - Neither canary is ever "fixed". A canary without a witness on the model is a result.
- **Hand proofs (gap T-G7).** BUILD_PLAN I42 names Lemma 6.2, Thm 6.3, Thm 6.4 and Cor 6.5 as the hand-proved meta-theorems that wait for Q14b. Q14b names Thm 6.4, in Lean.
  - I42 reads the plan with that answer. The proofs of the four results, in Lean and in the Bend core's per-step form, are hand-written once and generically, and emitted as fixed text by `holon/gen/theory.py`.
  - Instance proofs come from generators: `holon/gen/basis.py` and `holon/gen/congruence.py`.
  - The reading is Question 1 below.
- **Witnesses come from the model** (AGENTS rule 5): `holon.gen.basis` finds the canary's witness by evaluating the model's two walks with bend on candidate records, in a fixed order.
- **No special-casing.** `holon/gen/{basis,theory,congruence}.py` name no target or fixture identifier, no law id and no source file, and import no instrument.
- **Budgets** are `config/holon.json`'s `bend.budget_s_per_file` and `lean.budget_s_per_file`: 120 s each, per file and per kernel, wall clock on an otherwise idle machine.

## Questions for the human (raised by the prereg)

1. **Hand proofs beyond Q14b's wording.** I42 hand-writes, once and generically:
   - the Lean proofs of Lemma 6.2, Thm 6.3 and Cor 6.5, besides Thm 6.4;
   - the Bend core's proofs (the per-step forms).

   It reads this from BUILD_PLAN I42 ("waits for Q14b, since these are hand-proved meta-theorems"). Is that reading acceptable? If not, I43 can replace the fixed text with per-class proof generators.
2. **The affine form of the Bend core.** The Bend laws take one hypothesis per step of a walk, because a Bend function value is used at most once. The Lean theorems state the textbook form. Is this pair acceptable as "Thm 6.4 kernel-checked"? The alternative is a Bend form with a single quantified hypothesis, pursued upstream. That would need Bend to allow a reusable (Data-kinded) proof of a Pi type.
3. **Coverage by implication (I25 Question 3).** The six constant reads are now certified, but only on the pinned region (gap T-G2): narrower than I25's obligations, which a direct law per read would cover for every record. Should I25's evidenced-pair coverage count an element covered by such a certificate, with the region stated? The metric is not changed here.
4. **Certificates on the pinned region (gap T-G2).** A certificate holds on the image of the root law's pins. Whether that image is every record of the version is argued in the report, not kernel-checked. Should I43 add the section map (Sol to Go), which would state the certificates for every record?
