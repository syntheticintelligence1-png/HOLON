# I22 mutant diff sheet: equivalent-mutant adjudication (HOLON M2, auditor A1)

Generated from the frozen I22 instrument spec/M2/lib/mutation_preregistration.json (its "mutants" list,
canonical JSON sha256 37e91910afde0955a0de040dd88750ae7bdaab1c3e9c19eec28267ab82bf4272)
and the pinned morph-l2/morph checkout at 3e44e795586af3e11285b603ab642c67823add51.
`python -m holon mutate sheet` reproduces this file byte for byte. It shows each of the 110 mutants as a unified
diff (3 lines of context) and nothing else: no prediction, no outcome. No mutant has been run.

## What the human decides, and when

Sign off the catalog first: the operators, their rewrite rules, the site rule, the in-scope list and the
predicted laws of spec/M2/lib/mutation_preregistration.json (docs/HUMAN_ANSWERS.md Q6). If you reject it,
write nothing: no mutant runs, and a replacement catalog is preregistered under a new key.

For every mutant: is it EQUIVALENT to the original program? Decide from this sheet (and the pinned source) alone,
before any mutant is run and without looking at spec/M2/predictions.json key I22,
prompts/I22_mutation_adequacy.md, tests_m2/test_mutation_adequacy.py (they hold the predictions) or any I22
result. Write the
verdicts to spec/M2/equivalent_mutants.json and commit that file alone (a commit that changes no other file).
`python -m holon mutate run` refuses to run any mutant until that file exists, covers every mutant and records
the catalog sign-off.

A mutant is equivalent iff, from every state the deployed code can reach, every call sequence through the public
entry points of the mutated contract or package gives the same observables on the original and on the mutant:
for Solidity the success or revert of each call, its revert data, its return data, the emitted events (topics and
data) and every storage slot; for Go the return values, the errors, whether it panics, and every byte of every
slice it returns or writes. Gas is not an observable. A mutant that is equivalent only on states the code cannot
reach is equivalent; one that differs on any reachable state is not. When unsure, say not equivalent and give the
reason; every equivalent verdict needs a reason.

Equivalent mutants leave the denominator of the non-equivalent kill rate (threshold 0.80, docs/HUMAN_ANSWERS.md Q6);
the rate over all 110 mutants is reported too. Every Solidity mutant changes the deployed bytecode of Rollup
(solc 0.8.24, optimizer off, cancun, metadata off), so none is trivially equivalent by compilation.

## The file to write: spec/M2/equivalent_mutants.json

```json
{"adjudication_version": "holon-equivalent-mutants/0.1",
 "mutants_sha256": "37e91910afde0955a0de040dd88750ae7bdaab1c3e9c19eec28267ab82bf4272",
 "diff_sheet_sha256": "<the sha256 of this file, recorded as diff_sheet.sha256 in the instrument>",
 "adjudicator": "human",
 "catalog_signed_off": true,
 "verdicts": {"M001": {"equivalent": false},
              "M002": {"equivalent": true, "reason": "<why no reachable observable differs>"},
              "...": "one entry per mutant, M001 to M110"}}
```

## Operators

- mstore_offset (-1, +1): the literal offset K of an inline-assembly mstore/mstore8(add(p, K), v) becomes K-1 or K+1.
- shl_width (-8, +8): the literal shift S of an inline-assembly shl(S, v) becomes S-8 or S+8 (a field one byte wider or narrower).
- drop_delete (drop): a `delete x;` statement becomes the empty block `{}`.
- swap_cursor (swap): a read of lastCommittedBatchIndex becomes lastFinalizedBatchIndex, and vice versa.
- cmp_boundary (flip): a Solidity `>=` becomes `>`, and `>` becomes `>=`.
- putuint64_offset (-1, +1): the literal K of binary.BigEndian.PutUint64(x[K:], v) becomes K-1 or K+1.
- copy_offset (-1, +1): the literal K of copy(x[K:], y) becomes K-1 or K+1.
- drop_len_check (drop): an `if` comparing len(..) with a constant whose body only returns an error becomes `{}`.

Every replacement keeps the file's line count, so line numbers in the diffs are the pinned file's.

## M001 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:34 BatchHeaderCodecV0.storeBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -141,7 +141,7 @@
     /// @param _batchIndex The batch index.
     function storeBatchIndex(uint256 batchPtr, uint256 _batchIndex) internal pure {
         assembly {
-            mstore(add(batchPtr, 1), shl(192, _batchIndex))
+            mstore(add(batchPtr, 0), shl(192, _batchIndex))
         }
     }
 
```

## M002 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:34 BatchHeaderCodecV0.storeBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -141,7 +141,7 @@
     /// @param _batchIndex The batch index.
     function storeBatchIndex(uint256 batchPtr, uint256 _batchIndex) internal pure {
         assembly {
-            mstore(add(batchPtr, 1), shl(192, _batchIndex))
+            mstore(add(batchPtr, 2), shl(192, _batchIndex))
         }
     }
 
```

## M003 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:34 BatchHeaderCodecV0.storeL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -152,7 +152,7 @@
     /// @param _l1MessagePopped The number of L1 messages popped in current batch.
     function storeL1MessagePopped(uint256 batchPtr, uint256 _l1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 9), shl(192, _l1MessagePopped))
+            mstore(add(batchPtr, 8), shl(192, _l1MessagePopped))
         }
     }
 
```

## M004 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:34 BatchHeaderCodecV0.storeL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -152,7 +152,7 @@
     /// @param _l1MessagePopped The number of L1 messages popped in current batch.
     function storeL1MessagePopped(uint256 batchPtr, uint256 _l1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 9), shl(192, _l1MessagePopped))
+            mstore(add(batchPtr, 10), shl(192, _l1MessagePopped))
         }
     }
 
```

