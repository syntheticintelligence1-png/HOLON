import sys, json
sys.path.insert(0, ".")
from holon.frontends.go.ssaload import Program
from holon.frontends.go.ctx import Ctx
from holon.frontends.go.paths import Enumerator
dump = json.load(open("/tmp/claude-0/-home-user-HOLON/13f9caff-002b-57ac-9895-57449b3592cb/scratchpad/i67/dump.json"))
prog = Program(dump)
ctx = Ctx(prog, {"primitives": {}, "limits": {"max_paths": 512, "inline_depth": 4, "flow_depth": 3}})
fid = "morph-l2/common/batch.RetrieveBlobBytes"
fn = prog.funcs[fid]
from holon.frontends.go.flow import Flow
fl = Flow(ctx, fn)
loops = fl.loops()
print("loops:", [(L.header, L.kind, L.iv, L.init, L.cmp, L.limit, L.fuel, "in", L.in_succ, "exit", L.exit_succ) for L in loops])
L = loops[0]
en = Enumerator(ctx, {fid: fl}, fn)
res = en.run_loop(L)
print("=== body paths:", len(res.paths))
for p in res.paths:
    print(" end=%s site=%s" % (p["end"], p.get("site")))
    for a in p["cond"]:
        print("     cond:", json.dumps(a))
