# M0 facts audit: `facts/morph_header.json` against the real repo

- **Repo:** morph-l2/morph at `3e44e795586af3e11285b603ab642c67823add51` (`3e44e79`).
- **Method:** every `code` string and source reference in the facts was located in the checkout by file and function. Line numbers below are in the real repo, not the audit bundle.
- **Result:** every fact matches. One modelling note (A1) and one scope note (A2) follow the table. No facts were edited.

## Solidity: `enc_sol` (commit-path header build)

| Fact | Real code | Verdict |
|---|---|---|
| domain `version <= 2` | `contracts/contracts/l1/rollup/Rollup.sol:293` `require(batchDataInput.version <= 2, "invalid version")` | matches |
| length 249 / 257 by version | `Rollup.sol:332-335`: `_headerLength = BatchHeaderCodecV0.BATCH_HEADER_LENGTH` (249, `BatchHeaderCodecV0.sol:24`); `if (version >= 1)` → `BatchHeaderCodecV1.BATCH_HEADER_LENGTH` (257, `BatchHeaderCodecV1.sol:27`) | matches |
| `memory_init: dirty` | `Rollup.sol:336-339`: `_batchPtr := mload(0x40)`, no zeroing before the stores | matches (conservative: the model treats every unwritten byte as unknown) |
| op 0 `mstore8` version at 0 | `Rollup.sol:342` → `BatchHeaderCodecV0.sol:133` `mstore8(batchPtr, _version)` | matches |
| op 1 `mstore` `shl(192, batchIndex)` at 1 | `Rollup.sol:343` → `BatchHeaderCodecV0.sol:144` | matches |
| op 2 `mstore` `shl(192, l1MessagePopped)` at 9 | `Rollup.sol:344` → `BatchHeaderCodecV0.sol:155` | matches (see A1) |
| op 3 `mstore` `shl(192, totalL1MessagePopped)` at 17 | `Rollup.sol:345` → `BatchHeaderCodecV0.sol:166` | matches |
| op 4 `mstore` dataHash at 25 | `Rollup.sol:346` → `BatchHeaderCodecV0.sol:175` | matches |
| op 5 `mstore` blobVersionedHash at 57 | `Rollup.sol:347` → `BatchHeaderCodecV0.sol:184` | matches |
| op 6 `mstore` prevStateHash at 89 | `Rollup.sol:348` → `BatchHeaderCodecV0.sol:193` | matches |
| op 7 `mstore` postStateHash at 121 | `Rollup.sol:349` → `BatchHeaderCodecV0.sol:202` | matches |
| op 8 `mstore` withdrawRootHash at 153 | `Rollup.sol:350` → `BatchHeaderCodecV0.sol:211` | matches |
| op 9 `mstore` **zero** at 185 (input field ignored) | `Rollup.sol:351` `storeSequencerSetVerifyHash(_batchPtr, bytes32(0))` → `BatchHeaderCodecV0.sol:220` | matches |
| op 10 `mstore` parentBatchHash at 217 | `Rollup.sol:352` → `BatchHeaderCodecV0.sol:229` | matches |
| op 11 `mstore` `shl(192, lastBlockNumber)` at 249 when `version >= 1` | `Rollup.sol:353-354` → `BatchHeaderCodecV1.sol:56` | matches |
| hash over `_headerLength` bytes | `Rollup.sol:357` `computeBatchHash(_batchPtr, _headerLength)` | matches |

## Solidity: `ok_sol` (`_loadBatchHeader`)

| Fact | Real code | Verdict |
|---|---|---|
| empty → revert | `Rollup.sol:825` `require(batchHeader.length > 0, "Empty batch header")` | matches |
| version 0 → `len >= 249` | `Rollup.sol:838-839` → `BatchHeaderCodecV0.sol:32` `require(length >= BATCH_HEADER_LENGTH, ...)` | matches |
| version 1, 2 → `len == 257` | `Rollup.sol:840-842` → `BatchHeaderCodecV1.sol:35` `require(length == BATCH_HEADER_LENGTH, ...)` | matches |
| otherwise → revert | `Rollup.sol:843-844` `revert("Unsupported batch version")` | matches (replayed: version 3 reverts) |

## Go: `enc_go_v0`, `enc_go_v1`, `ok_go`, `dec_go`

| Fact | Real code (`common/batch/batch_header.go`) | Verdict |
|---|---|---|
| `enc_go_v0`: 249 zero bytes, byte 0 = 0, PutUint64 at 1/9/17, copy at 25…217 | `:212-235` `BatchHeaderV0.Bytes` | matches |
| `enc_go_v1`: 257 zero bytes, byte 0 = **1**, same writes + PutUint64 at 249 | `:240-258` `BatchHeaderV1.Bytes` (`:245` `batchBytes[0] = BatchHeaderVersion1`, `:256` lastBlockNumber) | matches; no V2 encoder exists (only constants `:23`, `:27`) |
| cache precondition (`EncodedBytes` empty) | `:213-215`, `:241-243` | matches (OWN rule, later milestone: O37) |
| `ok_go`: empty → error; v0 `== 249`; v1 `== 257`; v2 `== 257`; else error | `:37-58` `validate`, `:72-77` `Version` | matches |
| getters at 0, 1, 9, 17, 25, 57, 89, 121, 153, 185, 217, 249 | `:79-191` | matches; `LastBlockNumber` errors for version 0 (`:184-191`), `BlobCommitHash` dispatches by version |

## Notes

**A1 (reachable-set over-approximation, whitepaper L2).** In `IRollup.BatchDataInput`, `numL1Messages` is `uint16` (`IRollup.sol:20`) and `lastBlockNumber` is `uint64`. The facts model `l1MessagePopped` as a full 8-byte field. For PAR laws this over-approximates the reachable set R, so a PROVED law is proved for more inputs than Solidity can produce, which is sound. A witness that used `l1MessagePopped >= 2^16` would *not* be reachable through `commitBatch`. None of M0's witnesses do. M1 should record carrier ranges from ABI types so the refuter prefers reachable witnesses.

**A2 (version-2 blob field semantics).** At version 2 the 32 bytes at offset 57 are `keccak256(blobhash(0) ‖ … )`, not a versioned hash (Go comment `:19-22`; `BlobHashesHash`). The byte layout is identical, so the M0 PAR laws cannot see this. It is the O26 ghost-tag obligation (SORT×UNDO), scheduled for M1.
