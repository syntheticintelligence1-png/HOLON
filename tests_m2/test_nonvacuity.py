"""I3: every premised PROVED law has a kernel-checked inhabitant (G11V); REFUTED witnesses count."""
import copy
import re
import shutil
import unittest
from pathlib import Path

from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, laws, load_json, records, run_holon
from tests._util import run_bend


def premised(law: dict) -> bool:
    return bool(law["statement"].get("assume"))


def nonvac_dir(rec: dict) -> Path:
    p = Path(rec["non_vacuity"]["law"])
    p = p if p.is_absolute() else ROOT / p
    return p.parent


class TestNonVacuity(unittest.TestCase):
    def test_every_record_has_a_non_vacuity_status(self):
        for m in MILESTONES:
            ls = laws(m)
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    nv = rec["non_vacuity"]
                    self.assertEqual(nv["parent_statement_hash"], rec["statement_hash"])
                    if not premised(ls[lid]):
                        self.assertEqual(nv["status"], "no_premises")
                    elif rec["status"] == "REFUTED":
                        self.assertEqual(nv["status"], "counter_witness")
                    elif rec["status"] == "PROVED":
                        self.assertEqual(nv["status"], "inhabited", nv)

    def test_inhabitants_check_and_state_one_law(self):
        n = 0
        for m in MILESTONES:
            for lid, rec in records(m).items():
                if rec["non_vacuity"]["status"] != "inhabited":
                    continue
                n += 1
                with self.subTest(law=lid):
                    d = nonvac_dir(rec)
                    names = re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", (d / "LAWS.bend").read_text(), re.M)
                    self.assertEqual(names, ["nv_" + lid.lower()])
                    code, out = run_bend([str(d / "PROOF.bend")])
                    self.assertEqual(code, 0, out[-800:])
                    self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
        self.assertEqual(n, 9, "5 premised PROVED M0 laws + 4 premised PROVED M1 laws")

    def test_m1_inhabitant_premises_are_the_parents(self):
        B = holon_module("holon.bindings")
        for lid, rec in records("M1").items():
            if rec["non_vacuity"]["status"] != "inhabited":
                continue
            with self.subTest(law=lid):
                law = laws("M1")[lid]
                parent = B.statement_text(law, "M1", ROOT)
                want = re.findall(r"^\s+for h\d+: (\{.*\})\s*$", parent, re.M)
                text = (nonvac_dir(rec) / "LAWS.bend").read_text()
                body = text[text.index(f"law nv_{lid.lower()}:"):]
                got = re.findall(r"^\s+(?:exs c\d+: )?(\{.*\})\s*$", body, re.M)
                self.assertEqual(got, want)

    def test_m0_inhabitants_are_pin_headers(self):
        facts = load_json(ROOT / "facts" / "morph_header.json")
        F = holon_module("holon.facts")
        widths = F.widths(facts)
        ls = laws("M0")
        for lid, rec in records("M0").items():
            law = ls[lid]
            if not premised(law):
                continue
            with self.subTest(law=lid):
                nv = rec["non_vacuity"]
                if rec["status"] == "REFUTED":
                    self.assertEqual(nv["status"], "counter_witness")
                    continue
                self.assertEqual(nv["status"], "inhabited")
                pins = {}
                for p in law["statement"]["assume"]:
                    a, b = p["eq"]
                    f, v = (a, b) if "field" in a else (b, a)
                    pins[f["field"]] = v["bytes"]
                h = nv["witness"]["h"]
                for name, w in widths.items():
                    self.assertEqual(h[name], pins.get(name, "0x" + "00" * w), name)

    def test_undo_inhabitants_are_non_degenerate(self):
        for lid in ("L_undo_CSR", "L_undo_BD"):
            with self.subTest(law=lid):
                nv = records("M1")[lid]["non_vacuity"]
                self.assertEqual(nv["status"], "inhabited")
                self.assertIs(nv["degenerate"], False)
                self.assertNotEqual(nv["witness"]["s1"], nv["witness"]["s2"])

    def test_disch_inhabitants_are_reachable(self):
        for lid in ("L_disch_stale", "L_disch_stale_commit"):
            with self.subTest(law=lid):
                nv = records("M1")[lid]["non_vacuity"]
                self.assertEqual(nv["status"], "inhabited")
                self.assertIs(nv["reachable"], True)
                self.assertEqual(set(nv["witness"]["s"]), {"run"})

    def test_contradictory_premises_are_unknown(self):
        I = holon_module("holon.inhabit")
        from holon import bend
        from holon.mpipeline import CompiledMachine
        law = copy.deepcopy(laws("M1")["L_disch_stale_commit"])
        law["law_id"] = "L_vacuous_fixture"
        law["statement"]["assume"] = [
            {"eq": [{"fn": "is_commitBatch", "args": [{"var": "a"}]}, {"bool": True}]},
            {"eq": [{"fn": "is_wait", "args": [{"var": "a"}]}, {"bool": True}]},
        ]
        cfg = bend.config(ROOT)
        cm = CompiledMachine.build(ROOT / law["facts"], cfg)
        import tempfile
        out = Path(tempfile.mkdtemp(prefix="holon-nv-"))
        try:
            rec = {"law_id": law["law_id"], "status": "PROVED", "statement_hash": "sha256:" + "0" * 64}
            nv = I.inhabit(law, "M1", ROOT, out, cfg, cm=cm, rec=rec)
            self.assertEqual(nv["status"], "unknown")
            self.assertTrue(nv["bound"])
            self.assertFalse((out / "nonvac" / "PROOF.bend").exists())
        finally:
            shutil.rmtree(out, ignore_errors=True)


def gate(repo: Path, m: str, checks: str):
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


class TestG11V(unittest.TestCase):
    def test_g11v_passes(self):
        repo = copy_repo()
        try:
            for m in MILESTONES:
                with self.subTest(milestone=m):
                    p, rep = gate(repo, m, "G11V")
                    self.assertIsNotNone(rep, p.stdout[-1000:] + p.stderr[-1000:])
                    self.assertTrue(rep["checks"]["G11V"]["passed"], rep["checks"]["G11V"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_broken_inhabitant_fails_g11v(self):
        repo = copy_repo()
        try:
            f = repo / "gen" / "M1" / "L_undo_CSR" / "nonvac" / "PROOF.bend"
            f.write_text(f.read_text().replace("{==}", "{==}{==}", 1))
            p, rep = gate(repo, "M1", "G11V")
            self.assertFalse(rep["checks"]["G11V"]["passed"])
            self.assertIn("L_undo_CSR", rep["checks"]["G11V"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_missing_inhabitant_fails_g11v(self):
        repo = copy_repo()
        try:
            shutil.rmtree(repo / "gen" / "M0" / "L_par_hdr_v1" / "nonvac")
            p, rep = gate(repo, "M0", "G11V")
            self.assertFalse(rep["checks"]["G11V"]["passed"])
            self.assertIn("L_par_hdr_v1", rep["checks"]["G11V"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_inhabitant_with_a_dropped_premise_fails_g11v(self):
        repo = copy_repo()
        try:
            f = repo / "gen" / "M1" / "L_disch_stale" / "nonvac" / "LAWS.bend"
            lines = f.read_text().splitlines()
            i = next(k for k, l in enumerate(lines) if l.strip().startswith("exs c0:"))
            del lines[i]
            f.write_text("\n".join(lines) + "\n")
            p, rep = gate(repo, "M1", "G11V")
            self.assertFalse(rep["checks"]["G11V"]["passed"])
            self.assertIn("L_disch_stale", rep["checks"]["G11V"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
