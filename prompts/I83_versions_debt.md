# I83 (= I28b): I28's model debt paid

Read first: `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, then this prompt. Run `bend guide` once.
Then read `docs/iterations/I28.md` (all of it, Question 1 and P4-P6 above all), the contract of I28 (the docstring of
`tests_m3/test_versions.py`) and this key's contract, the docstring of `tests_m3/test_versions_debt.py`.

## Why

I28 built the versioned machine of the Rollup's deployed path (V3..V11). holon.sorts.model3 refused every successor-site
(commit) action before V11, and recorded each one as model debt:

- **V3-V5:** the frontend's `["mload", ["unknown", .., "memory"], ..]` reads of the memory copy of
  `batchDataInput.blockContexts`, in BatchCodecV0's and the Rollup's assembly.
- **V3-V4:** also `calldataload` at `skippedL1MessageBitmap.offset`.
- **V3-V10:** `abi.decode(batchSignatureInput.sequencerSets, (uint256, address[], uint256, address[], uint256,
  address[]))`, in `_getValidSequencerSet`.

As a result:
- G11V's in-flight clause found 0 of 8 MIG edges inhabited (I28-P5, a miss).
- The V10->V11 cutover's inhabitant could not replay (I28-P6, a miss).

I28 keeps its number and its misses. This key re-attempts P5 and P6 under the new key, as I62 re-ran I61.

## What

1. **Language** (rules L1-L4). Teach model3 these generic constructs, each in a function or block of its own:
   - L1: abi.decode of a tuple of value types and dynamic arrays of them, with the decoder's own checks as a revert
     that is not a check of the document;
   - L2: a word list as an external call's argument;
   - L3: the memory copy of input bytes read in assembly;
   - L4: calldataload at an input's calldata offset.

   Constraints:
   - Nothing names a version, a contract, an action or a law.
   - Every model model3 compiled before must come out byte-identical (R1). Add no prelude definition, and emit a new
     helper only into a model that uses it.
   - I69 (PR #52) extends the frontend, the evaluator and model3 too. Keep your changes apart from its changes, to make
     the merge easy.
2. **Candidate generator** (rules IS1-IS2, sidecar `spec/M3/lib/inflight_search.json`).
   - It works over the versioned machine's untyped modules.
   - It starts from the zero call, plus a canonical encoding for every abi.decode'd bytes leaf.
   - Its moves are directed by the first failing check. They are candidates, never evidence: Bend decides.
3. **Outputs** (rule IS3): I28's V8 and V9, unchanged, plus one replay run per inhabited edge.
4. **The lifecycle channel** (rules X0-X5). This is the coordinator's decision under the human's standing delegation
   (revocable; record it under Questions for the human).
   - **Why it is needed.** Extending the model changes the cone of every law bound to the versioned layer under a fixed
     statement. No unsigned kind covers that: binding_change needs every root unchanged or extensionally equal.
   - **The kind.** Add `model_extension` to `holon/statement_diff.py` and to G2's tie in `holon/bindings.py`. It is
     accepted only for a conservative extension of the bound model (X3), with the law's verdict re-established on the
     new model by both kernels (X4).
   - **Use it.** Re-bind the PAR-init law through it. Once I29's build has merged, re-bind I29's NAT laws the same way,
     with re-made records. Keep G2 green.
   - **Direction.** This kind runs in the strengthening direction only: more behaviours, never fewer. It changes no
     claim, statement or registry hash, and a refuted law keeps its witness. So it weakens no claim.
   - **The record field.** A constructor that gains fields (a version module's environment record gains `e_blobs` when
     a commit reads blob hashes) is part of X3. The gained fields are erased from every pattern and construction before
     comparing. This extends the coordinator's wording ("only new constructors are added"), and the extension must be
     stated in the report.

## Predictions

The key is `I83` in `spec/M3/predictions.json`. Six predictions are counted:
- P1: no model debt.
- P2: 8 of 8 inhabitants (I28-P5's check).
- P3: the cutover replays (I28-P6's check).
- P4: the inhabitants on the real code: V6->V7 .. V10->V11 pass, and V3->V4 .. V5->V6 differ in one word only.
- P5: I29's three cutover squares stay UNKNOWN. I29's own search and budget keep them so, not the debt.
- P6: G2 stays green through model_extension.

Regressions: R1-R3. I28-P4 at V3-V5 is not this debt (it is PI5's site rule over the frontend's loop-carried terms),
and it is not re-predicted.

## Process

Follow LANE_RULES (the coordinator's lane rules).
1. C_K first: this prompt, the key, the contract and its tests (red), the instrument `tests_m3/_i83.py`, the sidecar and
   the BUILD_PLAN row. Push it, and open the draft PR.
2. Build: the code, then the outputs. Re-make the records whose closures move: M1, M2 and T32 locally; M3 on runners.
3. Report: `docs/iterations/I83.md`, the last own commit. It has the sections Done / Surprises / Questions for the human /
   Not done.
