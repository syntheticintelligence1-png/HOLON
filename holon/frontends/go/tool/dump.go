package main

import (
	"fmt"
	"go/constant"
	"go/types"
	"runtime"
	"strings"

	"golang.org/x/tools/go/ssa"
)

func goVer() string { return runtime.Version() }

// dumpFunc renders one SSA function into the normalized IR.
//
// Value ids are integers assigned on first encounter (params first, then
// instruction order). ref() on a not-yet-emitted value emits an "undef"
// placeholder that is overwritten when the defining instruction is reached;
// every SSA value is produced exactly once so all placeholders resolve.
func dumpFunc(prog *ssa.Program, f *ssa.Function, root string) Func {
	fset := prog.Fset
	pos := fset.Position(f.Pos())
	end := pos
	if f.Syntax() != nil {
		end = fset.Position(f.Syntax().End())
	}
	file := relFile(root, pos.Filename)
	out := Func{
		ID:        fnID(f),
		Name:      f.Name(),
		Signature: f.Signature.String(),
		File:      file,
		Line:      pos.Line,
		EndLine:   end.Line,
		Exported:  f.Object() != nil && f.Object().Exported(),
	}
	if f.Pkg != nil {
		out.Pkg = f.Pkg.Pkg.Path()
	}
	if f.Signature.Recv() != nil {
		rt := f.Signature.Recv().Type()
		_, isPtr := rt.(*types.Pointer)
		name := ""
		if len(f.Params) > 0 && f.Params[0].Object() != nil {
			name = f.Params[0].Object().Name()
		}
		out.Recv = &Recv{Name: name, Type: rt.String(), Ptr: isPtr}
	}
	if f.Parent() != nil {
		out.Anonymous = true
	}
	for _, fv := range f.FreeVars {
		out.FreeVars = append(out.FreeVars, fv.Name())
	}

	ids := map[ssa.Value]int{}
	var instrs []Instr
	getID := func(v ssa.Value) int {
		if id, ok := ids[v]; ok {
			return id
		}
		id := len(instrs)
		ids[v] = id
		t := "unknown"
		if v != nil && v.Type() != nil {
			t = v.Type().String()
		}
		instrs = append(instrs, Instr{ID: id, Op: "undef", Type: t})
		return id
	}

	// parameters and free variables first: stable low ids
	for i, p := range f.Params {
		id := getID(p)
		in := &instrs[id]
		in.Op = "param"
		in.Index = i
		if p.Object() != nil {
			in.Name = p.Object().Name()
		}
	}
	for i, p := range f.FreeVars {
		id := getID(p)
		in := &instrs[id]
		in.Op = "freevar"
		in.Name = p.Name()
		in.Index = i
	}

	ref := func(v ssa.Value) int {
		if v == nil {
			return -1
		}
		switch c := v.(type) {
		case *ssa.Const:
			id := getID(c)
			instrs[id] = constInstr(id, c)
		case *ssa.Global:
			id := getID(c)
			instrs[id] = Instr{ID: id, Op: "global", Name: c.Name(), Type: c.Type().String()}
		case *ssa.Function:
			id := getID(c)
			instrs[id] = Instr{ID: id, Op: "fnref", Fn: canonicalCallee(fnID(c)), Type: c.Type().String()}
		case *ssa.Builtin:
			id := getID(c)
			instrs[id] = Instr{ID: id, Op: "builtin", Name: c.Name(), Type: c.Type().String()}
		default:
			return getID(v)
		}
		return ids[v]
	}
	refs := func(vs ...ssa.Value) []int {
		var out []int
		for _, v := range vs {
			out = append(out, ref(v))
		}
		return out
	}
	line := func(i ssa.Instruction) *int {
		p := fset.Position(i.Pos())
		if !p.IsValid() {
			return nil
		}
		l := p.Line
		return &l
	}

	var blocks []Block
	inCycle := cycleBlocks(f)
	for _, b := range f.Blocks {
		bl := Block{ID: b.Index, Comment: b.Comment, Loop: inCycle[b.Index]}
		for _, ins := range b.Instrs {
			var in Instr
			var val ssa.Value
			if v, ok := ins.(ssa.Value); ok {
				val = v
			}
			switch i := ins.(type) {
			case *ssa.Alloc:
				in = Instr{Op: "alloc"}
				if i.Heap {
					in.Name = "heap"
				}
			case *ssa.MakeSlice:
				in = Instr{Op: "makeslice", Args: refs(i.Len, i.Cap)}
			case *ssa.MakeMap:
				in = Instr{Op: "makemap", Args: refs(i.Reserve)}
			case *ssa.MakeChan:
				in = Instr{Op: "makechan"}
			case *ssa.MakeInterface:
				in = Instr{Op: "makeiface", Args: refs(i.X)}
			case *ssa.MakeClosure:
				if cf, ok := i.Fn.(*ssa.Function); ok {
					in = Instr{Op: "closure", Fn: canonicalCallee(fnID(cf)), Args: refs(i.Bindings...)}
				} else {
					in = Instr{Op: "closure", Args: refs(i.Bindings...)}
				}
			case *ssa.Slice:
				var lo, hi, mx = -1, -1, -1
				if i.Low != nil {
					lo = ref(i.Low)
				}
				if i.High != nil {
					hi = ref(i.High)
				}
				if i.Max != nil {
					mx = ref(i.Max)
				}
				in = Instr{Op: "slice", Args: append(refs(i.X), lo, hi, mx)}
			case *ssa.IndexAddr:
				in = Instr{Op: "indexaddr", Args: refs(i.X, i.Index)}
			case *ssa.Index:
				in = Instr{Op: "index", Args: refs(i.X, i.Index)}
			case *ssa.FieldAddr:
				in = Instr{Op: "fieldaddr", Name: fieldName(i.X.Type(), i.Field), Args: refs(i.X)}
			case *ssa.Field:
				in = Instr{Op: "field", Name: fieldName(i.X.Type(), i.Field), Args: refs(i.X)}
			case *ssa.Lookup:
				in = Instr{Op: "lookup", Args: refs(i.X, i.Index)}
			case *ssa.BinOp:
				in = Instr{Op: "binop", Name: i.Op.String(), Args: refs(i.X, i.Y)}
			case *ssa.UnOp:
				in = Instr{Op: "unop", Name: i.Op.String(), Args: refs(i.X)}
			case *ssa.ChangeType:
				in = Instr{Op: "changetype", Args: refs(i.X)}
			case *ssa.Convert:
				in = Instr{Op: "convert", Args: refs(i.X)}
			case *ssa.ChangeInterface:
				in = Instr{Op: "changeiface", Args: refs(i.X)}
			case *ssa.TypeAssert:
				in = Instr{Op: "typeassert", Args: refs(i.X)}
			case *ssa.Extract:
				in = Instr{Op: "extract", Args: refs(i.Tuple), Index: i.Index}
			case *ssa.Call:
				in = Instr{Op: "call", Fn: canonicalCallee(calleeID(&i.Call)), Args: refs(i.Call.Args...)}
			case *ssa.Store:
				in = Instr{Op: "store", Args: refs(i.Addr, i.Val)}
			case *ssa.MapUpdate:
				in = Instr{Op: "mapupdate", Args: refs(i.Map, i.Key, i.Value)}
			case *ssa.Phi:
				var edges [][]int
				for k, e := range i.Edges {
					edges = append(edges, []int{b.Preds[k].Index, ref(e)})
				}
				in = Instr{Op: "phi", Edges: edges}
			case *ssa.If:
				in = Instr{Op: "if", Cond: ref(i.Cond)}
			case *ssa.Jump:
				in = Instr{Op: "jump"}
			case *ssa.Return:
				in = Instr{Op: "return", Args: refs(i.Results...)}
			case *ssa.Panic:
				in = Instr{Op: "panic", Args: refs(i.X)}
			case *ssa.Go:
				in = Instr{Op: "go", Fn: canonicalCallee(calleeID(&i.Call)), Args: refs(i.Call.Args...)}
			case *ssa.Defer:
				in = Instr{Op: "defer", Fn: canonicalCallee(calleeID(&i.Call)), Args: refs(i.Call.Args...)}
			case *ssa.Send:
				in = Instr{Op: "send", Args: refs(i.Chan, i.X)}
			case *ssa.RunDefers:
				in = Instr{Op: "rundefers"}
			case *ssa.Select:
				in = Instr{Op: "select"}
			case *ssa.Range:
				in = Instr{Op: "range", Args: refs(i.X)}
			case *ssa.Next:
				in = Instr{Op: "next", Args: refs(i.Iter)}
			case *ssa.DebugRef:
				name := ""
				_, isVar := i.Object().(*types.Var)
				if i.Object() != nil {
					name = i.Object().Name()
				}
				out.DebugRefs = append(out.DebugRefs, DebugRef{
					Value: ref(i.X), Name: name, Expr: types.ExprString(i.Expr),
					IsAddr: i.IsAddr, IsVar: isVar, Line: fset.Position(i.Pos()).Line,
				})
				continue
			default:
				in = Instr{Op: "unknown", Name: fmt.Sprintf("%T", ins)}
			}
			var id int
			if val != nil {
				id = getID(val)
			} else {
				id = len(instrs)
				instrs = append(instrs, Instr{ID: id, Op: "void"})
			}
			in.ID = id
			in.Block = b.Index
			in.Line = line(ins)
			if in.Type == "" && val != nil && val.Type() != nil {
				in.Type = val.Type().String()
			}
			instrs[id] = in
			bl.Instrs = append(bl.Instrs, id)
		}
		bl.Succs = succEdges(b)
		blocks = append(blocks, bl)
	}
	out.Blocks = blocks
	out.Instrs = instrs
	return out
}

