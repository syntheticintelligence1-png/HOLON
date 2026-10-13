# I24: the rules engine and PAR, all sub-forms, on the extracted documents

Rendered from `docs/BUILD_PLAN.md` §4 I24 (whitepaper §5.1, §3.2, Thm 6.4 use, §10.3 steps 1–3, §8.4 PAR rows, Def 4.1–4.5, §10.1 Linking, §10.2, App. E PAR row, §11.3 sub-forms) and the delegated Q19 answer in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/iterations/I20.md`.

The exact outputs, formats and rules are in the docstring of `tests_m3/test_derive_par.py`:
- P0–P12, PAR over any diagram;
- X0–X9, the linked codec layer;
- B1–B5, the back-test across documents;
- G1–G7, the gaps preregistered (added at review: G6, byte-string laws have no proof route; G7, basis sufficiency under Thm 6.4 is not claimed).

`tests_m3/test_par_outcomes.py` reads the same contract. This is the first M3 iteration: it creates `laws/M3/`.

## Why this is a redraft

A reviewed draft of this key derived every M3 law from the hand-written documents (`facts/morph_header.json` and `spec/M1/facts/*.json`). That breaks BUILD_PLAN §2 invariant 3 and the Q19 answer: extracted facts are the input of every M3 law, and no waiver applies where an extracted document exists.

**What carries over unchanged:**
- rules P0–P12;
- the ten `par_<subform>.facts.json` fixtures;
- `tests_m3/_i24.py` and `tests_m3/_m3.py`.

**What is recomputed** over the documents `spec/M3/lib/derive_extracted.json` adopts: the Morph predictions and `spec/M3/lib/par_basis.json`. The adopted documents are the I17 Solidity header document, the I18 Go batch document and the I19 transitions document.

**What I24 now builds.** The extracted side had no diagram and no E1–E6 atoms for codec documents (I20, Not done), so I24 builds them as a generic layer.

## Goal

Make `holon derive` a rules engine with catalog versions, and add PAR: `holon/rules/par.py` generates every PAR sub-form wherever a diagram has the structure.

Build the linked codec layer:
- the link roles of I19 join a Solidity loader and a Go tagged predicate into one component;
- each component gets a diagram, E1/E2/E6 atoms and a Bend model.

Derive the first M3 laws over that component, and decide them. Then back-test against M0 across documents. Every M0 law gets one of two outcomes:
- a paired M3 law (alpha-equivalence modulo the frozen name map) whose implication is accepted, through Bend-checked bridges or a transferred witness;
- or an open gap.

A missed M0 law is a rule gap. It is never added by hand.

## Deliverables (summary; the contract has the details)

- **Rules registry** (`holon/rules/__init__.py`): `CATALOGS` by version.
  - M2 keeps `holon-rules/1.0` (SORT/site, with a byte-identical derivation).
  - M3 is `holon-rules/1.1`: PAR's ten sub-forms.
  - `--catalog` exists for test milestones.
  - SORT enters M3 with I30, not here.
- **`holon/rules/par.py`**: one producer per sub-form, in the dedupe order of P11, over facts 0.1/0.2 diagrams and component diagrams.
- **The linked codec layer** (`holon/diagram/linked.py`, `holon/gen/linked.py`):
  - `python -m holon codecs` writes `gen/M3/codec/header_length.json`, the one Morph component;
  - `holon diagram` and `holon evidence` for M3 write `gen/M3/diagram/header_length.json` and `gen/M3/evidence.json`;
  - `holon run` decides component laws on `gen/M3/model/header_length.bend`;
  - M2's diagram and evidence stay byte-identical.
- **IR 0.3, additively**:
  - the codec terms (`call`, `field`, `bytes`, `some`, `bool`) over facts 0.1 and linked documents;
  - the `expr` term over facts 0.2;
  - schema, statement-hash refs, emitters, proof classes and refutation, as the contract says.
- **`laws/M3/`** (`holon derive --milestone M3`), **`results/M3/`** (`holon run --milestone M3`) and **`spec/bindings/M3.json`** (`holon bind --milestone M3`).
- **Back-test.** `python -m holon backtest --milestone M3` reads the frozen name map `spec/M3/lib/backtest_map.json`. It writes:
  - `results/M3/backtest.json`;
  - the bridge and witness files under `gen/M3/backtest/`.
- **A planted linked fixture** (`tests_m3/fixtures/par_linked/`, already committed): a Solidity layout document and a Go codec document with their own adoption and link sidecars.
- **Partial M3 gate:** `holon gate --milestone M3 --checks G2,G3,G5,G9,G11,GEVID` passes. These are not in I24: G1, G6 replay of the new witnesses, G7, and G4 canaries over PAR laws.
- **`docs/iterations/I24.md`**, with a prediction table and the back-test table.

The build may be split in two halves:
- **A:** registry, `par.py`, IR, and the ten facts fixtures (contract P0–P12, unchanged from the reviewed draft);
- **B:** the linked codec layer, the Morph derivation and run, and the back-test.

## Predictions (key I24 of `spec/M3/predictions.json`)

| id | claim |
|---|---|
| P1 | The cycle basis of `gen/M3/diagram/header_length.json` has \|E\|−\|V\|+κ = 20−17+1 = 4 elements. Its non-tree edges are the getters BlobHashesHash and BlobVersionedHash, `BatchHeaderV1_Bytes` and `load_sol`. None adds a law: the two getters' cycles give three duplicates of the PAR-weak laws (one per common version, rule X8c), then one no_common_version and one not_a_parallel_pair. |
| P2 | Exactly 80 PAR laws over `gen/M3/codec/header_length.json`: 70 round trip, 6 cross-component, 3 PAR-weak (BlobCommitHash with BlobHashesHash at version 2, with BlobVersionedHash at versions 0 and 1, each under the tag premise `BatchHeaderBytes_Version(b) = Some(v)`) and 1 domain coherence. No branch, totality, cycle or machine law. The only reasons recorded are: totality explicit_option ×15, weak no_common_version ×2, cycle no_common_version ×1 and not_a_parallel_pair ×1. |
| P3 | The ten facts fixtures decide as designed (the reviewed draft's table). The linked fixture's 28 laws also decide as designed: 2 round trips, 5 of the 6 cross-component laws, the weak law `L_par_weak_HdrBytes_Root_HdrBytes_RootNew_v2` (inside its common version 2: Root decodes length 9, RootNew length 11; an intent question) and the domain law are REFUTED; the rest are PROVED. |
| P4 | All 70 round trips are PROVED. The 3 unpinned cross-component laws are REFUTED by a nonzero Go SequencerSetVerifyHash, with a Solidity witness that `enc_sol` stores. The 3 pinned ones are PROVED, the version-2 law of the Go patch among them. That last result reverses M0's L_par_hdr_v2 (O2) at the codec level. |
| P5 | The domain law is REFUTED by a version-0 byte string longer than 249 (O1). The three PAR-weak laws are UNKNOWN (no probe refutes them; a byte-string law has no proof route, G6): at their common version both getters accept the same lengths and read the same bytes 57..88. Their records carry a bound and no witness. |
| P6 | The back-test pairs 4 of the 8 M0 laws and accepts all 4: L_par_hdr_v0, L_par_hdr_v1 and L_par_hdr_ssvh by bridges, L_dom_hdr by witness. L_par_hdr_v2 and L_rt_go_v0/v1/v2 are open rule gaps. `exit_blockers` holds exactly those 4. |
| P7 | Statuses 73 PROVED, 4 REFUTED, 3 UNKNOWN. Evidence levels: round trips [E1, E2], cross-component [E1], PAR-weak [E6], domain []. Triage: none 76, finding 4; no Morph intent question. |

**Regressions.**
- Gates M0, M1 and M2 pass.
- `derive --milestone M2` is byte-identical.
- The matched M0 outcomes are identical (4 rows).
- M2's diagram and evidence regenerate byte-identically.

**Construction checks.**
- The registry, derivation and linked layer follow the contract exactly.
- No hand document is read for M3.
- The fixtures derive as designed.
- There is no special-casing.
- Records are valid and non-vacuous.
- Refs follow the functions named.
- The bridge and witness files check.
- The partial gate passes.

## Outcome paths, narrowly

`laws/M3/L_par_`, `results/M3/L_par_`, `gen/M3/laws/L_par_`, `gen/M3/proofs/L_par_`, `gen/M3/L_par_`, `gen/M3/codec/`, `gen/M3/model/header_length`, `gen/M3/backtest/` and `results/M3/backtest.json`.

Several M3 keys build in parallel (I24, I30 and I41), and `holon audit prereg` fails any outcome commit made on a branch parallel to the prereg commit. So I24's outcome paths name only files I24 alone writes. The files other M3 keys also write are deliberately left out:
- `laws/M3/REGISTRY.json` and `laws/M3/DERIVATION.json`;
- `gen/M3/diagram/` and `gen/M3/evidence.json`;
- `gen/M3/core/`, if `holon run` writes the core library there as it does for M2;
- the run- and gate-wide files under `results/M3/` (`summary.json`, `deps.json`, `metrics.json`, `metrics_timing.json`, `gate_report.json`, `gate_timing.json`);
- `spec/bindings/M3.json`;
- `docs/iterations/I24.md` (the report; no other key writes it, but reports are not outcome paths in any earlier key).

Commit them as usual. The audit does not attribute them to I24, so their order is not checked for I24.

## Rules

- **AGENTS.md is binding.**
  - Never edit `facts/`, `spec/M1/facts/`, `spec/M2/facts/`, `laws/M0/`, `laws/M1/` or `laws/M2/`.
  - Derive never copies an earlier law.
  - Nothing is hand-linked: no carrier, field or function is identified across languages except by rules X1 and X7.
- **Q19.** No hand document is an M3 input. The back-test alone reads `facts/morph_header.json`, and only through the frozen map.
- **No special-casing.** `holon/rules/par.py`, `holon/diagram/linked.py` and `holon/gen/linked.py` name no Morph or fixture identifier and no law id. The fixtures are test instruments, never M3 documents.
- **No tuning, no skips.**
  - A missed prediction is a Surprise, reported with its evidence.
  - An M0 law that no rule derives stays an open rule gap.
  - Rule admission is I45's job, and M3 exit cannot be claimed while a gap is open.
- **Lead decisions applied at the prereg.**
  - SORT enters M3 with I30.
  - O7 needs header/rollup diagrams linked by HASH edges. The transitions document has no M3 diagram (G1), so O7 is filed as a rule gap and never hand-linked (G3).
  - PAR-weak instantiates at common versions only (whitepaper Def 4.5, rule P4). It is not widened, and the L_par_hdr_v2 gap stays open.
  - The same holds over byte strings (rule X8c, added at review): a PAR-weak, branch or cycle law over the linked carrier gets one law per common version, scoped by the tag premise `T(b) = Some(v)` (T the component's unversioned tag-byte decoder). Without such a decoder there is no law (reason no_version_premise), never an unscoped one. Domain coherence stays unversioned (whitepaper §5.1: equal domains on R^ext).

## Questions for the human (raised by the prereg)

1. **Cross-document acceptance.** Do bridges and witness transfer (rule B4) count as the plan's "checked implication" across documents? The existing implication generator works within one facts file only. Across documents, a Bend implication needs the hand and extracted functions shown equal (bridges). For two REFUTED laws, the shared counter-witness is the natural check.
2. **Cross-language field identification.** Rule X7 identifies fields across languages only through a common decoder getter (E1 by position). That cannot detect two same-width fields that both encoders swap consistently with the getters. Should a name-level link role (I19's sidecar) be required as well?
3. **Encoder domains.** Rule X5 compares encoder layouts and leaves their domains unmodelled: the Solidity zero-state-root reverts and the Go cache path. Should a later PAR sub-form compare encoder domains across languages, or is the cache path OWN's only (I35)?
4. **Getter-level round trips.** Seventy getter-level round trips replace M0's three whole-header round trips, which rest on the hand-assembled `dec_go` and `view`. Is the rule gap on L_rt_go_v0/v1/v2 (G5) the right record, or should a rule assemble a decoder family (I45)?
5. **Byte-string version scope (rule X8c, added at review).** An unscoped PAR-weak law over the header byte string compared BlobCommitHash with BlobHashesHash at versions 0 and 1, where BlobHashesHash's label (2) does not reach, and was predicted REFUTED as an intent question. That is the widening the lead ruled out for PAR-weak, so the review scoped such laws by a tag premise (P5 now predicts UNKNOWN). If the human reads whitepaper §5.1 ("⟦p⟧ = ⟦q⟧ on R, including definedness") as licensing the unscoped comparison, X8c should be reverted together with P0's no_common_version for byte carriers, and the M0 L_par_hdr_v2 gap revisited under the same reading.
6. **Byte-string proofs.** Should a later iteration build §8.4's proof route for byte-string laws (case split on length and version, G6), so that the three UNKNOWN PAR-weak laws can be PROVED?