## M005 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:34 BatchHeaderCodecV0.storeTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -163,7 +163,7 @@
     /// @param _totalL1MessagePopped The total number of L1 messages popped after current batch.
     function storeTotalL1MessagePopped(uint256 batchPtr, uint256 _totalL1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 17), shl(192, _totalL1MessagePopped))
+            mstore(add(batchPtr, 16), shl(192, _totalL1MessagePopped))
         }
     }
 
```

## M006 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:34 BatchHeaderCodecV0.storeTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -163,7 +163,7 @@
     /// @param _totalL1MessagePopped The total number of L1 messages popped after current batch.
     function storeTotalL1MessagePopped(uint256 batchPtr, uint256 _totalL1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 17), shl(192, _totalL1MessagePopped))
+            mstore(add(batchPtr, 18), shl(192, _totalL1MessagePopped))
         }
     }
 
```

## M007 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:175:34 BatchHeaderCodecV0.storeDataHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -172,7 +172,7 @@
     /// @param _dataHash The data hash.
     function storeDataHash(uint256 batchPtr, bytes32 _dataHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 25), _dataHash)
+            mstore(add(batchPtr, 24), _dataHash)
         }
     }
 
```

## M008 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:175:34 BatchHeaderCodecV0.storeDataHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -172,7 +172,7 @@
     /// @param _dataHash The data hash.
     function storeDataHash(uint256 batchPtr, bytes32 _dataHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 25), _dataHash)
+            mstore(add(batchPtr, 26), _dataHash)
         }
     }
 
```

## M009 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:184:34 BatchHeaderCodecV0.storeBlobVersionedHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -181,7 +181,7 @@
     /// @param _blobVersionedHash The versioned hash of the blob with this batch’s data.
     function storeBlobVersionedHash(uint256 batchPtr, bytes32 _blobVersionedHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 57), _blobVersionedHash)
+            mstore(add(batchPtr, 56), _blobVersionedHash)
         }
     }
 
```

## M010 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:184:34 BatchHeaderCodecV0.storeBlobVersionedHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -181,7 +181,7 @@
     /// @param _blobVersionedHash The versioned hash of the blob with this batch’s data.
     function storeBlobVersionedHash(uint256 batchPtr, bytes32 _blobVersionedHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 57), _blobVersionedHash)
+            mstore(add(batchPtr, 58), _blobVersionedHash)
         }
     }
 
```

## M011 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:193:34 BatchHeaderCodecV0.storePrevStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -190,7 +190,7 @@
     /// @param _prevStateHash The hash of the previous state to be stored.
     function storePrevStateHash(uint256 batchPtr, bytes32 _prevStateHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 89), _prevStateHash)
+            mstore(add(batchPtr, 88), _prevStateHash)
         }
     }
 
```

## M012 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:193:34 BatchHeaderCodecV0.storePrevStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -190,7 +190,7 @@
     /// @param _prevStateHash The hash of the previous state to be stored.
     function storePrevStateHash(uint256 batchPtr, bytes32 _prevStateHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 89), _prevStateHash)
+            mstore(add(batchPtr, 90), _prevStateHash)
         }
     }
 
```

## M013 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:202:34 BatchHeaderCodecV0.storePostStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -199,7 +199,7 @@
     /// @param _postStateHash The hash of the post-state to be stored.
     function storePostStateHash(uint256 batchPtr, bytes32 _postStateHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 121), _postStateHash)
+            mstore(add(batchPtr, 120), _postStateHash)
         }
     }
 
```

## M014 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:202:34 BatchHeaderCodecV0.storePostStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -199,7 +199,7 @@
     /// @param _postStateHash The hash of the post-state to be stored.
     function storePostStateHash(uint256 batchPtr, bytes32 _postStateHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 121), _postStateHash)
+            mstore(add(batchPtr, 122), _postStateHash)
         }
     }
 
```

## M015 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:211:34 BatchHeaderCodecV0.storeWithdrawRootHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -208,7 +208,7 @@
     /// @param _withdrawRootHash The hash of the withdrawal root to be stored.
     function storeWithdrawRootHash(uint256 batchPtr, bytes32 _withdrawRootHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 153), _withdrawRootHash)
+            mstore(add(batchPtr, 152), _withdrawRootHash)
         }
     }
 
```

## M016 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:211:34 BatchHeaderCodecV0.storeWithdrawRootHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -208,7 +208,7 @@
     /// @param _withdrawRootHash The hash of the withdrawal root to be stored.
     function storeWithdrawRootHash(uint256 batchPtr, bytes32 _withdrawRootHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 153), _withdrawRootHash)
+            mstore(add(batchPtr, 154), _withdrawRootHash)
         }
     }
 
```

## M017 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:220:34 BatchHeaderCodecV0.storeSequencerSetVerifyHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -217,7 +217,7 @@
     /// @param _sequencerSetVerifyHash The hash of the sequencer set to be stored.
     function storeSequencerSetVerifyHash(uint256 batchPtr, bytes32 _sequencerSetVerifyHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 185), _sequencerSetVerifyHash)
+            mstore(add(batchPtr, 184), _sequencerSetVerifyHash)
         }
     }
 
```

## M018 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:220:34 BatchHeaderCodecV0.storeSequencerSetVerifyHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -217,7 +217,7 @@
     /// @param _sequencerSetVerifyHash The hash of the sequencer set to be stored.
     function storeSequencerSetVerifyHash(uint256 batchPtr, bytes32 _sequencerSetVerifyHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 185), _sequencerSetVerifyHash)
+            mstore(add(batchPtr, 186), _sequencerSetVerifyHash)
         }
     }
 
```

## M019 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:229:34 BatchHeaderCodecV0.storeParentBatchHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -226,7 +226,7 @@
     /// @param _parentBatchHash The parent batch hash.
     function storeParentBatchHash(uint256 batchPtr, bytes32 _parentBatchHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 217), _parentBatchHash)
