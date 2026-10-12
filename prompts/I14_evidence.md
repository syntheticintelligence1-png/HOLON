# I14: evidence calculus (E1–E6) and frozen evidence set

Rendered from `docs/BUILD_PLAN.md` §4, I14 (whitepaper Def 4.5, §5.1, §10.2 getter recovery, Prop 6.11 and L3; closes V7). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact CLI, file format, APIs, the six level definitions, the law-anchoring rules L1–L4, GEVID and the record fields are in the docstring of `tests_m2/test_evidence.py`; `tests_m2/test_evidence_fixture.py`, `tests_m2/test_evidence_gate.py` and `tests_m2/test_evidence_honesty.py` read the same contract. `tests_m2/_evidence.py`, `tests_m2/fixtures/evidence/` and `spec/M2/lib/evidence_lexical.json` are instruments fixed at the prereg. Do not edit them; if one is wrong, it is a Question and an amendment.

## Goal

Compute evidence levels from the diagram 𝔇 (I11) and the frozen sort assignment (I13), and freeze the evidence set (L3: lossy obligations are enumerated from evidence, and completeness is relative to the evidenced set). Check the laws' hand-typed metadata `evidence` against it (gate check GEVID: report-only for M0/M1, enforcing from M2). Derive `evidence_triage` in the v2 records without touching the frozen v1 `triage`.

## What to build

- **`holon/layout.py`: `recovers(layout, getter)` and `evidence(facts, encoder, decoder, version)`** (rule E1, §10.2: a getter recovers a field iff the field's positions map to it in order). `layout()` and `diff()` do not change.
- **`holon/diagram/evidence.py`** (module `holon.diagram.evidence`; `holon/evidence.py` is I4's replay-side module and is not touched):
  - `build(fact_paths, root, diagrams=None, assignment=None, milestone=None)`, `render(doc)`, `law_evidence(law, doc)`, `evidence_triage(status, max_level)`, `gevid(milestone, root)`, `main(argv)`, and the constants `EVIDENCE_VERSION`, `LEVELS`, `STRENGTH`.
  - The six levels, exactly as the contract defines them: E1 layout inversion (inverse and common-decoder atoms, per version); E2 write-then-read over the diagram's access sets, with **imprecise** `*` terms (a sequence passed to a library builtin that declares no access kind, the diagram's ACCESS debt; audit finding F-M2-30) kept out of the evidence and listed as `unresolved`; E3 equality guards between two path terms; E4 recomputation of a stored call over action inputs only; E5 identical refined sorts at the operands of a comparison or `+`/`-` node, refined meaning not `Nat (unrefined)`, `Bool`, `Mach(w)` or a union; E6 lexical, from the frozen sidecar only.
  - Reuse I11 and I13 code: `holon.diagram.access` for access sets (instrument it to learn which `*` terms come only from the kindless-builtin fallback; the diagram it writes must not change), `holon.sorts.grammar.affine` for operand sorts, `holon.gen.targetlib` for library kinds and types, `holon.diagram.fact_documents` for the milestone's documents.
- **`python -m holon evidence [--milestone M2] [--root DIR] [--out PATH]`**: add one docstring line and one early-dispatch block to `holon/__main__.py`, after the `native` block (`if argv[:1] == ["evidence"]: from .diagram import evidence; return evidence.main(argv[1:])`). Commit `gen/M2/evidence.json`.
- **`spec/schemas/evidence.schema.json`**: the document of the contract, one schema per `via` shape, levels E1..E6; it must reject a bare header and an unknown level.
- **Gate check GEVID** in `holon/gate.py`: `CHECK_ORDER` gets `"GEVID"` right after `"GREF"`; a `gevid` step that stores `holon.diagram.evidence.gevid(self.m, self.root)` as the check entry (its keys `passed` and `detail` satisfy the frozen gate-report schema; the other keys are the report); one docstring line. Report-only for M0 and M1, enforcing from M2. It reads no git and runs no tool; it checks that the committed `gen/M2/evidence.json` regenerates byte for byte from its inputs (so the frozen set cannot drift silently; audit finding F-M2-25 for this file).
- **Records** (`holon/records.py`, `v2_fields`): `evidence_levels`, `evidence_triage`, `evidence_override`, computed from `gen/M2/evidence.json` and `config/evidence_overrides.json`. Records whose facts the set does not cover (planted mutation runs, toy targets) get `null` levels and the computed triage, and nothing fails (the frozen `tests/test_31` and the I6 toy run still pass). Add the three fields to `spec/schemas/result_record_v2.schema.json` as required. Regenerate the M0 and M1 records (`holon run --milestone M0`, `--milestone M1`); `gen/M0` and `gen/M1` stay byte-identical.
- **One amendment follows**, logged in `spec/M2/amendments.jsonl` (precedent: the I9 and I16 lines) and reported under Surprises: the I6 records pin (`tests_m2/test_target_agnostic.py::norm_record`, `RECORDS_PIN`) sees the three new fields; narrow `norm_record` to drop `evidence_levels`, `evidence_triage` and `evidence_override`, and keep the pin.
- **Anchors for I15's site laws.** `anchors.sites` maps every site of the frozen assignment to the TRANS edges of the actions its occurrences name, and L2 maps I15's IR 0.3 term `{"site": ID, ...}` to `anchors.sites[ID]`. This is how the first generated M2 laws get computed evidence (E5 included) from the frozen set; the set never reads `laws/` (no cycle with the registry).
- `docs/iterations/I14.md`: Done, Surprises, Questions, Not done; the GEVID reports for M0 and M1; the divergence list; the unresolved pairs.

## Predictions (frozen before the pass first runs on the Morph diagrams)

1. E1 on all v0/v1 fields of (enc_sol, dec_go) and (enc_go_v1, dec_go), per version, except exactly `sequencerSetVerifyHash` for enc_sol and `version` for the Go encoders (I14-P1); exactly 7 E1 atoms, two of them common-decoder atoms, none relating enc_sol and enc_go_v1 at version 2 (P2).
2. E2 on the BVH residue `s_bvh`, written via revertBatch and read via each commit (P3).
3. E3 at the four previous-state-root guards (P4); 9 E3 atoms in all (P5); 2 E4 atoms, both for `blob_hash` (P6).
4. E5 at the :363 guard and the :360-364 let of each commit, not at `tags_ok` (P7); 3 E6 atoms between the header encoders (P8).
5. GEVID's verdict on the E5 claims: computed for `L_sort_remaining`, missing for `L_tag_BVH` (P9).
6. GEVID report shape: M0 mismatches exactly `L_dom_hdr` [E2] and `L_par_hdr_v2` [E1], with the computed levels of every M0 law (P10); M1 mismatches exactly `L_nat_eta2` [E2] and `L_tag_BVH` [E2, E5] (P11).
7. `L_par_hdr_ssvh`'s `evidence_triage` is `finding` against its v1 `intent_question`, listed as a divergence (P12); the divergences are exactly `L_par_hdr_ssvh` and `L_par_hdr_v2` (P13).

Exit: GEVID report generated for M0 and M1; tests green; gates M0 and M1 pass.

## Rules

- **Never tune to a prediction.** The level definitions, the anchoring rules, the refined-sort and precision rules and the lexical sidecar are fixed. A predicted atom, verdict or divergence that does not come out is a Surprise, reported with the atoms that explain it. Do not special-case edges, laws, carriers, fields or versions.
- **Laws are never edited to agree with GEVID.** A mismatch is a finding about the metadata. Do not touch `laws/M0` (frozen) or `laws/M1`.
- **No override in I14.** `config/evidence_overrides.json` stays absent (or holds no entry): an override is a human's recorded judgment with a reason, never an agent's way to remove a divergence.
- **The frozen v1 `triage` never changes.** Evidence-derived values live only in the v2 fields.
- **Generic code.** `holon/diagram/evidence.py` holds no Morph identifier and no quoted Morph name, short names included (`"win"`, `"lfi"`, ...), even in docstrings; its only target vocabulary is `spec/M2/lib/evidence_lexical.json`. It reads comments, docs, notes and site annotations nowhere: `tests_m2/test_evidence_honesty.py` strips them, and renames the facts' own identifiers, in a copy and requires the same evidence (I13's honesty mutations).
- **Inputs are upstream.** `gen/M2/diagram/` and `gen/M2/sorts/` do not change in I14; the evidence pass reads them and never writes them.
- Pure Python, standard library only; deterministic output (sorted keys, stable ids, no timestamps). Unresolved pairs are results, not errors.

