"""Bend is installed, pinned, and behaves the way docs/BEND_PRIMER.md says (P0 gate)."""
import re
import unittest

from tests._util import ROOT, config, load_json, run_bend

PROBES = ROOT / "bend" / "probes"


class TestBendProbes(unittest.TestCase):
    def test_version_is_pinned(self):
        code, out = run_bend(["version"])
        self.assertEqual(code, 0, out)
        m = re.search(r"bend (\d+\.\d+\.\d+)", out)
        self.assertIsNotNone(m, out)
        self.assertEqual(m.group(1), config()["bend"]["pinned_version"],
                         "installed bend differs from config/holon.json pinned_version; rerun the probes and update the pin")

    def test_probes(self):
        man = load_json(PROBES / "manifest.json")
        for p in man["probes"]:
            with self.subTest(probe=p["id"]):
                cwd = PROBES / p["dir"] if p["dir"] else PROBES
                code, out = run_bend([p["file"]], cwd=cwd)
                self.assertEqual(code, p["expect_exit"], f"{p['id']}: {out[:800]}")
                self.assertEqual(out.strip().splitlines()[0].strip(), p["expect_first_line"], out[:400])
                if p["expect_contains"]:
                    self.assertIn(p["expect_contains"], out)


if __name__ == "__main__":
    unittest.main()
