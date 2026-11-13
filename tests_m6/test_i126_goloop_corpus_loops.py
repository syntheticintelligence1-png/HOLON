"""I126 (M6 follow-on): goops coverage of the corpus's loop shapes. Contract tests (spec/M6/predictions/I126.json;
prompts/I126_goloop_corpus_loops.md; HUMAN_ANSWERS Q112 (5), Q93 (3), Q90 (1)-(2), Q104, Q117).

The wall (I124's baseline, the lead 19:08Z): 78 corpus PAR laws are refused at binding for a loop reason, because goops
writes their op as unsupported: 47 with 0 loop bodies, 17 with a body with no paths, 10 with two bodies, 4 with three.
The frontend gives no body to a loop with no induction phi, and no paths to a body whose iteration meets another loop's
header, nested or sequential alike; goloop's classes (I67, I122's S1 and S2) take one loop.

This key's opt-in loop_forms "seq" (protocol go.loop_forms "seq", with loops "shapes" and ops "typed"):
  (a) the frontend records every loop's form and why it has no body or no paths (loop_forms); a path of one iteration
      that meets a later, disjoint loop's header ends "next"; an earlier side-effect-free counted loop met on a later
      loop's prefix is passed, its values opaque;
  (b) class SEQ (holon.gen.goshapes): counted loops over one fixed-length byte array composed in program order, each
      trip computed in its induction variable's Go type with wraparound, an empty loop dropped once its trip is shown
      finite; the model is I122's S2 model over the concatenated trip.

Anything else stays Unsupported. The planted fixture tests_m6/fixtures/i126 is a Go package written for these tests
from the specification's rules: the expectations are known by construction (its doc comment). Every planted SEQ op is
compared with the pinned go 1.24.7 by running the real function (Q90's differential method).
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
FIX = ROOT / "tests_m6" / "fixtures" / "i126"
GOSRC = FIX / "src"
I122_FIX = ROOT / "tests_m6" / "fixtures" / "i122"
PROTO = "spec/M6/lib/i126_run.json"
OUT = ROOT / "results" / "M6" / "I126"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
FORMS = OUT / "loop_forms.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
GO_VERSION = "go version go1.24.7 linux/amd64"   # the pinned go on PATH (config/toolchains.json go_set)
PKG = "example.com/holon/i126/seq"
NAMES = ("Seq2", "WrapSeq", "EmptyThen", "Nested", "Carry", "CallSeq", "Break", "MapRange", "Spin")
FN = {f"seq_{n}": f"{PKG}.{n}" for n in NAMES}
SEQ_OPS = ("seq_Seq2", "seq_WrapSeq", "seq_EmptyThen")
OUTSIDE = ("seq_Nested", "seq_Carry", "seq_CallSeq", "seq_Break", "seq_MapRange", "seq_Spin")
TRIPS = {"seq_Seq2": [0, 1, 2, 3, 7, 6, 5, 4], "seq_WrapSeq": [16, 17, 252, 0, 4], "seq_EmptyThen": [32, 34]}
IDX = {"seq_Seq2": (0, 1, 2, 3, 7, 6, 5, 4), "seq_WrapSeq": (16, 17, 252, 0, 4), "seq_EmptyThen": (32, 34)}
HEADERS = {"Seq2": ("for i := 0; i < 4; i++", "for j := 7; j >= 4; j--"),
           "WrapSeq": ("for i := 16; i < 18; i++", "for k := uint8(252); k != 8; k += 4"),
           "EmptyThen": ("for i := 0; i < 10; i++", "for j := 32; j < 36; j += 2")}   # the fixture's headers, run as Go
FALSE_LAWS = ("L_par_tot_seq_Seq2", "L_par_tot_seq_WrapSeq")
TRUE_LAWS = ("L_par_tot_seq_EmptyThen",)
WHY_NONE = ("no induction variable", "step not constant", "no comparison")   # the key's frontend_forms (7)
WHY_NULL = ("another loop on a path", "a store not tracked", "path limit", "an unsupported construct")


def key() -> dict:
    return json.loads((ROOT / "spec/M6/predictions/I126.json").read_text(encoding="utf-8"))


def pred(pid: str) -> dict:
    return next(p for p in key()["predictions"] if p["id"] == pid)


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


def config(forms: bool = True, fix: Path = FIX) -> dict:
    cfg = json.loads((fix / "go_config.json").read_text(encoding="utf-8"))
    if forms:
        cfg["loop_forms"] = "seq"
    else:
        cfg.pop("loop_forms", None)
    return cfg


def extract(cfg: dict, tmp: Path, ok: bool = True, src: Path = GOSRC):
    tmp.mkdir(parents=True)
    cp = tmp / "cfg.json"
    cp.write_text(json.dumps(cfg))
    out = tmp / "out"
    out.mkdir()
    p = subprocess.run([sys.executable, "-m", "holon", "extract", "go", "--root", str(ROOT), "--config", str(cp),
                        "--src", str(src), "--out-dir", str(out)], cwd=ROOT, env=ENV, capture_output=True,
                       text=True, timeout=600)
    if not ok:
        return p
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    (f,) = sorted(out.glob("*.extracted.json"))
    return json.loads(f.read_text(encoding="utf-8"))


def op_doc(functions: dict, fn: dict = FN, component: str = "seq_ops") -> dict:
    """The planted functions as the ops of a Go-op document (holon.gen.goloop reads doc["ops"] alone)."""
    return {"component": component, "carrier": {"id": "Carrier"},
            "ops": {name: functions[fid] for name, fid in fn.items()}}


_CACHE: dict = {}


def planted_functions(forms: bool = True) -> dict:
    k = ("fns", forms)
    if k not in _CACHE:
        t = Path(tempfile.mkdtemp(prefix="holon-i126-doc-"))
        try:
            _CACHE[k] = extract(config(forms), t / "x")["go"]["functions"]
        finally:
            shutil.rmtree(t, ignore_errors=True)
    return _CACHE[k]


def planted_doc() -> dict:
    return op_doc(planted_functions())


def i122_doc(forms: bool) -> dict:
    """I122's planted package as a Go-op document, extracted with its own config, with or without loop_forms."""
    k = ("i122", forms)
    if k not in _CACHE:
        sys.path.insert(0, str(ROOT))
        from tests_m6 import test_i122_goloop_loop_shapes as T122
        t = Path(tempfile.mkdtemp(prefix="holon-i126-i122-"))
        try:
            fs = extract(config(forms, I122_FIX), t / "x", src=I122_FIX / "src")["go"]["functions"]
        finally:
            shutil.rmtree(t, ignore_errors=True)
        _CACHE[k] = op_doc(fs, T122.FN, "shapes_ops")
    return _CACHE[k]


