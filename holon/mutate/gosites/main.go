// Command gosites prints the sites of holon.mutate's Go operators (I61: the instrument's "operators" whose language
// is go), matched with go/ast on every function of the files it is given.
//
//	gosites ROOT FILE...
//
// FILE is a path relative to ROOT. The output is one JSON object per site and line, the files in argument order and
// each file's sites by start offset, then operator:
//
//	{"op", "file", "start", "end", "lits", "recv", "ptr", "name", "anon", "generic"}
//
// start and end bound the replaced byte range. lits holds the byte ranges of the decimal literals a variant shifts:
// one for putuint64_offset and copy_offset, the low and the high bound for go_slice_offset, none for drop_len_check.
// recv, ptr, name, anon and generic locate the enclosing function: the receiver's type name ("" for a function),
// whether the receiver is a pointer, the declared name, the path of function literals ([k, j]: the j-th literal of
// the k-th literal, in source order, which go/ssa names F$k$j) and whether the receiver has type parameters. go/ssa
// also numbers the bodies of range-over-func loops among a function's closures; telling those loops apart needs
// types, which go/ast does not have, so a site after such a loop inside a function literal would be misnamed.
//
// The program reads only the files it is named, and it knows no name of any target: the patterns are the
// operators' own (the standard library's binary.BigEndian, copy, len, errors.New and fmt.Errorf).
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

type site struct {
	Op      string   `json:"op"`
	File    string   `json:"file"`
	Start   int      `json:"start"`
	End     int      `json:"end"`
	Lits    [][2]int `json:"lits"`
	Recv    string   `json:"recv"`
	Ptr     bool     `json:"ptr"`
	Name    string   `json:"name"`
	Anon    []int    `json:"anon"`
	Generic bool     `json:"generic"`
}

// A decimal integer literal of the Go specification (no prefix, no leading zero, no digit separator).
var decimal = regexp.MustCompile(`^(0|[1-9][0-9]*)$`)

func decLit(e ast.Expr) (*ast.BasicLit, bool) {
	b, ok := e.(*ast.BasicLit)
	if !ok || b.Kind != token.INT || !decimal.MatchString(b.Value) {
		return nil, false
	}
	return b, true
}

func named(e ast.Expr, name string) bool {
	id, ok := e.(*ast.Ident)
	return ok && id.Name == name
}

// builtin: an identifier with the builtin's name that the file does not declare (go/parser resolves every
// identifier the file declares, so a predeclared one stays unresolved).
func builtin(e ast.Expr, name string) bool {
	id, ok := e.(*ast.Ident)
	return ok && id.Name == name && id.Obj == nil
}

// bigEndianPut: a call of binary.BigEndian.<method>, method exactly `exact`, or any Put* when exact is "".
func bigEndianPut(call *ast.CallExpr, exact string) bool {
	s, ok := call.Fun.(*ast.SelectorExpr)
	if !ok {
		return false
	}
	if exact != "" && s.Sel.Name != exact {
		return false
	}
	if exact == "" && !strings.HasPrefix(s.Sel.Name, "Put") {
		return false
	}
	x, ok := s.X.(*ast.SelectorExpr)
	return ok && x.Sel.Name == "BigEndian" && named(x.X, "binary")
}

// openSlice: x[K:], a slice expression with a decimal literal low bound K and no high and no max bound.
func openSlice(e ast.Expr) (*ast.BasicLit, bool) {
	sl, ok := e.(*ast.SliceExpr)
	if !ok || sl.Slice3 || sl.Low == nil || sl.High != nil || sl.Max != nil {
		return nil, false
	}
	return decLit(sl.Low)
}

// errorValue: the I18 go-errors-nonnil forms: an identifier or a selector named Err..., errors.New(..),
// fmt.Errorf(..).
func errorValue(e ast.Expr) bool {
	switch x := e.(type) {
	case *ast.Ident:
		return strings.HasPrefix(x.Name, "Err")
	case *ast.SelectorExpr:
		return strings.HasPrefix(x.Sel.Name, "Err")
	case *ast.CallExpr:
		s, ok := x.Fun.(*ast.SelectorExpr)
		if !ok {
			return false
		}
		return (named(s.X, "errors") && s.Sel.Name == "New") || (named(s.X, "fmt") && s.Sel.Name == "Errorf")
	}
	return false
}

func lenCall(e ast.Expr) bool {
	c, ok := e.(*ast.CallExpr)
	return ok && len(c.Args) == 1 && c.Ellipsis == token.NoPos && builtin(c.Fun, "len")
}

// constant: a decimal integer literal, or an identifier declared const in the same file.
func constant(e ast.Expr) bool {
	if _, ok := decLit(e); ok {
		return true
	}
	id, ok := e.(*ast.Ident)
	return ok && id.Obj != nil && id.Obj.Kind == ast.Con
}

// lenCheck: an if statement with no init and no else, whose condition compares len(e) with a constant and whose
// body is exactly one return statement whose last result is an error value.
func lenCheck(s *ast.IfStmt) bool {
	if s.Init != nil || s.Else != nil {
		return false
	}
	be, ok := s.Cond.(*ast.BinaryExpr)
	if !ok {
		return false
	}
	switch be.Op {
	case token.EQL, token.NEQ, token.LSS, token.LEQ, token.GTR, token.GEQ:
	default:
		return false
	}
	if !((lenCall(be.X) && constant(be.Y)) || (lenCall(be.Y) && constant(be.X))) {
		return false
	}
	if len(s.Body.List) != 1 {
		return false
	}
	r, ok := s.Body.List[0].(*ast.ReturnStmt)
	return ok && len(r.Results) > 0 && errorValue(r.Results[len(r.Results)-1])
}

