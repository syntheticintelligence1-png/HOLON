# I72: E2 over the adopted holon-facts/0.3 transitions documents (I33's evidence key)

The plan is row I72 of `docs/BUILD_PLAN.md`, section 3, the evidence half of I33's split (the I33 design note: a catalog key for UNDO cancellations, this evidence key, and the contract). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (Z1-Z7) are in the docstring of `tests_m3/test_e2_transitions.py`; I14's calculus is the docstring of `tests_m2/test_evidence.py`, I20's adopted-document rule the module docstring of `holon/diagram/evidence.py`.

## Why this key, and why before I33's contract

- I33's M3 contract `C_o12_m3` will claim E2 for a law over the adopted Rollup document `spec/M2/facts/morph_rollup.extracted.json`. GEVID (I14) enforces from M2 on, with no exemption: metadata evidence that the computed levels lack fails the gate.
- I20 covered each adopted transitions document with a model of anchors only. E1-E6 are defined over facts 0.1 and 0.2 diagrams, and `holon.diagram.build` has no 0.3 adapter, so such a model has no atom, and a law over it that names an edge has levels `[]`. The probe below, a law naming challengeState and setPause, has levels `[]` today.
- So the contract cannot pass GEVID without E2 over the document. I72 computes E2 there, and only E2. Same shape as I66: new model atoms, `evidence_sha256` moves in both registries, the M1, M2 and T32 records re-stamped, the M3 records trailing until the next M3 re-make.

## What I72 does

