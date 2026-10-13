# I60 mutant diff sheet: equivalent-mutant adjudication (HOLON M2, auditor A1, replacement catalog)

Generated from the frozen I60 instrument spec/M2/lib/mutation_catalog_i60.json (its "mutants" list, canonical JSON
sha256 eccefd69d69138492c1a387afddba644b84767059cde10163d5044fcaf3dc24a)
and the pinned morph-l2/morph checkout at 3e44e795586af3e11285b603ab642c67823add51 (OpenZeppelin units from config/holon.json
replay.sol_deps). `python -m holon mutate sheet` reproduces this file byte for byte. It shows each of the 242 mutants
(192 in stratum A, ids A..., 50 in stratum B, ids B...) as a unified diff with 3 lines of context, and nothing
else: no prediction, no outcome. No mutant has been run.

## What the panel decides

For every mutant: is it EQUIVALENT to the original program? Decide from this sheet and the pinned sources alone.
Do not read spec/M2/predictions.json key I60, prompts/I60_mutation_replacement.md,
tests_m2/test_mutation_adequacy_i60.py, docs/iterations/ or any I60 result: they hold the predictions.

A mutant is equivalent iff, from every state the deployed code can reach, every call sequence through the public
entry points gives the same observables on the original and on the mutant. Solidity: the entry points are those of
Rollup, the deployed contract that the codec libraries and the inherited OpenZeppelin contracts compile into (its
external and public functions and receive); the observables are the success or revert of each call, its revert
data, its return data, the emitted events (topics and data) and every storage slot. Go: the entry points are the
exported functions and methods of the mutated package; the observables are the return values, the errors, whether
a call panics, and every byte of every slice returned or written. Gas is not an observable. A mutant that differs
only on states the code cannot reach is equivalent; one that differs on any reachable state is not. When unsure,
say not equivalent. Every equivalent verdict needs a reason.

These mutants leave Rollup's deployed bytecode unchanged (solc 0.8.24, optimizer off, cancun, no metadata): A110, A111, A112, A113, A121, A122.
They are equivalent by construction.

Duplicate candidates (one operator, one statement): {A050, A051}. For each group, say which mutants give the same
observables as the group's lowest id on every reachable state.

The verdicts go to spec/M2/equivalent_mutants_i60.json (the format is in the instrument's "adjudication" field),
committed alone, after the catalog review and before any run. Equivalent mutants leave the denominator of the
non-equivalent kill rate; the rate over all mutants is reported too.

## Operators

- mstore_offset (-1, +1): the literal offset K of an inline-assembly mstore/mstore8(add(p, K), v) becomes K-1 or K+1.
- shl_width (-8, +8): the literal shift S of an inline-assembly shl(S, v) becomes S-8 or S+8.
- drop_delete (drop): a `delete x;` statement becomes the empty block `{}`.
- swap_cursor (swap): a read of lastCommittedBatchIndex becomes lastFinalizedBatchIndex, and vice versa.
- cmp_boundary (flip): a Solidity `>=` becomes `>`, and `>` becomes `>=`.
- cmp_boundary_mirror (flip): a Solidity `<=` becomes `<`, and `<` becomes `<=`.
- mload_offset (-1, +1): the literal offset K of an inline-assembly mload(add(p, K)) becomes K-1 or K+1.
- shr_width (-8, +8): the literal shift S of an inline-assembly shr(S, v) becomes S-8 or S+8.
- putuint64_offset (-1, +1): the literal K of binary.BigEndian.PutUint64(x[K:], v) becomes K-1 or K+1.
- copy_offset (-1, +1): the literal K of copy(x[K:], y) becomes K-1 or K+1.
- drop_len_check (drop): an `if` comparing len(..) with a constant whose body only returns an error becomes `{}`.
- go_slice_offset (-1, +1): a read slice x[K1:K2] with literal bounds becomes x[K1-1:K2-1] or x[K1+1:K2+1].

Every replacement keeps the file's line count, so line numbers in the diffs are the pinned file's.

## A001 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:34 BatchHeaderCodecV0.storeBatchIndex

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

## A002 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:34 BatchHeaderCodecV0.storeBatchIndex

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

## A003 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:34 BatchHeaderCodecV0.storeL1MessagePopped

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

## A004 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:34 BatchHeaderCodecV0.storeL1MessagePopped

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

## A005 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:34 BatchHeaderCodecV0.storeTotalL1MessagePopped

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

## A006 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:34 BatchHeaderCodecV0.storeTotalL1MessagePopped

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

## A007 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:175:34 BatchHeaderCodecV0.storeDataHash

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

## A008 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:175:34 BatchHeaderCodecV0.storeDataHash

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

## A009 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:184:34 BatchHeaderCodecV0.storeBlobVersionedHash

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

## A010 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:184:34 BatchHeaderCodecV0.storeBlobVersionedHash

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

## A011 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:193:34 BatchHeaderCodecV0.storePrevStateHash

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

## A012 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:193:34 BatchHeaderCodecV0.storePrevStateHash

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

## A013 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:202:34 BatchHeaderCodecV0.storePostStateHash

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

## A014 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:202:34 BatchHeaderCodecV0.storePostStateHash

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

## A015 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:211:34 BatchHeaderCodecV0.storeWithdrawRootHash

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

## A016 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:211:34 BatchHeaderCodecV0.storeWithdrawRootHash

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

## A017 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:220:34 BatchHeaderCodecV0.storeSequencerSetVerifyHash

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

## A018 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:220:34 BatchHeaderCodecV0.storeSequencerSetVerifyHash

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

## A019 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:229:34 BatchHeaderCodecV0.storeParentBatchHash

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

## A020 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:229:34 BatchHeaderCodecV0.storeParentBatchHash

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

## A021 mstore_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:34 BatchHeaderCodecV1.storeLastBlockNumber

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

## A022 mstore_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:34 BatchHeaderCodecV1.storeLastBlockNumber

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

## A023 shl_width -8 contracts/contracts/l1/rollup/Rollup.sol:871:33 Rollup._commitBatch

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

## A024 shl_width +8 contracts/contracts/l1/rollup/Rollup.sol:871:33 Rollup._commitBatch

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

## A025 shl_width -8 contracts/contracts/l1/rollup/Rollup.sol:873:33 Rollup._commitBatch

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

## A026 shl_width +8 contracts/contracts/l1/rollup/Rollup.sol:873:33 Rollup._commitBatch

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

## A027 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:42 BatchHeaderCodecV0.storeBatchIndex

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

## A028 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144:42 BatchHeaderCodecV0.storeBatchIndex

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

## A029 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:42 BatchHeaderCodecV0.storeL1MessagePopped

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

## A030 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:155:42 BatchHeaderCodecV0.storeL1MessagePopped

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

## A031 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:43 BatchHeaderCodecV0.storeTotalL1MessagePopped

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

## A032 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166:43 BatchHeaderCodecV0.storeTotalL1MessagePopped

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

## A033 shl_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:44 BatchHeaderCodecV1.storeLastBlockNumber

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

## A034 shl_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:56:44 BatchHeaderCodecV1.storeLastBlockNumber

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

## A035 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:453:13 Rollup.revertBatch

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

## A036 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:580:17 Rollup.setPause

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

## A037 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:657:9 Rollup.finalizeBatch

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

## A038 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:658:9 Rollup.finalizeBatch

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

## A039 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:659:9 Rollup.finalizeBatch

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

## A040 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:660:9 Rollup.finalizeBatch

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

## A041 drop_delete drop contracts/contracts/l1/rollup/Rollup.sol:675:9 Rollup.claimReward

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -672,7 +672,7 @@
     function claimReward(address receiver) external {
         uint256 amount = batchChallengeReward[_msgSender()];
         require(amount != 0, "invalid batchChallengeReward");
-        delete batchChallengeReward[_msgSender()];
+        {}
         _transfer(receiver, amount);
         emit ChallengeRewardClaim(receiver, amount);
     }
```

## A042 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:192:33 Rollup.initialize2

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -189,7 +189,7 @@
         require(_getInitializedVersion() == 2, "must have initialized!");
         require(_prevStateRoot != bytes32(0), "can not set state root with bytes32(0)!");
 
-        if (committedStateRoots[lastCommittedBatchIndex] == bytes32(0)) {
+        if (committedStateRoots[lastFinalizedBatchIndex] == bytes32(0)) {
             committedStateRoots[lastCommittedBatchIndex] = _prevStateRoot;
         }
     }
```

## A043 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:193:33 Rollup.initialize2

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -190,7 +190,7 @@
         require(_prevStateRoot != bytes32(0), "can not set state root with bytes32(0)!");
 
         if (committedStateRoots[lastCommittedBatchIndex] == bytes32(0)) {
-            committedStateRoots[lastCommittedBatchIndex] = _prevStateRoot;
+            committedStateRoots[lastFinalizedBatchIndex] = _prevStateRoot;
         }
     }
 
