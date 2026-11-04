"""I96a (= I46c, first half): DISCH's R0 derived from the binding (BUILD_PLAN row I96a; the key I96a of
spec/M3/predictions.json). The instrument is tests_m3/_i96a.py. It imports nothing from holon/ or tools/ and reuses
I31's instrument (tests_m3/_i31.py). The instrument and this docstring are fixed at the prereg (C_K) and pinned by
sha256 in the key's thresholds.

Contract. <B> is the key's base_commit, S is the DISCH sidecar spec/M3/lib/disch.json, and OUT is audit/i96a/.

R  The rule. `python -m holon disch-r0 --milestone M3` reads S's documents and, for each, the deployment record
   gen/M3/binding/<stem>.json that `holon binding` writes. It writes S's "r0" and "model_sidecar" and nothing else.
   Paths are the layout's: the document's storage and inherited_storage declarations, with __gap skipped.
     values        A scalar path holds its deployed word, at its offset and width. A mapping family holds 0 plus the
                   deployed words of its written keys; for a struct family, each member path does, at the member's
                   slot, offset and width. A non-zero word whose declared type is an address (address, address
                   payable, or a contract or interface type) is "T". A path whose deployed words are all 0 is
                   unlisted ({0}). Lists are sorted, ints first.
     keys          {family: {key: null, or for a struct family its members made non-zero, in declaration order}}, for
                   each key whose entry holds a non-zero word, found through the record's 64-byte keccak256 preimages
                   (key . slot). Integer keys are decimal; address keys are 0x plus 40 lowercase hex digits; other keys
                   are 0x plus 64 lowercase hex digits.
     proxy_slots   The written non-zero slots that no layout path holds, as 0x plus 64 lowercase hex digits, sorted.
     derived_from  [{"document", "path", "sha256"}] of the deployment records, by document. "doc" states this rule.
   model_sidecar is the milestone's typing sidecar, spec/M3/lib/sort_types.json, written explicitly.
   holon/analysis/closure.py is unchanged and gets no default for it. "expected" is never written. S is written as
   JSON with indent 2, sorted keys and ASCII escapes, plus a newline. The step refuses with exit 2 when S, a
   deployment record or the typing sidecar is missing; when the documents' derivations disagree; or when a written
   slot lies in a region the rule does not read (an array family, or a nested mapping).
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  The build.
   B1  The step names no target. holon/disch/r0.py contains no identifier of <B>'s documents (_i96a.identifiers), and
       no slot, word, key or address of <B>'s deployment record (_i96a.literals).
   B2  `python -m holon disch-r0 --milestone M3 --check` exits 0 at HEAD. Two runs on a copy write byte-identical
       sidecars. A run changes no member of S except r0 and model_sidecar. --check exits 1 after one byte of S's r0
       changes, and exits 2 when the deployment record is missing.
   B3  I31's yardstick, tests_m3/test_disch.py::TestInstruments::test_r0_is_the_binding_deployment, holds on HEAD's
       derived r0.
   B4  The I96 brief, spec/M3/lib/blind_session_i96.md, holds no outcome: no status word, and no law id of the lead's
       tree. It names `python -m holon disch-r0 --milestone M3` after `python -m holon binding --milestone M3`.
P  The outcomes. OUT is written after C_K.
   P1  OUT/lead.json is {"authored": <B>'s r0, "derived": HEAD's r0, "diff": _i96a.field_diff(authored, derived)}.
       Its diff is exactly values._initializing and values._paused (authored [0], derived unlisted). keys and
       proxy_slots are equal. _i31.r0_sets of the document is the same under both.
   P2  OUT/remake.json is {"laws": {law: {"before", "after", "why"}}, "closure": {file: [changed top-level members]}}
       for the 41 DISCH laws of <B>, re-made with the derived r0. No decision moves: 28 PROVED, 8 REFUTED and
       5 UNKNOWN, law for law. closure.json and conjuncts.json change only in their "sidecar" stamp.
   P3  OUT/sandbox.json comes from a pack-like sandbox: the pack of the I96a build commit, with I95's committed
       authored files (audit/blind/I95/authored/) overlaid and the step run there. The step writes the session's r0
       equal to HEAD's (_i96a.r0_row: blind = lead), and model_sidecar spec/M3/lib/sort_types.json.
   P4  In the sandbox, the session's closure analysis (OUT/sandbox/closure.json, OUT/sandbox/conjuncts.json) equals
       the lead's on the r0 listing, classes, permission, dead, closure, kinds, checks and basis
       (_i96a.analysis_diff is {}).
   P5  In the sandbox, under the session's own typing, the 11 DISCH laws of I95's breakdown are re-decided. None
       moves into agreement with the lead: each stays UNKNOWN.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m3 import _i31 as D
from tests_m3 import _i96a as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I96a.json"


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


def _head_sidecar() -> dict:
    return json.loads((ROOT / I.SIDECAR).read_text(encoding="utf-8"))


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
        src = (ROOT / "tests_m3" / "_i96a.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_the_step_names_no_target(self):
        src = (ROOT / "holon" / "disch" / "r0.py").read_text(encoding="utf-8")
        base = _th()["base_commit"]
        hit = sorted(w for w in I.identifiers(ROOT, base) if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", src))
        self.assertEqual(hit, [])
        low = src.lower()
        self.assertEqual(sorted(x for x in I.literals(ROOT, base) if x in low), [])

    def test_r4_b2_the_step_reproduces(self):
        r = _holon("disch-r0", "--milestone", "M3", "--check")
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-2000:])
        self.assertEqual(I.step_properties(ROOT), {"byte_identical": True, "other_members_unchanged": True,
                                                   "check_after_byte_change": 1, "check_without_record": 2})

    def test_r5_b3_the_yardstick_holds_on_the_derived_r0(self):
        from tests_m3 import test_disch as T
        with open(os.devnull, "w") as sink:
            res = unittest.TextTestRunner(stream=sink).run(T.TestInstruments("test_r0_is_the_binding_deployment"))
        self.assertTrue(res.wasSuccessful(), [str(e[1])[-800:] for e in res.failures + res.errors])

    def test_r6_b4_the_brief_names_the_step(self):
        text = (ROOT / "spec" / "M3" / "lib" / "blind_session_i96.md").read_text(encoding="utf-8")
        self.assertFalse(I.STATUS_WORDS.search(text))
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        self.assertFalse([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", text) if w in ids])
        a = text.find("python -m holon binding --milestone M3")
        b = text.find("python -m holon disch-r0 --milestone M3")
        self.assertTrue(0 <= a < b, (a, b))


class TestOutcome(unittest.TestCase):
    def test_p1_the_lead_field_diff(self):
        th = _th()
        rec = _load("lead.json")
        authored = I.sidecar_at(ROOT, th["base_commit"])["r0"]
        derived = _head_sidecar()["r0"]
        self.assertEqual((rec["authored"], rec["derived"]), (authored, derived))
        diff = I.field_diff(authored, derived)
        self.assertEqual(rec["diff"], diff)
        self.assertEqual(sorted((d["field"], d["path"], d["authored"], d["derived"]) for d in diff),
                         [("values", "_initializing", [0], None), ("values", "_paused", [0], None)])
        for rel in _head_sidecar()["documents"]:
            doc = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(D.r0_sets(doc, authored), D.r0_sets(doc, derived), rel)

    def test_p2_the_lead_remake_moves_no_decision(self):
        rec = _load("remake.json")
        th = _th()["lead_disch_at_base"]
        self.assertEqual({l_: v["before"] for l_, v in rec["laws"].items()}, th["laws"])
        self.assertEqual(I.moved(rec["laws"]), [])
        self.assertEqual(rec["closure"], {"closure.json": ["sidecar"], "conjuncts.json": ["sidecar"]})

    def test_p3_the_session_r0_row(self):
        rec = _load("sandbox.json")
        row = I.r0_row(rec["session_sidecar"], _head_sidecar())
        self.assertEqual(rec["r0_row"], row)
        self.assertTrue(row["equal"], row)
        self.assertEqual(rec["session_sidecar"]["model_sidecar"], "spec/M3/lib/sort_types.json")

    def test_p4_the_session_analysis_equals_the_lead(self):
        rec = _load("sandbox.json")
        lead = ROOT / "gen" / "M3" / "disch"
        diff = I.analysis_diff(_load("sandbox/closure.json"), _load("sandbox/conjuncts.json"),
                               json.loads((lead / "closure.json").read_text(encoding="utf-8")),
                               json.loads((lead / "conjuncts.json").read_text(encoding="utf-8")))
        self.assertEqual(rec["analysis_diff"], diff)
        self.assertEqual(diff, {})

    def test_p5_the_eleven_under_the_session_typing(self):
        rec = _load("sandbox.json")
        eleven = {x["law_id"]: x["lead"] for x in _th()["i95_disch_disagreements"]}
        self.assertEqual({l_: v["lead"] for l_, v in rec["laws"].items()}, eleven)
        self.assertEqual(sorted(l_ for l_, v in rec["laws"].items() if v["sandbox"] == v["lead"]), [])
        self.assertEqual(sorted({v["sandbox"] for v in rec["laws"].values()}), ["UNKNOWN"])


if __name__ == "__main__":
    unittest.main()
