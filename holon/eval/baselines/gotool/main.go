// Command gotool is the I52 baselines' Go reader (standard library only, go/parser and go/ast; no type checking).
//
//	gotool list DIR       the package in DIR (non-test files): functions with receiver, parameter and result types
//	                      and spans; type declarations (struct fields with promoted fields of same-package embedded
//	                      structs, underlying type expressions); and the Fuzz* functions of DIR's _test.go files
//	gotool mine DIR...    frequency-based beliefs B1-B3 over the packages (I52_baselines.json spec_mining), JSON
//
// Output is JSON on stdout, sorted, deterministic.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/printer"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Field struct {
	Name string `json:"name"`
	Type string `json:"type"`
	Via  string `json:"via"`
}

type Func struct {
	Name     string   `json:"name"`
	Recv     string   `json:"recv"`
	RecvPtr  bool     `json:"recv_ptr"`
	Params   []string `json:"params"`
	Results  []string `json:"results"`
	Generic  bool     `json:"generic"`
	File     string   `json:"file"`
	Start    int      `json:"start"`
	End      int      `json:"end"`
	Exported bool     `json:"exported"`
}

type TypeDecl struct {
	Name       string  `json:"name"`
	Underlying string  `json:"underlying"`
	Struct     bool    `json:"struct"`
	Fields     []Field `json:"fields"`
	File       string  `json:"file"`
	Start      int     `json:"start"`
	End        int     `json:"end"`
	Generic    bool    `json:"generic"`
}

type Pkg struct {
	Package string     `json:"package"`
	Funcs   []Func     `json:"funcs"`
	Types   []TypeDecl `json:"types"`
	Fuzz    []string   `json:"fuzz"`
	Errors  []string   `json:"errors"`
}

var fset = token.NewFileSet()

func expr(e ast.Expr) string {
	var b strings.Builder
	printer.Fprint(&b, fset, e)
	return b.String()
}

func parseDir(dir string, tests bool) (map[string]*ast.File, []string) {
	files := map[string]*ast.File{}
	var errs []string
	ents, _ := os.ReadDir(dir)
	for _, e := range ents {
		n := e.Name()
		if e.IsDir() || !strings.HasSuffix(n, ".go") || strings.HasPrefix(n, "holon_") {
			continue
		}
		if strings.HasSuffix(n, "_test.go") != tests {
			continue
		}
		f, err := parser.ParseFile(fset, filepath.Join(dir, n), nil, parser.ParseComments)
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		files[n] = f
	}
	return files, errs
}

func sortedKeys(m map[string]*ast.File) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	return ks
}

func fieldTypes(fl *ast.FieldList) []string {
	var out []string
	if fl == nil {
		return out
	}
	for _, f := range fl.List {
		n := len(f.Names)
		if n == 0 {
			n = 1
		}
		for i := 0; i < n; i++ {
			out = append(out, expr(f.Type))
		}
	}
	return out
}

func list(dir string) Pkg {
	files, errs := parseDir(dir, false)
	p := Pkg{Errors: errs}
	structs := map[string]*ast.StructType{}
	for _, name := range sortedKeys(files) {
		f := files[name]
		p.Package = f.Name.Name
		for _, d := range f.Decls {
			switch d := d.(type) {
			case *ast.FuncDecl:
				fn := Func{Name: d.Name.Name, File: name, Start: fset.Position(d.Pos()).Line, End: fset.Position(d.End()).Line,
					Params: fieldTypes(d.Type.Params), Results: fieldTypes(d.Type.Results), Exported: d.Name.IsExported(),
					Generic: d.Type.TypeParams != nil && len(d.Type.TypeParams.List) > 0}
				if d.Recv != nil && len(d.Recv.List) == 1 {
					t := d.Recv.List[0].Type
					if s, ok := t.(*ast.StarExpr); ok {
						fn.RecvPtr = true
						t = s.X
					}
					switch t := t.(type) {
					case *ast.Ident:
						fn.Recv = t.Name
					case *ast.IndexExpr:
						fn.Recv, fn.Generic = expr(t.X), true
					case *ast.IndexListExpr:
						fn.Recv, fn.Generic = expr(t.X), true
					}
				}
				p.Funcs = append(p.Funcs, fn)
			case *ast.GenDecl:
				for _, s := range d.Specs {
					ts, ok := s.(*ast.TypeSpec)
					if !ok {
						continue
					}
					td := TypeDecl{Name: ts.Name.Name, Underlying: expr(ts.Type), File: name,
						Start: fset.Position(ts.Pos()).Line, End: fset.Position(ts.End()).Line,
						Generic: ts.TypeParams != nil && len(ts.TypeParams.List) > 0}
					if st, ok := ts.Type.(*ast.StructType); ok {
						td.Struct = true
						structs[ts.Name.Name] = st
					}
					p.Types = append(p.Types, td)
				}
			}
		}
	}
	var fieldsOf func(st *ast.StructType, via string, depth int) []Field
	fieldsOf = func(st *ast.StructType, via string, depth int) []Field {
		var out []Field
		for _, f := range st.Fields.List {
			if len(f.Names) == 0 {
				tn := strings.TrimPrefix(expr(f.Type), "*")
				if inner, ok := structs[tn]; ok && depth < 4 {
					out = append(out, fieldsOf(inner, via+tn+".", depth+1)...)
				}
				continue
			}
			for _, n := range f.Names {
				if n.IsExported() {
					out = append(out, Field{Name: n.Name, Type: expr(f.Type), Via: via})
				}
			}
		}
		return out
	}
	for i := range p.Types {
		if st, ok := structs[p.Types[i].Name]; ok {
			// own fields shadow promoted ones
			seen := map[string]bool{}
			var fs []Field
			for _, f := range fieldsOf(st, "", 0) {
				if f.Via == "" {
					seen[f.Name] = true
				}
			}
			for _, f := range fieldsOf(st, "", 0) {
				if f.Via != "" && seen[f.Name] {
					continue
				}
				fs = append(fs, f)
			}
			p.Types[i].Fields = fs
		}
	}
	tfiles, _ := parseDir(dir, true)
	for _, name := range sortedKeys(tfiles) {
		for _, d := range tfiles[name].Decls {
			if fd, ok := d.(*ast.FuncDecl); ok && fd.Recv == nil && strings.HasPrefix(fd.Name.Name, "Fuzz") {
				p.Fuzz = append(p.Fuzz, fd.Name.Name)
			}
		}
	}
	sort.Strings(p.Fuzz)
	return p
}

