# I25: PAR-lossy and injective pushing over the frozen evidence set

Rendered from `docs/BUILD_PLAN.md` §4 I25 (whitepaper §10.3 step 6, Prop 6.11, Lemma 6.12, §12 L3; and what they rest on: Def 4.4 and 4.5, Cor 6.16, §10.2, Thm 6.4's invertible-fragment hypothesis, L21) and the delegated Q19 answer in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/iterations/I24.md`.

The exact outputs, formats and rules are in the docstring of `tests_m3/test_par_lossy.py` (rules L0–L9, gaps L-G1–L-G6). The instruments are fixed at this prereg:
- `tests_m3/_i25.py`: rules L1–L9 written out a second time, on top of I24's instruments `tests_m3/_i24x.py` and `_i24.py`;
- `tests_m3/fixtures/par_lossy/`: a variant of I24's linked fixture whose version-1 pair becomes injective (one Go constant changed);
- `spec/M3/lib/par_lossy.json`: every predicted value, the core statements and D7, computed by `tests_m3/_i25.py::par_lossy_doc`.

## Goal

Realize the lossy half of basis reduction (§10.3 step 6) on the M3 evidence set I24 froze:
- classify the invertible and lossy fragments (Def 4.4). I11 left this to I25: the layout algebra decides it for codecs, and CF premises decide it for HASH edges;
- enumerate the evidenced lossy elements of `gen/M3/evidence.json`;
- decide by Lemma 6.12 which of I24's cross-component laws is the pushed basis law of its pair, and which claims more than any observation relates (Prop 6.11). A family decoder that rejects the images (wrong length for the version's tag) is blind: it observes nothing, so its read range does not count;
- certify each such over-claim in Bend, at a concrete collision;
- state Lemma 6.12 as a core law under a pointwise CF premise;
- report evidenced-pair coverage, relative to the evidence set (L3);
- open an evidence review for every uncovered replay disagreement.

## What today's evidence set holds (computed at the prereg)

- **The set.** `gen/M3/evidence.json` holds 161 atoms over the one linked codec component `header_length`: E1 102 (70 inverse, 32 common_decoder), E2 55 and E6 4. The transitions document has an anchors-only model (I24 gap G1).
- **Every evidenced pair is lossy.** Every lossy edge is either a single-read getter (a projection of the header bytes) or `enc_sol` at version 0, which drops `lastBlockNumber`.
- **The round trips** (70) and **the three observed pairs** are covered by I24's laws. Each observed pair is a group of common-decoder atoms with its full and pinned cross-component laws.
  - **The pinned laws are pushed.** The decoders of each group read every byte position the two encoders can write differently, once the Go `SequencerSetVerifyHash` is pinned to the Solidity constant 0.
  - **The full laws are not pushed.** Position 185 is unread (unobserved field `SequencerSetVerifyHash`), so these laws claim what no observation relates. That is exactly why I24 found them REFUTED.
- **Six evidenced reads recover no field.** These are constant reads: `BatchHeaderBytes_Version` on the three Go encoders, and `BatchHeaderBytes_SequencerSetVerifyHash` on `enc_sol` at versions 0, 1 and 2.
  - No rule states them, so they are uncovered.
  - **Coverage: 73 of 79.**
- **One HASH candidate exists, unevidenced:** `enc_sol` and `load_sol` both feed `HASH.keccak256` (Rollup.sol:357, :849). The comparison that would evidence it is a guard of the transitions document, which has no M3 diagram.
- **D7 is outside today's extraction.** Its sites are `Verify.sol:9`, `:14-15` and `L1CrossDomainMessenger.sol:138`, `:155`, and no adopted M3 document contains either file. Its instance belongs to I36.
- **The review is empty:** the 15 refinement records of I16, I20 and I23 list no disagreement.

## Deliverables (summary; the contract has the details)

- **`holon/rules/par_lossy.py`** and **`python -m holon lossy --milestone M`**. It writes:
  - `gen/M3/par_lossy/header_length.json`: the fragment, elements, push verdicts, HASH candidates, collisions and coverage;
  - `gen/M3/par_lossy/core/{LAWS,PROOF}.bend`;
  - `gen/M3/par_lossy/collisions/<law_id>/{LAWS,PROOF}.bend`, three of them (all of kind cross);
  - `spec/M3/evidence_review.jsonl`, which is empty.

  The command also takes test milestones (`--codec`, `--gen-dir`, `--out`, `--review`, `--records`).
