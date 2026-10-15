// I48 instrument (tests_m4/_i48.py::go_ast; rule N3): prints the AST of one Go file, one line per node in preorder.
//
// Each node line is "<depth> <Type>" followed by every field of the node that is a token.Token, an ast.ChanDir, a
// string or a bool ("Op=+", "Tok=:=", "Dir=1", "Slice3=true"; an identifier as "Ident Name=x", every other string
// %q-quoted, so a literal prints as BasicLit Kind=STRING Value="\"a\""), and "<Field>=nil" for every child-node field
// that is nil (so x[i:] and x[:i] differ). A declaring identifier (rule N1 (a): the name of a func, method, var,
// const, type, field, parameter, result, label or import alias, or a := or range := name) ends with " Decl". Depth
// is decremented on ast.Inspect's nil callback, so f(g(1), 2) and f(g(1, 2)) differ.
//
// Comments are not nodes. The comments rule N1 keeps verbatim are printed first, in file order: each directive
// (//go:, // +build, //export , //line , /*line ) as "Directive at=<k> %q", k the number of nodes that start before
// it, and the cgo preamble (as cmd/cgo reads it: the doc comment of the import "C" spec, else the doc comment of its
// import declaration when that declaration holds exactly one spec, parenthesised or not) as "CgoPreamble %q", its raw
// comment texts joined by newlines. Positions are never printed. Standard library only; parses with
// parser.ParseComments.
//
// With -comments, it prints instead every comment of the file in file order as "Comment <byte offset> kept %q" (a
// directive, or a comment of the cgo preamble) or "Comment <byte offset> removed %q" (rule N1 removes it).
//
// Exit status: 0 printed, 1 the file does not parse, 2 usage.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"reflect"
	"strings"
)

func directive(t string) bool {
	return strings.HasPrefix(t, "//go:") || strings.HasPrefix(t, "// +build") || strings.HasPrefix(t, "//export ") ||
		strings.HasPrefix(t, "//line ") || strings.HasPrefix(t, "/*line ")
}

func raw(g *ast.CommentGroup) string {
	var xs []string
	for _, c := range g.List {
		xs = append(xs, c.Text)
	}
	return strings.Join(xs, "\n")
}

var (
	posType   = reflect.TypeOf(token.NoPos)
	tokType   = reflect.TypeOf(token.ILLEGAL)
	dirType   = reflect.TypeOf(ast.SEND)
	cgType    = reflect.TypeOf((*ast.CommentGroup)(nil))
	objType   = reflect.TypeOf((*ast.Object)(nil))
	scopeType = reflect.TypeOf((*ast.Scope)(nil))
	nodeType  = reflect.TypeOf((*ast.Node)(nil)).Elem()
)

func main() {
	args := os.Args[1:]
	comments := len(args) == 2 && args[0] == "-comments"
	if comments {
		args = args[1:]
	}
	if len(args) != 1 {
		fmt.Fprintln(os.Stderr, "usage: goast [-comments] FILE")
		os.Exit(2)
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, args[0], nil, parser.SkipObjectResolution|parser.ParseComments)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	preamble := map[*ast.CommentGroup]bool{}
	for _, d := range f.Decls {
		g, ok := d.(*ast.GenDecl)
		if !ok || g.Tok != token.IMPORT {
			continue
		}
		for _, s := range g.Specs {
			sp := s.(*ast.ImportSpec)
			if sp.Path.Value != `"C"` {
				continue
			}
			// as cmd/cgo reads it: the spec's doc comment, else the declaration's when it holds exactly one spec
			if sp.Doc != nil {
				preamble[sp.Doc] = true
			} else if g.Doc != nil && len(g.Specs) == 1 {
				preamble[g.Doc] = true
			}
		}
	}
	if comments {
		for _, g := range f.Comments {
			for _, c := range g.List {
				kept := "removed"
				if directive(c.Text) || preamble[g] {
					kept = "kept"
				}
				fmt.Printf("Comment %d %s %q\n", fset.Position(c.Pos()).Offset, kept, c.Text)
			}
		}
		return
	}

	// declaring identifiers (rule N1 (a)) and the start of every node
	decl := map[*ast.Ident]bool{}
	var starts []token.Pos
	ast.Inspect(f, func(n ast.Node) bool {
		if n == nil {
			return false
		}
		switch n.(type) {
		case *ast.CommentGroup, *ast.Comment:
			return false
		}
		starts = append(starts, n.Pos())
		switch x := n.(type) {
		case *ast.FuncDecl:
			decl[x.Name] = true
		case *ast.Field:
			for _, id := range x.Names {
				decl[id] = true
			}
		case *ast.TypeSpec:
			decl[x.Name] = true
		case *ast.ValueSpec:
			for _, id := range x.Names {
				decl[id] = true
			}
		case *ast.ImportSpec:
			if x.Name != nil {
				decl[x.Name] = true
			}
		case *ast.LabeledStmt:
			decl[x.Label] = true
		case *ast.AssignStmt:
			if x.Tok == token.DEFINE {
				for _, e := range x.Lhs {
					if id, ok := e.(*ast.Ident); ok {
						decl[id] = true
					}
				}
			}
		case *ast.RangeStmt:
			if x.Tok == token.DEFINE {
				for _, e := range []ast.Expr{x.Key, x.Value} {
					if id, ok := e.(*ast.Ident); ok {
						decl[id] = true
					}
				}
			}
		}
		return true
	})

	// the comments rule N1 keeps: directives (with their place among the nodes) and the cgo preamble
	for _, g := range f.Comments {
		for _, c := range g.List {
			if directive(c.Text) {
				k := 0
				for _, p := range starts {
					if p < c.Pos() {
						k++
					}
				}
				fmt.Printf("Directive at=%d %q\n", k, c.Text)
			}
		}
	}
	for _, g := range f.Comments {
		if preamble[g] {
			fmt.Printf("CgoPreamble %q\n", raw(g))
		}
	}

	depth := 0
	ast.Inspect(f, func(n ast.Node) bool {
		if n == nil {
			depth--
			return false
		}
		switch n.(type) {
		case *ast.CommentGroup, *ast.Comment:
			return false
		}
		v := reflect.ValueOf(n).Elem()
		t := v.Type()
		var b strings.Builder
		fmt.Fprintf(&b, "%d %s", depth, t.Name())
		_, isIdent := n.(*ast.Ident)
		for i := 0; i < v.NumField(); i++ {
			fv, ft := v.Field(i), t.Field(i)
			switch {
			case ft.Type == posType || ft.Type == cgType || ft.Type == objType || ft.Type == scopeType:
				continue
			case ft.Type == tokType || ft.Type == dirType:
				fmt.Fprintf(&b, " %s=%v", ft.Name, fv.Interface())
			case ft.Type.Kind() == reflect.String && isIdent:
				fmt.Fprintf(&b, " %s=%s", ft.Name, fv.String())
			case ft.Type.Kind() == reflect.String:
				fmt.Fprintf(&b, " %s=%q", ft.Name, fv.String())
			case ft.Type.Kind() == reflect.Bool:
				fmt.Fprintf(&b, " %s=%v", ft.Name, fv.Bool())
			case (ft.Type.Kind() == reflect.Interface || ft.Type.Kind() == reflect.Ptr) && ft.Type.Implements(nodeType):
				if fv.IsNil() {
					fmt.Fprintf(&b, " %s=nil", ft.Name)
				}
			}
		}
		if id, ok := n.(*ast.Ident); ok && decl[id] {
			b.WriteString(" Decl")
		}
		fmt.Println(b.String())
		depth++
		return true
	})
}