// ---------------------------------------------------------------------------------------------- mining
type Site struct {
	File string `json:"file"`
	Line int    `json:"line"`
	Func string `json:"func"`
}

type Deviant struct {
	Belief  string  `json:"belief"`
	Subject string  `json:"subject"`
	Support int     `json:"support"`
	Conf    float64 `json:"confidence"`
	Site    Site    `json:"site"`
	Message string  `json:"message"`
}

const minSupport = 3
const minConf = 0.75

func callee(c *ast.CallExpr) string {
	switch f := c.Fun.(type) {
	case *ast.Ident:
		return f.Name
	case *ast.SelectorExpr:
		return expr(f)
	}
	return ""
}

var skipCallee = map[string]bool{"len": true, "cap": true, "append": true, "make": true, "new": true, "panic": true,
	"copy": true, "delete": true, "close": true, "print": true, "println": true, "recover": true, "min": true, "max": true}

func isErrName(e ast.Expr) bool {
	id, ok := e.(*ast.Ident)
	return ok && (id.Name == "err" || strings.HasSuffix(id.Name, "Err") || strings.HasSuffix(id.Name, "err"))
}

func mine(dirs []string, root string) []Deviant {
	type use struct {
		site    Site
		checked bool
	}
	calls := map[string][]use{}
	type asrt struct {
		site Site
		ok   bool
	}
	asserts := map[string][]asrt{}
	type fninfo struct {
		site  Site
		seq   []string
		lines map[string]int
	}
	var fns []fninfo
	for _, dir := range dirs {
		files, _ := parseDir(dir, false)
		pkg := ""
		for _, name := range sortedKeys(files) {
			f := files[name]
			pkg = f.Name.Name
			rel, _ := filepath.Rel(root, filepath.Join(dir, name))
			rel = filepath.ToSlash(rel)
			for _, d := range f.Decls {
				fd, ok := d.(*ast.FuncDecl)
				if !ok || fd.Body == nil {
					continue
				}
				fname := fd.Name.Name
				if fd.Recv != nil && len(fd.Recv.List) == 1 {
					fname = strings.TrimPrefix(expr(fd.Recv.List[0].Type), "*") + "." + fname
				}
				fi := fninfo{site: Site{rel, fset.Position(fd.Pos()).Line, fname}, lines: map[string]int{}}
				ast.Inspect(fd.Body, func(n ast.Node) bool {
					switch n := n.(type) {
					case *ast.ExprStmt:
						if c, ok := n.X.(*ast.CallExpr); ok {
							if k := callee(c); k != "" && !skipCallee[k] {
								calls[k] = append(calls[k], use{Site{rel, fset.Position(c.Pos()).Line, fname}, false})
							}
						}
					case *ast.AssignStmt:
						if len(n.Rhs) == 1 {
							if c, ok := n.Rhs[0].(*ast.CallExpr); ok && len(n.Lhs) >= 1 {
								if k := callee(c); k != "" && !skipCallee[k] {
									last := n.Lhs[len(n.Lhs)-1]
									if isErrName(last) {
										calls[k] = append(calls[k], use{Site{rel, fset.Position(c.Pos()).Line, fname}, true})
									} else if id, ok := last.(*ast.Ident); ok && id.Name == "_" && len(n.Lhs) >= 2 {
										calls[k] = append(calls[k], use{Site{rel, fset.Position(c.Pos()).Line, fname}, false})
									}
								}
							}
							if ta, ok := n.Rhs[0].(*ast.TypeAssertExpr); ok && ta.Type != nil {
								key := pkg
								asserts[key] = append(asserts[key], asrt{Site{rel, fset.Position(ta.Pos()).Line, fname}, len(n.Lhs) == 2})
							}
						}
					case *ast.ValueSpec:
						if len(n.Values) == 1 {
							if ta, ok := n.Values[0].(*ast.TypeAssertExpr); ok && ta.Type != nil {
								asserts[pkg] = append(asserts[pkg], asrt{Site{rel, fset.Position(ta.Pos()).Line, fname}, len(n.Names) == 2})
							}
						}
					case *ast.CallExpr:
						if k := callee(n); k != "" && !skipCallee[k] {
							fi.seq = append(fi.seq, k)
							if _, ok := fi.lines[k]; !ok {
								fi.lines[k] = fset.Position(n.Pos()).Line
							}
						}
					}
					return true
				})
				fns = append(fns, fi)
			}
		}
	}
	var out []Deviant
	// B1: must-check results (error results by name, comma-ok assertions)
	ks := make([]string, 0, len(calls))
	for k := range calls {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	for _, k := range ks {
		us := calls[k]
		n, c := len(us), 0
		for _, u := range us {
			if u.checked {
				c++
			}
		}
		conf := float64(c) / float64(n)
		if n >= minSupport && conf >= minConf && c < n {
			for _, u := range us {
				if !u.checked {
					out = append(out, Deviant{"B1", k, n, conf, u.site,
						fmt.Sprintf("the result of %s is checked at %d of its %d call sites, but discarded here", k, c, n)})
				}
			}
		}
	}
	aks := make([]string, 0, len(asserts))
	for k := range asserts {
		aks = append(aks, k)
	}
	sort.Strings(aks)
	for _, k := range aks {
		as := asserts[k]
		n, c := len(as), 0
		for _, a := range as {
			if a.ok {
				c++
			}
		}
		conf := float64(c) / float64(n)
		if n >= minSupport && conf >= minConf && c < n {
			for _, a := range as {
				if !a.ok {
					out = append(out, Deviant{"B1", "type assertion in package " + k, n, conf, a.site,
						fmt.Sprintf("%d of the package's %d type assertions check the ok result; this one does not (it panics on a mismatch)", c, n)})
				}
			}
		}
	}
	// B2: lock pairing; B3: call order
	type pairStat struct{ with, total int }
	lockOf := func(k string) (string, string) {
		for _, p := range [][2]string{{".Lock", ".Unlock"}, {".RLock", ".RUnlock"}} {
			if strings.HasSuffix(k, p[0]) {
				return strings.TrimSuffix(k, p[0]), p[1]
			}
		}
		return "", ""
	}
	follow := map[string]map[string]int{}
	total := map[string]int{}
	for _, fi := range fns {
		firstSeen := map[string]bool{}
		for i, a := range fi.seq {
			if firstSeen[a] {
				continue
			}
			firstSeen[a] = true
			total[a]++
			after := map[string]bool{}
			for _, b := range fi.seq[i+1:] {
				if b != a {
					after[b] = true
				}
			}
			if follow[a] == nil {
				follow[a] = map[string]int{}
			}
			for b := range after {
				follow[a][b]++
			}
		}
	}
	as := make([]string, 0, len(total))
	for a := range total {
		as = append(as, a)
	}
	sort.Strings(as)
	for _, a := range as {
		if total[a] < minSupport {
			continue
		}
		obj, unlock := lockOf(a)
		bs := make([]string, 0, len(follow[a]))
		for b := range follow[a] {
			bs = append(bs, b)
		}
		sort.Strings(bs)
		for _, b := range bs {
			isLock := obj != "" && b == obj+unlock
			if obj != "" && !isLock {
				continue
			}
			conf := float64(follow[a][b]) / float64(total[a])
			if conf < minConf || follow[a][b] == total[a] {
				continue
			}
			belief := "B3"
			if isLock {
				belief = "B2"
			}
			for _, fi := range fns {
				idx := -1
				for i, x := range fi.seq {
					if x == a {
						idx = i
						break
					}
				}
				if idx < 0 {
					continue
				}
				has := false
				for _, x := range fi.seq[idx+1:] {
					if x == b {
						has = true
					}
				}
				if !has {
					out = append(out, Deviant{belief, a + " -> " + b, total[a], conf,
						Site{fi.site.File, fi.lines[a], fi.site.Func},
						fmt.Sprintf("%s is followed by %s in %d of the %d functions calling it, but not in %s", a, b, follow[a][b], total[a], fi.site.Func)})
				}
			}
		}
	}
	sort.Slice(out, func(i, j int) bool {
		x, y := out[i], out[j]
		if x.Site.File != y.Site.File {
			return x.Site.File < y.Site.File
		}
		if x.Site.Line != y.Site.Line {
			return x.Site.Line < y.Site.Line
		}
		if x.Belief != y.Belief {
			return x.Belief < y.Belief
		}
		return x.Subject < y.Subject
	})
	return out
}

func main() {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", " ")
	switch os.Args[1] {
	case "list":
		_ = enc.Encode(list(os.Args[2]))
	case "mine":
		_ = enc.Encode(mine(os.Args[3:], os.Args[2]))
	default:
		fmt.Fprintln(os.Stderr, "usage: gotool list DIR | gotool mine ROOT DIR...")
		os.Exit(2)
	}
}