+            mstore(add(batchPtr, 216), _parentBatchHash)
         }
     }
 
```

## M020 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:229:34 BatchHeaderCodecV0.storeParentBatchHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -226,7 +226,7 @@
     /// @param _parentBatchHash The parent batch hash.
     function storeParentBatchHash(uint256 batchPtr, bytes32 _parentBatchHash) internal pure {
         assembly {
-            mstore(add(batchPtr, 217), _parentBatchHash)
+            mstore(add(batchPtr, 218), _parentBatchHash)
         }
     }
 
```

## M021 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:34 BatchHeaderCodecV1.storeLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -53,7 +53,7 @@
     /// @param _lastBlockNumber The last block number to store.
     function storeLastBlockNumber(uint256 batchPtr, uint256 _lastBlockNumber) internal pure {
         assembly {
-            mstore(add(batchPtr, 249), shl(192, _lastBlockNumber))
+            mstore(add(batchPtr, 248), shl(192, _lastBlockNumber))
         }
     }
 }
```

## M022 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:34 BatchHeaderCodecV1.storeLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -53,7 +53,7 @@
     /// @param _lastBlockNumber The last block number to store.
     function storeLastBlockNumber(uint256 batchPtr, uint256 _lastBlockNumber) internal pure {
         assembly {
-            mstore(add(batchPtr, 249), shl(192, _lastBlockNumber))
+            mstore(add(batchPtr, 250), shl(192, _lastBlockNumber))
         }
     }
 }
```

## M023 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:42 BatchHeaderCodecV0.storeBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -141,7 +141,7 @@
     /// @param _batchIndex The batch index.
     function storeBatchIndex(uint256 batchPtr, uint256 _batchIndex) internal pure {
         assembly {
-            mstore(add(batchPtr, 1), shl(192, _batchIndex))
+            mstore(add(batchPtr, 1), shl(184, _batchIndex))
         }
     }
 
```

## M024 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:42 BatchHeaderCodecV0.storeBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -141,7 +141,7 @@
     /// @param _batchIndex The batch index.
     function storeBatchIndex(uint256 batchPtr, uint256 _batchIndex) internal pure {
         assembly {
-            mstore(add(batchPtr, 1), shl(192, _batchIndex))
+            mstore(add(batchPtr, 1), shl(200, _batchIndex))
         }
     }
 
```

## M025 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:42 BatchHeaderCodecV0.storeL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -152,7 +152,7 @@
     /// @param _l1MessagePopped The number of L1 messages popped in current batch.
     function storeL1MessagePopped(uint256 batchPtr, uint256 _l1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 9), shl(192, _l1MessagePopped))
+            mstore(add(batchPtr, 9), shl(184, _l1MessagePopped))
         }
     }
 
```

## M026 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:42 BatchHeaderCodecV0.storeL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -152,7 +152,7 @@
     /// @param _l1MessagePopped The number of L1 messages popped in current batch.
     function storeL1MessagePopped(uint256 batchPtr, uint256 _l1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 9), shl(192, _l1MessagePopped))
+            mstore(add(batchPtr, 9), shl(200, _l1MessagePopped))
         }
     }
 
```

## M027 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:43 BatchHeaderCodecV0.storeTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -163,7 +163,7 @@
     /// @param _totalL1MessagePopped The total number of L1 messages popped after current batch.
     function storeTotalL1MessagePopped(uint256 batchPtr, uint256 _totalL1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 17), shl(192, _totalL1MessagePopped))
+            mstore(add(batchPtr, 17), shl(184, _totalL1MessagePopped))
         }
     }
 
```

## M028 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:43 BatchHeaderCodecV0.storeTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -163,7 +163,7 @@
     /// @param _totalL1MessagePopped The total number of L1 messages popped after current batch.
     function storeTotalL1MessagePopped(uint256 batchPtr, uint256 _totalL1MessagePopped) internal pure {
         assembly {
-            mstore(add(batchPtr, 17), shl(192, _totalL1MessagePopped))
+            mstore(add(batchPtr, 17), shl(200, _totalL1MessagePopped))
         }
     }
 
```

## M029 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:44 BatchHeaderCodecV1.storeLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -53,7 +53,7 @@
     /// @param _lastBlockNumber The last block number to store.
     function storeLastBlockNumber(uint256 batchPtr, uint256 _lastBlockNumber) internal pure {
         assembly {
-            mstore(add(batchPtr, 249), shl(192, _lastBlockNumber))
+            mstore(add(batchPtr, 249), shl(184, _lastBlockNumber))
         }
     }
 }
```

## M030 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:44 BatchHeaderCodecV1.storeLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -53,7 +53,7 @@
     /// @param _lastBlockNumber The last block number to store.
     function storeLastBlockNumber(uint256 batchPtr, uint256 _lastBlockNumber) internal pure {
         assembly {
-            mstore(add(batchPtr, 249), shl(192, _lastBlockNumber))
+            mstore(add(batchPtr, 249), shl(200, _lastBlockNumber))
         }
     }
 }
```

