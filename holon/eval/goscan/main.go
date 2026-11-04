// goscan: what holon's renaming tool (holon/eval/rename.py; I48 rules N1-N3) reads from Go source files.
//
// It is the tool's own reader, built at run time with the pinned go (holon/eval/golang.py) into ~/.holon/eval/bin,
// and shares no code with any other Go program of the repository. Standard library only (go/scanner, go/parser,
// go/ast, go/token, strconv).
//
// Usage: goscan facts FILE...   or   goscan tokens FILE...
//
// Each FILE gives one JSON line. When the file does not parse: {"path", "ok": false, "error"}. Otherwise:
//
//	facts:  {"path", "ok": true, "package", "idents": [[offset, name, declared]...] (every *ast.Ident, in source
//	        order; declared for the name of a func, method, var, const, type, struct field, interface method, type
//	        parameter, parameter, result or receiver, label or import alias, or a := or range := name),
//	        "literals": [[kind, value]...] (every STRING and CHAR basic literal, import paths and struct tags included;
//	        the value with each escape decoded to its code point, a raw string without its carriage returns),
//	        "comments": [[offset, end, text, kept]...] (every comment in file order: its byte span in the file, the
//	        scanner's text and whether rule N1 keeps it: a directive or a comment of the cgo preamble),
//	        "kept_texts": [...] (the texts of the directives and of the preamble, as the scanner reads them),
//	        "imports_c": bool, "cgo": [...] (when the file imports "C": every name X of a selector expression C.X)}
//	tokens: {"path", "ok": true, "tokens": [[token, literal]...], "preamble": text} the scanner's token stream with
//	        automatic semicolons; a comment appears only when it is kept, and an identifier's literal is its name.
//
// Exit status: 0 printed (a file that does not parse is reported in its line), 2 usage or an unreadable file.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/scanner"
	"go/token"
	"os"
	"strconv"
	"strings"
)

// isDirective: a comment rule N1 keeps verbatim wherever it stands.
func isDirective(text string) bool {
	for _, p := range []string{"//go:", "// +build", "//export ", "//line ", "/*line "} {
		if strings.HasPrefix(text, p) {
			return true
		}
	}
	return false
}

// preambleGroups: the comment groups cmd/cgo reads as the preamble: the doc comment of an import "C" spec, or else
// the doc comment of its import declaration when that declaration holds this one spec only.
func preambleGroups(f *ast.File) map[*ast.CommentGroup]bool {
	out := map[*ast.CommentGroup]bool{}
	for _, d := range f.Decls {
		gd, ok := d.(*ast.GenDecl)
		if !ok || gd.Tok != token.IMPORT {
			continue
		}
		for _, s := range gd.Specs {
			is, ok := s.(*ast.ImportSpec)
			if !ok || is.Path == nil || is.Path.Value != `"C"` {
				continue
			}
			switch {
			case is.Doc != nil:
				out[is.Doc] = true
			case gd.Doc != nil && len(gd.Specs) == 1:
				out[gd.Doc] = true
			}
		}
	}
	return out
}

// commentEnd: the end offset of the comment starting at off, read from the bytes: a line comment stops before its
// newline (and before a carriage return right in front of it, as the scanner does), a general comment after "*/".
func commentEnd(src []byte, off int) int {
	if src[off+1] == '/' {
		end := off
		for end < len(src) && src[end] != '\n' {
			end++
		}
		if end > off+2 && src[end-1] == '\r' {
			end--
		}
		return end
	}
	i := strings.Index(string(src[off+2:]), "*/")
	if i < 0 {
		return len(src)
	}
	return off + 2 + i + 2
}

// literalValue: a STRING or CHAR literal's value, each escape decoded to the code point it names (a \x or octal
// escape too), a raw string without carriage returns.
func literalValue(lit string) string {
	if strings.HasPrefix(lit, "`") {
		return strings.ReplaceAll(lit[1:len(lit)-1], "\r", "")
	}
	quote := lit[0]
	body := lit[1 : len(lit)-1]
	var b strings.Builder
	for len(body) > 0 {
		r, _, tail, err := strconv.UnquoteChar(body, quote)
		if err != nil {
			return body // unreachable for a literal the parser accepted
		}
		b.WriteRune(r)
		body = tail
	}
	return b.String()
}

type result map[string]any

func parse(path string, src []byte) (*token.FileSet, *ast.File, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, path, src, parser.ParseComments|parser.SkipObjectResolution)
	return fset, f, err
}