```

## A044 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:212:17 Rollup.initialize4

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -209,7 +209,7 @@
     function initialize4(address _newSubmitter, uint256 _expectedLegacyCutoverBatchIndex) external reinitializer(4) {
         require(_msgSender() == _getProxyAdmin(), "only proxy admin");
         require(_newSubmitter != address(0) && _newSubmitter.code.length > 0, "invalid submitter");
-        require(lastCommittedBatchIndex == _expectedLegacyCutoverBatchIndex, "cutover batch mismatch");
+        require(lastFinalizedBatchIndex == _expectedLegacyCutoverBatchIndex, "cutover batch mismatch");
         require(!inChallenge, "challenge in progress");
         require(revertReqIndex == 0, "pending revert request");
 
```

## A045 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:312:32 Rollup._commitBatchWithBatchData

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

## A046 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:389:43 Rollup.commitBatchWithProof

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

## A047 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:417:17 Rollup.commitBatchWithProof

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

## A048 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:441:31 Rollup.revertBatch

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

## A049 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:476:17 Rollup.challengeState

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

## A050 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:489:26 Rollup.challengeState

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

## A051 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:489:60 Rollup.challengeState

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

## A052 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:643:21 Rollup.finalizeBatch

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

## A053 swap_cursor swap contracts/contracts/l1/rollup/Rollup.sol:686:31 Rollup.isBatchFinalized

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -683,7 +683,7 @@
 
     /// @inheritdoc IRollup
     function isBatchFinalized(uint256 _batchIndex) external view override returns (bool) {
-        return _batchIndex <= lastFinalizedBatchIndex;
+        return _batchIndex <= lastCommittedBatchIndex;
     }
 
     /// @dev Public function to checks whether the batch is in challenge.
```

## A054 cmp_boundary flip @openzeppelin/contracts-upgradeable/utils/AddressUpgradeable.sol:45:36 AddressUpgradeable.isContract

```diff
--- a/@openzeppelin/contracts-upgradeable/utils/AddressUpgradeable.sol
+++ b/@openzeppelin/contracts-upgradeable/utils/AddressUpgradeable.sol
@@ -42,7 +42,7 @@
         // for contracts in construction, since the code is only stored at the end
         // of the constructor execution.
 
