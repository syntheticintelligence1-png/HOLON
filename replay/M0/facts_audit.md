# M0 facts audit: facts/morph_header.json vs morph-l2/morph @ 3e44e795586af3e11285b603ab642c67823add51

I compared each `code` string and source reference against the real repository at
that commit. Paths are relative to the repo root. "matches" means the code has the
same semantics as the fact; spelling may differ slightly (e.g. `x` for the parameter name).

## enc_sol (Solidity commit-path encoder)

| fact | repo file:line | verdict |
|---|---|---|
| domain: `require(batchDataInput.version <= 2, "invalid version")` | contracts/contracts/l1/rollup/Rollup.sol:293 | matches |
| length_code: 249, 257 if version >= 1; hash = keccak256(batchPtr, len) | Rollup.sol:332-335, 357; BatchHeaderCodecV0.sol:24 (249), 239-243; BatchHeaderCodecV1.sol:27 (257) | matches |
| memory_init dirty: header written at the free pointer `mload(0x40)` | Rollup.sol:336-339 | matches (memory is not zeroed) |
| ops[0] storeVersion `mstore8(batchPtr, _version)` | Rollup.sol:342; BatchHeaderCodecV0.sol:131-135 | matches |
| ops[1] storeBatchIndex `mstore(add(p,1), shl(192,x))` | Rollup.sol:343; V0.sol:142-146 | matches |
| ops[2] storeL1MessagePopped `mstore(add(p,9), shl(192,x))` | Rollup.sol:344; V0.sol:153-157 | matches |
| ops[3] storeTotalL1MessagePopped `mstore(add(p,17), shl(192,x))` | Rollup.sol:345; V0.sol:164-168 | matches |
| ops[4] storeDataHash `mstore(add(p,25), x)` | Rollup.sol:346; V0.sol:173-177 | matches |
| ops[5] storeBlobVersionedHash `mstore(add(p,57), x)` | Rollup.sol:347; V0.sol:182-186 | matches |
| ops[6] storePrevStateHash `mstore(add(p,89), x)` | Rollup.sol:348; V0.sol:191-195 | matches |
| ops[7] storePostStateHash `mstore(add(p,121), x)` | Rollup.sol:349; V0.sol:200-204 | matches |
| ops[8] storeWithdrawRootHash `mstore(add(p,153), x)` | Rollup.sol:350; V0.sol:209-213 | matches |
| ops[9] storeSequencerSetVerifyHash(p, bytes32(0)), input ignored | Rollup.sol:351; V0.sol:218-222 | matches |
| ops[10] storeParentBatchHash `mstore(add(p,217), x)` | Rollup.sol:352; V0.sol:227-231 | matches |
| ops[11] if version >= 1, storeLastBlockNumber `mstore(add(p,249), shl(192,x))` | Rollup.sol:353-355; BatchHeaderCodecV1.sol:54-58 | matches |
| source bundle_lines 343-370 / 1264-1364 / 1434-1438 | — | bundle numbering, not repo lines (as the fact's line_note says) |

## ok_sol (`_loadBatchHeader` does not revert)

| fact | repo file:line | verdict |
|---|---|---|
| empty → revert "Empty batch header" | Rollup.sol:824-827 (`_getBatchVersion`) | matches |
| v0 → `length >= 249` | Rollup.sol:838-839; BatchHeaderCodecV0.sol:30-39 ("batch header length too small") | matches |
| v1, v2 → `length == 257` | Rollup.sol:840-842; BatchHeaderCodecV1.sol:33-41 ("batch header length is incorrect") | matches |
| otherwise → revert "Unsupported batch version" | Rollup.sol:843-844 | matches |

## enc_go_v0 / enc_go_v1 (common/batch/batch_header.go)

| fact | repo file:line | verdict |
|---|---|---|
| V0 Bytes: zeroed `make([]byte, 249)`, byte0 = 0, field writes | common/batch/batch_header.go:212-230 (ops at 216-227) | matches |
| V0/V1 cache precondition (EncodedBytes returned verbatim) | batch_header.go:213-215, 241-243 | matches. The cache is assigned on a value receiver (228, 257), so it never persists. |
| V1 Bytes: zeroed 257, byte0 = 1, fields, PutUint64 at 249 | batch_header.go:240-259 (ops at 244-256) | matches |
| V1 struct embeds V0 + LastBlockNumber | batch_header.go:232-238 | matches |
| note "no Go encoder for version 2"; V2 reuses the V1 wire format | batch_header.go:19-23 | **true at codec level, but the facts miss one producer**. See difference D1. |

## ok_go / dec_go (`BatchHeaderBytes.validate` and getters)

| fact | repo file:line | verdict |
|---|---|---|
| empty → ErrEmptyBatchHeaderBytes (Version()) | batch_header.go:72-77 | matches |
| v0 len == 249, v1 len == 257, v2 len == 257, else ErrInvalidBatchHeaderVersion | batch_header.go:37-58 (constants 17-27, errors 31-33) | matches |
| guard: getters return None when validate fails | BatchIndex 79-84, L1MessagePopped 86-91, TotalL1MessagePopped 93-98, DataHash 100-105, PrevStateRoot 149-154, PostStateRoot 156-161, WithdrawalRoot 163-168, SequencerSetVerifyHash 170-175, ParentBatchHash 177-182, LastBlockNumber 184-193 | matches. Each getter calls validate() first. |
| Version(): b[0] | 72-77 | matches. **Version() does not validate**: it returns b[0] for any non-empty input. This affects L_dom_hdr replay: Version() succeeds on the witness while the other getters fail. |
| BlobCommitHash dispatches by version: BlobVersionedHash if v < 2, else BlobHashesHash, both b[57:89] | 107-147 | matches |
| LastBlockNumber errors for v < 1, else b[249:257] | 184-193 | matches |

## Differences and omissions (the facts were not edited)

- **D1 (L_par_hdr_v2, out of model scope).** The real Go v2 producer is
  `BatchCache.createBatchHeaderWithSequencerSetHash` in common/batch/batch_cache.go:1720-1731.
  It encodes a `BatchHeaderV1`, then patches the version byte: `h := batchHeaderV1.Bytes(); h[0] = BatchHeaderVersion2`.
  The facts model `enc_go_v1` as a closed encoder, so the codec-level obstruction is real,
  but at system level the call site resolves it. A finding needs the composed producer, which belongs to M1.
- **D2 (L_par_hdr_ssvh, intent).** `sealBatch` (batch_cache.go:1447-1462) rejects a
  nonzero sequencerSetVerifyHash for live batches. Nonzero is accepted only when replaying
  legacy batches at index <= `legacyCutoverBatchIndex` (field doc at batch_cache.go:85-88), and those batches
  were committed by the older contract. Meanwhile the Solidity encoder writes zero (Rollup.sol:351), and
  finalize/proof public input reads the field from the stored header (Rollup.sol:773).
  The Go side therefore deliberately enforces ssvh == 0 for live batches, so this law is an intent question and not a live defect.
- **D3 (duplicate decoder).** node/types/batch_header.go is a DEPRECATED duplicate of
  common/batch's `BatchHeaderBytes` (its header comment says tx-submitter/utils still imports it).
  It lacks `BlobCommitHash` and the encoders. Its validate and getters otherwise match common/batch.
  The facts cover only common/batch, so a second `dec_go` instance is uncovered.
- **D4 (A-dirty is harmless at this commit).** For v0 the writes cover bytes [0,249), and for v1/v2 they cover [0,257).
  storeLastBlockNumber writes 24 bytes past the header end (249+32 = 281 > 257), outside the
  hashed range. No unwritten byte reaches the hash, which matches PROVED for L_par_hdr_v0 and L_par_hdr_v1.
