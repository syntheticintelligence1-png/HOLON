// Command ssadump prints the go/ssa form of a set of Go packages as one deterministic JSON document
// (format "holon-ssadump/0.1"). It is the compiler-side half of the HOLON Go frontend: every analysis
// rule lives in the Python extractor, which reads this document; nothing here names a target.
//
// Usage:
//
//	ssadump -dir DIR PATTERN...
//
// The packages matched by the patterns are loaded with golang.org/x/tools/go/packages from DIR (syntax
// and type information for the matched packages, type information of their dependencies from export
// data), go/ssa is built for the matched packages only, and the document is written to stdout:
//
//   - packages: the matched packages (import path, name, directory and compiled files relative to DIR);
//   - functions: every function of the matched packages (members, methods, closures, initializers and
//     wrappers, with go/ssa's Synthetic description), sorted by go/ssa Function.String(), each with its
//     parameters, free variables, results, blocks (predecessors, successors, immediate dominator) and
//     instructions (operands, type, position, and the fields of the instruction's kind), and the
//     For/Range statements of its own body (closures excluded);
//   - globals: the package-level variables of the matched packages;
//   - types: every type the document mentions, keyed by its go/types string with full package paths.
//
// Positions are "<path>:<line>:<col>" with <path> relative to DIR and "/" separators. The output holds no
// absolute path, no time and no host name; two runs on the same inputs print the same bytes.
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/constant"
	"go/token"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

const version = "holon-ssadump/0.1"

// ---------------------------------------------------------------------------------------------- output

type Doc struct {
	Version   string           `json:"ssadump_version"`
	Packages  []Package        `json:"packages"`
	Globals   []Global         `json:"globals"`
	Functions []Function       `json:"functions"`
	Types     map[string]*Type `json:"types"`
}

type Package struct {
	Path  string   `json:"path"`
	Name  string   `json:"name"`
	Dir   string   `json:"dir"`
	Files []string `json:"files"`
}

type Global struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Package string `json:"package"`
	Type    string `json:"type"`
	Pos     string `json:"pos"`
}

type Var struct {
	Name string `json:"name"`
	Type string `json:"type"`
}

type Loop struct {
	Kind string `json:"kind"`
	Pos  string `json:"pos"`
	End  string `json:"end"`
	Cond bool   `json:"cond"` // a loop condition: every range statement, a for statement with a condition
}

type Function struct {
	ID        string   `json:"id"`
	Name      string   `json:"name"`
	Package   string   `json:"package"`
	Synthetic string   `json:"synthetic"`
	Parent    string   `json:"parent"`
	Method    bool     `json:"method"`
	Pos       string   `json:"pos"`
	Signature string   `json:"signature"`
	Params    []Var    `json:"params"`
	FreeVars  []Var    `json:"freevars"`
	Results   []string `json:"results"`
	Blocks    []Block  `json:"blocks"`
	Recover   int      `json:"recover"`
	Loops     []Loop   `json:"loops"`
}

type Block struct {
	Index   int     `json:"index"`
	Comment string  `json:"comment"`
	Preds   []int   `json:"preds"`
	Succs   []int   `json:"succs"`
	Idom    int     `json:"idom"`
	Instrs  []Instr `json:"instrs"`
}

// Operand is one of: {"v": name} an instruction value of the same function; {"param": i}; {"free": i};
// {"const": {...}}; {"global": id}; {"func": id}; {"builtin": name}. A missing operand is null.
type Operand map[string]interface{}

type Const struct {
	Type  string `json:"type"`
	Kind  string `json:"kind"` // int | float | complex | string | bool | nil | zero | unknown
	Value string `json:"value"`
}

type Call struct {
	Mode     string    `json:"mode"` // static | invoke | dynamic | builtin
	Callee   string    `json:"callee"`
	Method   string    `json:"method"`
	Value    Operand   `json:"value"`
	Args     []Operand `json:"args"`
	Pos      string    `json:"pos"`
	Sig      string    `json:"signature"`
	Variadic bool      `json:"variadic"`
}

