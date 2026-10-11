"""I3 follow-up: checks added after the adversarial review of I3 (not part of the I3 preregistration)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json


def gate(repo: Path, m: str, checks: str):
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


class TestG11VRegenerates(unittest.TestCase):
    def failed(self, m: str, edit, needle: str) -> dict:
        repo = copy_repo()
        try:
            edit(repo)
            p, rep = gate(repo, m, "G11V")
            self.assertIsNotNone(rep, p.stdout[-1000:] + p.stderr[-1000:])
            g = rep["checks"]["G11V"]
            self.assertFalse(g["passed"], g["detail"])
            self.assertIn(needle, g["detail"])
            return g
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_commented_out_pins_fail(self):
        def edit(repo):
            d = repo / "gen" / "M0" / "L_par_hdr_v0" / "nonvac"
            text = (d / "LAWS.bend").read_text()
            lines = [("# " + l.strip()) if "M.get_" in l else l for l in text.splitlines()]
            lines.append("  {True{} == True{} : Bool}")
            (d / "LAWS.bend").write_text("\n".join(lines) + "\n")
        self.failed("M0", edit, "L_par_hdr_v0")

    def test_extra_model_file_fails(self):
        def edit(repo):
            d = repo / "gen" / "M1" / "L_disch_stale" / "nonvac"
            shutil.copy(repo / "gen" / "M1" / "model" / "morph_rollup.bend", d / "m.bend")
        self.failed("M1", edit, "L_disch_stale")

    def test_swapped_model_import_fails(self):
        def edit(repo):
            d = repo / "gen" / "M1" / "L_disch_stale" / "nonvac"
            for f in ("LAWS.bend", "PROOF.bend"):
                t = (d / f).read_text().replace("../../model/morph_rollup.bend", "../../model/./morph_rollup.bend")
                (d / f).write_text(t)
        self.failed("M1", edit, "L_disch_stale")

    def test_proof_not_of_the_recorded_witness_fails(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_disch_stale_commit.json"
            d = load_json(f)
            d["non_vacuity"]["witness"]["s"] = {"run": []}
            write_json(f, d)
        self.failed("M1", edit, "L_disch_stale_commit")

    def test_unreachable_inhabitant_fails(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_undo_CSR.json"
            d = load_json(f)
            d["non_vacuity"]["reachable"] = False
            write_json(f, d)
        self.failed("M1", edit, "reachable")


class TestUndoInhabitantsAreReachable(unittest.TestCase):
    def test_both_undo_inhabitants_are_reachable_pairs(self):
        for lid in ("L_undo_CSR", "L_undo_BD"):
            with self.subTest(law=lid):
                nv = load_json(ROOT / "results" / "M1" / f"{lid}.json")["non_vacuity"]
                self.assertIs(nv["reachable"], True)
                self.assertIs(nv["degenerate"], False)
                self.assertEqual(set(nv["witness"]["s1"]), {"run"})
                self.assertEqual(set(nv["witness"]["s2"]), {"run"})


class TestZeroBlobCommit(unittest.TestCase):
    def test_non_checkout_is_not_checked_against_the_target(self):
        Z = holon_module("holon.oracles.zero_blob")
        tmp = Path(tempfile.mkdtemp(prefix="holon-zb2-"))
        try:
            for rel in (Z.SOL_PATH, Z.GO_PATH):
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(Path("/root/work/morph") / rel if (Path("/root/work/morph") / rel).exists()
                            else ROOT / "README.md", tmp / rel)
            h = Z.check(tmp)
            self.assertEqual(h["status"], "mismatch")
            self.assertIsNone(h["checkout_commit"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestG1IgnoresRunLogs(unittest.TestCase):
    def test_gate_logs_do_not_affect_g1(self):
        repo = copy_repo()
        try:
            (repo / "results" / "M0" / "gate_timing.json").write_text('{"G5": {"x": 999}}\n')
            (repo / "results" / "M0" / "gate_report.json").write_text('{"junk": true}\n')
            p, rep = gate(repo, "M0", "G1")
            self.assertTrue(rep["checks"]["G1"]["passed"], rep["checks"]["G1"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
