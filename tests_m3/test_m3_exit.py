"""The M3 exit record, docs/M3_EXIT.md: I46's decision under spec/M3/lib/blind_rerun.json's rule, "the M3 exit is
met iff E1-E5 all hold". Each clause holds by its instrument or by the human's adjudication, and the record says
which.

  X1 E1: `holon report --milestone M3 --check` passes (REPORT OK).
  X2 E2: in audit/blind/I96/compare.json, M3's matched classes are at least min_matched and its agreement is at least
     the threshold.
  X3 E3: results/M3/audit_status.json has converged true. Every round of its streak is counted and clean, with A1,
     A2 and A4 records that ran: at least one mutant, one hostile case and one classified law.
  X4 E4: results/M3/backtest.json's exit blockers are none, or exactly those an adjudication of
     spec/M3/lib/exit_rulings.json covers (HUMAN_ANSWERS Q44).
  X5 E5: the adjudication of spec/M3/lib/exit_rulings.json holds (HUMAN_ANSWERS Q43, bound to its record's sha256).
  X6 the record's clause table states each clause's verdict and how it holds, as X1-X5 compute them, and the decision
     line states that the exit is met iff they all hold.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from tests_m3._m3 import run_holon

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "M3_EXIT.md"
PROTOCOL = ROOT / "spec" / "M3" / "lib" / "blind_rerun.json"
RULINGS = ROOT / "spec" / "M3" / "lib" / "exit_rulings.json"
COMPARE = ROOT / "audit" / "blind" / "I96" / "compare.json"
STATUS = ROOT / "results" / "M3" / "audit_status.json"
BACKTEST = ROOT / "results" / "M3" / "backtest.json"
ROUNDS = ROOT / "audit" / "rounds" / "M3"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def clauses() -> dict:
    """{clause: (holds, how)}: how is "instrument" or the ruling of the adjudication it rests on."""
    ex, rul = load(PROTOCOL)["exit"], load(RULINGS)["clauses"]
    out = {}
    out["E1"] = ("REPORT OK" in run_holon(["report", "--milestone", "M3", "--check"], timeout=1800).stdout, "instrument")
    m3 = load(COMPARE)["milestones"]["M3"]
    out["E2"] = (m3["matched"] >= ex["min_matched"] and m3["agree"] >= ex["threshold"] * m3["matched"], "instrument")
    out["E3"] = (load(STATUS).get("converged") is True, "instrument")
    blockers = load(BACKTEST)["exit_blockers"]
    if not blockers:
        out["E4"] = (True, "instrument")
    else:
        e4 = rul.get("E4") or {}
        out["E4"] = (e4.get("blockers") == blockers and e4.get("holds") is True, e4.get("ruling", "none"))
    e5 = rul.get("E5") or {}
    rec = ROOT / e5.get("record", "")
    ok = rec.is_file() and hashlib.sha256(rec.read_bytes()).hexdigest() == e5.get("record_sha256")
    out["E5"] = (bool(ok) and e5.get("holds") is True, e5.get("ruling", "none"))
    return out


class TestM3Exit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = clauses()

    def test_x1_to_x5_every_clause_holds(self):
        for name, (holds, how) in sorted(self.c.items()):
            with self.subTest(clause=name, how=how):
                self.assertTrue(holds)

    def test_x3_the_streak_did_work(self):
        st = load(STATUS)
        streak = [r for r in st["rounds"] if r["counted"]][-st["streak"]:]
        self.assertEqual(len(streak), st["streak"])
        for r in streak:
            with self.subTest(round=r["round"]):
                self.assertTrue(r["clean"])
                d = ROUNDS / f"round{r['round']}"
                self.assertTrue(load(d / "a1.json")["mutations"])
                self.assertTrue(load(d / "a2.json")["cases"])
                self.assertTrue(load(d / "a4.json")["laws"])

    def test_x6_the_record_states_them(self):
        text = RECORD.read_text(encoding="utf-8")
        for name, (holds, how) in self.c.items():
            with self.subTest(clause=name):
                rows = [ln for ln in text.splitlines() if ln.startswith(f"| {name} |")]
                self.assertEqual(len(rows), 1, f"one table row for {name}")
                cells = [x.strip() for x in rows[0].strip("|").split("|")]
                self.assertEqual(cells[2], "yes" if holds else "no")
                self.assertEqual(cells[3], "instrument" if how == "instrument" else f"adjudication ({how})")
        met = all(h for h, _ in self.c.values())
        self.assertIn("**The M3 exit is met.**" if met else "**The M3 exit is not met.**", text)


if __name__ == "__main__":
    unittest.main()
