// HOLON I21 (audit round M2/2, auditor A2) hostile-input harness, Go side, package morph-l2/common/batch
// (surfaces go_header, go_encoders and batchdata_act).
//
// holon/audit/hostile.py copies this file into a scratch copy of the pinned checkout's common/batch and runs
//   (cd common && HOLON_HOSTILE_IN=… HOLON_HOSTILE_OUT=… go test ./batch -run '^TestHolonHostileBatch$' -count=1)
// It calls the real code through its exported names (reflect) and writes what the code did; it compares nothing.
// validate is unexported: it is called here (an in-package harness, as I16's) for the frozen ok_go comparison only.
//
// Input ($HOLON_HOSTILE_IN), JSON:
//   {"headers": ["0x..", ..],                 the header corpus (surface go_header)
//    "methods": ["BatchIndex", ..],           exported BatchHeaderBytes methods, called by name
//    "encoders": [{"type": "BatchHeaderV0" | "BatchHeaderV1", "fields": {Go field: "0x.."},
//                  "encoded": "0x.." | null}] the encoder's struct, its EncodedBytes cache (surface go_encoders)
//    "sequences": {"append": [[arg, ..], ..], "depth": n, "methods": ["Append", ..], "call": {method: [arg, ..]}}}
// An argument is converted to the method's parameter type: "0x.." to []byte, a number to int, a list of "0x.." to a
// slice of 32-byte hashes. Every sequence of at most depth Append calls over the "append" argument lists (shortest
// first, then lexicographic in their order) runs from NewBatchData; after it each method is called once, on a fresh
// rebuild of the same sequence, with its "call" arguments. Each method is also called on a nil *BatchData.
//
// Output ($HOLON_HOSTILE_OUT), one JSON array per line:
//   ["H", i, method, token]            header i, exported method
//   ["V", i, token]                    header i, validate()
//   ["E", i, "0x.." | token]           encoder input i: Bytes(), or a panic token
//   ["F", [field name, ..], [field, ..]]  the receiver type's fields, and NewBatchData's values of them
//   ["B", k, [[field, ..], ..], [viewLen, viewCap, viewSha256], [token, ..]]
//                                      sequence k: the receiver's fields after each Append, TxsPayloadV2's result,
//                                      each method's token (in the order of "methods")
//   ["N", method, token]               the method on a nil *BatchData
//   ["DONE", nHeaders, nEncoders, nSequences]
// A receiver field is written by reflection, in declaration order: a slice as [len, cap], an integer as its value, a
// pointer as "nil" or "ptr". Tokens: "o" or "o:0x<value>" (returned, no error; a single result as big-endian bytes), "e:<message>"
// (a non-nil error), "p:<file>:<line>:<kind>:<message>" (a panic: the first frame outside the Go runtime, reflect and
// this harness; kind index | slice | nil | assert | div | panic).
package batch

import (
	"bufio"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"runtime"
	"strings"
	"testing"

	"github.com/morph-l2/go-ethereum/common"
)

type holonHostileIn struct {
	Headers  []string              `json:"headers"`
	Methods  []string              `json:"methods"`
	Encoders []holonHostileEncoder `json:"encoders"`
	Data     holonHostileBatchData `json:"sequences"`
}

type holonHostileEncoder struct {
	Type    string            `json:"type"`
	Fields  map[string]string `json:"fields"`
	Encoded *string           `json:"encoded"`
}

type holonHostileBatchData struct {
	Append  [][]interface{}            `json:"append"`
	Depth   int                        `json:"depth"`
	Methods []string                   `json:"methods"`
	Call    map[string][]interface{}   `json:"call"`
}

func holonUnhex(t *testing.T, s string) []byte {
	if !strings.HasPrefix(s, "0x") {
		t.Fatalf("holon hostile: not a 0x string: %q", s)
	}
	b, err := hex.DecodeString(s[2:])
	if err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	return b
}

func holonHex(b []byte) string { return "0x" + hex.EncodeToString(b) }

// holonPanicToken names a recovered panic by the first frame outside the runtime, reflect and this harness.
func holonPanicToken(r interface{}) string {
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
		if !(strings.HasPrefix(fn, "runtime.") || strings.HasPrefix(fn, "reflect.") ||
			strings.Contains(fn, ".holon") || strings.Contains(fn, ".TestHolon") || strings.HasSuffix(f.File, "_test.go")) {
			file, line = f.File, f.Line
			break
		}
		if !more {
			break
		}
	}
	msg = strings.ReplaceAll(msg, "\n", " ")
	return fmt.Sprintf("p:%s:%d:%s:%s", file, line, kind, msg)
}

