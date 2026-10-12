# Round 2 independent audit: M2 and M3 (PR #23)

## Verdict and boundary

**The M3 checked results reproduce, the four replays are genuine public-entry-point runs on the pinned contracts, and the M2 adequacy numbers are reported honestly. But the M3 "findings" (O13, O14, O29, O34) are not findings under the factory's own rules yet: they are PROVED closed scenario laws, so they never pass through G6, their result records say `replay: not_run` and `triage: none`, and two of the four rest on effects that were typed into the frontend spec rather than extracted. M3_SPEC decision 1 ("no hand-written facts in M3") is not met in substance.**

- Audited revision: `0820d64` (head of `devin/1791781240-m3-e2-bundle` when the audit started; PR #23 → `devin/holon-v2`). The branch later gained `2313c8b` and `5c41bce` (E3 index-bounds partiality, F3 Go replay); those were read as diffs only, see "Not done".
- Preregistration commits compared: `f750a6d` (M3_msg, M3_router), `7c54877` (M3_nat).
- Morph pinned at `3e44e795586af3e11285b603ab642c67823add51` (`~/.holon/morph`, verified with `git log -1`). Morph line numbers below are from that checkout. `R` = `contracts/contracts/l1/rollup/Rollup.sol`, `CDM` = `contracts/contracts/l1/L1CrossDomainMessenger.sol`, `MVRV` = `contracts/contracts/l1/rollup/MultipleVersionRollupVerifier.sol`, `SUB` = `contracts/contracts/l1/rollup/Submitter.sol`.
- Read: `docs/audit/round1.md`, `AGENTS.md`, `docs/M2_SPEC.md`, `docs/M2_A2_SPEC.md`, `docs/M2_A3_SPEC.md`, `docs/M3_SPEC.md`, whitepaper §9.6, §10.9, §11.3, §11.8, Appendix A rows F8/F10/F14, PR #23 description.
- Nothing was pushed. All reruns and probes happened in a detached `git worktree` at `~/audit_r2/work`; the repo checkout is untouched (`git status` clean after every gate).
- "Verified" below means I ran the command or read the cited lines. "Inference" is marked as such.

Severity is severity to HOLON's assurance claims, not Morph bounty severity.

## Ranked findings

### F1 — High: "PROVED is the finding" bypasses the finding filter; the M3_msg/M3_router/M3_nat gates run without G6/G8/G9

**Verified.**
- The law generators state the inversion explicitly: `spec/M3/laws_src/e2_laws.py:3-4` ("for the O29 and O34 laws a PROVED result IS the finding") and `spec/M3/laws_src/e2c_nat_laws.py:3-4` ("for those two PROVED is the finding"). Every M3 law is `"predicted": "PROVED"`; all 36 came out PROVED (`results/M3_*/summary.json`).
- The factory's finding rule is REFUTED + witness replay: whitepaper §9.6 (`whitepaper.md:899-905`), §10.9 step 3 (`:1019`), G6 (`:873`), and `docs/M3_SPEC.md:28` ("A REFUTED law counts as a finding only if its witness replays through public entry points (G6)"). A PROVED law has no witness, so nothing binds the replay to it.
- Consequence in the records: `results/M3_nat/L_nat_slash_legacy_misses.json` and `results/M3_msg/L_msg_budget_exhausts.json` carry `"triage": "none"`, `"replay": {"status": "not_run", "detail": "certificates are not replayed; refinement replay corpus in replay/M1"}` and `"scope": "unbounded"` for a closed trace with no binders. The boilerplate comes from `holon/mpipeline.py:311` (replay detail) and `:286` (scope). `config/triage.json` has keys `M0`, `M1` only.
- The gates for these milestones are the M0-style list: `holon/gate_records.py:48` `RECORD_GATE_MILESTONES = ("M1", "M3_sorts")`, so `Gate._order()` (`holon/gate.py:363-365`) gives `GENV,G2,G1,G3,G5,G11,G7,G4` for M3_msg/M3_router/M3_nat. My rerun log (`gate_M3_msg.log`) shows exactly those eight checks; no G6, G8 or G9. `docs/M3_SPEC.md:63-68` promises coverage-debt accounting, G6 and G11 for the M3 gate.
- `replay/M3/msg_report.json` and `nat_report.json` exist and are consistent (see §3), but no gate, record or registry references them; `tests_m3/test_m3_replay.py` compares the committed JSON against a fresh forge run, which is the only binding.

**Inference.** The PR description's "AGREE" for O13/O14/O29/O34 is a correct description of the forge output, but under the whitepaper's vocabulary these items are currently "model statements with a matching native test", not G6-bound findings. The blind-rerun comparison (`docs/M3_COMPARISON.md`) will have no record-level field to read for them.

**Remediation.** (a) Add M3_msg/M3_router/M3_nat to `RECORD_GATE_MILESTONES` and make G6 bind PROVED scenario laws whose notes/predictions mark them as findings: require `replay/M3/*_report.json[laws][lid]` with a sha256 of the law statement (not a witness) and verdict `agree`. (b) Stop writing M1 boilerplate into M3 records: `scope` should be `closed` for binder-free laws; `replay` should resolve from the M3 reports. (c) Extend `config/triage.json` with M3 entries so the finding/limitation label is in the record. (d) Alternatively, restate each finding as a REFUTED relational law (the U2 proposals already phrase them that way: `spec/M3/proposals/predictions.json` predicts `L_nat_cutover_slash`, `L_nat_cutover_defend`, `L_sort_payer_replay` and `L_dom_router` as REFUTED) so the existing G6 machinery applies.

### F2 — High: the NAT cutover findings rest on spec-written effects, and `L_nat_slash_legacy_misses` is vacuous on its facts

**Verified.**
- `initialize4`'s only finding-relevant effect is hand-written. `holon/frontends/solidity/specs/morph_rollup_m3.spec.json` key `storage_on_write.submitterContract` = `{"effects":[{"field":"active","expr":"nact"}], "add_inputs":[["nact","List<Nat>"]]}`. The extracted facts record it: `spec/M3/extracted/morph_rollup.json` `provenance["actions.initialize4.effects"] == "spec"`, and `spec/M3/coverage/morph_rollup_m3.json` lists `action:initialize4.effects.active` and `R:218 write submitterContract` as `spec_bound`. The real line `R:218` writes an address; nothing in the AST says what the new registry contains. The disclosure is honest; the substance is a hand fact.
- The slash effect is also a spec rule: `morph_rollup_m3.spec.json` `oracles["ISubmitter.slash"].effects = [{"field":"active","expr":["call","remove","@a0","active"]}]`. It surfaces in `proveState.effects.active = ["?", timeout, remove(bds, active), active]`. **Provenance mislabel:** `provenance["actions.proveState.effects"] == "ast"`, and the coverage item for `R:806` is `unmodelled_value` with the text "slash's active-set effect IS modelled"; there is no `spec_bound` item for it. The same spec rule is, in fact, the whole content of O14 in the model.
- `reinitializer(4)` is abstracted (`modifiers_abstracted` in the spec; coverage `action:initialize4.modifier:reinitializer abstracted_modifier`). The model therefore admits repeated cutovers. Probe `L_aud_i4_twice_ok` (below) is PROVED: `initialize4(who=6,sub=9,exp=1,nact=[7])` succeeds a second time from the post-cutover state. The real function can run once (`R:209`).
- `initialize4` is also listed in the spec's `abstracted_fns` while being emitted as an action; the action wins, but the spec is self-contradictory.
- Vacuity of `L_nat_slash_legacy_misses` (`laws/M3_nat/L_nat_slash_legacy_misses.json`): the claim is `active_has(7) == true` after `XCW + [proveState(1, who=7)]`. In the facts, the only remover from `active` is `remove(bds, active)` where `bds` is the committer of the challenged batch (2), so 7 can only leave `active` if 7 committed the batch. I ran the same observation with the probe removed: `L_aud_active7_without_probe` (`active_has(7)` after `XCW`) is PROVED, and `L_aud_active2_after_cutover` (`active_has(2) == false` right after `initialize4`) is PROVED. So the law is true before the slash happens, and the "legacy committer is not in the registry" fact is the `nact=[7]` input, not anything the slash does. The paired law `L_nat_slash_native_hits` (`active_has(7)==false` when 7 is `bds`) is the only one of the pair that exercises the slash effect, and that effect is the spec rule above. The setup law `L_setup_nat_slash_legacy_misses` does guarantee the `proveState` step ran ok, so the trace is non-vacuous as a trace; the *claim* is not sensitive to it.
- `L_nat_defend_legacy_blocked` reduces to `mem(2, active)` failing after `active := [7]`. The guard `mem(who, active)` at `R:120` is AST-extracted (`provenance["actions.proveState.guards"]=="ast"`), the value of `active` is the hand input.
- The Rollup side of the facts checks out against source: `initialize4` guards at `R:210-214` match (`who == PADMIN`, `sub != 0` for `code.length > 0`, `lci == exp`, `!inch`, `rri == 0`), `lcb := exp` at `R:216` is AST (`provenance` `ast` for guards/entry). `_challengerWin` at `R:803-809` calls `ISubmitter(submitterContract).slash(submitter)`; `SUB:147-161` zeroes `registered`/`stakeOf` and returns `amount*rewardPercentage/100`, so for an address never registered there it returns 0 without reverting. The native replay confirms this (§3).

**Inference.** O13 and O14 are real behaviours of the pinned code (the forge run shows them), but the model did not discover them; the model was told them through `storage_on_write` and the oracle rule, and the laws read the inputs back. Under M3_SPEC decision 1 these should be coverage debt with the laws predicted UNKNOWN, or the registry swap should be an explicit assume-guarantee premise (`assume: active' == new_registry.active_of`) rather than an action effect, with the Submitter machine (`spec/M3/extracted/submitter.json`, extracted with 36 `ast` sections and an `active_of` observer) linked in as the oracle.

**Remediation.** (a) Fix the provenance writer so an effect produced by an `oracles.*.effects` or `storage_on_write` rule is `spec`, and add `spec_bound` coverage items for `proveState.effects.active`. (b) Either link the extracted Submitter machine for `isActive`/`slash` (its `slash` action at `SUB:147-161` is already extracted with `reg := remove(sub, reg)`), or state the registry swap as a premise. (c) Replace the `active_has(7)` claim with one that observes the slash: e.g. an observer over the slash oracle's argument (`slashed == bds ∧ ¬mem(bds, active_before)`), or `active` unchanged across the probe. (d) Model `reinitializer(4)` as a one-shot guard (a `init_ver` register), or record it as debt and add a law that the model's second cutover is unreachable natively.

### F3 — Medium: the router laws prove a hand-typed definition, `L_rt_before_start` certifies a known divergence as PROVED, and O3/F14 itself is not mechanized

**Verified.**
- `holon/frontends/solidity/specs/mvrv.spec.json` `defs_from.get_verifier` has `"body_forced": true` with a literal body `lv[v].s <= idx ? lv[v].a : lv_le(lvv[v], idx)`. `spec/M3/extracted/mvrv.json` `defs.get_verifier.src == null`, `provenance["defs.get_verifier"] == "spec"`, coverage item `defs.get_verifier.body spec_bound`. The `verifier_of` observer that all seven `L_rt_*` laws read is this body. The body does match `MVRV:98-120` for the found cases (`b_lv_le` in `holon/gen/machine.py:522-530` returns the last element with `s <= idx`, which equals the backward scan's first hit because `legacyVerifiers` is pushed in increasing `startBatchIndex`), but the laws are checking the spec author's transcription, not the AST.
- Not-found: `MVRV:118` `revert ErrorVerifierNotFound()`; the model returns 0 (`b_lv_le` default `0n`). `laws/M3_router/L_rt_before_start.json` asserts `verifier_of(0, 9) == 0` after `updateVerifier(0,10,3,5)` and is PROVED; its note says "(source reverts; model 0 = debt)". The model is therefore kernel-certified to disagree with the source on this input, and `L_rt_unregistered_zero` (`verifier_of(1,100) == 0`, which *does* match `MVRV:101-120`: zero struct, `0 > 100` false, returns `address(0)`) is indistinguishable from it inside the model. `spec/M3/coverage/mvrv.json` has no item naming the revert→0 divergence; the only getVerifier item says "backward linear scan with break; modelled by b_lv_le builtin".
- O3/F14 (`whitepaper.md:1072`, `:1393`: "Commit admits (version, index) outside the router's domain") is a Rollup-level liveness claim. The U2 proposal `L_dom_router` (`spec/M3/proposals/predictions.json`) predicts REFUTED with a commitBatch→challengeState→proveState witness. No M3 law touches `commitBatch` or `proveState` with a router; `laws/M3_router/*` quantify over `MVRV` alone. The law notes and PR text label `rt_unregistered_zero` as "O3/F14".

**Remediation.** (a) Extract `getVerifier` from the AST (it is a single `if` plus a bounded loop; the translator already handles `for` loops via `h_bump_loop`, `holon/frontends/solidity/translate.py:1247-1252`, and could gain a generic last-match reducer), or keep `body_forced` but emit the not-found case as an explicit `Unsupported`/`reason` so a law over it comes out UNKNOWN instead of PROVED. (b) Add a coverage item "`MVRV:118` revert ErrorVerifierNotFound modelled as 0" with kind `unmodelled_revert`. (c) Re-label `L_rt_*` as router *unit* laws and keep "O3/F14" for a law that links the Rollup `proveState` oracle to the router machine, as the U2 proposal states.

### F4 — Medium: messenger extraction fidelity defect that is not in coverage debt (`_nextQueueIndex` collapsed onto `mn`, `qi` is a dead input)

**Verified.**
- `holon/frontends/solidity/specs/l1messenger.spec.json` `oracles["IL1MessageQueue.nextCrossDomainMessageIndex"] = {"emit": "mn", "add_inputs": ["mn"]}`. That is right for `_sendMessage` (`CDM:286` assigns the result to `_messageNonce`) and wrong for `replayMessage` (`CDM:208` assigns it to `_nextQueueIndex`).
- Result in `spec/M3/extracted/l1messenger.json` action `replayMessage`: inputs include `qi` (declared via `members["_nextQueueIndex"] = "qi"`) but `qi` occurs nowhere in guards or effects (1 occurrence in the action JSON, the input list). The effects are `mrt[xh].li := mn` and `pri[mn] := …`, whereas the source writes `prevReplayIndex[_nextQueueIndex]` (`CDM:218-220`) and `_replayState.lastIndex = uint128(_nextQueueIndex)` (`CDM:223`). Because every preregistered law passes `mn=0`, the replay chain in the model is `lastIndex := 0` on every replay and the `lastIndex != 0` branch is dead.
- `spec/M3/coverage/l1messenger.json` has no item for this; `provenance["actions.replayMessage.effects"] == "ast"`.
- Probe `L_aud_msg_budget_qi_dead` (budget law with `qi=0` on every step) is PROVED, confirming `qi` is inert.
- This does not affect the O34 laws: the budget guard `tm < maxr` (`CDM:226`) and `tm := tm + 1` are extracted correctly and `times_of(11) == 3` after three replays is PROVED (probe `L_aud_msg_times3`).

**Remediation.** Key oracle emits by the assignment target or the enclosing function (the spec already has `members` per action; let `oracles.*.emit` accept a per-action override), re-extract, and add a differ test that every declared input is read by at least one guard or effect. Until then, add a coverage item for `CDM:208,218-223`.

### F5 — Medium: preregistration drift: laws committed against facts that could not run them, hashes rebound after the fact, predictions outside the frozen place and unchecked by any gate

**Verified.**
- At `f750a6d` the 12 M3_msg laws use a `wait` action; `spec/M3/extracted/l1messenger.json` at that commit has no `wait` action (`git diff f750a6d 90b7565 -- spec/M3/extracted/l1messenger.json` adds it). The generator's own guard was written to pass anyway: `spec/M3/laws_src/e2_laws.py:67` builds `names = {…actions…} | {"wait"}`. `90b7565` then changed the facts and rewrote `facts_sha256` in all 12 laws (`git diff f750a6d 90b7565 --stat`: 4 lines per law, the sha line plus a trailing newline). `ir.statement_hash` hashes `facts_sha256`, so every M3_msg statement hash in `laws/M3_msg/REGISTRY.json` postdates the preregistration. I confirmed the statement payloads are byte-identical to `f750a6d` (only the sha line differs), so the predictions were not moved; but "preregistered before any run" is true only of the statement text, not of the law+facts pair that was actually checked.
- M3_nat is clean: facts `95f00c7` (06:35) precede laws `7c54877` (06:36) precede the run `9096780` (06:39); `git diff 7c54877 HEAD -- laws/M3_nat` touches only `REGISTRY.json`.
- Predictions: `docs/M3_SPEC.md:19` requires `predictions/M3.json`; `predictions/` is a frozen root (`tools/freeze.py:19-26`) and contains only `M0.json`, `M0_mutations.json`. The M3 predictions live as a `"predicted"` key inside each law file. No code reads it: `grep -rn predicted holon/` returns nothing, so no gate would notice a prediction miss.
- The U2 proposal ids and shapes (`L_nat_cutover_slash` REFUTED, `L_sort_payer_replay` REFUTED, `L_dom_router` REFUTED, `L_disch_replay_budget` PROVED invariant) were replaced by closed scenario laws predicted PROVED. Nothing in the repo maps proposal → mechanized law, so a §11.8/Appendix-A comparison cannot be computed from the files.
- Registry integrity (manual G9, since the gate does not run it): I recomputed `ir.statement_hash` for all 36 M3 laws; each matches `laws/<ms>/REGISTRY.json["statements"]` and `results/<ms>/<lid>.json["statement_hash"]`, and `facts_sha256` matches the on-disk facts for all three milestones.

**Remediation.** Pin the facts sha in the preregistration commit by running the generator against the final facts first (the generator asserts action names; let it fail on `wait`); when a facts amendment is unavoidable, record it as an erratum with before/after shas in the law `notes`. Put M3 predictions in an unfrozen but hash-recorded file (`spec/M3/predictions.json` with its sha in `docs/M3_SPEC.md`), add a gate check `predicted == status` that reports misses, and add a `proposal_id` field to each mechanized law.

### F6 — Medium: duplicate/weak scenario laws in M3_msg (`who` is not read by `replayMessage`)

**Verified.** `L_msg_budget_blocks_sender` differs from `L_msg_budget_exhausts` only in `who` (5 vs 6) on the probe. No `replayMessage` guard or effect mentions `who` (guards at `CDM:193,195,198,201,213,226,238` as extracted). Probe `L_aud_msg_budget_sender_who_irrelevant` (sender replays all three times, then once more) is PROVED. The "original sender has no exit" claim (`e2_laws.py:34`) is carried by the facts-level fact that nothing writes `dr` (`l1messenger.json` abstractions; replay report `drop_writers`), which no law states; the law restates the previous one. `L_msg_waiver_follows_origin` / `L_msg_waiver_not_caller` are sound as a pair: the fee key is AST-derived (`v_fee = est_fee(from, wl, amt)` with `from` = first argument of the call at `CDM:198`; source `CDM:199` passes `_from`). The def body `est_fee` is hand-typed (`body_forced`, `spec_bound` in coverage) but matches `L1MessageQueueWithGasPriceOracle.sol:113-119` (whitelisted sender → 0, else `_gasLimit * l2BaseFee`, with the product abstracted as `amt`).

**Remediation.** Replace `L_msg_budget_blocks_sender` with a law that states the absence: e.g. an invariant law `∀ action a ∈ bundle. mem(xh, dr) is unchanged` (O34's "no exit" needs exactly this universally quantified statement, which the U2 proposal `L_disch_replay_budget` already describes), or drop it.

### F7 — Low: `tests_m3` fails in a toolchain-complete environment (5 failures), and the PR's "55 OK" is stale

**Verified.** `python3 -m unittest discover -s tests_m3 -t . -v` → `Ran 62 tests`, `FAILED (failures=5)`, exit 1. All five are `tests_m3.e2.test_e2.TestMutantFacts.*`: the mutant extraction copies the morph tree and symlinks `contracts/node_modules` (`tests_m3/e2/test_e2.py:181-186`), which does not exist in the `tools/setup_env.sh --replay` checkout (`~/.holon/morph/contracts/node_modules` absent; solc fails on `@openzeppelin/...` imports). The other 57 tests pass, including the four forge replays (`test_forge_passed` ok for both suites). The PR says "55 OK"; HEAD has 62 tests. This is an environment-guard bug (the test should skip when the OpenZeppelin deps are absent, as `test_m3_replay.py:24-27` does), not a result defect, but it means the PR's "Done" line cannot be reproduced from `setup_env.sh` alone.

**Remediation.** Have `setup_env.sh --replay` run `npm ci` in `morph/contracts`, or have the e2 mutant tests reuse `holon.replay._sol_deps` and skip when it is unavailable.

### F8 — Low: M2 S6 "45,240/45,240 agree" is accurate but narrower than "the commitBatch transition from the reconstructed pre-state"

**Verified.** `replay/M2/report.json`: 1131 commits × 40 checks = 45,240, all `agree`, `disagreements: []`, manifest window blocks 26070237–26170657 (1131 commits). All 1131 corpus transactions are `commitBatch`; no `commitBatchWithProof`/`commitState` appear in the window. The coverage section records the v2 limitation honestly ("no enc_go_v2 … compared tail only", check `enc_go_v1_tail_eq`). The M2 exit criterion text (`docs/M2_SPEC.md` §1) is met as written; readers should not take it as covering the proof-carrying commit path.

## 1. Extraction honesty

| Frontend / file | Hand-typed content presented as part of the facts | Disclosed? | Per-name special cases | Debt missing from coverage |
|---|---|---|---|---|
| `holon/frontends/solidity` + `specs/morph_rollup_m3.spec.json` → `spec/M3/extracted/morph_rollup.json` | 38 of 73 provenance sections are `spec` (vocabulary sections, all `win`/shadow effects of commit*/revert/challenge/finalize via handlers, `initialize4.effects.active`, `wait`, `sendMessage` synthesized from `_queueTransaction`, `ISubmitter.slash` effect rule, `IRollupVerifier` `proof == 1` guard, `DEP` constant) | Mostly yes (`provenance` map + 117 coverage items) | `translate.py:1247` (`revertBatch` while-loop → `h_revert_loop`), `:1250` (`challengeState` for-loop → `h_bump_loop`), `:1253` (`_loadL1MessageHashes`). These are the only `fn ==` name tests in the frontends; both emit `prov="spec"` writes and are listed as `spec_bound` effects. | `proveState.effects.active` from the slash oracle rule is labelled `ast` (F2); `reinitializer(4)` one-shot semantics is `abstracted_modifier` but the resulting unreachable second cutover is not noted; `initialize4` appears in both `abstracted_fns` and `actions`. |
| `specs/l1messenger.spec.json` → `l1messenger.json` | `est_fee` body (`body_forced`), `setWhitelist`, `wait`, `initial` (`maxr: 3`), `params LFI/LCI` (unused leftovers), `dr` as a role set | Yes for `est_fee`/`setWhitelist`/`wait` | none | `_nextQueueIndex` → `mn` collision; `qi` dead; `pri`/`li` effects wrong (F4). Nothing records that `maxReplayTimes = 3` in `initial` is a deployment value, not source (`CDM` initializer sets it; the harness observed 3). |
| `specs/mvrv.spec.json` → `mvrv.json` | `get_verifier` body (`body_forced`), `initial`, `OWNER` | Yes | none | not-found revert modelled as 0 (F3) |
| `specs/submitter.spec.json` → `submitter.json` | vocabulary only; 36 `ast` sections | Yes | none | `slash.reward` is an oracle input (disclosed); fine. The machine is not linked to the Rollup facts, so the Rollup's `active` is a free register. |
| `holon/frontends/go/derivation.py` → `go_derivation.json` | None as facts. Field *names* (`batchBytes`, `parentIndex`, …) and the debt reason strings are literal in the reducer (`derivation.py:4-6` says so; `:398-401`, `:405-418`). Function targets are selected by name (`_find_fn(dump, "ParseBatch", …)` at `:807-816`); that is target selection, not a fact. The twin comparison is computed (`_twin_summary`, `_twin_diff`), and I confirmed its result against source: `common/batch/blob.go:49` reports `data[i*32]` (the unwritten destination) while `common/blob/payload.go:47` reports `blob[i*32]`. | Yes | none | `coverage` lists the three decode bodies, the remainder of `ParseBatch` and two oracle bodies. The HEAD after my checkout adds index-bounds partiality (`2313c8b`) with constants resolved from SSA (`MaxBlobBytesSize` by value, `derivation.py` delta lines `+55-57`), not literals. |

Byte-identity of the M2 Rollup extraction (`spec/M2/extracted/morph_rollup.json`, sha `edd33782…` claimed in the PR) was not rechecked; the M1 gate (G8 over `spec/M2/coverage`) passed.

## 2. Law and result integrity

- Prereg vs run: see F5. `git diff f750a6d HEAD -- laws/M3_msg laws/M3_router`: 12 files × (facts_sha256 line + newline) + two new `REGISTRY.json`. `git diff 7c54877 HEAD -- laws/M3_nat`: `REGISTRY.json` only. No statement, binder, premise or `predicted` field changed.
- Hash chain (manual G9): all 36 `statement_hash` values recomputed with `holon.ir.statement_hash` equal the registry and result records; `facts_sha256` equals the on-disk facts (`0863fe81…` messenger, `baa86b79…` mvrv, `acc1cc72…` rollup).
- Vacuity/tautology per law (closed laws; "vacuous" = the claim holds independently of the probe or of the extracted behaviour it names):
  - `L_nat_slash_legacy_misses`: **vacuous w.r.t. the slash** (F2; probe PROVED without the probe step). `L_nat_slash_native_hits`: meaningful; checks the spec rule `remove(bds, active)`.
  - `L_nat_defend_legacy_blocked`, `L_nat_defend_new_member`: meaningful on the extracted guard `mem(who, active)`; the value of `active` is the hand input `nact`.
  - `L_nat_cutover_admin_only/mismatch/in_challenge`, `L_nat_lcb`: check AST-extracted guards/effects (`R:210,212,213,216`). Sound unit laws.
  - `L_msg_budget_exhausts`, `L_msg_budget_owner_lifts`: meaningful on `CDM:226` and `:263-268`. `L_msg_budget_blocks_sender`: duplicate (F6). `L_msg_replay_ok`, `L_msg_no_replay_unsent`: unit laws on `CDM:193`.
  - `L_msg_waiver_follows_origin`, `L_msg_waiver_not_caller`: meaningful; the key (`from`) is AST-derived, the fee formula is hand-typed but source-equivalent.
  - `L_rt_unregistered_zero`, `L_rt_latest`, `L_rt_latest2`, `L_rt_legacy`, `L_rt_same_start_replaces`: check the hand `get_verifier` body plus AST-extracted `updateVerifier` effects (`MVRV:149-165` match: push-when-advancing, replace-in-place). `L_rt_before_start`: **certifies a source divergence** (F3). `L_rt_finalized_start`: checks `MVRV:149` with the oracle input `lfi`.
  - All 11 `L_setup_*` laws do their job: the setup trace of every probe law runs ok, so no probe passes on a failed setup.
- G4 canaries ran for each milestone (`negated`, `pin_const`, `swap_arg`), all rejected; G11 is trivial for binder-free laws (no premises to inhabit) and the records' `premises` field is the facts' `abstractions` prose, not law premises.

## 3. Replay validity (`replay/M3/*`)

- Rerun by me: `forge test --match-contract "HolonNatReplay|HolonMsgReplay" -vv --offline --use ~/.holon/solc-0.8.24` in the scratch project `tests_m3` builds (`~/scratch/m3msg/solidity`, real `contracts/` copy + npm deps via `holon.replay._sol_deps`): `4 tests passed, 0 failed`; the `HOLON …` lines equal those in `msg_report.json` and `nat_report.json`.
- No storage injection: `grep -n "vm.store\|stdstore\|HV.store\|vm.etch\|vm.mockCall"` over `replay/M3/solidity/*.sol` → none. Cheatcodes used: `warp`, `prank`, `deal` only.
- Contracts under test are real and reached through proxies with real initializers: `HolonMsgReplay.t.sol:41-51` (messenger, queue, `Whitelist`), `HolonNatReplay.t.sol:78-104` (Rollup behind `TransparentUpgradeableProxy` + real OZ `ProxyAdmin`, queue, real `Submitter` proxy with `addSubmitter` + public `stake`). The cutover goes through `ProxyAdmin.upgradeAndCall` (`:116-124`), which is the only way `_msgSender() == _getProxyAdmin()` (`R:210`) can hold; this is the production path.
- Stand-ins, disclosed in the harness header and report: `HolonSubmitterOracle` as the pre-cutover registry (`HolonNatReplay.t.sol:31-37`) and `HolonVerifierOracle` (`:40-44`). Neither is under test. The pinned tree has no legacy L1 registry (verified: `Rollup.initialize` takes an address; `contracts/contracts/l1/rollup/` holds only `Submitter.sol`, and the only `Staking.sol` is the abstract messenger base `contracts/libraries/staking/Staking.sol`, which has no `isActive`/`slash`), so a stand-in is unavoidable; it should remain labelled.
- Does each replay exercise the cited law's claim?
  - `L_msg_budget_blocks_sender`: yes — three third-party replays then the origin's replay reverts `Exceed maximum replay times` (`CDM:226`), then `updateMaxReplayTimes(4)` admits one more. The "no writer" claim in the report is confirmed by `grep -rn __isL1MessageDropped contracts/contracts --include=*.sol` → only the declaration (`CDM:45`) and the read (`CDM:195`).
  - `L_msg_waiver_follows_origin`: yes — whitelisted origin, non-whitelisted relayer replays at value 0, `feeVault.balance == 0`; dual case reverts `Insufficient msg.value for fee` (`CDM:201`).
  - `L_nat_defend_legacy_blocked`: yes — `proveState(Bob)` reverts `only active submitter allowed` (`R:120` modifier) after the swap; control `proveState(Carol)` reaches `_verifyProof` and fails at `R:758` (`Invalid batch proof`, empty proof) — i.e. past the submitter check but *not* at the stand-in verifier as the report's wording suggests; the report says "inside _verifyProof", which is accurate.
  - `L_nat_slash_legacy_misses`: yes — timeout prove by Carol, `batchChallengeReward(CHAL) == 0.1 ether` (deposit only, slash reward 0), `stakeOf(Bob) == 0` before and after, Carol still active; native control slashes Carol (`0.6 ether`, `stakeOf == 0`, inactive). This is the real-code evidence for O14 that the model law lacks (F2).
- Not replayed: the ten router laws (`MVRV` not deployed in any harness; the not-found revert at `MVRV:118` is therefore untested natively), the five `L_nat_cutover_*`/`L_nat_lcb` unit laws beyond what `cutover()` asserts (`submitterContract` and `legacyCutoverBatchIndex` reads at `HolonNatReplay.t.sol:122-123`), and `L_nat_defend_new_member` as a success (the control reverts at the proof, by design).
- `replay/M3/f3_report.json` + `replay/M3/go/holon_f3_test.go` (added in `2313c8b`, after my checkout): read only. The harness panics `common/batch.RetrieveBlobBytes` on element 3968 and `BatchInfo.ParseBatch` on a one-blob sidecar, with the 3967 and `common/blob` controls. Source agrees: `blob.go:49` indexes `data[i*32]` with `len(data) == 126976 = 3968*32`, so `i >= 3968` panics. The `recover` grep and the goroutine trace (`derivation.go:200`) are the report's own claims; I did not rerun `go test`.

## 4. M2 records

| Item | Reported | Recomputed from the committed report | Threshold |
|---|---|---|---|
| A1 (`replay/M2/mutation/report.json`) | 19/45 = 0.42 | `counts`: total 45, valid 45, detected 19, `extraction_gap` 5, `rule_gap` 21, equivalent 0; `score` 0.4222 | 0.8 (`spec/M2/mutants.json["threshold"]`, `report["threshold"]`) |
| A2 (`replay/M2/A2/report.json`) | 14/30 = 0.47 | total 30, valid 30, invalid 0, detected 14, `rule_gap` 16; walked A001–A030 in frozen order; `score` 0.4667 | 0.8 |
| A3 (`replay/M2/A3/report.json`) | 16/30 = 0.53 | total 34 walked (B001–B034), invalid 4 (B009, B012, B018, B031), valid 30, detected 16, `rule_gap` 14; `score` 0.5333 | 0.8 |
| S6 (`replay/M2/report.json`) | 45,240/45,240, 0 unexplained, 1,131 commits | 1131 commits × 40 check kinds = 45,240 `agree`; `disagreements: []`; manifest has 1131 commits | — |

- `docs/M2_SPEC.md:9-11`, `docs/M2_A2_SPEC.md:167`, `docs/M2_A3_SPEC.md:282` and `docs/M3_SPEC.md:9` state the same numbers and "adequacy-failed". No threshold field anywhere is below 0.8; `final: true` in all three reports; `equivalence_reclassifications: []` in all three (no mutant was argued away).
- Detection semantics follow the preregistered rule (`spec/M2/mutants.json["detected"]`: any status change incl. UNKNOWN). The reports disclose how many detections are "UNKNOWN-only" (`detected_via_counts`: A1 flip 13 / unknown_only 6; A2 13/1; A3 14/2). Two A1 mutants whose pipeline crashed (S03 `put_uint64_be … writes 9 bytes`, R01 `unbound variable cstart`) and A2's A001 (`unbound variable next`) were scored as **misses** (`rule_gap`, `miss_cause: pipeline_error`), which is the conservative direction.
- Ordering (git dates): A2 laws `eb4a3d0` 22:20 → materialized `c70dad3` 23:07 → sampler `371f2dc` 23:10 (discarded, erratum recorded in `docs/M2_A2_SPEC.md:261-265`) → frozen order `2c0f8ca` 23:21 → report `7d714c1` 00:46. A3 laws `8419780` 01:41 → materialized `29b69cb` 03:10 → sampler/set `2fa1c3e` 03:14 → report `927cb1f` 04:57. Consistent with the specs' pre-freeze logs.
- Not rechecked: the A3 draw (`seed 1397366245`, pool 75) by re-running the sampler, and the mutant-set sha256 values in `docs/M2_A3_SPEC.md:332-333`.

## 5. Gates, tests, freeze (my runs)

Environment: Python 3.12.13 (`/home/ubuntu/.pyenv`), Bend 2.0.36 (`~/.holon/bin/bend`), Lean 4.34.0 (`~/.elan`), Node v22.12.0 (`~/.holon/node`), Go 1.24.13 (`~/.holon/go`), forge 1.5.1-stable (`~/.holon/foundry`), solc 0.8.24 (`~/.holon/solc-0.8.24`), morph `~/.holon/morph` @ `3e44e795…`. `HOLON_MORPH_DIR` and `HOLON_SOLC` exported. Worktree `~/audit_r2/work` at `0820d64`.

| Command | Exit code | Result line |
|---|---|---|
| `python3 tools/freeze.py check` | 0 | FROZEN OK |
| `python3 -m holon gate --milestone M3_router` | 0 | GATE PASSED (GENV, G2, G1, G3, G5, G11, G7, G4) |
| `python3 -m holon gate --milestone M3_msg` | 0 | GATE PASSED (same 8 checks; 12 proofs, 23 canaries rejected) |
| `python3 -m holon gate --milestone M3_nat` | 0 | GATE PASSED (same 8 checks) |
| `python3 -m holon gate --milestone M3_sorts` | 0 | GATE PASSED (12 checks incl. G6, G8, G9, G11_names) |
| `python3 -m holon gate --milestone M0` | 0 | GATE PASSED |
| `python3 -m holon gate --milestone M1` | 0 | GATE PASSED |
| `python3 -m unittest discover -s tests_m3 -t . -v` | **1** | `Ran 62 tests`, `FAILED (failures=5)` — all five `tests_m3.e2.test_e2.TestMutantFacts.*`, cause: missing `contracts/node_modules` in the morph checkout (F7). Both forge replay suites ran fresh and passed. |
| `forge test --match-contract "HolonNatReplay\|HolonMsgReplay" -vv --offline --use ~/.holon/solc-0.8.24` (scratch project) | 0 | `4 tests passed, 0 failed`; HOLON lines identical to the committed reports |

`git status --short` in the worktree after all gates: empty (no tracked file was rewritten).

## Independent probes (not added to the repo)

Written as `holon-ir/0.2` closed laws into `laws/AUD_nat` and `laws/AUD_msg` of the scratch worktree with a generated `REGISTRY.json`, run with `python3 -m holon run --milestone AUD_<x> --out … --gen-dir …`. All PROVED, `bend --verdict` checked.

| Probe | Facts | Claim | Status | Reading |
|---|---|---|---|---|
| `L_aud_active7_without_probe` | `morph_rollup.json` | `active_has(7) == true` after `C1 + i4 + ch(1) + wait(10)` (no `proveState`) | PROVED | `L_nat_slash_legacy_misses`' observation does not depend on the slash step |
| `L_aud_active2_after_cutover` | same | `active_has(2) == false` after `C1 + i4` | PROVED | the legacy committer leaves the registry at `initialize4`, by the spec rule `active := nact` |
| `L_aud_active7_after_x` | same | `active_has(7) == true` after `C1 + i4` | PROVED | control |
| `L_aud_i4_twice_ok` | same | `last_ok(initialize4(6,9,1,[7]))` from the post-cutover state | PROVED | `reinitializer(4)` is not modelled; the model admits an unreachable second cutover |
| `L_aud_msg_budget_qi_dead` | `l1messenger.json` | `L_msg_budget_exhausts` with `qi = 0` everywhere | PROVED | `qi` is a dead input |
| `L_aud_msg_budget_sender_who_irrelevant` | same | sender replays 3×, 4th reverts `Exceed maximum replay times` | PROVED | `who` is not read by `replayMessage`; `L_msg_budget_blocks_sender` duplicates `L_msg_budget_exhausts` |
| `L_aud_msg_times3` | same | `times_of(11) == 3` after three replays | PROVED | the budget counter is extracted correctly |

## Verified facts vs inferences (summary)

Verified by command or by reading the cited lines: everything in §§1-5 and the probe table; the Morph source for `initialize4` (`R:209-219`), `proveState` (`R:595-622`), `_challengerWin` (`R:803-809`), `Submitter.slash` (`SUB:147-161`), `replayMessage` (`CDM:175-240`), `_sendMessage` (`CDM:275-317`), `updateMaxReplayTimes` (`CDM:263-268`), `estimateCrossDomainMessageFee` (`L1MessageQueueWithGasPriceOracle.sol:113-119`), `getVerifier`/`updateVerifier` (`MVRV:98-166`), the two `RetrieveBlobBytes` twins.

Inferences: that O13/O14 are correctly characterised as "transitional" behaviours of the pinned code (the harness shows them on a synthetic cutover; the mainnet legacy registry and whether its bond is withdrawable were not examined); that the `storage_on_write` rule was written with knowledge of the intended finding (the rule's `note` says "assume-guarantee input", which is the right framing but is not what the law records say); that the blind-rerun comparison will be unable to score these four items without F1's remediation.

## Not done / residual limits

- The branch moved to `5c41bce` during the audit; `2313c8b`/`5c41bce` (E3 index-bounds partiality, F3 Go replay) were reviewed as diffs only; `go test` for F3 was not rerun and the gates were not rerun on the new head.
- No re-execution of the A1–A3 campaigns or the S6 corpus replay (the corpus cache is not on this VM); scores were recomputed from the committed reports only.
- No fork/mainnet reachability work for the cutover (legacy registry contents, actual `initialize4` transaction); no economic analysis of O14's "bond not at risk".
- No fix, push, freeze or PR change; probes live only in `~/audit_r2/work` (a detached worktree) and are reproduced in full in this document.
