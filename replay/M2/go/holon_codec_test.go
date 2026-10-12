// HOLON I16 refinement harness, Go side (holon/refinement.py; binding replay/M2/implementations.json).
//
// holon refine copies this file into a scratch copy of morph common/batch at the facts' commit and runs
//   (cd common && HOLON_CODEC_IN=… HOLON_CODEC_OUT=… go test ./batch -run '^TestHolonCodec$' -count=1 -v)
// It calls the real code on every input and writes what the real code returns; it compares nothing.
//
// Input ($HOLON_CODEC_IN): [{"edge": e, "op": op, "getters": [Go method, ..], "headers": [{Go field: "0x.."}],
// "bytes": ["0x.."]}]. Ops:
//   BatchHeaderV0.Bytes  BatchHeaderV0{..}.Bytes() on each header (Go struct fields named as in Go)
//   BatchHeaderV1.Bytes  BatchHeaderV1{BatchHeaderV0: .., LastBlockNumber: ..}.Bytes()
//   validate             BatchHeaderBytes(b).validate() == nil
//   decode               null when validate() fails, else the listed getters' results as byte strings, in
//                        the listed order; a getter that errors after validate() passed is not available
//                        for that header and is left out (LastBlockNumber on version 0)
// Output ($HOLON_CODEC_OUT): {"outputs": {edge: [value, ..]}} in input order; byte strings are "0x" + hex.
package batch

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

type holonCodecJob struct {
	Edge    string              `json:"edge"`
	Op      string              `json:"op"`
	Getters []string            `json:"getters"`
	Headers []map[string]string `json:"headers"`
	Bytes   []string            `json:"bytes"`
}

func holonCodecUnhex(t *testing.T, s string) []byte {
	if !strings.HasPrefix(s, "0x") {
		t.Fatalf("holon codec: not a 0x string: %q", s)
	}
	b, err := hex.DecodeString(s[2:])
	if err != nil {
		t.Fatalf("holon codec: %v", err)
	}
	return b
}

func holonCodecHex(b []byte) string { return "0x" + hex.EncodeToString(b) }

// holonCodecFields checks that a header names exactly the Go fields an op fills (no silent zero value).
func holonCodecFields(t *testing.T, h map[string]string, want []string) {
	got := make([]string, 0, len(h))
	for k := range h {
		got = append(got, k)
	}
	sort.Strings(got)
	w := append([]string(nil), want...)
	sort.Strings(w)
	if strings.Join(got, ",") != strings.Join(w, ",") {
		t.Fatalf("holon codec: header fields %v, want %v", got, w)
	}
}

func holonCodecU64(t *testing.T, h map[string]string, k string) uint64 {
	b := holonCodecUnhex(t, h[k])
	if len(b) != 8 {
		t.Fatalf("holon codec: %s has %d bytes, want 8", k, len(b))
	}
	return binary.BigEndian.Uint64(b)
}

func holonCodecHash(t *testing.T, h map[string]string, k string) common.Hash {
	b := holonCodecUnhex(t, h[k])
	if len(b) != common.HashLength {
		t.Fatalf("holon codec: %s has %d bytes, want %d", k, len(b), common.HashLength)
	}
	return common.BytesToHash(b)
}

var holonCodecV0Fields = []string{"BatchIndex", "L1MessagePopped", "TotalL1MessagePopped", "DataHash",
	"BlobVersionedHash", "PrevStateRoot", "PostStateRoot", "WithdrawalRoot", "SequencerSetVerifyHash", "ParentBatchHash"}

func holonCodecHeaderV0(t *testing.T, h map[string]string) BatchHeaderV0 {
	return BatchHeaderV0{
		BatchIndex:             holonCodecU64(t, h, "BatchIndex"),
		L1MessagePopped:        holonCodecU64(t, h, "L1MessagePopped"),
		TotalL1MessagePopped:   holonCodecU64(t, h, "TotalL1MessagePopped"),
		DataHash:               holonCodecHash(t, h, "DataHash"),
		BlobVersionedHash:      holonCodecHash(t, h, "BlobVersionedHash"),
		PrevStateRoot:          holonCodecHash(t, h, "PrevStateRoot"),
		PostStateRoot:          holonCodecHash(t, h, "PostStateRoot"),
		WithdrawalRoot:         holonCodecHash(t, h, "WithdrawalRoot"),
		SequencerSetVerifyHash: holonCodecHash(t, h, "SequencerSetVerifyHash"),
		ParentBatchHash:        holonCodecHash(t, h, "ParentBatchHash"),
	}
}