// holonValue renders a returned value as big-endian bytes.
func holonValue(v reflect.Value) string {
	switch v.Kind() {
	case reflect.Uint8:
		return holonHex([]byte{byte(v.Uint())})
	case reflect.Uint16:
		b := make([]byte, 2)
		binary.BigEndian.PutUint16(b, uint16(v.Uint()))
		return holonHex(b)
	case reflect.Uint32:
		b := make([]byte, 4)
		binary.BigEndian.PutUint32(b, uint32(v.Uint()))
		return holonHex(b)
	case reflect.Uint64, reflect.Uint:
		b := make([]byte, 8)
		binary.BigEndian.PutUint64(b, v.Uint())
		return holonHex(b)
	case reflect.Bool:
		if v.Bool() {
			return "0x01"
		}
		return "0x00"
	case reflect.Slice:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			return holonHex(v.Bytes())
		}
	case reflect.Array:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			b := make([]byte, v.Len())
			for i := 0; i < v.Len(); i++ {
				b[i] = byte(v.Index(i).Uint())
			}
			return holonHex(b)
		}
	}
	return fmt.Sprintf("?%s", v.Type())
}

var holonErrorType = reflect.TypeOf((*error)(nil)).Elem()

// holonCall calls method m of recv with args and returns its token.
func holonCall(recv reflect.Value, m string, args []reflect.Value) (tok string) {
	defer func() {
		if r := recover(); r != nil {
			tok = holonPanicToken(r)
		}
	}()
	meth := recv.MethodByName(m)
	if !meth.IsValid() {
		return "x:no such method"
	}
	out := meth.Call(args)
	var vals []string
	for _, o := range out {
		if o.Type() == holonErrorType {
			if !o.IsNil() {
				return "e:" + strings.ReplaceAll(o.Interface().(error).Error(), "\n", " ")
			}
			continue
		}
		vals = append(vals, holonValue(o))
	}
	if len(vals) == 1 {
		return "o:" + vals[0]
	}
	return "o"
}

// holonArg converts a JSON argument to the parameter type ty.
func holonArg(t *testing.T, ty reflect.Type, a interface{}) reflect.Value {
	switch {
	case ty.Kind() == reflect.Slice && ty.Elem().Kind() == reflect.Uint8:
		return reflect.ValueOf(holonUnhex(t, a.(string))).Convert(ty)
	case ty.Kind() == reflect.Int:
		return reflect.ValueOf(int(a.(float64)))
	case ty.Kind() == reflect.Slice && ty.Elem().Kind() == reflect.Array && ty.Elem().Len() == 32:
		out := reflect.MakeSlice(ty, 0, 0)
		for _, x := range a.([]interface{}) {
			h := reflect.New(ty.Elem()).Elem()
			b := holonUnhex(t, x.(string))
			if len(b) != 32 {
				t.Fatalf("holon hostile: hash of %d bytes", len(b))
			}
			reflect.Copy(h, reflect.ValueOf(b))
			out = reflect.Append(out, h)
		}
		return out
	}
	t.Fatalf("holon hostile: no conversion to %s", ty)
	return reflect.Value{}
}

func holonArgs(t *testing.T, meth reflect.Value, args []interface{}) []reflect.Value {
	mt := meth.Type()
	if mt.NumIn() != len(args) {
		t.Fatalf("holon hostile: %d arguments for %d parameters", len(args), mt.NumIn())
	}
	out := make([]reflect.Value, len(args))
	for i, a := range args {
		out[i] = holonArg(t, mt.In(i), a)
	}
	return out
}

func holonHash32(t *testing.T, s string) common.Hash {
	b := holonUnhex(t, s)
	if len(b) != 32 {
		t.Fatalf("holon hostile: hash of %d bytes", len(b))
	}
	return common.BytesToHash(b)
}

func holonU64(t *testing.T, s string) uint64 {
	b := holonUnhex(t, s)
	if len(b) != 8 {
		t.Fatalf("holon hostile: uint64 of %d bytes", len(b))
	}
	return binary.BigEndian.Uint64(b)
}

func holonV0(t *testing.T, f map[string]string) BatchHeaderV0 {
	return BatchHeaderV0{
		BatchIndex:             holonU64(t, f["BatchIndex"]),
		L1MessagePopped:        holonU64(t, f["L1MessagePopped"]),
		TotalL1MessagePopped:   holonU64(t, f["TotalL1MessagePopped"]),
		DataHash:               holonHash32(t, f["DataHash"]),
		BlobVersionedHash:      holonHash32(t, f["BlobVersionedHash"]),
		PrevStateRoot:          holonHash32(t, f["PrevStateRoot"]),
		PostStateRoot:          holonHash32(t, f["PostStateRoot"]),
		WithdrawalRoot:         holonHash32(t, f["WithdrawalRoot"]),
		SequencerSetVerifyHash: holonHash32(t, f["SequencerSetVerifyHash"]),
		ParentBatchHash:        holonHash32(t, f["ParentBatchHash"]),
	}
}

func holonEncode(t *testing.T, e holonHostileEncoder) (out string) {
	defer func() {
		if r := recover(); r != nil {
			out = holonPanicToken(r)
		}
	}()
	v0 := holonV0(t, e.Fields)
	var enc []byte
	if e.Encoded != nil {
		enc = holonUnhex(t, *e.Encoded)
	}
	switch e.Type {
	case "BatchHeaderV0":
		v0.EncodedBytes = enc
		return holonHex(v0.Bytes())
	case "BatchHeaderV1":
		v1 := BatchHeaderV1{BatchHeaderV0: v0, LastBlockNumber: holonU64(t, e.Fields["LastBlockNumber"]), EncodedBytes: enc}
		return holonHex(v1.Bytes())
	}
	t.Fatalf("holon hostile: unknown encoder %q", e.Type)
	return ""
}

