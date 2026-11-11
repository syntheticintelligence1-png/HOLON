package batch

// Round 9 audit (A8, scratch only): the claims of the six I100 record laws (L_par_rec_*) and the three constant
// reads (L_par_rt_*_Version_v*) on the real Go code at the pinned commit. Not part of the target; copied into a
// scratch clone of the checkout, never into the checkout itself.

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"math/rand"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

func r9fill(r *rand.Rand, mode int, b []byte) {
	for i := range b {
		switch mode {
		case 0:
			b[i] = 0
		case 1:
			b[i] = 0xff
		case 2:
			b[i] = byte(i%255 + 1)
		default:
			b[i] = byte(r.Intn(256))
		}
	}
}

func r9v0(r *rand.Rand, mode int) BatchHeaderV0 {
	var w [8 * 3]byte
	r9fill(r, mode, w[:])
	var hs [7]common.Hash
	for i := range hs {
		r9fill(r, mode, hs[i][:])
	}
	return BatchHeaderV0{BatchIndex: binary.BigEndian.Uint64(w[0:8]), L1MessagePopped: binary.BigEndian.Uint64(w[8:16]),
		TotalL1MessagePopped: binary.BigEndian.Uint64(w[16:24]), DataHash: hs[0], BlobVersionedHash: hs[1],
		PrevStateRoot: hs[2], PostStateRoot: hs[3], WithdrawalRoot: hs[4], SequencerSetVerifyHash: hs[5], ParentBatchHash: hs[6]}
}

type r9chk struct{ bad []string }

func (c *r9chk) eqU(name string, got uint64, err error, want uint64) {
	if err != nil || got != want {
		c.bad = append(c.bad, fmt.Sprintf("%s: got %d err %v want %d", name, got, err, want))
	}
}
func (c *r9chk) eqH(name string, got common.Hash, err error, want common.Hash) {
	if err != nil || got != want {
		c.bad = append(c.bad, fmt.Sprintf("%s: got %x err %v want %x", name, got, err, want))
	}
}
func (c *r9chk) common(b BatchHeaderBytes, v uint8, h BatchHeaderV0) {
	ver, err := b.Version()
	if err != nil || ver != v {
		c.bad = append(c.bad, fmt.Sprintf("Version: got %d err %v want %d", ver, err, v))
	}
	x, e := b.BatchIndex()
	c.eqU("BatchIndex", x, e, h.BatchIndex)
	x, e = b.L1MessagePopped()
	c.eqU("L1MessagePopped", x, e, h.L1MessagePopped)
	x, e = b.TotalL1MessagePopped()
	c.eqU("TotalL1MessagePopped", x, e, h.TotalL1MessagePopped)
	y, e := b.DataHash()
	c.eqH("DataHash", y, e, h.DataHash)
	y, e = b.BlobCommitHash()
	c.eqH("BlobCommitHash", y, e, h.BlobVersionedHash)
	y, e = b.PrevStateRoot()
	c.eqH("PrevStateRoot", y, e, h.PrevStateRoot)
	y, e = b.PostStateRoot()
	c.eqH("PostStateRoot", y, e, h.PostStateRoot)
	y, e = b.WithdrawalRoot()
	c.eqH("WithdrawalRoot", y, e, h.WithdrawalRoot)
	y, e = b.SequencerSetVerifyHash()
	c.eqH("SequencerSetVerifyHash", y, e, h.SequencerSetVerifyHash)
	y, e = b.ParentBatchHash()
	c.eqH("ParentBatchHash", y, e, h.ParentBatchHash)
}

func TestR9RecordLaws(t *testing.T) {
	r := rand.New(rand.NewSource(20261111))
	n, fails := 0, 0
	report := func(law string, mode int, c *r9chk) {
		n++
		if len(c.bad) > 0 {
			fails++
			t.Errorf("%s mode %d: %v", law, mode, c.bad)
		}
	}
	for k := 0; k < 3003; k++ {
		mode := k
		if mode > 3 {
			mode = 3
		}
		h0 := r9v0(r, mode)
		// L_par_rec_BatchHeaderV0_Bytes_BatchHeaderBytes_v0 (+ the v0 constant read of Version)
		c := &r9chk{}
		b := h0.Bytes()
		c.common(b, 0, h0)
		y, e := b.BlobVersionedHash()
		c.eqH("BlobVersionedHash", y, e, h0.BlobVersionedHash)
		report("rec_V0_v0", mode, c)
		// L_par_rec_BatchHeaderV1_Bytes_BatchHeaderBytes_v1
		var lb [8]byte
		r9fill(r, mode, lb[:])
		h1 := BatchHeaderV1{BatchHeaderV0: h0, LastBlockNumber: binary.BigEndian.Uint64(lb[:])}
		c = &r9chk{}
		b = h1.Bytes()
		c.common(b, 1, h0)
		y, e = b.BlobVersionedHash()
		c.eqH("BlobVersionedHash", y, e, h0.BlobVersionedHash)
		x, e2 := b.LastBlockNumber()
		c.eqU("LastBlockNumber", x, e2, h1.LastBlockNumber)
		report("rec_V1_v1", mode, c)
		// L_par_rec_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_v2: the real function, V2 active;
		// the record it encodes is the V1 header it builds from the cache (no parent: index 1, parent hash zero)
		bc := &BatchCache{totalL1MessagePopped: h0.TotalL1MessagePopped, prevStateRoot: h0.PrevStateRoot,
			postStateRoot: h0.PostStateRoot, withdrawRoot: h0.WithdrawalRoot, lastPackedBlockHeight: h1.LastBlockNumber,
			isBatchUpgraded: func(uint64) bool { return true }, isBatchV2Upgraded: func(uint64) bool { return true }}
		b = bc.createBatchHeaderWithSequencerSetHash(h0.DataHash, nil, h0.SequencerSetVerifyHash, 1)
		want := BatchHeaderV0{BatchIndex: 1, L1MessagePopped: h0.TotalL1MessagePopped, TotalL1MessagePopped: h0.TotalL1MessagePopped,
			DataHash: h0.DataHash, PrevStateRoot: h0.PrevStateRoot, PostStateRoot: h0.PostStateRoot,
			WithdrawalRoot: h0.WithdrawalRoot, SequencerSetVerifyHash: h0.SequencerSetVerifyHash}
		y, e = b.BlobHashesHash()
		want.BlobVersionedHash = y // the aggregated hash, below the record abstraction; checked equal to BlobCommitHash
		c = &r9chk{}
		c.common(b, 2, want)
		c.eqH("BlobHashesHash", y, e, want.BlobVersionedHash)
		x, e2 = b.LastBlockNumber()
		c.eqU("LastBlockNumber", x, e2, h1.LastBlockNumber)
		if _, e := b.BlobVersionedHash(); e == nil {
			c.bad = append(c.bad, "BlobVersionedHash: no error at v2")
		}
		report("rec_create_v2", mode, c)
	}
	// the cache path (assumption A-codec-domain: an encoder's cache is its domain, not modelled): one witness per encoder
	h0 := r9v0(r, 2)
	h0.EncodedBytes = []byte{7}
	cv, _ := h0.Bytes().Version()
	_, ce := h0.Bytes().BatchIndex()
	t.Logf("A-codec-domain: V0 with EncodedBytes=0x07: Version()=%d, BatchIndex() err=%v, equal to fresh encoding: %v",
		cv, ce, bytes.Equal(h0.Bytes(), BatchHeaderV0{BatchIndex: h0.BatchIndex}.Bytes()))
	t.Logf("R9 record laws: %d instances, %d with a failing claim", n, fails)
}