type Instr struct {
	Op       string    `json:"op"`
	Name     string    `json:"name"`
	Type     string    `json:"type"`
	Pos      string    `json:"pos"`
	Operands []Operand `json:"operands"`
	// kind-specific fields (zero values when they do not apply)
	BinOp    string `json:"binop,omitempty"`
	UnOp     string `json:"unop,omitempty"`
	CommaOk  bool   `json:"commaok,omitempty"`
	Field    *int   `json:"field,omitempty"`
	FName    string `json:"fieldname,omitempty"`
	Heap     bool   `json:"heap,omitempty"`
	Comment  string `json:"comment,omitempty"`
	Index    *int   `json:"index,omitempty"`
	Asserted string `json:"asserted,omitempty"`
	Call     *Call  `json:"call,omitempty"`
	Fn       string `json:"fn,omitempty"`
	Edges    []int  `json:"edges,omitempty"`
	Text     string `json:"text"`
}

type Field struct {
	Name     string `json:"name"`
	Type     string `json:"type"`
	Embedded bool   `json:"embedded"`
}

type Type struct {
	Kind       string   `json:"kind"`
	Name       string   `json:"name,omitempty"`
	Underlying string   `json:"underlying,omitempty"`
	Elem       string   `json:"elem,omitempty"`
	Key        string   `json:"key,omitempty"`
	Len        *int64   `json:"len,omitempty"`
	Fields     []Field  `json:"fields,omitempty"`
	Elems      []string `json:"elems,omitempty"`
	Params     []string `json:"params,omitempty"`
	Results    []string `json:"results,omitempty"`
	Variadic   bool     `json:"variadic,omitempty"`
	Methods    []string `json:"methods,omitempty"`
	Integer    bool     `json:"integer,omitempty"`
	Unsigned   bool     `json:"unsigned,omitempty"`
	String     bool     `json:"string,omitempty"`
	Boolean    bool     `json:"boolean,omitempty"`
	Float      bool     `json:"float,omitempty"`
	Untyped    bool     `json:"untyped,omitempty"`
	Size       int64    `json:"size,omitempty"`
	Pkg        string   `json:"pkg,omitempty"`
}

// ---------------------------------------------------------------------------------------------- state

type dumper struct {
	dir   string
	fset  *token.FileSet
	sizes types.Sizes
	types map[string]*Type
}

func (d *dumper) pos(p token.Pos) string {
	if !p.IsValid() {
		return ""
	}
	pp := d.fset.Position(p)
	if pp.Filename == "" {
		return ""
	}
	return fmt.Sprintf("%s:%d:%d", d.rel(pp.Filename), pp.Line, pp.Column)
}

func (d *dumper) rel(file string) string {
	abs, err := filepath.Abs(file)
	if err == nil {
		if r, err := filepath.EvalSymlinks(abs); err == nil {
			abs = r
		}
		if r, err := filepath.Rel(d.dir, abs); err == nil && !strings.HasPrefix(r, "..") {
			return filepath.ToSlash(r)
		}
	}
	return "<outside>/" + filepath.Base(file)
}

func tkey(t types.Type) string {
	return types.TypeString(t, nil)
}

