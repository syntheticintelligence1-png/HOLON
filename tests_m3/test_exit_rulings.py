"""The human's rulings on clauses of the M3 exit (spec/M3/lib/exit_rulings.json; HUMAN_ANSWERS Q43 for E5 and Q44 for
E4).

  X1 every clause listed is one of spec/M3/lib/blind_rerun.json's exit clauses, with that clause's text;
  X2 each ruling names a row of docs/HUMAN_ANSWERS.md that is marked as the human's own and quotes the ruling's words;
  X3 each adjudication is bound to its record. A record kept byte for byte (E5, the blind run) matches its sha256,
     and the scorers' problem counts are the record's. A regenerated record (E4, the back-test table) holds exactly
     the adjudicated exit blockers;
  X4 the paper discloses each adjudicated clause: some line of whitepaper.md names both the ruling's row and the
     clause;
  X5 E4's closing law is M3's real-path law. It is a PAR cross_component_codec law, PROVED, whose premises pin
     version 2 and a zero sequencer-set hash (the M0 law's). The M0 law stays REFUTED, and the table's gap is B5's
     open rule gap, its candidates at version 1.
(Amended for HUMAN_ANSWERS Q44: X3 and X4 were written for E5 alone, and X5 is new.)
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
    return json.loads(Path(p).read_text(encoding="utf-8"))


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
                if "scorers" in r:
                    self.assertEqual(hashlib.sha256(rec.read_bytes()).hexdigest(), r["record_sha256"])
                    lc = load(rec)["leak_checks"]
                    self.assertEqual({k: v["problems"] for k, v in r["scorers"].items()},
                                     {k: len(lc[COUNT[k]]) for k in r["scorers"]})
                else:
                    self.assertEqual(load(rec)["exit_blockers"], r["blockers"])
                    self.assertTrue(r["blockers"], "an adjudication of no blocker adjudicates nothing")

    def test_x4_disclosed(self):
        paper = (ROOT / "whitepaper.md").read_text(encoding="utf-8").splitlines()
        for name, r in load(RULINGS)["clauses"].items():
            with self.subTest(clause=name):
                q = r["ruling"].split(" ", 1)[1]
                self.assertTrue([x for x in paper if f"`docs/HUMAN_ANSWERS.md` {q}" in x and name in x],
                                f"no line of whitepaper.md names both HUMAN_ANSWERS {q} and {name}")

    def test_x5_e4_real_path_law(self):
        r = load(RULINGS)["clauses"]["E4"]
        law, rec = load(ROOT / "laws" / "M3" / f"{r['law']}.json"), load(ROOT / "results" / "M3" / f"{r['law']}.json")
        self.assertEqual((law["rule"], law["subform"], rec["status"], r["law_status"]),
                         ("PAR", "cross_component_codec", "PROVED", "PROVED"))
        assume = law["statement"]["assume"]
        self.assertIn({"eq": [{"field": "version", "of": {"var": "k"}}, {"bytes": "0x02"}]}, assume)
        self.assertIn({"eq": [{"field": "BatchHeaderV0.SequencerSetVerifyHash", "of": {"var": "h"}},
                              {"bytes": "0x" + "00" * 32}]}, assume)
        self.assertEqual(load(ROOT / "results" / "M0" / "L_par_hdr_v2.json")["status"], "REFUTED")
        gap = {g["id"]: g for g in load(ROOT / r["record"])["gaps"]}["gap:M0:L_par_hdr_v2"]
        self.assertEqual((gap["kind"], gap["status"]), ("rule", "open"))
        self.assertEqual(gap["candidates"],
                         ["L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1", "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned"])
        self.assertIn(r["law"], Q.human_row(ROOT, r["ruling"]))


if __name__ == "__main__":
    unittest.main()