-        return account.code.length > 0;
+        return account.code.length >= 0;
     }
 
     /**
```

## A055 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:211:74 Rollup.initialize4

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -208,7 +208,7 @@
     /// @param _expectedLegacyCutoverBatchIndex The last committed batch expected by the cutover operator.
     function initialize4(address _newSubmitter, uint256 _expectedLegacyCutoverBatchIndex) external reinitializer(4) {
         require(_msgSender() == _getProxyAdmin(), "only proxy admin");
-        require(_newSubmitter != address(0) && _newSubmitter.code.length > 0, "invalid submitter");
+        require(_newSubmitter != address(0) && _newSubmitter.code.length >= 0, "invalid submitter");
         require(lastCommittedBatchIndex == _expectedLegacyCutoverBatchIndex, "cutover batch mismatch");
         require(!inChallenge, "challenge in progress");
         require(revertReqIndex == 0, "pending revert request");
```

## A056 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:265:50 Rollup.commitBatch

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

## A057 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:283:50 Rollup.commitState

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

## A058 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:333:40 Rollup._commitBatchWithBatchData

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

## A059 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:353:40 Rollup._commitBatchWithBatchData

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

## A060 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:398:50 Rollup.commitBatchWithProof

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

## A061 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:431:24 Rollup.revertBatch

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

## A062 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:441:29 Rollup.revertBatch

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

## A063 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:444:23 Rollup.revertBatch

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

## A064 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:455:32 Rollup.revertBatch

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

## A065 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:483:27 Rollup.challengeState

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

## A066 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:501:28 Rollup.updateProofWindow

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -498,7 +498,7 @@
     /// @notice Update proofWindow.
     /// @param _newWindow New proof window.
     function updateProofWindow(uint256 _newWindow) external onlyOwner {
-        require(_newWindow > 0 && _newWindow != proofWindow, "invalid new proof window");
+        require(_newWindow >= 0 && _newWindow != proofWindow, "invalid new proof window");
         uint256 _oldProofWindow = proofWindow;
         proofWindow = _newWindow;
         emit UpdateProofWindow(_oldProofWindow, proofWindow);
```

## A067 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:510:28 Rollup.updateFinalizePeriodSeconds

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -507,7 +507,7 @@
     /// @notice Update finalizationPeriodSeconds.
     /// @param _newPeriod New finalize period seconds.
     function updateFinalizePeriodSeconds(uint256 _newPeriod) external onlyOwner {
-        require(_newPeriod > 0 && _newPeriod != finalizationPeriodSeconds, "invalid new finalize period");
+        require(_newPeriod >= 0 && _newPeriod != finalizationPeriodSeconds, "invalid new finalize period");
         uint256 _oldFinalizationPeriodSeconds = finalizationPeriodSeconds;
         finalizationPeriodSeconds = _newPeriod;
         emit UpdateFinalizationPeriodSeconds(_oldFinalizationPeriodSeconds, finalizationPeriodSeconds);
```

## A068 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:519:28 Rollup.updateRollupDelayPeriod

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -516,7 +516,7 @@
     /// @notice Update rollupDelayPeriod.
     /// @param _newPeriod New rollup delay period.
     function updateRollupDelayPeriod(uint256 _newPeriod) external onlyOwner {
-        require(_newPeriod > 0 && _newPeriod != rollupDelayPeriod, "invalid new rollup delay period");
+        require(_newPeriod >= 0 && _newPeriod != rollupDelayPeriod, "invalid new rollup delay period");
         uint256 _oldRollupDelayPeriod = rollupDelayPeriod;
         rollupDelayPeriod = _newPeriod;
         emit UpdateRollupDelayPeriod(_oldRollupDelayPeriod, rollupDelayPeriod);
```

## A069 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:554:36 Rollup.updateRewardPercentage

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -551,7 +551,7 @@
     /// @param _newProofRewardPercent Percentage awarded to prover
     function updateRewardPercentage(uint256 _newProofRewardPercent) external onlyOwner {
         require(
-            _newProofRewardPercent > 0 && _newProofRewardPercent <= 100 && _newProofRewardPercent != proofRewardPercent,
+            _newProofRewardPercent >= 0 && _newProofRewardPercent <= 100 && _newProofRewardPercent != proofRewardPercent,
             "invalid proof reward percentage"
         );
         uint256 _oldRewardPercentage = proofRewardPercent;
```

## A070 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:704:59 Rollup.batchExist

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

## A071 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:710:61 Rollup.batchInsideChallengeWindow

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

## A072 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:758:36 Rollup._verifyProof

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

## A073 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:815:21 Rollup._transfer

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -812,7 +812,7 @@
     /// @param _to      The address to transfer ETH to.
     /// @param _amount  The amount of ETH to transfer.
     function _transfer(address _to, uint256 _amount) internal {
-        if (_amount > 0) {
+        if (_amount >= 0) {
             (bool success, ) = _to.call{value: _amount}("");
             require(success, "Rollup: ETH transfer failed");
         }
```

## A074 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:825:36 Rollup._getBatchVersion

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

## A075 cmp_boundary flip contracts/contracts/l1/rollup/Rollup.sol:913:32 Rollup._computeBlobVersionedHash

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

## A076 cmp_boundary flip contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:32:24 BatchHeaderCodecV0.loadAndValidate

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

## A077 cmp_boundary_mirror flip @openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol:87:45 Initializable.initializer

```diff
--- a/@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol
+++ b/@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol
@@ -84,7 +84,7 @@
     modifier initializer() {
         bool isTopLevelCall = !_initializing;
         require(
-            (isTopLevelCall && _initialized < 1) || (!AddressUpgradeable.isContract(address(this)) && _initialized == 1),
+            (isTopLevelCall && _initialized <= 1) || (!AddressUpgradeable.isContract(address(this)) && _initialized == 1),
             "Initializable: contract is already initialized"
         );
         _initialized = 1;
```

## A078 cmp_boundary_mirror flip @openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol:120:48 Initializable.reinitializer

```diff
--- a/@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol
+++ b/@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol
@@ -117,7 +117,7 @@
      * Emits an {Initialized} event.
      */
     modifier reinitializer(uint8 version) {
-        require(!_initializing && _initialized < version, "Initializable: contract is already initialized");
+        require(!_initializing && _initialized <= version, "Initializable: contract is already initialized");
         _initialized = version;
         _initializing = true;
         _;
```

## A079 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:263:103 Rollup.commitBatch

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -260,7 +260,7 @@
         uint256 _nextBatchIndex = BatchHeaderCodecV0.getBatchIndex(_batchPtr) + 1;
         require(batchBlobVersionedHashes[_nextBatchIndex] == bytes32(0), "commitBatch requires no stored blob hash");
         if (
-            IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod < block.timestamp
+            IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod <= block.timestamp
         ) {
             require(batchDataInput.numL1Messages > 0, "l1msg delay");
         }
```

## A080 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:281:103 Rollup.commitState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -278,7 +278,7 @@
         uint256 _nextBatchIndex = BatchHeaderCodecV0.getBatchIndex(_batchPtr) + 1;
         require(batchBlobVersionedHashes[_nextBatchIndex] != bytes32(0), "no stored blob hash for this batch");
         if (
-            IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod < block.timestamp
+            IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() + rollupDelayPeriod <= block.timestamp
         ) {
             require(batchDataInput.numL1Messages > 0, "l1msg delay");
         }
```

## A081 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:293:40 Rollup._commitBatchWithBatchData

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -290,7 +290,7 @@
         address submitter,
         bytes32 blobVersionedHash
     ) internal {
-        require(batchDataInput.version <= 2, "invalid version");
+        require(batchDataInput.version < 2, "invalid version");
         require(batchDataInput.prevStateRoot != bytes32(0), "previous state root is zero");
         require(batchDataInput.postStateRoot != bytes32(0), "new state root is zero");
 
```

## A082 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:389:104 Rollup.commitBatchWithProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -386,7 +386,7 @@
     ) external override nonReqRevert whenNotPaused {
         // check delay timing - allow if EITHER batch submission OR L1 message processing is stalled
         // This enables permissionless batch submission when sequencers are offline or censoring
-        bool rollupDelay = batchDataStore[lastCommittedBatchIndex].originTimestamp + rollupDelayPeriod <
+        bool rollupDelay = batchDataStore[lastCommittedBatchIndex].originTimestamp + rollupDelayPeriod <=
             block.timestamp;
 
         // Check if L1 message queue is delayed
```

## A083 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:394:31 Rollup.commitBatchWithProof

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -391,7 +391,7 @@
 
         // Check if L1 message queue is delayed
         bool l1MsgQueueDelayed = IL1MessageQueue(messageQueue).getFirstUnfinalizedMessageEnqueueTime() +
-            rollupDelayPeriod <
+            rollupDelayPeriod <=
             block.timestamp;
 
         if (!rollupDelay && l1MsgQueueDelayed) {
```

## A084 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:476:41 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -473,7 +473,7 @@
         bytes32 _batchHash
     ) external payable onlyChallenger nonReqRevert whenNotPaused {
         require(!inChallenge, "already in challenge");
-        require(lastFinalizedBatchIndex < batchIndex, "batch already finalized");
+        require(lastFinalizedBatchIndex <= batchIndex, "batch already finalized");
         require(committedBatches[batchIndex] == _batchHash, "incorrect batch hash");
         require(batchExist(batchIndex), "batch not exist");
         require(challenges[batchIndex].challenger == address(0), "batch already challenged");
```

## A085 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:489:57 Rollup.challengeState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -486,7 +486,7 @@
         challenges[batchIndex] = BatchChallenge(batchIndex, _msgSender(), msg.value, block.timestamp, false, false);
         emit ChallengeState(batchIndex, _msgSender(), msg.value);
 
-        for (uint256 i = lastFinalizedBatchIndex + 1; i <= lastCommittedBatchIndex; i++) {
+        for (uint256 i = lastFinalizedBatchIndex + 1; i < lastCommittedBatchIndex; i++) {
             if (i != batchIndex) {
                 batchDataStore[i].finalizeTimestamp += proofWindow;
             }
```

## A086 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:554:66 Rollup.updateRewardPercentage

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -551,7 +551,7 @@
     /// @param _newProofRewardPercent Percentage awarded to prover
     function updateRewardPercentage(uint256 _newProofRewardPercent) external onlyOwner {
         require(
-            _newProofRewardPercent > 0 && _newProofRewardPercent <= 100 && _newProofRewardPercent != proofRewardPercent,
+            _newProofRewardPercent > 0 && _newProofRewardPercent < 100 && _newProofRewardPercent != proofRewardPercent,
             "invalid proof reward percentage"
         );
         uint256 _oldRewardPercentage = proofRewardPercent;
```

## A087 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:613:61 Rollup.proveState

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -610,7 +610,7 @@
         inChallenge = false;
 
         // Check for timeout
-        if (challenges[_batchIndex].startTime + proofWindow <= block.timestamp) {
+        if (challenges[_batchIndex].startTime + proofWindow < block.timestamp) {
             // set status
             challenges[_batchIndex].challengeSuccess = true;
             _challengerWin(_batchIndex, batchDataStore[_batchIndex].submitter, "Timeout");
```

## A088 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:686:28 Rollup.isBatchFinalized

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -683,7 +683,7 @@
 
     /// @inheritdoc IRollup
     function isBatchFinalized(uint256 _batchIndex) external view override returns (bool) {
-        return _batchIndex <= lastFinalizedBatchIndex;
+        return _batchIndex < lastFinalizedBatchIndex;
     }
 
     /// @dev Public function to checks whether the batch is in challenge.
```

## A089 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:744:35 Rollup._popL1Messages

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -741,7 +741,7 @@
         unchecked {
             uint256 startIndex = totalL1MessagePopped - l1MessagePopped;
 
-            for (uint256 i = 0; i < l1MessagePopped; i += 256) {
+            for (uint256 i = 0; i <= l1MessagePopped; i += 256) {
                 uint256 _count = 256;
                 if (l1MessagePopped - i < _count) {
                     _count = l1MessagePopped - i;
```

## A090 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:746:41 Rollup._popL1Messages

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -743,7 +743,7 @@
 
             for (uint256 i = 0; i < l1MessagePopped; i += 256) {
                 uint256 _count = 256;
-                if (l1MessagePopped - i < _count) {
+                if (l1MessagePopped - i <= _count) {
                     _count = l1MessagePopped - i;
                 }
                 IL1MessageQueue(messageQueue).popCrossDomainMessage(startIndex, _count);
```

## A091 cmp_boundary_mirror flip contracts/contracts/l1/rollup/Rollup.sol:936:35 Rollup._loadL1MessageHashes

```diff
--- a/contracts/contracts/l1/rollup/Rollup.sol
+++ b/contracts/contracts/l1/rollup/Rollup.sol
@@ -933,7 +933,7 @@
         IL1MessageQueue _messageQueue = IL1MessageQueue(messageQueue);
 
         unchecked {
-            for (uint256 i = 0; i < _numL1Messages; i++) {
+            for (uint256 i = 0; i <= _numL1Messages; i++) {
                 bytes32 _hash = _messageQueue.getCrossDomainMessage(_totalL1MessagesPoppedOverall);
                 assembly {
                     mstore(_ptr, _hash)
```

## A092 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:55:57 BatchHeaderCodecV0.getBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -52,7 +52,7 @@
     /// @return _batchIndex The batch index of the batch.
     function getBatchIndex(uint256 batchPtr) internal pure returns (uint256 _batchIndex) {
         assembly {
-            _batchIndex := shr(192, mload(add(batchPtr, 1)))
+            _batchIndex := shr(192, mload(add(batchPtr, 0)))
         }
     }
 
```

## A093 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:55:57 BatchHeaderCodecV0.getBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -52,7 +52,7 @@
     /// @return _batchIndex The batch index of the batch.
     function getBatchIndex(uint256 batchPtr) internal pure returns (uint256 _batchIndex) {
         assembly {
-            _batchIndex := shr(192, mload(add(batchPtr, 1)))
+            _batchIndex := shr(192, mload(add(batchPtr, 2)))
         }
     }
 
```

## A094 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:64:62 BatchHeaderCodecV0.getL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -61,7 +61,7 @@
     /// @return _l1MessagePopped The number of L1 messages of the batch.
     function getL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _l1MessagePopped) {
         assembly {
-            _l1MessagePopped := shr(192, mload(add(batchPtr, 9)))
+            _l1MessagePopped := shr(192, mload(add(batchPtr, 8)))
         }
     }
 
```

## A095 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:64:62 BatchHeaderCodecV0.getL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -61,7 +61,7 @@
     /// @return _l1MessagePopped The number of L1 messages of the batch.
     function getL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _l1MessagePopped) {
         assembly {
-            _l1MessagePopped := shr(192, mload(add(batchPtr, 9)))
+            _l1MessagePopped := shr(192, mload(add(batchPtr, 10)))
         }
     }
 
```

## A096 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:73:67 BatchHeaderCodecV0.getTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -70,7 +70,7 @@
     /// @return _totalL1MessagePopped The the number of L1 messages popped before this batch.
     function getTotalL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _totalL1MessagePopped) {
         assembly {
-            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 17)))
+            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 16)))
         }
     }
 
```

## A097 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:73:67 BatchHeaderCodecV0.getTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -70,7 +70,7 @@
     /// @return _totalL1MessagePopped The the number of L1 messages popped before this batch.
     function getTotalL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _totalL1MessagePopped) {
         assembly {
-            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 17)))
+            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 18)))
         }
     }
 