// typ registers t (and every type it mentions) and returns its key.
func (d *dumper) typ(t types.Type) string {
	if t == nil {
		return ""
	}
	k := tkey(t)
	if _, ok := d.types[k]; ok {
		return k
	}
	e := &Type{}
	d.types[k] = e // registered before recursion: named types may refer to themselves
	switch t := t.(type) {
	case *types.Basic:
		e.Kind = "basic"
		e.Name = t.Name()
		info := t.Info()
		e.Integer = info&types.IsInteger != 0
		e.Unsigned = info&types.IsUnsigned != 0
		e.String = info&types.IsString != 0
		e.Boolean = info&types.IsBoolean != 0
		e.Float = info&(types.IsFloat|types.IsComplex) != 0
		e.Untyped = info&types.IsUntyped != 0
		if e.Integer && !e.Untyped {
			e.Size = d.sizes.Sizeof(t)
		}
	case *types.Alias:
		e.Kind = "alias"
		e.Name = t.Obj().Name()
		e.Underlying = d.typ(types.Unalias(t))
	case *types.Named:
		e.Kind = "named"
		e.Name = t.Obj().Name()
		if t.Obj().Pkg() != nil {
			e.Pkg = t.Obj().Pkg().Path()
		}
		e.Underlying = d.typ(t.Underlying())
	case *types.TypeParam:
		e.Kind = "typeparam"
		e.Name = t.Obj().Name()
		e.Underlying = d.typ(t.Underlying())
	case *types.Pointer:
		e.Kind = "pointer"
		e.Elem = d.typ(t.Elem())
	case *types.Slice:
		e.Kind = "slice"
		e.Elem = d.typ(t.Elem())
	case *types.Array:
		e.Kind = "array"
		e.Elem = d.typ(t.Elem())
		n := t.Len()
		e.Len = &n
	case *types.Map:
		e.Kind = "map"
		e.Key = d.typ(t.Key())
		e.Elem = d.typ(t.Elem())
	case *types.Chan:
		e.Kind = "chan"
		e.Elem = d.typ(t.Elem())
	case *types.Struct:
		e.Kind = "struct"
		e.Fields = []Field{}
		for i := 0; i < t.NumFields(); i++ {
			f := t.Field(i)
			e.Fields = append(e.Fields, Field{Name: f.Name(), Type: d.typ(f.Type()), Embedded: f.Embedded()})
		}
	case *types.Tuple:
		e.Kind = "tuple"
		e.Elems = []string{}
		for i := 0; i < t.Len(); i++ {
			e.Elems = append(e.Elems, d.typ(t.At(i).Type()))
		}
	case *types.Signature:
		e.Kind = "signature"
		e.Params = []string{}
		e.Results = []string{}
		for i := 0; i < t.Params().Len(); i++ {
			e.Params = append(e.Params, d.typ(t.Params().At(i).Type()))
		}
		for i := 0; i < t.Results().Len(); i++ {
			e.Results = append(e.Results, d.typ(t.Results().At(i).Type()))
		}
		e.Variadic = t.Variadic()
	case *types.Interface:
		e.Kind = "interface"
		e.Methods = []string{}
		for i := 0; i < t.NumMethods(); i++ {
			e.Methods = append(e.Methods, t.Method(i).Name())
		}
		sort.Strings(e.Methods)
	case *types.Union:
		e.Kind = "union"
	default:
		e.Kind = "other"
	}
	return k
}

// ---------------------------------------------------------------------------------------------- values

func (d *dumper) operand(fn *ssa.Function, v ssa.Value) Operand {
	if v == nil {
		return nil
	}
	switch v := v.(type) {
	case *ssa.Parameter:
		for i, p := range fn.Params {
			if p == v {
				return Operand{"param": i}
			}
		}
		return Operand{"unknown": v.Name()}
	case *ssa.FreeVar:
		for i, p := range fn.FreeVars {
			if p == v {
				return Operand{"free": i}
			}
		}
		return Operand{"unknown": v.Name()}
	case *ssa.Const:
		return Operand{"const": d.constant(v)}
	case *ssa.Global:
		d.typ(v.Type())
		return Operand{"global": v.String()}
	case *ssa.Function:
		return Operand{"func": v.String()}
	case *ssa.Builtin:
		return Operand{"builtin": v.Name()}
	}
	if _, ok := v.(ssa.Instruction); ok {
		return Operand{"v": v.Name()}
	}
	return Operand{"unknown": v.Name()}
}

