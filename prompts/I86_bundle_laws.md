# I86 (= I36b): Bundle I's laws over the current deployment, over I69's extraction

Rendered from `docs/BUILD_PLAN.md` §4 I36 and its rows I69 and I86 (whitepaper §7.5 payer and conservation, §5.7 DISCH, Lemma 6.12 and Cor 6.16, §11.6 D7-D9; Appendix A O29/F8, O30/F13, O34/F8), from the human answers Q21 (structural storage keys) and Q28 (BMC and the empty queue) in `docs/HUMAN_ANSWERS.md`, and from I69's prompt and report draft (PR #52). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, and run `bend guide` once.

The exact rules are in the docstring of `tests_m3/test_bundle_laws.py`:
- DC1-DC2, the principal classes;
- DB1-DB3, the model debt;
- LM1-LM2, the law models and the claims modules;
- C1-C2, the catalog; N1, the law ids; ST1, the statements;
- PY1-PY4, SORT payer; CS1-CS5, SORT conservation;
- K1-K8, DISCH keyed; PP1-PP6, PAR push;
- W1-W5 and D1-D4, witnesses and decisions;
- RC1-RC3 and RP1-RP3, records and replay;
- Q1-Q5, Q28's BMC over the linked queue;
- the commands, exit codes and commit rules.

The key's thresholds pin that docstring, the instrument `tests_m3/_i86.py`, the sidecar `spec/M3/lib/bundle_laws.json` and the basis `spec/M3/lib/bundle_laws_basis.json` by sha256. The base is `92c98e40`, the lead after I80, I81 and I72's build. I69 (PR #52) has not merged at the base: the basis reads its outputs from its pushed branch head `6576c56a` (thresholds.i69_rev), and the build starts once I69 has merged into the lead and the lead into this branch.

## Why a separate key

I69 (= I36a) was BUILD_PLAN I36's extraction half (the split of 2026-10-23). I86 = I36b states I36's laws over the current deployment: O29, O30, O34, D7, D8, D9, and Q28's BMC rerun. I36 keeps its number, its plan text and its predictions; I70 (= I36c) takes O13 and O20's economic half. Numbered I86 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys).

## The coordinator's ruling on I68

I68 (Q21's structural storage keys) is several hours from the lead and lands after I35. The ruling (2026-10-30): predict every I68-dependent law UNKNOWN, naming the dependency on I68 in the key; predict every other law on its merits. A law depends on I68 when its decision frames a mapping cell at a quantified key under the quantified keccak table, that is every keyed_blocking law (O34's blocking and D9) and every conservation law that credits a mapping cell. If I68 lands before the build's records, those laws are still decided as the key says (no proof attempted): a later key re-attempts them.

## What I86 does

1. **The model debt (DB1-DB3).** I69 left nine actions of model debt. I86 pays the messenger's five, because every messenger law needs them:
   - `abi.encodeWithSignature`: `sendMessage` (both overloads), `replayMessage`, `proveAndRelayMessage`;
   - Verify.sol's fold: a shift by a non-constant amount and the packed width of the loop-carried `node` (`verifyMerkleProof`, and `proveAndRelayMessage` through it).

   The extensions are generic and emitted only into a model that uses them. Every model compiled before compiles byte for byte (DB2). The queue's four (a storage array's length, Yul's `byte`) stay debt: no I86 law needs the queue's model (a law model answers external calls from its environment, A-env). I69's models and model refinement record are re-made (DB3, I69's rule m7).
