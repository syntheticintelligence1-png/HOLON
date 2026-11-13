"""I122 (M6, generality): goloop's loop shapes. Contract tests (spec/M6/predictions/I122.json;
prompts/I122_goloop_loop_shapes.md; HUMAN_ANSWERS Q93 (3), Q98 (2), Q90).

The wall I117 measured: goloop's I67 class takes one counted loop of step 1 from a constant to a constant over a byte
array, so four of one corpus entry's seven Go ops (and 13 corpus Go ops in all, I116's count) have a loop the Go frontend emits no
loop body for and goloop cannot model; their laws are unbound and UNKNOWN. This key adds two classes, each defined from
the Go specification and tried only after the I67 class refuses an op, behind the frontend's opt-in loops "shapes"
(protocol go.loops "shapes", with ops "typed"):

  S1 (range): one for-range loop over a slice X the carrier holds (the op's parameter or a field path from it), of an
      integer element type of at most 32 bits. The range expression is evaluated once, so the trip count is len(X),
      read from the carrier; iteration i reads X[i]. The carrier value is X's element sequence, of any length (a
      signed element in offset binary, value + 2**(n-1), which keeps the signed order).
  S2 (stride): one counted loop with a constant step other than 0 and 1 (either sign) over a fixed-length byte array,
      the induction variable of a recorded integer type T. The post statement wraps in T ("Integer overflow"), so the
      trip sequence is iv_0 = init, iv_(k+1) = fit(iv_k + s, T) while cmp(iv_k, limit) holds in T's order, computed
      concretely (at most 4096 iterations, every index in range, no byte read twice). Iteration k reads p[a*iv_k + c].

Anything else stays Unsupported, its laws unbound and UNKNOWN. The planted fixture tests_m6/fixtures/i122 is a Go
package written for these tests from the specification's rules: the expectations are known by construction (its doc
comment). Every planted op in a class is compared with the pinned go 1.24.7 by running the real function (Q90's
differential method). The corpus smoke measures are results/M6/I122/holon/corpus.json (holon eval holon --protocol
spec/M6/lib/i122_run.json --compose) and results/M6/I122/loop_shapes.json (model-generation counts, before any
decision: Q72).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i122"
GOSRC = FIX / "src"
PROTO = "spec/M6/lib/i122_run.json"
OUT = ROOT / "results" / "M6" / "I122"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SHAPES = OUT / "loop_shapes.json"
SEALED = OUT / "sealed.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
GO_VERSION = "go version go1.24.7 linux/amd64"   # the pinned go on PATH (config/toolchains.json go_set)
PKG = "example.com/holon/i122/shapes"
FN = {"shapes_Frame_Scan": f"(*{PKG}.Frame).Scan", "shapes_Frame_Tail": f"(*{PKG}.Frame).Tail",
      "shapes_Frame_Wide": f"(*{PKG}.Frame).Wide", "shapes_Signed": f"{PKG}.Signed", "shapes_Back": f"{PKG}.Back",
      "shapes_WrapScan": f"{PKG}.WrapScan", "shapes_Down": f"{PKG}.Down", "shapes_Pair": f"{PKG}.Pair"}
S1_OPS = ("shapes_Frame_Scan", "shapes_Frame_Tail", "shapes_Signed")
S2_OPS = ("shapes_Back", "shapes_WrapScan", "shapes_Down")
OUTSIDE = ("shapes_Frame_Wide", "shapes_Pair")
TRIPS = {"shapes_Back": [7, 5, 3, 1], "shapes_WrapScan": [250, 254, 2],
         "shapes_Down": [30, 27, 24, 21, 18, 15, 12, 9, 6, 3]}
HEADERS = {"shapes_Back": "for i := 7; i >= 0; i -= 2", "shapes_WrapScan": "for i := uint8(250); i != 6; i += 4",
           "shapes_Down": "for i := 30; i > 0; i -= 3"}   # the fixture's loop headers, run as Go (P3's trip check)
FALSE_LAWS = {"L_par_tot_shapes_WrapScan": "shapes_WrapScan", "L_par_tot_shapes_Back": "shapes_Back",
              "L_par_tot_shapes_Frame_Scan": "shapes_Frame_Scan", "L_par_tot_shapes_Signed": "shapes_Signed"}
TRUE_LAWS = ("L_par_tot_shapes_Frame_Tail", "L_par_tot_shapes_Down")


def pred(pid: str) -> dict:
    return next(p for p in json.loads((ROOT / "spec/M6/predictions/I122.json").read_text(encoding="utf-8"))
                ["predictions"] if p["id"] == pid)


def protocol(name: str = PROTO) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def go_bin() -> str:
    g = shutil.which("go")
    assert g, "no go on PATH"
    v = subprocess.run([g, "version"], capture_output=True, text=True).stdout.strip()
    assert v == GO_VERSION, v
    return g


def go_env() -> dict:
    return {**os.environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"}


def config(loops: bool = True) -> dict:
    cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
    if not loops:
        cfg.pop("loops")
    return cfg


def extract(cfg: dict, tmp: Path, ok: bool = True):
    tmp.mkdir(parents=True)
    cp = tmp / "cfg.json"
    cp.write_text(json.dumps(cfg))
    out = tmp / "out"
    out.mkdir()
    p = subprocess.run([sys.executable, "-m", "holon", "extract", "go", "--root", str(ROOT), "--config", str(cp),
                        "--src", str(GOSRC), "--out-dir", str(out)], cwd=ROOT, env=ENV, capture_output=True,
                       text=True, timeout=600)
    if not ok:
        return p
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    (f,) = sorted(out.glob("*.extracted.json"))
    return json.loads(f.read_text(encoding="utf-8"))


def op_doc(functions: dict) -> dict:
    """The planted functions as the ops of a Go-op document (holon.gen.goloop reads doc["ops"] alone)."""
    return {"component": "shapes_ops", "carrier": {"id": "Carrier"},
            "ops": {name: functions[fid] for name, fid in FN.items()}}


_CACHE: dict = {}


def planted_doc() -> dict:
    if "doc" not in _CACHE:
        t = Path(tempfile.mkdtemp(prefix="holon-i122-doc-"))
        try:
            _CACHE["doc"] = op_doc(extract(config(), t / "x")["go"]["functions"])
        finally:
            shutil.rmtree(t, ignore_errors=True)
    return _CACHE["doc"]


# ----------------------------------------------------------------------------------------------- the frontend
class TestFrontend(unittest.TestCase):
    """P1 (frontend half): loops "shapes" emits loop bodies for the new forms; without it nothing changes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i122-fe-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_p1_loop_bodies_under_the_opt_in(self):
        fs = extract(config(), self.tmp / "on")["go"]["functions"]
        want = {"shapes_Frame_Scan": ["len", ["field", ["param", "f"], "Data"]],
                "shapes_Frame_Tail": ["len", ["field", ["param", "f"], "Data"]],
                "shapes_Frame_Wide": ["len", ["field", ["param", "f"], "Words"]],
                "shapes_Signed": ["len", ["param", "s"]]}
        for name, lim in want.items():
            (lb,) = fs[FN[name]]["loop_bodies"]
            self.assertEqual((lb["init"], lb["step"], lb["cmp"], lb["limit"]), (["const", 0], 1, "<", lim), name)
            self.assertIsNotNone(lb["paths"], name)
            self.assertIn("terms", lb["typed"])
            self.assertIn("iv_type", lb["typed"])
        for name, (init, step, cmp) in {"shapes_Back": (7, -2, ">="), "shapes_WrapScan": (250, 4, "!="),
                                        "shapes_Down": (30, -3, ">"), "shapes_Pair": (0, 2, "<")}.items():
            (lb,) = fs[FN[name]]["loop_bodies"]
            self.assertEqual((lb["init"], lb["step"], lb["cmp"]), (["const", init], step, cmp), name)
            self.assertIsNotNone(lb["paths"], name)
        self.assertEqual(fs[FN["shapes_WrapScan"]]["loop_bodies"][0]["typed"]["iv_type"], "uint8")

    def test_p1_without_the_opt_in_nothing_changes(self):
        on = extract(config(), self.tmp / "on")
        off = extract(config(loops=False), self.tmp / "off")
        for fid, f in off["go"]["functions"].items():
            self.assertNotIn("loop_bodies", f, fid)
            g = dict(on["go"]["functions"][fid])
            g.pop("loop_bodies", None)
            self.assertEqual(g, f, fid)
        for k in on["go"]:
            if k != "functions":
                self.assertEqual(on["go"][k], off["go"][k], k)

    def test_p1_loops_value_checked(self):
        p = extract(dict(config(), loops="nested"), self.tmp / "bad", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("loops must be", p.stdout + p.stderr)
        cfg = config()
        cfg.pop("ops")
        p = extract(cfg, self.tmp / "bad2", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("loops", p.stdout + p.stderr)


# ----------------------------------------------------------------------------------------------- the classes
class TestClasses(unittest.TestCase):
    """P1 (class half), P2: which planted op is in which class, and the S2 trip sequences."""

    @classmethod
    def setUpClass(cls):
        from holon.gen import goloop
        cls.shs = goloop.shapes(planted_doc())

    def test_p1_s1_shapes(self):
        from holon.gen import goloop, goshapes
        for name in S1_OPS:
            sh = self.shs[name]
            self.assertIsInstance(sh, goshapes.RangeShape, f"{name}: {sh}")
            self.assertEqual(sh.kind, "S1")
        self.assertEqual(self.shs["shapes_Frame_Scan"].cell_map(), self.shs["shapes_Frame_Tail"].cell_map())
        bad = self.shs["shapes_Frame_Wide"]
        self.assertIsInstance(bad, goloop.Unsupported)
        self.assertIn("64", str(bad))

    def test_p2_s2_shapes(self):
        from holon.gen import goloop, goshapes
        for name, trip in TRIPS.items():
            sh = self.shs[name]
            self.assertIsInstance(sh, goshapes.StrideShape, f"{name}: {sh}")
            self.assertEqual(sh.kind, "S2")
            self.assertEqual(sh.trip, trip, name)
        self.assertEqual(self.shs["shapes_WrapScan"].cell_map(), ("idx", (250, 254, 2)))
        bad = self.shs["shapes_Pair"]
        self.assertIsInstance(bad, goloop.Unsupported)
        self.assertIn("two cells", str(bad))


# ----------------------------------------------------------------------------------------------- the differential test
DIFF_MAIN = '''package main

import (
\t"fmt"

\tshapes "example.com/holon/i122/shapes"
)

func out(f func() error) (s string) {
\tdefer func() {
\t\tif r := recover(); r != nil {
\t\t\ts = "OPanic"
\t\t}
\t}()
\tif f() != nil {
\t\treturn "OErr"
\t}
\treturn "ORet"
}

func blob(kv ...int) *shapes.Blob {
\tb := new(shapes.Blob)
\tfor j := 0; j+1 < len(kv); j += 2 {
\t\tb[kv[j]] = byte(kv[j+1])
\t}
\treturn b
}

func main() {
%s
}
'''

U8_EDGES = (0, 1, 254, 255)
I8_EDGES = (-128, -127, -101, -100, -1, 0, 1, 127)
BYTE_SET = (0, 1, 0x7f, 0x80, 0xff)


def run_go_main(body: str, tmp: Path) -> list[str]:
    w = tmp / "go"
    if w.exists():
        shutil.rmtree(w)
    shutil.copytree(GOSRC, w)
    (w / "cmd").mkdir()
    (w / "cmd" / "main.go").write_text(DIFF_MAIN % body)
    p = subprocess.run([go_bin(), "run", "./cmd"], cwd=w, capture_output=True, text=True, timeout=1200,
                       env=go_env())
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.split("\n")[:-1]


def s1_cases(elems) -> list[list[int]]:
    out = []
    for n in range(4):
        out += [list(c) for c in itertools.product(elems, repeat=n)]
    return out


def s2_cases(m: int) -> list[dict]:
    """Assignments of BYTE_SET values to at most two of the m iterations' cells (the others 0)."""
    out = [{}]
    for k in range(m):
        out += [{k: v} for v in BYTE_SET if v]
    for j, k in itertools.combinations(range(m), 2):
        out += [{j: u, k: v} for u in BYTE_SET for v in BYTE_SET if u and v]
    return out


class TestDifferential(unittest.TestCase):
    """P3: every planted op in S1 or S2, compiled Bend model = real Go (the pinned toolchain) on every edge input; the
    S2 trip sequences equal the headers' own, run as Go."""

    @classmethod
    def setUpClass(cls):
        from holon.gen import goloop
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i122-diff-"))
        doc = planted_doc()
        sha = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        cls.cm = goloop.CompiledModel.build(doc, sha, "shapes_ops")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cases(self) -> list:
        """(op, model cells, Go call) for every input P3's claim enumerates."""
        cases = []
        for name in S1_OPS:
            sh = self.cm.shapes[name]
            signed = name == "shapes_Signed"
            for xs in s1_cases(I8_EDGES if signed else U8_EDGES):
                lit = ", ".join(str(x) for x in xs)
                call = (f"func() error {{ return shapes.Signed(shapes.Sig{{{lit}}}) }}" if signed else
                        f"func() error {{ return (&shapes.Frame{{Data: []uint8{{{lit}}}}}).{name.split('_')[-1]}() }}")
                cases.append((name, sh.encode(xs), call))
        for name in S2_OPS:
            sh = self.cm.shapes[name]
            _, idx = sh.cell_map()
            for asg in s2_cases(len(idx)):
                cells = [asg.get(k, 0) for k in range(len(idx))]
                kv = ", ".join(f"{idx[k]}, {v}" for k, v in sorted(asg.items()))
                cases.append((name, cells, f"func() error {{ return shapes.{name.split('_', 1)[1]}(blob({kv})) }}"))
        return cases

    def test_p3_case_count(self):
        # amended (spec/M6/amendments/I122.jsonl): split from test_p3_model_equals_go, unchanged; P3's recorded miss
        self.assertGreaterEqual(len(self.cases()), pred("I122-P3")["expected"]["cases_at_least"])

    def test_p3_model_equals_go(self):
        # amended (spec/M6/amendments/I122.jsonl): the count assertion is test_p3_case_count
        from holon.gen import goshapes
        cases = self.cases()
        got = run_go_main("\n".join(f"\tfmt.Println(out({c}))" for _, _, c in cases), self.tmp)
        model = self.cm.calls([{"fn": o, "args": [{"val": list(cells)}]} for o, cells, _ in cases])
        mirror = [goshapes.evaluate(self.cm.shapes[o], cells) for o, cells, _ in cases]
        bad = [(o, cells, g, m.get("$") if isinstance(m, dict) else m, e)
               for (o, cells, _), g, m, e in zip(cases, got, model, mirror)
               if not (isinstance(m, dict) and g == m.get("$") == e)]
        self.assertEqual(bad[:10], [])

    def test_p3_trip_sequences_equal_go(self):
        body = "\n".join(f'\tfmt.Println("{n}")\n\t{h} {{\n\t\tfmt.Println(i)\n\t}}' for n, h in HEADERS.items())
        got = run_go_main(body, self.tmp)
        seqs, cur = {}, None
        for line in got:
            if line in HEADERS:
                cur = line
                seqs[cur] = []
            else:
                seqs[cur].append(int(line))
        for name in HEADERS:
            self.assertEqual(seqs[name], self.cm.shapes[name].trip, name)
            self.assertEqual(seqs[name], TRIPS[name], name)


# ----------------------------------------------------------------------------------------------- the planted run
class _Planted(unittest.TestCase):
    """The composed route's Go part, route C and typed part over the planted package, in a scratch root, under the
    I122 protocol (as tests_m6/test_i117_go_op_semantics.py's _Planted does under I117's)."""
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i122-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self):
        if "run" not in _Planted.runs:
            from holon.eval import holon_run as H
            t = self.tmp / "run"
            t.mkdir()
            proto = protocol()
            S = H.scratch_root(ROOT, t, "holon/i122", GOSRC)
            rel = "results/eval/holon/i122"
            (S / rel / "sidecars").mkdir(parents=True)
            (S / rel / "facts").mkdir(parents=True)
            R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
            M = proto["milestone"]
            cfg = config()
            cfg["source"] = {"path": "<given by --src>"}
            cp = S / rel / "sidecars" / "shapes.json"
            cp.write_text(H.dumps(cfg))
            st: dict = {}
            st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                                str(GOSRC), "--out-dir", str(S / rel / "facts")])
            assert st["extract"]["status"] == "ok", st["extract"]["detail"][-2000:]
            ms = H.go_machines(R, S, rel, proto, {"id": "i122"},
                               {"stem": "shapes", "unit": cfg["documents"]["shapes"][0]}, cfg, GOSRC, t)
            files = sorted(p.name for p in (S / rel / "facts").glob("*.extracted.json"))
            st["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents",
                                            ",".join(f"{rel}/facts/{f}" for f in files), "--out-dir",
                                            str(S / rel / "sidecars" / "roles"), "--mode", "static", "--install",
                                            "--roles", "hand"])
            lib = S / "spec" / M / "lib"
            H._rules(R, S, rel, M, proto, [{"file": f} for m in ms for f in m["files"]], st,
                     lambda: H._route_c(R, S, M, lib, st))
            _Planted.runs["run"] = (st, S, M)
        return _Planted.runs["run"]

    def recs(self) -> dict:
        _st, S, M = self.run_of()
        return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((S / "results" / M).glob("L*.json"))}

    def model_text(self) -> str:
        _st, S, M = self.run_of()
        return "\n".join(p.read_text(encoding="utf-8") for p in sorted((S / "gen" / M / "model").glob("*.bend")))