# ----------------------------------------------------------------------------------------------- the frontend
class TestFrontend(unittest.TestCase):
    """P1: loop_forms "seq" records the forms, ends a sequential exit "next" and passes an earlier loop on a prefix;
    without it nothing changes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i126-fe-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_p1_sequential_bodies_under_the_opt_in(self):
        fs = planted_functions()
        for n in ("Seq2", "WrapSeq", "EmptyThen"):
            lb1, lb2 = fs[FN[f"seq_{n}"]]["loop_bodies"]
            self.assertIsNotNone(lb1["paths"], n)
            self.assertIsNotNone(lb2["paths"], n)
            nxt = [p for p in lb1["paths"] if p["end"] == "next"]
            self.assertTrue(nxt, n)
            self.assertEqual({p["next"] for p in nxt}, {lb2["span"]}, n)
        lbs = fs[FN["seq_Nested"]]["loop_bodies"]
        self.assertTrue(all(lb["paths"] is None for lb in lbs))
        self.assertIsNone(fs[FN["seq_CallSeq"]]["loop_bodies"][1]["paths"])
        carry = fs[FN["seq_Carry"]]["loop_bodies"][1]["paths"]
        self.assertTrue(carry is None or any("carried" in json.dumps(p["cond"]) or "unknown" in json.dumps(p["cond"])
                                             for p in carry))

    def test_p1_loop_forms_recorded(self):
        fs = planted_functions()
        for n in NAMES:
            f = fs[FN[f"seq_{n}"]]
            self.assertIn("loop_forms", f, n)
            self.assertEqual(len(f["loop_forms"]), {"Nested": 2, "MapRange": 1, "Spin": 1}.get(n, 2), n)
        for n in ("MapRange", "Spin"):
            self.assertNotIn("loop_bodies", fs[FN[f"seq_{n}"]], n)
            (lf,) = fs[FN[f"seq_{n}"]]["loop_forms"]
            self.assertEqual((lf["kind"], lf["body"], lf["why"]), ("unbounded", "none", "no induction variable"), n)
        (m,) = fs[FN["seq_MapRange"]]["loop_forms"]
        self.assertEqual((m["syntax"], m["over"]), ("range", "map"))
        (s,) = fs[FN["seq_Spin"]]["loop_forms"]
        self.assertEqual((s["syntax"], s["cond"], s["over"]), ("for", False, None))
        inner = fs[FN["seq_Nested"]]["loop_forms"]
        self.assertEqual(sorted(lf["depth"] for lf in inner), [1, 2])
        self.assertTrue(all(lf["body"] == "null" and lf["why"] == "another loop on a path" for lf in inner))

    def test_p1_without_the_opt_in_nothing_changes(self):
        on = extract(config(), self.tmp / "on")
        off = extract(config(forms=False), self.tmp / "off")
        for fid, f in off["go"]["functions"].items():
            self.assertNotIn("loop_forms", f, fid)
            self.assertNotIn('"next"', json.dumps(f.get("loop_bodies")), fid)
        # amended (spec/M6/amendments/I126.jsonl): a body the opt-in enumerates has no OtherLoop debt entry under it
        done = {fid for fid, f in on["go"]["functions"].items()
                if f.get("loop_bodies") and all(lb["paths"] is not None for lb in f["loop_bodies"])}
        cov = dict(off["go"]["coverage"])
        cov["debt"] = [d for d in cov["debt"] if not (d.get("function") in done and d.get("what", "").startswith(
            "another loop on a path of one iteration"))]
        self.assertEqual(on["go"]["coverage"], cov)
        for k in on["go"]:
            if k not in ("functions", "coverage"):
                self.assertEqual(on["go"][k], off["go"][k], k)
        for fid, f in on["go"]["functions"].items():
            g = off["go"]["functions"][fid]
            for k in set(f) | set(g):
                if k not in ("loop_forms", "loop_bodies"):
                    self.assertEqual(f.get(k), g.get(k), (fid, k))
        # a function with at most one loop: its loop bodies are as without the opt-in
        for fid, f in on["go"]["functions"].items():
            if len(f.get("loop_forms") or []) <= 1:
                self.assertEqual(f.get("loop_bodies"), off["go"]["functions"][fid].get("loop_bodies"), fid)

    def test_p1_loop_forms_value_checked(self):
        p = extract(dict(config(), loop_forms="nested"), self.tmp / "bad", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("loop_forms must be", p.stdout + p.stderr)
        cfg = config()
        cfg.pop("loops")
        p = extract(cfg, self.tmp / "bad2", ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("loop_forms", p.stdout + p.stderr)


# ----------------------------------------------------------------------------------------------- the classes
class TestClasses(unittest.TestCase):
    """P2: which planted op is in SEQ, its concatenated trip and cell map, and the ops just outside."""

    @classmethod
    def setUpClass(cls):
        from holon.gen import goloop
        cls.shs = goloop.shapes(planted_doc())

    def test_p2_seq_shapes(self):
        from holon.gen import goshapes
        for name in SEQ_OPS:
            sh = self.shs[name]
            self.assertIsInstance(sh, goshapes.StrideShape, f"{name}: {sh}")
            self.assertEqual(sh.kind, "SEQ", name)
            self.assertEqual(sh.trip, TRIPS[name], name)
            self.assertEqual(sh.cell_map(), ("idx", IDX[name]), name)

    def test_p2_outside_unsupported(self):
        from holon.gen import goloop
        for name in OUTSIDE:
            sh = self.shs[name]
            self.assertIsInstance(sh, goloop.Unsupported, name)
            self.assertTrue(str(sh), name)


# ----------------------------------------------------------------------------------------------- the differential test
DIFF_MAIN = '''package main

import (
\t"fmt"

\tseq "example.com/holon/i126/seq"
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

func blob(kv ...int) *seq.Blob {
\tb := new(seq.Blob)
\tfor j := 0; j+1 < len(kv); j += 2 {
\t\tb[kv[j]] = byte(kv[j+1])
\t}
\treturn b
}

func main() {
%s
}
'''

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


def s2_cases(m: int) -> list[dict]:
    """Assignments of BYTE_SET values to at most two of the m iterations' cells (the others 0), as I122's."""
    out = [{}]
    for k in range(m):
        out += [{k: v} for v in BYTE_SET if v]
    for j, k in itertools.combinations(range(m), 2):
        out += [{j: u, k: v} for u in BYTE_SET for v in BYTE_SET if u and v]
    return out


class TestDifferential(unittest.TestCase):
    """P3: every planted SEQ op, compiled Bend model = real Go (the pinned toolchain) on every edge input; the trips
    equal the headers' own, run as Go."""

    @classmethod
    def setUpClass(cls):
        from holon.gen import goloop
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i126-diff-"))
        doc = planted_doc()
        sha = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        cls.cm = goloop.CompiledModel.build(doc, sha, "seq_ops")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cases(self) -> list:
        cases = []
        for name in SEQ_OPS:
            _, idx = self.cm.shapes[name].cell_map()
            for asg in s2_cases(len(idx)):
                cells = [asg.get(k, 0) for k in range(len(idx))]
                kv = ", ".join(f"{idx[k]}, {v}" for k, v in sorted(asg.items()))
                cases.append((name, cells, f"func() error {{ return seq.{name[4:]}(blob({kv})) }}"))
        return cases

    def test_p3_case_count(self):
        self.assertEqual(len(self.cases()), pred("I126-P3")["expected"]["cases"])

    def test_p3_model_equals_go(self):
        from holon.gen import goshapes
        cases = self.cases()
        got = run_go_main("\n".join(f"\tfmt.Println(out({c}))" for _, _, c in cases), self.tmp)
        model = self.cm.calls([{"fn": o, "args": [{"val": list(cells)}]} for o, cells, _ in cases])
        mirror = [goshapes.evaluate(self.cm.shapes[o], cells) for o, cells, _ in cases]
        self.assertEqual(len(got), len(cases))
        bad = [(o, cells, g, m.get("$") if isinstance(m, dict) else m, e)
               for (o, cells, _), g, m, e in zip(cases, got, model, mirror)
               if not (isinstance(m, dict) and g == m.get("$") == e)]
        self.assertEqual(bad[:10], [])

    def test_p3_trip_sequences_equal_go(self):
        body = []
        for n, hs in HEADERS.items():
            body.append(f'\tfmt.Println("{n}")')
            for h in hs:
                v = h.split()[1]
                body.append(f"\t{h} {{\n\t\tfmt.Println(\"{v}\", {v})\n\t}}")
        got = run_go_main("\n".join(body), self.tmp)
        seqs, cur = {}, None
        for line in got:
            if line in HEADERS:
                cur = line
                seqs[cur] = {}
            else:
                v, x = line.split()
                seqs[cur].setdefault(v, []).append(int(x))
        for n in HEADERS:
            sh = self.cm.shapes[f"seq_{n}"]
            loops = list(seqs[n].values())
            if n == "EmptyThen":   # the empty loop is dropped from the composition once its trip is shown finite
                self.assertEqual(loops[0], list(range(10)))
                loops = loops[1:]
            self.assertEqual([x for lp in loops for x in lp], sh.trip, n)
            self.assertEqual(sh.trip, TRIPS[f"seq_{n}"], n)


