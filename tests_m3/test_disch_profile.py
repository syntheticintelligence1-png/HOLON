"""I32 acceptance tests: DISCH II, discharge profiles (whitepaper Def 6.20, Prop 6.21, §8.4's DISCH row, §10.7), on the
test milestone T32, and the classification of I31's DISCH basis on M3. Preregistered with the key I32 of
spec/M3/predictions.json and the sidecar spec/M3/lib/disch_profile.json; the instrument is tests_m3/_i32.py (with
tests_m3/fixtures/disch_profile/i32.mjs), written without holon's profile code.

The contract (the build implements it; the tests check it):

C1  `python -m holon profile --milestone T32 [--root DIR]` exits 0 and writes, from the sidecar and the facts it
    names (spec/M1/facts/morph_rollup.json, M1's machine), for the sidecar's obligation (id "delay"):
    - gen/T32/model/<model>.bend: the machine model of the facts as holon.gen.machine generates it for M1;
    - gen/T32/profile/delay.json, the profile document: {"profile_version": "holon-disch-profile/0.1",
      "milestone": "T32", "obligation": "delay", "facts", "facts_sha256", "outcomes": [[cost, delay]] (every outcome
      of the one-occurrence search, unique, sorted), "frontier": [{"cost", "delay", "strategy": [move]}] (the
      Pareto-minimal outcomes, by cost), "dominated": [{"cost", "delay", "strategy", "by": [cost, delay]}] (every
      other outcome with a frontier point that dominates it), "class" (§5.7, from the frontier),
      "persistent": {"frontier": [{"cost", "delay", "strategy"}], "class"}, "schedule": {"H", "principals",
      "alphabet": [move]}, "tables": {"<cost>_<delay>": [row]}, "abstraction": {"deadlines": [dt], "horizon_s"}};
      a move is the hints' JSON ({"op", inputs...} or {"op": "wait", "dt"}); a row is {"turn", "hist": [[turn, i]],
      "move"}: at that turn, after the schedule moves hist (indices into the alphabet, each with the turn before
      which it was played), the strategy plays move;
    - gen/T32/profile/delay.bend, the profile module: s*, the alphabet, the schedules, the play and the checks;
    - laws/T32/REGISTRY.json and one law file per law: L_dp_delay_point_<c>_<d> for every frontier point (subform
      "profile_point", the §8.4 form: there is a table such that every schedule of at most H moves over the
      alphabet lets the play succeed within cost c and delay d), L_dp_delay_dominance ("profile_dominance": every
      strategy of at most dominance.strategy_moves moves ending in a successful target move has, for every frontier
      gap, cost >= the gap's cost or delay >= its delay), L_dp_delay_persistent_<c>_<d> for every persistent
      frontier point ("profile_persistent": a strategy with that outcome after which kappa is false), and
      L_dp_delay_abstraction ("profile_abstraction": the time abstraction's soundness at s*). Every law file has
      "law_id", "milestone": "T32", "rule": "DISCH", "subform", "facts", "facts_sha256" and a "statement" that
      names H, the principals, the alphabet and the bounds it quantifies over; REGISTRY.json lists every law id
      with its statement_hash ("sha256:" and the sha256 of the statement's canonical JSON: sorted keys, no
      whitespace, UTF-8);
    - gen/T32/<law_id>/LAWS.bend and PROOF.bend: the law in Bend (its header names the law id and the statement
      hash), and the proof, which imports LAWS.bend and the profile module and decides the law by evaluation;
    - results/T32/<law_id>.json: "law_id", "statement_hash", "status" (PROVED iff bend accepts PROOF.bend with ALL
      PROOFS CHECK and LAWS.bend states the law; otherwise UNKNOWN with what was tried), "checker", "disch_class"
      (the profile's class), "disch_profile": {"frontier": [[c, d]], "persistent": [[c, d]], "H", "exact": the
      sentence saying the profile is exact relative to the alphabets, the time abstraction and H}, and for a
      profile_point law its table as "witness"; results/T32/summary.json counts them;
    - gen/M3/disch/classification.json: {"classification_version": "holon-disch-classes/0.1", "milestone": "M3",
      "entries": [{"tag", "class", "disch_class", "by", "blk", "blk_status"}]}, the sidecar's classes.doc applied to
      I31's DISCH basis and records (tests_m3/_i32.py::classify).
    Two runs write laws/T32, gen/T32 and gen/M3/disch/classification.json byte for byte, and results/T32 equal up to
    keys named seconds (BUILD_PLAN I32 exit: "Profile laws regenerate byte-identically").
C2  No escape hatch in any T32 Bend file; no file of a generator closure (holon-ir/0.1-0.3, the typed, DISCH, UNDO
    and FACT runners) changes, and no M0-M3 law, record or Bend file, except gen/M3/disch/classification.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # frozen helpers
from tests_m3 import _i32 as I
from tests_m3._m3 import canonical_json, holon_module, item

T = "T32"
OB = "delay"
FAIL = "ALL PROOFS CHECK"
ESCAPES = re.compile(r"\?[A-Za-z_]\w*|\?TODO|@unsafe|\bdef\s+\w+\?\s*\(|import\s+\"[^\"]*\.c\"")


def strip_seconds(o):
    if isinstance(o, dict):
        return {k: strip_seconds(v) for k, v in o.items() if k != "seconds"}
    if isinstance(o, list):
        return [strip_seconds(v) for v in o]
    return o


def tree(root: Path, rels: list[str]) -> dict[str, bytes]:
    out = {}
    for rel in rels:
        p = root / rel
        if p.is_file():
            out[rel] = p.read_bytes()
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out[f.relative_to(root).as_posix()] = f.read_bytes()
    return out


class _Run:
    """One copy of the repository with holon profile --milestone T32 run twice, shared by the module."""
    repo = None
    first = None
    second = None
    p1 = p2 = None

    @classmethod
    def get(cls):
        if cls.repo is None:
            cls.repo = copy_repo()
            for rel in ("laws/T32", "gen/T32", "results/T32"):
                shutil.rmtree(cls.repo / rel, ignore_errors=True)
            (cls.repo / "gen/M3/disch/classification.json").unlink(missing_ok=True)
            cls.p1 = run_holon(["profile", "--milestone", T, "--root", str(cls.repo)], cwd=cls.repo, timeout=7200)
            cls.first = tree(cls.repo, ["laws/T32", "gen/T32", "results/T32", "gen/M3/disch/classification.json"])
            cls.p2 = run_holon(["profile", "--milestone", T, "--root", str(cls.repo)], cwd=cls.repo, timeout=7200)
            cls.second = tree(cls.repo, ["laws/T32", "gen/T32", "results/T32", "gen/M3/disch/classification.json"])
        return cls


def tearDownModule():
    if _Run.repo is not None:
        shutil.rmtree(_Run.repo.parent, ignore_errors=True)


def doc() -> dict:
    return load_json(ROOT / "gen" / T / "profile" / f"{OB}.json")


def law(lid: str) -> dict:
    return load_json(ROOT / "laws" / T / f"{lid}.json")


def rec(lid: str) -> dict:
    return load_json(ROOT / "results" / T / f"{lid}.json")


def point_id(c: int, d: int) -> str:
    return f"L_dp_{OB}_point_{c}_{d}"


# ------------------------------------------------------------------------------------------------ instrument
class TestInstrument(unittest.TestCase):
    """Constructions on the sidecar and the instrument alone (no holon profile code)."""

    def test_sstar_is_the_obligation(self):
        """s* (the sidecar's prefix on M1's machine): commitBatch reverts with reason 5 for n = 0 and with reason 15
        for n = 1, 2, 3, as laws/M1/L_disch_delay_nofree.json states."""
        r = I.run("sstar")
        self.assertEqual(r["reasons"], {"0": 5, "1": 15, "2": 15, "3": 15})

    def test_r1_frontier_and_the_dominated_proof_point(self):
        """I32-R1: the one-occurrence frontier at s* within 4 moves is {(1, 0), (0, 19)}, and (1000, 0) (the
        validity-proof route, L_disch_delay_prove) is an outcome dominated by (1, 0) (docs/M1_REPORT.md §2.1)."""
        item("I32", "I32-R1")
        f = I.frontier()
        self.assertEqual(f["frontier"], [[0, 19], [1, 0]])
        self.assertIn([1000, 0], [o[:2] for o in f["outcomes"]])


# ------------------------------------------------------------------------------------------------ the run
class TestRun(unittest.TestCase):
    def test_c1_runs_and_regenerates_byte_identically(self):
        """C1: the command exits 0 twice; laws/T32, gen/T32 and the classification byte for byte, results/T32 equal
        up to seconds; and the copy's outputs equal the committed ones."""
        r = _Run.get()
        self.assertEqual(r.p1.returncode, 0, r.p1.stdout[-3000:] + r.p1.stderr[-3000:])
        self.assertEqual(r.p2.returncode, 0, r.p2.stdout[-3000:] + r.p2.stderr[-3000:])
        self.assertTrue(r.first)
        for k in sorted(set(r.first) | set(r.second)):
            with self.subTest(file=k):
                a, b = r.first.get(k), r.second.get(k)
                if k.startswith("results/") and a and b:
                    self.assertEqual(strip_seconds(json.loads(a)), strip_seconds(json.loads(b)))
                else:
                    self.assertEqual(a, b)
        committed = tree(ROOT, ["laws/T32", "gen/T32", "results/T32", "gen/M3/disch/classification.json"])
        self.assertEqual(sorted(committed), sorted(r.first))
        for k in sorted(committed):
            with self.subTest(committed=k):
                if k.startswith("results/"):
                    self.assertEqual(strip_seconds(json.loads(committed[k])), strip_seconds(json.loads(r.first[k])))
                else:
                    self.assertEqual(committed[k], r.first[k])

    def test_c1_document_registry_and_laws(self):
        """C1: the profile document's outcomes, frontier and dominated points agree with each other and with the
        instrument's outcome set; the registry lists exactly the laws the document implies, each with its
        statement hash; every law file names T32, DISCH, its subform, the facts and their sha256."""
        d = doc()
        side = I.side()
        self.assertEqual(d["profile_version"], "holon-disch-profile/0.1")
        self.assertEqual((d["milestone"], d["obligation"], d["facts"]), (T, OB, side["facts"]))
        pts = [[f["cost"], f["delay"]] for f in d["frontier"]]
        self.assertEqual(pts, I.pareto(d["outcomes"]))
        for x in d["dominated"]:
            self.assertIn(x["by"], pts)
            self.assertTrue(x["by"][0] <= x["cost"] and x["by"][1] <= x["delay"])
        self.assertEqual(sorted(map(tuple, d["outcomes"])),
                         sorted({(f["cost"], f["delay"]) for f in d["frontier"]} |
                                {(x["cost"], x["delay"]) for x in d["dominated"]}))
        want = [point_id(c, dl) for c, dl in pts] + [f"L_dp_{OB}_dominance", f"L_dp_{OB}_abstraction"] + \
            [f"L_dp_{OB}_persistent_{f['cost']}_{f['delay']}" for f in d["persistent"]["frontier"]]
        reg = load_json(ROOT / "laws" / T / "REGISTRY.json")
        ids = sorted(e["law_id"] for e in reg["laws"])
        self.assertEqual(ids, sorted(want))
        for e in reg["laws"]:
            with self.subTest(law=e["law_id"]):
                lw = law(e["law_id"])
                self.assertEqual((lw["law_id"], lw["milestone"], lw["rule"]), (e["law_id"], T, "DISCH"))
                self.assertIn(lw["subform"], ("profile_point", "profile_dominance", "profile_persistent",
                                              "profile_abstraction"))
                self.assertEqual(lw["facts"], side["facts"])
                self.assertEqual(lw["facts_sha256"], hashlib.sha256((ROOT / side["facts"]).read_bytes()).hexdigest())
                self.assertEqual(e["statement_hash"], "sha256:" + hashlib.sha256(canonical_json(lw["statement"])).hexdigest())

    def test_c1_alphabet_is_the_e_closure(self):
        """C1 and the sidecar's schedule.doc: the document's schedule (H, principals) is the sidecar's, and its
        alphabet is the instrument's E-closure, in order."""
        d = doc()["schedule"]
        s = I.side()["schedule"]
        self.assertEqual((d["H"], d["principals"]), (s["H"], s["principals"]))
        self.assertEqual(d["alphabet"], I.alphabet())