def go_call(op: str, sh, w) -> str:
    """The fixture op at a record's witness value (holon.gen.goshapes' witness form), as a Go func() error."""
    name = op[len("shapes_"):]
    if name.startswith("Frame_"):
        (xs,) = w.values()
        return f"func() error {{ return (&shapes.Frame{{Data: []uint8{{{', '.join(map(str, xs))}}}}}).{name[6:]}() }}"
    if name == "Signed":
        return f"func() error {{ return shapes.Signed(shapes.Sig{{{', '.join(map(str, w))}}}) }}"
    cells = list(bytes.fromhex(w[2:]))
    _, idx = sh.cell_map()
    kv = ", ".join(f"{idx[k]}, {v}" for k, v in enumerate(cells) if v)
    return f"func() error {{ return shapes.{name}(blob({kv})) }}"


class TestPlanted(_Planted):
    def test_p4_false_laws_refuted_and_replayed(self):
        """The planted false laws are never PROVED; each is REFUTED at its witness, and every REFUTED record's witness,
        run as real Go, gives the outcomes the model's difference says."""
        from holon.gen import goloop
        rs = self.recs()
        for lid in FALSE_LAWS:
            self.assertEqual(rs[lid]["status"], "REFUTED", lid)
        shs = goloop.shapes(planted_doc())
        wrap = list(bytes.fromhex(next(iter(rs["L_par_tot_shapes_WrapScan"]["witness"].values()))[2:]))
        self.assertEqual(dict(zip(shs["shapes_WrapScan"].cell_map()[1], wrap)), {250: 0, 254: 0, 2: 0x7f})
        back = list(bytes.fromhex(next(iter(rs["L_par_tot_shapes_Back"]["witness"].values()))[2:]))
        self.assertEqual({i: v for i, v in zip(shs["shapes_Back"].cell_map()[1], back) if v}, {3: 0x80})
        self.assertEqual(next(iter(rs["L_par_tot_shapes_Frame_Scan"]["witness"].values())), {"Data": [255]})
        # amended (spec/M6/amendments/I122.jsonl): Signed's stated witness is test_p4_signed_witness
        calls, want = [], []
        _st, S, M = self.run_of()
        for lid, r in sorted(rs.items()):
            if r["status"] != "REFUTED" or not lid.startswith("L_par_"):
                continue
            law = json.loads((S / "laws" / M / f"{lid}.json").read_text(encoding="utf-8"))
            (b,) = [x["name"] for x in law["statement"]["binders"]]
            for side, val in zip(law["statement"]["claim"]["eq"], (r["difference"]["lhs"], r["difference"]["rhs"])):
                if "call" not in side:
                    continue
                f = side["call"]
                op = f[3:] if f.startswith("ok_") else f
                calls.append(go_call(op, shs[op], r["witness"][b]))
                want.append((f.startswith("ok_"), val))
        self.assertGreaterEqual(len(calls), pred("I122-P4")["expected"]["replayed_sides_at_least"])
        got = run_go_main("\n".join(f"\tfmt.Println(out({c}))" for c in calls), self.tmp)
        self.assertEqual(len(got), len(calls))
        for (is_ok, val), g in zip(want, got):
            self.assertEqual((g != "OPanic") if is_ok else g, val)

    def test_p4_signed_witness(self):
        # amended (spec/M6/amendments/I122.jsonl): split from test_p4_false_laws_refuted_and_replayed, unchanged;
        # P4's recorded miss
        rs = self.recs()
        self.assertEqual(next(iter(rs["L_par_tot_shapes_Signed"]["witness"].values())), [-101])

    def test_p5_true_laws_never_refuted(self):
        rs = self.recs()
        for lid in TRUE_LAWS:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
        self.assertEqual([lid for lid, r in rs.items() if "_par_" in lid and r["status"] == "PROVED"], [])

    def test_p6_outside_unbound(self):
        rs = self.recs()
        named = [lid for lid in rs if "_par_" in lid and any(o[len("shapes_"):] in lid for o in OUTSIDE)]
        self.assertTrue(named)
        for lid in named:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
            self.assertEqual([a["kind"] for a in rs[lid]["attempts"]], ["binding"], lid)
        text = self.model_text()
        self.assertRegex(text, r"# shapes_Frame_Wide: unsupported \(.*64")
        self.assertRegex(text, r"# shapes_Pair: unsupported \(.*two cells")


