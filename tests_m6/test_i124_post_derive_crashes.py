"""I124 (M6, generality): the post-derive crashes. Contract tests (spec/M6/predictions/I124.json;
prompts/I124_post_derive_crashes.md; HUMAN_ANSWERS Q106, the lead's ruling).

The walls I120 measured: with every stage reading the whole extracted document (I120's go.store_scope "commit") the
corpus derives 268 laws and decides 0, because the full documents reach post-derive stages that crash. Three
fail-closed instrument defects, each fixed here from the semantics, each with a planted fixture written from Go's and
Bend's semantics (tests_m6/fixtures/i124/src, never corpus code), a soundness control and an input just outside the
handled shape:

  F-M6-06  holon.gen.goloop.cells_literal raised IndexError on the empty cell sequence. A Go-op component whose ops
           read no field of the carrier (the straight-line class, I117) has a carrier of zero cells, whose one value is
           the empty sequence; every candidate witness is that sequence, and counter_proof built it with parts[-1] on
           an empty list. The fix: the empty sequence is Bend's empty list [] (exact: the only List<&2, U32> of length
           0). Planted: latch.Latch (Trip always panics, Rest never does).
  F-M6-07  a DISCH document whose typed model cannot be compiled (holon.sorts.evaluate3.EvalError, raised while the
           runner builds the document) stopped the DISCH runner, so every DISCH law of the milestone had no record. On
           the corpus the model is one Bend accepts (the same bytes compile, exit 0, in this key's sandbox) and the
           compile peaks near 12 GB of memory: a resource limit, not a generator defect (HUMAN_ANSWERS Q108). The fix,
           two parts: (a) the error names the cause (the exit code, the signal that ended the checker, or the
           time-out) with the checker's last output; (b) under the DISCH runner's --section-errors unknown (I112's
           opt-in, in the base protocol) a document whose model cannot be built is refused like a document whose
           section is refused: its laws are UNKNOWN with the error, nothing is attempted, and every other document is
           decided as before. Without the opt-in the error stops the runner, as before. Planted: two Go machines of
           this key's own (tests_m6/fixtures/i124/machines: Till, Drawer), with the compile of Drawer's typed model
           run by the real checker under a time-out it cannot meet (the planted fault FAULT, in the scratch root only:
           a deterministic recorded cause, HUMAN_ANSWERS Q108).
  F-M6-08  holon bind --unbound skip raised FileNotFoundError (not BindingError) and wrote nothing when a law's model
           gen/<M>/model/<component>.bend did not exist: the milestone runner writes that model when it first decides a
           law of the component, and a runner that never reached the component (F-M6-06's crash, or I118's per-document
           re-run of another document) leaves none. The fix: a law whose model the run never generated is unbound
           with that reason (a BindingError: it can be neither bound nor decided), every other law bound exactly as
           before. Anything else that fails still refuses as before (a law whose facts document is missing). Planted:
           the milestone runner run over Latch's laws only, then bind.

Nothing here is more permissive: every decision is still Bend's (a REFUTED only through a counter-law Bend accepts,
its witness replayed on the real Go code), a law the fix reaches that it cannot state stays UNKNOWN with its reason,
and the binding check still refuses every decided record of an unbound law. The planted runs use I117's landed
protocol (spec/M6/lib/i117_run.json), which names neither of I118's run and bind fallbacks, so each crash is seen as
the crash it is. The corpus measures (TestCorpusSmoke) are smoke on contaminated data, read from
results/M6/I124/holon/corpus.json and the base run beside it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i124"
GOSRC = FIX / "src"
PROTO = "spec/M6/lib/i117_run.json"
MACH = FIX / "machines"   # the planted Go machines of F-M6-07 (Till, Drawer)
OUT = ROOT / "results" / "M6" / "I124"
CORPUS = OUT / "holon" / "corpus.json"
BASE_CORPUS = OUT / "base" / "corpus.json"
GO_VERSION = "go version go1.24.7 linux/amd64"
CRASH_ENTRIES = ("c04", "c09", "c14", "c19")   # I120's report: the entries of the three crash classes


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I124.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def go_bin() -> str:
    go = shutil.which("go")
    assert go, "go is not on PATH"
    v = subprocess.run([go, "version"], capture_output=True, text=True).stdout.strip()
    assert v == GO_VERSION, f"the replay runs on the pinned toolchain, not {v!r}"
    return go


def reference_cells_literal(cells: list[int]) -> str:
    """holon.gen.goloop.cells_literal as it was before I124, for a non-empty sequence (the byte-identity control)."""
    runs = []
    for v in cells:
        if runs and runs[-1][0] == v:
            runs[-1][1] += 1
        else:
            runs.append([v, 1])
    parts = [f"List.replicate(U32, {k}n, {v})" if k > 1 else f"[{v}]" for v, k in runs]
    out = parts[-1]
    for p in reversed(parts[:-1]):
        out = f"List.append(&2, U32, {p}, {out})"
    return out


def unseconds(x):
    if isinstance(x, dict):
        return {k: unseconds(v) for k, v in x.items() if k not in ("seconds", "generator_sha256")}
    if isinstance(x, list):
        return [unseconds(v) for v in x]
    return x


# ----------------------------------------------------------------------------------------------- the planted run
class _Planted(unittest.TestCase):
    """The composed route's Go part, route C and the typed part over the planted package, in a scratch root, under
    I117's protocol (as tests_m6/test_i117_go_op_semantics.py's _Planted does)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i124-"))
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self):
        if "run" not in self.runs:
            from holon.eval import holon_run as H
            t = self.tmp / "run"
            t.mkdir()
            proto = protocol()
            S = H.scratch_root(ROOT, t, "holon/i124", GOSRC)
            rel = "results/eval/holon/i124"
            (S / rel / "sidecars").mkdir(parents=True)
            (S / rel / "facts").mkdir(parents=True)
            R = H.Runner(H.Ctx(t, GOSRC), S, proto, {})
            M = proto["milestone"]
            cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
            cfg["source"] = {"path": "<given by --src>"}
            cp = S / rel / "sidecars" / "latch.json"
            cp.write_text(H.dumps(cfg))
            st: dict = {}
            st["extract"] = R.holon("extract", ["extract", "go", "--root", str(S), "--config", str(cp), "--src",
                                                str(GOSRC), "--out-dir", str(S / rel / "facts")])
            assert st["extract"]["status"] == "ok", st["extract"]["detail"][-2000:]
            ms = H.go_machines(R, S, rel, proto, {"id": "i124"}, {"stem": "latch", "unit": cfg["documents"]["latch"][0]},
                               cfg, GOSRC, t)
            files = sorted(p.name for p in (S / rel / "facts").glob("*.extracted.json"))
            st["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents",
                                            ",".join(f"{rel}/facts/{f}" for f in files), "--out-dir",
                                            str(S / rel / "sidecars" / "roles"), "--mode", "static", "--install",
                                            "--roles", "hand"])
            lib = S / "spec" / M / "lib"
            H._rules(R, S, rel, M, proto, [{"file": f} for m in ms for f in m["files"]], st,
                     lambda: H._route_c(R, S, M, lib, st))
            self.runs["run"] = (st, S, M, R)
        return self.runs["run"]

    def recs(self) -> dict:
        _st, S, M, _R = self.run_of()
        return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((S / "results" / M).glob("L*.json"))}

    def laws(self, comp: str) -> list[str]:
        _st, S, M, _R = self.run_of()
        return sorted(p.stem for p in (S / "laws" / M).glob(f"L_par_*_latch_{comp}_*.json"))


