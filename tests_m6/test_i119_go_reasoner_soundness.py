"""I119 (M6, generality): Go reasoner soundness (HUMAN_ANSWERS Q93 (1); the defect I117's report, Surprise 1, found).

The contract (spec/M6/predictions/I119.json):

  (a) tools/i119_audit.py re-extracts every committed Go document in scratch copies of holon/ under the old reading and
      under I117's opaque-arithmetic rule alone, and writes results/M6/I119/audit.json: per-milestone counts of changed
      documents and of affected committed decided laws, and one sha256 bundle commitment of the affected-law list (the
      list itself stays in the vault: no law id is committed, Q56, Q89).
  (b) The rule is the Go frontend's default for every Go document: holon/frontends/go reads sized arithmetic as opaque
      in the path reasoner under every config version, with or without ops "typed"; the narrow-arithmetic loop mode
      (I67) is unchanged.

The planted package tests_m6/fixtures/i119 (Go semantics only): Inc64's panic is reachable only through 64-bit
wraparound; Idx's index is in bounds under unbounded integers and out of bounds under wraparound; Plus is a control.
The differential check runs them on the pinned go 1.24.7 (Q90's method).
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
FIX = ROOT / "tests_m6" / "fixtures" / "i119"
GOSRC = FIX / "src"
PKG = "example.com/holon/i119/wrap64"
OUT = ROOT / "results" / "M6" / "I119"
AUDIT = OUT / "audit.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
GO_VERSION = "go version go1.24.7 linux/amd64"
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I119.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def go_bin() -> str:
    go = shutil.which("go")
    assert go, "go is not on PATH"
    v = subprocess.run([go, "version"], capture_output=True, text=True).stdout.strip()
    assert v == GO_VERSION, f"the differential check runs on the pinned toolchain, not {v!r}"
    return go


def extract(cfg: dict, tmp: Path, sub: str = "go") -> dict:
    tmp.mkdir(parents=True)
    cp = tmp / "cfg.json"
    cp.write_text(json.dumps(cfg))
    out = tmp / "out"
    out.mkdir()
    p = subprocess.run([sys.executable, "-m", "holon", "extract", sub, "--root", str(ROOT), "--config", str(cp),
                        "--src", str(GOSRC), "--out-dir", str(out)], cwd=ROOT, env=ENV, capture_output=True,
                       text=True, timeout=600)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    (f,) = sorted(out.glob("*.extracted.json"))
    return json.loads(f.read_text(encoding="utf-8"))["go"]["functions"]


def ends(f: dict) -> list:
    return sorted(p["end"] for p in (f["paths"] or []))


def config() -> dict:
    cfg = json.loads((FIX / "go_config.json").read_text(encoding="utf-8"))
    cfg["source"] = {"path": str(GOSRC)}
    return cfg


# ----------------------------------------------------------------------------------------------- P1: the fixture
class TestFixture(unittest.TestCase):
    """P1: under the default (no ops), the wraparound branch is kept and the false in-bounds claim is not made."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i119-fx-"))
        cls.fs = extract(config(), cls.tmp / "default")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_p1_wraparound_branch_kept(self):
        inc = self.fs[f"{PKG}.Inc64"]
        self.assertIn("panic", ends(inc), "the branch x+1 < x (x = MaxInt64) is reachable in Go")
        self.assertEqual([s["status"] for s in inc["sites"] if s["kind"] == "panic"], ["open"])

    def test_p1_index_not_safe(self):
        idx = self.fs[f"{PKG}.Idx"]
        self.assertIn("panic", ends(idx))
        st = [s["status"] for s in idx["sites"] if s["kind"] == "index"]
        self.assertEqual(st, ["open"], "i >= 0 && i+1 <= len(b) does not bound i under wraparound")

    def test_p1_control_unchanged(self):
        self.assertEqual(ends(self.fs[f"{PKG}.Plus"]), ["panic", "return", "return"])

    def test_p1_ops_typed_agrees(self):
        cfg = dict(config(), ops="typed")
        fs = extract(cfg, self.tmp / "typed")
        for fn in ("Inc64", "Idx", "Plus"):
            self.assertEqual(fs[f"{PKG}.{fn}"]["paths"], self.fs[f"{PKG}.{fn}"]["paths"], fn)
            self.assertEqual(fs[f"{PKG}.{fn}"]["sites"], self.fs[f"{PKG}.{fn}"]["sites"], fn)

    def test_p1_old_reading_recorded(self):
        """The audit's baseline reproduced the defect on the fixture: no panic path in Inc64, Idx's site safe."""
        a = json.loads(AUDIT.read_text(encoding="utf-8"))
        fx = a["fixture"]
        self.assertEqual(fx["old"]["Inc64"]["ends"], ["return"])
        self.assertEqual(fx["old"]["Idx"]["index_status"], "safe")
        self.assertIn("panic", fx["rule"]["Inc64"]["ends"])
        self.assertEqual(fx["rule"]["Idx"]["index_status"], "open")


