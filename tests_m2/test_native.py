"""I16: native C model (whitepaper §8.7 "the model compiles to a C library"; BUILD_PLAN I16).

`bend F.bend -o F.c` emits C and `bend F.bend -o F` builds a native binary (clang); both need a `main`
(BEND_PRIMER §2, `bend guide` "Tooling"). holon/gen/cdriver.py generates the driver that gives the M0
model a `main`; holon/model_native.py builds it and evaluates IR terms through the binary. The .mjs model
(holon/model_eval.py) stays the reference engine. If the C build fails, the plan's fallback applies:
keep .mjs, record the failure in results/M2/native.json, report a Surprise, and still produce the
per-edge records (on .mjs). A fallback is never silent: the prediction test fails and names it.

API these tests read:
  holon.model_native.NativeModel.build(facts_path) -> NativeModel   builds under holon.bend.build_dir()
      (the tests point HOLON_BUILD_DIR at a fresh directory, so nothing cached is reused)
  NativeModel.run_jobs(jobs) -> [[value, ..], ..]   same contract and value encoding as
      holon.model_eval.CompiledModel.run_jobs; an evaluation error is {"error": msg}. It executes only the
      built binary (the agreement test runs it with PATH empty, so neither node nor bend is reachable)
  NativeModel.binary (Path)   the native executable it runs: an ELF file under holon.bend.build_dir()
  NativeModel.c_source (Path) the C source bend emitted for it (`bend driver.bend -o driver.c`); its
      sha256 is native.json's c_source_sha256 (the C source is byte-identical across builds)
  holon.model_native.NativeBuildError   raised by build when bend or the C compiler fails; str(e) holds the
      captured compiler output, with the build directory's path replaced by "<build>" (so the text does
      not depend on where it was built)
  holon.gen.cdriver.generate(facts_path) -> {relative file name: text}   the driver sources, byte-identical
      across calls; any .bend file among them holds no escape hatch (BEND_PRIMER §3.2)

results/M2/native.json, one of:
  {"milestone": "M0", "status": "native", "c_source_sha256": 64 hex, "compiler": str,
   "laws": n, "candidates": N, "agree": N, "disagree": 0}
      candidates = every (law, candidate) pair holon.refute.candidates yields over the M0 laws (the whole
      candidate space, not stopped at the first hit); agree = pairs on which every claim term (both sides
      and every subterm, as holon.refute evaluates them) gives the same value on both engines
  {"milestone": "M0", "status": "fallback", "reason": the captured compiler error (normalized as in
   NativeBuildError; it must reappear in str(NativeBuildError) on a fresh build), "command": str,
   "exit_code": int != 0}

bend/notes/c_probe/: probe.bend (a small program with a `main`, no escape hatch) and RESULT.json
  {"emit_c_exit": int, "build_exit": int, "run_exit": int | null, "run_stdout": str | null}: the exit code
  of `bend probe.bend -o probe.c`, of `bend probe.bend -o probe`, and the binary's exit code and stdout
  (null when it did not build). The test re-runs all three.

Every refinement record's model_engine is "native" when native.json says native, else "mjs".
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._util import run_bend
from tests_m2 import _i16 as H
from tests_m2._m2 import ROOT, holon_module, laws, load_json


class _FreshBuild:
    """HOLON_BUILD_DIR points at a fresh directory for the class: native and .mjs are built from scratch."""

    @classmethod
    def setUpClass(cls):
        cls.build = Path(tempfile.mkdtemp(prefix="holon-i16-native-"))
        cls.old = os.environ.get("HOLON_BUILD_DIR")
        os.environ["HOLON_BUILD_DIR"] = str(cls.build)

    @classmethod
    def tearDownClass(cls):
        if cls.old is None:
            os.environ.pop("HOLON_BUILD_DIR", None)
        else:
            os.environ["HOLON_BUILD_DIR"] = cls.old
        shutil.rmtree(cls.build, ignore_errors=True)


def refuter_jobs(facts: dict) -> list[tuple[str, dict]]:
    """(law id, job) for every candidate of every M0 law, built the way holon.refute.search builds them."""
    R = holon_module("holon.refute")
    LG = holon_module("holon.gen.laws")
    ME = holon_module("holon.model_eval")
    out = []
    for lid, law in laws("M0").items():
        types = LG.binder_types(law)
        a, b = law["statement"]["claim"]["eq"]
        terms = [a, b] + [x for side in (a, b) for x in R.subterms(side)]
        pins = LG.collect_pins(law, facts)
        for _, env in R.candidates(law, facts, pins):
            out.append((lid, {"terms": terms, "env": {v: ME.value_in(types[v], env[v], facts) for v in types}}))
    return out


def norm(vals: list) -> list:
    """Evaluation errors compare as a class (messages differ between JS and C)."""
    return [{"error": True} if isinstance(v, dict) and "error" in v else v for v in vals]


class TestNativeRecord(_FreshBuild, unittest.TestCase):
    """Construction: the outcome of the native build is recorded explicitly, either way."""

    def test_native_record_is_explicit(self):
        rec = load_json(H.NATIVE)
        self.assertEqual(rec["milestone"], "M0")
        self.assertIn(rec["status"], ("native", "fallback"))
        MN = holon_module("holon.model_native")
        engines = {e: H.edge_record(e)["model_engine"] for e in H.EDGES}
        if rec["status"] == "fallback":
            self.assertIsInstance(rec["reason"], str)
            self.assertTrue(rec["reason"].strip(), "a fallback records the captured compiler error")
            self.assertIsInstance(rec["exit_code"], int)
            self.assertNotEqual(rec["exit_code"], 0)
            self.assertTrue(rec["command"].strip())
            with self.assertRaises(MN.NativeBuildError) as cm:
                MN.NativeModel.build(H.FACTS)
            self.assertIn(rec["reason"].strip(), str(cm.exception), "the recorded error reproduces")
            self.assertEqual(set(engines.values()), {"mjs"}, engines)
        else:
            self.assertRegex(rec["c_source_sha256"], H.HEX64)
            self.assertTrue(rec["compiler"].strip())
            nat = MN.NativeModel.build(H.FACTS)
            self.assertTrue(Path(nat.binary).resolve().is_relative_to(self.build.resolve()), nat.binary)
            self.assertEqual(Path(nat.binary).read_bytes()[:4], b"\x7fELF", "a native executable")
            self.assertTrue(Path(nat.c_source).resolve().is_relative_to(self.build.resolve()), nat.c_source)
            self.assertEqual(hashlib.sha256(Path(nat.c_source).read_bytes()).hexdigest(), rec["c_source_sha256"])
            self.assertEqual(set(engines.values()), {"native"}, engines)

    def test_c_probe_outcome_is_recorded_and_reproduces(self):
        probe = H.C_PROBE / "probe.bend"
        self.assertTrue(probe.is_file(), probe)
        text = probe.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^def main\b")
        for f in sorted(H.C_PROBE.rglob("*.bend")):
            self.assertEqual(H.escape_hatches(f.read_text(encoding="utf-8")), [], f)
        res = load_json(H.C_PROBE / "RESULT.json")
        tmp = Path(tempfile.mkdtemp(prefix="holon-i16-cprobe-"))
        try:
            code, out = run_bend([str(probe), "-o", str(tmp / "probe.c")], cwd=tmp)
            self.assertEqual(code, res["emit_c_exit"], out[-1500:])
            if code == 0:
                self.assertGreater((tmp / "probe.c").stat().st_size, 0)
            code, out = run_bend([str(probe), "-o", str(tmp / "probe")], cwd=tmp)
            self.assertEqual(code, res["build_exit"], out[-1500:])
            if code == 0:
                p = subprocess.run([str(tmp / "probe")], cwd=tmp, capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, res["run_exit"])
                self.assertEqual(p.stdout, res["run_stdout"])
            else:
                self.assertIsNone(res["run_exit"])
                self.assertIsNone(res["run_stdout"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if load_json(H.NATIVE)["status"] == "native":
            self.assertEqual((res["emit_c_exit"], res["build_exit"], res["run_exit"]), (0, 0, 0))

    def test_c_driver_is_generated_deterministically_without_escape_hatches(self):
        D = holon_module("holon.gen.cdriver")
        a, b = D.generate(H.FACTS), D.generate(H.FACTS)
        self.assertTrue(a)
        self.assertEqual(a, b)
        for name, text in sorted(a.items()):
            if name.endswith(".bend"):
                with self.subTest(file=name):
                    self.assertEqual(H.escape_hatches(text), [])


class TestNativeAgreement(_FreshBuild, unittest.TestCase):
    def test_native_agrees_with_mjs_on_every_refuter_candidate(self):
        """I16-P1: native and .mjs agree on 100% of the refuter's candidates (every candidate
        holon.refute.candidates yields for every M0 law; every claim term compared). A recorded fallback
        means the prediction was not met: the test fails and names it (BUILD_PLAN I16 risks: a Surprise)."""
        rec = load_json(H.NATIVE)
        if rec["status"] == "fallback":
            self.fail("I16-P1 not met: the native C model fell back to .mjs: " + str(rec.get("reason"))[:800])
        self.assertEqual(rec["status"], "native")
        MN = holon_module("holon.model_native")
        ME = holon_module("holon.model_eval")
        mjs = ME.CompiledModel.build(H.FACTS)
        nat = MN.NativeModel.build(H.FACTS)
        self.assertEqual(Path(nat.binary).read_bytes()[:4], b"\x7fELF", "the native engine is a native executable")
        jobs = refuter_jobs(mjs.facts)
        self.assertGreater(len(jobs), 0)
        a = mjs.run_jobs([j for _, j in jobs])
        path = os.environ.get("PATH")
        os.environ["PATH"] = ""  # the native side runs its binary only: no node, no bend
        try:
            b = nat.run_jobs([j for _, j in jobs])
        finally:
            if path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = path
        self.assertEqual(len(a), len(jobs))
        self.assertEqual(len(b), len(jobs))
        bad = [(lid, i) for i, ((lid, _), x, y) in enumerate(zip(jobs, a, b)) if norm(x) != norm(y)]
        self.assertEqual(bad[:20], [], f"{len(bad)} of {len(jobs)} candidates differ")
        self.assertEqual(rec["laws"], len(laws("M0")))
        self.assertEqual(rec["candidates"], len(jobs))
        self.assertEqual(rec["agree"], len(jobs))
        self.assertEqual(rec["disagree"], 0)


if __name__ == "__main__":
    unittest.main()