2. **The catalog (C1).** holon-rules/1.11, the next free version after I71's 1.7, I29's 1.8, I35's 1.9 and I84's 1.10, chained to the newest at the build's base. It adds six sub-forms:
   - SORT `payer` (O29);
   - SORT `conservation` (O30, D8's inflow half);
   - DISCH `keyed_blocking`, `keyed_external` and `keyed_external_none` (O34, D9);
   - PAR `push` (D7).

   **Why new sub-forms, against the preference for the existing catalog.** No existing sub-form states a payer or a conservation claim (SORT's typed sub-forms are realize, as_member and reinterpret). I31's DISCH basis holds only state conjuncts, while O34's and D9's guards read a mapping at a key computed from the action's inputs. And PAR-lossy's pushing is I25's core law, not a catalog producer, with D7 deferred to I36 in I25's own sidecar. So the bump is unavoidable, and one bump carries all six.
3. **The law models (LM1).** The bundle members are not in I30's typed sidecar, and adding them would move I30's frozen instrument and the frozen sort assignment. So I86's laws are stated over I69's untyped member models, which already define `Reach<kh, s>` over the keccak table. The Rollup's law model is compiled by I69's rule M3 into `gen/M3/bundle_laws/models/rollup.bend`, so that every law of the bundle uses one deployment and one machine.
4. **The laws (17).**

   | sub-form | laws | obligation |
   |---|---|---|
   | payer | `replayMessage` at :201, both `sendMessage` overloads at :291 | O29 and its two keyed-on-the-payer siblings |
   | conservation | the 8 payable actions of the bundle | O30 (`commitBatch`) and D8's inflow half |
   | keyed DISCH | :226's budget guard (blocking anyone; external and external_none onlyOwner) and :141's finalized guard (blocking anyone and onlyOwner) | O34 and D9 |
   | push | the Merkle check at :154-157 | D7 |
5. **Witnesses (W1-W5)** come from I69's corpus, run by I69's linked machine, and are evaluated on the compiled law model from the model's own state chain. For a conservation law with no corpus witness, they come from the value variants of its successful corpus frames. Every counter-law is decided by the pinned Bend, and every REFUTED or existential witness is replayed on the real bundle through I69's harness (RP1-RP3).
6. **Q28 (Q1-Q5).** Q28 reruns I40's BMC over the 13 Rollup checks that read the queue's `getFirstUnfinalizedMessageEnqueueTime`, with the queue linked:
   - its storage is part of the state;
   - its programs answer the Rollup's calls into it;
   - an enqueue move stands for the messenger's `sendMessage`.

## Predictions, and what of BUILD_PLAN is adopted

| BUILD_PLAN I36 (current deployment) | I86 |
|---|---|
| O29 REFUTED | **P2**: REFUTED, witness from the corpus, replayed with the fee difference observed; **P3**: the two `sendMessage` payer laws PROVED |
| O34 owner strategy PROVED | **P7**: keyed_external PROVED (and its keyed_external_none twin REFUTED), replayed |
| O34 blocking PROVED | **P8**: UNKNOWN, naming I68 (the coordinator's ruling) |
| D7 PROVED through injective pushing under CF | **P10**: PROVED, with an inhabitant; PP6's construction check |
| D9 PROVED | **P9**: both keyed_blocking laws UNKNOWN, naming I68 (the ruling) |
| O30 REFUTED | **P4**: REFUTED by a value variant (a successful commit carrying 1 wei), replayed |
| D8 PROVED, with annotated exceptions | **P5**: the three unaccounted inflows REFUTED (the Rollup's `receive`, annotated as the whitepaper's slash receive, and the messenger's owner-only `receive`, which the whitepaper does not list); **P6**: the other five inflow laws UNKNOWN (two name I68, three name the missing value-outflow record) |
| Q28's BMC rerun (HUMAN_ANSWERS Q28) | **P11**: the three callok targets no_path, and the delay guards of `commitBatch` (:265) and `commitBatchWithProof` (:398) path, replayed |
| (the model debt I69 left) | **P1**: the messenger compiles every action and refines on I69's corpus |
| stand-in label (Q12) | not applicable: the current deployment holds no legacy staking contract (L1Staking is I70's, and I69 recovered its real code) |

**D8 as a whole is predicted UNKNOWN.** Its debit half is not stated (see Deviations), and five of its eight inflow laws wait on I68 or on the outflow record. Its exceptions are decided:
- O30 and the annotated receive, as the whitepaper says;
- plus the messenger's owner-only `receive`, an unaccounted inflow outside the whitepaper's exceptions, predicted REFUTED and reported as a D8 discrepancy.

Regressions:
- **R1:** DB2's byte identity.
- **R2:** the commit rules, with M1, M2 and T32 re-made.
- **R3:** both prereg audits pass, and CI fails only on the base's items.
- **R4:** the new code names no target.

## Deviations from the plan's text, and why

- **O34 blocking and D9 are UNKNOWN by prediction.** This is the coordinator's ruling on I68, not a weakened claim: their statements are fixed here and a later key decides them over I68's model.
- **D8's debit half is not stated.** A cell-level debit claim would need two things the M3 model does not have:
  - a value-outflow record;
  - a notion of a live amount cell. The Rollup keeps a resolved challenge's `challengeDeposit` while crediting it to `batchChallengeReward`, so a per-step cell delta would be refuted by bookkeeping, not by a lost value.

  The inflow half is stated in full. "D8 PROVED with annotated exceptions" therefore cannot be established by this key, and the report says so.
- **`holon/sorts/conservation.py`** (BUILD_PLAN I36's deliverable) becomes the conservation producer's analysis (CS1-CS2). Its form follows the catalog; the plan names no format.
- **The messenger and the Rollup only.** I86's laws touch the messenger and the Rollup only (plus the Submitter's `stake` among the inflows). The whitelist and the queue carry no I86 law: the queue is linked only in Q28's BMC.

## What was known before this prereg (disclosed)

**Read:**
- the sources of the messenger, `CrossDomainMessenger.sol`, `Verify.sol`, the queue and the Submitter, and the Rollup's commit, challenge, receive and delay-guard lines, at the head `3e44e79`, through git objects with lazy fetching disabled;
- I69's prompt, sidecar (its seed trace S1_messaging plants a third-party replay of a whitelisted sender's message, three replays, the budget's exhaustion and the owner's raise), declaration, member documents and `models.json`, and its draft report in its worktree (P5's nine debt actions, P6's 0 disagreements over 3348 steps);
- I40's report (Q28's list) and `results/M3/refute/reaches.json`;
- I25's sidecar (D7 deferred to I36);
- I84's prereg, as the closest template;
- I68's and I83's prompts (I83 pays I28's debt, not I69's).

**Ran:**
- the instrument's basis (`python -m tests_m3._i86 --write --rev 6576c56a`, under a second);
- `holon model --milestone M3`, typed and untyped, into a scratch directory: the typed text equals the committed one, and the untyped text's sha256 is pinned (thresholds);
- one scratch Bend probe of the word-to-bytes round trip on I69's messenger model. It does not reduce for symbolic limbs (`u_b4z(Cmp.is_eq(U32.cmp(l, 0)), l)` is stuck on the primitive U32), which is why D7's claim is stated over the encoding's bytes.

**Never run before this prereg:** model3 on the messenger with any extension, the linked machine, the corpus, forge, BMC, and Bend on any I86 law, counter-law or witness. No status, witness or replay was observed. I69's `results/M3/bundle/steps.json` was not read.

## Risks for the build

1. **DB1** may meet a further construct after the first error of each debt action (I69 recorded only the first). Then the action stays debt, P1 misses, and every law that needs it is UNKNOWN, naming the debt.
2. **Witnesses.** The corpus may hold no value-carrying successful frame for a `receive`. The value variants exist for exactly this. A law with no witness in either source is UNKNOWN with its bound, and its prediction misses.
3. **Kernel time** on long Reach chains over the Rollup's law model (O30's prefix). A fuel or time stop is budget exhaustion, never acceptance.
4. **Q28's linked encoding** is new code in holon.bmc's terms. A query out of budget is unknown, and P11 misses. Q28 is the last item of the build.
5. **Catalog ordering.** 1.10 (I84) and 1.11 may land in either order. Whoever merges second chains the versions and re-derives.
6. **The re-make.** model3 and holon/rules are in every closure, so M1, M2 and T32 are re-made locally and M3 on CI runners (LANE_RULES). I28's base items stay as they are.

## Questions for the human (stated at the prereg)

- **Q-I86-a (D8's debit half).** Should a later key give the M3 model a value-outflow record and state D8's debit half over live amount cells (a challenge's deposit is live until the challenge finishes)? Or is D8's inflow half, with its exceptions, what the paper should report?
- **Q-I86-b (the messenger's receive).** The messenger's `receive` (onlyOwner) accepts ETH and records nothing. Is that an intended owner top-up, to be annotated as the whitepaper annotates the slash receive, or a finding?
- **Q-I86-c (I68's laws).** When I68 lands, should I86's three keyed_blocking laws and two ledger-class conservation laws be re-attempted under a new key (I87 or later), as I83 re-attempts I28's misses?

## Commands

```
python -m holon bundle model|refine                     (I69's, re-made under DB1)
python -m holon bundle laws [--check]
python -m holon derive --milestone M3
python -m holon run --milestone M3 --laws <the 17 ids>
python -m holon bundle replay-laws [--check]
python -m holon bundle bmc [--check]
```

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, an earlier key, I69's, I25's or I40's sidecars, or `spec/M3/lib/refute.json`.
- **The instrument, the sidecar and the basis are fixed at the prereg.** A wrong instrument is a Question plus an amendment line, never a silent edit.
- **A missed prediction is a result.** Never adjust a witness source, a value variant, a bound, the annotation or a dependency after a run.
- **The target repository is read through git objects** with lazy fetching disabled. Never fetch or read `scroll-tech/*` or `spec/heldout/`.