## M031 shl_width -8 contracts/contracts/l1/rollup/Rollup.sol:871:33 Rollup._commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -868,7 +868,7 @@
         }
 
         assembly {
-            mstore(dataPtr, shl(192, _lastBlockNumber)) // store lastBlockNumber
+            mstore(dataPtr, shl(184, _lastBlockNumber)) // store lastBlockNumber
             dataPtr := add(dataPtr, 8)
             mstore(dataPtr, shl(240, _numL1Messages)) // store numL1Messages
             dataPtr := add(dataPtr, 2)
```

## M032 shl_width +8 contracts/contracts/l1/rollup/Rollup.sol:871:33 Rollup._commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -868,7 +868,7 @@
         }
 
         assembly {
-            mstore(dataPtr, shl(192, _lastBlockNumber)) // store lastBlockNumber
+            mstore(dataPtr, shl(200, _lastBlockNumber)) // store lastBlockNumber
             dataPtr := add(dataPtr, 8)
             mstore(dataPtr, shl(240, _numL1Messages)) // store numL1Messages
             dataPtr := add(dataPtr, 2)
```

## M033 shl_width -8 contracts/contracts/l1/rollup/Rollup.sol:873:33 Rollup._commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -870,7 +870,7 @@
         assembly {
             mstore(dataPtr, shl(192, _lastBlockNumber)) // store lastBlockNumber
             dataPtr := add(dataPtr, 8)
-            mstore(dataPtr, shl(240, _numL1Messages)) // store numL1Messages
+            mstore(dataPtr, shl(232, _numL1Messages)) // store numL1Messages
             dataPtr := add(dataPtr, 2)
             mstore(0x40, add(dataPtr, mul(_numL1Messages, 0x20))) // reserve memory for l1 message hashes
         }
```

## M034 shl_width +8 contracts/contracts/l1/rollup/Rollup.sol:873:33 Rollup._commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -870,7 +870,7 @@
         assembly {
             mstore(dataPtr, shl(192, _lastBlockNumber)) // store lastBlockNumber
             dataPtr := add(dataPtr, 8)
-            mstore(dataPtr, shl(240, _numL1Messages)) // store numL1Messages
+            mstore(dataPtr, shl(248, _numL1Messages)) // store numL1Messages
             dataPtr := add(dataPtr, 2)
             mstore(0x40, add(dataPtr, mul(_numL1Messages, 0x20))) // reserve memory for l1 message hashes
         }
```

## M035 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:453:13 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -450,7 +450,7 @@
                 batchChallengeReward[challenges[_batchIndex].challenger] += challenges[_batchIndex].challengeDeposit;
                 inChallenge = false;
             }
-            delete challenges[_batchIndex];
+            {}
 
             if (revertReqIndex > 0 && _batchIndex == revertReqIndex) {
                 revertReqIndex = 0;
```

## M036 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:580:17 Rollup.setPause

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -577,7 +577,7 @@
             if (inChallenge) {
                 batchChallengeReward[challenges[batchChallenged].challenger] += challenges[batchChallenged]
                     .challengeDeposit;
-                delete challenges[batchChallenged];
+                {}
                 inChallenge = false;
             }
             emit Paused(_msgSender());
```

## M037 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:657:9 Rollup.finalizeBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -654,7 +654,7 @@
             BatchHeaderCodecV0.getL1MessagePopped(memPtr)
         );
 
-        delete batchDataStore[_batchIndex - 1];
+        {}
         delete committedStateRoots[_batchIndex - 1];
         delete batchBlobVersionedHashes[_batchIndex - 1];
         delete challenges[_batchIndex - 1];
```

## M038 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:658:9 Rollup.finalizeBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -655,7 +655,7 @@
         );
 
         delete batchDataStore[_batchIndex - 1];
-        delete committedStateRoots[_batchIndex - 1];
+        {}
         delete batchBlobVersionedHashes[_batchIndex - 1];
         delete challenges[_batchIndex - 1];
 
```

## M039 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:659:9 Rollup.finalizeBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -656,7 +656,7 @@
 
         delete batchDataStore[_batchIndex - 1];
         delete committedStateRoots[_batchIndex - 1];
-        delete batchBlobVersionedHashes[_batchIndex - 1];
+        {}
         delete challenges[_batchIndex - 1];
 
         emit FinalizeBatch(
```

## M040 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:660:9 Rollup.finalizeBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -657,7 +657,7 @@
         delete batchDataStore[_batchIndex - 1];
         delete committedStateRoots[_batchIndex - 1];
         delete batchBlobVersionedHashes[_batchIndex - 1];
-        delete challenges[_batchIndex - 1];
+        {}
 
         emit FinalizeBatch(
             _batchIndex,
```

## M041 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:312:32 Rollup._commitBatchWithBatchData

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -309,7 +309,7 @@
         (uint256 _batchPtr, bytes32 _parentBatchHash) = _loadBatchHeader(batchDataInput.parentBatchHeader);
         uint256 _batchIndex = BatchHeaderCodecV0.getBatchIndex(_batchPtr);
         require(committedBatches[_batchIndex + 1] == bytes32(0), "batch already committed");
-        require(_batchIndex == lastCommittedBatchIndex, "incorrect batch index");
+        require(_batchIndex == lastFinalizedBatchIndex, "incorrect batch index");
         require(committedBatches[_batchIndex] == _parentBatchHash, "incorrect parent batch hash");
         require(committedStateRoots[_batchIndex] == batchDataInput.prevStateRoot, "incorrect previous state root");
 
```

## M042 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:389:43 Rollup.commitBatchWithProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -386,7 +386,7 @@
     ) external override nonReqRevert whenNotPaused {
         // check delay timing - allow if EITHER batch submission OR L1 message processing is stalled
         // This enables permissionless batch submission when sequencers are offline or censoring
-        bool rollupDelay = batchDataStore[lastCommittedBatchIndex].originTimestamp + rollupDelayPeriod <
+        bool rollupDelay = batchDataStore[lastFinalizedBatchIndex].originTimestamp + rollupDelayPeriod <
             block.timestamp;
 
         // Check if L1 message queue is delayed
```

## M043 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:417:17 Rollup.commitBatchWithProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -414,7 +414,7 @@
         (uint256 memPtr, bytes32 _batchHash) = _loadBatchHeader(_batchHeader);
         // check batch hash
         uint256 _batchIndex = BatchHeaderCodecV0.getBatchIndex(memPtr);
-        require(lastCommittedBatchIndex == _batchIndex, "incorrect batch header");
+        require(lastFinalizedBatchIndex == _batchIndex, "incorrect batch header");
         require(committedBatches[_batchIndex] == _batchHash, "incorrect batch hash");
 
         // Override finalizeTimestamp for ZKP-backed immediate finality
```

## M044 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:441:31 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -438,7 +438,7 @@
         // make sure no gap is left when reverting from the ending to the beginning.
         require(committedBatches[_batchIndex + _count] == bytes32(0), "reverting must start from the ending");
         // check finalization
-        require(_batchIndex > lastFinalizedBatchIndex, "can only revert unFinalized batch");
+        require(_batchIndex > lastCommittedBatchIndex, "can only revert unFinalized batch");
 
         lastCommittedBatchIndex = _batchIndex - 1;
         while (_count > 0) {
```

## M045 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:476:17 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -473,7 +473,7 @@
         bytes32 _batchHash
     ) external payable onlyChallenger nonReqRevert whenNotPaused {
         require(!inChallenge, "already in challenge");
-        require(lastFinalizedBatchIndex < batchIndex, "batch already finalized");
+        require(lastCommittedBatchIndex < batchIndex, "batch already finalized");
         require(committedBatches[batchIndex] == _batchHash, "incorrect batch hash");
         require(batchExist(batchIndex), "batch not exist");
         require(challenges[batchIndex].challenger == address(0), "batch already challenged");
```

## M046 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:489:26 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -486,7 +486,7 @@
         challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);
         emit ChallengeState(batchIndex, _msgSender(), msg.value);
 
-        for (uint256 i = lastFinalizedBatchIndex + 1; i <= lastCommittedBatchIndex; i++) {
+        for (uint256 i = lastCommittedBatchIndex + 1; i <= lastCommittedBatchIndex; i++) {
             if (i != batchIndex) {
                 batchDataStore[i].finalizeTimestamp += proofWindow;
             }
```

## M047 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:489:60 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -486,7 +486,7 @@
         challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);
         emit ChallengeState(batchIndex, _msgSender(), msg.value);
 
