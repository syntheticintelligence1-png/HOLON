// HOLON M1 replay (Go side, L_par_hdr_v2_composed). holon/mreplay.py copies this into a scratch
// copy of morph common/ and runs `go test -run 'TestHolon(Own|V2)'`. It drives the REAL v2
// producer BatchCache.createBatchHeaderWithSequencerSetHash (batch_cache.go:1684-1731 — the
// V1.Bytes() + h[0]=BatchHeaderVersion2 patch) on hand-built BatchCache variants and logs one
// line per case as
//   HOLON_V2_GO <case> 0x<hex>
// byte0 == 2 and the 257-byte length are asserted here; sequencerSetVerifyHash is only asserted
// zero when the case passes a zero ssvh argument. mreplay.py decodes the bytes and compares each
// case to the compiled model's enc_go_v2_producer on the same field values.
package batch

import (
	"fmt"
	"math"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
	"morph-l2/common/blob"
)

type holonV2Case struct {
	name string
	bc   *BatchCache
	args struct {
		dataHash                common.Hash
		sequencerSetVerifyHash  common.Hash
		blockTimestamp          uint64
	}
}

func holonParent(index, totalL1 uint64, dataHash, postRoot common.Hash) *BatchHeaderBytes {
	parent := BatchHeaderV0{
		BatchIndex:            index,
		TotalL1MessagePopped:  totalL1,
		DataHash:              dataHash,
		BlobVersionedHash:     blob.EmptyVersionedHash,
		PostStateRoot:         postRoot,
	}
	b := parent.Bytes()
	if len(b) != 249 {
		panic(fmt.Sprintf("v0 header length = %d, want 249", len(b)))
	}
	hb := BatchHeaderBytes(b)
	return &hb
}

func holonBC(parent *BatchHeaderBytes, totalL1, lastHeight uint64, prev, post, wr common.Hash) *BatchCache {
	return &BatchCache{
		parentBatchHeader:     parent,
		totalL1MessagePopped:  totalL1,
		prevStateRoot:         prev,
		postStateRoot:         post,
		withdrawRoot:          wr,
		lastPackedBlockHeight: lastHeight,
		isBatchUpgraded:       func(uint64) bool { return true },
		isBatchV2Upgraded:     func(uint64) bool { return true },
	}
}

func TestHolonV2Producer(t *testing.T) {
	dh := common.HexToHash("0xda7a")
	prev := common.HexToHash("0xbeef")
	post := common.HexToHash("0x1001")
	wr := common.HexToHash("0x77aa")
	ssvh := common.HexToHash("0x5eed")

	cases := []holonV2Case{}
	add := func(name string, bc *BatchCache, dataHash, s common.Hash, ts uint64) {
		c := holonV2Case{name: name, bc: bc}
		c.args.dataHash = dataHash
		c.args.sequencerSetVerifyHash = s
		c.args.blockTimestamp = ts
		cases = append(cases, c)
	}

	add("base", holonBC(holonParent(0, 0, dh, prev), 0, 1000, prev, post, wr), dh, common.Hash{}, 1)

	// every uint64 field at max, nonzero roots and dataHash; child index wraps to 0
	maxDH := common.HexToHash("0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
	add("max_uint64",
		holonBC(holonParent(math.MaxUint64, 0, maxDH, maxDH),
			math.MaxUint64, math.MaxUint64, maxDH, maxDH, maxDH),
		maxDH, common.Hash{}, math.MaxUint64)

	add("nonzero_ssvh", holonBC(holonParent(0, 0, dh, prev), 0, 1000, prev, post, wr), dh, ssvh, 1)

	for _, c := range cases {
		// sidecar == nil -> blobHashes = [blob.EmptyVersionedHash], so the stored
		// blobVersionedHash is aggregateBlobHashes([EMPTY]) = keccak256(EMPTY).
		got := c.bc.createBatchHeaderWithSequencerSetHash(c.args.dataHash, nil, c.args.sequencerSetVerifyHash, c.args.blockTimestamp)
		if got[0] != BatchHeaderVersion2 {
			t.Fatalf("%s: byte0 = %d, want BatchHeaderVersion2 (2)", c.name, got[0])
		}
		if len(got) != 257 {
			t.Fatalf("%s: header length = %d, want 257", c.name, len(got))
		}
		if c.args.sequencerSetVerifyHash == (common.Hash{}) {
			s, err := got.SequencerSetVerifyHash()
			if err != nil {
				t.Fatal(err)
			}
			if s != (common.Hash{}) {
				t.Fatalf("%s: sequencerSetVerifyHash = %s, want zero", c.name, s)
			}
		}
		fmt.Printf("HOLON_V2_GO %s 0x%x\n", c.name, []byte(got))
	}
}
