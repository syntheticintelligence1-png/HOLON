# Round 1 independent audit: M0/M1

## Verdict and boundary

**The checked model results reproduce, but M0/M1 are not yet a conforming implementation of the whitepaper's assurance/finding gates.** In particular, a green gate does not establish premise non-vacuity, and `triage: finding` plus `replay: passed` does not establish production reachability. There are also genuine, reproducible public-call obstructions; these should not be discarded along with the false-positive scope claims.

Audit date: 2026-10-11. Audited HOLON base: [`9ed1681c14dde316c5225431d28317a8b12eecfc`](https://github.com/syntheticintelligence1-png/HOLON/tree/9ed1681c14dde316c5225431d28317a8b12eecfc). Target: [`morph-l2/morph@3e44e795586af3e11285b603ab642c67823add51`](https://github.com/morph-l2/morph/tree/3e44e795586af3e11285b603ab642c67823add51). All Morph line numbers below refer to that commit, not a deployed chain or current upstream. HOLON line numbers refer to the audited base. `R` abbreviates `contracts/contracts/l1/rollup/Rollup.sol`; `Q` abbreviates the adjacent `L1MessageQueueWithGasPriceOracle.sol`.

Read AGENTS, the M0 specification and Bend primer, whitepaper §§5–6, 8.5–8.7, 9.3–9.6, 11 and 12.3, M2_SPEC, ARCHITECTURE and M1_REPORT. Compared all 24 laws, all three facts files, their generators, result records, prediction registries and native replay harnesses. Regeneration, adversarial probes and additional native tests ran in a separate working copy. **This PR changes only this document; no law, fact, prediction, test, registry, implementation or frozen digest is changed.**

Severity below is severity to HOLON's assurance claims, **not a Morph bounty severity or an assertion of deployed exploitability**. “Finding” in the filter means a demonstrated API-level obstruction with the stated permissions and boundary; economic impact still needs separate analysis.

## Ranked findings

### R1 — High: V2 helper refutation is promoted past a production encoder that repairs it

**Evidence.** `laws/M0/L_par_hdr_v2.json` compares Solidity encoding with `BatchHeaderV1.Bytes`, whose first byte is necessarily 1. This is a valid counterexample to that helper-level equation. But Morph's actual producer at `common/batch/batch_cache.go:1707-1736` has a V2 branch: it aggregates blob hashes, invokes the V1-format helper, then sets `h[0] = BatchHeaderVersion2` at line 1730. `replay/M0/facts_audit.md:42` incorrectly says “no V2 encoder exists.” The M0 Go replay exercises the helper, not this producer; its Solidity side is `not_applicable`, yet `results/M0/L_par_hdr_v2.json` is a passed finding.

**Independent test.** Constructed a `BatchCache` with both upgrade predicates true and called the real `createBatchHeader`: output length **257**, version **2**, and `validate()` succeeds. The test does not claim the nil-sidecar fixture is a complete valid V2 transaction; it directly disproves the absence of the production version rewrite. The all-zero frozen header witness also does not satisfy public `commitBatch` root/blob guards (`R:294-295,913`).

**Consequence / fix owner.** Extraction and finding-filter owners: retain the checked helper refutation, but classify its *protocol interpretation* as **Model defect (wrong path/scope)**. Model the full producer and its activation predicates before alleging cross-component V2 disagreement. Frozen-file owner must approve correction of the old audit assertion; do not “fix” this by changing the prediction to manufacture a pass.

### R2 — High: G11 tests law presence, not premise inhabitance

**Evidence.** `holon/gate.py:180-196` checks that a result exists, that `LAWS.bend` has the expected law name, and that a summary exists. It never reads premise witnesses, let alone checks representative inhabitants. Its success text nevertheless says “non-vacuous LAWS.bend.” This is not G11 as specified in whitepaper §9.3/§12.3. The complete gate list at `holon/gate.py:39` is GENV/G2/G1/G3/G5/G11/G7/G4, not all eleven whitepaper gates; notably native replay is not enforced here as G6.

**Independent probe.** Loaded actual M1 records, replaced only their in-memory `premises` metadata with `['False = True']`, removed any inhabitant field, and called `Gate.g11()`: it still passed. This isolates G11's omission; it is **not** a claim that editing frozen IR evades G2 or that this probe forged a complete gate pass. The audit separately evaluated representatives for every current explicit premise conjunction (table below), and found no currently unsatisfiable written conjunction. M0's premise pinning also rejects contradictory pins; that useful check is not a general inhabitance certificate.

**Consequence / fix owner.** Gate/IR owners: add hash-bound, checked inhabitance obligations for the conjunction of premises, including oracle hypotheses and representative non-degenerate states. Keep the existing law-name check under its actual name. Until then, “GATE PASSED” means the implemented subset passed, not whitepaper gate conformance.

### R3 — High: oracle and cryptographic assumptions are not carried as parametric proof obligations

**Evidence.** `spec/M1/facts/morph_rollup.json:12-20` selects concrete stand-ins: honest presented headers, index-based commitment equality, injective Nat aggregation, an active-set submitter and proof acceptance iff `proof == 1`. `holon/gen/machine.py:99-108,311-313` constructs injective Nat encodings rather than quantifying over a hash satisfying a local premise. `holon/mpipeline.py:230-237` appends the same CF text to every result, even the Go OWN law, but the generated theorem does not receive that hypothesis. It omits comparable structured verifier, messenger and growth-oracle obligations. This is a useful abstract model, but not the parametric contract required by §8.5.

**Independent tests.** Real `ZkEvmVerifierV1.verifyBatch(hex"01", root)` reverted; the replay's `HolonVerifierOracle` accepts that same one-byte proof (`replay/M1/solidity/HolonTraceReplay.t.sol:43-47,182-185`). The real path goes through `ZkEvmVerifierV1.sol:22-28` and `SP1VerifierPlonk.sol:54-100`, including proof-selector/length and cryptographic checks. Do not interpret this as proving no valid proof exists: the missing item is a proof for the actual public input used by the schedule. Real Submitter activation/deposit/slash and the zero-blob hypothesis did pass restricted native tests (A4 table).

**Consequence / fix owner.** Model/IR and replay owners: separate abstract-model theorem scope from concrete-refinement evidence; carry each oracle contract and its validity region explicitly. `L_sym_omega` and the proof-based DISCH strategy have no real-proof production schedule in the current evidence. Label them **Known limitation / conditional** until supplied. `scope: unbounded` is valid only for the closed generated model; it is not unbounded refinement to Solidity, Go, or a chain. Do not replace local finite-set CF with global injectivity: whitepaper Theorem 6.15 rules that out.

### R4 — Medium: DISCH's advertised profile has become examples plus a single-call obstruction

**Evidence.** Whitepaper §11.8 predicts a two-point discharge profile. `laws/M1/L_disch_delay_nofree.json:9-55` quantifies only message count `n` in one hard-coded `commitBatch` from a fixed constructed state. The pay/wait laws existentially find one strategy each from that state. Neither the missing universal quantification over admissible principal strategies nor Pareto minimality follows from that single-call failure. Costs and delay are concrete facts-level functions, not universal fee/proof-cost hypotheses. The third proof strategy is correctly marked post-hoc in `spec/M1/predictions.json`.

**Consequence / fix owner.** DISCH law/spec owners: report “two achievable example points plus a restricted immediate-call obstruction,” or preregister and prove a lower bound over the relevant principal's full strategy language. Do not present these three existing theorems as establishing the whole profile. No counterexample to the intended profile itself was established by this audit.

### R5 — Medium: migration replay manufactures the antecedent and omits initialize2's domain

**Evidence.** `spec/M1/facts/morph_rollup.json:3081-3129` defines `legacy` by zeroing CSR and `eta2` by its conditional write, without the nonzero-root or initializer-version guards. Actual `R:188-195` has `reinitializer(2)` and `root != 0`. `replay/M1/solidity/HolonTraceReplay.t.sol:192-200` uses `stdstore`/`HV.store` to erase CSR before calling `initialize2`; this is not a public-entry-point schedule. `config/triage.json` acknowledges the historical condition but still labels it a finding.

**Consequence / fix owner.** Migration extraction/replay owners: retain the abstract counterexample as **Known limitation (historical reachability unproved)**. Supply the old implementation, a reachable pre-upgrade state, initializer version, and upgrade transaction sequence. Model the migration's domain, rather than claiming its write alone models `initialize2`. The audit does not disprove the latent historical bug; it rejects the present evidence as satisfying §9.6.

### R6 — Medium: the Go growth oracle's declared bound is absent from the law domain

**Evidence.** `spec/M1/facts/morph_batchdata.json:12-16` explicitly says capacities beyond the ≤512-byte class table use an incorrect exact-capacity fallback. This honesty is good. But `laws/M1/L_own_txspayload.json:9-33` quantifies over arbitrary traces with no growth-bound premise, and its result is `scope: unbounded`. The search policy's bound does not restrict a theorem's domain.

**Independent test.** On Go 1.24.13, `append([]byte{}, make([]byte, 513)...)` has capacity **576**, not the fallback **513**. The table up through 512 matches `runtime/sizeclasses.go:95`, and the small native OWN witness does reproduce (length 70, capacity 80, first difference 68). Thus this is a refinement/domain problem, **not a reason to discard the existing small counterexample**.

**Consequence / fix owner.** Heap-model and result-schema owners: bind refinement to a checked all-allocations-in-table predicate, or model the runtime oracle fully; keep abstract universal scope separate from native validity bounds.

### R7 — Low: one stale real-source citation, plus untracked statement-scope changes

**Evidence.** `spec/M1/facts/morph_rollup.json:716` cites `R:685-687` for `batchInChallenge`; those lines implement `isBatchFinalized`. The intended `challenger != 0 && !finished` implementation is at **691-693**. The modeled expression itself matches. M0's V0/V1 proofs also include `ssvh = 0` (`laws/M0/L_par_hdr_v0.json:19-45` and the V1 analogue), not stated in the terse §11.8 rows. This premise is necessary and satisfiable, and was already explicit in the M0 contract; it should be identified as strengthened-hypothesis scope relative to that table, not silently credited as the unrestricted prediction. No later edits to those frozen law statements were found in their git history.

**Consequence / fix owner.** Facts/freeze owner: correct the citation through the normal proposal/refreeze process. Spec owner: record explicit scope/diff approvals for transcription changes. This audit changes neither frozen artifact.

## A3 — complete regression matrix

P = PROVED, R = REFUTED. Fresh outcomes match recorded outcomes; this does not establish the intended *production* interpretation. No §11.8 row is simply dropped, and no previously frozen M0/M1 statement was found weakened by a later implementation commit. The principal differences are at whitepaper-to-IR transcription and model/observer boundaries.

| Law | Fresh | §11.8 comparison / actual checked scope |
|---|---|---|
| `L_par_hdr_v0` | P | Predicted P; adds/retains `version=0, ssvh=0`; fixed-width fields, empty Go cache. R7. |
| `L_par_hdr_v1` | P | Predicted P; `version=1, ssvh=0`, same narrowing. |
| `L_par_hdr_v2` | R | Predicted R and byte-0 witness reproduced for the V1 helper; wrong production-path inference, R1. |
| `L_par_hdr_ssvh` | R | Additional M0 law, absent from §11.8; version 1 with nonzero ssvh distinguishes the helper. Correctly an intent question, not evidence of a current producer emitting it. |
| `L_dom_hdr` | R | Renames/generalizes `L_dom_v0` to arbitrary bytes; the predicted v0/250-byte subcase remains the witness. |
| `L_rt_go_v0` | P | Additional M0 law: **Go decode of Solidity encode**, not Go encode/decode. Version 0 and zero ssvh; `view` omits last-block-number. |
| `L_rt_go_v1` | P | Additional M0 decode-after-Solidity-encode law; version 1 and zero ssvh. |
| `L_rt_go_v2` | P | Same for version 2; not evidence for a missing Go V2 encoder. |
| `L_undo_CSR` | P | Projection erases shadow CSR above LCI; all modeled states/traces, not just reachable ones (stronger domain). No public storage-getter observations. |
| `L_undo_BD` | P | Same for shadow BD; narrower register/observer interpretation than arbitrary storage equivalence. |
| `L_undo_BVH` | R | Predicted schedule retained; successful commit premise and next-index premise explicit. |
| `L_undo_cancel` | R | Predicted challenge/pause residue retained; successful challenge premise explicit. |
| `L_sort_remaining` | R | Predicted timeout arithmetic symptom retained at `t=start+W+1`. |
| `L_tag_BVH` | R | Witness uses v1→v2 rather than §11.8's v2→v1; same cross-sort reuse obstruction, transparently recorded in predictions. |
| `L_fact_Z` | R | Equal header commitment vs different blob lists; consumer is `blobs_of`, not a modeled L2 execution/derivation result. |
| `L_sym_omega` | R | Renames `L_sym_ω(zk,challenge)`; both action orders must succeed in the oracle model. R3 limits concrete replay. |
| `L_disch_delay_nofree` | P | Decomposition of profile claim; only one action family, R4. |
| `L_disch_delay_pay` | P | One existential cost-1, delay-0 strategy from fixed state; not minimality. |
| `L_disch_delay_wait` | P | One existential cost-0, delay-19 strategy from fixed state; not universal Δ-fin bound. |
| `L_disch_delay_prove` | P | Post-hoc third point, cost 1000 in abstract units; explicitly marked, not a preregistration success. |
| `L_disch_stale` | P | `kappa` preserved under `perm(a)` including time, on arbitrary model states. Principal/action set is fixed by model. |
| `L_disch_stale_commit` | P | Additional decomposition: under `kappa`, permissionless proof-commit fails. Does not say owner/active submitters cannot discharge. |
| `L_nat_eta2` | R | Post-hoc relative to §11.8, drawing on §11.4; explicitly marked. R5 historical antecedent unproved. |
| `L_own_txspayload` | R | Predicted **conditional** alias obstruction retained; public Go API result, not a production call-site lifetime finding. |

The two UNDO projection laws are not vacuous merely because they erase a register: they quantify over pairs differing in that register and nonempty continuations. They certify that their *chosen machine observation* is independent of it. They do not claim raw `committedStateRoots(i)`/`batchDataStore(i)` getters return equal values after revert. That boundary must survive into user-facing conclusions.

History check: path-scoped `git log`/`git diff` on `laws/M0`, `laws/M1`, and `spec/M1` found original M0 statements, the M1 initial statements, and subsequent addition of OWN/registry entries; no removal of an existing M0/M1 law. The M1 prediction transcription correctly distinguishes its two post-hoc items. The additional M0 round-trip/ssvh laws are not §11.8 predictions.

## A4 — premise and oracle inhabitance/strength matrix

`CompiledMachine.evaluate` was run against the compiled Bend artifact, not a reimplementation. For every R law the recorded witness yielded all premises true and the claim false. Existential strategy records yielded all four conjuncts true. For the remaining premise-bearing P laws, the following nontrivial representatives were evaluated. These are audit tests, not the missing kernel-certified G11 inhabitant artifacts.

| Explicit premise group | Representative and result |
|---|---|
| M0 version / zero-ssvh pins (six P/R versioned laws) | Deterministic random-filled headers with the specified pins; all operations defined. P equations true, V2 helper equation false. Nonzero data/root/index bytes avoid all-zero inhabitants. |
| M0 ssvh law, version 1 only | Random-filled header with nonzero ssvh: defined and unequal. |
| M0 domain law | No premises; bytes domain inhabited. Checked native v0 250-byte rejection/acceptance and public padded genesis below. |
| UNDO CSR/BD projection equality | Start after a successful commit; copy state and append a different shadow CSR/BD entry to just the erased register. A nonempty revert/recommit continuation preserved projection equality. Both premise and claim true. Pair is a model-state inhabitant; not a claim both copies arose from an identical production history. |
| UNDO BVH successful commit/type/next index | Recorded `p=[]`, commit version 1, `k=1`, recommit continuation: three premises true. |
| UNDO cancel successful challenge | Recorded two-commit prefix, `j=1`: premise true, continuation differs. |
| DISCH stale `kappa` and `perm` | Actual model prefix commit, challenge, wait 11 (W=10), then `wait(1)`: both premises and claim true. |
| DISCH stale-commit `kappa` and proof-commit type | Same reachable model prefix, typed proof-commit action: both premises true and `last_ok=false`. |
| FACT Z commit types/success/equal new header | Recorded empty prefix with absent sidecar versus `[Z]`: five premises true, blob lists unequal. |
| SYM action types / both orders succeed | Recorded prefix commit + wait 21 and proof token 1: four premises true **in the oracle model only**. |
| Other M1 laws | `assume=[]`; no premise conjunction to be empty. Sort/tag/OWN/NAT countertraces are nonempty. DISCH nofree tested at `n=1`; pay/wait/prove strategy witnesses satisfy their claims. |

| Hypothesis / abstraction | Native or source check | Assessment |
|---|---|---|
| M0 A-width / A-version | Codec `shl(192, x)` and Go uint64 fields agree on 8-byte width; `R:293` version ≤2. `BatchDataInput.numL1Messages` is uint16, so the eight-byte abstract field over-approximates public inputs. | Satisfiable; layout theorem, not unrestricted public reachability. |
| M0 A-cache | `batch_header.go:213-215,241-243` returns a supplied nonempty cache without rebuilding. Native witnesses use fresh structs. | Empty-cache premise satisfiable, must not be dropped from scope. |
| M0 A-dirty / A-hash | Every output byte written by the audited store order; comparisons are bytes, not hashes. | No cryptographic premise required. No unwritten in-range byte found. |
| Local CF for headers | Native harness recomputes header hashes; 300 traces/2432 steps agreed on its sampled projection. | Finite empirical support, not proof of hash injectivity or validity for all future header sets. `CB[k] != 0 iff k≤LCI` also needs exclusion of a zero digest, beyond pairwise collision freedom alone. |
| V2 `agg` injectivity | Nat pairing/list encoding is injective but unbounded; real `R:888-918` uses 256-bit keccak of blob hashes. | Satisfiable as an abstract encoding; no unrestricted concrete injectivity claim is valid. A local finite-set assumption and refinement relation are required. |
| HypZ | Real KZG `BlobToCommitment` on 131072 zero bytes, then `CalcBlobHashV1`: **010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014**, equal to Morph's constant. | Tested, nonempty sidecar representative exists. Public commitment equality also reproduced. |
| Submitter active/slash/deposit | Real proxied `Submitter`: initialize `(minimumStake=1, deposit=1, reward%=70)`, owner add, stake 2, active=true; slash returns 1 and active=false; slash(0)=0. | Restricted projection holds; stand-in omits stake/withdraw/admin/reward behavior and is not the full neighbor. |
| Verifier `proof==1` | Real `ZkEvmVerifierV1` rejects one-byte `01`; stand-in accepts. | Model hypothesis satisfiable but not this concrete proof's behavior. A real circuit proof for the trace remains untested/unavailable. |
| Messenger appends | `Q:288-301,366-380` writes queue and timestamp; actual public messenger checks pause, fees/value, gas and duplicate message (`L1CrossDomainMessenger.sol:102-119,275-306`). | Reachable via an appropriately funded/unpaused messenger call, but not an unconditional action of any `who`; built-in replay impersonates messenger. No full messenger replay performed here. |
| Go growth | Go 1.24.13 table/`nextslicecap`/rounding read; small alias witness native pass; 513-byte probe cap=576. | ≤512-table region supported; fallback contradicted outside it, R6. |
| Legacy migration antecedent | Pinned `initialize2` conditional write matches, but version lifecycle/nonzero root absent and old state is injected. | Model inhabitant exists; production historical inhabitant not supplied. R5. |
| Nat times/indices/roots; fixed F/W/D, actors | Initial state is a possible post-genesis deployment (native public setup below). Solidity widths/checked overflow and parameter/admin changes are not fully modeled. | Explicit environment restriction is necessary; arbitrary-Nat proofs are not unconditional production proofs. |

## Facts audit — citation, guard and write coverage

The inventory is **7 M0 functions**, **22 Rollup state fields / 8 definitions / 10 actions / 2 migrations / 5 observers**, and **8 heap-state fields / 2 actions / 1 observer**. Rollup actions contain **127 guard entries** (including let-bindings) and **42 effect assignments**; heap actions contain 7 guard entries and 7 effect assignments. All were traced to the source regions below or identified as model scaffolding. Rollup JSON contains 112 `src` strings (including duplicate citations and oracle/environment labels); heap JSON contains 7. M0's `src` keys on operations are operands, **not source citations**: its source provenance is `source[].file/fn/bundle_lines`. Bundle-line numbers are intentionally not real-repo line numbers.

Legend: **M** matches within stated representation; **I** incomplete; **O** over-approximation/specialization; **C** contradicted; **D** declared debt. An M is not a claim that omitted behavior is proved irrelevant.

### M0: every function and field operation

| Facts item | Actual pinned source | Result |
|---|---|---|
| `enc_sol` allocation, version/length | `R:293,332-359`; codec V0 length 249, V1 length 257 | M; roots/count widths are public-path restrictions, not codec-only guards. |
| `enc_sol` stores at 0,1,9,17,25,57,89,121,153,185,217 | `BatchHeaderCodecV0.sol:133,144,155,166,175,184,193,202,211,220,229`; caller `R:343-355` | M; overlapping uint64 stores must precede later fields. Ssvh input is deliberately ignored and replaced by zero. |
| Conditional last block at 249 | `R:357-359`; `BatchHeaderCodecV1.sol:54-56` | M, version ≥1. |
| `enc_go_v0` allocation/cache/all 11 field writes | `common/batch/batch_header.go:212-229` | M in empty-cache domain; fixed version 0, BE uint64 and 32-byte copies agree. |
| `enc_go_v1` allocation/cache/all 12 field writes | `batch_header.go:240-258` | M for this helper; C for old audit's “no V2 encoder” inference, R1. |
| `ok_sol`: empty, v0, v1/v2, other | `R:824-846`; V0 codec `:30-32`; V1 codec `:33-35` | M: nonempty; ≥249 for v0; exactly 257 for v1/2; other version rejected. |
| `ok_go`: all versions/lengths | `batch_header.go:37-58,72-76` | M: exact lengths, no v0 padding. `Version()` alone checks nonempty, not validity. |
| `dec_go`: version/index/l1/total/data | `batch_header.go:72-104` | M at 0/[1:9]/[9:17]/[17:25]/[25:57]; getters validate before slicing. |
| `dec_go`: blob/prev/post/withdraw/ssvh/parent/last | `batch_header.go:111-192` | M at offsets 57/89/121/153/185/217/249; `BlobCommitHash` dispatch is correct; last block unavailable for v0. |
| `view` | Model projection of those fields | M by definition; omits last block for v0. Not an additional source entry point. |

### M1 Rollup: every action, guard group and effect group

Common modifiers were checked in real source: active submitter `R:119-120`, challenger `:125-126`, pending-revert `:131-132`, OpenZeppelin OwnableUpgradeable `:56` and PausableUpgradeable `:77,94,106`. Their facts match within the selected actor/oracle model. Honest-header specialization removes byte/hash authentication as an input dimension; it does not validate arbitrary calldata.

| Facts action (guard/effect counts) | Guards/citations checked | Writes checked / verdict |
|---|---|---|
| `commitBatch` (25/5), facts beginning `:768` | `R:255-269`: modifiers, stored BVH zero, delayed-queue inclusion; common helper `:293-316`: version, roots, fresh next index, parent LCI, previous CSR, total; `Q:108` range; blobs `R:888-918`; arithmetic `:360-364`. | Window entry CB/header/CSR/BVH/BD, shadow-list consumption and LCI abstraction match `R:343-374` (**M/O**). Header hash check at 313 is specialized away. uint16/uint64 ABI bounds and general uint256 overflows not encoded. |
| `commitState` (24/5) | `R:273-286`: same modifiers, no new blob, stored BVH nonzero, delayed-queue check; same common helper ranges and queue bound. | Reuses stored BVH, overwrites header/CSR/BD, preserves provenance tag of old BVH (**M**); that preserved tag exposes the cross-version obstruction. |
| `commitBatchWithProof` (31/5) | `R:382-426`: pause/revert request, rollup delay 389-390, queue delay 393-395, conditional message inclusion 397-399, timing 400, stored BVH 403/406, compute-blob fallback, common helper; proof nonempty `:758` and verifier oracle. | Normal commit writes then finalization timestamp=t (`:421`) (**M/O**). Honest new-header checks `:416-418` omitted from input language; proof oracle **I**, R3. No active-submitter requirement here: model correctly omits it. |
| `revertBatch` (8/8) | `R:430-466`: owner, count>0, authenticated index specialization, end-of-chain count condition, index>LFI. | Clears CB/challenges, reduces LCI, clears relevant challenge/revert request; retained CSR/BD/BVH/tag become shadows (**M**). Accounting excluded (**D**), storage loops/gas not modeled. |
| `challengeState` (11/4) | `R:471-496`: challenger/pause/revert request, no current challenge, index existence/not already challenged, window, deposit. | Creates challenge, sets batchChallenged/inChallenge, increments other unfinalized timestamps by W (**M**). Generator `b_bump_go` skips window position 0=LFI and the challenged index, matching source loop. |
| `proveState` (10/4) | `R:595-622`: revert/pause/active, header, open challenge, timeout (`start+W≤t`), nonempty proof and verifier only before timeout. | Finished/win flag, inChallenge false, revert request and active-set removal on timeout (**M/O**); real slash `Submitter.sol:146-159`, accounting in `R:791-807` debt. Successful-proof path limited by R3. |
| `finalizeBatch` (15/5) | `R:625-643`: authenticated header, stored batch, no challenge/success, outside window, prior root, current root absent, next finalized index; queue cursor `Q:325`. | LFI/finalized root, queue pop, deletes previous CSR/BD/BVH/challenge `R:651-660` represented by window shift (**M**); withdrawalRoots write omitted (**D**). Queue's count≤256 is enforced by Rollup's chunked pop helper, not a missing top-level model guard. |
| `setPause` (3/3) | `R:573-588`; owner and OZ pause/unpause domains. | Pause flag; if pausing an open challenge, clear it/inChallenge but not other batches' extended deadlines (**M**). Reward credit deliberately omitted (**D**). |
| `sendMessage` (0/2) | `Q:288-301,366-380` | Queue length and enqueue timestamp writes **M**; no permissions, fee, gas or messenger-state guards **I/O**, not a full public messenger transition. |
| `wait` (0/1) | Environment label, not a Solidity function | Monotone t increment **M** for elapsed time; does not model bounds, gas or other transactions. |

Additional definition/migration/state audit:

* `lci`, `in_win`, `w`, `bvh_at`, `tag_at` implement the window/shadow indexing abstraction, not five missing source functions. State writes preserve the intended normal initialized contiguous-chain representation. `enq_first` matches `Q:261-268`, including current-time fallback for empty/zero-timestamp queue. `open_ch` expression matches `R:691-693` but its citation is stale (R7). `blob_hash` matches `R:888-918` for valid contiguous EIP-4844 blob-hash lists; arbitrary Nat lists/holes are an over-approximation.
* `legacy` is an uncited hypothetical history transformation, not an available public action. `eta2` conditional CSR write matches `R:192-194`; its **guards do not**, R5. Initialization/version state is absent. The fixed initial state is a possible deployment, not all reachable deployments/upgrades.
* `lci_of`, `csr_last`, `kappa`, `tags_ok`, `new_hdr` are model projections/invariants. Ghost tags are not on-chain stored tags, and `new_hdr` abstracts commitment equality. Raw storage getters, balances, events and downstream consumer semantics are not all observations of this machine.
* Queue `tot+n≤qlen` is a derived bound for positive n, not verbatim source. `_loadL1MessageHashes` returns immediately at n=0 (`R:930-932`); under normal initial `tot≤qlen` the extra bound is redundant. It is not valid for all possible `importGenesisBatch` inputs: `R:225-248` does not check total-popped against queue length. Genesis input coverage is explicitly debt, so do not promote the fixed-s0 proof to all public initializations.
* Coverage debt in facts is real: genesis/initialize/initialize3/4, parameter/challenger/verifier updates, reward claims/accounting, withdrawal roots, dataHash content and the proof-status view are excluded. Register ownership and permissionless-only DISCH conclusions cannot silently quantify over these missing actions.

### M1 heap: every cited operation

| Facts item | Real source | Result |
|---|---|---|
| Initial empty slices | `common/batch/batch_data.go:23-29` | M for nonnil `NewBatchData`; nil receiver behavior is outside this initial domain. |
| Append (4 let/guard entries, 3 effects) | `batch_data.go:31-43`, repeated citations to `:35,36` | Both slice headers/backing writes correctly distinguish in-place append from growth in the supported oracle region. Nil receiver check, block/l1 counters and l1 hash append omitted (**D/O**). |
| TxsPayloadV2 (3 let/guard entries, 4 effects) | `batch_data.go:117-120`, append at `:119` | Returned slice can share context backing; context slice header is not updated; heap/view/snapshot/liveness state matches this behavior (**M**). Snapshot/liveness are observer instrumentation. |
| Growth and view observer | Go 1.24 `runtime/slice.go`, `msize.go`, `sizeclasses.go:95` | Correct small-size oracle premise; larger-size fallback **C**, R6. `view_intact` compares live returned bytes with snapshot, not arbitrary ownership safety. |

No additional wrong offset/store/guard order was found inside these represented domains. Agreement of those entries is not a proof of complete extraction: the table's I/O/D items and R1–R7 remain material qualifications.

## §9.6 — every refutation through the finding filter

Built-in replay was rerun, then independent tests replaced the submitter stand-in with the real proxied `Submitter`, registered/staked the actor through public calls, and initialized/imported genesis through public Rollup calls. For the no-proof traces the installed real verifier was never invoked. Actor selection, time and EVM blob context used test-environment facilities; **no storage mutation** was used in these independent public-call tests. Blob token 17 was concretized to the realizable zero-blob hash Z where only nonzero/equality mattered. This renaming preserves the tested guards; it does not establish arbitrary synthetic hashes are realizable sidecars. These are local native public-call schedules, not forked transactions or mainnet deployment evidence.

| Refuted law | Reachability/concretization and classification |
|---|---|
| M0 `L_par_hdr_v2` | Low-level helper mismatch only; production version rewrite defeats the asserted protocol divergence. **Model defect (path selection)**, R1. |
| M0 `L_par_hdr_ssvh` | Fresh exported Go struct with nonzero ssvh reproduces the helper mismatch. Current `BatchCache.createBatchHeader` passes zero (`batch_cache.go:1680-1681`). **Known limitation / intent question** until a relevant producer supplies nonzero. Existing triage is appropriately cautious. |
| M0 `L_dom_hdr` | Exact all-zero witness is loader-level, not valid genesis. Independently constructed a valid v0 genesis header with one extra byte; public owner `importGenesisBatch` accepted length 250, and Go exact-length validator rejects that length. **Finding: public validation-domain mismatch**, with an explicit nonzero-root/data/Z concretization. No downstream exploit claimed. |
| M1 `L_undo_BVH` | Public commit(i,Z), owner revert(i), recommit fails `commitBatch requires no stored blob hash`; the baseline fresh commit succeeds. **Finding**, owner/revert prerequisite. |
| M1 `L_undo_cancel` | Two commits, allowed challenge(1), owner pause/unpause, wait F=40; challenge(2) still succeeds due to retained +W. Built-in paired baseline fails outside window. **Finding**, owner pause prerequisite. |
| M1 `L_sort_remaining` | Commit, allowed challenge, wait W+1, active-submitter commit next batch: native panic **0x11**. **Finding**, temporary obstruction until an authorized discharge; not an assertion of permanent lock. |
| M1 `L_tag_BVH` | Commit v1 with realizable single-blob Z, owner revert, public commitState v2 without new blobs succeeds and retains Z. **Finding: cross-sort reuse** under a protocol version meaning, with owner prerequisite. The ghost tag is not itself an on-chain observable or proof of downstream economic loss. |
| M1 `L_fact_Z` | Two fresh public deployments with identical state/arguments, one no-sidecar and one zero-blob context: same CB hash **e13873b91d31ecbf0b874275ae775630b1b0e21388a824914f8f063a2c4c36fe**. Real KZG oracle supplies Z. **Finding: nonbinding of sidecar presence**; actual derivation/output harm remains **Known limitation**, since `blobs_of` is not the production consumer. |
| M1 `L_sym_omega` | Both successful orderings/continuations require proof token 1 accepted by stub. Real proof bytes rejected. **Known limitation / conditional candidate**, not presently a production finding. This does not refute the ordering mechanism if valid proofs are supplied. |
| M1 `L_nat_eta2` | CSR-erasing storage cheatcode supplies historical precondition. **Known limitation / historical candidate**, R5; not a reachable public-only trace at this pinned implementation. |
| M1 `L_own_txspayload` | Exported Go `NewBatchData→Append→Append→TxsPayloadV2→Append` changes held view (first difference 68). **Finding at Go API boundary, conditional on holding the slice.** Production callers `batch_cache.go:1581` and `node/derivation/verify_local.go:186` consume it immediately; no production held-across-Append path demonstrated. |

The successful native tests above establish public API reachability for the stated initialization/permissions, not legitimacy of every parameter under off-chain operational policy. In particular, owner-dependent traces must retain that label. Native blob opcodes were populated with a hash whose KZG preimage was independently constructed; broadcasting and consensus sidecar validation were not exercised.

## Reproduction and validation

`tools/setup_env.sh --replay` installed the pinned Bend/Lean and replay toolchain. The VM default Python 3.10 cannot parse M1's nested f-string in `holon/gen/mproofs.py:331`; Python **3.12.13** was used instead. Node **24.19.0**, Bend **2.0.36**, Lean **4.34.0**, Go **1.24.13**, solc **0.8.24**, and installed Foundry were used. This is a setup/documentation discrepancy (`requirements-dev.txt` says Python 3.10+), not an audit fix.

Commands run from the isolated copy with those tools on PATH:

```sh
python -m holon run --milestone M0
python -m holon gate --milestone M0
python -m holon run --milestone M1
python -m holon gate --milestone M1
python -m holon replay --milestone M0 --morph <pinned-morph> --solc <solc-0.8.24> --work <scratch-M0>
python -m holon replay --milestone M1 --morph <pinned-morph> --solc <solc-0.8.24> --work <scratch-M1> --corpus 300
python -m unittest discover -s tests -t . -v
python -m unittest discover -s tests_m1 -t . -v
HOLON_REPLAY=1 python -m unittest tests.test_50_replay -v
HOLON_REPLAY=1 python -m unittest tests_m1.test_m1_replay -v
python -m compileall -q holon
python tools/freeze.py check
```

| Check | Observed result |
|---|---|
| M0 run/gate | 5 P / 3 R; all 8 proofs rechecked in Bend and BendTT; 17 generated files identical; 16 canaries rejected. |
| M1 run/gate | 8 P / 8 R; all 16 proofs rechecked in both kernels; 34 generated files identical; 21 canaries rejected. |
| M0 native replay | Three Go witnesses passed; domain Solidity loader passed; two codec Solidity entries `not_applicable`, **not** full two-path replay. |
| M1 native replay | All 8 built-in witnesses passed **under harness assumptions**; 300 traces, 2432 steps, 0 model/harness disagreements. |
| M0 suite | `Ran 38 tests in 151.546s` / `OK (skipped=1)`; optional replay test rerun separately with flag. |
| M1 suite | `Ran 13 tests in 415.889s` / `OK (skipped=1)`; optional replay test rerun separately with flag. |
| Optional replay tests | Separate M0 and M1 report-validation tests run with `HOLON_REPLAY=1`; these validate report content, not fresh native execution (the replay commands above do that). |
| Independent oracle tests | Go: production V2 rewrite, real zero-blob KZG hash, and 513-byte growth mismatch, 3 passed. Foundry: real verifier rejection and real Submitter projection, 2 passed. |
| Independent public-call tests | Four Foundry tests passed: padded genesis; arithmetic/cancellation schedules; BVH undo/tag schedules; zero-blob commitment equality. |
| Integrity | `FROZEN OK`; Python compile check passed; no configured lint/type-check command or active pre-commit hook found. Docs-only change, no runtime implementation edited. |

Minimal independent probes (run in scratch, not added under frozen tests):

```go
// In package batch against the pinned real common module:
bc := &BatchCache{
    isBatchUpgraded: func(uint64) bool { return true },
    isBatchV2Upgraded: func(uint64) bool { return true },
}
h := bc.createBatchHeader(common.Hash{}, nil, 0)
// len(h)==257, h[0]==2, h.validate()==nil.
var z kzg4844.Blob
c, err := kzg4844.BlobToCommitment(&z) // err == nil
zh := kzg4844.CalcBlobHashV1(sha256.New(), &c)
// common.Hash(zh) == blob.EmptyVersionedHash.
s := append([]byte{}, make([]byte, 513)...)
// cap(s)==576 on the tested Go runtime.
```

```python
# In isolated HOLON, demonstrate the G11 boundary, not a whole-gate attack:
g = Gate('M1', Path.cwd())
records = g.records()
for rec in records.values():
    rec['premises'] = ['False = True']
    rec.pop('inhabitants', None)
g.records = lambda: records
g.g11()
assert g.checks['G11']['passed']  # No premise evidence inspected.
```

Independent public schedules use F=40, W=10, D=20, t=epoch+10, root=100, owner=this test, submitter=0x1002, challenger=0x1004; normal proxy initialization, Submitter owner-add/stake, challenger-add and genesis-import precede every trace. Header generation uses real field widths and checks `keccak(header)==committedBatches(index)` after successful commits. The verifier rejection test was initially over-specific about revert data; real code returned an empty revert, so the final test asserts rejection rather than misreporting a panic code. None of these probes was used to alter a generated proof or prediction.

## Questions for the human / proposed ownership decisions

No response is needed to publish this audit; these are follow-up decisions, not blockers to this docs-only PR.

1. **Spec/freeze owner:** approve a proposal correcting the V2 production-path claim and stale `open_ch` citation; keep the original helper theorem/result as historical evidence.
2. **Gate/IR owner:** prioritize actual G11 inhabitants and a structured hypothesis/refinement ledger before using green gates as trust signals. Require public-path evidence for promotion to finding.
3. **DISCH owner:** choose the weaker, accurately named example-point deliverable now; preregister full principal-strategy/profile minimality as separate work.
4. **Replay/migration owner:** require real proof fixtures and historical upgrade provenance; do not remove uncertainty labels on SYM/NAT solely because the current harness passes.

## Not done / residual limits

* No deployed-chain/fork replay, historical implementation reconstruction, real ZK proof production, consensus-sidecar broadcast, or end-to-end L2 consumer impact demonstration. Those omissions are why conditional items remain conditional.
* No proof that any cryptographic premise holds for all future inputs; the checks are finite and the model is not the real hash/verifier.
* No full messenger fee/gas/accounting replay, no completion of declared admin/accounting/genesis/parameter coverage debt, and no ABI/overflow-complete refinement of unbounded Nat.
* No generator/fact/law/test fixes, freeze rewrite, or merge. Audit-only probes remain outside the repository; commands, key inputs, observed results and source locations are documented here.