# ----------------------------------------------------------------------------------------------- the planted run
class _Planted(unittest.TestCase):
    """The composed route's Go part, route C and typed part over the planted package, in a scratch root, under the
    I122 protocol (as tests_m6/test_i117_go_op_semantics.py's _Planted does under I117's)."""
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i126-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self):
        if "run" not in _Planted.runs:
            from holon.eval import holon_run as H
            t = self.tmp / "run"
            t.mkdir()
            proto = protocol()
            S = H.scratch_root(ROOT, t, "holon/i126", GOSRC)
            rel = "results/eval/holon/i126"
            (S / rel / "sidecars").mkdir(parents=True)
            (S / rel / "facts").mkdir(parents=True)
            R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
            M = proto["milestone"]
            cfg = config()
            cfg["source"] = {"path": "<given by --src>"}
            cp = S / rel / "sidecars" / "seq.json"
            cp.write_text(H.dumps(cfg))
            st: dict = {}
            st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                                str(GOSRC), "--out-dir", str(S / rel / "facts")])
            assert st["extract"]["status"] == "ok", st["extract"]["detail"][-2000:]
            ms = H.go_machines(R, S, rel, proto, {"id": "i126"},
                               {"stem": "seq", "unit": cfg["documents"]["seq"][0]}, cfg, GOSRC, t)
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
    cells = list(bytes.fromhex(w[2:]))
    _, idx = sh.cell_map()
    kv = ", ".join(f"{idx[k]}, {v}" for k, v in enumerate(cells) if v)
    return f"func() error {{ return seq.{op[4:]}(blob({kv})) }}"


