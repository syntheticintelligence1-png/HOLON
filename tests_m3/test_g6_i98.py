"""I98: G6 on M3, the two REFUTED records G6 refuses, one rule for the final filter and G6, and G6 in CI (BUILD_PLAN row
I98; the key I98 of spec/M3/predictions.json). The instrument is tests_m3/_i98.py. It imports nothing from holon/ or
tools/. The instrument and this docstring are fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.

Contract. <B> is the key's base_commit (I97's head), TWO the two REFUTED records G6 refuses at <B> (_i98.TWO), and OUT
is docs/iterations/I98/.

R  The ruling (the lead's I98 brief). G6 binds every REFUTED record to a passed replay on the real contract. A record G6
   refuses is one of two things: a harness or binding defect, fixed in the harness or a generator and then replayed
   again; or a witness that does not reproduce on the real contract, which leaves REFUTED for UNKNOWN through a
   generator or the final filter, recorded with what was tried. No law is dropped, and no record is edited by hand.
S  The build.
   S1  Each of TWO is diagnosed, with its evidence, in OUT/diagnosis.json: {"laws": {law: {"class": "harness" or
       "not_reproduced", "evidence", "fix"}}}.
   S2  One rule. holon.replay_bind.unbound(milestone, root) is {law: [why]} for the REFUTED records G6 refuses, from
       G6's own clauses: every clause of G6 that judges a REFUTED record reports its judgment through holon.replay_bind,
       so G6 and unbound(...) cannot differ. holon.replay_bind.examined(milestone, root) is the set of REFUTED records
       some G6 clause judges. The final filter (`holon refute --milestone M3 --only filter`) takes every record that
       unbound("M3", root) names out of REFUTED: status UNKNOWN, a bound that names G6's refusal, and an attempt that
       keeps the witness and the replay; it bins no such record. So every record of a family G6 judges that the final
       filter leaves REFUTED is G6-bound.
   S3  CI (.github/workflows/holon-ci.yml) runs G6 on M3: an M3 job's `holon gate --milestone M3 --checks <list>` holds
       G6.
   S4  The sweep: OUT/sweep.json {"refuted": n, "examined": [law], "not_examined": {law: {"rule", "subform",
       "replay"}}} over the REFUTED M3 records after the re-make, "replay" being the record's own replay status.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, and the instrument imports nothing from holon/
   or tools/.
B  The build's checks.
   B1  The planted tree is refused: on a copy of HEAD with _i98.plant applied (the report entries of _i98.PLANTED
       removed), `holon gate --milestone M3 --checks G6` fails, and its detail names every planted law.
   B2  On that planted copy, the final filter takes every planted law to UNKNOWN, with a bound that names G6, and G6's
       detail then names no planted law.
   B3  The workflow holds an M3 job whose `holon gate --milestone M3 --checks <list>` holds G6.
   B4  holon/replay_bind.py names no target: no law id of the lead's tree and no contract of the target.
   B5  At HEAD, G6 passes exactly when unbound("M3", ROOT) is empty, and G6's detail names every law it holds.
P  The outcomes (OUT is written after C_K).
   P1  L_sort_tag_rollup_279_e01ea84a is a harness defect: `holon run` rewrites replay/M3/sorts/report.json with only
       the laws of its own run, which dropped the law's entry (present at 7198eb50 and 6df08eb6, gone at c8f646b7, I68's
       re-make of :363). Replayed again, its entry passes with the record's trace, and it stays REFUTED.
   P2  L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter is a harness defect (I26's own
       diagnosis): the replay's model run answers, from the refinement hints, the call lookup of an `||` operand the
       real code skips (the verifier call at proveState), so the model's observation lists a call the deployment does
       not make. With the replay evaluating the witness's steps on the environment the witness states, it passes, and
       the law stays REFUTED.
   P3  G6 passes on M3 after the re-make (OUT/g6.json, from `holon gate --milestone M3 --checks G6`), unbound("M3") is
       empty, and no M3 record changes status (OUT/records.json).
   P4  CI's M3 job runs G6 beside G7 and G4, and G6 passes on the lead after the re-make (OUT/ci.json).
   P5  The planted tree is refused and then filtered as B1 and B2 state (OUT/plant.json).
   P6  The sweep: 34 REFUTED M3 records are judged by no G6 clause, the PAR (14), SYM (17) and OWN (3) laws. 30 of them
       name a passed replay of their own family; the other 4, PAR cross_component_codec (3) and domain_coherence (1),
       name none (replay not_run).
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
from collections import Counter
from pathlib import Path

from tests_m3 import _i98 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I98.json"
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
        src = (ROOT / "tests_m3" / "_i98.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))


class TestBuild(unittest.TestCase):
    def test_r3_b1_b2_the_planted_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp) / "w"
            shutil.copytree(ROOT, w, ignore=lambda d, names: [n for n in names if Path(d) == ROOT and n in SKIP])
            planted = I.plant(w)
            self.assertEqual(planted, sorted(I.PLANTED))
            code, checks = I.gate(w, "G6")
            self.assertNotEqual(code, 0)
            passed, detail = checks["G6"]
            self.assertFalse(passed)
            for law in planted:
                self.assertIn(law, detail)
            self.assertEqual(I.final_filter(w), 0)
            for law in planted:
                st, bound = I.status(w, law)
                self.assertEqual(st, "UNKNOWN", law)
                self.assertIn("G6", bound or "", law)
            _code, checks = I.gate(w, "G6")
            for law in planted:
                self.assertNotIn(law, checks["G6"][1])

    def test_r4_b3_ci_runs_g6_on_m3(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        runs = re.findall(r"holon gate --milestone M3 --checks ([A-Z0-9,]+)", wf)
        self.assertTrue(any("G6" in r.split(",") for r in runs), runs)

    def test_r5_b4_replay_bind_names_no_target(self):
        ids = {p.stem for p in (ROOT / "laws" / "M3").glob("L*.json")}
        src = (ROOT / "holon" / "replay_bind.py").read_text(encoding="utf-8")
        self.assertEqual([w for w in re.findall(r"\bL_[A-Za-z0-9_]+", src) if w in ids], [])
        self.assertFalse(re.search(r"(?i)rollup|morph|messenger|batchdata|L1MessageQueue", src))

    def test_r6_b5_one_rule_at_head(self):
        sys.path.insert(0, str(ROOT))
        from holon import replay_bind
        unbound = replay_bind.unbound("M3", ROOT)
        self.assertTrue(set(unbound) <= set(replay_bind.examined("M3", ROOT)))
        _code, checks = I.gate(ROOT, "G6")
        passed, detail = checks["G6"]
        self.assertEqual(passed, not unbound, detail)
        for law in unbound:
            self.assertIn(law, detail)


class TestOutcome(unittest.TestCase):
    def test_p1_p2_the_two_are_harness_defects(self):
        d = _load("diagnosis.json")["laws"]
        self.assertEqual(sorted(d), sorted(I.TWO))
        for law in I.TWO:
            self.assertEqual(d[law]["class"], "harness", law)

    def test_p3_g6_passes_after_the_remake(self):
        g6 = _load("g6.json")
        self.assertTrue(g6["passed"], g6.get("detail"))
        self.assertEqual(g6["unbound"], {})
        rec = _load("records.json")
        for law in I.TWO:
            self.assertEqual(rec[law]["status"], "REFUTED", law)
        self.assertEqual(rec["other_status_changes"], [])

    def test_p4_ci_runs_g6(self):
        ci = _load("ci.json")
        self.assertIn("G6", ci["checks"])
        self.assertTrue({"G7", "G4"} <= set(ci["checks"]))
        self.assertTrue(ci["passed_on_lead"]["G6"])

    def test_p5_the_planted_tree(self):
        p = _load("plant.json")
        self.assertEqual(sorted(p["planted"]), sorted(I.PLANTED))
        self.assertFalse(p["g6_passed"])
        self.assertTrue(set(I.PLANTED) <= set(p["named"]))
        self.assertEqual({law: s for law, s in p["filtered"].items()}, {law: "UNKNOWN" for law in I.PLANTED})
        self.assertEqual(p["named_after_filter"], [])

    def test_p6_the_sweep(self):
        s = _load("sweep.json")
        ne = s["not_examined"]
        self.assertEqual(len(ne), 34)
        self.assertEqual(Counter(v["rule"] for v in ne.values()), Counter({"PAR": 14, "SYM": 17, "OWN": 3}))
        self.assertEqual(Counter(v["replay"] for v in ne.values()), Counter({"passed": 30, "not_run": 4}))
        self.assertEqual(Counter(v["subform"] for v in ne.values() if v["replay"] == "not_run"),
                         Counter({"cross_component_codec": 3, "domain_coherence": 1}))


class TestAmendAll(unittest.TestCase):
    """Added after C_K (15650253) by the disclosed prereg amendment of the lead's ruling of 2026-11-09, which widens I98
    (spec/M3/amendments/I98.jsonl; its line for this class pins this docstring's sha256). Nothing above changes: R0-R6
    and P1-P6 stand as preregistered. These checks are the amendment's, not counted predictions of the key.

    W  The widening. G6 judges every REFUTED M3 record. A record of a family that no clause judged before (the PAR, SYM
       and OWN laws outside the bundle laws) is judged in one of two ways. Either it is bound to its family's passed
       replay, like the other clauses: the witness identity the replay names (its sha256, or its trace), strict sides
       (every side passed) and the sides' provenance. Or it is exempt by a spec rule over a family or a witness kind,
       which G6 names in its detail with a count per rule, applied uniformly; never a per-law exemption or a list of law
       ids (AGENTS rule 2). A record that must replay and has none gets a replay through its generator or runner. When
       none can be made, or its witness does not reproduce on the real target, it leaves REFUTED for UNKNOWN through
       code (the final filter's one rule, S2), disclosed, and its law is kept.
    A1 The clauses. holon.replay_bind.examined("M3", root) holds every REFUTED M3 record, at HEAD and after the re-make,
       and G6's detail names each clause with the number of records it judges, and each exemption rule with its count.
    A2 Each family after the re-make (OUT/families.json: {family: {"rule", "subform", "records", "bound", "exempt":
       {rule: n}, "moved": [law]}}), as predicted:
       - OWN alias and lost_write (3): bound to replay/M3/own/report.json;
       - PAR branch (1): bound to replay/M3/gocount/report.json; PAR totality (1), weak (1) and the Go domain_coherence
         law (1): bound to replay/M3/goops/report.json;
       - PAR init_chain (1): bound to replay/M3/versions/report.json;
       - PAR go_branch (2) and go_recompute (1): bound to replay/M3/gox/<law>.json;
       - SYM member_tau (3) and sentinel_inv (1): bound to replay/M3/symb/<law>.json;
       - SYM omega (6), pi (3) and tau (4): bound to replay/M3/sym/report.json;
       - PAR cross_component_codec: the version 0 and version 1 laws (2) bound to their I40 sides in
         replay/M3/refute/report.json (go and solidity, each passed and observing its part), the version 2 law (1) moved
         to UNKNOWN;
       - the Solidity domain_coherence law (1): moved to UNKNOWN;
       - PAR link_domain (2): judged by the bundle2 clause, as before.
       No family is exempt: no spec rule exempts any of them. So 30 bind, 0 are exempt and 2 move.
    A3 The moved records are UNKNOWN after the re-make, each with a bound that names G6 and an attempt that keeps its
       witness, and their law files stay.
    """
    TEST_ID = "tests_m3/test_g6_i98.py::TestAmendAll"

    def test_a0_the_amendment_is_disclosed_and_pins_this_contract(self):
        src = (ROOT / "spec" / "M3" / "amendments" / "I98.jsonl").read_text(encoding="utf-8")
        mine = [a for a in (json.loads(ln) for ln in src.splitlines() if ln.strip()) if a.get("test") == self.TEST_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(type(self).__doc__.encode("utf-8")).hexdigest())
        agg = (ROOT / "spec" / "M3" / "amendments.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for ln in agg if ln.strip() and json.loads(ln) == mine[0]), 1)

    def test_a1_every_refuted_record_is_judged(self):
        sys.path.insert(0, str(ROOT))
        from holon import replay_bind
        refuted = set()
        for p in (ROOT / "results" / "M3").glob("L*.json"):
            if json.loads(p.read_text(encoding="utf-8")).get("status") == "REFUTED":
                refuted.add(p.stem)
        self.assertEqual(sorted(refuted - set(replay_bind.examined("M3", ROOT))), [])

    def test_a2_the_families(self):
        fam = _load("families.json")
        total = Counter()
        for f, v in fam.items():
            self.assertEqual(v.get("exempt") or {}, {}, f)
            total["bound"] += v["bound"]
            total["moved"] += len(v["moved"])
        self.assertEqual((total["bound"], total["moved"]), (30, 2))
        moved = Counter()
        for f, v in fam.items():
            for law in v["moved"]:
                moved[(v["rule"], v["subform"])] += 1
        self.assertEqual(moved, Counter({("PAR", "cross_component_codec"): 1, ("PAR", "domain_coherence"): 1}))

    def test_a3_the_moved_records(self):
        fam = _load("families.json")
        rec = _load("records.json")
        for v in fam.values():
            for law in v["moved"]:
                self.assertEqual(rec[law]["status"], "UNKNOWN", law)
                self.assertIn("G6", rec[law]["bound"], law)
                self.assertTrue(rec[law]["witness_kept"], law)
                self.assertTrue((ROOT / "laws" / "M3" / f"{law}.json").is_file(), law)


if __name__ == "__main__":
    unittest.main()
