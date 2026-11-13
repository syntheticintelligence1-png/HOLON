"""I117 (M6, generality): Go op semantics for the binding. Contract tests (spec/M6/predictions/I117.json;
prompts/I117_go_op_semantics.md; HUMAN_ANSWERS Q90, Q91).

The wall I115 measured: every one of the corpus's 93 PAR laws is UNKNOWN by binding, because a PAR law over Go code
can be bound only when every op it names has a meaning in the Go-op model, and goloop defines only its loop class.

  (1) Go op semantics (holon.gen.goint), each definition read from the Go specification (its docstring quotes the
      rule): fixed-width wraparound of + - * and <<, truncated division and remainder (MinInt / -1 is MinInt, a zero
      divisor panics), shifts (arithmetic for a signed left operand, logical for an unsigned one, no upper limit, a
      negative count panics), unary - and ^, conversions between integer types (sign or zero extension, then
      truncation), comparisons. A Go integer is the 64-bit two's complement of its value (Word(64n) in Bend); int, uint
      and uintptr are 64 bits on the pinned linux/amd64 toolchain. An op the module cannot state exactly has no
      definition (Undefined).
  (2) The Go frontend's opt-in ops "typed" (config holon-go-frontend/0.3; protocol go.ops "typed"): every
      path-enumerated function, codec-shaped or not, records the Go type of each typed term, and its reasoner reads
      sized arithmetic as opaque (lin), so no branch is pruned by unbounded arithmetic; a load after a store or a call
      through memory the enumerator does not model marks the function stale. The Go machine documents are extracted
      without it.
  (3) The Go-op model's straight-line class (holon.gen.gostraight; Q90, Q91 (1)): an op with no loop over a byte array
      (cells at constant indexes) or a guard over the carrier's fields (integer and bool fields, nil-ness, len), each
      term in Go's semantics. Not stated exactly, so Unsupported (its laws unbound, UNKNOWN): a division by a
      non-constant or a shift by a signed non-constant count (the frontend's paths record no panic for them), a stale
      field load, any other term, paths that do not partition the sample points.
  (4) Q91 (3): on the mpipeline path the binding check runs before the emitter (holon run --unbound unknown): an
      unbound law is never emitted or decided.

The planted fixture tests_m6/fixtures/i117 is a Go package written for these tests from the specification's rules: the
expectations are known by construction (its doc comment). The corpus smoke measures are results/M6/I117/holon/
corpus.json (holon eval holon --protocol spec/M6/lib/i117_run.json --compose); a run on I106's targets, labelled
contaminated: post-I107, commits aggregates only (results/M6/I117/sealed.json; Q56, Q72).
"""
from __future__ import annotations

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
FIX = ROOT / "tests_m6" / "fixtures" / "i117"
GOSRC = FIX / "src"
PROTO = "spec/M6/lib/i117_run.json"
OUT = ROOT / "results" / "M6" / "I117"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
GO_VERSION = "go version go1.24.7 linux/amd64"   # the pinned go on PATH (config/toolchains.json go_set)
PKG = "example.com/holon/i117/wrap"
FALSE_LAWS = ("L_par_tot_wrap_SumWrap", "L_par_tot_wrap_Gate_Admit")   # false under Go, true under unbounded ints
TRUE_LAWS = ("L_par_tot_wrap_ShiftMix", "L_par_tot_wrap_SignedLow", "L_par_tot_wrap_Counter_Bump",
             "L_par_dom_ok_wrap_ShiftMix_ok_wrap_SignedLow")


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I117.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def go_bin() -> str:
    go = shutil.which("go")
    assert go, "go is not on PATH"
    v = subprocess.run([go, "version"], capture_output=True, text=True).stdout.strip()
    assert v == GO_VERSION, f"the differential test runs on the pinned toolchain, not {v!r}"
    return go


def bend_run(args: list, cwd: Path):
    """The pinned checker (holon.bend.run): (exit code, output)."""
    from holon import bend
    r = bend.run(args, cwd=cwd, timeout=1800)
    return r.code, r.out