type walker struct {
	fset    *token.FileSet
	file    string
	recv    string
	ptr     bool
	name    string
	generic bool
	written map[*ast.SliceExpr]bool // first arguments of copy and of binary.BigEndian.Put* (not read)
	out     []site
}

func (w *walker) off(p token.Pos) int { return w.fset.Position(p).Offset }

func (w *walker) emit(op string, a, b token.Pos, lits []*ast.BasicLit, anon []int) {
	s := site{Op: op, File: w.file, Start: w.off(a), End: w.off(b), Lits: [][2]int{}, Recv: w.recv, Ptr: w.ptr,
		Name: w.name, Anon: append([]int{}, anon...), Generic: w.generic}
	for _, l := range lits {
		s.Lits = append(s.Lits, [2]int{w.off(l.Pos()), w.off(l.End())})
	}
	w.out = append(w.out, s)
}

// walk matches the patterns in body, the body of the function at path anon; each function literal is walked as
// its own function, numbered in source order.
func (w *walker) walk(body *ast.BlockStmt, anon []int) {
	n := 0
	ast.Inspect(body, func(x ast.Node) bool {
		switch v := x.(type) {
		case *ast.FuncLit:
			n++
			w.walk(v.Body, append(append([]int{}, anon...), n))
			return false
		case *ast.CallExpr:
			if len(v.Args) == 2 && bigEndianPut(v, "PutUint64") {
				if lit, ok := openSlice(v.Args[0]); ok {
					w.emit("putuint64_offset", lit.Pos(), lit.End(), []*ast.BasicLit{lit}, anon)
				}
			}
			if len(v.Args) == 2 && builtin(v.Fun, "copy") {
				if lit, ok := openSlice(v.Args[0]); ok {
					w.emit("copy_offset", lit.Pos(), lit.End(), []*ast.BasicLit{lit}, anon)
				}
			}
		case *ast.IfStmt:
			if lenCheck(v) {
				w.emit("drop_len_check", v.Pos(), v.End(), nil, anon)
			}
		case *ast.SliceExpr:
			if !v.Slice3 && v.Max == nil && v.Low != nil && v.High != nil && !w.written[v] {
				lo, ok1 := decLit(v.Low)
				hi, ok2 := decLit(v.High)
				if ok1 && ok2 {
					w.emit("go_slice_offset", lo.Pos(), hi.End(), []*ast.BasicLit{lo, hi}, anon)
				}
			}
		}
		return true
	})
}

func receiver(fd *ast.FuncDecl) (string, bool, bool) {
	if fd.Recv == nil || len(fd.Recv.List) == 0 {
		return "", false, false
	}
	t := fd.Recv.List[0].Type
	ptr := false
	if s, ok := t.(*ast.StarExpr); ok {
		ptr, t = true, s.X
	}
	switch x := t.(type) {
	case *ast.Ident:
		return x.Name, ptr, false
	case *ast.IndexExpr:
		if id, ok := x.X.(*ast.Ident); ok {
			return id.Name, ptr, true
		}
	case *ast.IndexListExpr:
		if id, ok := x.X.(*ast.Ident); ok {
			return id.Name, ptr, true
		}
	}
	return "?", ptr, true
}

func sites(root, rel string) ([]site, error) {
	src, err := os.ReadFile(filepath.Join(root, rel))
	if err != nil {
		return nil, err
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, rel, src, 0)
	if err != nil {
		return nil, err
	}
	var out []site
	for _, d := range f.Decls {
		fd, ok := d.(*ast.FuncDecl)
		if !ok || fd.Body == nil {
			continue
		}
		w := &walker{fset: fset, file: rel, name: fd.Name.Name, written: map[*ast.SliceExpr]bool{}}
		w.recv, w.ptr, w.generic = receiver(fd)
		ast.Inspect(fd.Body, func(x ast.Node) bool {
			if c, ok := x.(*ast.CallExpr); ok && len(c.Args) >= 1 && (builtin(c.Fun, "copy") || bigEndianPut(c, "")) {
				if sl, ok := c.Args[0].(*ast.SliceExpr); ok {
					w.written[sl] = true
				}
			}
			return true
		})
		w.walk(fd.Body, nil)
		out = append(out, w.out...)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Start != out[j].Start {
			return out[i].Start < out[j].Start
		}
		return out[i].Op < out[j].Op
	})
	return out, nil
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: gosites ROOT FILE...")
		os.Exit(2)
	}
	enc := json.NewEncoder(os.Stdout)
	for _, rel := range os.Args[2:] {
		ss, err := sites(os.Args[1], rel)
		if err != nil {
			fmt.Fprintf(os.Stderr, "gosites: %s: %v\n", rel, err)
			os.Exit(1)
		}
		for _, s := range ss {
			if err := enc.Encode(s); err != nil {
				fmt.Fprintf(os.Stderr, "gosites: %v\n", err)
				os.Exit(1)
			}
		}
	}
}