- **The core laws `core_inj_push`, `core_inj_pull` and `core_cf_succ`.** Their statements are frozen in the sidecar. Their proofs come from a proof generator, and both kernels must check them.
  - **Placement, a stated deviation:** they live in `gen/M3/par_lossy/core/`, not in `holon.gen.core`'s catalog (`gen/<M>/core/`, I8). That catalog holds Nat/Bool lemmas with their own proof classes and is emitted for every M2+ milestone; adding a type-polymorphic law there would rewrite `gen/M2/core` and `gen/M3/core`. I36's D7 instance imports `gen/M3/par_lossy/core/PROOF.bend`.
- **`python -m holon metrics --milestone M3`** writes `evidenced_pair_coverage` into `results/M3/metrics.json`.
- **`docs/iterations/I25.md`**, with the prediction table.

## Predictions (key I25 of `spec/M3/predictions.json`)

| id | claim |
|---|---|
| P1 | Fragment: 22 entries. `enc_sol`@0 is lossy (it drops `lastBlockNumber`). `enc_sol`@1 and @2, `BatchHeaderV0_Bytes`@0, `BatchHeaderV1_Bytes`@1 and the patch @2 are invertible. The 14 getters are lossy, `load_sol` is unmodelled and `HASH.keccak256` is cf. |
| P2 | 79 elements: 70 round_trip, 3 observed (10, 11 and 11 common-decoder atoms) and 6 constant_read, with no partial_read. 3 E2 atoms are excluded for having no common version. E6: 4 atoms, 2 of them with a law. |
| P3 | No family decoder is blind. Of the cross-component laws, the 3 pinned ones are pushed. The 3 full ones are not, each first failing at position 185 (unobserved field `SequencerSetVerifyHash` byte 0 vs constant 0). |
| P4 | Three collision certificates of kind cross, one per full law, with 10/11/11 `obs_<d>` laws plus `differ`; none uncertified. Each passes bend. |
| P5 | `inj_push` is PROVED: `core/LAWS.bend` holds exactly the three frozen statements, and bend and bend `--verdict` both report ALL PROOFS CHECK. The canary (no `cf`) does not check. |
| P6 | Coverage 73 of 79 (rate 73/79). The uncovered elements are exactly the 6 constant reads (`no_rule`). The `metrics.json` entry carries the Prop 6.11 sentence, `uncovered_disagreements` 0 and 1 HASH candidate. |
| P7 | Exactly one HASH candidate: `HASH.keccak256` with (`enc_sol`, `load_sol`), sinks Rollup.sol:357 and :849, unevidenced. |
| P8 | `spec/M3/evidence_review.jsonl` is empty: the 15 records list 0 disagreements. |
| P9 | **T251**, the variant. The pairs at versions 0 and 1 are pushed by their pinned laws, and `holon run` decides both PROVED, `L_par_cc_RecV1_Bytes_enc_x_v1_pinned` for the first time. At version 2 getter `HdrBytes_B` rejects the 9-byte images (blind), so neither version-2 law is pushed (position 3); `holon run` still decides `L_par_cc_Cache_makeV2_enc_x_v2_pinned` PROVED (not pushed, PROVED). The full laws are REFUTED. Coverage 22 of 33 (observed 2 of 3); 4 certificates check (2 cross, 2 same_side). |
| P10 | **T252**, I24's `par_linked`. The v1 and v2 pairs have no basis law: at v1 the pinned law fails at position 6 (the constants 255 and 0 differ) and the full law at 5; at v2 `HdrBytes_B` is blind and both laws fail at 3. The v0 pair is pushed. Coverage 21 of 33, which is below 1, and 5 certificates check (3 cross, 2 same_side). The statuses are I24's. |

**Regressions and construction checks (not counted).**
- **R1:** no law and no catalog version is added (L-G1). `laws/M3` is unchanged, and I24's tests stay green.
- **R2:** the frozen evidence set's component atoms are exactly rule X7's 161. Its codec, diagram and evidence files are untouched.
- **R3:** D7 is outside today's extraction.
- **R4:** gates M0–M2 pass, the partial M3 gate passes, and M2's metrics are unchanged.
- **R5:** on Morph the static push verdicts pair with I24's records (pushed PROVED, not pushed REFUTED). Rule L4 does not require that pairing in general: a pushed law REFUTED is a finding on an evidenced pair, and a law that is not pushed may be PROVED (T251 v2). A divergence is reported, never resolved by changing a verdict.
- **R7:** no refinement record is over an M3 component edge (gap L-G7): 12 of the 15 name the hand-written `facts/morph_header.json`, 3 the transitions document.
- **R6:** the sidecar is the instrument's computation, and the statements are well-typed. The build's documents equal the instrument's, and the CLI is deterministic, refuses stale inputs and reads no hand document. The code is generic, and the planted review records behave as rule L9 says.