// holonFieldNames: the receiver type's field names, in declaration order.
func holonFieldNames() []string {
	t := reflect.TypeOf(BatchData{})
	out := make([]string, t.NumField())
	for i := range out {
		out[i] = t.Field(i).Name
	}
	return out
}

// holonFields: the receiver's fields by reflection, in declaration order: a slice as [len, cap], an integer as its
// value, a pointer as "nil" or "ptr".
func holonFields(cks *BatchData) []interface{} {
	v := reflect.ValueOf(cks).Elem()
	out := make([]interface{}, v.NumField())
	for i := 0; i < v.NumField(); i++ {
		f := v.Field(i)
		switch f.Kind() {
		case reflect.Slice:
			out[i] = []int{f.Len(), f.Cap()}
		case reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uint:
			out[i] = f.Uint()
		case reflect.Int, reflect.Int64, reflect.Int32:
			out[i] = f.Int()
		case reflect.Ptr:
			if f.IsNil() {
				out[i] = "nil"
			} else {
				out[i] = "ptr"
			}
		default:
			out[i] = "?"
		}
	}
	return out
}

func holonView(cks *BatchData) (res []interface{}) {
	defer func() {
		if r := recover(); r != nil {
			res = []interface{}{holonPanicToken(r)}
		}
	}()
	v := cks.TxsPayloadV2()
	sum := sha256.Sum256(v)
	return []interface{}{len(v), cap(v), hex.EncodeToString(sum[:])}
}

func TestHolonHostileBatch(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_HOSTILE_IN"))
	if err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	var in holonHostileIn
	if err := json.Unmarshal(raw, &in); err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	f, err := os.Create(os.Getenv("HOLON_HOSTILE_OUT"))
	if err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	w := bufio.NewWriterSize(f, 1<<20)
	line := func(v ...interface{}) {
		b, err := json.Marshal(v)
		if err != nil {
			t.Fatalf("holon hostile: %v", err)
		}
		w.Write(b)
		w.WriteByte('\n')
	}
	// go_header: every exported method by name, and validate for the ok_go comparison
	for i, h := range in.Headers {
		b := BatchHeaderBytes(holonUnhex(t, h))
		recv := reflect.ValueOf(b)
		for _, m := range in.Methods {
			line("H", i, m, holonCall(recv, m, nil))
		}
		vt := func() (tok string) {
			defer func() {
				if r := recover(); r != nil {
					tok = holonPanicToken(r)
				}
			}()
			if err := b.validate(); err != nil {
				return "e:" + err.Error()
			}
			return "o"
		}()
		line("V", i, vt)
	}
	// go_encoders
	for i, e := range in.Encoders {
		line("E", i, holonEncode(t, e))
	}
	// batchdata_act
	bd := in.Data
	probe := NewBatchData()
	appendM := reflect.ValueOf(probe).MethodByName("Append")
	appends := make([][]reflect.Value, len(bd.Append))
	for i, a := range bd.Append {
		appends[i] = holonArgs(t, appendM, a)
	}
	calls := map[string][]reflect.Value{}
	for _, m := range bd.Methods {
		meth := reflect.ValueOf(probe).MethodByName(m)
		if !meth.IsValid() {
			t.Fatalf("holon hostile: no method %s", m)
		}
		calls[m] = holonArgs(t, meth, bd.Call[m])
	}
	build := func(seq []int) *BatchData {
		cks := NewBatchData()
		for _, k := range seq {
			reflect.ValueOf(cks).MethodByName("Append").Call(appends[k])
		}
		return cks
	}
	line("F", holonFieldNames(), holonFields(NewBatchData()))
	nseq := 0
	var seq []int
	emit := func() {
		cks := NewBatchData()
		after := []interface{}{}
		for _, k := range seq {
			reflect.ValueOf(cks).MethodByName("Append").Call(appends[k])
			after = append(after, holonFields(cks))
		}
		view := holonView(build(seq))
		toks := make([]string, len(bd.Methods))
		for i, m := range bd.Methods {
			tok := holonCall(reflect.ValueOf(build(seq)), m, calls[m])
			if strings.HasPrefix(tok, "o:") {
				tok = "o"
			}
			toks[i] = tok
		}
		line("B", nseq, after, view, toks)
		nseq++
	}
	var walk func(d int)
	walk = func(d int) {
		if len(seq) == d {
			emit()
			return
		}
		for k := range appends {
			seq = append(seq, k)
			walk(d)
			seq = seq[:len(seq)-1]
		}
	}
	for d := 0; d <= bd.Depth; d++ {
		walk(d)
	}
	var nilData *BatchData
	for _, m := range bd.Methods {
		tok := holonCall(reflect.ValueOf(nilData), m, calls[m])
		if strings.HasPrefix(tok, "o:") {
			tok = "o"
		}
		line("N", m, tok)
	}
	line("DONE", len(in.Headers), len(in.Encoders), nseq)
	if err := w.Flush(); err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	f.Close()
}
