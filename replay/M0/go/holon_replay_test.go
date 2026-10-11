package batch

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

type holonRecord struct {
	LawID   string                     `json:"law_id"`
	Status  string                     `json:"status"`
	Witness map[string]json.RawMessage `json:"witness"`
}

func loadRecord(t *testing.T, law string) holonRecord {
	dir := os.Getenv("HOLON_RESULTS")
	if dir == "" {
		t.Skip("HOLON_RESULTS not set")
	}
	raw, err := os.ReadFile(filepath.Join(dir, law+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var r holonRecord
	if err := json.Unmarshal(raw, &r); err != nil {
		t.Fatal(err)
	}
	if r.Status != "REFUTED" || len(r.Witness) != 1 {
		t.Fatalf("%s: status %s, %d binders", law, r.Status, len(r.Witness))
	}
	return r
}

func onlyBinder(r holonRecord) json.RawMessage {
	for _, v := range r.Witness {
		return v
	}
	return nil
}

func hexBytes(t *testing.T, s string, width int) []byte {
	s = strings.TrimPrefix(strings.TrimPrefix(s, "0x"), "0X")
	if len(s)%2 == 1 {
		s = "0" + s
	}
	b, err := hex.DecodeString(s)
	if err != nil {
		t.Fatal(err)
	}
	if width < 0 {
		return b
	}
	if len(b) > width {
		t.Fatalf("value %s wider than %d bytes", s, width)
	}
	return append(make([]byte, width-len(b)), b...)
}

func witnessHeader(t *testing.T, r holonRecord) (uint8, BatchHeaderV1) {
	var m map[string]string
	if err := json.Unmarshal(onlyBinder(r), &m); err != nil {
		t.Fatalf("header witness: %v", err)
	}
	u64 := func(k string) uint64 { return binary.BigEndian.Uint64(hexBytes(t, m[k], 8)) }
	h32 := func(k string) common.Hash { return common.BytesToHash(hexBytes(t, m[k], 32)) }
	v0 := BatchHeaderV0{
		BatchIndex:             u64("batchIndex"),
		L1MessagePopped:        u64("l1MessagePopped"),
		TotalL1MessagePopped:   u64("totalL1MessagePopped"),
		DataHash:               h32("dataHash"),
		BlobVersionedHash:      h32("blobVersionedHash"),
		PrevStateRoot:          h32("prevStateHash"),
		PostStateRoot:          h32("postStateHash"),
		WithdrawalRoot:         h32("withdrawRootHash"),
		SequencerSetVerifyHash: h32("sequencerSetVerifyHash"),
		ParentBatchHash:        h32("parentBatchHash"),
	}
	return hexBytes(t, m["version"], 1)[0], BatchHeaderV1{BatchHeaderV0: v0, LastBlockNumber: u64("lastBlockNumber")}
}

func TestHolonReplay_L_par_hdr_v2(t *testing.T) {
	version, h := witnessHeader(t, loadRecord(t, "L_par_hdr_v2"))
	if version != 2 {
		t.Fatalf("witness version %d, want 2", version)
	}
	got := h.Bytes()
	if len(got) != 257 || got[0] != 1 {
		t.Fatalf("BatchHeaderV1.Bytes(): len %d byte0 %d; model predicted len 257 byte0 1", len(got), got[0])
	}
	t.Logf("OBSERVED witness.version=2; BatchHeaderV1{witness}.Bytes() len=%d byte0=%d", len(got), got[0])
}

func TestHolonReplay_L_dom_hdr(t *testing.T) {
	var s string
	if err := json.Unmarshal(onlyBinder(loadRecord(t, "L_dom_hdr")), &s); err != nil {
		t.Fatalf("bytes witness: %v", err)
	}
	b := BatchHeaderBytes(hexBytes(t, s, -1))
	if len(b) != 250 && (len(b) <= 249 || b[0] != 0) {
		t.Fatalf("witness len %d byte0 %d is not a version-0 header longer than 249", len(b), b[0])
	}
	_, err := b.Hash()
	if !errors.Is(err, ErrInvalidBatchHeaderLength) {
		t.Fatalf("Hash() err = %v, want ErrInvalidBatchHeaderLength", err)
	}
	v, verr := b.Version()
	if verr != nil || v != 0 {
		t.Fatalf("Version() = %d, %v; want 0, nil (Version does not validate)", v, verr)
	}
	getters := map[string]func() error{
		"BatchIndex":             func() error { _, e := b.BatchIndex(); return e },
		"L1MessagePopped":        func() error { _, e := b.L1MessagePopped(); return e },
		"TotalL1MessagePopped":   func() error { _, e := b.TotalL1MessagePopped(); return e },
		"DataHash":               func() error { _, e := b.DataHash(); return e },
		"BlobCommitHash":         func() error { _, e := b.BlobCommitHash(); return e },
		"PrevStateRoot":          func() error { _, e := b.PrevStateRoot(); return e },
		"PostStateRoot":          func() error { _, e := b.PostStateRoot(); return e },
		"WithdrawalRoot":         func() error { _, e := b.WithdrawalRoot(); return e },
		"SequencerSetVerifyHash": func() error { _, e := b.SequencerSetVerifyHash(); return e },
		"ParentBatchHash":        func() error { _, e := b.ParentBatchHash(); return e },
		"LastBlockNumber":        func() error { _, e := b.LastBlockNumber(); return e },
	}
	for name, g := range getters {
		if e := g(); !errors.Is(e, ErrInvalidBatchHeaderLength) {
			t.Errorf("%s() err = %v, want ErrInvalidBatchHeaderLength", name, e)
		}
	}
	t.Logf("OBSERVED len=%d byte0=%d; Hash() err=%q; Version()=(0,nil); all 11 validating getters err=%q", len(b), b[0], err, ErrInvalidBatchHeaderLength)
}

func TestHolonReplay_L_par_hdr_ssvh(t *testing.T) {
	_, h := witnessHeader(t, loadRecord(t, "L_par_hdr_ssvh"))
	want := h.SequencerSetVerifyHash
	if want == (common.Hash{}) {
		t.Fatal("witness sequencerSetVerifyHash is zero")
	}
	got := h.Bytes()
	if common.BytesToHash(got[185:217]) != want {
		t.Fatalf("Bytes()[185:217] = %x, want %x", got[185:217], want)
	}
	t.Logf("OBSERVED Bytes()[185:217]=%x (nonzero witness ssvh copied verbatim; Solidity writes bytes32(0) at Rollup.sol:351)", got[185:217])
}
