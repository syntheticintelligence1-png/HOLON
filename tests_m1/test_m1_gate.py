"""M1: the gate passes on the committed tree, rejects every canary, and catches tampering."""
import json
import shutil
import unittest
from pathlib import Path

from tests._util import config, copy_repo, load_json, run_holon, validate


def run_gate(repo: Path):
    report = repo / "gate_report_m1.json"
    p = run_holon(["gate", "--milestone", "M1", "--root", str(repo), "--report", str(report)], cwd=repo)
    return p, (load_json(report) if report.exists() else None)


def proved_dir(repo: Path) -> Path:
    rec = load_json(repo / "results" / "M1" / "L_undo_CSR.json")
    p = Path(rec["artifacts"]["proof"])
    return (p if p.is_absolute() else repo / p).parent


class TestM1Gate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.proc, cls.report = run_gate(cls.repo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_gate_passes(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout[-3000:] + self.proc.stderr[-2000:])
        validate(self.report, "gate_report")
        self.assertEqual(self.report["bend_version"], config()["bend"]["pinned_version"])
        for g, c in self.report["checks"].items():
            self.assertTrue(c["passed"], f"{g}: {c['detail']}")

    def test_canaries(self):
        from holon.mpipeline import CompiledMachine
        cm = CompiledMachine.build(Path(__file__).resolve().parents[1] / "spec" / "M1" / "facts" / "morph_rollup.json")
        cans = self.report["canaries"]
        self.assertGreaterEqual(len(cans), 10)
        self.assertGreaterEqual(len({c["kind"] for c in cans}), 3)
        for c in cans:
            if c["law"].get("ir_version") != "holon-ir/0.2":
                # ir/0.1 (PAR) canaries are validated inside the gate itself
                continue
            with self.subTest(canary=c["id"]):
                self.assertTrue(c["rejected"])
                ev = cm.evaluate(c["law"], c["counterexample"])
                if c.get("negated", c["kind"] == "negated"):
                    self.assertTrue(all(ev["premises"]) and all(ev["claims"]), "negated canary: the law holds here")
                else:
                    self.assertTrue(all(ev["premises"]))
                    self.assertFalse(all(ev["claims"]), "the counterexample must falsify the canary")


class TestM1GateTamper(unittest.TestCase):
    def check(self, edit, must_fail):
        repo = copy_repo()
        try:
            edit(repo)
            p, rep = run_gate(repo)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIsNotNone(rep)
        for g in must_fail:
            self.assertFalse(rep["checks"][g]["passed"], g)

    def test_hole(self):
        def e(repo):
            f = proved_dir(repo) / "PROOF.bend"
            f.write_text(f.read_text() + "\ndef extra_hole(x: Nat) -> Nat:\n  ?TODO\n")
        self.check(e, ["G3", "G5"])

    def test_statement_edited(self):
        def e(repo):
            f = repo / "laws" / "M1" / "L_undo_CSR.json"
            law = json.loads(f.read_text())
            law["statement"]["assume"] = []
            f.write_text(json.dumps(law, indent=2))
        self.check(e, ["G2"])

    def test_vacuous(self):
        def e(repo):
            d = proved_dir(repo)
            (d / "LAWS.bend").write_text("import Base\n")
            (d / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
        self.check(e, ["G11"])

    def test_bunfig(self):
        self.check(lambda repo: (repo / "bunfig.toml").write_text('preload = ["./x.ts"]\n'), ["GENV"])


if __name__ == "__main__":
    unittest.main()