# ------------------------------------------------------------------------------------------------ outcomes
class TestOutcomes(unittest.TestCase):
    def _point(self, pid: str, c: int, dl: int):
        item("I32", pid)
        lid = point_id(c, dl)
        r = rec(lid)
        self.assertEqual(r["status"], "PROVED", r.get("attempts"))
        table = doc()["tables"][f"{c}_{dl}"]
        self.assertEqual(r["witness"], table)
        res = I.check(table, doc()["schedule"]["alphabet"], c, dl)
        self.assertGreater(res["schedules"], 1)
        self.assertEqual(res["failures"], [])

    def test_p1_pay_point_robust(self):
        """I32-P1: the pay point (1, 0) in the §8.4 form, H = 2 over the challenger and anyone, is PROVED; its table
        survives every schedule (the instrument replays them all)."""
        self._point("I32-P1", 1, 0)

    def test_p2_wait_point_robust(self):
        """I32-P2: the wait point (0, 19) in the §8.4 form, the same H and principals, is PROVED; its table survives
        every schedule."""
        self._point("I32-P2", 0, 19)

    def test_p3_bounded_dominance(self):
        """I32-P3: L_dp_delay_dominance is PROVED; and by the instrument's exhaustive enumeration (at most 4 moves)
        no successful strategy has cost < 1 and delay < 19."""
        item("I32", "I32-P3")
        self.assertEqual(rec(f"L_dp_{OB}_dominance")["status"], "PROVED")
        inside = [o for o in I.outcomes() if o[0] < 1 and o[1] < 19]
        self.assertEqual(inside, [])

    def test_p4_persistent_profile_and_classes(self):
        """I32-P4: the persistent profile (kappa false after the target move) is {(0, 19)}, class delay, by the
        document and the instrument; the one-occurrence class is mixed; its laws are PROVED; every T32 record
        carries disch_class mixed."""
        item("I32", "I32-P4")
        d = doc()
        self.assertEqual([[f["cost"], f["delay"]] for f in d["persistent"]["frontier"]], [[0, 19]])
        self.assertEqual(I.persistent()["frontier"], [[0, 19]])
        self.assertEqual((d["class"], d["persistent"]["class"]), ("mixed", "delay"))
        self.assertEqual(I.classify_points(I.frontier()["frontier"]), "mixed")
        self.assertEqual(rec(f"L_dp_{OB}_persistent_0_19")["status"], "PROVED")
        for p in sorted((ROOT / "results" / T).glob("L_*.json")):
            with self.subTest(record=p.name):
                r = load_json(p)
                self.assertEqual(r["disch_class"], "mixed")
                self.assertEqual(r["disch_profile"]["frontier"], [[0, 19], [1, 0]])
                self.assertEqual(r["disch_profile"]["persistent"], [[0, 19]])
                self.assertIn("exact", r["disch_profile"])

    def test_p5_abstraction_sound(self):
        """I32-P5: L_dp_delay_abstraction is PROVED; and the instrument finds no dt in 0..60 where an alphabet
        move's outcome differs from its outcome at the greatest hinted deadline <= dt."""
        item("I32", "I32-P5")
        self.assertEqual(rec(f"L_dp_{OB}_abstraction")["status"], "PROVED")
        moves = [m for t in doc()["tables"].values() for m in (r["move"] for r in t)]
        res = I.abstraction(moves, doc()["schedule"]["alphabet"])
        self.assertGreater(res["checked"], 0)
        self.assertEqual(res["mismatches"], [])


