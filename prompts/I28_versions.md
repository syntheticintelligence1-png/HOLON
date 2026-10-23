# I28: versioned machines, PAR-init (O9), D4 as a gap record, G11V's in-flight sets

Rendered from `docs/BUILD_PLAN.md` §4 I28, its laws half (whitepaper Def 4.3 S_k/A_k and the MIG edges, §5.1 initialization coherence, §10.1, §11.3 O9, §11.6 D4, App. A F12.5, §12.3 L21). I63 (= I28a) built the history half. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (V1-V9, PI1-PI6, S1-S3, G1-G3), commands, formats, exit codes, shared files, commit rules and the definition of I28's own commits are in the docstring of `tests_m3/test_versions.py`. The key's thresholds pin that docstring, the instrument `tests_m3/_i28.py`, the sidecar `spec/M3/lib/versions.json`, the basis `spec/M3/lib/versions_basis.json` and five inputs, among them the deployment record, by sha256. The base is the lead after I66's prereg merge (PR #46), `a0bfc521`.

## What I28 does

1. **Versions (V1-V4).** It reads I63's committed history and timeline, never writing them.
   - The deployed path is V3, V4, V5, V6, V7, V8, V9, V10, V11: the versions of the timeline's matched upgrades, with V6's redeploy collapsed. V1 and V2 were never deployed.
   - There are 8 MIG edges along the path, plus the entry edge from the placeholder.
   - The only in-flight entries that are retyped or reinterpreted are the cutover's two (V10->V11: `batchDataStore`, `submitterContract`).
   - Reversing each edge gives one incompatible downgrade, V11->V10.
2. **Documents (V5).** `holon versions extract` runs the I19 frontend on each path version's commit, with a generated sidecar per version. A version that fails to extract becomes debt, never smoothed over.
3. **The versioned machine (V6).** Each version's document is compiled by `holon.sorts.model3`'s compiler, as I30 compiles the adopted one (`step_k`, `run_k`), in whatever storage representation that compiler has when the model is built. The versioned layer has fixed names:
   - the state `VSt`, with one storage kept across upgrades;
   - the step type `VStep`: `C_<version>_<action>` for an action, `U_<from>_<to>` and `U_entry` for migrations under the transparent-proxy assumption A-proxy (the admin's `upgradeTo`, or `upgradeToAndCall` with the edge's reinitializer);
   - `vr0`, `vstep`, `vok`, `vrun`;
   - `VReach` (`VR0`, `VRStep`) from the proxy's creation;
   - `vread`, which reads a word at a layout coordinate (base slot, offset, mapping path).

   `holon/sorts/` and `gen/M3/sorts/` stay as they are.