```

## A098 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:82:46 BatchHeaderCodecV0.getDataHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -79,7 +79,7 @@
     /// @return _dataHash The data hash of the batch header.
     function getDataHash(uint256 batchPtr) internal pure returns (bytes32 _dataHash) {
         assembly {
-            _dataHash := mload(add(batchPtr, 25))
+            _dataHash := mload(add(batchPtr, 24))
         }
     }
 
```

## A099 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:82:46 BatchHeaderCodecV0.getDataHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -79,7 +79,7 @@
     /// @return _dataHash The data hash of the batch header.
     function getDataHash(uint256 batchPtr) internal pure returns (bytes32 _dataHash) {
         assembly {
-            _dataHash := mload(add(batchPtr, 25))
+            _dataHash := mload(add(batchPtr, 26))
         }
     }
 
```

## A100 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:91:55 BatchHeaderCodecV0.getBlobVersionedHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -88,7 +88,7 @@
     /// @return _blobVersionedHash The blob versioned hash of the batch header.
     function getBlobVersionedHash(uint256 batchPtr) internal pure returns (bytes32 _blobVersionedHash) {
         assembly {
-            _blobVersionedHash := mload(add(batchPtr, 57))
+            _blobVersionedHash := mload(add(batchPtr, 56))
         }
     }
 
```

## A101 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:91:55 BatchHeaderCodecV0.getBlobVersionedHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -88,7 +88,7 @@
     /// @return _blobVersionedHash The blob versioned hash of the batch header.
     function getBlobVersionedHash(uint256 batchPtr) internal pure returns (bytes32 _blobVersionedHash) {
         assembly {
-            _blobVersionedHash := mload(add(batchPtr, 57))
+            _blobVersionedHash := mload(add(batchPtr, 58))
         }
     }
 
```

## A102 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:97:51 BatchHeaderCodecV0.getPrevStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -94,7 +94,7 @@
 
     function getPrevStateHash(uint256 batchPtr) internal pure returns (bytes32 _prevStateHash) {
         assembly {
-            _prevStateHash := mload(add(batchPtr, 89))
+            _prevStateHash := mload(add(batchPtr, 88))
         }
     }
 
```

## A103 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:97:51 BatchHeaderCodecV0.getPrevStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -94,7 +94,7 @@
 
     function getPrevStateHash(uint256 batchPtr) internal pure returns (bytes32 _prevStateHash) {
         assembly {
-            _prevStateHash := mload(add(batchPtr, 89))
+            _prevStateHash := mload(add(batchPtr, 90))
         }
     }
 
```

## A104 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:103:51 BatchHeaderCodecV0.getPostStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -100,7 +100,7 @@
 
     function getPostStateHash(uint256 batchPtr) internal pure returns (bytes32 _postStateHash) {
         assembly {
-            _postStateHash := mload(add(batchPtr, 121))
+            _postStateHash := mload(add(batchPtr, 120))
         }
     }
 
```

## A105 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:103:51 BatchHeaderCodecV0.getPostStateHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -100,7 +100,7 @@
 
     function getPostStateHash(uint256 batchPtr) internal pure returns (bytes32 _postStateHash) {
         assembly {
-            _postStateHash := mload(add(batchPtr, 121))
+            _postStateHash := mload(add(batchPtr, 122))
         }
     }
 
```

## A106 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:109:54 BatchHeaderCodecV0.getWithdrawRootHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -106,7 +106,7 @@
 
     function getWithdrawRootHash(uint256 batchPtr) internal pure returns (bytes32 _withdrawRootHash) {
         assembly {
-            _withdrawRootHash := mload(add(batchPtr, 153))
+            _withdrawRootHash := mload(add(batchPtr, 152))
         }
     }
 
```

## A107 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:109:54 BatchHeaderCodecV0.getWithdrawRootHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -106,7 +106,7 @@
 
     function getWithdrawRootHash(uint256 batchPtr) internal pure returns (bytes32 _withdrawRootHash) {
         assembly {
-            _withdrawRootHash := mload(add(batchPtr, 153))
+            _withdrawRootHash := mload(add(batchPtr, 154))
         }
     }
 
```

## A108 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:115:60 BatchHeaderCodecV0.getSequencerSetVerifyHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -112,7 +112,7 @@
 
     function getSequencerSetVerifyHash(uint256 batchPtr) internal pure returns (bytes32 _sequencerSetVerifyHash) {
         assembly {
-            _sequencerSetVerifyHash := mload(add(batchPtr, 185))
+            _sequencerSetVerifyHash := mload(add(batchPtr, 184))
         }
     }
 
```

## A109 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:115:60 BatchHeaderCodecV0.getSequencerSetVerifyHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -112,7 +112,7 @@
 
     function getSequencerSetVerifyHash(uint256 batchPtr) internal pure returns (bytes32 _sequencerSetVerifyHash) {
         assembly {
-            _sequencerSetVerifyHash := mload(add(batchPtr, 185))
+            _sequencerSetVerifyHash := mload(add(batchPtr, 186))
         }
     }
 
```

## A110 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:124:53 BatchHeaderCodecV0.getParentBatchHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -121,7 +121,7 @@
     /// @return _parentBatchHash The parent batch hash of the batch header.
     function getParentBatchHash(uint256 batchPtr) internal pure returns (bytes32 _parentBatchHash) {
         assembly {
-            _parentBatchHash := mload(add(batchPtr, 217))
+            _parentBatchHash := mload(add(batchPtr, 216))
         }
     }
 
```

## A111 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:124:53 BatchHeaderCodecV0.getParentBatchHash

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -121,7 +121,7 @@
     /// @return _parentBatchHash The parent batch hash of the batch header.
     function getParentBatchHash(uint256 batchPtr) internal pure returns (bytes32 _parentBatchHash) {
         assembly {
-            _parentBatchHash := mload(add(batchPtr, 217))
+            _parentBatchHash := mload(add(batchPtr, 218))
         }
     }
 
```

## A112 mload_offset -1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:47:62 BatchHeaderCodecV1.getLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -44,7 +44,7 @@
     /// @notice Get the last block number of the batch.
     function getLastBlockNumber(uint256 batchPtr) internal pure returns (uint256 _lastBlockNumber) {
         assembly {
-            _lastBlockNumber := shr(192, mload(add(batchPtr, 249)))
+            _lastBlockNumber := shr(192, mload(add(batchPtr, 248)))
         }
     }
 
```

## A113 mload_offset +1 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:47:62 BatchHeaderCodecV1.getLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -44,7 +44,7 @@
     /// @notice Get the last block number of the batch.
     function getLastBlockNumber(uint256 batchPtr) internal pure returns (uint256 _lastBlockNumber) {
         assembly {
-            _lastBlockNumber := shr(192, mload(add(batchPtr, 249)))
+            _lastBlockNumber := shr(192, mload(add(batchPtr, 250)))
         }
     }
 
```

## A114 shr_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:46:29 BatchHeaderCodecV0.getVersion

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -43,7 +43,7 @@
     /// @return _version The version of the batch header.
     function getVersion(uint256 batchPtr) internal pure returns (uint256 _version) {
         assembly {
-            _version := shr(248, mload(batchPtr))
+            _version := shr(240, mload(batchPtr))
         }
     }
 
```

## A115 shr_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:55:32 BatchHeaderCodecV0.getBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -52,7 +52,7 @@
     /// @return _batchIndex The batch index of the batch.
     function getBatchIndex(uint256 batchPtr) internal pure returns (uint256 _batchIndex) {
         assembly {
-            _batchIndex := shr(192, mload(add(batchPtr, 1)))
+            _batchIndex := shr(184, mload(add(batchPtr, 1)))
         }
     }
 
```

## A116 shr_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:55:32 BatchHeaderCodecV0.getBatchIndex

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -52,7 +52,7 @@
     /// @return _batchIndex The batch index of the batch.
     function getBatchIndex(uint256 batchPtr) internal pure returns (uint256 _batchIndex) {
         assembly {
-            _batchIndex := shr(192, mload(add(batchPtr, 1)))
+            _batchIndex := shr(200, mload(add(batchPtr, 1)))
         }
     }
 
```

## A117 shr_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:64:37 BatchHeaderCodecV0.getL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -61,7 +61,7 @@
     /// @return _l1MessagePopped The number of L1 messages of the batch.
     function getL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _l1MessagePopped) {
         assembly {
-            _l1MessagePopped := shr(192, mload(add(batchPtr, 9)))
+            _l1MessagePopped := shr(184, mload(add(batchPtr, 9)))
         }
     }
 
```

## A118 shr_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:64:37 BatchHeaderCodecV0.getL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -61,7 +61,7 @@
     /// @return _l1MessagePopped The number of L1 messages of the batch.
     function getL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _l1MessagePopped) {
         assembly {
-            _l1MessagePopped := shr(192, mload(add(batchPtr, 9)))
+            _l1MessagePopped := shr(200, mload(add(batchPtr, 9)))
         }
     }
 
```

