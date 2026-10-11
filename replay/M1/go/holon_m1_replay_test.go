package batch

// HOLON M1 replay, M0-closure side: drive the REAL v2 batch-header producer
// createBatchHeaderWithSequencerSetHash (batch_cache.go) on a hand-built
// BatchCache, and check byte0 == 2, sequencerSetVerifyHash == 0, and that the
// 257 output bytes equal the generated model's enc_go_v2_producer evaluated
// through holon/model_eval on the same field values.

import (
	"bytes"
	"encoding/hex"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
	"morph-l2/common/blob"
)

// Expected header bytes: output of the compiled Bend model's
// enc_go_v2_producer (facts proposals/M1/facts/morph_header_m1.json) on the
// field values used below, evaluated via `python3 -m holon` model_eval.
var wantV2Hex = "0x02000000000000000100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000da7aadb7d19fe5d8965c5e38fa14434d14cdbc6fb677ba675d1b7157ef649f1a4d87000000000000000000000000000000000000000000000000000000000000beef000000000000000000000000000000000000000000000000000000000000100100000000000000000000000000000000000000000000000000000000000077aa0000000000000000000000000000000000000000000000000000000000000000ab6640fc302397224d914ed4e0f1b77920eee1eeb049c770d2cd090e8c37be3d00000000000003e8"

func mustHash(hexs string) common.Hash {
	return common.HexToHash(hexs)
}

func TestCreateBatchHeaderV2Producer(t *testing.T) {
	// Genesis parent: real V0 header bytes for the same genesis the Solidity
	// harness imported (index 0, postStateRoot 0x..beef, dataHash 0x..da7a,
	// blobVersionedHash = EMPTY).
	parent := BatchHeaderV0{
		BatchIndex:           0,
		DataHash:             mustHash("0x000000000000000000000000000000000000000000000000000000000000da7a"),
		BlobVersionedHash:    blob.EmptyVersionedHash,
		PostStateRoot:        mustHash("0x000000000000000000000000000000000000000000000000000000000000beef"),
	}
	parentBytes := parent.Bytes()
	if len(parentBytes) != 249 {
		t.Fatalf("v0 header length = %d, want 249", len(parentBytes))
	}

	bc := &BatchCache{
		parentBatchHeader:     &parentBytes,
		totalL1MessagePopped:  0,
		prevStateRoot:         mustHash("0x000000000000000000000000000000000000000000000000000000000000beef"),
		postStateRoot:         mustHash("0x0000000000000000000000000000000000000000000000000000000000001001"),
		withdrawRoot:          mustHash("0x00000000000000000000000000000000000000000000000000000000000077aa"),
		lastPackedBlockHeight: 1000,
		isBatchUpgraded:       func(uint64) bool { return true },
		isBatchV2Upgraded:     func(uint64) bool { return true },
	}

	dataHash := mustHash("0x000000000000000000000000000000000000000000000000000000000000da7a")
	// sidecar == nil -> blobHashes = [blob.EmptyVersionedHash], so the stored
	// blobVersionedHash is aggregateBlobHashes([EMPTY]) = keccak256(EMPTY).
	got := bc.createBatchHeaderWithSequencerSetHash(dataHash, nil, common.Hash{}, 1)

	if got[0] != BatchHeaderVersion2 {
		t.Fatalf("byte0 = %d, want BatchHeaderVersion2 (2)", got[0])
	}
	ssvh, err := got.SequencerSetVerifyHash()
	if err != nil {
		t.Fatal(err)
	}
	if ssvh != (common.Hash{}) {
		t.Fatalf("sequencerSetVerifyHash = %s, want zero", ssvh)
	}
	want, err := hex.DecodeString(wantV2Hex[2:])
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("header mismatch:\n got: 0x%x\nwant: %s", []byte(got), wantV2Hex)
	}
	if len(got) != 257 {
		t.Fatalf("header length = %d, want 257", len(got))
	}
}
