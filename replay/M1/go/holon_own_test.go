// HOLON M1 replay (Go side, OWN rule). holon/mreplay.py copies this into a scratch copy of morph
// common/batch and runs `go test -run TestHolonOwnReplay -v`. It replays the L_own_txspayload witness
// (from $HOLON_RESULTS/L_own_txspayload.json) on the REAL BatchData and logs
//   HOLON L_own_txspayload passed|failed <observed>
package batch

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

type holonOwnStep struct {
	Op      string `json:"op"`
	Bctx    []int  `json:"bctx"`
	Payload []int  `json:"payload"`
}

func holonBytes(xs []int) []byte {
	b := make([]byte, len(xs))
	for i, x := range xs {
		b[i] = byte(x)
	}
	return b
}

func TestHolonOwnReplay(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(os.Getenv("HOLON_RESULTS"), "L_own_txspayload.json"))
	if err != nil {
		t.Fatal(err)
	}
	var rec struct {
		Status  string                    `json:"status"`
		Witness map[string][]holonOwnStep `json:"witness"`
	}
	if err := json.Unmarshal(raw, &rec); err != nil {
		t.Fatal(err)
	}
	if rec.Status != "REFUTED" {
		t.Fatalf("L_own_txspayload is %s", rec.Status)
	}
	d := NewBatchData()
	var view, snap []byte
	held := false
	for _, s := range rec.Witness["p"] {
		switch s.Op {
		case "append":
			d.Append(holonBytes(s.Bctx), holonBytes(s.Payload), nil)
		case "txsPayloadV2":
			view = d.TxsPayloadV2()
			snap = append([]byte(nil), view...)
			held = true
		default:
			t.Fatalf("unknown op %s", s.Op)
		}
	}
	changed := held && !bytes.Equal(view, snap)
	obs := fmt.Sprintf("view held across Append: len=%d cap(blockContexts)=%d changed=%v first-diff=%d (Go %s)",
		len(view), cap(d.blockContexts), changed, firstDiff(view, snap), os.Getenv("HOLON_GOVERSION"))
	status := "failed"
	if changed {
		status = "passed"
	}
	fmt.Printf("HOLON L_own_txspayload %s %s\n", status, obs)
	if !changed {
		t.Errorf("real code did not show the aliasing the model predicts: %s", obs)
	}
}

// The realistic configuration: 60-byte block contexts, 1-byte payloads (blocks with few txs).
func TestHolonOwnRealistic(t *testing.T) {
	d := NewBatchData()
	ctx := func(k byte) []byte { return bytes.Repeat([]byte{k}, 60) }
	for k := byte(1); k <= 3; k++ {
		d.Append(ctx(k), []byte{k}, nil)
	}
	view := d.TxsPayloadV2()
	snap := append([]byte(nil), view...)
	d.Append(ctx(4), []byte{4}, nil)
	changed := !bytes.Equal(view, snap)
	fmt.Printf("HOLON realistic %v len=%d cap(blockContexts)=%d first-diff=%d\n", changed, len(view), cap(d.blockContexts), firstDiff(view, snap))
}

func firstDiff(a, b []byte) int {
	for i := range a {
		if i >= len(b) || a[i] != b[i] {
			return i
		}
	}
	return -1
}
