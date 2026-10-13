// HOLON I21 (audit round M2/2, auditor A2) harness for the header carrier's Go consumer, package
// morph-l2/node/derivation (surface go_consumer).
//
// holon/audit/hostile.py copies this file into a scratch copy of the pinned checkout's node/derivation and runs
//   (cd node && HOLON_HOSTILE_IN=… HOLON_HOSTILE_OUT=… go test ./derivation -run '^TestHolonHostileConsumer$' -count=1)
// The harness builds a Derivation whose four ABIs are loaded exactly as NewDerivationClient loads them
// (derivation.go:108-123) and calls only the two exported entry points: (*Derivation).UnPackData on the calldata,
// then (*BatchInfo).ParseBatch on the unpacked batch with a blob sidecar. It compares nothing.
//
// Input ($HOLON_HOSTILE_IN), JSON:
//   {"selectors": ["0x4a8d544f", ..],          hostile: for each selector, the commitBatch of the ABI that has it
//    "headers": ["0x..", ..],                  with each header as parentBatchHeader and every other argument
//                                              well-formed (packed with that ABI); parsed with one zero blob
//    "snapshot": "<dir>",                      the I59 snapshot (objects/<aa>/<sha256>[.gz])
//    "real": [{"key": n, "tx": "<sha256>", "blobs": ["<sha256>", ..]}]}
// A real commit's calldata is the "input" of its transaction object, and its sidecar holds its blobs in order. Every
// object is read from the snapshot and its sha256 checked against the name the index gives it; a missing object or
// a hash mismatch fails the run.
// Output ($HOLON_HOSTILE_OUT), one JSON array per line:
//   ["h", selector index, header index, unpack token, parent keccak256 | null, parse token, parent header | null]
//   ["r", key, selector, unpack token, parent keccak256 | null, parse token, parent header | null]
//   ["DONE", nHostile, nReal]
// Tokens: "o" (a nil error), "e:<message>", "p:<file>:<line>:<kind>:<message>" (a recovered panic: the first frame
// outside the runtime and this harness). A hostile line carries the unpacked parent header only when ParseBatch
// returned an error that names a header step (its message starts "decode batch header"); a real line always does.
package derivation

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/accounts/abi"
	eth "github.com/morph-l2/go-ethereum/core/types"
	"github.com/morph-l2/go-ethereum/crypto"
	"github.com/morph-l2/go-ethereum/crypto/kzg4844"
	geth "github.com/morph-l2/go-ethereum/eth"

	"morph-l2/bindings/bindings"
	"morph-l2/node/types"
)

type holonConsumerReal struct {
	Key   int      `json:"key"`
	Tx    string   `json:"tx"`
	Blobs []string `json:"blobs"`
}

type holonConsumerIn struct {
	Selectors []string            `json:"selectors"`
	Headers   []string            `json:"headers"`
	Snapshot  string              `json:"snapshot"`
	Real      []holonConsumerReal `json:"real"`
}

func holonConsumerPanic(r interface{}) string {
	msg := fmt.Sprint(r)
	kind := "panic"
	switch {
	case strings.Contains(msg, "index out of range"):
		kind = "index"
	case strings.Contains(msg, "slice bounds out of range"):
		kind = "slice"
	case strings.Contains(msg, "nil pointer dereference"):
		kind = "nil"
	case strings.Contains(msg, "interface conversion"):
		kind = "assert"
	case strings.Contains(msg, "divide by zero"):
		kind = "div"
	}
	pcs := make([]uintptr, 64)
	n := runtime.Callers(1, pcs)
	frames := runtime.CallersFrames(pcs[:n])
	file, line := "?", 0
	for {
		f, more := frames.Next()
		fn := f.Function
		if !(strings.HasPrefix(fn, "runtime.") || strings.HasPrefix(fn, "reflect.") || strings.Contains(fn, ".holon") ||
			strings.Contains(fn, ".TestHolon") || strings.HasSuffix(f.File, "_test.go")) {
			file, line = f.File, f.Line
			break
		}
		if !more {
			break
		}
	}
	return fmt.Sprintf("p:%s:%d:%s:%s", file, line, kind, strings.ReplaceAll(msg, "\n", " "))
}