class TestPlanted(_Planted):
    def test_p4_false_laws_refuted_and_replayed(self):
        """The planted false laws are never PROVED; each is REFUTED at its witness, and every REFUTED record's witness,
        run as real Go, gives the outcomes the model's difference says."""
        from holon.gen import goloop
        rs = self.recs()
        for lid in FALSE_LAWS:
            self.assertEqual(rs[lid]["status"], "REFUTED", lid)
        shs = goloop.shapes(planted_doc())

        def nonzero(lid, op):
            w = list(bytes.fromhex(next(iter(rs[lid]["witness"].values()))[2:]))
            return {i: v for i, v in zip(shs[op].cell_map()[1], w) if v}
        self.assertEqual(nonzero("L_par_tot_seq_Seq2", "seq_Seq2"), {7: 0x80})
        self.assertEqual(nonzero("L_par_tot_seq_WrapSeq", "seq_WrapSeq"), {16: 1, 17: 1, 0: 0x7f})
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
        self.assertGreaterEqual(len(calls), pred("I126-P4")["expected"]["replayed_sides_at_least"])
        got = run_go_main("\n".join(f"\tfmt.Println(out({c}))" for c in calls), self.tmp)
        self.assertEqual(len(got), len(calls))
        for (is_ok, val), g in zip(want, got):
            self.assertEqual((g != "OPanic") if is_ok else g, val)

    def test_p5_true_laws_never_refuted(self):
        rs = self.recs()
        for lid in TRUE_LAWS:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
        self.assertEqual([lid for lid, r in rs.items() if "_par_" in lid and r["status"] == "PROVED"], [])

    def test_p6_outside_unbound(self):
        rs = self.recs()
        named = [lid for lid in rs if "_par_" in lid and any(lid.endswith(o) or f"{o}_" in lid for o in OUTSIDE)]
        self.assertTrue(named)
        for lid in named:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
            self.assertEqual([a["kind"] for a in rs[lid]["attempts"]], ["binding"], lid)
        text = self.model_text()
        for o in OUTSIDE:
            self.assertRegex(text, rf"# {o}: unsupported \(", o)