## Outcome paths, narrowly

`gen/M3/par_lossy/` and `spec/M3/evidence_review.jsonl`.

The shared files are deliberately left out (`holon audit prereg` rule 4). These are `results/M3/metrics.json` and `results/M3/metrics_timing.json`, which `holon metrics` writes, and `docs/iterations/I25.md`. Commit them as usual.

I25 writes nothing under `laws/`, `results/M3/L*`, `gen/M3/codec/`, `gen/M3/diagram/` or `gen/M3/evidence.json`.

## Rules

- **AGENTS.md is binding.**
  - Never edit `facts/`, `spec/M1/`, `spec/M2/`, `laws/M0`–`M3`, `gen/M0`–`M2`, `results/M0`–`M2` or I24's M3 inputs.
  - **The evidence set is frozen.** If it changes, the elements change. Report that; never re-derive around it.
- **Q19.** Everything is over the adopted extracted documents. The tool must give the same outputs with `facts/` and `spec/M1/facts` removed.
- **No special-casing.** `holon/rules/par_lossy.py` and every `holon/**/*lossy*.py` name no target or fixture identifier, no law id and no target file.
- **Proofs are generated.** The core proofs and the collision certificates come from generators, never from hand-written Bend, and have no escape hatch.
- **No tuning, no skips.**
  - A static verdict never changes a kernel status and a kernel status never changes a verdict. Where they diverge from the predicted pairing, report it.
  - A missed prediction is a Surprise.
- **Build order.** I25 adds no catalog version, so it does not interact with the catalog pins of I30 (1.2), I27 (1.3) or I31 (1.4).
  - I25 reads the evidence set's `evidence_sha256` at build time, because I30 may change its `sorts_sha256`.
  - It recomputes the component atoms by rule X7. If I30 added E5 atoms over a component, elements of kind "other" would appear and P2 and P6 would miss. Report that, never adjust it.

## Questions for the human (raised by the prereg)

1. **Constant and partial reads (L-G4).** Each of these reads is evidenced at E2 (strong) and has no rule. Morph has 4 pairs: the Go version bytes, and Solidity's zero `SequencerSetVerifyHash` at 3 versions.
   - In the linked fixture, `enc_x` writes 9 bytes at version 2 where the reader `RootNew` expects 11. A constant-read law there would be REFUTED as a finding. Today only the PAR-weak intent question sees it.
   - Should a sub-form `d(e(h)) = Some(c)` be admitted through I45? That needs two instances and a basis argument.
2. **The CF rendering in IR 0.3** (`holon.gen.mlaws`, I7/I12) renders CF(h, S) as pairwise `h(a) != h(b)`. When two listed terms are equal as values, that is stronger than Cor 6.16's CF, which is "h a = h b ⇒ a = b": it then also excludes a = b, and the law becomes vacuous at those points.
   - `core_inj_push` therefore states CF in the implication form, per point.
   - Should the IR's CF premise move to the implication form, or should G11V check pairwise distinctness of the listed terms?
3. **Coverage counts direct coverage (L-G5).** An element implied by other laws counts as uncovered, for example `SequencerSetVerifyHash(enc_sol(k)) = Some(0)`, which follows from the pinned cross-component law and the Go round trip. Should coverage instead count implications that I42/I43 certify?
4. **Replay over the extracted codec model (L-G7).** Every codec and domain refinement record (I16, I23) replays the hand-written M0 header model `facts/morph_header.json`; none replays an M3 component edge (the extracted `morph_batch.go`/`morph_header` codecs). Rule L9 therefore can only ever open reviews with reason `unresolved_edge` from today's records, and the M3 evidence review cannot close a disagreement against an evidenced pair. Should an iteration (I36 or a fix iteration) add per-edge replay records over the linked component's edges?
5. **`spec/M3/lib/oracles.json` does not exist.** I24 dropped it because no M3 law is over a hash parameter. I25's CF premise is the core law's pointwise premise, so no oracle sidecar is needed. A HASH push instance (D7 in I36, header presentation once the transitions diagram exists) will need the hash as a parameter with its CF premise, which is I12's machinery over extracted documents.
