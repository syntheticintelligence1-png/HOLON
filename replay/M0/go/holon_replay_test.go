// HOLON M0 replay harness (Go side). Copied into a scratch copy of morph common/batch
// by holon/replay.py and run with `go test -run TestHolonReplay -v`.
//
// It reads the REFUTED witnesses from $HOLON_RESULTS/<law>.json and runs them through
// the real code at the pinned commit. Each subtest logs one line
//   HOLON <law> passed|failed <observed>
// which holon/replay.py parses into replay/M0/report.json.
package batch

import (
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

type holonRecord struct {
	Status  string                     `json:"status"`
	Witness map[string]json.RawMessage `json:"witness"`
}

func holonLoad(t *testing.T, law string) holonRecord {
	dir := os.Getenv("HOLON_RESULTS")
	if dir == "" {
		t.Fatal("HOLON_RESULTS is not set")
	}
	raw, err := os.ReadFile(filepath.Join(dir, law+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var r holonRecord
	if err := json.Unmarshal(raw, &r); err != nil {
		t.Fatal(err)
	}
	if r.Status != "REFUTED" {
		t.Fatalf("%s is %s, not REFUTED", law, r.Status)
	}
	return r
}

func holonHex(t *testing.T, s string) []byte {
	b, err := hex.DecodeString(strings.TrimPrefix(s, "0x"))
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func holonHeader(t *testing.T, r holonRecord) map[string][]byte {
	var h map[string]string
	if err := json.Unmarshal(r.Witness["h"], &h); err != nil {
		t.Fatal(err)
	}
	out := map[string][]byte{}
	for k, v := range h {
		out[k] = holonHex(t, v)
	}
	return out
}

func holonU64(b []byte) uint64 {
	var x uint64
	for _, c := range b {
		x = x<<8 | uint64(c)
	}
	return x
}

func holonV1(h map[string][]byte) BatchHeaderV1 {
	return BatchHeaderV1{
		BatchHeaderV0: BatchHeaderV0{
			BatchIndex:             holonU64(h["batchIndex"]),
			L1MessagePopped:        holonU64(h["l1MessagePopped"]),
			TotalL1MessagePopped:   holonU64(h["totalL1MessagePopped"]),
			DataHash:               common.BytesToHash(h["dataHash"]),
			BlobVersionedHash:      common.BytesToHash(h["blobVersionedHash"]),
			PrevStateRoot:          common.BytesToHash(h["prevStateHash"]),
			PostStateRoot:          common.BytesToHash(h["postStateHash"]),
			WithdrawalRoot:         common.BytesToHash(h["withdrawRootHash"]),
			SequencerSetVerifyHash: common.BytesToHash(h["sequencerSetVerifyHash"]),
			ParentBatchHash:        common.BytesToHash(h["parentBatchHash"]),
		},
		LastBlockNumber: holonU64(h["lastBlockNumber"]),
	}
}

func holonReport(t *testing.T, law string, ok bool, observed string) {
	status := "failed"
	if ok {
		status = "passed"
	}
	fmt.Printf("HOLON %s %s %s\n", law, status, observed)
	if !ok {
		t.Errorf("%s: real code disagrees with the model: %s", law, observed)
	}
}

func TestHolonReplay(t *testing.T) {
	// O2 / F12.2: Solidity commits version-2 headers with byte 0 = 2; the only Go encoder writes 1.
	t.Run("L_par_hdr_v2", func(t *testing.T) {
		h := holonHeader(t, holonLoad(t, "L_par_hdr_v2"))
		b := holonV1(h).Bytes()
		obs := fmt.Sprintf("witness version=%d; BatchHeaderV1.Bytes()[0]=%d; len=%d", h["version"][0], b[0], len(b))
		holonReport(t, "L_par_hdr_v2", h["version"][0] == 2 && b[0] == 1, obs)
	})
	// O1 / F12.1: a 250-byte version-0 header is accepted by Solidity, rejected by Go.
	t.Run("L_dom_hdr", func(t *testing.T) {
		r := holonLoad(t, "L_dom_hdr")
		var s string
		if err := json.Unmarshal(r.Witness["b"], &s); err != nil {
			t.Fatal(err)
		}
		b := BatchHeaderBytes(holonHex(t, s))
		_, herr := b.Hash()
		v, verr := b.Version()
		_, ierr := b.BatchIndex()
		obs := fmt.Sprintf("len=%d; Version()=(%d,%v); Hash() err=%v; BatchIndex() err=%v", len(b), v, verr, herr, ierr)
		holonReport(t, "L_dom_hdr", errors.Is(herr, ErrInvalidBatchHeaderLength) &&
			errors.Is(ierr, ErrInvalidBatchHeaderLength) && verr == nil && v == 0, obs)
	})
	// Intent question: Go copies SequencerSetVerifyHash; Solidity always commits zero there.
	t.Run("L_par_hdr_ssvh", func(t *testing.T) {
		h := holonHeader(t, holonLoad(t, "L_par_hdr_ssvh"))
		b := holonV1(h).Bytes()
		got := hex.EncodeToString(b[185:217])
		want := hex.EncodeToString(h["sequencerSetVerifyHash"])
		obs := fmt.Sprintf("Bytes()[185:217]=0x%s; witness ssvh=0x%s", got, want)
		holonReport(t, "L_par_hdr_ssvh", got == want && strings.Trim(want, "0") != "", obs)
	})
}
