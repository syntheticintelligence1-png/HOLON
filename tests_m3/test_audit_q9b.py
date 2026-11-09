"""HUMAN_ANSWERS Q9b: same-family M3 audit rounds that cite the ruling count toward convergence (the human,
2026-11-09). The rule (holon/audit/rounds.py qualifies and RD1, holon/audit/converge.py) and the ruling's sidecar
spec/M3/lib/audit_rulings.json; the reading is tests_m3/_q9b.py, which applies I87's instrument unchanged.

  Q1 on every Q9b scenario, holon's validity, convergence, streak, counted rounds and per-round verdicts are the
     reading's, and holon's row for a counted Q9b round keeps family "same" and names the ruling in its why;
  Q2 without the sidecar, a same-family round citing the ruling is not admitted: I87's rule stands;
  Q3 the sidecar names the ruling HUMAN_ANSWERS Q9b and docs/HUMAN_ANSWERS.md holds its row, with the disclosure;
  Q4 every committed round of M3 is valid against the schema, and the committed status is the reading's.
"""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from tests_m3 import _i87 as I
from tests_m3 import _q9b as Q
from tests_m3.test_audit_loop import load, run_holon, scratch_root, validate, write_scratch

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec" / "schemas"


def holon_status(rounds: list, findings: list, *, with_rulings: bool = True) -> dict:
    root = scratch_root()
    try:
        write_scratch(root, "M9", rounds, findings)
        if with_rulings:
            shutil.copy(ROOT / "spec" / "M3" / "lib" / "audit_rulings.json",
                        root / "spec" / "M9" / "lib" / "audit_rulings.json")
        out = root / "status.json"
        p = run_holon(["audit", "converge", "--milestone", "M9", "--root", str(root), "--out", str(out)])
        if p.returncode != 0:
            raise AssertionError(p.stdout[-1500:] + p.stderr[-1500:])
        return load(out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


class TestQ9b(unittest.TestCase):
    def test_q1_rule_on_fixtures(self):
        """Q1: holon agrees with the reading on every Q9b scenario; a counted Q9b row keeps family "same"."""
        pol, rul = I.policy(), Q.rulings()
        for name, rounds, findings in Q.fixtures():
            with self.subTest(scenario=name):
                want = Q.converge(rounds, findings, pol, rul)
                got = holon_status(rounds, findings)
                self.assertEqual((not got["problems"], got["converged"], got["streak"], got["counted"]),
                                 (want["valid"], want["converged"], want["streak"], want["counted"]))
                self.assertEqual({r["round"]: (r["counted"], r["clean"]) for r in got["rounds"]}, want["rounds"])
                self.assertEqual(validate(got, SCHEMAS / "audit_status.schema.json"), [])
                for row in got["rounds"]:
                    rnd = next(r for r in rounds if r["round"] == row["round"])
                    if row["counted"] and Q.admitted(rnd, rul):
                        self.assertEqual(row["family"], "same")
                        self.assertTrue(row["why"].startswith("counted: a same-family round admitted by "
                                                              "HUMAN_ANSWERS Q9b"), row["why"])
        verdicts = [Q.converge(r, f, pol, rul) for _n, r, f in Q.fixtures()]
        self.assertEqual(sum(v["converged"] for v in verdicts), 2)
        self.assertEqual(sum(not v["valid"] for v in verdicts), 5)

    def test_q2_no_sidecar_no_admission(self):
        """Q2: without spec/<M>/lib/audit_rulings.json, three clean same-family rounds citing the ruling are invalid
        (RD1) and none is counted: I87's reading."""
        rounds = [Q.q9b_round(n, "M9", f"s{n}") for n in (1, 2, 3)]
        got = holon_status(rounds, [], with_rulings=False)
        want = I.converge(rounds, [], I.policy())
        self.assertFalse(want["valid"])
        self.assertEqual((not got["problems"], got["converged"], got["counted"]), (False, False, 0))
        self.assertTrue(any(p.startswith("RD1: round1:") for p in got["problems"]), got["problems"])

    def test_q3_the_ruling(self):
        """Q3: the sidecar names HUMAN_ANSWERS Q9b and discloses the shared family; HUMAN_ANSWERS holds the row."""
        rul = Q.rulings()
        self.assertEqual(rul["same_family_admitted"]["ruling"], Q.RULING)
        self.assertIn("builders' own family", rul["same_family_admitted"]["disclosure"])
        text = (ROOT / "docs" / "HUMAN_ANSWERS.md").read_text(encoding="utf-8")
        row = next((ln for ln in text.splitlines() if ln.startswith("| **Q9b**")), None)
        self.assertIsNotNone(row, "docs/HUMAN_ANSWERS.md has no Q9b row")
        for needed in ("`same`", "limitation", "fresh"):
            self.assertIn(needed, row)

    def test_q4_committed_rounds(self):
        """Q4: the committed M3 rounds are valid against the schema, and results/M3/audit_status.json is the
        reading's (converged, streak, counted, per-round verdicts)."""
        schema = SCHEMAS / "audit_round.schema.json"
        rounds = [load(p) for p in sorted((ROOT / "audit" / "rounds" / "M3").glob("round*.json"))]
        for r in rounds:
            self.assertEqual(validate(r, schema), [], r.get("round"))
        findings = [json.loads(x) for x in (ROOT / "audit" / "M3_findings.jsonl").read_text().splitlines() if x.strip()]
        want = Q.converge(rounds, findings, I.policy(), Q.rulings())
        st = load(ROOT / "results" / "M3" / "audit_status.json")
        self.assertTrue(want["valid"], want["problems"])
        self.assertEqual((st["converged"], st["streak"], st["counted"]),
                         (want["converged"], want["streak"], want["counted"]))
        self.assertEqual({r["round"]: (r["counted"], r["clean"]) for r in st["rounds"]}, want["rounds"])


if __name__ == "__main__":
    unittest.main()