func constInstr(id int, c *ssa.Const) Instr {
	in := Instr{ID: id, Op: "const", Type: c.Type().String()}
	v := c.Value
	if v == nil {
		in.Value = nil
		in.Name = "nil"
		return in
	}
	switch v.Kind() {
	case constant.Int:
		if x, ok := constant.Int64Val(v); ok {
			in.Value = x
		} else {
			in.Value = v.String()
		}
	case constant.Bool:
		in.Value = constant.BoolVal(v)
	case constant.String:
		in.Value = constant.StringVal(v)
	case constant.Float:
		f, _ := constant.Float64Val(v)
		in.Value = f
	default:
		in.Value = v.String()
	}
	return in
}

// cycleBlocks marks blocks that lie on a back edge (loop bodies), using DFS
// over the CFG with a grey/black stack.
func cycleBlocks(f *ssa.Function) map[int]bool {
	onstack := map[int]bool{}
	done := map[int]bool{}
	cycle := map[int]bool{}
	var visit func(b *ssa.BasicBlock)
	visit = func(b *ssa.BasicBlock) {
		if done[b.Index] {
			return
		}
		onstack[b.Index] = true
		for _, s := range b.Succs {
			if onstack[s.Index] {
				cycle[s.Index] = true
				cycle[b.Index] = true
				continue
			}
			if !done[s.Index] {
				visit(s)
			}
		}
		onstack[b.Index] = false
		done[b.Index] = true
	}
	if len(f.Blocks) > 0 {
		visit(f.Blocks[0])
	}
	return cycle
}

func succEdges(b *ssa.BasicBlock) []Edge {
	var out []Edge
	last := b.Instrs[len(b.Instrs)-1]
	switch last.(type) {
	case *ssa.If:
		out = append(out, Edge{To: b.Succs[0].Index, Tag: "then"}, Edge{To: b.Succs[1].Index, Tag: "else"})
	default:
		for _, s := range b.Succs {
			out = append(out, Edge{To: s.Index, Tag: "next"})
		}
	}
	return out
}

// relFile relativizes a filename to the checkout root when possible.
func relFile(root, p string) string {
	root = strings.TrimSuffix(root, "/")
	if strings.HasPrefix(p, root+"/") {
		return strings.TrimPrefix(p, root+"/")
	}
	return p
}
