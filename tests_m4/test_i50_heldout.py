"""I50: the held-out target's rules, run, replay and metrics (key I50, spec/M4/predictions.json).

Written after I49's extraction (gen/targets/scroll/facts/ScrollChain.extracted.json) and before derive or any rule ran
on the held-out target. The route, the generated sidecars' rules and the law checks are fixed in
spec/M4/lib/heldout_run.json; the predicted per-rule counts and rule classes are in the key.

Contract (the build must make every test here pass; it may add tests, never change these):

K1  `python -m holon target derive --target NAME [--check]` writes the four sidecars of rules Q1-Q4 to
    gen/targets/NAME/lib/, and, from a scratch root, the sort pass (gen/targets/NAME/sorts/), DISCH's closure
    (gen/targets/NAME/disch/) and the derivation (gen/targets/NAME/laws/: the laws, DERIVATION.json, REGISTRY.json)
    of the pinned catalog holon-rules/1.15 over the target's document, as test milestone T50. --check writes nothing
    and exits 0 iff a fresh run reproduces every file byte for byte.
K2  `python -m holon target run --target NAME` (target.json run.kind "typed") decides every law of the derivation
    with the runner the M3 pipeline uses for its rule, unchanged, and writes one result record per law and
    summary.json to results/targets/NAME/records/, the generated model and law files to gen/targets/NAME/run/, and
    results/targets/NAME/replay.json (one entry per REFUTED law: status passed, failed or not_run, with a reason).
K3  `python -m holon target gate --target NAME` runs I49's six checks, then L2, L9, L3, L5, L11 and L6, in that order.
K4  `python -m holon target sizes` fills the held-out row's obligations from gen/targets/NAME/laws/DERIVATION.json.
"""
from __future__ import annotations

import json
import shutil
import unittest
from collections import Counter

from tests_m4._m4 import ROOT, copy_repo, load_json, predictions
from tests_m4 import _i49 as H
from tests_m4.test_i49_heldout import holon, I49_CHECKS

KEY = "I50"
RUN = ROOT / "spec" / "M4" / "lib" / "heldout_run.json"
INSTRUMENTS = ["spec/M4/lib/heldout_run.json"]
NAME = "scroll"
DOC = "gen/targets/scroll/facts/ScrollChain.extracted.json"
LIB = ROOT / "gen" / "targets" / NAME / "lib"
LAWS = ROOT / "gen" / "targets" / NAME / "laws"
RECORDS = ROOT / "results" / "targets" / NAME / "records"
REPLAY = ROOT / "results" / "targets" / NAME / "replay.json"
LAW_CHECKS = ["L2", "L9", "L3", "L5", "L11", "L6"]
STATUSES = {"PROVED", "REFUTED", "UNKNOWN"}


def derivation() -> dict:
    return load_json(LAWS / "DERIVATION.json")


def counts() -> dict:
    return dict(sorted(Counter(f"{x['rule']}/{x['subform']}" for x in derivation()["laws"]).items()))


def m3(name: str) -> dict:
    return load_json(ROOT / "spec" / "M3" / "lib" / f"{name}.json")


def expected_sidecars() -> dict:
    """Rules Q1-Q4, recomputed from the development milestone's sidecars."""
    ts = f"gen/targets/{NAME}/lib/sort_types.json"
    st, un, di, fa = m3("sort_types"), m3("undo"), m3("disch"), m3("fact")
    return {
        "sort_types": {"sort_types_version": "holon-sort-types/0.1", "documents": [DOC], "seeds": st["seeds"],
                       "binding": None, "search": st["search"]},
        "undo": {"undo_version": "holon-undo/0.1", "sort_types": ts, "observation": un["observation"],
                 "premise": un["premise"], "search": un["search"]},
        "disch": {"disch_version": "holon-disch/0.1", "documents": [DOC], "binding": None, "model_sidecar": ts,
                  "hypotheses": {}, "search": di["search"]},
        "fact": {"fact_version": "holon-fact/0.1", "iteration": "I50", "documents": [DOC], "sort_types": ts,
                 "binding": None, "hypotheses": {}, "search": fa["search"], "measure": fa["measure"],
                 "term_size": fa["term_size"]},
    }


class TestPrereg(unittest.TestCase):
    def test_key_shape(self):
        k = predictions(KEY)
        self.assertEqual(k["tests"], ["tests_m4/test_i50_heldout.py"])
        self.assertEqual([p["id"] for p in k["predictions"]], [f"I50-P{i}" for i in range(1, 6)])
        self.assertEqual(k["thresholds"]["rule_catalog_version"], "holon-rules/1.15")
        self.assertEqual(k["thresholds"]["document_sha256"], H.sha256(ROOT / DOC))

    def test_instruments_pinned(self):
        pins = predictions(KEY)["thresholds"]["instrument_sha256"]
        self.assertEqual(sorted(pins), sorted(INSTRUMENTS))
        for rel in INSTRUMENTS:
            self.assertEqual(H.sha256(ROOT / rel), pins[rel], rel)