// holonDerivation: the four ABIs exactly as NewDerivationClient loads them (derivation.go:108-123).
func holonDerivation(t *testing.T) *Derivation {
	rollupAbi, err := bindings.RollupMetaData.GetAbi()
	if err != nil {
		t.Fatal(err)
	}
	preSubmitterRollupAbi, err := types.PreSubmitterRollupMetaData.GetAbi()
	if err != nil {
		t.Fatal(err)
	}
	legacyRollupAbi, err := types.LegacyRollupMetaData.GetAbi()
	if err != nil {
		t.Fatal(err)
	}
	beforeMoveBlockCtxAbi, err := types.BeforeMoveBlockCtxABI.GetAbi()
	if err != nil {
		t.Fatal(err)
	}
	return &Derivation{
		rollupABI:             rollupAbi,
		preSubmitterRollupABI: preSubmitterRollupAbi,
		legacyRollupABI:       legacyRollupAbi,
		beforeMoveBlockCtxABI: beforeMoveBlockCtxAbi,
	}
}

// holonFill gives every field a well-formed value: parentBatchHeader the hostile header, uints 1, byte strings one
// byte, fixed byte arrays 0x11.., big integers 1.
func holonFill(v reflect.Value, header []byte, name string) {
	switch v.Kind() {
	case reflect.Struct:
		for i := 0; i < v.NumField(); i++ {
			holonFill(v.Field(i), header, v.Type().Field(i).Name)
		}
	case reflect.Ptr:
		if v.Type() == reflect.TypeOf((*big.Int)(nil)) {
			v.Set(reflect.ValueOf(big.NewInt(1)))
		}
	case reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		v.SetUint(1)
	case reflect.Slice:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			if name == "ParentBatchHeader" {
				v.SetBytes(append([]byte{}, header...))
			} else {
				v.SetBytes([]byte{0xab})
			}
		}
	case reflect.Array:
		for i := 0; i < v.Len(); i++ {
			if v.Index(i).Kind() == reflect.Uint8 {
				v.Index(i).SetUint(0x11)
			}
		}
	}
}

// holonCommitCalldata packs a commitBatch of the ABI whose commitBatch has the selector, with the header as
// parentBatchHeader.
func holonCommitCalldata(t *testing.T, d *Derivation, sel []byte, header []byte) []byte {
	for _, a := range []*abi.ABI{d.beforeMoveBlockCtxABI, d.legacyRollupABI, d.preSubmitterRollupABI, d.rollupABI} {
		m, ok := a.Methods["commitBatch"]
		if !ok || !bytes.Equal(m.ID, sel) {
			continue
		}
		var args []interface{}
		for _, in := range m.Inputs {
			v := reflect.New(in.Type.GetType()).Elem()
			holonFill(v, header, "")
			args = append(args, v.Interface())
		}
		packed, err := m.Inputs.Pack(args...)
		if err != nil {
			t.Fatalf("holon consumer: pack %x: %v", sel, err)
		}
		return append(append([]byte{}, m.ID...), packed...)
	}
	t.Fatalf("holon consumer: no commitBatch with selector %x", sel)
	return nil
}

func holonErrToken(err error) string {
	if err == nil {
		return "o"
	}
	return "e:" + strings.ReplaceAll(err.Error(), "\n", " ")
}

func holonUnpack(d *Derivation, data []byte) (batch geth.RPCRollupBatch, tok string) {
	defer func() {
		if r := recover(); r != nil {
			tok = holonConsumerPanic(r)
		}
	}()
	b, err := d.UnPackData(data)
	return b, holonErrToken(err)
}

func holonParse(batch geth.RPCRollupBatch) (tok string) {
	defer func() {
		if r := recover(); r != nil {
			tok = holonConsumerPanic(r)
		}
	}()
	bi := new(BatchInfo)
	return holonErrToken(bi.ParseBatch(batch))
}

