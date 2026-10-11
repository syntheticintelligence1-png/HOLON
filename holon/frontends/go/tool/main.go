// gossa: dump normalized go/ssa for the HOLON M2 go-ssa frontend (unit S3).
//
// The tool loads Go packages from a checkout (with its go.work workspace),
// builds SSA, and emits a deterministic JSON value-graph per function:
// params, consts, slice/index/field ops, calls (canonicalized callee names),
// stores, terminators (if/jump/switch/return/panic) and block edges.
// Reduction to facts happens on the Python side (holon/frontends/go).
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

// ---------- dump schema (gossa-dump/0.1) ----------

type Dump struct {
	Tool     string   `json:"tool"`
	Version  string   `json:"dump_version"`
	GoVer    string   `json:"go"`
	Packages []string `json:"packages"`
	Funcs    []Func   `json:"functions"`
}

type Func struct {
	ID        string    `json:"id"`
	Pkg       string    `json:"pkg"`
	Name      string    `json:"name"`
	Recv      *Recv     `json:"recv,omitempty"`
	Signature string    `json:"signature"`
	File      string    `json:"file"`
	Line      int       `json:"line"`
	EndLine   int       `json:"end_line"`
	Exported  bool      `json:"exported"`
	Blocks    []Block   `json:"blocks"`
	Instrs    []Instr   `json:"instrs"`
	FreeVars  []string  `json:"free_vars,omitempty"`
	Anonymous bool      `json:"anonymous,omitempty"`
}

type Recv struct {
	Name string `json:"name"`
	Type string `json:"type"`
	Ptr  bool   `json:"ptr"`
}

type Block struct {
	ID      int     `json:"id"`
	Instrs  []int   `json:"instrs"`
	Succs   []Edge  `json:"succs"`
	Comment string  `json:"comment,omitempty"`
	Loop    bool    `json:"loop,omitempty"`
}

type Edge struct {
	To  int    `json:"to"`
	Tag string   `json:"tag"`
}

// Instr is one SSA instruction (or a value-producing one). Fields are
// value ids ("v12"), literals, or resolved names; see op comments below.
type Instr struct {
	ID    int    `json:"id"`
	Block int    `json:"block"`
	Op    string `json:"op"`
	Line  *int   `json:"line,omitempty"`

	// generic fields, used per op
	Name  string   `json:"name,omitempty"`  // param/field/global/builtin name
	Type  string   `json:"type,omitempty"`  // result type (or alloc/cast type)
	Args  []int    `json:"args,omitempty"`  // operand value ids
	Fn    string   `json:"fn,omitempty"`    // canonical callee id (call op)
	Value any      `json:"value,omitempty"` // const literal (const op)
	Index int      `json:"index,omitempty"` // extract index
	Edges [][]int  `json:"edges,omitempty"` // phi: [block, value] pairs
	Kinds []string `json:"kinds,omitempty"` // succ tags already on blocks; unused
	Cond  int      `json:"cond,omitempty"`  // if/switch condition id
	Cases []any    `json:"cases,omitempty"` // switch case consts
	Bind  int      `json:"bind,omitempty"`  // the local the result binds to, when named
}

// ---------- naming helpers ----------

func calleeID(call *ssa.CallCommon) string {
	v := call.Value
	if b, ok := v.(*ssa.Builtin); ok {
		return "builtin." + b.Name()
	}
	if call.IsInvoke() {
		// interface method call; keep the method name and the abstract signature
		return "invoke." + call.Method.Name()
	}
	fn := call.StaticCallee()
	if fn == nil {
		return "dyn." + v.String()
	}
	return fnID(fn)
}

// fnID renders a *ssa.Function canonically:
//   pkgpath.Name              for package funcs
//   pkgpath.(RecvType).Method for methods (recv type without *)
//   builtin.<name>            for builtins (handled by caller)
func fnID(fn *ssa.Function) string {
	pkg := ""
	if fn.Pkg != nil {
		pkg = fn.Pkg.Pkg.Path()
	}
	sig := fn.Signature
	if sig.Recv() != nil {
		rt := sig.Recv().Type()
		ts := rt.String()
		ts = strings.TrimPrefix(ts, "*")
		// keep the fully qualified type string; shorten the leading pkg path
		return fmt.Sprintf("%s.(%s).%s", pkg, ts, fn.Name())
	}
	if pkg != "" {
		return fmt.Sprintf("%s.%s", pkg, fn.Name())
	}
	return fn.Name()
}