func (d *dumper) constant(c *ssa.Const) Const {
	out := Const{Type: d.typ(c.Type())}
	if c.Value == nil {
		if c.IsNil() {
			out.Kind = "nil"
		} else {
			out.Kind = "zero"
		}
		return out
	}
	switch c.Value.Kind() {
	case constant.Bool:
		out.Kind = "bool"
		out.Value = fmt.Sprint(constant.BoolVal(c.Value))
	case constant.String:
		out.Kind = "string"
		out.Value = constant.StringVal(c.Value)
	case constant.Int:
		out.Kind = "int"
		out.Value = c.Value.ExactString()
	case constant.Float:
		out.Kind = "float"
		out.Value = c.Value.ExactString()
	case constant.Complex:
		out.Kind = "complex"
		out.Value = c.Value.ExactString()
	default:
		out.Kind = "unknown"
		out.Value = c.Value.ExactString()
	}
	return out
}

func intp(i int) *int { return &i }

func (d *dumper) call(fn *ssa.Function, c *ssa.CallCommon) *Call {
	out := &Call{Pos: d.pos(c.Pos()), Sig: d.typ(c.Signature()), Args: []Operand{}}
	out.Variadic = c.Signature().Variadic()
	for _, a := range c.Args {
		out.Args = append(out.Args, d.operand(fn, a))
	}
	switch {
	case c.IsInvoke():
		out.Mode = "invoke"
		out.Method = c.Method.Name()
		out.Value = d.operand(fn, c.Value)
	default:
		if b, ok := c.Value.(*ssa.Builtin); ok {
			out.Mode = "builtin"
			out.Callee = b.Name()
		} else if s := c.StaticCallee(); s != nil {
			out.Mode = "static"
			out.Callee = s.String()
			out.Value = d.operand(fn, c.Value)
		} else {
			out.Mode = "dynamic"
			out.Value = d.operand(fn, c.Value)
		}
	}
	return out
}

func opName(in ssa.Instruction) string {
	s := fmt.Sprintf("%T", in)
	return strings.TrimPrefix(s, "*ssa.")
}

func (d *dumper) instr(fn *ssa.Function, in ssa.Instruction) Instr {
	out := Instr{Op: opName(in), Pos: d.pos(in.Pos()), Operands: []Operand{}}
	if v, ok := in.(ssa.Value); ok {
		out.Name = v.Name()
		out.Type = d.typ(v.Type())
	}
	for _, r := range in.Operands(nil) {
		if r == nil || *r == nil {
			out.Operands = append(out.Operands, nil)
		} else {
			out.Operands = append(out.Operands, d.operand(fn, *r))
		}
	}
	switch in := in.(type) {
	case *ssa.BinOp:
		out.BinOp = in.Op.String()
	case *ssa.UnOp:
		out.UnOp = in.Op.String()
		out.CommaOk = in.CommaOk
	case *ssa.Field:
		out.Field = intp(in.Field)
		out.FName = structField(in.X.Type(), in.Field, false)
	case *ssa.FieldAddr:
		out.Field = intp(in.Field)
		out.FName = structField(in.X.Type(), in.Field, true)
	case *ssa.Alloc:
		out.Heap = in.Heap
		out.Comment = in.Comment
	case *ssa.Phi:
		out.Comment = in.Comment
		for _, p := range in.Block().Preds {
			out.Edges = append(out.Edges, p.Index)
		}
	case *ssa.Extract:
		out.Index = intp(in.Index)
	case *ssa.Lookup:
		out.CommaOk = in.CommaOk
	case *ssa.TypeAssert:
		out.Asserted = d.typ(in.AssertedType)
		out.CommaOk = in.CommaOk
	case *ssa.Call:
		out.Call = d.call(fn, &in.Call)
	case *ssa.Go:
		out.Call = d.call(fn, &in.Call)
	case *ssa.Defer:
		out.Call = d.call(fn, &in.Call)
	case *ssa.MakeClosure:
		out.Fn = in.Fn.(*ssa.Function).String()
	case *ssa.Next:
		out.CommaOk = in.IsString
	}
	out.Text = instrText(in)
	return out
}