# ------------------------------------------------------------------------------------------------ kernel
class TestKernel(unittest.TestCase):
    def test_every_law_checks_and_states_itself(self):
        """C1: every T32 record's status agrees with bend on its PROOF.bend (ALL PROOFS CHECK iff PROVED); LAWS.bend's
        header names the law id and the registry's statement hash; PROOF.bend imports ./LAWS.bend; no escape hatch
        in any T32 Bend file (C2)."""
        reg = load_json(ROOT / "laws" / T / "REGISTRY.json")
        for e in reg["laws"]:
            lid = e["law_id"]
            with self.subTest(law=lid):
                d = ROOT / "gen" / T / lid
                laws_text = (d / "LAWS.bend").read_text()
                self.assertIn(f"law_id: {lid}", laws_text)
                self.assertIn(e["statement_hash"], laws_text)
                self.assertIn("import ./LAWS.bend", (d / "PROOF.bend").read_text())
                code, out = run_bend(["PROOF.bend"], cwd=d, timeout=3600)
                self.assertEqual(code == 0 and FAIL in out, rec(lid)["status"] == "PROVED", out[-2000:])
        for p in sorted((ROOT / "gen" / T).rglob("*.bend")):
            with self.subTest(file=p.relative_to(ROOT).as_posix()):
                text = "\n".join(l.split("#", 1)[0] for l in p.read_text().splitlines())
                self.assertIsNone(ESCAPES.search(text))