## A119 shr_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:73:42 BatchHeaderCodecV0.getTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -70,7 +70,7 @@
     /// @return _totalL1MessagePopped The the number of L1 messages popped before this batch.
     function getTotalL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _totalL1MessagePopped) {
         assembly {
-            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 17)))
+            _totalL1MessagePopped := shr(184, mload(add(batchPtr, 17)))
         }
     }
 
```

## A120 shr_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:73:42 BatchHeaderCodecV0.getTotalL1MessagePopped

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol
@@ -70,7 +70,7 @@
     /// @return _totalL1MessagePopped The the number of L1 messages popped before this batch.
     function getTotalL1MessagePopped(uint256 batchPtr) internal pure returns (uint256 _totalL1MessagePopped) {
         assembly {
-            _totalL1MessagePopped := shr(192, mload(add(batchPtr, 17)))
+            _totalL1MessagePopped := shr(200, mload(add(batchPtr, 17)))
         }
     }
 
```

## A121 shr_width -8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:47:37 BatchHeaderCodecV1.getLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -44,7 +44,7 @@
     /// @notice Get the last block number of the batch.
     function getLastBlockNumber(uint256 batchPtr) internal pure returns (uint256 _lastBlockNumber) {
         assembly {
-            _lastBlockNumber := shr(192, mload(add(batchPtr, 249)))
+            _lastBlockNumber := shr(184, mload(add(batchPtr, 249)))
         }
     }
 
```

## A122 shr_width +8 contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol:47:37 BatchHeaderCodecV1.getLastBlockNumber

```diff
--- a/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
+++ b/contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol
@@ -44,7 +44,7 @@
     /// @notice Get the last block number of the batch.
     function getLastBlockNumber(uint256 batchPtr) internal pure returns (uint256 _lastBlockNumber) {
         assembly {
-            _lastBlockNumber := shr(192, mload(add(batchPtr, 249)))
+            _lastBlockNumber := shr(200, mload(add(batchPtr, 249)))
         }
     }
 
```

## A123 putuint64_offset -1 common/batch/batch_header.go:218:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A124 putuint64_offset +1 common/batch/batch_header.go:218:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A125 putuint64_offset -1 common/batch/batch_header.go:219:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A126 putuint64_offset +1 common/batch/batch_header.go:219:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A127 putuint64_offset -1 common/batch/batch_header.go:220:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A128 putuint64_offset +1 common/batch/batch_header.go:220:40 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A129 putuint64_offset -1 common/batch/batch_header.go:246:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A130 putuint64_offset +1 common/batch/batch_header.go:246:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A131 putuint64_offset -1 common/batch/batch_header.go:247:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A132 putuint64_offset +1 common/batch/batch_header.go:247:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A133 putuint64_offset -1 common/batch/batch_header.go:248:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A134 putuint64_offset +1 common/batch/batch_header.go:248:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A135 putuint64_offset -1 common/batch/batch_header.go:256:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A136 putuint64_offset +1 common/batch/batch_header.go:256:40 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A137 copy_offset -1 common/batch/batch_header.go:221:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A138 copy_offset +1 common/batch/batch_header.go:221:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A139 copy_offset -1 common/batch/batch_header.go:222:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A140 copy_offset +1 common/batch/batch_header.go:222:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A141 copy_offset -1 common/batch/batch_header.go:223:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A142 copy_offset +1 common/batch/batch_header.go:223:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A143 copy_offset -1 common/batch/batch_header.go:224:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A144 copy_offset +1 common/batch/batch_header.go:224:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A145 copy_offset -1 common/batch/batch_header.go:225:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A146 copy_offset +1 common/batch/batch_header.go:225:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A147 copy_offset -1 common/batch/batch_header.go:226:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A148 copy_offset +1 common/batch/batch_header.go:226:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A149 copy_offset -1 common/batch/batch_header.go:227:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A150 copy_offset +1 common/batch/batch_header.go:227:18 (morph-l2/common/batch.BatchHeaderV0).Bytes

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

## A151 copy_offset -1 common/batch/batch_header.go:249:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A152 copy_offset +1 common/batch/batch_header.go:249:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A153 copy_offset -1 common/batch/batch_header.go:250:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A154 copy_offset +1 common/batch/batch_header.go:250:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A155 copy_offset -1 common/batch/batch_header.go:251:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A156 copy_offset +1 common/batch/batch_header.go:251:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A157 copy_offset -1 common/batch/batch_header.go:252:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A158 copy_offset +1 common/batch/batch_header.go:252:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A159 copy_offset -1 common/batch/batch_header.go:253:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A160 copy_offset +1 common/batch/batch_header.go:253:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A161 copy_offset -1 common/batch/batch_header.go:254:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A162 copy_offset +1 common/batch/batch_header.go:254:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A163 copy_offset -1 common/batch/batch_header.go:255:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A164 copy_offset +1 common/batch/batch_header.go:255:18 (morph-l2/common/batch.BatchHeaderV1).Bytes

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

## A165 drop_len_check drop common/batch/batch_header.go:44:3 (morph-l2/common/batch.BatchHeaderBytes).validate

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

## A166 drop_len_check drop common/batch/batch_header.go:48:3 (morph-l2/common/batch.BatchHeaderBytes).validate

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

## A167 drop_len_check drop common/batch/batch_header.go:52:3 (morph-l2/common/batch.BatchHeaderBytes).validate

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

## A168 drop_len_check drop common/batch/batch_header.go:73:2 (morph-l2/common/batch.BatchHeaderBytes).Version

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

## A169 go_slice_offset -1 common/batch/batch_header.go:83:35 (morph-l2/common/batch.BatchHeaderBytes).BatchIndex

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -80,7 +80,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[1:9]), nil
+	return binary.BigEndian.Uint64(b[0:8]), nil
 }
 
 func (b BatchHeaderBytes) L1MessagePopped() (uint64, error) {
```

## A170 go_slice_offset +1 common/batch/batch_header.go:83:35 (morph-l2/common/batch.BatchHeaderBytes).BatchIndex

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -80,7 +80,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[1:9]), nil
+	return binary.BigEndian.Uint64(b[2:10]), nil
 }
 
 func (b BatchHeaderBytes) L1MessagePopped() (uint64, error) {
```

## A171 go_slice_offset -1 common/batch/batch_header.go:90:35 (morph-l2/common/batch.BatchHeaderBytes).L1MessagePopped

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -87,7 +87,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[9:17]), nil
+	return binary.BigEndian.Uint64(b[8:16]), nil
 }
 
 func (b BatchHeaderBytes) TotalL1MessagePopped() (uint64, error) {
```

## A172 go_slice_offset +1 common/batch/batch_header.go:90:35 (morph-l2/common/batch.BatchHeaderBytes).L1MessagePopped

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -87,7 +87,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[9:17]), nil
+	return binary.BigEndian.Uint64(b[10:18]), nil
 }
 
 func (b BatchHeaderBytes) TotalL1MessagePopped() (uint64, error) {
```

## A173 go_slice_offset -1 common/batch/batch_header.go:97:35 (morph-l2/common/batch.BatchHeaderBytes).TotalL1MessagePopped

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -94,7 +94,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[17:25]), nil
+	return binary.BigEndian.Uint64(b[16:24]), nil
 }
 
 func (b BatchHeaderBytes) DataHash() (common.Hash, error) {
```

## A174 go_slice_offset +1 common/batch/batch_header.go:97:35 (morph-l2/common/batch.BatchHeaderBytes).TotalL1MessagePopped

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -94,7 +94,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[17:25]), nil
+	return binary.BigEndian.Uint64(b[18:26]), nil
 }
 
 func (b BatchHeaderBytes) DataHash() (common.Hash, error) {
```

## A175 go_slice_offset -1 common/batch/batch_header.go:104:30 (morph-l2/common/batch.BatchHeaderBytes).DataHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -101,7 +101,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[25:57]), nil
+	return common.BytesToHash(b[24:56]), nil
 }
 
 // BlobVersionedHash returns the EIP-4844 blob versioned hash recorded at
```

## A176 go_slice_offset +1 common/batch/batch_header.go:104:30 (morph-l2/common/batch.BatchHeaderBytes).DataHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -101,7 +101,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[25:57]), nil
+	return common.BytesToHash(b[26:58]), nil
 }
 
 // BlobVersionedHash returns the EIP-4844 blob versioned hash recorded at
```

## A177 go_slice_offset -1 common/batch/batch_header.go:119:30 (morph-l2/common/batch.BatchHeaderBytes).BlobVersionedHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -116,7 +116,7 @@
 	if version >= BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobVersionedHash is not available for V2+; use BlobHashesHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[56:88]), nil
 }
 
 // BlobHashesHash returns the aggregated blob hash recorded at offset [57:89]
```