# ----------------------------------------------------------------------------------------------- the corpus
def aggs(doc: dict) -> dict:
    """(entry, family) -> {derived, decided, ...}: the law counts a composed run commits (laws_aggregate)."""
    return {(r["id"], k): f for r in doc["rows"] for k, f in (r.get("laws_aggregate") or {}).items()}


def extracted(doc: dict) -> set:
    """The entries whose Go documents both stages extracted (a row with any law family derived)."""
    return {r["id"] for r in doc["rows"] if r.get("laws_aggregate")}


class TestCorpusSmoke(unittest.TestCase):
    """P8-P10: the counted composed corpus run (results/M6/I126/holon/corpus.json), its baseline
    (results/M6/I126/baseline/corpus.json, base_run.json alone, same code) and the counts (loop_forms.json, Q72)."""

    def doc(self) -> dict:
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def base_doc(self) -> dict:
        return json.loads((OUT / "baseline" / "corpus.json").read_text(encoding="utf-8"))

    def forms_doc(self) -> dict:
        return json.loads(FORMS.read_text(encoding="utf-8"))

    def test_p8_forms_and_reasons(self):
        s = self.forms_doc()
        self.assertEqual(sum(s["by_class"].values()) + sum(s["unsupported_reasons"].values()), s["ops"])
        self.assertTrue(set(s["by_class"]) <= {"I67", "straight", "S1", "S2", "SEQ"})
        self.assertGreaterEqual(sum(s["loop_forms"].values()), s["ops_with_loop"])
        self.assertTrue(s["zero_body_loops"])
        self.assertLessEqual(set(s["zero_body_loops"]), set(WHY_NONE))

    def test_p9_ops_in_class_and_laws(self):
        s = self.forms_doc()
        self.assertEqual(s["by_class"].get("SEQ", 0), pred("I126-P9")["expected"]["ops_in_seq"])
        d, b = self.doc(), self.base_doc()
        both = extracted(d) & extracted(b)
        a1, a2 = aggs(d), aggs(b)
        par = sorted(k for k in set(a1) | set(a2) if k[0] in both and k[1].startswith("PAR/"))
        self.assertEqual({k: (a1.get(k) or {}).get("derived", 0) for k in par},
                         {k: (a2.get(k) or {}).get("derived", 0) for k in par})
        bound = {r["id"]: (r.get("bind") or {}).get("bound", 0) for r in d["rows"] if r["id"] in both}
        self.assertEqual(bound, {r["id"]: (r.get("bind") or {}).get("bound", 0) for r in b["rows"] if r["id"] in both})
        self.assertEqual(sum(f["decided"] for k, f in a1.items() if k[0] in both),
                         sum(f["decided"] for k, f in a2.items() if k[0] in both))

    def test_p10_nothing_per_law_committed(self):
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and p.suffix in (".json", ".md", ".txt"):
                self.assertIsNone(LAW_ID.search(p.read_text(encoding="utf-8", errors="replace")),
                                  p.relative_to(ROOT).as_posix())
        for d in (self.doc(), self.base_doc()):
            for row in d["rows"]:
                self.assertEqual(row.get("laws"), [], row["id"])   # Q56: per-law rows withheld
                if any(f["derived"] for f in (row.get("laws_aggregate") or {}).values()):
                    self.assertRegex(row.get("laws_bundle_sha256") or "", r"^[0-9a-f]{64}$", row["id"])
            sm = d["summary"]
            self.assertEqual(sm["findings"], 0)
            self.assertEqual(sm["detected_any"], [])
            for r, v in sm["recall"].items():
                self.assertEqual((v["detected"], v["recall"]), ([], 0.0), r)


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    """P7, R1: without the opt-in every output is as before; I122's S1 and S2 are unchanged."""

    def test_p7_loop_models_byte_identical(self):
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

    def test_p7_i122_classes_unchanged(self):
        """I122's planted ops are in S1 and S2 with I122's trips, with or without loop_forms, and their op texts are
        identical (S1 and S2 come before SEQ)."""
        from holon.gen import goloop, goshapes
        from tests_m6 import test_i122_goloop_loop_shapes as T122
        off, on = goloop.shapes(i122_doc(False)), goloop.shapes(i122_doc(True))
        for name in T122.S1_OPS + T122.S2_OPS:
            for shs in (off, on):
                self.assertTrue(goshapes.is_shape(shs[name]), f"{name}: {shs[name]}")
                self.assertIn(shs[name].kind, ("S1", "S2"), name)
            self.assertEqual(goshapes.op_text(on[name]), goshapes.op_text(off[name]), name)
        for name, trip in T122.TRIPS.items():
            self.assertEqual(on[name].trip, trip, name)
        for name in T122.OUTSIDE:
            self.assertIsInstance(on[name], goloop.Unsupported, name)

    def test_p7_no_earlier_protocol_names_go_loop_forms(self):
        for p in sorted((ROOT / "spec").glob("*/lib/*_run.json")):
            if p.name == "i126_run.json":
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("go"), dict):
                self.assertNotIn("loop_forms", d["go"], p.relative_to(ROOT).as_posix())

    def test_p7_protocol_is_its_base_plus_go_loop_forms(self):
        a = protocol("spec/M6/lib/base_run.json")
        b = protocol()
        sha = hashlib.sha256((ROOT / "spec/M6/lib/base_run.json").read_bytes()).hexdigest()
        self.assertIn(sha, b["doc"])
        self.assertEqual(b["go"].pop("loop_forms"), "seq")
        b["go"].pop("loop_forms_doc")
        self.assertEqual(b.pop("base_protocol"), "spec/M6/lib/base_run.json")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k, None)
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
                    "tests-m6-i117", "tests-m6-i122", "tests-m6-i123", "tests-m6-i126"):
            self.assertTrue(f"name: {job}" in wf, job)


if __name__ == "__main__":
    unittest.main()
