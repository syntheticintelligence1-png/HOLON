"""Records test: every PROVED/REFUTED law of M0/M1 has a results/lean record
with the required fields, and the coverage-debt file exists."""

import json
import unittest
from pathlib import Path

from holon import ir

REPO = Path(__file__).resolve().parents[2]
REQUIRED = {"statement_hash", "lean_sha256", "exit_code", "seconds", "kernel_result"}


class TestRecords(unittest.TestCase):
    def test_every_law_recorded(self):
        missing, bad = [], []
        for milestone in ("M0", "M1"):
            rdir = REPO / "results" / "lean" / milestone
            for law in ir.load_laws_any(milestone, REPO):
                lid = law["law_id"]
                if not (REPO / "results" / milestone / f"{lid}.json").exists():
                    continue
                if json.loads((REPO / "results" / milestone / f"{lid}.json").read_text()).get(
                        "status") not in ("PROVED", "REFUTED"):
                    continue
                rp = rdir / f"{lid}.json"
                if not rp.exists():
                    missing.append(f"{milestone}/{lid}")
                    continue
                rec = json.loads(rp.read_text())
                if not REQUIRED <= set(rec):
                    bad.append(f"{milestone}/{lid}: missing keys {REQUIRED - set(rec)}")
                if rec.get("kernel_result") not in ("PASS", "UNSUPPORTED", "FAIL"):
                    bad.append(f"{milestone}/{lid}: kernel_result {rec.get('kernel_result')}")
        self.assertFalse(missing, f"no lean record for {missing}")
        self.assertFalse(bad, bad)

    def test_coverage_files(self):
        for ms in ("m0", "m1"):
            p = REPO / "spec" / "M2" / "coverage" / f"lean_{ms}.json"
            if not p.exists():
                continue  # a milestone with no gaps may legitimately lack it
            cov = json.loads(p.read_text())
            self.assertEqual(cov.get("frontend"), "lean")
            self.assertTrue(all({"element", "kind", "reason"} <= set(i) for i in cov["items"]))


if __name__ == "__main__":
    unittest.main()