4. **Refinement (V7, V9).** The upgrade path is fixed in the sidecar: 14 steps, three of them reverting probes. It runs in the model and on the real code of all nine versions behind an OpenZeppelin 4.9.3 TransparentUpgradeableProxy. The two sides must agree on every step's status and revert data (each probe reverts with the `Error(string)` reason the key names), and, at the union of the real slots either side writes, on every 32-byte word.
5. **PAR-init (PI1-PI6), rule PAR's new sub-form `init_chain`, catalog holon-rules/1.6.**
   - A chain is a commitment family with a root site, which hashes input bytes without authenticating a parent, and successor sites, which authenticate a parent header and commit a header built in memory.
   - A chained pair (o, o', s) is a header cell that every successor computes as the parent's cell plus the child's cell o'.
   - The law says the root header's cell o equals its own cell o' (the recurrence's base case).
   - Over the rollup this is the queue cursor: cell 17 (`totalL1MessagePopped`) is the running sum of cell 9 (`l1MessagePopped`). That makes O9 an instance.
6. **Gap records, generated and never hand-written.**
   - D4 gets a link gap (PI5, G1), with obligation D4, Question Q63 and status open.
   - The reverse edge V11->V10 gets a downgrade gap (V4, G2). It stands for F12.5 only under reading (a) of Question 64, and it is a construction check, not a prediction.
7. **G11V (V8).** Every MIG edge of the path gets an in-flight inhabitant: a reachable state at the source version, a commit, then the migration.
   - Legacy words are given for the retyped and reinterpreted entries.
   - Each INHABIT.bend has a fixed shape, tied to its trace and its legacy words:
     - the states, with `s_0` exactly `VM.vr0()`;
     - the steps, each carrying its trace step's arguments, decoded from the calldata, and its caller (`_i28.abi_leaves`);
     - one `vstep` equation per step, and the last two steps' success;
     - one `vread` equation per legacy word, at its layout coordinate;
     - a `VReach` term built from those steps and states in order, down to `VR0`.
   - Bend checks each file, and BendTT does too when the verdict is enabled.
   - G11V reports a new clause, "in-flight: n of n edges inhabited".

## Deviations from the plan's text, and why

- **D4 is a link gap, not a PROVED law** (G1, Question 63). The plan predicted "D4 PROVED by `reach_invariant` under the initialization-coherence premise". Three things block that over the Rollup:
  - D4's registers P and L are the message queue's: `spec/M2/lib/window_rollup.json` marks `qpend` and `qlen` external. No adopted M3 document extracts them.
  - D4 needs two premises the code does not enforce:
    - initialization coherence, whose PAR-init law I28 predicts REFUTED (O9);
    - a queue-length bound L < 2^64. The commit adds the batch's count to the total unchecked, and the header stores the total in 8 bytes, so a total carried past 2^64 - 1 is stored wrapped. That breaks P <= T while T <= L can still hold.
  - `reach_invariant` is a holon-facts/0.2 machinery, and no Reach-inductive proof has been checked over the M3 typed model.

  The link gap names the call sites where the cursor meets the queue. At V11 they are: `commitBatch`, `commitBatchWithProof` and `commitState` call `getCrossDomainMessage`; `finalizeBatch` calls `popCrossDomainMessage`. D4 moves to the key that links the queue (I36), with both premises named. BUILD_PLAN's I28 and I36 entries should record the move once Q63 is answered. A prereg commit cannot edit BUILD_PLAN.
- **F12.5 is not covered by I28 unless the human picks reading (a)** (G2, Question 64). The plan's fallback is "or a rule-gap record is filed". The downgrade gap V11->V10 is generated from I63's layouts, so it holds by construction. It is a construction check, scored as no prediction. Under reading (b), which the prereg review thinks more likely, I28 states nothing about F12.5. Neither I28's report nor the case-study mapping may call F12.5 covered until the human answers.
- **No `spec/M3/facts/morph_rollup.extracted.json`.** The per-version documents are generated outputs under `gen/M3/versions/documents/`. The adopted head document (Q19) stays byte-identical, and V11's extraction equals it. That equality is a construction check: V11's repository units are the head's.
- **The model is written by `holon versions model`**, not by `machine.py`: I30's model code and outputs are frozen inputs here.
- **`init_chain`, not I24's `init`.** I24's sub-form `init` (rule P7) states E3 equations over a holon-facts/0.2 machine's initial state. I24 G1 says it has no instance over a transitions document. `init_chain` is the transitions-document form, so the PAR producers of holon-rules/1.1 stay the same objects. The law-id prefix `L_pinit_` keeps the 80 `L_par_*` counts that F30/F39 and I43-R1 pin.
- **In-flight inhabitants for every edge**, not only the cutover. The witness and the cutover inhabitant also replay on the real code (the plan's exit: "the O9 witness replays").

## What was known before this prereg (disclosed)

- **The basis** (`spec/M3/lib/versions_basis.json`), computed by the instrument from I63's committed outputs, the adopted head document and the sidecar's gap obligations, as BUILD_PLAN §0.1 requires:
  - the path, edges, in-flight counts (24, 25, 25, 25, 26, 26, 27, 27), the two in-flight types, the ten deployments with their immutable words (V6 twice: chain id 1, then 2818), the reverse edges and the one downgrade gap;
  - over the head document: the one chain (`committedBatches`, root `importGenesisBatch`, successors `commitBatch`, `commitBatchWithProof`, `commitState`, pair (17, 9, 192)) and the one link gap with its four sites.
- **The target's sources, read with `git show` at the path versions' commits** (the I63 checkout `/root/work/morph`):
  - `Rollup.sol`'s pragmas and imports at all nine (every one pins `=0.8.24`);
  - the initializers, `importGenesisBatch`, the successor functions and the queue calls at V3 (`v0.4.0`), V7, V9, V10 and V11;
  - V3's `commitBatch` and `_loadBatchHeader`;
  - V10's `commitBatch`, its `BatchData` store and `onlyActiveStaker`;
  - `IRollup.BatchData` at V10 and V11, and `IRollup.BatchDataInput` at all nine (its first two fields are `uint8 version, bytes parentBatchHeader` at every one: the basis of `_i28.commit_key`);
  - the ABI types of the commit functions at all nine (no array parameter), for `_i28.abi_leaves`;
  - the probes' revert reasons: OpenZeppelin 4.9.3's `initializer` guard in the pinned tree, V3's `importGenesisBatch` (`v0.4.0` Rollup.sol:181) and V11's `initialize4` (Rollup.sol:212).

  The prereg review then read all nine commits and found that `importGenesisBatch`'s index check exists from V4 on; only V3 lacks it. `git diff 5edbc693 3e44e795` is empty over the seven repository units among the head document's twelve extraction units; the other five come from the pinned OpenZeppelin tree.
- **The history's layouts:** `l1StakingContract` sits at slot 151 at V1-V10, `submitterContract` at V11; `committedBatches` at 161 and `batchDataStore` at 162 at every version.
- **The deployment record's calls, decoded:**
  - `initialize`: submitter stand-in `0x5615…`, queue, verifier, 40, 10, 70;
  - `updateRollupDelayPeriod(20)`;
  - `addChallenger(0x1004)`;
  - `importGenesisBatch` with a 249-byte version-0 header: index 0, popped 0, total 0, data hash 1, the zero versioned hash, post-state root 0x64.
- **holon read to find cross-key constraints:** `holon/rules/__init__.py`, `holon/statement_diff.py`, `holon/ir.py` (`HASHED_KEYS_03` holds `rule_catalog_version`), `holon/lean.py` (`_attempted`), `holon/gate.py`, `holon/audit/prereg.py`, `holon/mpipeline.py` (`law_import_problem`), `holon/bend.py` (the verdict) and, on the new base, `holon/profile.py` (`GEN_PROFILE` and its closure). `holon.records.generator_files` was called to list the closures (0.1: 6 files; `holon/rules/` is in 0.2 and 0.3).
- **The independent prereg review** of the first draft (`b6a5318c`, on the stale base `fde1f819`): no sign-off, with 1 blocking, 5 major and 13 minor findings and 2 notes. This draft folds every one of them; the report gives the map. The draft's base was stale because the lead had already merged I32's build.
- **Its verification pass** of the fold (`11c1c932`): no sign-off. It found:
  - N1 (major): the own-commit selection picked another lane's merge of the lead;
  - N2 (major): a defect in I66's re-scope of I32-R2, which is I66's to fix;
  - N3 and N4 (minor): a loose INHABIT.bend shape check, and probes compared without their revert reasons;
  - N5 (a note on ordering).

  `268e828f` fixed N1, N3 and N4. A toy repository reproduced N1 and showed the ancestry selection picking I28's merge. N5 became a precondition of the build, and the base now meets it.
- **Its second verification pass** (`268e828f`) signed off, with one minor finding and two notes:
  - S1 (minor): a report merged in from a side branch made the selection pick that merge inside the build branch;
  - S2 (note): before M exists, the first commit rule cannot be checked from git;
  - S3 (note): the caller could sit in any field after the arguments.

  This draft, rebased onto `a0bfc521`, fixes S1 with a condition on M and a third commit rule, and pins the caller as the first leaf after the arguments (S3). The reviewer's two toy repositories pick I28's merge under the fixed selection. The I66 verification's T4 is a risk below and a commit rule in the docstring.
- **Moved onto `f5534775`** after the sign-off. That is the lead with F40, I66's build and I65's build. F40 adds the deployment's runtime code, a new `code` field, to `gen/M3/sorts/models/morph_rollup.extracted.init.json`. I28 reads only that file's `storage` and `calls`, so the move changes just the key's `base` and that file's pin. Every other pin holds on the new base: the instrument, the contract docstring, the sidecar, the basis and the other four inputs. The prereg's tests give the same results as on `a0bfc521`. In `spec/M3/amendments.jsonl`, I28's eight lines now follow I66's three.
- **Not run:** the frontend on any old version, Bend, `holon run|gate|derive` on M3, and anything on the network. The predictions about extraction, the model, the search and the replay are untested.

## Risks for the build

1. **Old code through the frontend.** V3-V5 use `BatchCodecV0` and loop over block contexts. V3-V10 call `IL1Staking`. A construct the frontend refuses makes that version debt, so P1 misses.
   - Every trace passes the path's versions in order from V3, so a debt version also cuts P2 and every witness or inhabitant whose trace reaches it. For V3, that is all of them.
   - If V3 becomes debt, P1, P2, P3, P5 and P6 miss together, as one dependent event. The report must say so when it gives the hit rate.
2. **Bend size and G5's 120 s.** One version's typed model is about 979 KB of Bend, and nine are about 9 MB. V6 allows one module per version, so a proof or inhabitant can import only the versions its trace reaches.
3. **The storage representation (Q21).** The Q21 key (I68, from the human's Q21 answer) re-models M3's storage with structural keys `SK{base, offset, path}`, so that no keccak table is used for slots. I28's contract is written so that this does not contradict it:
   - V6 compiles each version with `holon.sorts.model3`'s compiler in whatever representation it has when the model is built.
   - Every I28 claim and output about storage names real slots (EVM addresses, as the real chain and the instrument compute them) or layout coordinates, never the model's encoding of a location. Examples: the replay's slots (one entry per real slot, full words), the in-flight legacy words, `committedBatches[0]`, and `_initialized` at slot 0.
   - The `vread(s, base, offset, path)` coordinate has the shape of a structural key, so INHABIT.bend reads the same under either representation.
   - "Every location kept across an upgrade" holds key by key under structural keys. The cutover's slot 151 and `batchDataStore`'s fourth member are the same keys read with V11's masks.
   - The init term's statement ref hashes documents, not the model, so a re-model does not move the law's statement hash. Its binding (`spec/bindings/M3.json`, G2) does reach the versioned model's definitions, so it is part of I68's rebinding problem (its H1).

   No I28 prediction depends on the hashed slot encoding.
   - If I68 lands after I28's build, it regenerates the versioned model, the inhabitants, the PAR-init proof and the replay in-contract. Only I28's `--check` outputs move, and the replay must map structural keys to real slots.
   - If it lands first, I28 builds on structural keys from the start.
4. **Wiring `init_chain` into derive.**
   - `_typed_rules` runs every catalog key but PAR.
   - `_par_part` runs `cat["PAR"]` per codec document, in `par.SUBFORMS` order, so it skips the new sub-form.
   - `law_hash` over a law whose facts is the versioned document needs a reader other than `TypedDocument`.
   - DERIVATION's I24 keys must not move.
5. **The re-derivation's churn.** I26 spent hours on this for 1.5.
   - Every M3 statement hash moves, so `holon.statement_diff recatalog` runs (32 min under I26).
   - Every law is rebound (`spec/bindings/M3.json`; `holon bind` must learn the new law).
   - The PAR records are re-made in I43's order (run, `holon lean`, run), and the typed SORT, DISCH and FACT records are re-made.
   - The M1 and M2 records are regenerated for `generator_sha256`, because `holon/rules/` is in their closures.
   - So are the five T32 records, through `holon profile --milestone T32`: `GEN_PROFILE`'s closure holds `holon/rules/`, so without it I32's C1 fails on `generator_sha256`. I66 does the same for its own closure edits.
   - Then metrics, evidence and the Q4 schema copy.
6. **The inhabitant search.** V10->V11 needs exactly the sidecar's 12 steps. The commit inputs of old versions differ from the head's: V3 takes block contexts, and later versions take `lastBlockNumber`/`numL1Messages`. I30's candidates target the head document.
7. **Legacy external calls in the replay.** `isActiveStaker`, `getStakerBitmap` and `verifySignature` go to the address the deployment record's `initialize` puts in slot 151. That is the binding's submitter stand-in, so the replay needs a labelled stand-in answering both interfaces as the trace's environment does (Q12; I36 owns the real legacy staking contract).
8. **The two-sided refinement.** The harness must report each real step's state diff (for example anvil's `debug_traceTransaction` prestate diff, or struct logs). The model's write set alone is not enough (V7, V9). Each step's revert data is compared too: the model's comes from its run (model3's `run_<a>` returns it), and the real one is the transaction's return data, which the proxy passes on from a reverting `upgradeToAndCall`.
9. **I40 and G6 for a versioned witness.** Refute's concretization and final filter, and G6's binding to `replay/M3/versions/report.json`.
10. **Couplings with other keys.**
    - If P3 misses with a PROVED PAR-init law, I43's `rendered()` raises: the law's kind is "other" and its rule is neither DISCH nor FACT. No tree would then satisfy both I43 and I28 without an I43 amendment.
    - The per-version documents are frontend outputs, and the init ref hashes them. Any later frontend change (I35-I39 extend the extractors) stales `gen/M3/versions` and re-versions the PAR-init law, through `statement_diff` lines.
11. **Order against other lanes.**
    - F40 (the other session's caller-pool fix) re-makes the typed, DISCH and FACT records. I28's re-make must follow it, or be redone after it.
    - I66's prereg (PR #46) is on the base. It re-scopes I32-R2 (`tests_m3/test_disch_profile.py`) to I32's own commits, which I28's closure edits need; I28 does not amend I32-R2 itself.
    - I32-R2 computes the generator closures at HEAD (I66's verification, T4). If an I28 commit made a closure module import one of I32's six holon files, I32-R2 would turn red for a change I32 did not make. The six are `holon/__main__.py`, `holon/profile.py`, `holon/gen/profile.py`, `holon/rules/disch_profile.py`, `holon/analysis/abstraction.py` and `holon/js/profile.mjs`.
      - Today only `holon/__main__.py` reaches them, through `holon.profile`, and no closure module imports either.
      - I28's planned edit stays clear of them: `holon/rules/__init__.py` (in the holon-ir/0.2 and 0.3 closures) gains an import of `holon/rules/par_init.py` and of no other rule module, and neither imports the six, directly or through `holon/versions/`.
      - The `holon versions` CLI goes into `holon/__main__.py`, which no closure module imports. A commit rule in the docstring states the constraint.
    - I65's build may land first.
12. **Reds that are not I28's**, from I26's report on the base:
    - I43's construction checks (107 failures, I26 Question 5). I28's bump moves the same pins again. I28 amends none of them, and re-baselines `spec/M3/lib/lean_promoted.json` only alone in its commit, under I43's disposition or the human's answer;
    - I40-R2 (I26 Question 9);
    - I15's scan (I26 Question 8);
    - I26's P5 and P7.

## The build branch and commit sequence

The build branch starts at the prereg commit, as I63's and I32's did. I28's own commits, which R1 and R2 judge, are the first-parent commits of the build merge's second-parent side. Before that merge, they are the first-parent commits from the prereg. The build merge M is chosen by ancestry from the commit that adds `docs/iterations/I28.md`, so it is the same commit on the lead and on every branch that merges the lead later. The order follows the earlier keys' commit rules in the docstring.

Three commit rules keep that definition exact on every branch:
- **The prereg reaches the lead only on the second-parent side of a merge commit**: no direct push, fast-forward, squash or rebase merge. Then the prereg commit lies on no other branch's first-parent chain, so no other lane's commits count as I28's.
- **The build reaches the lead only through its own merge commit M**, and no other line merges the build branch before M does.
- **The build branch merges only the lead**, never a side branch. Every I28 commit then lies on its first-parent line. M is never a merge inside the build branch: the test rejects a candidate whose first parent's first-parent chain holds the prereg.

I66's prereg (PR #46) is on the base, so its re-scope of I32-R2 is in force before I28's first commit that changes a closure file.

1. Code (`holon/versions/`, `holon/rules/par_init.py`, the catalog, the IR init term and its ref, bindings, the G11V clause, refute and G6 integration).
2. `gen/M3/versions/` (extract, model, analyze).
3. `laws/M3` under holon-rules/1.6, then the `catalog_rederivation` lines, then the rebinding.
4. The M1 and M2 records, regenerated in commits of their own, and the five T32 records by `holon profile --milestone T32`, in a commit of its own.
5. The re-made M3 records, in commits that touch no M0-M2 path (I26-R1, I31-R2).
6. The new record, the inhabitants and the replay.
7. Refute's filter for the new record, in a commit that adds no record (I40-R2).
8. Metrics, evidence, the Q4 copy and casestudy.
9. The report, `docs/iterations/I28.md`.

## Predictions (key I28 in `spec/M3/predictions.json`)

- **P1.** V3..V10 extract, and none is debt. Each document and its generated sidecar are at the history's commit.
  - Each document has one chain: `committedBatches`, root `importGenesisBatch`, pair (17, 9, 192).
  - Its successor sites are `commitBatch` (V3-V6); add `commitBatchWithProof` (V7, V8); add `commitState` (V9, V10).
- **P2.** The model refines the real upgrade path in both directions. The 14 steps are:
  - the entry edge, then `initialize` and `importGenesisBatch`;
  - the same two calls again, each reverting (OpenZeppelin's "Initializable: contract is already initialized", then "genesis batch imported");
  - the 7 MIG edges up to V10;
  - the cutover with the wrong index 1, reverting ("cutover batch mismatch");
  - the cutover.

  Statuses and revert data agree: each probe reverts on both sides with exactly its named `Error(string)`, never at another guard. So do the words at the union of both sides' writes. Reverting steps write nothing, and each successful call writes. `_initialized` (real slot 0) reads 1, 2, 3 and 4 after `initialize` and after the edges into V4, V7 and V11.
- **P3 (O9).** One `init_chain` law, `L_pinit_Rollup_importGenesisBatch_committedBatches_17_9`, is REFUTED at V3.
  - The trace is [entry, `initialize`, `importGenesisBatch`]. The root step is the recorded genesis call by its recorded caller, with the header's total set to 1 and popped still 0.
  - PROOF.bend imports LAWS.bend. Bend checks it (BendTT too when the verdict is enabled), and the witness replays on V3's code.
  - Why: `importGenesisBatch` never reads bytes 17..24 at any version.
- **P4 (D4).** One link gap, with these sites at V3..V10: the successors call `getCrossDomainMessage`, `finalizeBatch` calls `popCrossDomainMessage`, and nothing else does.
- **P5 (G11V).** All 8 MIG edges are inhabited by shape-checked INHABIT.bend files, each accepted.
  - The shape anchors each file at `VM.vr0()`. Each step carries its trace step's arguments and caller, and the `VReach` term is built from the file's own steps and states, so the Bend-checked trace is the trace P6 replays.
  - Each key is the index its last commit writes.
  - At V10->V11, the nonzero legacy words are `batchDataStore[k].signedSequencersBitmap` and real slot 151 (`l1StakingContract`).
  - G11V reports "in-flight: 8 of 8 edges inhabited", whatever its other items say. Those items include Q36's DISCH law, which is the other session's and unrelated to I28's in-flight sets; the clause holds with or without F40.
- **P6.** The cutover's inhabitant replays. After the real `upgradeToAndCall(V11, initialize4(..))`:
  - `batchDataStore(k)` returns the legacy bitmap's low 160 bits as its submitter;
  - `submitterContract()` returns `initialize4`'s first argument.

**Construction checks, not scored:**
- the downgrade gap V11->V10 (F12.5 only under reading (a));
- V11's document equal to the adopted head document;
- the link gap's V11 sites, obligation, question and status;
- the re-make of every M1, M2 and T32 record's `generator_sha256`.

**Regressions** (green at the prereg):
- **R1.** No commit of I28's own deletes an M3 law or record. None changes an existing M3 law in anything but `rule_catalog_version` (each such change has its `catalog_rederivation` line), and none changes an existing M3 record's status.
- **R2.** No commit of I28's own touches:
  - a frozen root;
  - I63's outputs or instrument;
  - `spec/M1/` or `spec/M2/`;
  - an earlier M3 sidecar;
  - `holon/sorts/`, `gen/M3/sorts/` or `gen/M3/theory/`;
  - `laws/T32/`, `gen/T32/`, `results/T32/summary.json` or `gen/M3/disch/classification.json`;
  - an M0-M2 law, `gen/` or `replay/` path, or `results/M0/`.

  M1, M2 and T32 records may change only in `generator_sha256` and `seconds`.

## Earlier tests amended at this prereg

Each amended test checks at the prereg what it checked before (`spec/M3/amendments.jsonl`, 8 lines):
- **I24.** The PAR readers leave out exactly the laws, entries and records of sub-form `init_chain`, and nothing else. The readers are `_Morph.derived` and its two inherited keys, `test_derivation_follows_the_rules`, `par_records` and `test_every_m3_law_has_a_valid_record`. `test_catalogs` keeps I24's producers as the same objects and admits `init_chain`, and only it, beside them.
- **I25.** `test_i25_adds_no_law_and_no_catalog` makes the same catalog narrowing.

I32-R2 is not amended here: I66's prereg re-scopes it.

## Deliverables

- `holon/versions/` and `holon/rules/par_init.py`. Both are generic: every target name comes from the sidecar or the documents. The lines I28 adds anywhere under `holon/` are checked for target names too.
- `python -m holon versions extract|model|analyze|inhabit|replay [--check]`.
- The outputs under the key's outcome paths: `gen/M3/versions/`, `results/M3/versions/`, `replay/M3/versions/`, the `L_pinit_` law, its record, its LAWS.bend and PROOF.bend, and `docs/iterations/I28.md`.
- The shared files the docstring lists, changed only as it says.
- An independent build review by one fresh agent, and the report, with every miss and every debt item stated plainly.

## Questions for the human

- **Q63 (D4).** Do you accept recording D4 over the Rollup as a generated link gap, and moving the invariant to the key that links the message queue (I36)?
  - If so, the key that states D4 should carry two named premises: initialization coherence, whose PAR-init law I28 predicts REFUTED (O9), and the queue-length bound L < 2^64.
  - The alternative, a weaker Rollup-only order under a no-wrap premise, is not D4.
- **Q64 (F12.5).** Which "downgrade" is meant?
  - (a) A reverse implementation transition. This is the gap V11->V10, with the cutover's struct and slot 151 retyped back. That transition is not an operation of the deployed system's history.
  - (b) A batch header's version going down along a chain of commits. At V11, `_commitBatchWithBatchData` checks only `version <= 2`, so a version-0 batch can follow a version-1 or version-2 parent. F12's other items are codec and header obligations, which makes (b) the more likely reading. No PAR sub-form states an order along chains, so (b) needs a rule-gap record or a new sub-form in a later key.

  Until you answer, I28 does not count F12.5 as covered.

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, I63's outputs, `spec/M1`, `spec/M2`, `holon/sorts/`, `gen/M3/sorts/` or `gen/M3/theory/`.
- The instrument, the sidecar and the basis are fixed at this commit. A wrong instrument is a Question plus an amendment line, never a silent edit.
- A missed prediction is a result. Report it; never adjust a rule, an input or a budget to make it hold.
- Witnesses and inhabitants come from the versioned model, and their replays from the real code. The checker's word is final.
