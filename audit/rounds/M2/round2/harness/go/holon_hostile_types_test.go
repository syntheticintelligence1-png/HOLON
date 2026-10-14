// HOLON I21 (audit round M2/2, auditor A2) hostile-input harness, Go side, package morph-l2/node/types.
//
// holon/audit/hostile.py copies this file into a scratch copy of the pinned checkout's node/types and runs
//   (cd node && HOLON_HOSTILE_IN=… HOLON_HOSTILE_OUT=… go test ./types -run '^TestHolonHostileTypes$' -count=1)
// It calls every exported BatchHeaderBytes method of the package by its name (reflect) on every input, and writes
// what the real code returned; it compares nothing.
//
// Input ($HOLON_HOSTILE_IN): {"headers": ["0x..", ..], "methods": ["BatchIndex", ..]} (other keys are ignored).
// Output ($HOLON_HOSTILE_OUT), one JSON array per line: ["H", i, method, token], then ["DONE", nHeaders]. Tokens as in
// holon_hostile_batch_test.go: "o[:0x<value>]", "e:<message>", "p:<file>:<line>:<kind>:<message>".
package types

import (
	"bufio"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"runtime"
	"strings"
	"testing"
)

type holonTypesIn struct {
	Headers []string `json:"headers"`
	Methods []string `json:"methods"`
}

func holonTypesPanic(r interface{}) string {
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
	return fmt.Sprintf("p:%s:%d:%s:%s", file, line, kind, strings.ReplaceAll(msg, "\n", " "))
}

func holonTypesValue(v reflect.Value) string {
	switch v.Kind() {
	case reflect.Uint8:
		return "0x" + hex.EncodeToString([]byte{byte(v.Uint())})
	case reflect.Uint64, reflect.Uint:
		b := make([]byte, 8)
		binary.BigEndian.PutUint64(b, v.Uint())
		return "0x" + hex.EncodeToString(b)
	case reflect.Slice:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			return "0x" + hex.EncodeToString(v.Bytes())
		}
	case reflect.Array:
		if v.Type().Elem().Kind() == reflect.Uint8 {
			b := make([]byte, v.Len())
			for i := 0; i < v.Len(); i++ {
				b[i] = byte(v.Index(i).Uint())
			}
			return "0x" + hex.EncodeToString(b)
		}
	}
	return fmt.Sprintf("?%s", v.Type())
}

var holonTypesErr = reflect.TypeOf((*error)(nil)).Elem()

func holonTypesCall(recv reflect.Value, m string) (tok string) {
	defer func() {
		if r := recover(); r != nil {
			tok = holonTypesPanic(r)
		}
	}()
	meth := recv.MethodByName(m)
	if !meth.IsValid() {
		return "x:no such method"
	}
	var vals []string
	for _, o := range meth.Call(nil) {
		if o.Type() == holonTypesErr {
			if !o.IsNil() {
				return "e:" + strings.ReplaceAll(o.Interface().(error).Error(), "\n", " ")
			}
			continue
		}
		vals = append(vals, holonTypesValue(o))
	}
	if len(vals) == 1 {
		return "o:" + vals[0]
	}
	return "o"
}

func TestHolonHostileTypes(t *testing.T) {
	raw, err := os.ReadFile(os.Getenv("HOLON_HOSTILE_IN"))
	if err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	var in holonTypesIn
	if err := json.Unmarshal(raw, &in); err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	f, err := os.Create(os.Getenv("HOLON_HOSTILE_OUT"))
	if err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	w := bufio.NewWriterSize(f, 1<<20)
	line := func(v ...interface{}) {
		b, _ := json.Marshal(v)
		w.Write(b)
		w.WriteByte('\n')
	}
	for i, h := range in.Headers {
		if !strings.HasPrefix(h, "0x") {
			t.Fatalf("holon hostile: not a 0x string: %q", h)
		}
		raw, err := hex.DecodeString(h[2:])
		if err != nil {
			t.Fatalf("holon hostile: %v", err)
		}
		recv := reflect.ValueOf(BatchHeaderBytes(raw))
		for _, m := range in.Methods {
			line("H", i, m, holonTypesCall(recv, m))
		}
	}
	line("DONE", len(in.Headers))
	if err := w.Flush(); err != nil {
		t.Fatalf("holon hostile: %v", err)
	}
	f.Close()
}