# ----------------------------------------------------------------------------------------------- (1) the semantics
class TestSemantics(unittest.TestCase):
    """P1: the differential test. Every edge case runs as real Go under the pinned toolchain and is compared with the
    reference (holon.gen.goint) and with the model's definitions (the compiled Bend module); a sample is checked by
    Bend's own evaluation, and a planted wrong value is rejected."""

    @classmethod
    def setUpClass(cls):
        from holon.gen import goint_diff as D
        cls.D = D
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i117-diff-"))
        cls.cases = D.cases()
        cls.go = D.run_go(go_bin(), cls.cases, cls.tmp / "go")
        cls.ref = [D.reference(c) for c in cls.cases]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_p1_cases_cover_the_edges(self):
        e = pred("I117-P1")["expected"]
        self.assertGreaterEqual(len(self.cases), e["cases_at_least"])
        kinds = {(c["k"], c.get("op")) for c in self.cases}
        for o in ("+", "-", "*", "/", "%", "&", "|", "^", "&^"):
            self.assertIn(("bin", o), kinds)
        for o in ("<<", ">>"):
            self.assertIn(("shift", o), kinds)
        self.assertIn(("conv", None), kinds)
        self.assertTrue(any(c["k"] == "bin" and c["op"] == "/" and c["t"] == "int64" and c["a"] == -2 ** 63
                            and c["b"] == -1 for c in self.cases))   # MinInt / -1
        self.assertTrue(any(c["k"] == "shift" and c["b"] == 64 for c in self.cases))   # past the width
        self.assertTrue(any(c["k"] == "shift" and c["b"] < 0 for c in self.cases))    # a negative count
        self.assertIn("panic", self.ref)

    def test_p1_go_equals_reference(self):
        self.assertEqual(len(self.go), len(self.cases))
        bad = [(c, g, r) for c, g, r in zip(self.cases, self.go, self.ref) if g != r]
        self.assertEqual(bad[:5], [])

    def test_p1_go_equals_the_compiled_model(self):
        D = self.D
        w = self.tmp / "model"
        w.mkdir()
        (w / "h.bend").write_text(D.model_text(self.cases))
        code, out = bend_run(["h.bend", "-o", "h.mjs"], w)
        self.assertEqual(code, 0, out[-2000:])
        q = subprocess.run(["node", "--stack-size=65500", str(ROOT / "holon" / "js" / "linked.mjs")],
                           input=json.dumps({"module": str(w / "h.mjs"),
                                             "calls": [D.model_call(c) for c in self.cases]}),
                           capture_output=True, text=True)
        self.assertEqual(q.returncode, 0, q.stderr[-2000:])
        got = [D.model_answer(c, r) for c, r in zip(self.cases, json.loads(q.stdout)["results"])]
        bad = [(c, g, m) for c, g, m in zip(self.cases, self.go, got) if g != m]
        self.assertEqual(bad[:5], [])

    def test_p1_the_checker_agrees_and_rejects_a_wrong_value(self):
        D = self.D
        sel = [(c, g) for i, (c, g) in enumerate(zip(self.cases, self.go)) if g != "panic" and i % 40 == 0]
        self.assertGreaterEqual(len(sel), pred("I117-P1")["expected"]["checked_by_bend_at_least"])
        w = self.tmp / "kernel"
        w.mkdir()
        (w / "k.bend").write_text(D.check_text([c for c, _ in sel], [g for _, g in sel]))
        code, out = bend_run(["k.bend"], w)
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("ALL PROOFS CHECK", out)
        c, g = sel[3]
        wrong = "true" if g == "false" else "false" if g == "true" else str(int(g) + 1)
        (w / "n.bend").write_text(D.check_text([c for c, _ in sel[:3]] + [c], [g for _, g in sel[:3]] + [wrong]))
        code, out = bend_run(["n.bend"], w)
        self.assertNotEqual(code, 0)
        self.assertIn("Location: d3", out)

    def test_p1_undefined_stays_undefined(self):
        from holon.gen import goint as GI
        for t in ("float64", "string", "example.com/x.Named", "complex128"):
            self.assertIsNone(GI.itype(t))
            with self.assertRaises(GI.Undefined):
                GI.binop_text("+", t, "a", "b")