# ----------------------------------------------------------------------------------------------- the corpus
def aggs(doc: dict) -> dict:
    """(entry, family) -> {derived, decided, unknown}: the law counts a composed run commits (laws_aggregate)."""
    return {(r["id"], k): f for r in doc["rows"] for k, f in (r.get("laws_aggregate") or {}).items()}


class TestCorpusSmoke(unittest.TestCase):
    """P8-P10: the counted composed corpus run (results/M6/I122/holon/corpus.json) and the model-generation counts
    (results/M6/I122/loop_shapes.json, pre-decision, Q72)."""

    def doc(self) -> dict:
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def shapes_doc(self) -> dict:
        return json.loads(SHAPES.read_text(encoding="utf-8"))

    def base_doc(self) -> dict:
        # amended (spec/M6/amendments/I122.jsonl, Q104): this key's own baseline run, base_run.json alone, same code
        return json.loads((OUT / "baseline" / "corpus.json").read_text(encoding="utf-8"))

    def test_p8_loop_bodies_and_reasons(self):
        s = self.shapes_doc()
        self.assertGreaterEqual(s["ops_with_loop"], 1)
        self.assertGreaterEqual(s["loop_bodies"], pred("I122-P8")["expected"]["loop_bodies_at_least"])
        self.assertEqual(sum(s["by_class"].values()) + sum(s["unsupported_reasons"].values()), s["ops"])
        self.assertTrue(set(s["by_class"]) <= {"I67", "straight", "S1", "S2"})

    def test_p9_ops_in_class_and_laws(self):
        s = self.shapes_doc()
        n = s["by_class"].get("S1", 0) + s["by_class"].get("S2", 0)
        self.assertEqual(n, pred("I122-P9")["expected"]["ops_in_new_classes"])
        # amended (spec/M6/amendments/I122.jsonl): the laws are the rows' laws_aggregate; the PAR comparison is
        # test_p9_par_laws_equal_baseline
        self.assertEqual(sum(f["decided"] for _k, f in aggs(self.doc()).items()),
                         sum(f["decided"] for _k, f in aggs(self.base_doc()).items()))

    def test_p9_par_laws_equal_baseline(self):
        # amended (spec/M6/amendments/I122.jsonl): split from test_p9_ops_in_class_and_laws; P9's recorded miss
        a, b = aggs(self.doc()), aggs(self.base_doc())
        par = sorted(k for k in set(a) | set(b) if k[1].startswith("PAR/"))
        self.assertEqual({k: (a.get(k) or {}).get("derived", 0) for k in par},
                         {k: (b.get(k) or {}).get("derived", 0) for k in par})

    def test_p10_nothing_per_law_committed(self):
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and p.suffix in (".json", ".md", ".txt"):
                self.assertIsNone(LAW_ID.search(p.read_text(encoding="utf-8", errors="replace")),
                                  p.relative_to(ROOT).as_posix())
        d = self.doc()
        # amended (spec/M6/amendments/I122.jsonl): the document's rows, laws, laws_aggregate, laws_bundle_sha256
        for row in d["rows"]:
            self.assertEqual(row.get("laws"), [], row["id"])   # Q56: per-law rows withheld
            if any(f["derived"] for f in (row.get("laws_aggregate") or {}).values()):
                self.assertRegex(row.get("laws_bundle_sha256") or "", r"^[0-9a-f]{64}$", row["id"])
        sm = d["summary"]
        self.assertEqual(sm["findings"], 0)
        self.assertEqual(sm["detected_any"], [])
        for r, v in sm["recall"].items():
            self.assertEqual((v["detected"], v["recall"]), ([], 0.0), r)