## Parallel build with I15 (separate worktrees; the lead merges)

- **I14 owns** `holon/diagram/evidence.py`, the `recovers`/`evidence` additions to `holon/layout.py`, the evidence fields in `holon/records.py`, GEVID in `holon/gate.py`, the `evidence` subcommand in `holon/__main__.py`, `spec/schemas/evidence.schema.json`, the evidence fields of `spec/schemas/result_record_v2.schema.json`, `gen/M2/evidence.json`, `results/M0/` and `results/M1/`, and the `norm_record` amendment.
- **I15 owns** `laws/M2/` (including `REGISTRY.json` and `DERIVATION.json`), `holon/rules/`, the I15 parts of `holon/sorts/`, `gen/M2/sorts/obstructions.json`, `results/M2/` law records, and the `derive` subcommand. I14 writes none of them.
- **Contract between the two.** `holon derive` writes `"evidence_sha256"` into `laws/M2/REGISTRY.json`, copied from `gen/M2/evidence.json` when that file exists. Rule generators never hand-assign `evidence` to generated laws: they write `"evidence": []` (or omit it), so GEVID, enforcing from M2, passes on them; evidence for M2 laws comes from the evidence set through their records.
- **At the merge**, the lead runs, in order: `holon evidence --milestone M2` (inputs may have changed, e.g. new fact documents or a re-rendered assignment), `holon derive` (the registry picks up `evidence_sha256`), `holon run --milestone M2` (M2 records gain the evidence fields), then the gates M0, M1 and M2. `tests_m2/test_evidence_gate.py::TestRegistry` checks the registry hash and GEVID on M2 whenever `laws/M2/REGISTRY.json` exists.
- Shared files (`holon/gate.py`, `holon/__main__.py`, `holon/records.py`, `spec/schemas/result_record_v2.schema.json`, `tests_m2/test_target_agnostic.py`, `spec/M2/amendments.jsonl`) get textual conflicts only; keep each change in its own hunk.
- **Never commit the other iteration's outcome paths.** Do not commit anything under `laws/M2/`, `results/M2/` or `replay/M2/`; when you run a gate for another milestone, pass `--report` to a scratch path. `gen/M2/evidence.json` and `results/M0/`, `results/M1/` are yours.

## Before committing

Run every suite, `holon gate` for M0 and M1, `tools/freeze.py check` and `holon audit prereg --milestone M2`.
