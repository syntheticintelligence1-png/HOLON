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



class TestAmendGhost(unittest.TestCase):
    """Added after C_K (15650253) by the disclosed prereg amendment of the lead's calls on I98 (2026-11-09, after the
    outcome 40ce4b05 and before any build result for them; spec/M3/amendments/I98.jsonl, whose line for this class pins
    this docstring's sha256). Nothing above changes: R0-R6, P1-P6 and A0-A3 stand as preregistered. Where this ruling
    makes their outcome differ (P1's "it stays REFUTED", P3, A2), the report says so, and their checks are not edited.
    OUT/ghost.json and OUT/closure.json are written after the build.

    G  The ruling. G6 binds a REFUTED record only when its replay observes the obstruction on the real code. The one
       exception, GHOST_ONLY, is family-level and mechanical: a record whose obstruction is stated over ghost state
       alone binds on calls agreeing (a passed replay). G6's detail names GHOST_ONLY with the number of records it
       binds. holon.replay_bind.ghost_only(law, entry) -> (bool, [term]) decides it from the law's IR alone: the law's
       claim (laws/<M>/<law>.json), with the definition it applies expanded to that definition's terms in its
       laws/<M>/DERIVATION.json entry (a coercion: its member function and its read). The violated predicate names
       only generated ghost fields when none of those terms reads the code's state or inputs (storage, map, index,
       param, caller, env, call, outflow); the list is the code-observable terms it names. A claim applying any other
       definition (sym, disch, undo, fact, bundle, symb, square, wnat, own, gox, init) compares the code's state by its
       family's definition, so it is not ghost-only. Nothing names a law.
    G1 What each clause's replay observes (a record judged by several clauses is observed by each, or not bound):
       - typed (I30): the entry's obstruction_observed (holon.sorts.run3.replay_entry: a realize entry observes the
         real panic in its span; an as_member or a reinterpret entry observes nothing);
       - UNDO: the real runs with and without x;y diverge at t[diverges_at], where the model's do;
       - DISCH: blocked_before and discharged_after, on the real storage;
       - FACT, bundle (I86) and bundle2: the replay's pass rule reads the obstruction on the real code (holon.fact.run:
         a kernel law's commitments equal across runs whose consumers differ, an attr or pi law's bonded field the
         model's; holon.bundle.replay_laws and holon.bundle2.laws_replay: the frame's outcome, fee or field);
       - contract: the record's replay passed (no M3 contract law is REFUTED);
       - NAT and PAR-init: the side's obstruction_observed (holon.rules.nat_replay.side, holon.versions.replay.side);
       - go (own, gocount, goops, par): every side's obstruction_observed; gox: verdict agree; symb: agree; I40: every
         side passed with obstruction_observed;
       - sym (I34, replay/<M>/sym/report.json): nothing. Its replay compares the deployment's outcomes with the
         model's and evaluates the claim on the model with the deployment's call answers (holon.symd.run). It reads no
         word of the real state, so it does not observe the obstruction.
    G2 Predicted on M3 after the re-make (the typed replay, the FACT law re-made, the PAR library replay and the final
       filter, as in the outcome 40ce4b05), counted:
       - L_sort_tag_rollup_279_e01ea84a moves to UNKNOWN. Its typed entry passes with calls agreeing and
         obstruction_observed false. GHOST_ONLY does not apply: its predicate names the parameter batchDataInput (the
         member function reads its version) and the register batchBlobVersionedHashes (the read). Its law is kept.
       - The 13 SYM records bound to replay/M3/sym/report.json move to UNKNOWN: omega 6, pi 3, tau 4. GHOST_ONLY
         applies to none: their claims apply sym definitions (sink-reaching keys, outcomes, the Time words of logs).
       - No other record moves for this ruling, and GHOST_ONLY binds 0 records. With I98's earlier move (the version 2
         codec law), REFUTED M3 goes from 65 at the base (5b1fe820) to 50.
       - G6 passes after the re-make: all 50 REFUTED M3 records are judged and bound, each by a replay that observes
         its obstruction.
       OUT/ghost.json: {"refuted_base", "refuted_after", "moved": {law: {"rule", "subform", "clause", "why",
       "status", "bound", "witness_kept"}}, "ghost_only": {law: [term]}, "g6_after": {"passed", "detail",
       "unbound"}}, from the build's own runs.
    G3 The closure, counted. holon/replay_bind.py holds G6's judgement of every REFUTED record of the milestone's
       results (each clause above). The gates call it, and so does the final filter. It imports no gate: no
       holon/gate.py, holon/sorts/gate3.py or family gate is in its imports or theirs. The generator closure of
       holon-ir/0.2 and 0.3 is then the lead's (2b44372f, 217 files) plus holon/replay_bind.py, holon/gox/lawrun.py,
       holon/sorts/contract3_run.py and its imports holon/sorts/contract3.py, holon/sorts/residue.py and
       holon/sorts/residue_lemmas.py: 223 files, against 292 at 40ce4b05. OUT/closure.json: {"lead", "head",
       "added": [path]}.
    G4 A moved record is UNKNOWN as A3 states: a bound that names G6, the witness kept in its replay_binding attempt,
       its law file kept. Its checked LAWS.bend becomes its statement's emission, the bound emission of an UNKNOWN
       record (F39), with no proof artifact. The counter-law that Bend accepted stays in that attempt by sha256 (its
       LAWS.bend and its PROOF.bend), with its checker block, the replay and the kernels.
    G5 Knock-on, recorded, not counted.
       - E4 does not change: no moved law is in a row of results/M3/backtest.json, so the 4 exit blockers stay.
       - E2, from I96b's audit/blind/I96/compare.json read through git show. The tag law is lead_only. The 13 SYM
         classes are matched and agreeing, so each disagrees after the move. 204 of 207 (0.986) becomes 191 of 207
         (0.923), which is still at least I96b's agreement_min of 0.9.
       - Earlier contract checks that the ruling makes false are not edited. They are
         tests_m3/test_sort_types.py::TestPredictedOutcomes.test_commit_state_recommit_read_is_refuted_on_an_o26_path
         (I30-P1), and tests_m3/test_sym.py::TestPredictions.test_p1_o20_the_pi_split_over_the_submitter_role and
         test_p2_o19_analogue_reorder_refuted (I34-P1, I34-P2). None of them runs in CI.
    G6 A30's note at G6's typed clause ("flagged here, never absorbed into the status") is superseded by the lead's I98
       ruling: G6's refusal moves the status through the final filter.
    """
    TEST_ID = "tests_m3/test_g6_i98.py::TestAmendGhost"
    A30_ID = "tests_m3/test_g6_i98.py::TestAmendGhost.test_g6_a30_is_superseded"
    TAG = "L_sort_tag_rollup_279_e01ea84a"
    CLOSURE_ADDED = ["holon/gox/lawrun.py", "holon/replay_bind.py", "holon/sorts/contract3.py",
                     "holon/sorts/contract3_run.py", "holon/sorts/residue.py", "holon/sorts/residue_lemmas.py"]

    def _lines(self) -> list:
        src = (ROOT / "spec" / "M3" / "amendments" / "I98.jsonl").read_text(encoding="utf-8")
        return [json.loads(ln) for ln in src.splitlines() if ln.strip()]

    def test_g0_the_amendment_is_disclosed_and_pins_this_contract(self):
        lines = self._lines()
        mine = [a for a in lines if a.get("test") == self.TEST_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(type(self).__doc__.encode("utf-8")).hexdigest())
        agg = (ROOT / "spec" / "M3" / "amendments.jsonl").read_text(encoding="utf-8").splitlines()
        for a in mine + [a for a in lines if a.get("test") == self.A30_ID]:
            self.assertEqual(sum(1 for ln in agg if ln.strip() and json.loads(ln) == a), 1, a.get("test"))

    def test_g1_ghost_only_is_decided_from_the_ir(self):
        sys.path.insert(0, str(ROOT))
        from holon import replay_bind as RB
        law = json.loads((ROOT / "laws" / "M3" / f"{self.TAG}.json").read_text(encoding="utf-8"))
        dv = json.loads((ROOT / "laws" / "M3" / "DERIVATION.json").read_text(encoding="utf-8"))
        entry = next(e for e in dv["laws"] if e.get("law_id") == self.TAG)
        ok, terms = RB.ghost_only(law, entry)
        self.assertFalse(ok)
        self.assertIn("param batchDataInput", terms)
        self.assertIn("storage batchBlobVersionedHashes", terms)
        # the rule itself, on IR built here
        claim = {"eq": [{"coerce": "m:as_member:site:h", "from": {"var": "s"}, "on": {"var": "a"}}, {"bool": True}]}
        coerce = {"statement": {"claim": claim}}
        ghost = {"coercion": {"from": "A + B", "members": ["A", "B"], "member_fn": ["sort", "A"], "to": None},
                 "basis": {}}
        self.assertEqual(RB.ghost_only(coerce, ghost), (True, []))
        by_param = {"coercion": dict(ghost["coercion"], member_fn=["?", ["==", ["param", "p"], 2], ["sort", "A"],
                                                                  ["sort", "B"]]), "basis": {}}
        self.assertEqual(RB.ghost_only(coerce, by_param), (False, ["param p"]))
        by_read = dict(ghost, basis={"read": ["map", ["storage", "f"], ["param", "k"]]})
        self.assertEqual(RB.ghost_only(coerce, by_read), (False, ["param k", "storage f"]))
        sym = {"statement": {"claim": {"eq": [{"on": [{"var": "s"}], "sym": "m:omega:a:b"}, {"bool": True}]}}}
        self.assertFalse(RB.ghost_only(sym, None)[0])

    def test_g2_the_moves(self):
        g = _load("ghost.json")
        moved = g["moved"]
        self.assertIn(self.TAG, moved)
        self.assertEqual(Counter((v["rule"], v["subform"]) for v in moved.values()),
                         Counter({("SORT", "as_member"): 1, ("SYM", "omega"): 6, ("SYM", "pi"): 3, ("SYM", "tau"): 4}))
        self.assertEqual(g["ghost_only"], {})
        self.assertEqual((g["refuted_base"], g["refuted_after"]), (65, 50))
        for law, v in moved.items():
            self.assertEqual(v["status"], "UNKNOWN", law)
            self.assertIn("G6", v["bound"], law)
            self.assertTrue(v["witness_kept"], law)
            self.assertTrue((ROOT / "laws" / "M3" / f"{law}.json").is_file(), law)

    def test_g3_g6_names_the_rule_and_binds_every_record(self):
        g = _load("ghost.json")["g6_after"]
        self.assertTrue(g["passed"], g["detail"])
        self.assertEqual(g["unbound"], {})
        self.assertRegex(g["detail"], r"GHOST_ONLY[^;]*: 0 records")
        sys.path.insert(0, str(ROOT))
        from holon import replay_bind as RB
        _u, _e, g6 = RB.binding("M3", ROOT)
        self.assertRegex(g6["detail"], r"GHOST_ONLY[^;]*: \d+ records?")

    def test_g4_the_closure(self):
        src = (ROOT / "holon" / "replay_bind.py").read_text(encoding="utf-8")
        mods = re.findall(r"(?m)^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", src)
        self.assertFalse([m for m in mods if "gate" in "".join(m)], mods)
        c = _load("closure.json")
        self.assertEqual((c["lead"], c["head"]), (217, 223))
        self.assertEqual(sorted(c["added"]), self.CLOSURE_ADDED)
        sys.path.insert(0, str(ROOT))
        from holon import records as R
        files = set(R.generator_files("holon-ir/0.2", ROOT)) | set(R.generator_files("holon-ir/0.3", ROOT))
        self.assertEqual(sorted(f for f in files if "gate" in f.rsplit("/", 1)[-1]), [])

    def test_g5_a_moved_record_binds_its_statement(self):
        sys.path.insert(0, str(ROOT))
        from holon import bindings as B
        bound = json.loads((ROOT / "spec" / "bindings" / "M3.json").read_text(encoding="utf-8"))["laws"]
        for law in _load("ghost.json")["moved"]:
            rec = json.loads((ROOT / "results" / "M3" / f"{law}.json").read_text(encoding="utf-8"))
            if rec.get("status") != "UNKNOWN":
                continue    # not re-made here: G2 checks the outcome
            with self.subTest(law=law):
                text = (ROOT / rec["artifacts"]["laws"]).read_text(encoding="utf-8")
                self.assertEqual(B.text_sha256(text), bound[law]["statement_sha256"])
                self.assertIsNone(rec["artifacts"].get("proof"))
                att = [a for a in rec["attempts"] if a.get("kind") == "replay_binding"][-1]
                want = bound[law].get("counter_sha256")
                self.assertIn(att["counter_law"]["laws_sha256"], want if isinstance(want, list) else [want])

    def test_g6_a30_is_superseded(self):
        mine = [a for a in self._lines() if a.get("test") == self.A30_ID]
        self.assertEqual(len(mine), 1, mine)
        self.assertIn("never absorbed into the status", mine[0]["why"])
        self.assertNotIn("never absorbed into the status", (ROOT / "holon" / "sorts" / "gate3.py").read_text())
        self.assertIn("A30", (ROOT / "holon" / "replay_bind.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