// canonicalEndian maps the encoding/binary endianness concrete type to the
// exported package-level variable it is reached through.
func canonicalCallee(id string) string {
	for _, e := range []string{"BigEndian", "LittleEndian"} {
		lower := strings.ToLower(e[:1]) + e[1:]
		prefix := fmt.Sprintf("encoding/binary.(encoding/binary.%s).", lower)
		if strings.HasPrefix(id, prefix) {
			return "binary." + e + "." + strings.TrimPrefix(id, prefix)
		}
	}
	return id
}

// fieldName resolves the field name for Field/FieldAddr on a struct type.
func fieldName(t types.Type, idx int) string {
	if p, ok := t.(*types.Pointer); ok {
		t = p.Elem()
	}
	if n, ok := t.(*types.Named); ok {
		t = n.Underlying()
	}
	if s, ok := t.(*types.Struct); ok && idx < s.NumFields() {
		return s.Field(idx).Name()
	}
	return fmt.Sprintf("#%d", idx)
}

// ---------- main ----------

func main() {
	var dir, out string
	var pats flagList
	flag.StringVar(&dir, "dir", "", "checkout root (with go.work)")
	flag.Var(&pats, "pkg", "package pattern (repeatable)")
	flag.StringVar(&out, "out", "", "output JSON path")
	pretty := flag.Bool("pretty", false, "indent JSON")
	flag.Parse()
	if dir == "" || out == "" || len(pats) == 0 {
		fmt.Fprintln(os.Stderr, "usage: gossa --dir DIR --pkg PATTERN [--pkg ...] --out FILE")
		os.Exit(2)
	}
	abs, err := filepath.Abs(dir)
	if err != nil {
		fail(err)
	}
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedCompiledGoFiles |
			packages.NeedImports | packages.NeedDeps | packages.NeedTypes |
			packages.NeedSyntax | packages.NeedTypesInfo | packages.NeedModule,
		Dir: abs,
	}
	initial, err := packages.Load(cfg, pats...)
	if err != nil {
		fail(err)
	}
	if packages.PrintErrors(initial) > 0 {
		fail(fmt.Errorf("package loading failed"))
	}
	prog, _ := ssautil.Packages(initial, ssa.InstantiateGenerics)
	prog.Build()

	want := map[string]bool{}
	for _, p := range pats {
		want[p] = true
	}
	// also allow go list -style resolution: keep packages whose path matches
	// a pattern exactly (patterns are literal import paths here).
	var funcs []*ssa.Function
	seen := map[*ssa.Function]bool{}
	for f := range ssautil.AllFunctions(prog) {
		if f.Pkg == nil {
			continue
		}
		p := f.Pkg.Pkg.Path()
		if !want[p] {
			continue
		}
		if seen[f] {
			continue
		}
		seen[f] = true
		funcs = append(funcs, f)
	}
	sort.Slice(funcs, func(i, j int) bool { return fnID(funcs[i]) < fnID(funcs[j]) })

	d := Dump{Tool: "holon/frontends/go/tool", Version: "gossa-dump/0.1", GoVer: goVer(), Packages: pats}
	for _, f := range funcs {
		d.Funcs = append(d.Funcs, dumpFunc(prog, f, abs))
	}
	var w *os.File
	if out == "-" {
		w = os.Stdout
	} else {
		if w, err = os.Create(out); err != nil {
			fail(err)
		}
		defer w.Close()
	}
	enc := json.NewEncoder(w)
	if *pretty {
		enc.SetIndent("", "  ")
	}
	if err := enc.Encode(d); err != nil {
		fail(err)
	}
}

type flagList []string

func (f *flagList) String() string { return strings.Join(*f, ",") }
func (f *flagList) Set(s string) error {
	*f = append(*f, s)
	return nil
}

func fail(e error) {
	fmt.Fprintln(os.Stderr, "gossa:", e)
	os.Exit(1)
}