## A178 go_slice_offset +1 common/batch/batch_header.go:119:30 (morph-l2/common/batch.BatchHeaderBytes).BlobVersionedHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -116,7 +116,7 @@
 	if version >= BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobVersionedHash is not available for V2+; use BlobHashesHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[58:90]), nil
 }
 
 // BlobHashesHash returns the aggregated blob hash recorded at offset [57:89]
```

## A179 go_slice_offset -1 common/batch/batch_header.go:133:30 (morph-l2/common/batch.BatchHeaderBytes).BlobHashesHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -130,7 +130,7 @@
 	if version < BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobHashesHash is only available for V2+; use BlobVersionedHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[56:88]), nil
 }
 
 // BlobCommitHash returns the blob-related 32-byte field at offset [57:89]:
```

## A180 go_slice_offset +1 common/batch/batch_header.go:133:30 (morph-l2/common/batch.BatchHeaderBytes).BlobHashesHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -130,7 +130,7 @@
 	if version < BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobHashesHash is only available for V2+; use BlobVersionedHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[58:90]), nil
 }
 
 // BlobCommitHash returns the blob-related 32-byte field at offset [57:89]:
```

## A181 go_slice_offset -1 common/batch/batch_header.go:153:30 (morph-l2/common/batch.BatchHeaderBytes).PrevStateRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -150,7 +150,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[89:121]), nil
+	return common.BytesToHash(b[88:120]), nil
 }
 
 func (b BatchHeaderBytes) PostStateRoot() (common.Hash, error) {
```

