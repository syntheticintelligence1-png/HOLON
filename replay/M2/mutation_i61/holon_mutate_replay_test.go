// HOLON I61 replay harness, Go side (holon/mutate/replay.py; instrument replay.m0; binding replay/M2/implementations.json).
//
// holon.mutate.replay copies this file into a scratch copy of a source tree's common/batch, builds the package's test
// binary once per tree in the tree's own workspace (its go.work, offline):
//   (cd common && go test -c -trimpath -o <bin> ./batch)
// and starts it once:
//   (cd common/batch && <bin> -test.run '^TestHolonMutateReplay$' -test.count=1 -test.timeout=0)
// The package's own _test.go files are left out of the scratch copy: they import modules the offline module cache does
// not hold, and the harness needs none of them.
//
// It makes I16's harness's calls (replay/M2/go/holon_codec_test.go: the same ops, the same Go fields and getters, the same
// value encodings) with a recover around each call; I16's harness does not recover, so one panic there fails every Go
// edge. It calls the real code on every input and writes what the real code returns; it compares nothing.
//
// Requests, one JSON object per line on stdin:
//   {"id": n, "op": op, "getters": [Go method, ..], "headers": [{Go field: "0x.."}], "bytes": ["0x.."]}
// Ops (I16's):
//   BatchHeaderV0.Bytes  BatchHeaderV0{..}.Bytes() on each header, with an empty EncodedBytes cache
//   BatchHeaderV1.Bytes  BatchHeaderV1{BatchHeaderV0: .., LastBlockNumber: ..}.Bytes(), empty caches
//   validate             BatchHeaderBytes(b).validate() == nil
//   decode               null when validate() fails, else the listed getters' results as byte strings, in the listed
//                        order; a getter that errors after validate() passed is left out
// Responses, one line on stdout per request: "HOLON-I61 " + {"id": n, "results": [{"kind": "value" | "panic",
// "value": v, "detail": s}], "error": s}, results in input order. A panic in a call is that call's result (kind
// "panic", detail the recovered value); an input that does not parse is an error of the request.
package batch