- **Accesses (Z1).** From the document's own terms, not a diagram. A write record (`family`, `path`, `value`, at any depth: top-level writes and loop bodies) writes its family at its path. A read is a maximal map/member selection chain over a state term of the family: `["storage", f]`, or `["carried", L, s]`, `["exit", L, s]` (the family inside or after loop L), or `["store", s, P, v]` (the family after a write). A bare state term of a scalar family is a whole read. A state term in a threading position is not a read:
  - `post[f]` restates the writes;
  - the entry and value of a loop record's carried, next, at_break and exit entries named `["storage", f]` thread the family through the loop.
  Without that, every writer of a family would also "read" it (I20's anchors count those terms, which is fine for anchors and wrong for E2). A whole mapping read as a value is a construct the rule does not map: EvidenceError, nothing written.
- **Overlap (Z2).** Paths are separated only by different member names or different literal map keys. A symbolic key overlaps every key, as I14's index terms do (`overlap` in `holon/diagram/evidence.py`: "index expressions are evaluated in the states of different steps, so their syntax cannot separate them").
- **Atoms (Z3).** One E2 atom per (p, q, family) with an overlapping write and read, p == q included as in I14's E2, via `{carrier, writes, reads}` with rendered paths (`*`, `[*]`, `[0]`, `.finalizeTimestamp`), I14's id scheme. No unresolved entries: the 0.3 terms have no kindless-builtin fallback.
- **Where (Z4).** `holon.diagram.evidence.transitions_atoms(model, doc)`. The build gives the adopted model those atoms when it covers adopted documents for a target milestone (M<k>) from the committed diagrams, which is what `holon evidence --milestone M2`/`M3` and GEVID's regeneration do. A build for a test milestone, with diagrams passed in, for no milestone or with adopted off gives no atom, as I66 restricted window views. So the four in-memory and toy sets I66's key pins do not move.
- **Laws (Z5).** law_evidence does not change. No committed law over an adopted document names an edge: 2 in laws/M2 and 51 in laws/M3, all UNDO/FACT/DISCH/SORT terms. So no law's evidence, record field or GEVID row moves.
- **Regenerated (Z6), by this recipe:**
  1. `holon evidence` for M2 and M3;
  2. `holon derive` for M2 (REGISTRY's evidence_sha256) and M3 (REGISTRY and DERIVATION, their evidence hashes);
  3. `holon lossy --milestone M3` (header_length's evidence input entry);
  4. `holon metrics --milestone M3` (evidenced_pair_coverage's evidence_sha256);
  5. `holon run` M1 and M2, then the filter stage, in one commit, and `holon profile --milestone T32`: every M1, M2 and T32 record in generator_sha256 and seconds alone (`holon/diagram/evidence.py` is in the holon-ir/0.2 and 0.3 closures and I32's).
  No M3 record is re-made: they trail, as after I66, until the next M3 re-make (I28's build, or I71's).
- **Earlier tests (Z7).**
  - I66's `test_the_set_gains_the_view_model_alone` compares all non-view atoms with I66's prereg. It is narrowed to leave out the adopted models' E2 atoms. This is in the prereg commit, logged in `spec/M3/amendments.jsonl`.
  - I14's three tests assume an adopted model has no atom and every atom an endpoint in a diagram. They are narrowed in a later commit, since an M3 prereg commit may not touch `tests_m2/`, and logged in `spec/M2/amendments.jsonl`.

## What was known before this prereg (disclosed)

- **No build code ran.** A draft of `transitions_atoms` and its build hook was written in scratch before this commit, never applied to the tree or run. What ran, on the committed tree:
  - scratch probes of the rule, refined in three steps: family level 479 pairs; paths with `post` read as reads, 474; threading positions excluded, 421, the rule written here;
  - the instrument on M2's and M3's adopted documents (the Rollup document alone, 421 atoms each);
  - law_evidence and I66's instrument on the probe over the committed sets: covered, both edges named, levels `[]`;
  - law_evidence over the 53 laws over the document (none names an edge);
  - GEVID on M0-M3: all pass; M0 and M1 have two report-only mismatches each, which are pinned.
- **The instrument's count is known; that is what an instrument computes.** P1, the one counted prediction, risks holon's code (written after this commit) reading the document differently from the instrument: write records at depth, selections over carried, exit and store states, the threading positions, literal against symbolic keys, members.
- **R5's observation (recorded, not counted).** The hand abstraction `morph_rollup` (M1's facts, in gen/M2/evidence.json) has 60 E2 action pairs among the 8 actions it shares by name with the extracted document. All 60 are pairs of the extracted document's atoms. The extracted document relates exactly one pair more among those actions: finalizeBatch to setPause, on `challenges`. finalizeBatch writes `challenges` and setPause reads it. That is a data flow the hand abstraction does not model, between two actions I33's L2 (challengeState, setPause) and the O12 window care about. It is reported here as an observation, for the human and for I33's design, and it changes nothing in I72.

## Risks

- **Precision of reads.** A read counted where the action only threads state would add false E2 evidence; a missed read would hide true evidence. The threading rule is stated structurally, by the term positions of `post` and of the loop records, never by family or action name. The build review should try a planted document for each position.
- **Closure churn.** Every M1, M2 and T32 record is re-stamped. Whichever of I72 and I28's build lands second re-stamps them again. The M3 records trail until the next M3 re-make.
- **Merge order with I28.** I28's build adds a versioned document to gen/M3/evidence.json (anchors only). If it lands first, I72's build regenerates over it. I72's rule covers only `adopted_documents`, not versioned documents, and changes nothing there.

## Predictions (key I72 in `spec/M3/predictions.json`)

- **P1 (counted).** The model's E2 inventory in both sets is the instrument's: 421 atoms, 55 self-pairs, 25 families, five pinned examples, nothing else and no unresolved entry.

**Regressions:**
- **R1.** No law's evidence moves, GEVID passes as at the prereg, and the registries record their sets' evidence_sha256.
- **R2.** The own commits change only what Z6 allows.
- **R3.** Z4 holds where it should and nowhere else, and every other model and header is as at the prereg.
- **R4.** Construction checks on the instrument and the probe at the prereg.
- **R5.** The probe gets E2, with 92 relevant atoms, plus the hand-abstraction observation.