// instrText is go/ssa's own rendering of the instruction with package paths in full (for humans and
// debugging only; the extractor reads the structured fields).
func instrText(in ssa.Instruction) string {
	if v, ok := in.(ssa.Value); ok && v.Name() != "" {
		return v.Name() + " = " + in.String()
	}
	return in.String()
}

func structField(t types.Type, i int, ptr bool) string {
	u := t.Underlying()
	if ptr {
		if p, ok := u.(*types.Pointer); ok {
			u = p.Elem().Underlying()
		}
	}
	if s, ok := u.(*types.Struct); ok && i < s.NumFields() {
		return s.Field(i).Name()
	}
	return ""
}

// ---------------------------------------------------------------------------------------------- functions

func (d *dumper) function(fn *ssa.Function) Function {
	out := Function{ID: fn.String(), Name: fn.Name(), Synthetic: fn.Synthetic, Pos: d.pos(fn.Pos()),
		Signature: d.typ(fn.Signature), Params: []Var{}, FreeVars: []Var{}, Results: []string{},
		Blocks: []Block{}, Recover: -1, Loops: []Loop{}}
	if fn.Pkg != nil {
		out.Package = fn.Pkg.Pkg.Path()
	}
	if fn.Parent() != nil {
		out.Parent = fn.Parent().String()
	}
	out.Method = fn.Signature.Recv() != nil
	for _, p := range fn.Params {
		out.Params = append(out.Params, Var{Name: p.Name(), Type: d.typ(p.Type())})
	}
	for _, p := range fn.FreeVars {
		out.FreeVars = append(out.FreeVars, Var{Name: p.Name(), Type: d.typ(p.Type())})
	}
	res := fn.Signature.Results()
	for i := 0; i < res.Len(); i++ {
		out.Results = append(out.Results, d.typ(res.At(i).Type()))
	}
	for _, b := range fn.Blocks {
		blk := Block{Index: b.Index, Comment: b.Comment, Preds: []int{}, Succs: []int{}, Idom: -1, Instrs: []Instr{}}
		for _, p := range b.Preds {
			blk.Preds = append(blk.Preds, p.Index)
		}
		for _, s := range b.Succs {
			blk.Succs = append(blk.Succs, s.Index)
		}
		if b.Idom() != nil {
			blk.Idom = b.Idom().Index
		}
		for _, in := range b.Instrs {
			blk.Instrs = append(blk.Instrs, d.instr(fn, in))
		}
		out.Blocks = append(out.Blocks, blk)
	}
	if fn.Recover != nil {
		out.Recover = fn.Recover.Index
	}
	out.Loops = d.loops(fn)
	return out
}

// loops lists the For and Range statements of fn's own body (the bodies of function literals belong to
// the closures).
func (d *dumper) loops(fn *ssa.Function) []Loop {
	out := []Loop{}
	var body *ast.BlockStmt
	switch s := fn.Syntax().(type) {
	case *ast.FuncDecl:
		body = s.Body
	case *ast.FuncLit:
		body = s.Body
	}
	if body == nil {
		return out
	}
	ast.Inspect(body, func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.FuncLit:
			return false
		case *ast.ForStmt:
			out = append(out, Loop{Kind: "for", Pos: d.pos(n.For), End: d.pos(n.End()), Cond: n.Cond != nil})
		case *ast.RangeStmt:
			out = append(out, Loop{Kind: "range", Pos: d.pos(n.For), End: d.pos(n.End()), Cond: true})
		}
		return true
	})
	return out
}

// ---------------------------------------------------------------------------------------------- main