REPLAY_MAIN = '''package main

import (
\t"fmt"

\tlatch "example.com/holon/i124/latch"
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
    shutil.rmtree(w, ignore_errors=True)
    shutil.copytree(GOSRC, w)
    (w / "cmd").mkdir()
    (w / "cmd" / "main.go").write_text(REPLAY_MAIN % "\n".join(f"\tfmt.Println(out({c}))" for c in calls))
    p = subprocess.run([go_bin(), "run", "./cmd"], cwd=w, capture_output=True, text=True, timeout=600,
                       env={**os.environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"})
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.split()


# ======================================================================================== F-M6-06: the empty carrier
class TestF06Unit(unittest.TestCase):
    """P1 (unit): the empty sequence is Bend's empty list; every non-empty sequence is written byte for byte as before."""

    def test_p1_empty_is_the_empty_list(self):
        from holon.gen import goloop
        self.assertEqual(goloop.cells_literal([]), "[]")

    def test_p1_non_empty_byte_identical(self):
        from holon.gen import goloop
        for cells in ([0], [255], [1, 1], [1, 2], [7, 7, 7, 0, 0, 9], [0xffffffff, 0, 0xffffffff], list(range(20))):
            self.assertEqual(goloop.cells_literal(cells), reference_cells_literal(cells), cells)


class TestF06Planted(_Planted):
    """P2, P3: the planted Latch component reaches the empty-carrier path; under the fix the runner finishes, the false
    laws are REFUTED through Bend with a witness that replays on the real Go code, the true law is never REFUTED, and
    the component outside the model class (Stale) stays UNKNOWN with its reason."""

    def test_p2_the_shape_reaches_the_empty_carrier(self):
        _st, S, M, _R = self.run_of()
        docs = {json.loads(p.read_text(encoding="utf-8"))["component"]: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((S / "gen" / M / "goops").glob("*.json"))}
        from holon.gen import goloop
        latch = [d for c, d in docs.items() if "latch" in c.lower() and any("Latch" in o for o in d["ops"])]
        self.assertEqual(len(latch), 1, sorted(docs))
        cm = goloop.CompiledModel.build(latch[0], "0" * 64, "probe", json.loads((ROOT / "config" / "holon.json").read_text()))
        maps = {o: sh.cell_map() for o, sh in cm.shapes.items() if not isinstance(sh, goloop.Unsupported)}
        self.assertTrue(maps)
        for o, m in maps.items():
            self.assertEqual(m[-1], 0, (o, m))   # zero cells: the carrier's one value is the empty sequence

    def test_p2_runner_finishes(self):
        st, _S, _M, _R = self.run_of()
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        self.assertIn("0 laws with no record", st["run"]["detail"])

    def test_p2_false_laws_refuted_and_replayed(self):
        recs = self.recs()
        tot_trip = "L_par_tot_latch_Latch_Trip"
        self.assertEqual(recs[tot_trip]["status"], "REFUTED")
        self.assertEqual(recs[tot_trip]["kernel"]["verdict"], "checked")
        refuted = {k: r for k, r in recs.items() if r["status"] == "REFUTED"}
        self.assertTrue(refuted)
        calls, want = [], []
        for k, r in sorted(refuted.items()):
            self.assertIn("_latch_Latch_", k)   # only the Latch component has a false law
            (w,) = r["witness"].values()
            self.assertEqual(w, {}, k)   # the empty carrier: a Latch with no field read
            calls += ["func() error { return (&latch.Latch{}).Trip() }", "func() error { return (&latch.Latch{}).Rest() }"]
            want += ["OPanic", "ORet"]
        got = replay_go(calls, self.tmp)
        self.assertEqual(got, want)
        # each record's difference is the replayed outcomes: tot (ok_Trip = True) is False = True; weak and dom
        # compare Rest's ORet with Trip's OPanic
        self.assertEqual(recs[tot_trip]["difference"], {"lhs": False, "rhs": True})

    def test_p2_true_law_never_refuted(self):
        recs = self.recs()
        r = recs["L_par_tot_latch_Latch_Rest"]
        self.assertEqual(r["status"], "UNKNOWN")
        kinds = [a.get("kind") for a in r.get("attempts") or []]
        self.assertIn("counter-law", kinds)
        self.assertTrue(all(a.get("error") for a in r["attempts"] if a.get("kind") == "counter-law"),
                        "Bend rejects every counter-proof of the true law")
        self.assertEqual(recs["L_par_tot_latch_Valve_Shut"]["status"], "UNKNOWN")

    def test_p3_just_outside_refused_with_reason(self):
        recs = self.recs()
        stale = {k: r for k, r in recs.items() if "_latch_Stale_" in k}
        self.assertTrue(stale)
        for k, r in stale.items():
            self.assertEqual(r["status"], "UNKNOWN", k)
            self.assertTrue(r.get("bound"), k)


# ======================================================================================== F-M6-07: the model build
class TestF07Unit(unittest.TestCase):
    """P4 (unit): a failed compile names its cause."""

    def test_p4_cause_named(self):
        from holon.bend import Run
        from holon.sorts import evaluate3 as E3
        cases = [(Run(None, "partial\n[timeout]", 180.0, []), "timed out"),
                 (Run(-9, "", 3.0, []), "signal 9"),
                 (Run(1, "Error: parse", 1.0, []), "exit 1")]
        for r, want in cases:
            msg = E3.compile_failure(Path("gen/M9/sorts/models/x.bend"), r)
            self.assertIn("bend failed to compile gen/M9/sorts/models/x.bend", msg)
            self.assertIn(want, msg)
        self.assertIn("no module was written", E3.compile_failure(Path("x.bend"), Run(0, "", 1.0, [])))


# The planted fault (F-M6-07; HUMAN_ANSWERS Q108: a deterministic recorded cause), written into the scratch root only
# (the runner's PYTHONPATH is the scratch root, so its Python imports it at start): the compile of exactly the
# poisoned model's text runs the real checker with a time-out it cannot meet (FAULT_TIMEOUT_S), so holon.bend.run
# stops it and returns its [timeout] result, as it does for any checker run over its bound. Nothing in holon/ is
# changed; every other Bend run is the real one, with its configured bound.
FAULT_TIMEOUT_S = 0.05
FAULT = """import holon.bend as _b
from pathlib import Path as _P
_POISON = _P(%r).read_text(encoding="utf-8")
_run = _b.run


def run(args, cwd=None, timeout=None, cfg=None):
    a = [str(x) for x in args]
    if cwd is not None and a[:1] == ["model.bend"] and (_P(cwd) / "model.bend").read_text(encoding="utf-8") == _POISON:
        return _run(args, cwd=cwd, timeout=%r, cfg=cfg)
    return _run(args, cwd=cwd, timeout=timeout, cfg=cfg)


_b.run = run
"""


class _Go(unittest.TestCase):
    """The planted Go machines (tests_m6/fixtures/i124/machines: Till, Drawer), extracted by the Go machine frontend and
    run through the typed part with a private evaluator cache (HOLON_CACHE), with I112's helpers and protocol (its
    disch.section_errors "unknown")."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i124-go-"))
        from tests_m6 import test_i112_run_wall as T
        cls.T = T
        p = T.run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(MACH / "go_config.json"),
                         "--src", str(MACH / "src"), "--out-dir", str(cls.tmp / "docs")])
        if p.returncode != 0:
            raise AssertionError(p.stderr[-3000:])
        cls.docs = {json.loads(x.read_text(encoding="utf-8"))["contract"].rsplit(".", 1)[-1]: x
                    for x in sorted((cls.tmp / "docs").glob("*.extracted.json"))}
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self, names: tuple, cache: str, section_errors: bool = True, poison: str | None = None):
        """The typed part over the named documents with HOLON_CACHE=<tmp>/<cache>. poison: a document whose typed
        model's compile is then bounded by a time-out it cannot meet (FAULT), and the typed part run again."""
        k = (names, cache, section_errors, poison)
        if k not in self.runs:
            T = self.T
            from holon.eval import holon_run as H
            t = self.tmp / f"run{len(self.runs)}"
            t.mkdir()
            proto = T.protocol(T.PROTO)
            if not section_errors:
                proto["disch"].pop("section_errors", None)
            old = os.environ.get("HOLON_CACHE")
            os.environ["HOLON_CACHE"] = str(self.tmp / cache)
            try:
                S, rel, R = T.scratch(t, proto, MACH / "src")
                for n in names:
                    shutil.copy(self.docs[n], S / rel / "facts" / self.docs[n].name)
                st = T.typed_part(S, rel, R, proto, [self.docs[n].name for n in names])
                if poison is not None:   # the planted fault, then the typed part again
                    M = proto["milestone"]
                    model = next((S / "gen" / M / "sorts" / "models").glob(f"*{poison}.extracted.bend"))
                    import hashlib
                    text = model.read_text(encoding="utf-8")
                    shutil.rmtree(self.tmp / cache / "m3eval" / hashlib.sha256(text.encode("utf-8")).hexdigest()[:32],
                                  ignore_errors=True)
                    (t / "poison.bend").write_text(text, encoding="utf-8")
                    (S / "sitecustomize.py").write_text(FAULT % (str(t / "poison.bend"), FAULT_TIMEOUT_S))
                    shutil.rmtree(S / "results" / M, ignore_errors=True)
                    st = T.typed_part(S, rel, R, proto, [self.docs[n].name for n in names])
            finally:
                if old is None:
                    os.environ.pop("HOLON_CACHE", None)
                else:
                    os.environ["HOLON_CACHE"] = old
            self.runs[k] = (st, S, rel, proto["milestone"])
        return self.runs[k]


class TestF07Planted(_Go):
    """P5, P6: a document whose model cannot be built leaves its DISCH laws UNKNOWN with the error; the other document
    is decided exactly as alone; without the opt-in the runner stops, as before."""

    def test_p5_confined_to_its_document(self):
        """The same two documents with and without the planted fault: only the faulted document's DISCH laws move
        (decided without it, UNKNOWN with the error under it); every other record is byte for byte the same."""
        T = self.T
        _a, A, _rel, M = self.run_of(("Till", "Drawer"), "clean")
        st, B, _rel, _M = self.run_of(("Till", "Drawer"), "poisoned", poison="Drawer")
        self.assertEqual(st["run"]["status"], "ok", st["run"]["detail"][-2000:])
        facts = T.law_facts(B, M)
        disch = {k for k in facts if json.loads((B / "laws" / M / f"{k}.json").read_text()).get("rule") == "DISCH"}
        drawer = sorted(k for k in disch if (facts[k] or "").endswith("till.Drawer.extracted.json"))
        self.assertTrue(drawer)
        self.assertTrue(any(json.loads((A / "results" / M / f"{k}.json").read_text())["status"] in ("PROVED", "REFUTED")
                            for k in drawer), "without the fault the document's laws are decided")
        for k in drawer:
            r = json.loads((B / "results" / M / f"{k}.json").read_text(encoding="utf-8"))
            self.assertEqual(r["status"], "UNKNOWN", k)
            self.assertEqual([a["kind"] for a in r["attempts"]], ["section"], k)
            self.assertIn("could not be built", r["attempts"][0]["error"])
            self.assertIn("timed out", r["attempts"][0]["error"])
            self.assertIsNone(r.get("witness"), k)
        others = [n for n in sorted(facts) if n not in drawer and (A / "results" / M / f"{n}.json").is_file()]
        self.assertTrue(any(json.loads((A / "results" / M / f"{n}.json").read_text())["status"] in ("PROVED", "REFUTED")
                            for n in others), "the other document decides a law")
        for n in others:
            ra = json.loads((A / "results" / M / f"{n}.json").read_text(encoding="utf-8"))
            rb = json.loads((B / "results" / M / f"{n}.json").read_text(encoding="utf-8"))
            self.assertEqual(unseconds(ra), unseconds(rb), n)

    def test_p6_without_the_option_stops_as_before(self):
        st, B, _rel, M = self.run_of(("Till", "Drawer"), "poisoned2", section_errors=False, poison="Drawer")
        self.assertNotEqual(st["run"]["status"], "ok")
        disch = [k for k in self.T.law_facts(B, M)
                 if json.loads((B / "laws" / M / f"{k}.json").read_text()).get("rule") == "DISCH"]
        self.assertTrue(disch)
        self.assertEqual([k for k in disch if (B / "results" / M / f"{k}.json").is_file()], [])


# ======================================================================================== F-M6-08: bind
class TestF08Planted(_Planted):
    """P7-P9: bind over a milestone whose runner reached only the Latch component."""

    def partial(self, name: str) -> tuple[Path, str, dict]:
        """A copy of the planted root whose results and Go-op models are removed and whose milestone runner is run over
        Latch's laws only (as I118's per-document re-run runs one document's laws), then holon bind --unbound skip."""
        st, S, M, R = self.run_of()
        key = ("partial", name)
        if key not in self.runs:
            from holon.eval import holon_run as H
            P = self.tmp / name / "root"
            shutil.copytree(S, P, symlinks=True)
            shutil.rmtree(P / "results" / M, ignore_errors=True)
            shutil.rmtree(P / "gen" / M / "model", ignore_errors=True)
            for f in (P / "spec" / "bindings").glob(f"{M}.*"):   # the full run's own binding
                f.unlink()
            proto = protocol()
            R2 = H.Runner(R.ctx, P, proto, {})
            out = {}
            out["run"] = R2.holon("run", ["run", "--milestone", M, *H.runner_args("milestone", proto, "", "", ""),
                                          "--laws", ",".join(self.laws("Latch")), "--out", f"results/{M}", "--gen-dir",
                                          f"gen/{M}"])
            out["bind"] = R2.holon("bind", ["bind", "--milestone", M, "--root", str(P), "--unbound", "skip"],
                                   timeout_key="derive")
            self.runs[key] = (P, M, out)
        return self.runs[key]

    def test_p7_bind_finishes(self):
        P, M, out = self.partial("p7")
        self.assertEqual(out["run"]["status"], "ok", out["run"]["detail"][-2000:])
        self.assertEqual(out["bind"]["status"], "ok", out["bind"]["detail"][-2000:])
        bound = json.loads((P / "spec" / "bindings" / f"{M}.json").read_text())["laws"]
        unbound = json.loads((P / "spec" / "bindings" / f"{M}.unbound.json").read_text())["laws"]
        for k in self.laws("Latch"):
            self.assertIn(k, bound, k)
        for k in self.laws("Valve"):
            self.assertIn(k, unbound, k)
            self.assertIn("was not generated", unbound[k])

    def test_p8_bound_laws_as_in_the_full_run(self):
        """The laws the partial run reached are bound byte for byte as the full run binds them."""
        _st, S, M, _R = self.run_of()
        fb = json.loads((S / "spec" / "bindings" / f"{M}.json").read_text())["laws"]   # the full run's bind stage
        P, M, _out = self.partial("p7")
        pb = json.loads((P / "spec" / "bindings" / f"{M}.json").read_text())["laws"]
        for k in self.laws("Latch"):
            self.assertEqual(pb[k], fb[k], k)

    def test_p8_unbound_never_decided(self):
        """The soundness control: a decided record of an unbound law (a planted REFUTED for Valve's law) is refused by
        the binding check; the reached component's decided records are admitted."""
        from holon.eval import holon_run as H
        P, M, _out = self.partial("p8")
        (v,) = [k for k in self.laws("Valve") if k.startswith("L_par_tot_")]
        trip = json.loads((P / "results" / M / "L_par_tot_latch_Latch_Trip.json").read_text())
        forged = dict(trip, law_id=v, status="REFUTED")
        (P / "results" / M / f"{v}.json").write_text(json.dumps(forged))
        refused = H.binding_check(P, M, self.laws("Latch") + self.laws("Valve"))
        self.assertEqual(refused, 1)
        self.assertEqual(json.loads((P / "results" / M / f"{v}.json").read_text())["status"], "UNKNOWN")
        self.assertEqual(json.loads((P / "results" / M / "L_par_tot_latch_Latch_Trip.json").read_text())["status"],
                         "REFUTED")

    def test_p9_just_outside_still_refuses(self):
        """A law whose facts document is missing is not a model the run never generated: bind still refuses (exit 1,
        nothing written), as before."""
        st, S, M, R = self.run_of()
        from holon.eval import holon_run as H
        Q = self.tmp / "p9" / "root"
        if not Q.exists():
            shutil.copytree(S, Q, symlinks=True)
            for f in (Q / "spec" / "bindings").glob(f"{M}.*"):   # the full run's own binding
                f.unlink()
        (v,) = [k for k in self.laws("Valve") if k.startswith("L_par_tot_")]
        law = json.loads((Q / "laws" / M / f"{v}.json").read_text())
        (Q / law["facts"]).unlink()
        r = H.Runner(R.ctx, Q, protocol(), {}).holon("bind", ["bind", "--milestone", M, "--root", str(Q), "--unbound",
                                                             "skip"], timeout_key="derive")
        self.assertEqual(r["exit"], 1, r["detail"][-1500:])
        self.assertFalse((Q / "spec" / "bindings" / f"{M}.json").exists())


# ======================================================================================== the corpus (smoke)
def _rows(p: Path) -> dict:
    return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}


@unittest.skipUnless(CORPUS.is_file() and BASE_CORPUS.is_file(), "the measured runs are not committed yet")
class TestCorpusSmoke(unittest.TestCase):
    """P10-P12: smoke on contaminated data (I51's corpus; Q98), base against this key's code, one protocol."""

    def test_p10_crash_classes_gone(self):
        rows = _rows(CORPUS)
        for i in CRASH_ENTRIES:
            r = rows.get(i)
            if r is None or "run_runners" not in r:
                continue
            for k, v in r["run_runners"].items():
                self.assertEqual(v["exit"], 0, (i, k))
            self.assertEqual((r["stages"].get("bind") or {}).get("exit"), 0, i)

    def test_p11_no_law_without_a_record(self):
        rows = _rows(CORPUS)
        for i in CRASH_ENTRIES:
            r = rows.get(i)
            if r is None or "run" not in r["stages"]:
                continue
            self.assertIn("; 0 laws with no record", r["stages"]["run"]["detail"], i)

    def test_p12_decided_not_fewer(self):
        """Decided counts are PROVED and REFUTED together (Q56, Q89), summed over the rows' laws_aggregate."""
        def decided(p: Path) -> int:
            return sum(f["decided"] for r in _rows(p).values() for f in (r.get("laws_aggregate") or {}).values())
        self.assertGreaterEqual(decided(CORPUS), decided(BASE_CORPUS))
        self.assertGreaterEqual(decided(CORPUS), pred("I124-P12")["expected"]["decided_at_least"])


# ======================================================================================== F-M6-11: the memory record
class TestMemoryRecord(unittest.TestCase):
    """Q108 (3), F-M6-11 (added after the prereg as build work, recording only): the preflight records MemTotal,
    MemAvailable and the cgroup memory limit; it decides nothing (the status is the binaries' alone)."""

    def test_memory_recorded_only(self):
        from holon.eval import holon_run as H
        m = H.memory_record()
        self.assertEqual(set(m), {"mem_total", "mem_available", "cgroup_limit"})
        self.assertGreater(m["mem_total"], 0)
        self.assertGreaterEqual(m["mem_total"], m["mem_available"])
        r = H.preflight(protocol("spec/M6/lib/i118_run.json"), {})
        self.assertEqual(r["status"], "ok")   # nothing to check: the memory record does not move the status
        self.assertEqual(set(r["memory"]), set(m))


# ======================================================================================== regressions
class TestRegressions(unittest.TestCase):
    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        names = re.findall(r"- name: (tests-m6-i\d+)\b", wf)
        self.assertIn("tests-m6-i124", names)
        for n in ("tests-m6-i112", "tests-m6-i115", "tests-m6-i116", "tests-m6-i117", "tests-m6-i118"):
            self.assertIn(n, names)

    def test_r1_no_bend_escape_hatch(self):
        from holon.gen import goloop
        for t in (goloop.cells_literal([]), goloop.cells_literal([1, 1, 2])):
            for bad in ("admit", "sorry", "Ω", "trust", "axiom"):
                self.assertNotIn(bad, t)


if __name__ == "__main__":
    unittest.main()
