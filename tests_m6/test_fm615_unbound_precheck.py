"""F-M6-15 (HUMAN_ANSWERS Q113): `holon run --unbound unknown`'s pre-check binds the statement text the run's own
emitter writes, not the IR's fallback type names.

The defect. Under --unbound unknown the runner checks, before it decides a law, that the law's statement binds to its
model (holon.codecrun.unbound_error, over holon.bindings.kernel_cone). I115 built that pre-check's names from
holon.records.ir_roots_text, the IR's fallback type map, which renames a record carrier `Header` to `Hdr`. A linked
codec model names the carrier `R_Header` (holon.gen.linked), and no `Hdr`, so every bindable codec law over such a
model failed the pre-check and was recorded UNKNOWN undecided, although the decision after the pre-check (lines
285-290, on the emitted statement's own text) binds. The checker never ran on those laws: their UNKNOWN was an
instrument artifact, not a verdict.

The fix (holon.codecrun.precheck_text / emitted_text and the mirror in holon.mpipeline). The pre-check binds the
statement text the emitter produces, without deciding it, and falls back to ir_roots_text only where the emitter
refuses the statement. So the pre-check and the post-decision check can never disagree on a law the emitter can
express.

The fixtures are synthetic (tests_m6/fixtures/fm615 and tests_m3/fixtures/par_linked, a planted codec component; never
Morph or corpus code). The rule it guards:

  (a) a law over a model that defines R_<Type> and no Hdr binds under --unbound, and is decided exactly as without the
      flag (TestLinkedFixtureFlip.test_a_bindable_laws_are_decided_under_the_flag);
  (b) a truly unbindable law (a name no model defines) stays UNKNOWN with its binding error, and nothing crashes
      (TestPrecheckSeam.test_b_name_the_model_lacks_stays_unbound);
  (c) under --unbound the records are byte-identical to the run without it, compared as G1 compares
      (TestLinkedFixtureFlip.test_c_flag_changes_no_record).

Nothing here makes a law PROVED the checker did not accept: every verdict is Bend's, on the model, in the sandbox.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo  # noqa: F401  (frozen helpers)

FIX = ROOT / "tests_m6" / "fixtures" / "fm615"
MODEL = FIX / "model.bend"
# the planted linked codec component (tests_m3/fixtures/par_linked): a synthetic record codec, carrier Header -> R_Header
ADOPTION = "tests_m3/fixtures/par_linked/derive_extracted.json"
LINK = "tests_m3/fixtures/par_linked/link.json"
ROLE = "hdr_len"
M = "T615"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}


def holon(args, cwd, timeout=3600):
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


# ---------------------------------------------------------------------------------- the pre-check seam (unit, fast)
class TestPrecheckSeam(unittest.TestCase):
    """The rule at the seam, with no full run: the name the emitter writes binds where the IR's fallback name does
    not, and the fall-back happens only when the emitter refuses the statement."""

    @classmethod
    def setUpClass(cls):
        from holon import bend, codecrun, records
        cls.CR, cls.records = codecrun, records
        cls.cfg = bend.config(ROOT)
        cls.assertTrueFile = MODEL.is_file()

    def setUp(self):
        self.assertTrue(MODEL.is_file(), "tests_m6/fixtures/fm615/model.bend is missing")
        self.CR.UNBOUND = "unknown"

    def tearDown(self):
        self.CR.UNBOUND = None

    def test_a_emitter_name_binds(self):
        # the model defines R_Rec (as a linked model names R_<carrier>): the emitter's name resolves
        err = self.CR.unbound_error("law L:\n  for +r: M.R_Rec\n  {M.get0(r) == M.get0(r) : Bool}", MODEL, self.cfg)
        self.assertIsNone(err, err)

    def test_b_name_the_model_lacks_stays_unbound(self):
        # a name no model defines (the F-M6-05 shape): UNKNOWN with the binding error, nothing raised
        err = self.CR.unbound_error("law L:\n  for +r: M.Rec\n  {r == r : Bool}", MODEL, self.cfg)
        self.assertIsNotNone(err)
        self.assertIn("resolves to no kernel entry", err)

    def test_precheck_uses_the_emitter_text(self):
        law = {"law_id": "L_syn", "rule": "PAR", "statement": {"binders": [], "claim": {"eq": [{"obsv": "get0"},
                                                                                              {"obsv": "get0"}]}}}
        emitted = "law L:\n  for +r: M.R_Rec\n  {M.get0(r) == M.get0(r) : Bool}"
        self.assertEqual(self.CR.precheck_text(law, lambda: emitted), emitted)

    def test_precheck_falls_back_only_when_the_emitter_refuses(self):
        from holon.gen import codec01 as C1
        law = {"law_id": "L_syn", "rule": "PAR", "statement": {"binders": [], "claim": {"eq": [{"obsv": "get0"},
                                                                                              {"obsv": "get0"}]}}}

        def refuse():
            raise C1.Unsupported("planted: the emitter cannot express this statement")

        self.assertEqual(self.CR.precheck_text(law, refuse), self.records.ir_roots_text(law))

    def test_the_old_name_source_disagrees_with_the_model(self):
        # the witness of the defect: ir_roots_text would name a carrier the model does not define
        self.assertIn("R_Rec", MODEL.read_text(encoding="utf-8"))
        self.assertNotRegex(MODEL.read_text(encoding="utf-8"), r"\btype Rec\b")


# ------------------------------------------------------------------- the flip on a planted codec run (end to end)
class TestLinkedFixtureFlip(unittest.TestCase):
    """(a) and (c) over the planted linked codec component, decided by Bend in a scratch tree: with --unbound the
    bindable laws are decided (none wrongly UNKNOWN), and the records equal the run without the flag."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.ok = False
        cls.reason = ""
        c = holon(["codecs", "--milestone", M, "--root", str(cls.repo), "--adoption", ADOPTION, "--link", LINK],
                  cls.repo)
        if c.returncode != 0:
            cls.reason = "codecs: " + (c.stdout + c.stderr)[-1500:]
            return
        d = holon(["derive", "--milestone", M, "--catalog", "holon-rules/1.1", "--root", str(cls.repo), "--out",
                   str(cls.repo / "laws" / M), "--codec", f"gen/{M}/codec/{ROLE}.json"], cls.repo)
        if d.returncode != 0:
            cls.reason = "derive: " + (d.stdout + d.stderr)[-1500:]
            return
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-fm615-"))
        cls.runs = {}
        for tag, extra in (("flag", ["--unbound", "unknown"]), ("noflag", [])):
            r = holon(["run", "--milestone", M, "--out", str(cls.tmp / f"r_{tag}"),
                       "--gen-dir", str(cls.tmp / f"g_{tag}"), *extra], cls.repo)
            if r.returncode != 0:
                cls.reason = f"run {tag}: " + (r.stdout + r.stderr)[-1500:]
                return
            cls.runs[tag] = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                             for p in sorted((cls.tmp / f"r_{tag}").glob("L*.json"))}
        cls.ok = True

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo.parent, ignore_errors=True)
        if getattr(cls, "tmp", None):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _ready(self):
        if not self.ok:
            self.fail(self.reason)

    def test_a_bindable_laws_are_decided_under_the_flag(self):
        self._ready()
        flag = self.runs["flag"]
        self.assertTrue(flag, "no records")
        unbound = [k for k, r in flag.items() if "cannot be bound" in str(r.get("bound"))]
        self.assertEqual(unbound, [], f"{len(unbound)} law(s) wrongly recorded unbindable under the fix")
        decided = [k for k, r in flag.items() if r["status"] in ("PROVED", "REFUTED")]
        self.assertTrue(decided, {k: r["status"] for k, r in flag.items()})

    def test_c_flag_changes_no_record(self):
        self._ready()
        flag, noflag = self.runs["flag"], self.runs["noflag"]
        self.assertEqual(sorted(flag), sorted(noflag))
        diff = [k for k in flag if _g1(flag[k]) != _g1(noflag[k])]
        self.assertEqual(diff, [], f"records differ under the flag (G1-compared): {diff}")


# generator_sha256 and every timing field are stripped, and the scratch gen-dir path is normalised, exactly as G1
# compares two runs of the same tree
_PATH = re.compile(r"/g_(flag|noflag)/")


def _g1(o):
    if isinstance(o, dict):
        return {k: _g1(v) for k, v in o.items() if k != "generator_sha256" and k != "seconds"
                and not k.endswith("_seconds")}
    if isinstance(o, list):
        return [_g1(v) for v in o]
    if isinstance(o, str):
        return _PATH.sub("/gENV/", o)
    return o


if __name__ == "__main__":
    unittest.main()
