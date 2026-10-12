"""Audit M2/1 F-M2-17: the I7 probe p_ir03_import_depth exists, its verdicts are recorded, and bend/notes/README.md
records the verdict of every probe in bend/notes (BUILD_PLAN I7 exit "probe verdicts recorded").

p_ir03_import_depth/run.py re-runs every proofs/**/PROOF.bend under bend and --verdict and compares with its
RESULT.json. Two of its verdicts carry the F-M2-07 fix: a proof that imports no law checks vacuously (so the
acceptance points must check the import, holon.mpipeline.law_import_problem), and importing the law makes Bend
demand its proof (an unfilled import is a TODO).
"""
import json
import subprocess
import sys
import unittest

from tests_m2._m2 import ROOT, holon_module

NOTES = ROOT / "bend" / "notes"
PROBE = NOTES / "p_ir03_import_depth"


class TestNotes(unittest.TestCase):
    def test_readme_records_every_probe(self):
        text = (NOTES / "README.md").read_text(encoding="utf-8")
        for p in sorted(NOTES.iterdir()):
            if p.name == "README.md" or p.name.startswith(("_", ".")):
                continue
            with self.subTest(probe=p.name):
                self.assertIn(f"`{p.name}", text)

    def test_import_depth_verdicts_reproduce(self):
        p = subprocess.run([sys.executable, str(PROBE / "run.py")], capture_output=True, text=True, timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-2000:])
        got = json.loads(p.stdout)
        self.assertEqual(got["proofs/a/PROOF.bend"]["bend"]["exit"], 0)
        self.assertEqual(got["proofs/deep/x/PROOF.bend"]["verdict"]["exit"], 0)
        self.assertEqual(got["proofs/noimport/PROOF.bend"]["bend"]["exit"], 0, "an import-less proof checks vacuously")
        self.assertIn("TODO", " ".join(got["proofs/unfilled/PROOF.bend"]["bend"]["errors"]))
        self.assertIn("plain names", " ".join(got["proofs/dotmid/PROOF.bend"]["bend"]["errors"]))
        self.assertIn("TODO", " ".join(got["proofs/law_in_proof/PROOF.bend"]["bend"]["errors"]))

    def test_the_acceptance_check_rejects_the_vacuous_case_and_accepts_the_layout(self):
        mp = holon_module("holon.mpipeline")
        laws = PROBE / "laws" / "a" / "LAWS.bend"
        self.assertIsNotNone(mp.law_import_problem(PROBE / "proofs" / "noimport" / "PROOF.bend", laws))
        self.assertIsNone(mp.law_import_problem(PROBE / "proofs" / "a" / "PROOF.bend", laws))
        self.assertIsNone(mp.law_import_problem(PROBE / "proofs" / "deep" / "x" / "PROOF.bend", laws))

    def test_the_gate_law_scan_finds_the_commented_law(self):
        G = holon_module("holon.gate")
        found = [p.relative_to(PROBE).as_posix() for p in G.laws_in_proofs(PROBE)]
        self.assertEqual(found, ["proofs/law_in_proof/PROOF.bend"])


if __name__ == "__main__":
    unittest.main()
