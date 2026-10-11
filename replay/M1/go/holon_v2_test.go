// HOLON M1 replay (Go side, L_par_hdr_v2_composed). holon/mreplay.py copies this into a scratch
// copy of morph common/ and runs `go test -run 'TestHolon(Own|V2)'`. It drives the REAL v2
// producer BatchCache.createBatchHeaderWithSequencerSetHash (batch_cache.go:1684-1731 — the
// V1.Bytes() + h[0]=BatchHeaderVersion2 patch) on a hand-built BatchCache and logs the produced
// 257-byte header as
//   HOLON_V2_GO 0x<hex>
// byte0 == 2 and a zero sequencerSetVerifyHash are asserted here; mreplay.py decodes the bytes
// and compares them to the compiled model's enc_go_v2_producer on the same field values.
package batch

import (
	"fmt"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
	"morph-l2/common/blob"
)

func TestHolonV2Producer(t *testing.T) {
	parent := BatchHeaderV0{
		BatchIndex:        0,
		DataHash:          common.HexToHash("0x000000000000000000000000000000000000000000000000000000000000da7a"),
		BlobVersionedHash: blob.EmptyVersionedHash,
		PostStateRoot:     common.HexToHash("0x000000000000000000000000000000000000000000000000000000000000beef"),
	}
	parentBytes := parent.Bytes()
	if len(parentBytes) != 249 {
		t.Fatalf("v0 header length = %d, want 249", len(parentBytes))
	}

	bc := &BatchCache{
		parentBatchHeader:     &parentBytes,
		totalL1MessagePopped:  0,
		prevStateRoot:         common.HexToHash("0x000000000000000000000000000000000000000000000000000000000000beef"),
		postStateRoot:         common.HexToHash("0x0000000000000000000000000000000000000000000000000000000000001001"),
		withdrawRoot:          common.HexToHash("0x00000000000000000000000000000000000000000000000000000000000077aa"),
		lastPackedBlockHeight: 1000,
		isBatchUpgraded:       func(uint64) bool { return true },
		isBatchV2Upgraded:     func(uint64) bool { return true },
	}

	dataHash := common.HexToHash("0x000000000000000000000000000000000000000000000000000000000000da7a")
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
	if len(got) != 257 {
		t.Fatalf("header length = %d, want 257", len(got))
	}
	fmt.Printf("HOLON_V2_GO 0x%x\n", []byte(got))
}