class TestDerive(unittest.TestCase):
    """K1; I50-P1, I50-P2."""

    def test_sidecars_follow_the_rules(self):
        for n, want in expected_sidecars().items():
            with self.subTest(sidecar=n):
                got = load_json(LIB / f"{n}.json")
                self.assertEqual({k: v for k, v in got.items() if k != "doc"}, want)

    def test_catalog_and_document(self):
        d = derivation()
        self.assertEqual(d["rule_catalog_version"], "holon-rules/1.15")
        self.assertEqual(d["milestone"], "T50")
        self.assertEqual({x["facts"] for x in d["laws"]}, {DOC})
        reg = load_json(LAWS / "REGISTRY.json")
        self.assertEqual(reg["statements"], {x["law_id"]: x["statement_hash"] for x in d["laws"]})
        self.assertEqual(sorted(p.stem for p in LAWS.glob("L*.json")), sorted(reg["statements"]))

    def test_p1_counts(self):
        self.assertEqual(counts(), predictions(KEY)["predictions"][0]["expected"])

    def test_p2_classes(self):
        want = predictions(KEY)["predictions"][1]["expected"]
        self.assertEqual(sorted(k for k, v in counts().items() if v > 0), want["derive"])
        self.assertEqual(sorted({k.split("/")[0] for k in counts()}), want["rules"])

    def test_derive_regenerates(self):
        p = holon(["target", "derive", "--target", NAME, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])


class TestRun(unittest.TestCase):
    """K2; I50-P3, I50-P4."""

    def test_every_law_has_a_record(self):
        ids = sorted(x["law_id"] for x in derivation()["laws"])
        summary = load_json(RECORDS / "summary.json")
        self.assertEqual(sorted(summary), ids)
        for lid in ids:
            rec = load_json(RECORDS / f"{lid}.json")
            self.assertEqual(rec["law_id"], lid)
            self.assertIn(rec["status"], STATUSES)
            self.assertEqual(summary[lid], rec["status"])

    def test_p4_statuses(self):
        want = predictions(KEY)["predictions"][3]["expected"]
        summary = load_json(RECORDS / "summary.json")
        sub = {x["law_id"]: f"{x['rule']}/{x['subform']}" for x in derivation()["laws"]}
        by = {}
        for lid, st in summary.items():
            by.setdefault(sub[lid], Counter())[st] += 1
        self.assertGreaterEqual(sum(1 for s in summary.values() if s == "PROVED"), want["proved_at_least"])
        for k in want["all_proved"]:
            with self.subTest(subform=k):
                self.assertEqual(set(by.get(k, Counter({"none": 1}))), {"PROVED"}, by.get(k))
        for k in want["all_unknown"]:
            with self.subTest(subform=k):
                self.assertEqual(set(by.get(k, Counter({"none": 1}))), {"UNKNOWN"}, by.get(k))

    def test_replay_entries(self):
        summary = load_json(RECORDS / "summary.json")
        rep = load_json(REPLAY)
        refuted = sorted(k for k, v in summary.items() if v == "REFUTED")
        self.assertEqual(sorted(rep["laws"]), refuted)
        for lid, e in rep["laws"].items():
            self.assertIn(e["status"], ("passed", "failed", "not_run"))
            self.assertTrue(e["reason"].strip())


class TestGate(unittest.TestCase):
    """K3; I50-P3."""

    def test_law_checks_pass(self):
        repo = copy_repo()
        try:
            p = holon(["target", "gate", "--target", NAME], cwd=repo)
            rep = load_json(repo / "results" / "targets" / NAME / "gate_report.json")
            self.assertEqual(list(rep["checks"]), I49_CHECKS + LAW_CHECKS, p.stdout[-2000:])
            for c in LAW_CHECKS:
                self.assertTrue(rep["checks"][c]["passed"], (c, rep["checks"][c]))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestSizes(unittest.TestCase):
    """K4; I50-P5."""

    def test_heldout_row_counted(self):
        rep = load_json(ROOT / H.SIZES)
        row = rep["rows"][3]
        self.assertEqual(row["id"], "heldout")
        self.assertIsNone(row["obligations"]["pending"])
        self.assertEqual(row["obligations"]["source"], f"gen/targets/{NAME}/laws/DERIVATION.json")
        self.assertEqual(row["obligations"]["by_rule_subform"], counts())
        self.assertEqual(row["obligations"]["total"], len(derivation()["laws"]))


class TestRegressions(unittest.TestCase):
    def test_r1_i49_checks_unchanged(self):
        """I50-R1: I49's six checks keep their verdicts: G8 still fails on the same two statements, the rest pass."""
        rep = load_json(ROOT / "results" / "targets" / NAME / "gate_report.json")
        for c in I49_CHECKS:
            self.assertEqual(rep["checks"][c]["passed"], c != "G8", (c, rep["checks"][c]))
        self.assertIn("ScrollChain.sol:748-750 (Block)", rep["checks"]["G8"]["detail"])

    def test_r2_no_rule_change(self):
        """I50-R2: holon/rules/ is the pin's, byte for byte (the brief: never edit holon/rules/ or the catalog)."""
        ch = H.pin_changes()
        self.assertEqual([f for f in ch["modified"] + ch["deleted"] + ch["added"] if f.startswith("holon/rules/")], [])

    def test_r3_outcomes_and_scan(self):
        """I50-R3: no M0-M3 outcome changes and no holon/ file names a target (I49's R2 and R3, re-run here)."""
        from tests_m4.test_i49_heldout import TestRegressions as R49
        t = R49()
        R49.test_r2_outcomes_unchanged(t)
        R49.test_r3_target_agnostic(t)


if __name__ == "__main__":
    unittest.main()