import (
	"bufio"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

type holonI61Request struct {
	ID      int                 `json:"id"`
	Op      string              `json:"op"`
	Getters []string            `json:"getters"`
	Headers []map[string]string `json:"headers"`
	Bytes   []string            `json:"bytes"`
}

type holonI61Result struct {
	Kind   string      `json:"kind"`
	Value  interface{} `json:"value"`
	Detail string      `json:"detail"`
}

type holonI61Response struct {
	ID      int              `json:"id"`
	Results []holonI61Result `json:"results"`
	Error   string           `json:"error"`
}

func holonI61Unhex(s string) ([]byte, error) {
	if !strings.HasPrefix(s, "0x") {
		return nil, fmt.Errorf("not a 0x string: %q", s)
	}
	return hex.DecodeString(s[2:])
}

func holonI61Hex(b []byte) string { return "0x" + hex.EncodeToString(b) }

// holonI61Fields checks that a header names exactly the Go fields an op fills (no silent zero value), as I16's does.
func holonI61Fields(h map[string]string, want []string) error {
	got := make([]string, 0, len(h))
	for k := range h {
		got = append(got, k)
	}
	sort.Strings(got)
	w := append([]string(nil), want...)
	sort.Strings(w)
	if strings.Join(got, ",") != strings.Join(w, ",") {
		return fmt.Errorf("header fields %v, want %v", got, w)
	}
	return nil
}

func holonI61U64(h map[string]string, k string) (uint64, error) {
	b, err := holonI61Unhex(h[k])
	if err != nil {
		return 0, fmt.Errorf("%s: %v", k, err)
	}
	if len(b) != 8 {
		return 0, fmt.Errorf("%s has %d bytes, want 8", k, len(b))
	}
	return binary.BigEndian.Uint64(b), nil
}

func holonI61Hash(h map[string]string, k string) (common.Hash, error) {
	b, err := holonI61Unhex(h[k])
	if err != nil {
		return common.Hash{}, fmt.Errorf("%s: %v", k, err)
	}
	if len(b) != common.HashLength {
		return common.Hash{}, fmt.Errorf("%s has %d bytes, want %d", k, len(b), common.HashLength)
	}
	return common.BytesToHash(b), nil
}

var holonI61V0Fields = []string{"BatchIndex", "L1MessagePopped", "TotalL1MessagePopped", "DataHash",
	"BlobVersionedHash", "PrevStateRoot", "PostStateRoot", "WithdrawalRoot", "SequencerSetVerifyHash", "ParentBatchHash"}

func holonI61HeaderV0(h map[string]string) (BatchHeaderV0, error) {
	var v BatchHeaderV0
	var err error
	u64 := func(dst *uint64, k string) {
		if err == nil {
			*dst, err = holonI61U64(h, k)
		}
	}
	hash := func(dst *common.Hash, k string) {
		if err == nil {
			*dst, err = holonI61Hash(h, k)
		}
	}
	u64(&v.BatchIndex, "BatchIndex")
	u64(&v.L1MessagePopped, "L1MessagePopped")
	u64(&v.TotalL1MessagePopped, "TotalL1MessagePopped")
	hash(&v.DataHash, "DataHash")
	hash(&v.BlobVersionedHash, "BlobVersionedHash")
	hash(&v.PrevStateRoot, "PrevStateRoot")
	hash(&v.PostStateRoot, "PostStateRoot")
	hash(&v.WithdrawalRoot, "WithdrawalRoot")
	hash(&v.SequencerSetVerifyHash, "SequencerSetVerifyHash")
	hash(&v.ParentBatchHash, "ParentBatchHash")
	return v, err
}

func holonI61BE64(x uint64) []byte {
	b := make([]byte, 8)
	binary.BigEndian.PutUint64(b, x)
	return b
}

// holonI61Getter calls one getter of the real decoder by its Go name (I16's holonCodecGetter).
func holonI61Getter(b BatchHeaderBytes, name string) ([]byte, error) {
	u := func(x uint64, err error) ([]byte, error) { return holonI61BE64(x), err }
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
	panic(fmt.Sprintf("holon I61: no getter %s", name)) // checked before any call (holonI61Serve)
}

var holonI61Getters = map[string]bool{"Version": true, "BatchIndex": true, "L1MessagePopped": true,
	"TotalL1MessagePopped": true, "DataHash": true, "BlobCommitHash": true, "PrevStateRoot": true,
	"PostStateRoot": true, "WithdrawalRoot": true, "SequencerSetVerifyHash": true, "ParentBatchHash": true,
	"LastBlockNumber": true}

func holonI61Decode(b BatchHeaderBytes, getters []string) interface{} {
	if b.validate() != nil {
		return nil
	}
	out := make([]string, 0, len(getters))
	for _, g := range getters {
		v, err := holonI61Getter(b, g)
		if err != nil {
			continue
		}
		out = append(out, holonI61Hex(v))
	}
	return out
}

// holonI61Call runs one call of the real code under its own recover: a panic is that call's result.
func holonI61Call(f func() interface{}) (r holonI61Result) {
	defer func() {
		if p := recover(); p != nil {
			r = holonI61Result{Kind: "panic", Value: nil, Detail: fmt.Sprint(p)}
		}
	}()
	return holonI61Result{Kind: "value", Value: f(), Detail: ""}
}

func holonI61Serve(line string) (resp holonI61Response) {
	var req holonI61Request
	if err := json.Unmarshal([]byte(line), &req); err != nil {
		return holonI61Response{ID: -1, Error: fmt.Sprintf("request does not parse: %v", err)}
	}
	resp = holonI61Response{ID: req.ID, Results: []holonI61Result{}}
	fail := func(err error) holonI61Response {
		return holonI61Response{ID: req.ID, Results: []holonI61Result{}, Error: err.Error()}
	}
	switch req.Op {
	case "BatchHeaderV0.Bytes":
		hs := make([]BatchHeaderV0, 0, len(req.Headers))
		for _, h := range req.Headers {
			if err := holonI61Fields(h, holonI61V0Fields); err != nil {
				return fail(err)
			}
			v, err := holonI61HeaderV0(h)
			if err != nil {
				return fail(err)
			}
			hs = append(hs, v)
		}
		for _, v := range hs {
			v := v
			resp.Results = append(resp.Results, holonI61Call(func() interface{} { return holonI61Hex(v.Bytes()) }))
		}
	case "BatchHeaderV1.Bytes":
		hs := make([]BatchHeaderV1, 0, len(req.Headers))
		for _, h := range req.Headers {
			if err := holonI61Fields(h, append(append([]string(nil), holonI61V0Fields...), "LastBlockNumber")); err != nil {
				return fail(err)
			}
			v0, err := holonI61HeaderV0(h)
			if err != nil {
				return fail(err)
			}
			lbn, err := holonI61U64(h, "LastBlockNumber")
			if err != nil {
				return fail(err)
			}
			hs = append(hs, BatchHeaderV1{BatchHeaderV0: v0, LastBlockNumber: lbn})
		}
		for _, v := range hs {
			v := v
			resp.Results = append(resp.Results, holonI61Call(func() interface{} { return holonI61Hex(v.Bytes()) }))
		}
	case "validate", "decode":
		bs := make([][]byte, 0, len(req.Bytes))
		for _, s := range req.Bytes {
			b, err := holonI61Unhex(s)
			if err != nil {
				return fail(err)
			}
			bs = append(bs, b)
		}
		for _, g := range req.Getters {
			if !holonI61Getters[g] {
				return fail(fmt.Errorf("no getter %s", g))
			}
		}
		for _, b := range bs {
			b := BatchHeaderBytes(b)
			if req.Op == "validate" {
				resp.Results = append(resp.Results, holonI61Call(func() interface{} { return b.validate() == nil }))
			} else {
				getters := req.Getters
				resp.Results = append(resp.Results, holonI61Call(func() interface{} { return holonI61Decode(b, getters) }))
			}
		}
	default:
		return fail(fmt.Errorf("unknown op %q", req.Op))
	}
	return resp
}

func TestHolonMutateReplay(t *testing.T) {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)
	for {
		line, err := in.ReadString('\n')
		if strings.TrimSpace(line) != "" {
			enc, merr := json.Marshal(holonI61Serve(line))
			if merr != nil {
				enc, _ = json.Marshal(holonI61Response{ID: -1, Error: merr.Error()})
			}
			out.WriteString("HOLON-I61 ")
			out.Write(enc)
			out.WriteString("\n")
			if ferr := out.Flush(); ferr != nil {
				t.Fatal(ferr)
			}
		}
		if err == io.EOF {
			return
		}
		if err != nil {
			t.Fatal(err)
		}
	}
}