# ----------------------------------------------------------------------------------------------- (2) the frontend
def extract(cfg: dict, tmp: Path) -> dict:
    tmp.mkdir(parents=True)
    cp = tmp / "cfg.json"
    cp.write_text(json.dumps(cfg))
    out = tmp / "out"
    out.mkdir()
    p = subprocess.run([sys.executable, "-m", "holon", "extract", "go", "--root", str(ROOT), "--config", str(cp),
                        "--src", str(GOSRC), "--out-dir", str(out)], cwd=ROOT, env=ENV, capture_output=True,
                       text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    (f,) = sorted(out.glob("*.extracted.json"))
    return json.loads(f.read_text(encoding="utf-8"))["go"]["functions"]


class TestFrontend(unittest.TestCase):
    """P2: ops "typed": typed terms recorded for every enumerated function; the reasoner control."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i117-fe-"))
        self.cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_p2_typed_terms_and_the_reasoner_control(self):
        fs = extract(self.cfg, self.tmp / "typed")
        inc = fs[f"{PKG}.IncWrap"]
        self.assertTrue(any(p["end"] == "panic" for p in inc["paths"]), "the wrapped branch is kept")
        terms = {json.dumps(t): ty for t, ty in inc["typed"]["terms"]}
        self.assertEqual(terms[json.dumps(["op", "+", ["index", ["param", "b"], ["const", 2]], ["const", 1]])], "byte")
        self.assertEqual(inc["typed"]["lengths"], {"b": 8})
        bump = fs[f"(*{PKG}.Counter).Bump"]
        self.assertIsNotNone(bump["paths"])       # not codec-shaped, enumerated under ops "typed"
        self.assertFalse(bump["typed"]["stale"])  # the store comes after the last load
        cfg0 = dict(self.cfg)
        cfg0.pop("ops")
        fs0 = extract(cfg0, self.tmp / "plain")
        inc0 = fs0[f"{PKG}.IncWrap"]
        # amended by I119 (spec/M6/amendments/I117.jsonl): before I119 the branch was pruned without ops typed (the
        # unbounded reading); from I119 (HUMAN_ANSWERS Q93 (1)(b)) the opaque-arithmetic rule is the default
        self.assertTrue(any(p["end"] == "panic" for p in inc0["paths"]), "from I119 the branch is kept by default")
        self.assertNotIn("typed", inc0)
        self.assertIsNone(fs0[f"(*{PKG}.Counter).Bump"]["paths"])

    def test_p2_ops_value_checked(self):
        cfg = dict(self.cfg, ops="exact")
        cp = self.tmp / "bad.json"
        cp.write_text(json.dumps(cfg))
        (self.tmp / "o").mkdir()
        p = subprocess.run([sys.executable, "-m", "holon", "extract", "go", "--root", str(ROOT), "--config", str(cp),
                            "--src", str(GOSRC), "--out-dir", str(self.tmp / "o")], cwd=ROOT, env=ENV,
                           capture_output=True, text=True, timeout=600)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ops must be", p.stdout + p.stderr)


# ----------------------------------------------------------------------------------------------- (3) the planted run
class _Planted(unittest.TestCase):
    """The composed route's Go part, route C and typed part over the planted package, in a scratch root, under the
    I117 protocol (as tests_m6/test_i115_binding_wall.py's _Planted does under I115's)."""
    runs: dict = {}

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i117-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self):
        if "run" not in _Planted.runs:
            from holon.eval import holon_run as H
            t = self.tmp / "run"
            t.mkdir()
            proto = protocol()
            S = H.scratch_root(ROOT, t, "holon/i117", GOSRC)
            rel = "results/eval/holon/i117"
            (S / rel / "sidecars").mkdir(parents=True)
            (S / rel / "facts").mkdir(parents=True)
            R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
            M = proto["milestone"]
            cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
            cfg["source"] = {"path": "<given by --src>"}
            cp = S / rel / "sidecars" / "wrap.json"
            cp.write_text(H.dumps(cfg))
            st: dict = {}
            st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                                str(GOSRC), "--out-dir", str(S / rel / "facts")])
            assert st["extract"]["status"] == "ok", st["extract"]["detail"][-2000:]
            ms = H.go_machines(R, S, rel, proto, {"id": "i117"}, {"stem": "wrap", "unit": cfg["documents"]["wrap"][0]},
                               cfg, GOSRC, t)
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


REPLAY_MAIN = '''package main

import (
\t"fmt"

\twrap "example.com/holon/i117/wrap"
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

func main() {
%s
}
'''


def replay_go(calls: list[str], tmp: Path) -> list[str]:
    """Each call (a Go expression of type func() error over the fixture package) run on the pinned toolchain: its
    outcome as the model names it."""
    w = tmp / "replay"
    shutil.copytree(GOSRC, w)
    (w / "cmd").mkdir()
    (w / "cmd" / "main.go").write_text(REPLAY_MAIN % "\n".join(f"\tfmt.Println(out({c}))" for c in calls))
    p = subprocess.run([go_bin(), "run", "./cmd"], cwd=w, capture_output=True, text=True, timeout=600,
                       env={**os.environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"})
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.split()


def go_call(op: str, w) -> str:
    """The fixture op wrap_<X> (or wrap_<T>_<M>) at a record's witness, as a Go func() error."""
    name = op[len("wrap_"):]
    if isinstance(w, str):   # bytes: "0x.."
        bs = bytes.fromhex(w[2:])
        return f"func() error {{ return wrap.{name}(wrap.Blob{{{', '.join(str(b) for b in bs)}}}) }}"
    typ, meth = name.split("_", 1)
    fs = []
    for k, v in sorted(w.items()):
        if k.endswith(" == nil"):
            fs.append(f"{k[:-7]}: {'nil' if v else 'new(int)'}")
        elif k.startswith("len("):
            fs.append(f"{k[4:-1]}: make([]int, {v})")
        else:
            fs.append(f"{k}: {str(v).lower() if isinstance(v, bool) else v}")
    return f"func() error {{ return (&wrap.{typ}{{{', '.join(fs)}}}).{meth}() }}"


class TestPlanted(_Planted):
    def test_p3_false_laws_refuted_and_replayed(self):
        """The planted laws false under Go's semantics (true under unbounded integers) are never PROVED; each is
        REFUTED, and every REFUTED record's witness, run as real Go, gives the outcomes the model's difference says."""
        rs = self.recs()
        for lid in FALSE_LAWS:
            self.assertEqual(rs[lid]["status"], "REFUTED", lid)
        self.assertEqual(rs["L_par_tot_wrap_SumWrap"]["witness"], {"b": "0x01ff000000000000"})
        self.assertEqual(rs["L_par_tot_wrap_Gate_Admit"]["witness"]["b"]["Lim"], 2 ** 31 - 1)
        calls, want = [], []
        for lid, r in sorted(rs.items()):
            if r["status"] != "REFUTED" or not lid.startswith("L_par_"):
                continue
            law = json.loads((self.run_of()[1] / "laws" / self.run_of()[2] / f"{lid}.json").read_text())
            (b,) = [x["name"] for x in law["statement"]["binders"]]
            for side, val in zip(law["statement"]["claim"]["eq"], (r["difference"]["lhs"], r["difference"]["rhs"])):
                if "call" not in side:
                    continue
                f = side["call"]
                op = f[3:] if f.startswith("ok_") else f
                calls.append(go_call(op, r["witness"][b]))
                want.append((f.startswith("ok_"), val))
        self.assertGreaterEqual(len(calls), pred("I117-P3")["expected"]["replayed_sides_at_least"])
        got = replay_go(calls, self.tmp)
        self.assertEqual(len(got), len(calls))
        for (is_ok, val), g in zip(want, got):
            self.assertEqual((g != "OPanic") if is_ok else g, val)

    def test_p3_true_laws_never_refuted(self):
        rs = self.recs()
        for lid in TRUE_LAWS:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
        self.assertEqual([lid for lid, r in rs.items() if r["status"] == "PROVED" and lid.startswith("L_par_")], [])

    def test_p4_undefined_op_unbound(self):
        """Quot divides by a non-constant: its zero-divisor panic is not on the frontend's paths, so it is undefined
        in the model, and every law naming it is UNKNOWN by binding; nothing else is unbound."""
        st, S, M = self.run_of()
        rs = self.recs()
        quot = sorted(lid for lid in rs if "Quot" in lid)
        self.assertGreaterEqual(len(quot), 1)
        for lid in quot:
            self.assertEqual(rs[lid]["status"], "UNKNOWN", lid)
            self.assertEqual([a["kind"] for a in rs[lid]["attempts"]], ["binding"], lid)
        unb = json.loads((S / "spec" / "bindings" / f"{M}.unbound.json").read_text())["laws"]
        self.assertEqual(sorted(unb), quot)
        bound = json.loads((S / "spec" / "bindings" / f"{M}.json").read_text())["laws"]
        laws = sorted(p.stem for p in (S / "laws" / M).glob("L*.json"))
        self.assertEqual(sorted(set(unb) | set(bound)), laws)
        self.assertEqual(st["bind"]["status"], "ok")
        self.assertEqual(st["bind"]["aggregate"], {"laws": len(laws), "bound": len(laws) - len(quot),
                                                   "unbound": len(quot), "refused": 0})
        model = (S / "gen" / M / "model" / "blob_ops.bend").read_text()
        self.assertIn("# wrap_Quot: unsupported", model)
        self.assertIn("division by a non-constant", model)

    def test_p4_field_guards(self):
        """Q91 (1): Gate's guards over its fields: Check is refuted where Conn is non-nil and Items has 4 elements."""
        rs = self.recs()
        r = rs["L_par_tot_wrap_Gate_Check"]
        self.assertEqual(r["status"], "REFUTED")
        w = r["witness"]["b"]
        self.assertFalse(w["Conn == nil"])
        self.assertEqual(w["len(Items)"], 4)
        self.assertEqual(rs["L_par_tot_wrap_Counter_Bump"]["status"], "UNKNOWN")
        self.assertNotIn("binding", [a["kind"] for a in rs["L_par_tot_wrap_Counter_Bump"]["attempts"]])


# ----------------------------------------------------------------------------------------------- (4) Q91 (3)
class TestMpipelineBinding(unittest.TestCase):
    """P5: on the mpipeline path an unbound law is refused before any decision is emitted: a copy of an M1 law whose
    statement names a function the model does not define, run with --unbound unknown in a scratch root."""

    def test_p5_unbound_before_the_emitter(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i117-mp-"))
        try:
            S = tmp / "root"
            ig = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "heldout")
            for d in ("holon", "config", "spec", "bend", "schemas", "laws/M1", "gen/M1", "results/M1", "facts"):
                if (ROOT / d).is_dir():
                    shutil.copytree(ROOT / d, S / d, ignore=ig)
            src = sorted((S / "laws" / "M1").glob("L_*.json"))[0]
            law = json.loads(src.read_text())
            law["law_id"] = "L_i117_unbound"
            claim = law["statement"]["claim"]["eq"][0]
            self.assertIn("fn", claim)
            claim["fn"] = "i117_undefined"
            (S / "laws" / "M1" / "L_i117_unbound.json").write_text(json.dumps(law, indent=2, sort_keys=True) + "\n")
            p = subprocess.run([sys.executable, "-m", "holon", "run", "--milestone", "M1", "--laws", "L_i117_unbound",
                                "--no-registry", "--unbound", "unknown"], cwd=S, env=ENV, capture_output=True,
                               text=True, timeout=1200)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            r = json.loads((S / "results" / "M1" / "L_i117_unbound.json").read_text())
            self.assertEqual(r["status"], "UNKNOWN")
            self.assertEqual([a["kind"] for a in r["attempts"]], ["binding"])   # nothing emitted, nothing decided
            self.assertIn("i117_undefined", r["attempts"][0]["error"])
            self.assertIsNone(r["artifacts"]["laws"])
            self.assertIsNone(r["artifacts"]["proof"])
            self.assertFalse((S / "gen" / "M1" / "L_i117_unbound").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------------------------- measured outcomes
class TestCorpusSmoke(unittest.TestCase):
    """P7-P10: smoke measures on I51's 20 entries (contaminated by I51, I103-I116 and I107)."""

    def doc(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I117/holon/corpus.json is missing")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def rows(self) -> dict:
        return {r["id"]: r for r in self.doc()["rows"]}

    def test_p7_stage_reach(self):
        e = pred("I117-P7")["expected"]
        self.assertEqual(self.doc()["preflight"]["status"], "ok")
        reach: dict = {}
        for i, r in self.rows().items():
            for s, v in (r.get("stages") or {}).items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(i)
            if r.get("laws_aggregate"):
                self.assertEqual((r["stages"].get("bind") or {}).get("status"), "ok", i)
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)

    def test_p8_par_bound(self):
        e = pred("I117-P8")["expected"]
        bound, refused = 0, 0
        for r in self.rows().values():
            b = r.get("bind") or {}
            bound += b.get("bound", 0)
            refused += b.get("refused", 0)
        self.assertGreaterEqual(bound, e["bound_at_least"])
        self.assertEqual(refused, 0)

    def test_p9_laws_aggregate(self):
        e = pred("I117-P9")["expected"]
        rows = self.rows()
        aggs = [(k, f) for r in rows.values() for k, f in (r.get("laws_aggregate") or {}).items()]
        for i, r in rows.items():
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
        for k, f in aggs:
            self.assertEqual(set(f), {"derived", "decided", "unknown"}, k)
            self.assertEqual(f["derived"], f["decided"] + f["unknown"], k)
        self.assertGreaterEqual(sum(f["derived"] for _k, f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for _k, f in aggs), e["decided_at_least"])

    def test_p10_nothing_per_law_committed(self):
        base = OUT / "holon"
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base).as_posix()
            if LAW_ID.search(rel) or "/bindings/" in f"/{rel}" or p.name.endswith(".unbound.json"):
                hits.append(rel)
                continue
            if p.name == "corpus.json":
                for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                    if LAW_ID.search(json.dumps({k: v for k, v in r.items() if k != "laws_aggregate"})):
                        hits.append(f"corpus.json:{r['id']}")
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if LAW_ID.search(text):
                hits.append(rel)
        self.assertEqual(hits, [])


class TestSealedContaminated(unittest.TestCase):
    """P11: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p11_spent_targets(self):
        self.assertTrue(SEALED.is_file(), "results/M6/I117/sealed.json is missing")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        for x in d["targets"]:
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, x["id"])
            for k in x.get("laws_aggregate", {}).values():
                self.assertEqual(set(k), {"derived", "decided", "unknown"}, x["id"])


# ----------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    """P6: without the opt-ins every output is as before."""

    def test_p6_loop_models_byte_identical(self):
        """A Go-op document with no "typed" key (every Morph document) generates the model it generated before: the
        committed M3 Go-op models, regenerated."""
        from holon.gen import goloop
        n = 0
        for p in sorted((ROOT / "gen" / "M3" / "goops").glob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc.get("ops"), dict):
                continue
            m = ROOT / "gen" / "M3" / "model" / f"{doc['component']}.bend"
            self.assertTrue(m.is_file(), m)
            text = m.read_text(encoding="utf-8")
            sha = re.search(r"sha256 ([0-9a-f]{64})", text).group(1)
            self.assertEqual(goloop.generate(doc, sha), text, m.name)
            n += 1
        self.assertGreaterEqual(n, 1)

    def test_p6_no_earlier_protocol_names_go_ops(self):
        for p in sorted((ROOT / "spec").glob("*/lib/*.json")):
            if p.name == "i117_run.json":
                continue
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and isinstance(d.get("go"), dict):
                self.assertNotIn("ops", d["go"], p.relative_to(ROOT).as_posix())

    def test_p6_protocol_is_its_base_plus_go_ops(self):
        b = protocol()
        a = protocol(b["base_protocol"])
        self.assertEqual(b["go"].pop("ops"), "typed")
        b["go"].pop("ops_doc")
        b.pop("base_protocol")
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_p6_no_bend_escape_hatch(self):
        from holon.gen import goint, goint_diff, gostraight
        for text in (goint.PRELUDE, gostraight.CELL_DEF, goint_diff.HARNESS_HEAD):
            self.assertNotIn("?", text)
            self.assertNotIn("@unsafe", text)
            self.assertNotIn("import \"", text)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i115",
                    "tests-m6-i117"):
            self.assertTrue(f"name: {job}" in wf, job)


if __name__ == "__main__":
    unittest.main()