# ----------------------------------------------------------------------------------------------- P2: differential
MAIN = '''package main

import (
\t"fmt"
\t"math"

\tw "example.com/holon/i119/wrap64"
)

func out(f func()) (s string) {
\tdefer func() {
\t\tif r := recover(); r != nil {
\t\t\ts = "panic"
\t\t}
\t}()
\tf()
\treturn "return"
}

func main() {
\tfmt.Println(out(func() { _ = w.Inc64(nil, math.MaxInt64) }))
\tfmt.Println(out(func() { _ = w.Idx(make([]byte, 1), math.MaxInt) }))
\tfmt.Println(out(func() { fmt.Print(w.Idx(make([]byte, 1), 0), " ") }))
\tfmt.Println(out(func() { _ = w.Plus([]byte{7, 0}) }))
\tfmt.Println(out(func() { _ = w.Inc64(nil, 0) }))
}
'''


class TestDifferential(unittest.TestCase):
    """P2: the pinned Go toolchain confirms the paths the default keeps (Q90's differential method)."""

    def test_p2_go_confirms(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i119-go-"))
        try:
            w = tmp / "w"
            shutil.copytree(GOSRC, w)
            (w / "cmd").mkdir()
            (w / "cmd" / "main.go").write_text(MAIN)
            p = subprocess.run([go_bin(), "run", "./cmd"], cwd=w, capture_output=True, text=True, timeout=600,
                               env={**os.environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"})
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            self.assertEqual(p.stdout.split("\n")[:5], ["panic", "panic", "0 return", "panic", "return"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------------------------- P3-P5: the audit
class TestAudit(unittest.TestCase):
    """P3-P5: the committed audit summary: counts and a commitment only."""

    @classmethod
    def setUpClass(cls):
        cls.text = AUDIT.read_text(encoding="utf-8")
        cls.a = json.loads(cls.text)

    def test_audit_names_no_law(self):
        self.assertIsNone(LAW_ID.search(self.text), "the affected-law list stays in the vault (Q56)")
        self.assertRegex(self.a["affected_bundle_sha256"], r"^[0-9a-f]{64}$")

    def test_audit_counts_are_per_milestone(self):
        aff = self.a["affected_decided_laws"]
        self.assertEqual(sorted(aff), ["M0", "M1", "M2", "M3", "corpus"])
        for v in aff.values():
            self.assertIsInstance(v, int)

    def test_p3_morph_baseline_reproduces(self):
        m = self.a["morph"]
        self.assertEqual(m["documents"], pred("I119-P3")["expected"]["morph_documents"])
        self.assertEqual(m["baseline_identical"], m["documents"], "the old reading re-extracts the committed bytes")

    def test_audit_corpus_covered(self):
        c = self.a["corpus"]
        self.assertGreater(c["configs"], 0)
        self.assertEqual(c["configs"], c["extracted"] + c["refused"])

    def test_audit_is_read_only(self):
        """Nothing committed moved in (a): the audited commit's committed Go documents are the ones checked."""
        # amended by I119 (spec/M6/amendments/I119.jsonl): the consumer-section document by its extractor part
        for d in self.a["morph"]["files"]:
            self.assertTrue(extractor_part_reproduces(d), d["path"])


def extractor_part_reproduces(d: dict) -> bool:
    """A committed Morph Go document equals its baseline extraction: by bytes, or (a document with a 'consumer'
    section added by I85's derivation consumer) by its other keys, against the committed document of the same
    config whose bytes are the baseline's."""
    if d["committed_sha256"] == d["baseline_sha256"]:
        return True
    doc = json.loads((ROOT / d["path"]).read_text(encoding="utf-8"))
    if "consumer" not in doc:
        return False
    doc.pop("consumer")
    import hashlib
    for p in sorted((ROOT / "spec").glob("M*/facts/*.extracted.json")):
        if hashlib.sha256(p.read_bytes()).hexdigest() == d["baseline_sha256"]:
            return json.loads(p.read_text(encoding="utf-8")) == doc
    return False


# ----------------------------------------------------------------------------------------------- P6: the default
class TestDefault(unittest.TestCase):
    """P6: the rule is the default under every config version; ops "typed" keeps only its typed section."""

    def test_p6_reasoner_default(self):
        from holon.frontends.go.ctx import Ctx
        for v in ("holon-go-frontend/0.1", "holon-go-frontend/0.2", "holon-go-frontend/0.3"):
            self.assertTrue(Ctx.opaque_arith_of({"config_version": v}), v)
            self.assertTrue(Ctx.opaque_arith_of({"config_version": v, "ops": "typed"}), v)

    def test_p6_reasoner_unit(self):
        from holon.frontends.go.terms import Reasoner
        x = ("param", "x")
        a = ("<", ("op", "+", x, ("const", 1)), x)
        self.assertIs(Reasoner([], opaque=False).status(a), False, "the unbounded reading refutes x+1 < x")
        self.assertIsNone(Reasoner([], opaque=True).status(a), "x+1 < x is satisfiable under wraparound")
        self.assertIs(Reasoner([], opaque=True).status(("<", x, ("op", "+", x, ("const", 1)))) is True, False)

    def test_p6_every_version_keeps_the_branch(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i119-v-"))
        try:
            for v in ("holon-go-frontend/0.1", "holon-go-frontend/0.2"):
                fs = extract(dict(config(), config_version=v), tmp / v.replace("/", "_"))
                self.assertIn("panic", ends(fs[f"{PKG}.Inc64"]), v)
                self.assertEqual([s["status"] for s in fs[f"{PKG}.Idx"]["sites"] if s["kind"] == "index"], ["open"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p6_machines_read_the_same_rule(self):
        """go_machines builds its enumerator from the same Ctx: no config key turns the rule off."""
        src = (ROOT / "holon" / "frontends" / "go" / "paths.py").read_text(encoding="utf-8")
        self.assertIn("self.ctx.opaque_arith", src)
        self.assertNotIn("Reasoner(st.cond, self.nonnil, self.ctx.typed_ops)", src)

    def test_p6_narrow_loop_mode_unchanged(self):
        src = (ROOT / "holon" / "frontends" / "go" / "paths.py").read_text(encoding="utf-8")
        self.assertIn('("narrow", bits, unsigned, term)', src)


# ----------------------------------------------------------------------------------------------- P8: regressions
class TestRegressions(unittest.TestCase):
    def test_p8_ci_job_lists_classes(self):
        ci = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: tests-m6-i119", ci)
        for c in ("TestFixture", "TestDifferential", "TestAudit", "TestDefault", "TestRegressions"):
            self.assertIn(f"tests_m6.test_i119_go_reasoner_soundness.{c}", ci)

    def test_p8_no_bend_escape_hatch(self):
        bad = re.compile(r"\?TODO|@unsafe|import \"\./")
        for p in sorted((ROOT / "holon").rglob("*.py")):
            if "frontends/go" in str(p):
                self.assertIsNone(bad.search(p.read_text(encoding="utf-8")), str(p))

    def test_p8_audit_tool_reads_no_sealed_input(self):
        t = (ROOT / "tools" / "i119_audit.py").read_text(encoding="utf-8")
        for s in ("heldout3", "heldout/", "I113_candidates", "scroll-tech"):
            self.assertNotIn(s, t)


if __name__ == "__main__":
    unittest.main()
