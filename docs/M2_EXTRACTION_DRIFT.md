# M2 extraction drift (post-R5)

Regenerating `spec/M2/extracted/morph_rollup.json` with the current extractor
(R5: def params are bound names during `defs_from` body translation, so
lets/guards referencing them survive `_unbound_names`) produces the drift below.
The M2 facts stay at the committed bytes — the M2 record is frozen — so this
document records what a regeneration would add, per item, with its source.

facts sha256, committed (`edd3378…`): `edd337829f4aebf62e4d253c862b7b6c82f1e42f0e8205cb464604c6b01e92a0`
facts sha256, regenerated (`371aab2…`): `371aab2fcb139419e1475ec839a8052b8dbaae78e581773833e33e483f843d27`

## Newly appearing guards (call-site emission of `defs_from` guards)

All four come from `_computeBlobVersionedHash` (`Rollup.sol:892-917`), the
`blob_hash` def. On the committed facts its requires were silently dropped by
`_unbound_names` (they reference def params `ver`/`blobs`); with params bound
they are emitted at the call sites with arg substitution.

| action | guard | reason | src | source check |
|---|---|---|---|---|
| commitBatch | `ver != 2 \|\| blob_count(blobs) > 0` | V2 requires at least 1 blob | `contracts/contracts/l1/rollup/Rollup.sol:913` | `require(_blobCount > 0, "V2 requires at least 1 blob")` inside `if (_version == 2)` — revert iff `ver==2 && blobCount==0`. `blob_count(blobs)` abstracts the asm `_blobCount` loop. |
| commitBatch | `ver == 2 \|\| nth(blobs, 1) == 0` | legacy batches support exactly 1 blob | `contracts/contracts/l1/rollup/Rollup.sol:915` | `require(blobhash(1) == bytes32(0), ...)` in the `else` (ver != 2) — revert iff `ver!=2 && blobhash(1)!=0`. `nth(blobs,1)` abstracts `blobhash(1)`. |
| commitBatchWithProof | `stored != 0 \|\| ver != 2 \|\| blob_count(blobs) > 0` | V2 requires at least 1 blob | `contracts/contracts/l1/rollup/Rollup.sol:913` | same inner require, emitted only under the `else` of `batchBlobVersionedHashes[_nextBatchIndex] != 0` (`Rollup.sol:405-410`), i.e. conds `[stored == 0]`. Correct reach: the call site is reached only when no stored blob hash exists. |
| commitBatchWithProof | `stored != 0 \|\| ver == 2 \|\| nth(blobs, 1) == 0` | legacy batches support exactly 1 blob | `contracts/contracts/l1/rollup/Rollup.sol:915` | same as above, under conds `[stored == 0]`. |

New reason-table entries: `6: "V2 requires at least 1 blob"`,
`7: "legacy batches support exactly 1 blob"` (all later reason ids shift).

## Known provenance drift (pre-existing, unrelated to R5)

- `provenance["actions.proveState.effects"]`: `ast` → `spec`. The proveState
  effects carry a spec-declared `emit_overrides` path whose provenance label
  was never re-recorded after the F2 provenance work landed. Metadata only —
  the effect expressions are byte-identical.
- Coverage file (`spec/M2/coverage/solidity_transitions.json`): matching
  `spec_bound` items appear for `action:proveState.effects.active` and the
  spec-declared observers (`csr_last`, `kappa`, `lci_of`, `new_hdr`,
  `tags_ok`). Metadata only.

## Lets

No newly appearing lets: every def-local let that was previously dropped for
referencing a param is inlined into the guards above (call-site emission
inlines def-let names via `_inline_lets`), so the emitted guard exprs are
closed over params/inputs only.