# ------------------------------------------------------------------------------------------------ M3
class TestClassification(unittest.TestCase):
    def test_m3_classification_is_the_instruments(self):
        """C1 (construction): gen/M3/disch/classification.json's entries are tests_m3/_i32.py::classify on the
        committed I31 analysis and records."""
        d = load_json(ROOT / "gen" / "M3" / "disch" / "classification.json")
        self.assertEqual((d["classification_version"], d["milestone"]), ("holon-disch-classes/0.1", "M3"))
        self.assertEqual(d["entries"], I.classify())


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r2_no_closure_and_no_earlier_output_changes(self):
        """I32-R2 and C2: between the I32 prereg commit and HEAD, no file of the holon-ir/0.1-0.3 closures or of the
        typed, DISCH, UNDO and FACT runners' closures changes, and no file under laws/M0-M3, results/M0-M3 or
        gen/M0-M3 changes except gen/M3/disch/classification.json; M1's L_disch_delay_* records are unchanged."""
        item("I32", "I32-R2")
        R = holon_module("holon.records")
        files = set()
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            files |= set(R.generator_files(v, ROOT))
        for mod, attr in (("holon.sorts.run3", "GEN3"), ("holon.disch.run", "GEN_DISCH"), ("holon.undo.run", "GEN_UNDO"),
                          ("holon.fact.run", "GEN_FACT")):
            files |= set(getattr(holon_module(mod), attr))
        prereg = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H", "-1", "--grep", "^I32 prereg"],
                                capture_output=True, text=True).stdout.strip()
        self.assertTrue(prereg, "no I32 prereg commit")
        changed = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", prereg, "HEAD"],
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(f for f in changed if f in files), [])
        earlier = [f for f in changed if re.match(r"^(laws|results|gen)/M[0-3]/", f)
                   and f != "gen/M3/disch/classification.json"]
        self.assertEqual(earlier, [])
        for lid in ("L_disch_delay_nofree", "L_disch_delay_pay", "L_disch_delay_wait", "L_disch_delay_prove"):
            with self.subTest(record=lid):
                old = subprocess.run(["git", "-C", str(ROOT), "show", f"{prereg}:results/M1/{lid}.json"],
                                     capture_output=True, text=True).stdout
                self.assertEqual(json.loads(old), load_json(ROOT / "results" / "M1" / f"{lid}.json"))


if __name__ == "__main__":
    unittest.main()