func holonCodecBE64(x uint64) []byte {
	b := make([]byte, 8)
	binary.BigEndian.PutUint64(b, x)
	return b
}

// holonCodecGetter calls one getter of the real decoder by its Go name.
func holonCodecGetter(t *testing.T, b BatchHeaderBytes, name string) ([]byte, error) {
	u := func(x uint64, err error) ([]byte, error) { return holonCodecBE64(x), err }
	h := func(x common.Hash, err error) ([]byte, error) { return x.Bytes(), err }
	switch name {
	case "Version":
		v, err := b.Version()
		return []byte{v}, err
	case "BatchIndex":
		return u(b.BatchIndex())
	case "L1MessagePopped":
		return u(b.L1MessagePopped())
	case "TotalL1MessagePopped":
		return u(b.TotalL1MessagePopped())
	case "DataHash":
		return h(b.DataHash())
	case "BlobCommitHash":
		return h(b.BlobCommitHash())
	case "PrevStateRoot":
		return h(b.PrevStateRoot())
	case "PostStateRoot":
		return h(b.PostStateRoot())
	case "WithdrawalRoot":
		return h(b.WithdrawalRoot())
	case "SequencerSetVerifyHash":
		return h(b.SequencerSetVerifyHash())
	case "ParentBatchHash":
		return h(b.ParentBatchHash())
	case "LastBlockNumber":
		return u(b.LastBlockNumber())
	}
	t.Fatalf("holon codec: no getter %s", name)
	return nil, nil
}

func holonCodecDecode(t *testing.T, b BatchHeaderBytes, getters []string) interface{} {
	if b.validate() != nil {
		return nil
	}
	out := make([]string, 0, len(getters))
	for _, g := range getters {
		v, err := holonCodecGetter(t, b, g)
		if err != nil {
			continue
		}
		out = append(out, holonCodecHex(v))
	}
	return out
}

func TestHolonCodec(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_CODEC_IN"))
	if err != nil {
		t.Fatal(err)
	}
	var jobs []holonCodecJob
	if err := json.Unmarshal(raw, &jobs); err != nil {
		t.Fatal(err)
	}
	outputs := map[string][]interface{}{}
	n := 0
	for _, j := range jobs {
		res := []interface{}{}
		switch j.Op {
		case "BatchHeaderV0.Bytes":
			for _, h := range j.Headers {
				holonCodecFields(t, h, holonCodecV0Fields)
				res = append(res, holonCodecHex(holonCodecHeaderV0(t, h).Bytes()))
			}
		case "BatchHeaderV1.Bytes":
			for _, h := range j.Headers {
				holonCodecFields(t, h, append(append([]string(nil), holonCodecV0Fields...), "LastBlockNumber"))
				v1 := BatchHeaderV1{BatchHeaderV0: holonCodecHeaderV0(t, h), LastBlockNumber: holonCodecU64(t, h, "LastBlockNumber")}
				res = append(res, holonCodecHex(v1.Bytes()))
			}
		case "validate":
			for _, s := range j.Bytes {
				res = append(res, BatchHeaderBytes(holonCodecUnhex(t, s)).validate() == nil)
			}
		case "decode":
			for _, s := range j.Bytes {
				res = append(res, holonCodecDecode(t, BatchHeaderBytes(holonCodecUnhex(t, s)), j.Getters))
			}
		default:
			t.Fatalf("holon codec: unknown op %q for edge %s", j.Op, j.Edge)
		}
		if _, dup := outputs[j.Edge]; dup {
			t.Fatalf("holon codec: edge %s twice", j.Edge)
		}
		outputs[j.Edge] = res
		n += len(res)
	}
	enc, err := json.Marshal(map[string]interface{}{"outputs": outputs})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(os.Getenv("HOLON_CODEC_OUT"), enc, 0o644); err != nil {
		t.Fatal(err)
	}
	fmt.Printf("HOLON codec: %d outputs for %d edges\n", n, len(outputs))
}
