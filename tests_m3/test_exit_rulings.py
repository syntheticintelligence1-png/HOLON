"""The human's rulings on clauses of the M3 exit (spec/M3/lib/exit_rulings.json; HUMAN_ANSWERS Q43 for E5).

  X1 every clause listed is one of spec/M3/lib/blind_rerun.json's exit clauses, with that clause's text;
  X2 each ruling names a row of docs/HUMAN_ANSWERS.md that is marked as the human's own and quotes the ruling's words;
  X3 each record's sha256 is the committed file's, and the scorers' problem counts are the record's;
  X4 the paper discloses each adjudicated clause's ruling (whitepaper.md, the L8 row for the blind rerun's E5).
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tests_m3 import _q42 as Q

ROOT = Path(__file__).resolve().parents[1]
RULINGS = ROOT / "spec" / "M3" / "lib" / "exit_rulings.json"
PROTOCOL = ROOT / "spec" / "M3" / "lib" / "blind_rerun.json"
COUNT = {"preregistered": "calls_problems", "amended": "reads_problems"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


class TestExitRulings(unittest.TestCase):
    def test_x1_clauses(self):
        clauses = load(PROTOCOL)["exit"]["clauses"]
        for name, r in load(RULINGS)["clauses"].items():
            with self.subTest(clause=name):
                self.assertIn(name, clauses)
                self.assertEqual(r["clause"], clauses[name])
                self.assertIs(r["holds"], True)
                self.assertEqual(r["by"], "adjudication")

    def test_x2_rulings_are_the_humans(self):
        for name, r in load(RULINGS)["clauses"].items():
            with self.subTest(clause=name):
                row = Q.human_row(ROOT, r["ruling"])
                self.assertIsNotNone(row, f"{r['ruling']} is no row of docs/HUMAN_ANSWERS.md marked as the human's own")
                self.assertIn(r["words"], row)

    def test_x3_records(self):
        for name, r in load(RULINGS)["clauses"].items():
            with self.subTest(clause=name):
                rec = ROOT / r["record"]
                self.assertEqual(hashlib.sha256(rec.read_bytes()).hexdigest(), r["record_sha256"])
                lc = load(rec)["leak_checks"]
                self.assertEqual({k: v["problems"] for k, v in r["scorers"].items()},
                                 {k: len(lc[COUNT[k]]) for k in r["scorers"]})

    def test_x4_disclosed(self):
        paper = (ROOT / "whitepaper.md").read_text(encoding="utf-8").splitlines()
        l8 = [x for x in paper if x.startswith("| L8 |")]
        self.assertEqual(len(l8), 1)
        for name, r in load(RULINGS)["clauses"].items():
            with self.subTest(clause=name):
                q = r["ruling"].split(" ", 1)[1]
                self.assertIn(f"`docs/HUMAN_ANSWERS.md` {q}", l8[0])
                self.assertIn(name, l8[0])


if __name__ == "__main__":
    unittest.main()
