// HOLON M3 PAR replay harness (Go side), I98. Copied into a scratch copy of morph common/batch by
// holon/replay.py (main_replay_par) and run with `go test -run TestHolonPar -v`.
//
// It reads the REFUTED witnesses from $HOLON_RESULTS/<law>.json and runs them through the real code
// at the pinned commit. Each subtest logs one line
//   HOLON <law> passed|failed <observed>
// which holon/replay.py parses into replay/M3/par/report.json. A subtest passes when the real code
// gives the claim's left side the value the witness's difference says it has.
package batch

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type holonParRecord struct {
	Status     string                     `json:"status"`
	Witness    map[string]json.RawMessage `json:"witness"`
	Difference map[string]json.RawMessage `json:"difference"`
}

func holonParLoad(t *testing.T, law string) holonParRecord {
	dir := os.Getenv("HOLON_RESULTS")
	if dir == "" {
		t.Fatal("HOLON_RESULTS is not set")
	}
	raw, err := os.ReadFile(filepath.Join(dir, law+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var r holonParRecord
	if err := json.Unmarshal(raw, &r); err != nil {
		t.Fatal(err)
	}
	if r.Status != "REFUTED" {
		t.Fatalf("%s: status %s, not REFUTED", law, r.Status)
	}
	return r
}

func holonParBytes(t *testing.T, r holonParRecord, name string) []byte {
	var s string
	if err := json.Unmarshal(r.Witness[name], &s); err != nil {
		t.Fatal(err)
	}
	b, err := hex.DecodeString(strings.TrimPrefix(s, "0x"))
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func holonParBool(t *testing.T, r holonParRecord, side string) bool {
	var v bool
	if err := json.Unmarshal(r.Difference[side], &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func holonParReport(t *testing.T, law string, ok bool, observed string) {
	status := "failed"
	if ok {
		status = "passed"
	}
	fmt.Printf("HOLON %s %s %s\n", law, status, observed)
	if !ok {
		t.Errorf("%s: real code disagrees with the model: %s", law, observed)
	}
}

func TestHolonPar(t *testing.T) {
	// BatchHeaderBytes_validate(b) == ok_load_sol(b): the left side is Go's validation of the header bytes.
	t.Run("L_par_dom_BatchHeaderBytes_validate_ok_load_sol", func(t *testing.T) {
		law := "L_par_dom_BatchHeaderBytes_validate_ok_load_sol"
		r := holonParLoad(t, law)
		b := BatchHeaderBytes(holonParBytes(t, r, "b"))
		err := b.validate()
		holonParReport(t, law, (err == nil) == holonParBool(t, r, "lhs"),
			fmt.Sprintf("len=%d; validate()=%v", len(b), err))
	})
}
