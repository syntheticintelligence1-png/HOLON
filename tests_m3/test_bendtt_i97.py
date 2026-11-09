"""I97: the F-M3-13 fix, BendTT (G7) on M3 in CI and the six BendTT rejections classified (BUILD_PLAN row I97; the key
I97 of spec/M3/predictions.json). The instrument is tests_m3/_i97.py. It imports nothing from holon/ or tools/. The
instrument and this docstring are fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <B> is the key's base_commit, SIX the six records of round 3's F-M3-13 (_i97.SIX), and OUT is
docs/iterations/I97/.

R  The ruling (the lead, F-M3-13 high under Q8). A BendTT rejection of a proof that bend2 accepts is a cross-kernel
   disagreement unless a minimized repro shows BendTT rejecting a construct it does not implement (or cannot normalize
   within its kernel), not an invalid proof.
S  The build.
   S1  The registry spec/M3/lib/bendtt_constructs.json declares each unsupported construct: its name, the mechanical
       detection rule (holon.bend.construct_of) and its minimized repro, a PROOF.bend/LAWS.bend pair (with any model
       file) under tests_m3/fixtures/bendtt_i97/<construct>/, which bend2 accepts and BendTT rejects. It names no law.
   S2  holon.bend.classify_rejection(proof, cfg) is None when BendTT accepts the proof; otherwise {"class":
       "unsupported", "construct", "repro"} when a registered construct is detected in the proof, else {"class":
       "disagreement"}.
   S3  The record-making code (the shared bend2-then-BendTT check of holon/bundle/lawrun.py, which the Go and the
       member laws use, and every other place that records a BendTT verdict) records an unsupported rejection as the
       bendtt entry {"result": "unsupported", "reason": "<construct>: <repro>"}, independence_class I1, the status
       unchanged; a disagreement leaves the law undecided (UNKNOWN, the disagreement in its attempt), never decided on
       one kernel against the other. No law is dropped.
   S4  G7 (holon/gate.py) re-checks every decided proof with BendTT, as before. A rejection passes only when the
       record's bendtt entry is "unsupported" with a registered construct, holon.bend.construct_of detects that
       construct in the proof, and the construct's repro still has bend2 accept and BendTT reject. A record whose
       bendtt entry claims "checked" and whose re-check fails, fails G7.
   S5  CI (.github/workflows/holon-ci.yml) runs G7 for M3, and G4 and G6 where the budget allows; a check left out is
       named with its reason in the workflow and in the report.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  The build's checks.
   B1  Each registered repro has bend2 accept and BendTT reject (_i97.bend_pair).
   B2  The registry names no law id of the lead's tree, and holon/bend.py's classifier names no target.
   B3  holon.bend.classify_rejection classifies each of SIX's committed proofs as OUT/classification.json records.
   B4  The forged tree is refused: on a copy of HEAD with _i97.forge applied, `holon gate --milestone M3 --checks G7`
       fails, and its detail names every forged law.
   B5  The workflow holds an M3 job whose command runs `holon gate --milestone M3` with G7 among its checks.
P  The outcomes (OUT is written after C_K).
   P1  All six are unsupported constructs, none a real disagreement, in at most two constructs: one for the two Go
       laws and one for the four member laws (OUT/classification.json).
   P2  The six keep REFUTED, as single-kernel I1 records with their reason; no other M3 record changes status.
   P3  G7 passes on M3 at HEAD after the re-make (OUT/g7.json, from `holon gate --milestone M3 --checks G7`).
   P4  CI's M3 check set gains G7, G4 and G6, and each passes on the lead; G1 is left out, with its reason (its
       regeneration of M3's outputs exceeds a job's budget) (OUT/ci.json).
   P5  The forged tree is refused by CI's M3 check set: G7 fails and names all six (OUT/forge.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i97 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I97.json"
SKIP = {".git", "cache", "build", "node_modules"}


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _holon(*args, timeout=3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _registry() -> dict:
    return json.loads((ROOT / I.REGISTRY).read_text(encoding="utf-8"))


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = _holon("audit", "prereg", "--milestone", "M3", timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i97.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_the_repros_reproduce(self):
        reg = _registry()
        self.assertTrue(reg["constructs"])
        for c in reg["constructs"]:
            self.assertEqual(I.bend_pair(ROOT / c["repro"]), (True, False), c["name"])

    def test_r4_b2_the_registry_and_classifier_name_no_target(self):
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        text = (ROOT / I.REGISTRY).read_text(encoding="utf-8")
        self.assertEqual([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", text) if w in ids], [])
        src = (ROOT / "holon" / "bend.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?i)rollup|morph|messenger|batchdata|L1MessageQueue", src))

    def test_r5_b3_the_six_are_classified(self):
        from holon import bend
        got = {}
        for lid in I.SIX:
            rec = json.loads((ROOT / "results" / "M3" / f"{lid}.json").read_text(encoding="utf-8"))
            c = bend.classify_rejection(ROOT / rec["artifacts"]["proof"], bend.config(ROOT))
            got[lid] = c
        self.assertEqual(got, _load("classification.json")["laws"])

    def test_r6_b4_the_forged_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp) / "w"
            shutil.copytree(ROOT, w, ignore=lambda d, names: [n for n in names if Path(d) == ROOT and n in SKIP])
            forged = I.forge(w)
            code, checks = I.gate(w, "G7")
        self.assertTrue(set(I.SIX) <= set(forged), forged)
        self.assertNotEqual(code, 0)
        passed, detail = checks["G7"]
        self.assertFalse(passed)
        for lid in forged:
            self.assertIn(lid, detail)

    def test_r7_b5_ci_runs_g7_on_m3(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        runs = re.findall(r"holon gate --milestone M3 --checks ([A-Z0-9,]+)", wf)
        self.assertTrue(any("G7" in r.split(",") for r in runs), runs)


class TestOutcome(unittest.TestCase):
    def test_p1_the_six_are_unsupported_constructs(self):
        laws = _load("classification.json")["laws"]
        self.assertEqual(sorted(laws), sorted(I.SIX))
        self.assertEqual({v["class"] for v in laws.values()}, {"unsupported"})
        gox = {laws[l]["construct"] for l in I.SIX if l.startswith("L_par_gobr_")}
        sym = {laws[l]["construct"] for l in I.SIX if l.startswith("L_sym_")}
        self.assertEqual((len(gox), len(sym)), (1, 1))
        self.assertLessEqual(len(gox | sym), 2)

    def test_p2_the_six_keep_refuted_as_single_kernel(self):
        rec = _load("records.json")
        for lid in I.SIX:
            self.assertEqual((rec[lid]["status"], rec[lid]["bendtt"], rec[lid]["independence_class"]),
                             ("REFUTED", "unsupported", "I1"), lid)
        self.assertEqual(rec["other_status_changes"], [])

    def test_p3_g7_passes_on_m3(self):
        g7 = _load("g7.json")
        self.assertTrue(g7["passed"], g7.get("detail"))

    def test_p4_the_ci_check_set(self):
        ci = _load("ci.json")
        self.assertEqual(sorted(ci["added"]), ["G4", "G6", "G7"])
        self.assertTrue(all(ci["passed_on_lead"][c] for c in ci["added"]), ci["passed_on_lead"])
        self.assertIn("G1", ci["left_out"])

    def test_p5_the_forge_is_refused(self):
        f = _load("forge.json")
        self.assertFalse(f["g7_passed"])
        self.assertTrue(set(I.SIX) <= set(f["named"]), f["named"])


if __name__ == "__main__":
    unittest.main()