-        for (uint256 i = lastFinalizedBatchIndex + 1; i <= lastCommittedBatchIndex; i++) {
+        for (uint256 i = lastFinalizedBatchIndex + 1; i <= lastFinalizedBatchIndex; i++) {
             if (i != batchIndex) {
                 batchDataStore[i].finalizeTimestamp += proofWindow;
             }
```

## M048 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:643:21 Rollup.finalizeBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -640,7 +640,7 @@
         require(finalizedStateRoots[_batchIndex] == bytes32(0), "batch already verified");
         // check and update lastFinalizedBatchIndex
         unchecked {
-            require(lastFinalizedBatchIndex + 1 == _batchIndex, "incorrect batch index");
+            require(lastCommittedBatchIndex + 1 == _batchIndex, "incorrect batch index");
             lastFinalizedBatchIndex = _batchIndex;
         }
 
```

## M049 cmp_boundary flip contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:32:24 BatchHeaderCodecV0.loadAndValidate

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -29,7 +29,7 @@
     /// @return length The length in bytes of the batch header.
     function loadAndValidate(bytes calldata _batchHeader) internal pure returns (uint256 batchPtr, uint256 length) {
         length = _batchHeader.length;
-        require(length >= BATCH_HEADER_LENGTH, "batch header length too small");
+        require(length > BATCH_HEADER_LENGTH, "batch header length too small");
         // copy batch header to memory.
         assembly {
             batchPtr := mload(0x40)
```

## M050 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:265:50 Rollup.commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -262,7 +262,7 @@
         if (
             IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod < block.timestamp
         ) {
-            require(batchDataInput.numL1Messages > 0, "l1msg delay");
+            require(batchDataInput.numL1Messages >= 0, "l1msg delay");
         }
         bytes32 _blobVersionedHash = _computeBlobVersionedHash(batchDataInput.version);
         _commitBatchWithBatchData(batchDataInput, _msgSender(), _blobVersionedHash);
```

## M051 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:283:50 Rollup.commitState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -280,7 +280,7 @@
         if (
             IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod < block.timestamp
         ) {
-            require(batchDataInput.numL1Messages > 0, "l1msg delay");
+            require(batchDataInput.numL1Messages >= 0, "l1msg delay");
         }
         _commitBatchWithBatchData(batchDataInput, _msgSender(), batchBlobVersionedHashes[_nextBatchIndex]);
     }
```

## M052 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:333:40 Rollup._commitBatchWithBatchData

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -330,7 +330,7 @@
         {
             // Determine header length: V0 = 249, V1/V2 = 257
             uint256 _headerLength = BatchHeaderCodecV0.BATCH_HEADER_LENGTH;
-            if (batchDataInput.version >= 1) {
+            if (batchDataInput.version > 1) {
                 _headerLength = BatchHeaderCodecV1.BATCH_HEADER_LENGTH;
             }
             assembly {
```

## M053 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:353:40 Rollup._commitBatchWithBatchData

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -350,7 +350,7 @@
             BatchHeaderCodecV0.storeWithdrawRootHash(_batchPtr, batchDataInput.withdrawalRoot);
             BatchHeaderCodecV0.storeSequencerSetVerifyHash(_batchPtr, bytes32(0));
             BatchHeaderCodecV0.storeParentBatchHash(_batchPtr, _parentBatchHash);
-            if (batchDataInput.version >= 1) {
+            if (batchDataInput.version > 1) {
                 BatchHeaderCodecV1.storeLastBlockNumber(_batchPtr, batchDataInput.lastBlockNumber);
             }
 
```

## M054 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:398:50 Rollup.commitBatchWithProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -395,7 +395,7 @@
             block.timestamp;
 
         if (!rollupDelay && l1MsgQueueDelayed) {
-            require(batchDataInput.numL1Messages > 0, "l1msg delay");
+            require(batchDataInput.numL1Messages >= 0, "l1msg delay");
         }
         require(rollupDelay || l1MsgQueueDelayed, "invalid timing");
         // check if the next batch has a stored blob hash
```

## M055 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:431:24 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -428,7 +428,7 @@
     /// @dev If the owner wants to revert a sequence of batches by sending multiple transactions,
     ///      make sure to revert recent batches first.
     function revertBatch(bytes calldata _batchHeader, uint256 _count) external onlyOwner {
-        require(_count > 0, "count must be nonzero");
+        require(_count >= 0, "count must be nonzero");
 
         (uint256 memPtr, bytes32 _batchHash) = _loadBatchHeader(_batchHeader);
         // check batch hash
```

## M056 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:441:29 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -438,7 +438,7 @@
         // make sure no gap is left when reverting from the ending to the beginning.
         require(committedBatches[_batchIndex + _count] == bytes32(0), "reverting must start from the ending");
         // check finalization
-        require(_batchIndex > lastFinalizedBatchIndex, "can only revert unFinalized batch");
+        require(_batchIndex >= lastFinalizedBatchIndex, "can only revert unFinalized batch");
 
         lastCommittedBatchIndex = _batchIndex - 1;
         while (_count > 0) {
```

## M057 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:444:23 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -441,7 +441,7 @@
         require(_batchIndex > lastFinalizedBatchIndex, "can only revert unFinalized batch");
 
         lastCommittedBatchIndex = _batchIndex - 1;
-        while (_count > 0) {
+        while (_count >= 0) {
             emit RevertBatch(_batchIndex, _batchHash);
 
             committedBatches[_batchIndex] = bytes32(0);
```

## M058 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:455:32 Rollup.revertBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -452,7 +452,7 @@
             }
             delete challenges[_batchIndex];
 
-            if (revertReqIndex > 0 && _batchIndex == revertReqIndex) {
+            if (revertReqIndex >= 0 && _batchIndex == revertReqIndex) {
                 revertReqIndex = 0;
             }
 
```

## M059 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:483:27 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -480,7 +480,7 @@
         // check challenge window
         require(batchInsideChallengeWindow(batchIndex), "cannot challenge batch outside the challenge window");
         // check challenge amount
-        require(msg.value >= ISubmitter(submitterContract).challengeDeposit(), "insufficient value");
+        require(msg.value > ISubmitter(submitterContract).challengeDeposit(), "insufficient value");
 
         batchChallenged = batchIndex;
         challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);
```

## M060 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:704:59 Rollup.batchExist

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -701,7 +701,7 @@
     /// @dev Public function to checks whether batch exists.
     /// @param batchIndex The index of the batch to be checked.
     function batchExist(uint256 batchIndex) public view returns (bool) {
-        return batchDataStore[batchIndex].originTimestamp > 0 && committedBatches[batchIndex] != bytes32(0);
+        return batchDataStore[batchIndex].originTimestamp >= 0 && committedBatches[batchIndex] != bytes32(0);
     }
 
     /// @dev Public function to checks whether the batch is in challengeWindow.
```

## M061 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:710:61 Rollup.batchInsideChallengeWindow

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -707,7 +707,7 @@
     /// @dev Public function to checks whether the batch is in challengeWindow.
     /// @param batchIndex The index of the batch to be checked.
     function batchInsideChallengeWindow(uint256 batchIndex) public view returns (bool) {
-        return batchDataStore[batchIndex].finalizeTimestamp > block.timestamp;
+        return batchDataStore[batchIndex].finalizeTimestamp >= block.timestamp;
     }
 
     /// @dev proveCommittedBatchState verifies the ZK proof for a committed batch.
```

## M062 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:758:36 Rollup._verifyProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -755,7 +755,7 @@
     /// @dev Internal function to verify the zk proof.
     function _verifyProof(uint256 memPtr, bytes calldata _batchProof) private view {
         // Check validity of proof
-        require(_batchProof.length > 0, "Invalid batch proof");
+        require(_batchProof.length >= 0, "Invalid batch proof");
 
         uint256 _batchIndex = BatchHeaderCodecV0.getBatchIndex(memPtr);
 
```

## M063 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:825:36 Rollup._getBatchVersion

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -822,7 +822,7 @@
     /// @param batchHeader The encoded batch header bytes
     /// @return version The version of the batch header
     function _getBatchVersion(bytes calldata batchHeader) internal pure returns (uint8 version) {
-        require(batchHeader.length > 0, "Empty batch header");
+        require(batchHeader.length >= 0, "Empty batch header");
         version = uint8(batchHeader[0]); // Safe extraction of the first byte
     }
 
```

## M064 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:913:32 Rollup._computeBlobVersionedHash

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -910,7 +910,7 @@
                 _blobVersionedHash := keccak256(scratchPtr, mul(i, 32))
                 mstore(0x40, add(scratchPtr, mul(i, 32)))
             }
-            require(_blobCount > 0, "V2 requires at least 1 blob");
+            require(_blobCount >= 0, "V2 requires at least 1 blob");
         } else {
             require(blobhash(1) == bytes32(0), "legacy batches support exactly 1 blob");
             _blobVersionedHash = (blobhash(0) == bytes32(0)) ? ZERO_VERSIONED_HASH : blobhash(0);
```

## M065 putuint64_offset -1 common/batch/batch_header.go:218:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -215,7 +215,7 @@
 	}
 	batchBytes := make([]byte, expectedLengthV0)
 	batchBytes[0] = BatchHeaderVersion0
-	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
+	binary.BigEndian.PutUint64(batchBytes[0:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
```

## M066 putuint64_offset +1 common/batch/batch_header.go:218:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -215,7 +215,7 @@
 	}
 	batchBytes := make([]byte, expectedLengthV0)
 	batchBytes[0] = BatchHeaderVersion0
-	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
+	binary.BigEndian.PutUint64(batchBytes[2:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
```

## M067 putuint64_offset -1 common/batch/batch_header.go:219:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -216,7 +216,7 @@
 	batchBytes := make([]byte, expectedLengthV0)
 	batchBytes[0] = BatchHeaderVersion0
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
-	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[8:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
```

## M068 putuint64_offset +1 common/batch/batch_header.go:219:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -216,7 +216,7 @@
 	batchBytes := make([]byte, expectedLengthV0)
 	batchBytes[0] = BatchHeaderVersion0
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
-	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[10:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
```

## M069 putuint64_offset -1 common/batch/batch_header.go:220:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -217,7 +217,7 @@
 	batchBytes[0] = BatchHeaderVersion0
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
-	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[16:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
```

## M070 putuint64_offset +1 common/batch/batch_header.go:220:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -217,7 +217,7 @@
 	batchBytes[0] = BatchHeaderVersion0
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
-	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[18:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
```

## M071 putuint64_offset -1 common/batch/batch_header.go:246:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -243,7 +243,7 @@
 	}
 	batchBytes := make([]byte, expectedLengthV1)
 	batchBytes[0] = BatchHeaderVersion1
-	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
+	binary.BigEndian.PutUint64(batchBytes[0:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
```

## M072 putuint64_offset +1 common/batch/batch_header.go:246:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -243,7 +243,7 @@
 	}
 	batchBytes := make([]byte, expectedLengthV1)
 	batchBytes[0] = BatchHeaderVersion1
-	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
+	binary.BigEndian.PutUint64(batchBytes[2:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
```

## M073 putuint64_offset -1 common/batch/batch_header.go:247:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -244,7 +244,7 @@
 	batchBytes := make([]byte, expectedLengthV1)
 	batchBytes[0] = BatchHeaderVersion1
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
-	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[8:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
```

## M074 putuint64_offset +1 common/batch/batch_header.go:247:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -244,7 +244,7 @@
 	batchBytes := make([]byte, expectedLengthV1)
 	batchBytes[0] = BatchHeaderVersion1
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
-	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[10:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
```

## M075 putuint64_offset -1 common/batch/batch_header.go:248:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -245,7 +245,7 @@
 	batchBytes[0] = BatchHeaderVersion1
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
-	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[16:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
```

## M076 putuint64_offset +1 common/batch/batch_header.go:248:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -245,7 +245,7 @@
 	batchBytes[0] = BatchHeaderVersion1
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
-	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
+	binary.BigEndian.PutUint64(batchBytes[18:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
```

## M077 putuint64_offset -1 common/batch/batch_header.go:256:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -253,7 +253,7 @@
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
-	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
+	binary.BigEndian.PutUint64(batchBytes[248:], b.LastBlockNumber)
 
 	b.EncodedBytes = batchBytes
 	return batchBytes
```

## M078 putuint64_offset +1 common/batch/batch_header.go:256:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -253,7 +253,7 @@
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
-	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
+	binary.BigEndian.PutUint64(batchBytes[250:], b.LastBlockNumber)
 
 	b.EncodedBytes = batchBytes
 	return batchBytes
```

## M079 copy_offset -1 common/batch/batch_header.go:221:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -218,7 +218,7 @@
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
-	copy(batchBytes[25:], b.DataHash[:])
+	copy(batchBytes[24:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
```

## M080 copy_offset +1 common/batch/batch_header.go:221:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -218,7 +218,7 @@
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
-	copy(batchBytes[25:], b.DataHash[:])
+	copy(batchBytes[26:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
```

## M081 copy_offset -1 common/batch/batch_header.go:222:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -219,7 +219,7 @@
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
-	copy(batchBytes[57:], b.BlobVersionedHash[:])
+	copy(batchBytes[56:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
```

## M082 copy_offset +1 common/batch/batch_header.go:222:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -219,7 +219,7 @@
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
-	copy(batchBytes[57:], b.BlobVersionedHash[:])
+	copy(batchBytes[58:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
```

## M083 copy_offset -1 common/batch/batch_header.go:223:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -220,7 +220,7 @@
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
-	copy(batchBytes[89:], b.PrevStateRoot[:])
+	copy(batchBytes[88:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
```

## M084 copy_offset +1 common/batch/batch_header.go:223:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -220,7 +220,7 @@
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
-	copy(batchBytes[89:], b.PrevStateRoot[:])
+	copy(batchBytes[90:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
```

## M085 copy_offset -1 common/batch/batch_header.go:224:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -221,7 +221,7 @@
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
-	copy(batchBytes[121:], b.PostStateRoot[:])
+	copy(batchBytes[120:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
```

## M086 copy_offset +1 common/batch/batch_header.go:224:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -221,7 +221,7 @@
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
-	copy(batchBytes[121:], b.PostStateRoot[:])
+	copy(batchBytes[122:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
```

## M087 copy_offset -1 common/batch/batch_header.go:225:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -222,7 +222,7 @@
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
-	copy(batchBytes[153:], b.WithdrawalRoot[:])
+	copy(batchBytes[152:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
```

## M088 copy_offset +1 common/batch/batch_header.go:225:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -222,7 +222,7 @@
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
-	copy(batchBytes[153:], b.WithdrawalRoot[:])
+	copy(batchBytes[154:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
```

## M089 copy_offset -1 common/batch/batch_header.go:226:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -223,7 +223,7 @@
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
-	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
+	copy(batchBytes[184:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
 	return batchBytes
```

## M090 copy_offset +1 common/batch/batch_header.go:226:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -223,7 +223,7 @@
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
-	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
+	copy(batchBytes[186:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
 	return batchBytes
```

## M091 copy_offset -1 common/batch/batch_header.go:227:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -224,7 +224,7 @@
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
-	copy(batchBytes[217:], b.ParentBatchHash[:])
+	copy(batchBytes[216:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
 	return batchBytes
 }
```

## M092 copy_offset +1 common/batch/batch_header.go:227:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -224,7 +224,7 @@
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
-	copy(batchBytes[217:], b.ParentBatchHash[:])
+	copy(batchBytes[218:], b.ParentBatchHash[:])
 	b.EncodedBytes = batchBytes
 	return batchBytes
 }
```

## M093 copy_offset -1 common/batch/batch_header.go:249:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -246,7 +246,7 @@
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
-	copy(batchBytes[25:], b.DataHash[:])
+	copy(batchBytes[24:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
```

## M094 copy_offset +1 common/batch/batch_header.go:249:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -246,7 +246,7 @@
 	binary.BigEndian.PutUint64(batchBytes[1:], b.BatchIndex)
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
-	copy(batchBytes[25:], b.DataHash[:])
+	copy(batchBytes[26:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
```

## M095 copy_offset -1 common/batch/batch_header.go:250:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -247,7 +247,7 @@
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
-	copy(batchBytes[57:], b.BlobVersionedHash[:])
+	copy(batchBytes[56:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
```

## M096 copy_offset +1 common/batch/batch_header.go:250:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -247,7 +247,7 @@
 	binary.BigEndian.PutUint64(batchBytes[9:], b.L1MessagePopped)
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
-	copy(batchBytes[57:], b.BlobVersionedHash[:])
+	copy(batchBytes[58:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
```

## M097 copy_offset -1 common/batch/batch_header.go:251:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -248,7 +248,7 @@
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
-	copy(batchBytes[89:], b.PrevStateRoot[:])
+	copy(batchBytes[88:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
```

## M098 copy_offset +1 common/batch/batch_header.go:251:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -248,7 +248,7 @@
 	binary.BigEndian.PutUint64(batchBytes[17:], b.TotalL1MessagePopped)
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
-	copy(batchBytes[89:], b.PrevStateRoot[:])
+	copy(batchBytes[90:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
```

## M099 copy_offset -1 common/batch/batch_header.go:252:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -249,7 +249,7 @@
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
-	copy(batchBytes[121:], b.PostStateRoot[:])
+	copy(batchBytes[120:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
```

## M100 copy_offset +1 common/batch/batch_header.go:252:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -249,7 +249,7 @@
 	copy(batchBytes[25:], b.DataHash[:])
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
-	copy(batchBytes[121:], b.PostStateRoot[:])
+	copy(batchBytes[122:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
```

## M101 copy_offset -1 common/batch/batch_header.go:253:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -250,7 +250,7 @@
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
-	copy(batchBytes[153:], b.WithdrawalRoot[:])
+	copy(batchBytes[152:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
```

## M102 copy_offset +1 common/batch/batch_header.go:253:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -250,7 +250,7 @@
 	copy(batchBytes[57:], b.BlobVersionedHash[:])
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
-	copy(batchBytes[153:], b.WithdrawalRoot[:])
+	copy(batchBytes[154:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
```

## M103 copy_offset -1 common/batch/batch_header.go:254:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -251,7 +251,7 @@
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
-	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
+	copy(batchBytes[184:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
 
```

## M104 copy_offset +1 common/batch/batch_header.go:254:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -251,7 +251,7 @@
 	copy(batchBytes[89:], b.PrevStateRoot[:])
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
-	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
+	copy(batchBytes[186:], b.SequencerSetVerifyHash[:])
 	copy(batchBytes[217:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
 
```

## M105 copy_offset -1 common/batch/batch_header.go:255:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -252,7 +252,7 @@
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
-	copy(batchBytes[217:], b.ParentBatchHash[:])
+	copy(batchBytes[216:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
 
 	b.EncodedBytes = batchBytes
```

## M106 copy_offset +1 common/batch/batch_header.go:255:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -252,7 +252,7 @@
 	copy(batchBytes[121:], b.PostStateRoot[:])
 	copy(batchBytes[153:], b.WithdrawalRoot[:])
 	copy(batchBytes[185:], b.SequencerSetVerifyHash[:])
-	copy(batchBytes[217:], b.ParentBatchHash[:])
+	copy(batchBytes[218:], b.ParentBatchHash[:])
 	binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)
 
 	b.EncodedBytes = batchBytes
```

## M107 drop_len_check drop common/batch/batch_header.go:44:3 (morph-l2/common/batch.BatchHeaderBytes).validate

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -41,9 +41,9 @@
 	}
 	switch version {
 	case BatchHeaderVersion0:
-		if len(b) != expectedLengthV0 {
-			return ErrInvalidBatchHeaderLength
-		}
+		{}
+
+
 	case BatchHeaderVersion1:
 		if len(b) != expectedLengthV1 {
 			return ErrInvalidBatchHeaderLength
```

## M108 drop_len_check drop common/batch/batch_header.go:48:3 (morph-l2/common/batch.BatchHeaderBytes).validate

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -45,9 +45,9 @@
 			return ErrInvalidBatchHeaderLength
 		}
 	case BatchHeaderVersion1:
-		if len(b) != expectedLengthV1 {
-			return ErrInvalidBatchHeaderLength
-		}
+		{}
+
+
 	case BatchHeaderVersion2:
 		if len(b) != expectedLengthV2 {
 			return ErrInvalidBatchHeaderLength
```

## M109 drop_len_check drop common/batch/batch_header.go:52:3 (morph-l2/common/batch.BatchHeaderBytes).validate

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -49,9 +49,9 @@
 			return ErrInvalidBatchHeaderLength
 		}
 	case BatchHeaderVersion2:
-		if len(b) != expectedLengthV2 {
-			return ErrInvalidBatchHeaderLength
-		}
+		{}
+
+
 	default:
 		return ErrInvalidBatchHeaderVersion
 	}
```

## M110 drop_len_check drop common/batch/batch_header.go:73:2 (morph-l2/common/batch.BatchHeaderBytes).Version

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -70,9 +70,9 @@
 }
 
 func (b BatchHeaderBytes) Version() (uint8, error) {
-	if len(b) == 0 {
-		return 0, ErrEmptyBatchHeaderBytes
-	}
+	{}
+
+
 	return b[0], nil
 }
 
```
