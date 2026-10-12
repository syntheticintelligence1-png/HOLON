# I10: statement lifecycle, A3, prover separation

Rendered from `docs/BUILD_PLAN.md` §4, I10. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Q3 default: without a key, the gate rejects every weakening; re-extraction and strengthening proceed.

## What to build

- **`laws/STATEMENT_DIFF.jsonl`.** Append-only, and initially empty. Entry kinds:
  - `reextraction`: allowed unsigned only if the changed refs come from extractor output that G1 reproduces from the pinned code with the pinned extractor. Hand-written facts (`extraction.method` is a hand-written fixture or hand extraction) can never use it.
  - `binding_change`: a checked equivalence law between the old and the new def, or a signature.
  - `strengthening`: a kernel-checked S′ ⇒ S.
  - `weakening`: a gpg signature from `keys/` (Q3) and an auditor review. No key exists, so every weakening is rejected.
  - `cross_milestone`: a checked S_new ⇒ S_old, or a signed weakening. Pairs come from `DERIVATION.json` back-test links, never from ids.
- **`holon/statement_diff.py`.** `check_entry`, `check_file` and `check_cross_milestone`; the API is in the test docstrings.
- **`holon/gen/implication.py`.** It generates the obligation S′ ⇒ S as one Bend law (S's binders; S's premises and S′'s claim as premise binders; S's claim as the claim) and proves it with the existing proof classes, plus `pick`: the claim is one of the premises, or a conjunct of one.
  - S′'s premises must follow from S's: textual inclusion for now.
  - Bend checks every implication; a generated proof counts only when it checks.
- **`holon/audit/regress.py`.** `holon audit regress --from A --to B [--json]` reads history with `git show` only. It reports statement-hash changes, and per law the commits that first added its law file, its result record and its prediction entry.
  - For M1, a prediction entry is a `laws[]` item of `spec/M1/predictions.json` whose `law_id` is the law.
  - It is an audit tool, not a gate check.
- **Prover separation.** For every milestone other than M0 and M1:
  - laws are written under `<gen>/laws/<law_id>/LAWS.bend`, and proofs under `<gen>/proofs/<law_id>/PROOF.bend`;
  - `holon.gate.laws_in_proofs(gen_dir)` lists proof files that declare a law, and G3 fails on any;
  - Bend already refuses proof files that redefine model names (probe p15).
- **Tests:** `tests_m2/test_statement_diff.py`, `test_regress.py` and `test_cross_milestone.py`.

## Rules

Never weaken a claim. A signature is a human act: never create a key. The 24 frozen statements and their hashes do not change.