func main() {
	dir := flag.String("dir", ".", "directory the patterns are resolved in; positions are relative to it")
	flag.Parse()
	patterns := flag.Args()
	if len(patterns) == 0 {
		fmt.Fprintln(os.Stderr, "usage: ssadump -dir DIR PATTERN...")
		os.Exit(2)
	}
	absDir, err := filepath.Abs(*dir)
	if err == nil {
		absDir, err = filepath.EvalSymlinks(absDir)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "ssadump:", err)
		os.Exit(2)
	}
	mode := packages.NeedName | packages.NeedFiles | packages.NeedCompiledGoFiles | packages.NeedImports |
		packages.NeedTypes | packages.NeedTypesSizes | packages.NeedSyntax | packages.NeedTypesInfo
	cfg := &packages.Config{Mode: mode, Dir: absDir, Tests: false}
	pkgs, err := packages.Load(cfg, patterns...)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ssadump: load:", err)
		os.Exit(2)
	}
	bad := 0
	for _, p := range pkgs {
		for _, e := range p.Errors {
			fmt.Fprintf(os.Stderr, "ssadump: %s: %s\n", p.PkgPath, e.Msg)
			bad++
		}
		if p.Types == nil || p.IllTyped {
			bad++
		}
	}
	if bad > 0 || len(pkgs) == 0 {
		fmt.Fprintln(os.Stderr, "ssadump: packages did not load or type-check")
		os.Exit(2)
	}
	sort.Slice(pkgs, func(i, j int) bool { return pkgs[i].PkgPath < pkgs[j].PkgPath })

	prog := ssa.NewProgram(pkgs[0].Fset, ssa.BuilderMode(0))
	created := map[*types.Package]bool{}
	var spkgs []*ssa.Package
	for _, p := range pkgs {
		created[p.Types] = true
		spkgs = append(spkgs, prog.CreatePackage(p.Types, p.Syntax, p.TypesInfo, true))
	}
	var createAll func([]*types.Package)
	createAll = func(ps []*types.Package) {
		for _, p := range ps {
			if !created[p] {
				created[p] = true
				prog.CreatePackage(p, nil, nil, true)
				createAll(p.Imports())
			}
		}
	}
	for _, p := range pkgs {
		createAll(p.Types.Imports())
	}
	for _, sp := range spkgs {
		sp.Build()
	}

	d := &dumper{dir: absDir, fset: prog.Fset, sizes: types.SizesFor("gc", "amd64"), types: map[string]*Type{}}
	doc := Doc{Version: version, Packages: []Package{}, Globals: []Global{}, Functions: []Function{}}
	matched := map[*ssa.Package]bool{}
	for i, p := range pkgs {
		matched[spkgs[i]] = true
		files := []string{}
		for _, f := range p.CompiledGoFiles {
			files = append(files, d.rel(f))
		}
		sort.Strings(files)
		pdir := ""
		if len(files) > 0 {
			pdir = filepath.ToSlash(filepath.Dir(files[0]))
		}
		doc.Packages = append(doc.Packages, Package{Path: p.PkgPath, Name: p.Name, Dir: pdir, Files: files})
		for _, m := range spkgs[i].Members {
			if g, ok := m.(*ssa.Global); ok {
				doc.Globals = append(doc.Globals, Global{ID: g.String(), Name: g.Name(), Package: p.PkgPath,
					Type: d.typ(g.Type()), Pos: d.pos(g.Pos())})
			}
		}
	}
	sort.Slice(doc.Globals, func(i, j int) bool { return doc.Globals[i].ID < doc.Globals[j].ID })

	var fns []*ssa.Function
	for fn := range ssautil.AllFunctions(prog) {
		if fn.Pkg != nil && matched[fn.Pkg] {
			fns = append(fns, fn)
		}
	}
	sort.Slice(fns, func(i, j int) bool {
		a, b := fns[i].String(), fns[j].String()
		if a != b {
			return a < b
		}
		return d.pos(fns[i].Pos()) < d.pos(fns[j].Pos())
	})
	for _, fn := range fns {
		doc.Functions = append(doc.Functions, d.function(fn))
	}
	doc.Types = d.types

	w := bufio.NewWriterSize(os.Stdout, 1<<20)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(doc); err != nil {
		fmt.Fprintln(os.Stderr, "ssadump: write:", err)
		os.Exit(2)
	}
	if err := w.Flush(); err != nil {
		fmt.Fprintln(os.Stderr, "ssadump: write:", err)
		os.Exit(2)
	}
}