func facts(path string, src []byte) result {
	fset, f, err := parse(path, src)
	if err != nil {
		return result{"path": path, "ok": false, "error": err.Error()}
	}
	tf := fset.File(f.Pos())
	declared := map[*ast.Ident]bool{}
	var idents [][3]any
	var lits [][2]string
	cgo := []string{}
	importsC := false
	mark := func(ids ...*ast.Ident) {
		for _, id := range ids {
			if id != nil {
				declared[id] = true
			}
		}
	}
	// first pass: which identifiers declare a name
	ast.Inspect(f, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.FuncDecl:
			mark(x.Name)
		case *ast.Field:
			mark(x.Names...)
		case *ast.TypeSpec:
			mark(x.Name)
		case *ast.ValueSpec:
			mark(x.Names...)
		case *ast.ImportSpec:
			mark(x.Name)
			if v, err := strconv.Unquote(x.Path.Value); err == nil && v == "C" {
				importsC = true
			}
		case *ast.LabeledStmt:
			mark(x.Label)
		case *ast.AssignStmt:
			if x.Tok == token.DEFINE {
				for _, e := range x.Lhs {
					if id, ok := e.(*ast.Ident); ok {
						mark(id)
					}
				}
			}
		case *ast.RangeStmt:
			if x.Tok == token.DEFINE {
				for _, e := range []ast.Expr{x.Key, x.Value} {
					if id, ok := e.(*ast.Ident); ok {
						mark(id)
					}
				}
			}
		}
		return true
	})
	// second pass: every identifier, literal and C.X selector
	ast.Inspect(f, func(n ast.Node) bool {
		switch x := n.(type) {
		case *ast.CommentGroup, *ast.Comment:
			return false
		case *ast.Ident:
			idents = append(idents, [3]any{tf.Offset(x.NamePos), x.Name, declared[x]})
		case *ast.BasicLit:
			if x.Kind == token.STRING || x.Kind == token.CHAR {
				lits = append(lits, [2]string{x.Kind.String(), literalValue(x.Value)})
			}
		case *ast.SelectorExpr:
			if id, ok := x.X.(*ast.Ident); ok && id.Name == "C" && x.Sel != nil {
				cgo = append(cgo, x.Sel.Name)
			}
		}
		return true
	})
	if !importsC {
		cgo = []string{}
	}
	pre := preambleGroups(f)
	comments := [][4]any{}
	kept := []string{}
	for _, g := range f.Comments {
		for _, c := range g.List {
			off := tf.Offset(c.Slash)
			k := isDirective(c.Text) || pre[g]
			comments = append(comments, [4]any{off, commentEnd(src, off), c.Text, k})
			if isDirective(c.Text) {
				kept = append(kept, c.Text)
			}
		}
	}
	for _, g := range f.Comments {
		if pre[g] {
			var xs []string
			for _, c := range g.List {
				xs = append(xs, c.Text)
			}
			kept = append(kept, strings.Join(xs, "\n"))
		}
	}
	if idents == nil {
		idents = [][3]any{}
	}
	if lits == nil {
		lits = [][2]string{}
	}
	return result{"path": path, "ok": true, "package": f.Name.Name, "idents": idents, "literals": lits,
		"comments": comments, "kept_texts": kept, "imports_c": importsC, "cgo": cgo}
}

func tokens(path string, src []byte) result {
	fset, f, err := parse(path, src)
	if err != nil {
		return result{"path": path, "ok": false, "error": err.Error()}
	}
	pre := preambleGroups(f)
	keptAt := map[int]bool{}
	var preamble []string
	tf := fset.File(f.Pos())
	for _, g := range f.Comments {
		for _, c := range g.List {
			if isDirective(c.Text) || pre[g] {
				keptAt[tf.Offset(c.Slash)] = true
			}
			if pre[g] {
				preamble = append(preamble, c.Text)
			}
		}
	}
	var s scanner.Scanner
	sf := token.NewFileSet().AddFile(path, -1, len(src))
	var serr error
	s.Init(sf, src, func(pos token.Position, msg string) { serr = fmt.Errorf("%s: %s", pos, msg) }, scanner.ScanComments)
	toks := [][2]string{}
	for {
		pos, tok, lit := s.Scan()
		if tok == token.EOF {
			break
		}
		switch {
		case tok == token.COMMENT:
			if keptAt[sf.Offset(pos)] {
				toks = append(toks, [2]string{"COMMENT", lit})
			}
		case tok == token.IDENT || tok.IsLiteral():
			toks = append(toks, [2]string{tok.String(), lit})
		case tok == token.SEMICOLON:
			toks = append(toks, [2]string{";", lit})
		default:
			toks = append(toks, [2]string{tok.String(), ""})
		}
	}
	if serr != nil {
		return result{"path": path, "ok": false, "error": serr.Error()}
	}
	return result{"path": path, "ok": true, "tokens": toks, "preamble": strings.Join(preamble, "\n")}
}

func main() {
	if len(os.Args) < 2 || (os.Args[1] != "facts" && os.Args[1] != "tokens") {
		fmt.Fprintln(os.Stderr, "usage: goscan facts|tokens FILE...")
		os.Exit(2)
	}
	w := bufio.NewWriter(os.Stdout)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	for _, path := range os.Args[2:] {
		src, err := os.ReadFile(path)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		var r result
		if os.Args[1] == "facts" {
			r = facts(path, src)
		} else {
			r = tokens(path, src)
		}
		if err := enc.Encode(r); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	}
	if err := w.Flush(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}