func holonObject(t *testing.T, dir, sha string) []byte {
	if len(sha) != 64 {
		t.Fatalf("holon consumer: bad object name %q", sha)
	}
	base := filepath.Join(dir, "objects", sha[:2], sha)
	raw, err := os.ReadFile(base)
	if err != nil {
		gz, err2 := os.ReadFile(base + ".gz")
		if err2 != nil {
			t.Fatalf("holon consumer: object %s is not in the snapshot %s", sha, dir)
		}
		zr, err := gzip.NewReader(bytes.NewReader(gz))
		if err != nil {
			t.Fatalf("holon consumer: object %s: %v", sha, err)
		}
		raw, err = io.ReadAll(zr)
		if err != nil {
			t.Fatalf("holon consumer: object %s: %v", sha, err)
		}
	}
	sum := sha256.Sum256(raw)
	if hex.EncodeToString(sum[:]) != sha {
		t.Fatalf("holon consumer: object %s does not hash to its name", sha)
	}
	return raw
}

func holonCalldata(t *testing.T, raw []byte) []byte {
	var tx struct {
		Input string `json:"input"`
	}
	if err := json.Unmarshal(raw, &tx); err != nil {
		t.Fatalf("holon consumer: transaction object: %v", err)
	}
	if !strings.HasPrefix(tx.Input, "0x") {
		t.Fatalf("holon consumer: a transaction input without 0x")
	}
	b, err := hex.DecodeString(tx.Input[2:])
	if err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	return b
}

func holonUnhexC(t *testing.T, s string) []byte {
	if !strings.HasPrefix(s, "0x") {
		t.Fatalf("holon consumer: not a 0x string")
	}
	b, err := hex.DecodeString(s[2:])
	if err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	return b
}

func TestHolonHostileConsumer(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_HOSTILE_IN"))
	if err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	var in holonConsumerIn
	if err := json.Unmarshal(raw, &in); err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	f, err := os.Create(os.Getenv("HOLON_HOSTILE_OUT"))
	if err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	w := bufio.NewWriterSize(f, 1<<20)
	line := func(v ...interface{}) {
		b, _ := json.Marshal(v)
		w.Write(b)
		w.WriteByte('\n')
	}
	d := holonDerivation(t)
	one := func(data []byte, sidecar eth.BlobTxSidecar, always bool) []interface{} {
		batch, ut := holonUnpack(d, data)
		if ut != "o" {
			return []interface{}{ut, nil, nil, nil}
		}
		parent := "0x" + hex.EncodeToString(crypto.Keccak256(batch.ParentBatchHeader))
		batch.Sidecar = sidecar
		pt := holonParse(batch)
		var hdr interface{}
		if always || strings.HasPrefix(pt, "e:decode batch header") {
			hdr = "0x" + hex.EncodeToString(batch.ParentBatchHeader)
		}
		return []interface{}{ut, parent, pt, hdr}
	}
	zero := eth.BlobTxSidecar{Blobs: []kzg4844.Blob{{}}}
	nh := 0
	for si, s := range in.Selectors {
		sel := holonUnhexC(t, s)
		for hi, h := range in.Headers {
			r := one(holonCommitCalldata(t, d, sel, holonUnhexC(t, h)), zero, false)
			line(append([]interface{}{"h", si, hi}, r...)...)
			nh++
		}
	}
	for _, c := range in.Real {
		data := holonCalldata(t, holonObject(t, in.Snapshot, c.Tx))
		sc := eth.BlobTxSidecar{}
		for _, s := range c.Blobs {
			b := holonObject(t, in.Snapshot, s)
			var blob kzg4844.Blob
			if len(b) != len(blob) {
				t.Fatalf("holon consumer: blob %s has %d bytes", s, len(b))
			}
			copy(blob[:], b)
			sc.Blobs = append(sc.Blobs, blob)
		}
		sel := ""
		if len(data) >= 4 {
			sel = "0x" + hex.EncodeToString(data[:4])
		}
		r := one(data, sc, true)
		line(append([]interface{}{"r", c.Key, sel}, r...)...)
	}
	line("DONE", nh, len(in.Real))
	if err := w.Flush(); err != nil {
		t.Fatalf("holon consumer: %v", err)
	}
	f.Close()
}