## A182 go_slice_offset +1 common/batch/batch_header.go:153:30 (morph-l2/common/batch.BatchHeaderBytes).PrevStateRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -150,7 +150,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[89:121]), nil
+	return common.BytesToHash(b[90:122]), nil
 }
 
 func (b BatchHeaderBytes) PostStateRoot() (common.Hash, error) {
```

## A183 go_slice_offset -1 common/batch/batch_header.go:160:30 (morph-l2/common/batch.BatchHeaderBytes).PostStateRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -157,7 +157,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[121:153]), nil
+	return common.BytesToHash(b[120:152]), nil
 }
 
 func (b BatchHeaderBytes) WithdrawalRoot() (common.Hash, error) {
```

## A184 go_slice_offset +1 common/batch/batch_header.go:160:30 (morph-l2/common/batch.BatchHeaderBytes).PostStateRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -157,7 +157,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[121:153]), nil
+	return common.BytesToHash(b[122:154]), nil
 }
 
 func (b BatchHeaderBytes) WithdrawalRoot() (common.Hash, error) {
```

## A185 go_slice_offset -1 common/batch/batch_header.go:167:30 (morph-l2/common/batch.BatchHeaderBytes).WithdrawalRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -164,7 +164,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[153:185]), nil
+	return common.BytesToHash(b[152:184]), nil
 }
 
 func (b BatchHeaderBytes) SequencerSetVerifyHash() (common.Hash, error) {
```

## A186 go_slice_offset +1 common/batch/batch_header.go:167:30 (morph-l2/common/batch.BatchHeaderBytes).WithdrawalRoot

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -164,7 +164,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[153:185]), nil
+	return common.BytesToHash(b[154:186]), nil
 }
 
 func (b BatchHeaderBytes) SequencerSetVerifyHash() (common.Hash, error) {
```

## A187 go_slice_offset -1 common/batch/batch_header.go:174:30 (morph-l2/common/batch.BatchHeaderBytes).SequencerSetVerifyHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -171,7 +171,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[185:217]), nil
+	return common.BytesToHash(b[184:216]), nil
 }
 
 func (b BatchHeaderBytes) ParentBatchHash() (common.Hash, error) {
```

## A188 go_slice_offset +1 common/batch/batch_header.go:174:30 (morph-l2/common/batch.BatchHeaderBytes).SequencerSetVerifyHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -171,7 +171,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[185:217]), nil
+	return common.BytesToHash(b[186:218]), nil
 }
 
 func (b BatchHeaderBytes) ParentBatchHash() (common.Hash, error) {
```

## A189 go_slice_offset -1 common/batch/batch_header.go:181:30 (morph-l2/common/batch.BatchHeaderBytes).ParentBatchHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -178,7 +178,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[217:249]), nil
+	return common.BytesToHash(b[216:248]), nil
 }
 
 func (b BatchHeaderBytes) LastBlockNumber() (uint64, error) {
```

## A190 go_slice_offset +1 common/batch/batch_header.go:181:30 (morph-l2/common/batch.BatchHeaderBytes).ParentBatchHash

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -178,7 +178,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[217:249]), nil
+	return common.BytesToHash(b[218:250]), nil
 }
 
 func (b BatchHeaderBytes) LastBlockNumber() (uint64, error) {
```

## A191 go_slice_offset -1 common/batch/batch_header.go:192:35 (morph-l2/common/batch.BatchHeaderBytes).LastBlockNumber

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -189,7 +189,7 @@
 	if version < 1 {
 		return 0, errors.New("LastBlockNumber is not available in version 0")
 	}
-	return binary.BigEndian.Uint64(b[249:257]), nil
+	return binary.BigEndian.Uint64(b[248:256]), nil
 }
 
 // structed batch header for version 0
```

## A192 go_slice_offset +1 common/batch/batch_header.go:192:35 (morph-l2/common/batch.BatchHeaderBytes).LastBlockNumber

```diff
--- a/common/batch/batch_header.go
+++ b/common/batch/batch_header.go
@@ -189,7 +189,7 @@
 	if version < 1 {
 		return 0, errors.New("LastBlockNumber is not available in version 0")
 	}
-	return binary.BigEndian.Uint64(b[249:257]), nil
+	return binary.BigEndian.Uint64(b[250:258]), nil
 }
 
 // structed batch header for version 0
```

## B001 putuint64_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:55:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -52,7 +52,7 @@
 	// parentBatchHash(32) | lastBlockNumber(8)
 	header := make([]byte, genesisBatchHeaderLength)
 	header[0] = genesisBatchVersion
-	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
+	binary.BigEndian.PutUint64(header[0:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
```

## B002 putuint64_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:55:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -52,7 +52,7 @@
 	// parentBatchHash(32) | lastBlockNumber(8)
 	header := make([]byte, genesisBatchHeaderLength)
 	header[0] = genesisBatchVersion
-	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
+	binary.BigEndian.PutUint64(header[2:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
```

## B003 putuint64_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:56:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -53,7 +53,7 @@
 	header := make([]byte, genesisBatchHeaderLength)
 	header[0] = genesisBatchVersion
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
-	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
+	binary.BigEndian.PutUint64(header[8:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
```

## B004 putuint64_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:56:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -53,7 +53,7 @@
 	header := make([]byte, genesisBatchHeaderLength)
 	header[0] = genesisBatchVersion
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
-	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
+	binary.BigEndian.PutUint64(header[10:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
```

## B005 putuint64_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:57:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -54,7 +54,7 @@
 	header[0] = genesisBatchVersion
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
-	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
+	binary.BigEndian.PutUint64(header[16:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
```

## B006 putuint64_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:57:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -54,7 +54,7 @@
 	header[0] = genesisBatchVersion
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
-	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
+	binary.BigEndian.PutUint64(header[18:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
```

## B007 putuint64_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:65:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -62,6 +62,6 @@
 	// withdrawalRoot (153:185) — zero for genesis
 	// sequencerSetVerifyHash (185:217) — zero for genesis
 	// parentBatchHash (217:249) — zero for genesis
-	binary.BigEndian.PutUint64(header[249:], genesisHeader.Number.Uint64()) // lastBlockNumber (= 0 for fresh genesis)
+	binary.BigEndian.PutUint64(header[248:], genesisHeader.Number.Uint64()) // lastBlockNumber (= 0 for fresh genesis)
 	return header, nil
 }
```

## B008 putuint64_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:65:36 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -62,6 +62,6 @@
 	// withdrawalRoot (153:185) — zero for genesis
 	// sequencerSetVerifyHash (185:217) — zero for genesis
 	// parentBatchHash (217:249) — zero for genesis
-	binary.BigEndian.PutUint64(header[249:], genesisHeader.Number.Uint64()) // lastBlockNumber (= 0 for fresh genesis)
+	binary.BigEndian.PutUint64(header[250:], genesisHeader.Number.Uint64()) // lastBlockNumber (= 0 for fresh genesis)
 	return header, nil
 }
```

## B009 copy_offset -1 common/batch/batch_data.go:108:16 (*morph-l2/common/batch.BatchData).calculateHash

```diff
--- a/common/batch/batch_data.go
+++ b/common/batch/batch_data.go
@@ -105,7 +105,7 @@
 	hashData := make([]byte, 8+2+len(cks.l1TxHashes)) // 8 bytes for height, 2 bytes for l1TxNum
 	copy(hashData[:8], Uint64ToBigEndianBytes(height))
 	copy(hashData[8:10], Uint16ToBigEndianBytes(cks.l1TxNum))
-	copy(hashData[10:], cks.l1TxHashes)
+	copy(hashData[9:], cks.l1TxHashes)
 
 	return crypto.Keccak256Hash(hashData)
 }
```

## B010 copy_offset +1 common/batch/batch_data.go:108:16 (*morph-l2/common/batch.BatchData).calculateHash

```diff
--- a/common/batch/batch_data.go
+++ b/common/batch/batch_data.go
@@ -105,7 +105,7 @@
 	hashData := make([]byte, 8+2+len(cks.l1TxHashes)) // 8 bytes for height, 2 bytes for l1TxNum
 	copy(hashData[:8], Uint64ToBigEndianBytes(height))
 	copy(hashData[8:10], Uint16ToBigEndianBytes(cks.l1TxNum))
-	copy(hashData[10:], cks.l1TxHashes)
+	copy(hashData[11:], cks.l1TxHashes)
 
 	return crypto.Keccak256Hash(hashData)
 }
```

## B011 copy_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:58:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -55,7 +55,7 @@
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
-	copy(header[25:], dataHash[:])
+	copy(header[24:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
 	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
```

## B012 copy_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:58:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -55,7 +55,7 @@
 	binary.BigEndian.PutUint64(header[1:], 0)  // batchIndex
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
-	copy(header[25:], dataHash[:])
+	copy(header[26:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
 	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
```

## B013 copy_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:59:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -56,7 +56,7 @@
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
-	copy(header[57:], emptyBlobVersionedHash[:])
+	copy(header[56:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
 	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
 	// withdrawalRoot (153:185) — zero for genesis
```

## B014 copy_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:59:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -56,7 +56,7 @@
 	binary.BigEndian.PutUint64(header[9:], 0)  // l1MessagePopped
 	binary.BigEndian.PutUint64(header[17:], 0) // totalL1MessagePopped
 	copy(header[25:], dataHash[:])
-	copy(header[57:], emptyBlobVersionedHash[:])
+	copy(header[58:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
 	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
 	// withdrawalRoot (153:185) — zero for genesis
```

## B015 copy_offset -1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:61:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -58,7 +58,7 @@
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
-	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
+	copy(header[120:], genesisHeader.Root[:]) // postStateRoot
 	// withdrawalRoot (153:185) — zero for genesis
 	// sequencerSetVerifyHash (185:217) — zero for genesis
 	// parentBatchHash (217:249) — zero for genesis
```

## B016 copy_offset +1 ops/l2-genesis/morph-chain-ops/genesis/batch.go:61:14 morph-l2/morph-deployer/morph-chain-ops/genesis.GenesisBatchHeader

```diff
--- a/ops/l2-genesis/morph-chain-ops/genesis/batch.go
+++ b/ops/l2-genesis/morph-chain-ops/genesis/batch.go
@@ -58,7 +58,7 @@
 	copy(header[25:], dataHash[:])
 	copy(header[57:], emptyBlobVersionedHash[:])
 	// prevStateRoot (89:121) — zero for genesis
-	copy(header[121:], genesisHeader.Root[:]) // postStateRoot
+	copy(header[122:], genesisHeader.Root[:]) // postStateRoot
 	// withdrawalRoot (153:185) — zero for genesis
 	// sequencerSetVerifyHash (185:217) — zero for genesis
 	// parentBatchHash (217:249) — zero for genesis
```

## B017 drop_len_check drop common/batch/batch_cache.go:1097:4 morph-l2/common/batch.validateLegacyTransitionRecord

```diff
--- a/common/batch/batch_cache.go
+++ b/common/batch/batch_cache.go
@@ -1094,9 +1094,9 @@
 		if version >= BatchHeaderVersion2 {
 			sidecarCommitHash = aggregateBlobHashes(blobHashes)
 		} else {
-			if len(blobHashes) != 1 {
-				return fmt.Errorf("batch %d header version %d requires exactly one blob, got %d", index, version, len(blobHashes))
-			}
+			{}
+
+
 			sidecarCommitHash = blobHashes[0]
 		}
 		headerCommitHash, err := header.BlobCommitHash()
```

## B018 drop_len_check drop common/batch/batch_data.go:85:2 (*morph-l2/common/batch.BatchData).DataHashV2

```diff
--- a/common/batch/batch_data.go
+++ b/common/batch/batch_data.go
@@ -82,9 +82,9 @@
 // the last block height, L1 transaction count, and L1 transaction hashes.
 func (cks *BatchData) DataHashV2() (common.Hash, error) {
 	// Validate blockContexts length
-	if len(cks.blockContexts) < 60 {
-		return common.Hash{}, fmt.Errorf("blockContexts too short, length: %d", len(cks.blockContexts))
-	}
+	{}
+
+
 
 	// Extract the last 60 bytes
 	lastBlockContext := cks.blockContexts[len(cks.blockContexts)-60:]
```

## B019 drop_len_check drop common/batch/batch_storage.go:401:2 (*morph-l2/common/batch.BatchStorage).ValidateExactKeySet

```diff
--- a/common/batch/batch_storage.go
+++ b/common/batch/batch_storage.go
@@ -398,9 +398,9 @@
 		}
 		delete(expected, string(key))
 	}
-	if len(expected) != 0 {
-		return fmt.Errorf("sealed batch indices snapshot references %d missing persisted keys", len(expected))
-	}
+	{}
+
+
 	return nil
 }
 
```

## B020 drop_len_check drop node/derivation/batch_info.go:88:2 (*morph-l2/node/derivation.BatchInfo).ParseBatch

```diff
--- a/node/derivation/batch_info.go
+++ b/node/derivation/batch_info.go
@@ -85,9 +85,9 @@
 
 // ParseBatch This method is externally referenced for parsing Batch
 func (bi *BatchInfo) ParseBatch(batch geth.RPCRollupBatch) error {
-	if len(batch.Sidecar.Blobs) == 0 {
-		return fmt.Errorf("blobs length can not be zero")
-	}
+	{}
+
+
 	parentBatchHeader := commonbatch.BatchHeaderBytes(batch.ParentBatchHeader)
 	parentBatchIndex, err := parentBatchHeader.BatchIndex()
 	if err != nil {
```

## B021 drop_len_check drop node/derivation/batch_info.go:137:4 (*morph-l2/node/derivation.BatchInfo).ParseBatch

```diff
--- a/node/derivation/batch_info.go
+++ b/node/derivation/batch_info.go
@@ -134,9 +134,9 @@
 			// V0 -> V1+ transition: parent header carries no LastBlockNumber,
 			// so derive blockCount from the first block context embedded at
 			// the start of the decompressed batch.
-			if len(batchBytes) < 60 {
-				return fmt.Errorf("decompressed batch too short for start block context: have %d, need 60", len(batchBytes))
-			}
+			{}
+
+
 			var startBlock BlockContext
 			if err := startBlock.Decode(batchBytes[:60]); err != nil {
 				return fmt.Errorf("decode chunk block context error:%v", err)
```

## B022 drop_len_check drop node/derivation/batch_info.go:170:3 (*morph-l2/node/derivation.BatchInfo).ParseBatch

```diff
--- a/node/derivation/batch_info.go
+++ b/node/derivation/batch_info.go
@@ -167,9 +167,9 @@
 		// Block contexts come from calldata; the entire decompressed stream
 		// is tx payload data. ABI-decoded `bytes` can be a non-nil zero/short
 		// slice, so guard the 2-byte block-count prefix read explicitly.
-		if len(batch.BlockContexts) < 2 {
-			return fmt.Errorf("calldata block contexts too short for block count prefix: have %d, need 2", len(batch.BlockContexts))
-		}
+		{}
+
+
 		blockCount = uint64(binary.BigEndian.Uint16(batch.BlockContexts[:2]))
 		if uint64(len(batch.BlockContexts)) < 2+60*blockCount {
 			return fmt.Errorf("calldata block contexts too short: have %d, need %d", len(batch.BlockContexts), 2+60*blockCount)
```

## B023 drop_len_check drop node/types/batch_header.go:59:3 (morph-l2/node/types.BatchHeaderBytes).validate

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -56,9 +56,9 @@
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

## B024 drop_len_check drop node/types/batch_header.go:63:3 (morph-l2/node/types.BatchHeaderBytes).validate

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -60,9 +60,9 @@
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

## B025 drop_len_check drop node/types/batch_header.go:67:3 (morph-l2/node/types.BatchHeaderBytes).validate

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -64,9 +64,9 @@
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

## B026 drop_len_check drop node/types/batch_header.go:88:2 (morph-l2/node/types.BatchHeaderBytes).Version

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -85,9 +85,9 @@
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

## B027 go_slice_offset -1 node/types/batch_header.go:98:35 (morph-l2/node/types.BatchHeaderBytes).BatchIndex

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -95,7 +95,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[1:9]), nil
+	return binary.BigEndian.Uint64(b[0:8]), nil
 }
 
 func (b BatchHeaderBytes) L1MessagePopped() (uint64, error) {
```

## B028 go_slice_offset +1 node/types/batch_header.go:98:35 (morph-l2/node/types.BatchHeaderBytes).BatchIndex

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -95,7 +95,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[1:9]), nil
+	return binary.BigEndian.Uint64(b[2:10]), nil
 }
 
 func (b BatchHeaderBytes) L1MessagePopped() (uint64, error) {
```

## B029 go_slice_offset -1 node/types/batch_header.go:105:35 (morph-l2/node/types.BatchHeaderBytes).L1MessagePopped

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -102,7 +102,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[9:17]), nil
+	return binary.BigEndian.Uint64(b[8:16]), nil
 }
 
 func (b BatchHeaderBytes) TotalL1MessagePopped() (uint64, error) {
```

## B030 go_slice_offset +1 node/types/batch_header.go:105:35 (morph-l2/node/types.BatchHeaderBytes).L1MessagePopped

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -102,7 +102,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[9:17]), nil
+	return binary.BigEndian.Uint64(b[10:18]), nil
 }
 
 func (b BatchHeaderBytes) TotalL1MessagePopped() (uint64, error) {
```

## B031 go_slice_offset -1 node/types/batch_header.go:112:35 (morph-l2/node/types.BatchHeaderBytes).TotalL1MessagePopped

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -109,7 +109,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[17:25]), nil
+	return binary.BigEndian.Uint64(b[16:24]), nil
 }
 
 func (b BatchHeaderBytes) DataHash() (common.Hash, error) {
```

## B032 go_slice_offset +1 node/types/batch_header.go:112:35 (morph-l2/node/types.BatchHeaderBytes).TotalL1MessagePopped

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -109,7 +109,7 @@
 	if err := b.validate(); err != nil {
 		return 0, err
 	}
-	return binary.BigEndian.Uint64(b[17:25]), nil
+	return binary.BigEndian.Uint64(b[18:26]), nil
 }
 
 func (b BatchHeaderBytes) DataHash() (common.Hash, error) {
```

## B033 go_slice_offset -1 node/types/batch_header.go:119:30 (morph-l2/node/types.BatchHeaderBytes).DataHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -116,7 +116,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[25:57]), nil
+	return common.BytesToHash(b[24:56]), nil
 }
 
 // BlobVersionedHash returns the EIP-4844 blob versioned hash recorded at
```

## B034 go_slice_offset +1 node/types/batch_header.go:119:30 (morph-l2/node/types.BatchHeaderBytes).DataHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -116,7 +116,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[25:57]), nil
+	return common.BytesToHash(b[26:58]), nil
 }
 
 // BlobVersionedHash returns the EIP-4844 blob versioned hash recorded at
```

## B035 go_slice_offset -1 node/types/batch_header.go:134:30 (morph-l2/node/types.BatchHeaderBytes).BlobVersionedHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -131,7 +131,7 @@
 	if version >= BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobVersionedHash is not available for V2+; use BlobHashesHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[56:88]), nil
 }
 
 // BlobHashesHash returns the aggregated blob hash recorded at offset [57:89]
```

## B036 go_slice_offset +1 node/types/batch_header.go:134:30 (morph-l2/node/types.BatchHeaderBytes).BlobVersionedHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -131,7 +131,7 @@
 	if version >= BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobVersionedHash is not available for V2+; use BlobHashesHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[58:90]), nil
 }
 
 // BlobHashesHash returns the aggregated blob hash recorded at offset [57:89]
```

## B037 go_slice_offset -1 node/types/batch_header.go:148:30 (morph-l2/node/types.BatchHeaderBytes).BlobHashesHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -145,7 +145,7 @@
 	if version < BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobHashesHash is only available for V2+; use BlobVersionedHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[56:88]), nil
 }
 
 func (b BatchHeaderBytes) PrevStateRoot() (common.Hash, error) {
```

## B038 go_slice_offset +1 node/types/batch_header.go:148:30 (morph-l2/node/types.BatchHeaderBytes).BlobHashesHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -145,7 +145,7 @@
 	if version < BatchHeaderVersion2 {
 		return common.Hash{}, errors.New("BlobHashesHash is only available for V2+; use BlobVersionedHash")
 	}
-	return common.BytesToHash(b[57:89]), nil
+	return common.BytesToHash(b[58:90]), nil
 }
 
 func (b BatchHeaderBytes) PrevStateRoot() (common.Hash, error) {
```

## B039 go_slice_offset -1 node/types/batch_header.go:155:30 (morph-l2/node/types.BatchHeaderBytes).PrevStateRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -152,7 +152,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[89:121]), nil
+	return common.BytesToHash(b[88:120]), nil
 }
 
 func (b BatchHeaderBytes) PostStateRoot() (common.Hash, error) {
```

## B040 go_slice_offset +1 node/types/batch_header.go:155:30 (morph-l2/node/types.BatchHeaderBytes).PrevStateRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -152,7 +152,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[89:121]), nil
+	return common.BytesToHash(b[90:122]), nil
 }
 
 func (b BatchHeaderBytes) PostStateRoot() (common.Hash, error) {
```

## B041 go_slice_offset -1 node/types/batch_header.go:162:30 (morph-l2/node/types.BatchHeaderBytes).PostStateRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -159,7 +159,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[121:153]), nil
+	return common.BytesToHash(b[120:152]), nil
 }
 
 func (b BatchHeaderBytes) WithdrawalRoot() (common.Hash, error) {
```

## B042 go_slice_offset +1 node/types/batch_header.go:162:30 (morph-l2/node/types.BatchHeaderBytes).PostStateRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -159,7 +159,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[121:153]), nil
+	return common.BytesToHash(b[122:154]), nil
 }
 
 func (b BatchHeaderBytes) WithdrawalRoot() (common.Hash, error) {
```

## B043 go_slice_offset -1 node/types/batch_header.go:169:30 (morph-l2/node/types.BatchHeaderBytes).WithdrawalRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -166,7 +166,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[153:185]), nil
+	return common.BytesToHash(b[152:184]), nil
 }
 
 func (b BatchHeaderBytes) SequencerSetVerifyHash() (common.Hash, error) {
```

## B044 go_slice_offset +1 node/types/batch_header.go:169:30 (morph-l2/node/types.BatchHeaderBytes).WithdrawalRoot

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -166,7 +166,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[153:185]), nil
+	return common.BytesToHash(b[154:186]), nil
 }
 
 func (b BatchHeaderBytes) SequencerSetVerifyHash() (common.Hash, error) {
```

## B045 go_slice_offset -1 node/types/batch_header.go:176:30 (morph-l2/node/types.BatchHeaderBytes).SequencerSetVerifyHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -173,7 +173,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[185:217]), nil
+	return common.BytesToHash(b[184:216]), nil
 }
 
 func (b BatchHeaderBytes) ParentBatchHash() (common.Hash, error) {
```

## B046 go_slice_offset +1 node/types/batch_header.go:176:30 (morph-l2/node/types.BatchHeaderBytes).SequencerSetVerifyHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -173,7 +173,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[185:217]), nil
+	return common.BytesToHash(b[186:218]), nil
 }
 
 func (b BatchHeaderBytes) ParentBatchHash() (common.Hash, error) {
```

## B047 go_slice_offset -1 node/types/batch_header.go:183:30 (morph-l2/node/types.BatchHeaderBytes).ParentBatchHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -180,7 +180,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[217:249]), nil
+	return common.BytesToHash(b[216:248]), nil
 }
 
 func (b BatchHeaderBytes) LastBlockNumber() (uint64, error) {
```

## B048 go_slice_offset +1 node/types/batch_header.go:183:30 (morph-l2/node/types.BatchHeaderBytes).ParentBatchHash

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -180,7 +180,7 @@
 	if err := b.validate(); err != nil {
 		return common.Hash{}, err
 	}
-	return common.BytesToHash(b[217:249]), nil
+	return common.BytesToHash(b[218:250]), nil
 }
 
 func (b BatchHeaderBytes) LastBlockNumber() (uint64, error) {
```

## B049 go_slice_offset -1 node/types/batch_header.go:194:35 (morph-l2/node/types.BatchHeaderBytes).LastBlockNumber

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -191,5 +191,5 @@
 	if version < 1 {
 		return 0, errors.New("LastBlockNumber is not available in version 0")
 	}
-	return binary.BigEndian.Uint64(b[249:257]), nil
+	return binary.BigEndian.Uint64(b[248:256]), nil
 }
```

## B050 go_slice_offset +1 node/types/batch_header.go:194:35 (morph-l2/node/types.BatchHeaderBytes).LastBlockNumber

```diff
--- a/node/types/batch_header.go
+++ b/node/types/batch_header.go
@@ -191,5 +191,5 @@
 	if version < 1 {
 		return 0, errors.New("LastBlockNumber is not available in version 0")
 	}
-	return binary.BigEndian.Uint64(b[249:257]), nil
+	return binary.BigEndian.Uint64(b[250:258]), nil
 }
```