class TestSealedContaminated(unittest.TestCase):
    """P11 (only if run, contaminated: post-I107): aggregates only, equal to the base landing's measurement."""

    def test_p11_spent_targets(self):
        if not SEALED.exists():   # P11 is conditional on a run the coordinator asks for; the report says whether
            self.assertIn("P11", (ROOT / "docs" / "iterations" / "I122.md").read_text(encoding="utf-8"))
            return
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d.get("label"), "contaminated: post-I107")
        self.assertIsNone(LAW_ID.search(SEALED.read_text(encoding="utf-8")))


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    """P7: without the opt-in every output is as before."""

    def test_p7_loop_models_byte_identical(self):
        """Every committed M3 Go-op model regenerates byte-identical (no Morph document carries the shapes data)."""
        from holon.gen import goloop
        n = 0
        for p in sorted((ROOT / "gen" / "M3" / "goops").glob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc.get("ops"), dict):
                continue
            m = ROOT / "gen" / "M3" / "model" / f"{doc['component']}.bend"
            text = m.read_text(encoding="utf-8")
            sha = re.search(r"sha256 ([0-9a-f]{64})", text).group(1)
            self.assertEqual(goloop.generate(doc, sha), text, m.name)
            n += 1
        self.assertGreaterEqual(n, 1)

    def test_p7_i67_class_first(self):
        """An op in goloop's I67 class is modelled as before even when its entry carries the shapes data."""
        from holon.gen import goloop
        for p in sorted((ROOT / "gen" / "M3" / "goops").glob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc.get("ops"), dict):
                continue
            before = goloop.shapes(doc)
            d2 = json.loads(json.dumps(doc))
            for op in d2["ops"].values():
                for lb in op.get("loop_bodies") or []:
                    lb["typed"] = {"terms": [], "iv_type": "int"}
            after = goloop.shapes(d2)
            for k, sh in before.items():
                if isinstance(sh, goloop.Shape):
                    self.assertIsInstance(after[k], goloop.Shape, k)
                    self.assertEqual(goloop.op_text(after[k]), goloop.op_text(sh), k)

    def test_p7_no_earlier_protocol_names_go_loops(self):
        for p in sorted((ROOT / "spec").glob("*/lib/i*_run.json")):
            if p.name == "i122_run.json":
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            # amended (spec/M6/amendments/I122.jsonl): the protocols of I122 and later keys are not earlier ones
            it = str(d.get("iteration") or "") if isinstance(d, dict) else ""
            if it[1:].isdigit() and int(it[1:]) >= 122:
                continue
            if isinstance(d, dict) and isinstance(d.get("go"), dict):
                self.assertNotIn("loops", d["go"], p.relative_to(ROOT).as_posix())

    def test_p7_protocol_is_its_base_plus_go_loops(self):
        # amended (spec/M6/amendments/I122.jsonl): compared with the base it measured on (tools/base_protocol.py's
        # generations before this key), never with the committed base_run.json, which later landings extend
        sys.path.insert(0, str(ROOT / "tools"))
        import base_protocol as bp
        gens = getattr(bp, "GENERATIONS", None)
        text = bp.build(gens[:1]) if gens else bp.build()
        b = protocol()
        self.assertIn(hashlib.sha256(text.encode("utf-8")).hexdigest(), b["doc"])
        a = json.loads(text)
        self.assertEqual(b["go"].pop("loops"), "shapes")
        b["go"].pop("loops_doc")
        b.pop("base_protocol")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_p7_no_bend_escape_hatch(self):
        from holon.gen import goloop
        text = goloop.generate(planted_doc(), "0" * 64)
        self.assertNotIn("?", text)
        self.assertNotIn("@unsafe", text)
        self.assertNotIn("import \"", text)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i115",
                    "tests-m6-i117", "tests-m6-i122"):
            self.assertTrue(f"name: {job}" in wf, job)


if __name__ == "__main__":
    unittest.main()
